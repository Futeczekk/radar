import asyncio

import httpx
import pytest
from fastapi import HTTPException

from app.api.scan import diff as diff_endpoint
from app.main import app
from app.models.repository import DiffRequest
from app.services.diff import SnapshotMismatchError, diff_snapshots
from app.sources.github import GitHubError, get_commit


def relationship(source, target, kind="imports", scope="project"):
    return {
        "source": source,
        "target": target,
        "type": kind,
        "scope": scope,
        "confidence": 1.0,
        "evidence": [{"file": source, "line": 1, "snippet": "known", "reason": "deterministic"}],
    }


def snapshot(commit_sha, files, facts=None, relationships=None, components=None, component_relationships=None):
    return {
        "repository": "demo/repo",
        "ref": commit_sha,
        "commit_sha": commit_sha,
        "files": files,
        "facts": facts or [],
        "repository_graph": {
            "nodes": [{"id": item if isinstance(item, str) else item["path"], "type": "file"} for item in files],
            "relationships": relationships or [],
        },
        "component_graph": {
            "components": components or [],
            "relationships": component_relationships or [],
        },
    }


def test_identical_snapshots_produce_empty_deterministic_diff():
    state = snapshot("a", [{"path": "a.py", "sha": "1"}])

    result = diff_snapshots(state, state)

    assert result["changes"] == {
        "files": {"added": [], "removed": [], "changed": []},
        "facts": {"added": [], "removed": [], "changed": []},
        "relationships": {"added": [], "removed": []},
        "components": {"added": [], "removed": [], "changed": []},
        "component_relationships": {"added": [], "removed": []},
        "impact": [],
    }


def test_files_facts_relationships_and_impacts_are_compared():
    base_relationships = [relationship("api.py", "legacy.py")]
    target_relationships = [relationship("api.py", "cache.py")]
    base = snapshot(
        "a",
        [{"path": "api.py", "sha": "api-a"}, {"path": "legacy.py", "sha": "old"}, {"path": "service.py", "sha": "service-a"}],
        facts=[{"type": "python.requires", "subject": "Python", "value": ">=3.11", "scope": "project", "confidence": 1.0}],
        relationships=base_relationships + [relationship("service.py", "legacy.py")],
    )
    target = snapshot(
        "b",
        [{"path": "api.py", "sha": "api-b"}, {"path": "cache.py", "sha": "new"}, {"path": "service.py", "sha": "service-a"}],
        facts=[{"type": "python.requires", "subject": "Python", "value": ">=3.12", "scope": "project", "confidence": 1.0}],
        relationships=target_relationships + [relationship("service.py", "cache.py")],
    )

    result = diff_snapshots(base, target)

    assert [item["path"] for item in result["changes"]["files"]["added"]] == ["cache.py"]
    assert [item["path"] for item in result["changes"]["files"]["removed"]] == ["legacy.py"]
    assert [item["path"] for item in result["changes"]["files"]["changed"]] == ["api.py"]
    assert result["changes"]["facts"]["changed"][0]["after"]["value"] == ">=3.12"
    assert result["changes"]["relationships"]["added"][0]["target"] == "cache.py"
    assert result["changes"]["relationships"]["removed"][0]["target"] == "legacy.py"
    removed_impact = next(item for item in result["changes"]["impact"] if item["file"] == "legacy.py")
    assert [item["node"] for item in removed_impact["impact"]["direct_dependents"]] == ["api.py", "service.py"]


def test_components_and_component_relationships_preserve_structural_changes():
    base_components = [{"id": "backend", "type": "backend", "scope": "project", "files": ["api.py"], "confidence": 0.95}]
    target_components = [{"id": "backend", "type": "backend", "scope": "project", "files": ["api.py", "service.py"], "confidence": 0.95}, {"id": "cache", "type": "data", "scope": "project", "files": ["cache.py"], "confidence": 0.8}]
    result = diff_snapshots(
        snapshot("a", [], components=base_components, component_relationships=[]),
        snapshot("b", [], components=target_components, component_relationships=[relationship("backend", "cache", "depends_on")]),
    )

    assert [item["id"] for item in result["changes"]["components"]["added"]] == ["cache"]
    assert result["changes"]["components"]["changed"][0]["id"] == "backend"
    assert result["changes"]["component_relationships"]["added"][0]["source"] == "backend"


def test_scope_confidence_ordering_and_duplicate_suppression_are_deterministic():
    edge = relationship("tests/test_api.py", "api.py", scope="test")
    base = snapshot("a", [{"path": "api.py", "sha": "1"}], relationships=[edge, edge])
    target = snapshot("b", [{"path": "api.py", "sha": "2"}], relationships=[edge])

    result = diff_snapshots(base, target)

    assert result["changes"]["files"]["changed"][0]["scope"] == "project"
    assert result["changes"]["relationships"]["added"] == []
    assert result["changes"]["relationships"]["removed"] == []
    assert result["changes"]["impact"][0]["impact"]["direct_dependents"][0]["scope"] == "test"


def test_fact_evidence_order_does_not_create_a_false_change():
    base_fact = {
        "type": "runtime", "subject": "Python", "value": ">=3.11",
        "scope": "project", "confidence": 1.0,
        "evidence": [{"file": "a", "reason": "first"}, {"file": "b", "reason": "second"}],
    }
    target_fact = dict(base_fact)
    target_fact["evidence"] = list(reversed(base_fact["evidence"]))

    result = diff_snapshots(snapshot("a", [], facts=[base_fact]), snapshot("b", [], facts=[target_fact]))

    assert result["changes"]["facts"] == {"added": [], "removed": [], "changed": []}


def test_ci_fact_value_change_is_reported_as_changed():
    base_fact = {
        "type": "ci.python_version",
        "subject": "Python",
        "value": "3.11",
        "scope": "ci",
        "source_type": "ci_config",
        "environment": "runtime",
        "confidence": 1.0,
        "evidence": [{"file": ".github/workflows/test.yml"}],
    }
    target_fact = dict(base_fact)
    target_fact["value"] = ["3.11", "3.12", "3.13"]

    result = diff_snapshots(
        snapshot("a", [], facts=[base_fact]),
        snapshot("b", [], facts=[target_fact]),
    )

    assert result["changes"]["facts"]["added"] == []
    assert result["changes"]["facts"]["removed"] == []
    assert result["changes"]["facts"]["changed"][0]["before"]["value"] == "3.11"
    assert result["changes"]["facts"]["changed"][0]["after"]["value"] == ["3.11", "3.12", "3.13"]


def test_diff_route_reports_controlled_ci_fact_transition_as_changed(monkeypatch):
    base_fact = {
        "type": "ci.python_version",
        "subject": "Python",
        "value": "3.11",
        "scope": "ci",
        "source_type": "ci_config",
        "environment": "runtime",
        "confidence": 1.0,
        "extractor": "github_actions",
        "evidence": [{"file": ".github/workflows/test.yml", "line": 12}],
    }
    target_fact = dict(base_fact)
    target_fact["value"] = ["3.11", "3.12", "3.13"]
    snapshots = {
        "b5b0a2c": snapshot("b5b0a2c", [], facts=[base_fact]),
        "f1021eb": snapshot("f1021eb", [], facts=[target_fact]),
    }
    monkeypatch.setattr(
        "app.api.scan.scan_repository",
        lambda url, ref=None: {"snapshot": snapshots[ref]},
    )

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/diff", json={
                "url": "https://github.com/Futii10/radar-test",
                "base_ref": "b5b0a2c",
                "target_ref": "f1021eb",
            })

    response = asyncio.run(request())
    facts = response.json()["changes"]["facts"]

    assert response.status_code == 200
    assert facts["added"] == []
    assert facts["removed"] == []
    assert len(facts["changed"]) == 1
    assert facts["changed"][0]["before"]["value"] == "3.11"
    assert facts["changed"][0]["after"]["value"] == ["3.11", "3.12", "3.13"]
    assert facts["changed"][0]["before"]["source_type"] == "ci_config"
    assert facts["changed"][0]["after"]["extractor"] == "github_actions"


def test_github_workflow_file_change_preserves_ci_scope():
    result = diff_snapshots(
        snapshot("a", [{"path": ".github/workflows/test.yml", "sha": "a"}]),
        snapshot("b", [{"path": ".github/workflows/test.yml", "sha": "b"}]),
    )

    assert result["changes"]["files"]["changed"][0]["scope"] == "ci"


def test_repository_mismatch_is_rejected():
    base = snapshot("a", [])
    target = snapshot("b", [])
    target["repository"] = "other/repo"

    try:
        diff_snapshots(base, target)
    except SnapshotMismatchError:
        pass
    else:
        raise AssertionError("repository mismatch should be rejected")


def test_invalid_ref_is_reported_by_github_source(monkeypatch):
    class Response:
        status_code = 404

        def json(self):
            return {}

    monkeypatch.setattr("app.sources.github.httpx.get", lambda *args, **kwargs: Response())

    with pytest.raises(GitHubError) as error:
        get_commit("demo/repo", "missing-ref")

    assert error.value.status_code == 404
    assert error.value.error_type == "ref_not_found"


def test_diff_endpoint_exposes_ref_not_found_error(monkeypatch):
    def invalid_ref(*args, **kwargs):
        raise GitHubError("GitHub repository ref not found", 404, "ref_not_found")

    monkeypatch.setattr("app.api.scan.scan_repository", invalid_ref)

    with pytest.raises(HTTPException) as error:
        diff_endpoint(DiffRequest(
            url="https://github.com/demo/repo",
            base_ref="missing-ref",
            target_ref="target-ref",
        ))

    assert error.value.status_code == 404
    assert error.value.detail == {
        "error": "ref_not_found",
        "message": "GitHub repository ref not found",
    }


def test_diff_route_preserves_ref_not_found_from_commit_lookup(monkeypatch):
    class Response:
        headers = {}
        text = "Not Found"

        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self.payload = payload or {}

        def json(self):
            return self.payload

    def fake_get(url, **kwargs):
        if url.endswith("/repos/Futii10/radar-test"):
            return Response(200, {
                "full_name": "Futii10/radar-test",
                "default_branch": "main",
                "description": None,
                "stargazers_count": 0,
                "open_issues_count": 0,
            })
        if "/commits/THIS_REF_DOES_NOT_EXIST_12345" in url:
            return Response(404)
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr("app.sources.github.httpx.get", fake_get)

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/diff", json={
                "url": "https://github.com/Futii10/radar-test",
                "base_ref": "THIS_REF_DOES_NOT_EXIST_12345",
                "target_ref": "unused",
            })

    response = asyncio.run(request())

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "ref_not_found"
    assert response.json()["detail"]["error"] != "github_source_error"


def test_diff_route_preserves_ref_not_found_for_github_commit_422(monkeypatch):
    class Response:
        headers = {}
        text = "No commit found for SHA"

        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self.payload = payload or {}

        def json(self):
            return self.payload

    def fake_get(url, **kwargs):
        if url.endswith("/repos/Futii10/radar-test"):
            return Response(200, {
                "full_name": "Futii10/radar-test",
                "default_branch": "main",
                "description": None,
                "stargazers_count": 0,
                "open_issues_count": 0,
            })
        if "/commits/THIS_REF_DOES_NOT_EXIST_12345" in url:
            return Response(422)
        raise AssertionError(f"unexpected request: {url}")

    monkeypatch.setattr("app.sources.github.httpx.get", fake_get)

    async def request():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/diff", json={
                "url": "https://github.com/Futii10/radar-test",
                "base_ref": "THIS_REF_DOES_NOT_EXIST_12345",
                "target_ref": "unused",
            })

    response = asyncio.run(request())

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "ref_not_found"
