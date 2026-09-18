import json

import httpx
import pytest

from app.core.repository_identity import normalize_repository_identity
from app.api.scan import router
from app.main import app
from app.models.map import MapRequest
from app.services.repository_map import MultiRepositoryMapService


def scanned(repository, revision, facts=None):
    return {
        "repository": repository,
        "ref": "main",
        "commit_sha": revision,
        "facts": facts or [],
        "snapshot": {
            "repository": repository,
            "ref": "main",
            "commit_sha": revision,
            "facts": facts or [],
        },
    }


def reference(path, value):
    return {
        "type": "repository.reference",
        "subject": "Repository",
        "value": {"repository": value, "raw": value, "dependency": "shared"},
        "confidence": 1.0,
        "evidence": [{"file": path, "line": 1, "snippet": None, "reason": "explicit repository URL"}],
        "scope": "project",
        "source_type": "manifest",
        "environment": "build",
    }


def test_repository_identity_is_exact_and_ref_independent():
    assert normalize_repository_identity("git+https://GitHub.com/acme/shared.git") == "https://github.com/acme/shared"
    assert normalize_repository_identity("git@github.com:acme/shared.git") == "https://github.com/acme/shared"
    assert normalize_repository_identity("https://github.com/acme/shared?ref=main") is None
    assert normalize_repository_identity("shared") is None


def test_explicit_reference_creates_one_edge_with_dependencies_and_dependents():
    calls = []
    values = {
        "https://github.com/acme/a": scanned("acme/a", "a1", [reference("package.json", "git+https://github.com/acme/b.git")]),
        "https://github.com/acme/b": scanned("acme/b", "b1"),
    }

    def scan(url, ref):
        calls.append(url)
        return values[url]

    result = MultiRepositoryMapService(scan).build([
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/b", "ref": "main"},
    ])

    assert result["status"] == "COMPLETE"
    assert len(result["relationships"]) == 1
    edge = result["relationships"][0]
    assert edge["source_repository"] == "https://github.com/acme/a"
    assert edge["target_repository"] == "https://github.com/acme/b"
    assert edge["evidence"]
    entries = {item["repository_id"]: item for item in result["repositories"]}
    assert entries["https://github.com/acme/a"]["dependencies"] == ["https://github.com/acme/b"]
    assert entries["https://github.com/acme/b"]["dependents"] == ["https://github.com/acme/a"]
    assert calls == ["https://github.com/acme/a", "https://github.com/acme/b"]


def test_names_without_explicit_reference_do_not_create_edges_and_outside_is_unresolved():
    values = {
        "https://github.com/acme/a": scanned("acme/a", "a1", [reference("package.json", "https://github.com/acme/outside.git")]),
        "https://github.com/acme/b": scanned("acme/b", "b1"),
    }
    result = MultiRepositoryMapService(lambda url, ref: values[url]).build([
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/b", "ref": "main"},
    ])

    assert result["relationships"] == []
    assert result["unresolved_references"][0]["reason"] == "OUTSIDE_COLLECTION"


def test_order_permutation_and_duplicate_same_request_are_semantically_stable():
    values = {
        "https://github.com/acme/a": scanned("acme/a", "a1", [reference("package.json", "https://github.com/acme/b.git")]),
        "https://github.com/acme/b": scanned("acme/b", "b1"),
    }
    service = MultiRepositoryMapService(lambda url, ref: values[url])
    first = service.build([
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/b", "ref": "main"},
    ])
    second = MultiRepositoryMapService(lambda url, ref: values[url]).build([
        {"url": "https://github.com/acme/b", "ref": "main"},
        {"url": "https://github.com/acme/a", "ref": "main"},
    ])
    assert first == second


def test_partial_failure_preserves_success_and_no_edge_to_failed_target():
    def scan(url, ref):
        if url.endswith("/b"):
            raise ValueError("invalid ref")
        return scanned("acme/a", "a1", [reference("package.json", "https://github.com/acme/b.git")])

    result = MultiRepositoryMapService(scan).build([
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/b", "ref": "bad"},
    ])

    assert result["status"] == "PARTIAL"
    assert {item["status"] for item in result["repositories"]} == {"SUCCESS", "FAILED"}
    assert result["relationships"] == []
    assert result["unresolved_references"][0]["reason"] == "TARGET_UNAVAILABLE"


def test_repeated_snapshot_is_cached_after_first_scan():
    calls = []
    value = scanned("acme/a", "a1")
    service = MultiRepositoryMapService(lambda url, ref: calls.append(url) or value)
    immutable_ref = "a" * 40
    service.build([{"url": "https://github.com/acme/a", "ref": immutable_ref}])
    service.build([{"url": "https://github.com/acme/a", "ref": immutable_ref}])
    assert calls == ["https://github.com/acme/a"]


def test_mutable_ref_is_reresolved_and_never_reuses_stale_snapshot():
    revisions = iter(["a1", "a2"])
    service = MultiRepositoryMapService(lambda url, ref: scanned("acme/a", next(revisions)))

    first = service.build([{"url": "https://github.com/acme/a", "ref": "main"}])
    second = service.build([{"url": "https://github.com/acme/a", "ref": "main"}])

    assert first["repositories"][0]["resolved_revision"] == "a1"
    assert second["repositories"][0]["resolved_revision"] == "a2"


def test_same_repository_with_different_snapshots_is_explicit_conflict():
    values = {
        "v1": scanned("acme/a", "a1"),
        "v2": scanned("acme/a", "a2"),
    }
    result = MultiRepositoryMapService(lambda url, ref: values[ref]).build([
        {"url": "https://github.com/acme/a", "ref": "v1"},
        {"url": "https://github.com/acme/a", "ref": "v2"},
    ])

    assert result["status"] == "PARTIAL"
    assert [item["status"] for item in result["repositories"]] == ["SUCCESS", "CONFLICT"]
    conflict = next(item for item in result["repositories"] if item["status"] == "CONFLICT")
    assert conflict["error"]["code"] == "DUPLICATE_REPOSITORY_CONFLICT"


def test_map_request_rejects_empty_collection():
    with pytest.raises(ValueError):
        MultiRepositoryMapService(lambda url, ref: {}).build([])


def test_map_endpoint_is_additive_and_thin(monkeypatch):
    service = MultiRepositoryMapService(lambda url, ref: scanned("acme/a", "a1"))
    monkeypatch.setattr("app.api.scan._map_service", service)

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/map", json={"repositories": [{"url": "https://github.com/acme/a", "ref": "main"}]})

    response = __import__("asyncio").run(request())
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETE"