from app.application.scanning import ScanApplication
from app.core.configuration_conflicts import compare_versions, detect_configuration_conflicts
from app.extractors.configuration import extract_configuration
from validation.cache import SnapshotCache


def _conflicts(files):
    facts, findings = extract_configuration(files)
    return facts, findings, detect_configuration_conflicts(facts)


def test_incompatible_python_project_requirement_and_ci_runtime():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.10'
        """,
    })

    assert len(conflicts) == 1
    assert conflicts[0]["subject"] == "Python"
    assert conflicts[0]["status"] == "incompatible"
    assert [item["original_value"] for item in conflicts[0]["observations"]] == [">=3.11", "3.10"]


def test_compatible_python_project_requirement_and_ci_runtime_is_not_conflict():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.12'
        """,
    })

    assert conflicts == []


def test_node_project_requirement_and_ci_runtime_follow_compatibility():
    _, _, incompatible = _conflicts({
        "package.json": '{"engines": {"node": ">=20"}}',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-node@v4
                with:
                  node-version: '18'
        """,
    })
    assert incompatible[0]["subject"] == "Node.js"
    assert incompatible[0]["status"] == "incompatible"

    _, _, compatible = _conflicts({
        "package.json": '{"engines": {"node": ">=20"}}',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-node@v4
                with:
                  node-version: '20'
        """,
    })
    assert compatible == []


def test_project_and_docker_runtime_preserve_original_and_normalized_values():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "Dockerfile": "FROM python:3.10-slim\n",
    })

    assert len(conflicts) == 1
    observations = conflicts[0]["observations"]
    docker = next(item for item in observations if item["original_value"] == "python:3.10-slim")
    assert docker["normalized_value"] == {"operator": "==", "version": "3.10", "wildcard": False}


def test_same_values_from_multiple_sources_are_compatible():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "Dockerfile": "FROM python:3.11\n",
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.11'
        """,
    })

    assert conflicts == []


def test_unsupported_constraint_is_not_emitted_as_a_conflict():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11,<4"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.10'
        """,
    })

    assert conflicts == []


def test_unsupported_variable_or_interpolation_is_not_emitted_as_a_conflict():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.10"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: ${{ env.PYTHON_VERSION }}
        """,
    })

    assert conflicts == []


def test_supported_version_forms_are_compared_conservatively():
    assert compare_versions(">=3.11", "3.12") == "compatible"
    assert compare_versions(">=3.11", "3.10") == "incompatible"
    assert compare_versions("3.11", "3.11.x") == "compatible"
    assert compare_versions("20.x", "20") == "compatible"
    assert compare_versions("<3.12", "3.12") == "incompatible"
    assert compare_versions("${{ matrix.python-version }}", "3.12") == "unknown"


def test_ci_matrix_does_not_create_self_conflicts_or_requirement_false_positive():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.12"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            strategy:
              matrix:
                python-version: ['3.10', '3.11', '3.12']
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: ${{ matrix.python-version }}
        """,
    })

    assert conflicts == []


def test_ci_matrix_with_nonstandard_key_is_still_ignored():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.12"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            strategy:
              matrix:
                python: ['3.10', '3.12']
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: ${{ matrix.python }}
        """,
    })

    assert conflicts == []


def test_independent_ci_runtimes_do_not_create_top_level_conflicts():
    _, _, conflicts = _conflicts({
        ".github/workflows/python.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.11'
        """,
        ".github/workflows/other.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.13'
        """,
    })

    assert conflicts == []


def test_weak_scopes_and_unrelated_subprojects_do_not_pollute_project():
    _, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.12"\n',
        "vendor/legacy/pyproject.toml": '[project]\nrequires-python = ">=3.8"\n',
        "tests/fixtures/pyproject.toml": '[project]\nrequires-python = ">=3.7"\n',
        "backend/pyproject.toml": '[project]\nrequires-python = ">=3.10"\n',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.12'
        """,
    })

    assert conflicts == []


def test_conflict_ordering_and_deduplication_are_stable():
    files = {
        "Dockerfile": "FROM node:18\nFROM python:3.10\n",
        "package.json": '{"engines": {"node": ">=20"}}',
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
    }
    _, _, first = _conflicts(files)
    _, _, second = _conflicts(dict(reversed(list(files.items()))))

    assert first == second
    assert [item["subject"] for item in first] == ["Node.js", "Python"]


def test_conflict_preserves_context_and_all_evidence():
    facts, _, conflicts = _conflicts({
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "Dockerfile": "FROM python:3.10\n",
    })

    assert {item["scope"] for item in conflicts[0]["observations"]} == {"project"}
    assert {item["environment"] for item in conflicts[0]["observations"]} == {"runtime", "build"}
    assert {item["file"] for item in conflicts[0]["evidence"]} == {"Dockerfile", "pyproject.toml"}
    assert all(fact["confidence"] == 1.0 for fact in facts)

def test_cache_hit_and_miss_have_semantically_identical_conflicts(tmp_path):
    file_contents = {
        "pyproject.toml": '[project]\nrequires-python = ">=3.11"\n',
        "Dockerfile": "FROM python:3.10\n",
    }
    snapshot = {
        "repository": "example/repo",
        "commit_sha": "sha",
        "file_contents": file_contents,
    }
    cache = SnapshotCache(tmp_path)
    cache.put("example/repo", "sha", snapshot)

    live_facts, _ = extract_configuration(file_contents)
    cached_snapshot = cache.get("example/repo", "sha")
    cached_facts, _ = extract_configuration(cached_snapshot["file_contents"])

    assert detect_configuration_conflicts(live_facts) == detect_configuration_conflicts(cached_facts)


def test_scan_response_adds_empty_conflict_field_without_removing_existing_fields(monkeypatch):
    class Source:
        def load_snapshot(self, url, ref=None):
            from app.models.snapshot import RepositorySnapshot

            return RepositorySnapshot(
                repository="example/repo",
                ref="main",
                commit_sha="sha",
                files=(),
                file_contents={},
            ), {
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
    result = ScanApplication(Source()).scan("https://github.com/example/repo")

    assert result["configuration_conflicts"] == []
    assert result["findings"] == []
    assert result["facts"] == []