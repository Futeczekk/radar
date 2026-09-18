from __future__ import annotations

from collections import deque
from copy import deepcopy
import re
from typing import Any, Callable

from app.core.repository_identity import normalize_repository_identity
from app.models.map import (
    RepositoryMapEntry,
    RepositoryMapResponse,
    RepositoryRelationship,
    UnresolvedReference,
)
from app.sources.github import GitHubError


class MultiRepositoryMapService:
    """Builds a map from an explicit collection of repository scan results."""

    def __init__(self, scanner: Callable[[str, str | None], dict] | None = None):
        self.scanner = scanner
        self._analysis_cache: dict[tuple[str, str], dict] = {}
        self._request_cache: dict[tuple[str, str | None], dict] = {}

    def _scan(self, url: str, ref: str | None) -> dict:
        if self.scanner is not None:
            return self.scanner(url, ref)
        from app.application.scanning import scan_repository

        return scan_repository(url, ref)

    @staticmethod
    def _error(error: Exception) -> dict[str, str]:
        if isinstance(error, GitHubError):
            return {"code": error.error_type, "message": str(error)}
        if isinstance(error, ValueError):
            return {"code": "SOURCE_RESOLUTION_FAILED", "message": str(error)}
        return {"code": "SCAN_FAILED", "message": str(error)}

    @staticmethod
    def _repository_id(scanned: dict, requested_url: str) -> str:
        snapshot = scanned.get("snapshot", scanned)
        return normalize_repository_identity(snapshot.get("repository") or requested_url) or requested_url.rstrip("/")

    @staticmethod
    def _snapshot_id(repository_id: str, revision: str) -> str:
        return f"{repository_id}@{revision}"

    @staticmethod
    def _immutable_ref(ref: str | None) -> bool:
        return isinstance(ref, str) and re.fullmatch(r"[0-9a-fA-F]{40}", ref) is not None

    @staticmethod
    def _references(scanned: dict) -> list[dict[str, Any]]:
        references = []
        for fact in scanned.get("facts", []):
            if fact.get("type") != "repository.reference":
                continue
            value = fact.get("value")
            if not isinstance(value, dict):
                continue
            references.append({
                "reference": value.get("repository"),
                "value": value.get("raw") or value.get("repository"),
                "path": fact.get("evidence", [{}])[0].get("file", "") if fact.get("evidence") else "",
                "evidence": fact.get("evidence", []),
            })
        return references

    @staticmethod
    def _request_payloads(requests: list[Any]) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for request in requests:
            if hasattr(request, "model_dump"):
                payloads.append(request.model_dump())
            elif hasattr(request, "dict"):
                payloads.append(request.dict())
            elif isinstance(request, dict):
                payloads.append(request)
            else:
                payloads.append({"url": request})
        return payloads

    def build_impact(self, requests: list[Any], target: str) -> dict[str, Any]:
        if not requests:
            raise ValueError("repositories must not be empty")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target repository must not be empty")

        map_result = self.build(self._request_payloads(requests))
        relationships = map_result.get("relationships", [])
        successful = {
            item.get("repository_id"): item
            for item in map_result.get("repositories", [])
            if item.get("status") == "SUCCESS"
        }
        normalized_target = normalize_repository_identity(target) or target.rstrip("/")

        if normalized_target not in successful:
            return {
                "target": normalized_target,
                "found": False,
                "status": map_result.get("status", "COMPLETE"),
                "direct_dependents": [],
                "transitive_dependents": [],
            }

        reverse: dict[str, list[dict[str, Any]]] = {}
        for relationship in relationships:
            target_repository = relationship.get("target_repository")
            if not target_repository:
                continue
            reverse.setdefault(target_repository, []).append(relationship)
        for relationships_for_target in reverse.values():
            relationships_for_target.sort(key=lambda item: (item.get("source_repository", ""), item.get("target_repository", ""), item.get("type", "")))

        queue: deque[tuple[str, list[str], list[dict[str, Any]]]] = deque([(normalized_target, [normalized_target], [])])
        best: dict[str, dict[str, Any]] = {}

        while queue:
            current, path, evidence_chain = queue.popleft()
            for relationship in reverse.get(current, []):
                dependent = relationship.get("source_repository")
                if not dependent or dependent == normalized_target or dependent in path:
                    continue
                next_path = [dependent] + path
                next_evidence = [relationship] + evidence_chain
                distance = len(next_path) - 1
                current_best = best.get(dependent)
                if current_best is None or distance < current_best["distance"] or (distance == current_best["distance"] and tuple(next_path) < tuple(current_best["path"])):
                    best[dependent] = {
                        "repository": dependent,
                        "distance": distance,
                        "path": next_path,
                        "evidence": next_evidence,
                    }
                    queue.append((dependent, next_path, next_evidence))

        direct_dependents: list[dict[str, Any]] = []
        transitive_dependents: list[dict[str, Any]] = []
        for repository in sorted(best):
            item = best[repository]
            impact_item = {
                "repository": repository,
                "distance": item["distance"],
                "path": item["path"],
                "evidence": [
                    {
                        "source_repository": evidence.get("source_repository"),
                        "target_repository": evidence.get("target_repository"),
                        "evidence": [
                            {
                                key: value
                                for key, value in record.items()
                                if key not in {"source_repository", "snapshot_id", "kind", "value"}
                            }
                            for record in evidence.get("evidence", [])
                        ],
                    }
                    for evidence in item["evidence"]
                ],
            }
            if item["distance"] == 1:
                direct_dependents.append(impact_item)
            else:
                transitive_dependents.append(impact_item)

        direct_dependents.sort(key=lambda item: item["repository"])
        transitive_dependents.sort(key=lambda item: item["repository"])

        return {
            "target": normalized_target,
            "found": True,
            "status": map_result.get("status", "COMPLETE"),
            "direct_dependents": direct_dependents,
            "transitive_dependents": transitive_dependents,
        }

    def build(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_requests = self._request_payloads(requests)
        if not normalized_requests:
            raise ValueError("repositories must not be empty")

        entries: list[RepositoryMapEntry] = []
        successful: dict[str, tuple[RepositoryMapEntry, dict]] = {}
        failures: list[RepositoryMapEntry] = []
        seen_request_keys: set[tuple[str, str | None]] = set()
        duplicate_conflicts: list[RepositoryMapEntry] = []

        for request in normalized_requests:
            url = request.get("url")
            ref = request.get("ref")
            identity = normalize_repository_identity(url) if isinstance(url, str) else None
            if identity is None:
                entry = RepositoryMapEntry(
                    repository_id=url or "unknown",
                    requested_url=url or "",
                    requested_ref=ref,
                    status="FAILED",
                    error={"code": "SOURCE_RESOLUTION_FAILED", "message": "Unsupported repository URL"},
                )
                failures.append(entry)
                continue
            request_key = (identity, ref)
            if request_key in seen_request_keys:
                continue
            seen_request_keys.add(request_key)
            try:
                if self._immutable_ref(ref) and request_key in self._request_cache:
                    scanned = deepcopy(self._request_cache[request_key])
                else:
                    scanned = self._scan(url, ref)
                snapshot = scanned.get("snapshot", scanned)
                revision = snapshot.get("commit_sha")
                if not revision:
                    raise ValueError("Snapshot has no resolved immutable revision")
                repository_id = self._repository_id(scanned, url)
                cache_key = (repository_id, revision)
                if cache_key in self._analysis_cache:
                    scanned = deepcopy(self._analysis_cache[cache_key])
                else:
                    self._analysis_cache[cache_key] = deepcopy(scanned)
                if self._immutable_ref(ref):
                    self._request_cache[request_key] = deepcopy(scanned)
                if repository_id in successful:
                    existing_entry, _ = successful[repository_id]
                    if existing_entry.resolved_revision != revision:
                        duplicate_conflicts.append(RepositoryMapEntry(
                            repository_id=repository_id,
                            requested_url=url,
                            requested_ref=ref,
                            resolved_revision=revision,
                            snapshot_id=self._snapshot_id(repository_id, revision),
                            status="CONFLICT",
                            error={"code": "DUPLICATE_REPOSITORY_CONFLICT", "message": "Repository resolved to multiple snapshots"},
                        ))
                    continue
                entry = RepositoryMapEntry(
                    repository_id=repository_id,
                    requested_url=url,
                    requested_ref=ref,
                    resolved_revision=revision,
                    snapshot_id=self._snapshot_id(repository_id, revision),
                    status="SUCCESS",
                )
                successful[repository_id] = (entry, scanned)
                entries.append(entry)
            except Exception as error:
                entry = RepositoryMapEntry(
                    repository_id=identity,
                    requested_url=url,
                    requested_ref=ref,
                    status="FAILED",
                    error=self._error(error),
                )
                failures.append(entry)

        entries.extend(failures)
        entries.extend(duplicate_conflicts)
        entries.sort(key=lambda item: (item.repository_id, item.requested_ref or "", item.status))
        collection_identities = {item.repository_id for item in entries}
        identities = {item.repository_id for item in entries if item.status == "SUCCESS"}
        relationships: dict[tuple[str, str, str], RepositoryRelationship] = {}
        unresolved: dict[tuple[str, str, str, str], UnresolvedReference] = {}

        for source_id, (entry, scanned) in successful.items():
            for reference in self._references(scanned):
                target = normalize_repository_identity(reference.get("reference"))
                if target is None:
                    reason = "UNRESOLVED"
                elif target not in collection_identities:
                    reason = "OUTSIDE_COLLECTION"
                elif target not in identities:
                    reason = "TARGET_UNAVAILABLE"
                else:
                    target_entry = next(item for item in entries if item.repository_id == target and item.status == "SUCCESS")
                    if target_entry.resolved_revision is None:
                        reason = "TARGET_UNAVAILABLE"
                    else:
                        key = (source_id, target, "repository_dependency")
                        current = relationships.get(key)
                        evidence = list((current.evidence if current else []))
                        for item in reference.get("evidence", []):
                            evidence.append({
                                **item,
                                "source_repository": source_id,
                                "snapshot_id": entry.snapshot_id,
                                "kind": "git_repository_reference",
                                "value": reference.get("value"),
                            })
                        deduped = {str(item): item for item in evidence}
                        relationships[key] = RepositoryRelationship(
                            source_repository=source_id,
                            target_repository=target,
                            type="repository_dependency",
                            evidence=sorted(deduped.values(), key=lambda item: (item.get("file", ""), item.get("line") or 0, item.get("reason", ""))),
                        )
                        continue
                unresolved_key = (source_id, str(reference.get("reference")), reference.get("path", ""), reason)
                unresolved[unresolved_key] = UnresolvedReference(
                    source_repository=source_id,
                    target_reference=str(reference.get("reference")),
                    path=reference.get("path", ""),
                    reason=reason,
                    value=str(reference.get("value")),
                )

        relationship_values = sorted(relationships.values(), key=lambda item: (item.source_repository, item.target_repository, item.type))
        dependent_map = {identity: [] for identity in identities}
        dependency_map = {identity: [] for identity in identities}
        for relationship in relationship_values:
            dependency_map[relationship.source_repository].append(relationship.target_repository)
            dependent_map[relationship.target_repository].append(relationship.source_repository)
        for entry in entries:
            if entry.status == "SUCCESS":
                entry.dependencies = sorted(dependency_map[entry.repository_id])
                entry.dependents = sorted(dependent_map[entry.repository_id])

        status = "COMPLETE" if not failures and not duplicate_conflicts else "PARTIAL" if successful else "FAILED"
        result = RepositoryMapResponse(
            status=status,
            repositories=entries,
            relationships=relationship_values,
            unresolved_references=sorted(unresolved.values(), key=lambda item: (item.source_repository, item.path, item.target_reference, item.reason)),
        )
        return result.model_dump() if hasattr(result, "model_dump") else result.dict()