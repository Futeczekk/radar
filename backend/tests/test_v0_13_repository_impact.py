import httpx
import pytest

from app.main import app
from app.models.map import MapImpactRequest
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


def test_repository_impact_returns_empty_result_for_no_dependents():
    service = MultiRepositoryMapService(lambda url, ref: scanned(url.rsplit("/", 1)[-1], "a1"))
    result = service.build_impact([
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/solo", "ref": "main"},
    ], "https://github.com/acme/shared")

    assert result["found"] is True
    assert result["direct_dependents"] == []
    assert result["transitive_dependents"] == []


def test_repository_impact_tracks_direct_and_transitive_dependents_with_evidence():
    values = {
        "https://github.com/acme/shared": scanned("acme/shared", "s1"),
        "https://github.com/acme/api": scanned("acme/api", "a1", [reference("package.json", "https://github.com/acme/shared")]),
        "https://github.com/acme/worker": scanned("acme/worker", "w1", [reference("package.json", "https://github.com/acme/api")]),
        "https://github.com/acme/other": scanned("acme/other", "o1", [reference("package.json", "https://github.com/acme/else")]),
    }

    result = MultiRepositoryMapService(lambda url, ref: values[url]).build_impact([
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/api", "ref": "main"},
        {"url": "https://github.com/acme/worker", "ref": "main"},
        {"url": "https://github.com/acme/other", "ref": "main"},
    ], "https://github.com/acme/shared")

    assert result["found"] is True
    assert [item["repository"] for item in result["direct_dependents"]] == ["https://github.com/acme/api"]
    assert [item["repository"] for item in result["transitive_dependents"]] == ["https://github.com/acme/worker"]
    assert result["direct_dependents"][0]["distance"] == 1
    assert result["transitive_dependents"][0]["distance"] == 2
    assert result["transitive_dependents"][0]["path"] == ["https://github.com/acme/worker", "https://github.com/acme/api", "https://github.com/acme/shared"]
    assert result["transitive_dependents"][0]["evidence"][0]["target_repository"] == "https://github.com/acme/api"
    assert result["transitive_dependents"][0]["evidence"][1]["target_repository"] == "https://github.com/acme/shared"
    assert result["direct_dependents"][0]["evidence"][0]["target_repository"] == "https://github.com/acme/shared"


def test_repository_impact_ignores_unrelated_and_unknown_targets_and_uses_identity_exactness():
    values = {
        "https://github.com/acme/shared": scanned("acme/shared", "s1"),
        "https://github.com/acme/api": scanned("acme/api", "a1", [reference("package.json", "git+https://github.com/acme/shared.git")]),
        "https://github.com/acme/unrelated": scanned("acme/unrelated", "u1", [reference("package.json", "https://github.com/acme/ghost")]),
    }
    service = MultiRepositoryMapService(lambda url, ref: values[url])
    result = service.build_impact([
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/api", "ref": "main"},
        {"url": "https://github.com/acme/unrelated", "ref": "main"},
    ], "https://github.com/acme/shared")

    assert [item["repository"] for item in result["direct_dependents"]] == ["https://github.com/acme/api"]
    assert service.build_impact([
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/api", "ref": "main"},
    ], "https://github.com/acme/missing")["found"] is False


def test_repository_impact_avoids_self_target_cycles_and_deduplicates_repeated_edges():
    values = {
        "https://github.com/acme/a": scanned("acme/a", "a1", [reference("package.json", "https://github.com/acme/b")]),
        "https://github.com/acme/b": scanned("acme/b", "b1", [reference("package.json", "https://github.com/acme/a")]),
        "https://github.com/acme/c": scanned("acme/c", "c1", [reference("package.json", "https://github.com/acme/a"), reference("package.json", "https://github.com/acme/a")]),
    }
    result = MultiRepositoryMapService(lambda url, ref: values[url]).build_impact([
        {"url": "https://github.com/acme/a", "ref": "main"},
        {"url": "https://github.com/acme/b", "ref": "main"},
        {"url": "https://github.com/acme/c", "ref": "main"},
    ], "https://github.com/acme/a")

    assert result["found"] is True
    repositories = {item["repository"] for item in result["direct_dependents"] + result["transitive_dependents"]}
    assert repositories == {"https://github.com/acme/b", "https://github.com/acme/c"}
    assert all(item["repository"] != "https://github.com/acme/a" for item in result["direct_dependents"] + result["transitive_dependents"])


def test_repository_impact_selects_shortest_path_and_is_order_independent():
    values = {
        "https://github.com/acme/shared": scanned("acme/shared", "s1"),
        "https://github.com/acme/api": scanned("acme/api", "a1", [reference("package.json", "https://github.com/acme/shared")]),
        "https://github.com/acme/web": scanned("acme/web", "w1", [reference("package.json", "https://github.com/acme/shared")]),
        "https://github.com/acme/worker": scanned("acme/worker", "w1", [reference("package.json", "https://github.com/acme/api"), reference("package.json", "https://github.com/acme/web")]),
    }
    requests = [
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/api", "ref": "main"},
        {"url": "https://github.com/acme/web", "ref": "main"},
        {"url": "https://github.com/acme/worker", "ref": "main"},
    ]
    first = MultiRepositoryMapService(lambda url, ref: values[url]).build_impact(requests, "https://github.com/acme/shared")
    second = MultiRepositoryMapService(lambda url, ref: values[url]).build_impact(list(reversed(requests)), "https://github.com/acme/shared")
    assert first == second
    assert [item["repository"] for item in first["direct_dependents"]] == ["https://github.com/acme/api", "https://github.com/acme/web"]
    assert [item["repository"] for item in first["transitive_dependents"]] == ["https://github.com/acme/worker"]
    assert first["transitive_dependents"][0]["path"] == ["https://github.com/acme/worker", "https://github.com/acme/api", "https://github.com/acme/shared"]


def test_repository_impact_partial_failure_keeps_status_and_ignores_failed_targets():
    def scan(url, ref):
        if url.endswith("/bad"):
            raise ValueError("bad repo")
        return scanned(url.rsplit("/", 1)[-1], "a1", [reference("package.json", "https://github.com/acme/shared")])

    result = MultiRepositoryMapService(scan).build_impact([
        {"url": "https://github.com/acme/shared", "ref": "main"},
        {"url": "https://github.com/acme/ok", "ref": "main"},
        {"url": "https://github.com/acme/bad", "ref": "bad"},
    ], "https://github.com/acme/shared")

    assert result["status"] == "PARTIAL"
    assert result["direct_dependents"] == [{
        "repository": "https://github.com/acme/ok",
        "distance": 1,
        "path": ["https://github.com/acme/ok", "https://github.com/acme/shared"],
        "evidence": [{
            "source_repository": "https://github.com/acme/ok",
            "target_repository": "https://github.com/acme/shared",
            "evidence": [{"file": "package.json", "line": 1, "snippet": None, "reason": "explicit repository URL"}],
        }],
    }]


def test_map_impact_endpoint_is_additive_and_uses_collection_target(monkeypatch):
    values = {
        "https://github.com/acme/shared": scanned("acme/shared", "s1"),
        "https://github.com/acme/api": scanned("acme/api", "a1", [reference("package.json", "https://github.com/acme/shared")]),
    }
    service = MultiRepositoryMapService(lambda url, ref: values[url])
    monkeypatch.setattr("app.api.scan._map_service", service)
    request = MapImpactRequest(
        repositories=[
            {"url": "https://github.com/acme/shared", "ref": "main"},
            {"url": "https://github.com/acme/api", "ref": "main"},
        ],
        target="https://github.com/acme/shared",
    )

    result = service.build_impact(request.repositories, request.target)
    assert result["direct_dependents"][0]["repository"] == "https://github.com/acme/api"

    async def request_call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/map/impact", json={"repositories": request.model_dump()["repositories"], "target": request.target})

    response = __import__("asyncio").run(request_call())
    assert response.status_code == 200
    assert response.json()["direct_dependents"][0]["repository"] == "https://github.com/acme/api"
