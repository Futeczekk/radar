import json
from pathlib import Path

import pytest

from app.api.scan import scan as scan_endpoint
from app.application.scanning import ScanApplication
from app.extractors.configuration import extract_configuration
from app.models.repository import RepositoryRequest
from app.models.snapshot import RepositorySnapshot
from app.sources.github_adapter import GitHubSource
from validation.cache import SnapshotCache


def test_repository_snapshot_is_immutable_and_source_neutral():
    snapshot = RepositorySnapshot(
        repository="owner/repo",
        ref="main",
        commit_sha="abc123",
        files=({"path": "app.py", "sha": "file-sha"},),
        file_contents={"app.py": "print('ok')"},
        source="local",
    )

    assert snapshot.paths == ["app.py"]
    assert snapshot.as_dict()["source"] == "local"
    try:
        snapshot.ref = "other"
    except AttributeError:
        pass
    else:
        raise AssertionError("RepositorySnapshot must be immutable")


def test_snapshot_cache_is_scoped_to_repository_and_commit(tmp_path):
    cache = SnapshotCache(tmp_path)
    snapshot = {"files": [{"path": "app.py"}], "facts": []}

    cache.put("owner/repo", "abc123", snapshot)

    assert cache.get("owner/repo", "abc123") == snapshot
    assert cache.get("owner/repo", "def456") is None
    assert cache.get("other/repo", "abc123") is None


def test_corrupt_cache_is_a_miss(tmp_path):
    cache = SnapshotCache(tmp_path)
    cache.put("owner/repo", "abc123", {"files": []})
    path = next(Path(tmp_path).glob("*.json"))
    path.write_text("not json", encoding="utf-8")

    assert cache.get("owner/repo", "abc123") is None


def test_cache_payload_contains_no_environment_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    cache = SnapshotCache(tmp_path)
    cache.put("owner/repo", "abc123", {"files": []})

    payload = json.loads(next(Path(tmp_path).glob("*.json")).read_text())
    assert "secret-token" not in json.dumps(payload)


def test_core_and_extractors_do_not_import_transport():
    root = Path(__file__).parents[1] / "app"
    for directory in (root / "core", root / "extractors"):
        for path in directory.glob("*.py"):
            assert "fastapi" not in path.read_text(encoding="utf-8").lower()


@pytest.mark.parametrize(
    ("commit_sha", "paths"),
    [
        (
            "f1021eb25d0f4cfbd0d3f8fc37caeaeab0f31b95",
            [".github/workflows/test.yml", "CMakeLists.txt", "Dockerfile", "package.json", "pyproject.toml"],
        ),
        (
            "d893460cc40474cd605a75ae08c7ca83e722b5e6",
            [".github/workflows/test.yml", "CMakeLists.txt", "Dockerfile", "backend/__init__.py", "backend/api.py", "backend/database.py", "backend/main.py", "backend/service.py", "package.json", "pyproject.toml"],
        ),
    ],
)
def test_github_source_loads_the_requested_controlled_commit(monkeypatch, commit_sha, paths):
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository",
        lambda repository: {"full_name": repository, "default_branch": "main"},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_commit",
        lambda repository, ref: {"sha": commit_sha},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository_tree_entries",
        lambda repository, ref: [{"path": path, "sha": f"sha-{index}"} for index, path in enumerate(paths)],
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository_file_contents",
        lambda repository, ref, requested_paths: {},
    )

    snapshot, _ = GitHubSource().load_snapshot(
        "https://github.com/Futii10/radar-test",
        commit_sha,
    )

    assert snapshot.ref == commit_sha
    assert snapshot.commit_sha == commit_sha
    assert snapshot.paths == sorted(paths)


def test_github_source_uses_default_branch_when_ref_is_omitted(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository",
        lambda repository: {"full_name": repository, "default_branch": "main"},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_commit",
        lambda repository, ref: calls.append(("commit", ref)) or {"sha": "default-sha"},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository_tree_entries",
        lambda repository, ref: calls.append(("tree", ref)) or [],
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository_file_contents",
        lambda repository, ref, paths: {},
    )

    snapshot, _ = GitHubSource().load_snapshot("https://github.com/Futii10/radar-test")

    assert snapshot.ref == "main"
    assert snapshot.commit_sha == "default-sha"
    assert calls == [("commit", "main"), ("tree", "default-sha")]


def test_github_source_fetches_important_files_beyond_first_200_entries(monkeypatch):
    paths = [f"src/file_{index}.py" for index in range(201)] + ["pyproject.toml", ".github/workflows/test.yml"]
    requested = {}
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository",
        lambda repository: {"full_name": repository, "default_branch": "main"},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_commit",
        lambda repository, ref: {"sha": "commit-sha"},
    )
    monkeypatch.setattr(
        "app.sources.github_adapter.get_repository_tree_entries",
        lambda repository, ref: [{"path": path, "sha": path} for path in paths],
    )

    def fake_file_contents(repository, ref, requested_paths):
        requested["paths"] = requested_paths
        return {path: "content" for path in requested_paths}

    monkeypatch.setattr("app.sources.github_adapter.get_repository_file_contents", fake_file_contents)

    snapshot, _ = GitHubSource().load_snapshot("https://github.com/example/repo", "commit-sha")

    assert requested["paths"] == paths[:200] + ["pyproject.toml", ".github/workflows/test.yml"]
    assert set(snapshot.file_contents) == set(requested["paths"])


def test_scan_application_extracts_configuration_from_snapshot_contents(monkeypatch):
    snapshot = RepositorySnapshot(
        repository="example/repo",
        ref="commit-sha",
        commit_sha="commit-sha",
        files=(
            {"path": "Dockerfile", "sha": "docker-sha"},
            {"path": "pyproject.toml", "sha": "python-sha"},
        ),
        file_contents={
            "Dockerfile": "FROM python:3.12-slim\n",
            "pyproject.toml": '[project]\nname = "example"\nrequires-python = ">=3.12"\n',
        },
        source="test",
    )

    class Source:
        def load_snapshot(self, url, ref=None):
            return snapshot, {
                "repository": "example/repo",
                "full_name": "example/repo",
                "description": None,
                "stargazers_count": 0,
                "open_issues_count": 0,
                "default_branch": "main",
            }

        def latest_release(self, repository):
            return None

    monkeypatch.setattr("app.application.scanning.get_previous_release", lambda repository: None)
    monkeypatch.setattr("app.application.scanning.save_repository_state", lambda repository, version: None)

    result = ScanApplication(Source()).scan("https://github.com/example/repo", "commit-sha")
    fact_types = {fact["type"] for fact in result["facts"]}

    assert {"docker.base_image", "python.required_version"}.issubset(fact_types)


def test_cached_snapshot_contents_produce_the_same_configuration_facts(tmp_path):
    snapshot = RepositorySnapshot(
        repository="example/repo",
        ref="commit-sha",
        commit_sha="commit-sha",
        file_contents={
            "Dockerfile": "FROM python:3.12-slim\n",
            "pyproject.toml": '[project]\nrequires-python = ">=3.12"\n',
        },
    )
    cache = SnapshotCache(tmp_path)
    cache.put("example/repo", "commit-sha", snapshot.as_dict())
    cached = cache.get("example/repo", "commit-sha")

    assert cached is not None
    live_facts, _ = extract_configuration(snapshot.file_contents)
    cached_facts, _ = extract_configuration(cached["file_contents"])
    assert cached_facts == live_facts


@pytest.mark.parametrize("ref", [None, "f1021eb25d0f4cfbd0d3f8fc37caeaeab0f31b95"])
def test_scan_endpoint_forwards_requested_or_default_ref(monkeypatch, ref):
    captured = {}

    def fake_scan(url, requested_ref=None):
        captured.update({"url": url, "ref": requested_ref})
        return {"commit_sha": "commit"}

    monkeypatch.setattr("app.api.scan.scan_repository", fake_scan)

    result = scan_endpoint(RepositoryRequest(url="https://github.com/Futii10/radar-test", ref=ref))

    assert result == {"commit_sha": "commit"}
    assert captured == {"url": "https://github.com/Futii10/radar-test", "ref": ref}
