from __future__ import annotations

import json
from typing import Any

from app.core.configuration_conflicts import detect_configuration_conflicts
from app.models.technical import TechnicalChange
from app.services.impact import build_component_impact, build_file_impact


WEAK_SCOPES = {"test", "example", "vendor", "generated", "subproject", "documentation"}
RUNTIME_FACTS = {
    "python.required_version": ("runtime", "Python", "version_changed"),
    "node.required_version": ("runtime", "Node.js", "version_changed"),
    "docker.base_image": ("runtime", "Docker", "base_image_changed"),
    "ci.python_version": ("runtime", "Python", "ci_runtime_changed"),
    "ci.node_version": ("runtime", "Node.js", "ci_runtime_changed"),
    "cmake.minimum_version": ("build", "CMake", "minimum_version_changed"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _scope(value: dict[str, Any]) -> str | None:
    return value.get("scope") if isinstance(value, dict) else None


def _evidence(value: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    return sorted(value.get("evidence", []), key=lambda item: (
        item.get("file", ""), item.get("line") or 0, item.get("reason", ""),
    ))


def _make_change(
    *, category: str, subject: str, change_type: str, before: Any = None,
    after: Any = None, before_evidence: list[dict[str, Any]] | None = None,
    after_evidence: list[dict[str, Any]] | None = None, scopes: set[str] | None = None,
    confidence: float = 1.0, affected_elements: list[str] | None = None,
) -> dict[str, Any]:
    change = TechnicalChange(
        category=category,
        subject=subject,
        change_type=change_type,
        before=before,
        after=after,
        evidence={"before": before_evidence or [], "after": after_evidence or []},
        scopes=sorted(scopes or set()),
        confidence=confidence,
        affected_elements=sorted(set(affected_elements or [])),
    )
    return change.model_dump() if hasattr(change, "model_dump") else change.dict()


def _fact_changes(diff: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    fact_items = list(diff.get("changed", []))
    fact_items.extend({"before": {}, "after": item} for item in diff.get("added", []))
    fact_items.extend({"before": item, "after": {}} for item in diff.get("removed", []))
    for item in fact_items:
        before = item.get("before", {})
        after = item.get("after", {})
        fact_type = after.get("type") or before.get("type")
        definition = RUNTIME_FACTS.get(fact_type)
        if definition is None:
            continue
        category, subject, change_type = definition
        scopes = {_scope(before), _scope(after)} - {None} - WEAK_SCOPES
        if not scopes:
            continue
        changes.append(_make_change(
            category=category,
            subject=subject,
            change_type=change_type,
            before=before.get("value"),
            after=after.get("value"),
            before_evidence=_evidence(before),
            after_evidence=_evidence(after),
            scopes=scopes,
            confidence=min(before.get("confidence", 0.0), after.get("confidence", 0.0)),
        ))
    return changes


def _conflict_signature(conflict: dict[str, Any]) -> str:
    return _canonical({
        "subject": conflict.get("subject"),
        "compatibility": conflict.get("compatibility"),
        "observations": conflict.get("observations", []),
    })


def _conflict_changes(base: dict[str, Any], target: dict[str, Any]) -> list[dict[str, Any]]:
    before = {
        _conflict_signature(item): item
        for item in detect_configuration_conflicts(base.get("facts", []))
    }
    after = {
        _conflict_signature(item): item
        for item in detect_configuration_conflicts(target.get("facts", []))
    }
    introduced = set(after) - set(before)
    resolved = set(before) - set(after)
    changes = []
    paired = []
    for new_signature in sorted(introduced):
        new_conflict = after[new_signature]
        candidates = [old_signature for old_signature in sorted(resolved) if before[old_signature].get("subject") == new_conflict.get("subject")]
        if len(candidates) == 1:
            old_signature = candidates[0]
            paired.append((old_signature, new_signature))
            resolved.remove(old_signature)
            introduced.remove(new_signature)

    for old_signature, new_signature in paired:
        old_conflict = before[old_signature]
        new_conflict = after[new_signature]
        observations = old_conflict.get("observations", []) + new_conflict.get("observations", [])
        changes.append(_make_change(
            category="configuration_conflict",
            subject=new_conflict.get("subject", "unknown"),
            change_type="conflict_changed",
            before=old_conflict,
            after=new_conflict,
            before_evidence=old_conflict.get("evidence", []),
            after_evidence=new_conflict.get("evidence", []),
            scopes={item.get("scope") for item in observations} - {None} - WEAK_SCOPES,
            confidence=min(old_conflict.get("confidence", 0.0), new_conflict.get("confidence", 0.0)),
        ))

    for signature in sorted(introduced):
        conflict = after[signature]
        observations = conflict.get("observations", [])
        changes.append(_make_change(
            category="configuration_conflict",
            subject=conflict.get("subject", "unknown"),
            change_type="conflict_introduced",
            after=conflict,
            after_evidence=conflict.get("evidence", []),
            scopes={item.get("scope") for item in observations} - {None} - WEAK_SCOPES,
            confidence=conflict.get("confidence", 0.0),
        ))
    for signature in sorted(resolved):
        conflict = before[signature]
        observations = conflict.get("observations", [])
        changes.append(_make_change(
            category="configuration_conflict",
            subject=conflict.get("subject", "unknown"),
            change_type="conflict_resolved",
            before=conflict,
            before_evidence=conflict.get("evidence", []),
            scopes={item.get("scope") for item in observations} - {None} - WEAK_SCOPES,
            confidence=conflict.get("confidence", 0.0),
        ))
    return changes


def _relationship_changes(diff: dict[str, Any], base: dict[str, Any], target: dict[str, Any], component: bool = False) -> list[dict[str, Any]]:
    changes = []
    for change_type, records, graph in (
        ("relationship_added", diff.get("added", []), target),
        ("relationship_removed", diff.get("removed", []), base),
    ):
        for relationship in records:
            scope = relationship.get("scope", "project")
            if scope in WEAK_SCOPES:
                continue
            subject = f"{relationship.get('source')} -> {relationship.get('target')}"
            affected = []
            if component:
                impact = build_component_impact(graph.get("component_graph", {}), relationship.get("target"))
            else:
                impact = build_file_impact(graph.get("repository_graph", {}), relationship.get("target"))
            if impact.get("found"):
                affected = [item["node"] for item in impact.get("direct_dependents", []) + impact.get("transitive_dependents", [])]
            changes.append(_make_change(
                category="component_dependency" if component else "dependency",
                subject=subject,
                change_type=change_type,
                after=relationship if change_type == "relationship_added" else None,
                before=relationship if change_type == "relationship_removed" else None,
                before_evidence=relationship.get("evidence", []) if change_type == "relationship_removed" else [],
                after_evidence=relationship.get("evidence", []) if change_type == "relationship_added" else [],
                scopes={scope},
                confidence=relationship.get("confidence", 0.0),
                affected_elements=affected,
            ))
    return changes


def _component_changes(diff: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for change_type, records in (("component_added", diff.get("added", [])), ("component_removed", diff.get("removed", []))):
        for component in records:
            scope = component.get("scope", "project")
            if scope in WEAK_SCOPES:
                continue
            changes.append(_make_change(
                category="component",
                subject=component.get("id", "unknown"),
                change_type=change_type,
                after=component if change_type == "component_added" else None,
                before=component if change_type == "component_removed" else None,
                before_evidence=component.get("evidence", []) if change_type == "component_removed" else [],
                after_evidence=component.get("evidence", []) if change_type == "component_added" else [],
                scopes={scope},
                confidence=component.get("confidence", 0.0),
            ))
    for item in diff.get("changed", []):
        before = item.get("before", {})
        after = item.get("after", {})
        if before.get("type") == after.get("type"):
            continue
        scopes = {before.get("scope"), after.get("scope")} - {None} - WEAK_SCOPES
        if not scopes:
            continue
        changes.append(_make_change(
            category="component",
            subject=item.get("id", "unknown"),
            change_type="component_type_changed",
            before=before.get("type"),
            after=after.get("type"),
            before_evidence=before.get("evidence", []),
            after_evidence=after.get("evidence", []),
            scopes=scopes,
            confidence=min(before.get("confidence", 0.0), after.get("confidence", 0.0)),
        ))
    return changes


def evaluate_technical_changes(base: dict[str, Any], target: dict[str, Any], diff: dict[str, Any]) -> list[dict[str, Any]]:
    base_data = base.get("snapshot", base)
    target_data = target.get("snapshot", target)
    changes = _fact_changes(diff.get("facts", {}))
    changes.extend(_conflict_changes(base_data, target_data))
    changes.extend(_relationship_changes(diff.get("relationships", {}), base_data, target_data))
    changes.extend(_relationship_changes(diff.get("component_relationships", {}), base_data, target_data, component=True))
    changes.extend(_component_changes(diff.get("components", {})))
    unique = {}
    for change in changes:
        key = _canonical({key: change[key] for key in ("category", "subject", "change_type", "before", "after")})
        unique[key] = change
    return sorted(unique.values(), key=lambda item: (
        item["category"], item["subject"], item["change_type"],
        _canonical(item.get("before")), _canonical(item.get("after")),
    ))