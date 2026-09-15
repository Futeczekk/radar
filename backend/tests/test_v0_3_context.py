from app.extractors.configuration import extract_configuration


def test_python_ci_matrix_does_not_create_false_positive():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        ".github/workflows/test.yml": """
        name: test
        jobs:
          test:
            strategy:
              matrix:
                python-version: ['3.11', '3.12', '3.13']
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: ${{ matrix.python-version }}
        """
    })
    assert not any(f["type"] == "version_inconsistency" for f in findings)
    python_facts = [f for f in facts if f["subject"] == "Python"]
    assert any(f.get("scope") == "project" for f in python_facts)
    assert any(f.get("scope") == "ci" for f in python_facts)


def test_real_python_drift_is_still_detected():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.11'
        """
    })
    assert any(f["type"] == "version_inconsistency" for f in findings)


def test_example_subdirectory_does_not_define_main_project_runtime():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        "examples/legacy/package.json": '{"engines": {"node": ">=18"}}'
    })
    example_fact = next((f for f in facts if f["type"] == "node.required_version" and f["evidence"][0]["file"] == "examples/legacy/package.json"), None)
    assert example_fact is not None
    assert example_fact.get("scope") == "example"
    assert not any(f["type"] == "version_inconsistency" for f in findings)


def test_node_ci_matrix_is_not_false_positive():
    facts, findings = extract_configuration({
        "package.json": '{"engines": {"node": ">=22"}}',
        ".github/workflows/test.yml": """
        jobs:
          test:
            strategy:
              matrix:
                node-version: ['18', '20', '22']
            steps:
              - uses: actions/setup-node@v4
                with:
                  node-version: ${{ matrix.node-version }}
        """
    })
    assert not any(f["type"] == "version_inconsistency" for f in findings)


def test_vendor_test_and_generated_files_are_ignored_for_primary_runtime():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        "vendor/legacy/pyproject.toml": "[project]\nrequires-python = \">=3.9\"\n",
        "tests/fixtures/local/pyproject.toml": "[project]\nrequires-python = \">=3.8\"\n",
        "build/generated/pyproject.toml": "[project]\nrequires-python = \">=3.7\"\n",
    })
    assert any(f["type"] == "python.required_version" and f.get("scope") == "project" for f in facts)
    assert not any(f["type"] == "version_inconsistency" for f in findings)


def test_multi_stage_dockerfile_keeps_each_stage_as_evidence_without_conflict():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        "Dockerfile": "FROM python:3.11 AS builder\nFROM python:3.12 AS runtime\n",
    })
    docker_fact = next((f for f in facts if f["type"] == "docker.base_image"), None)
    assert docker_fact is not None
    assert docker_fact["value"] == ["python:3.11", "python:3.12"]
    assert not any(f["type"] == "version_inconsistency" for f in findings)


def test_monorepo_subprojects_are_not_merged_into_single_conflict():
    facts, findings = extract_configuration({
        "backend/pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        "frontend/package.json": '{"engines": {"node": ">=18"}}',
        "legacy-admin/package.json": '{"engines": {"node": ">=20"}}',
        ".github/workflows/test.yml": """
        jobs:
          test:
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.12'
        """
    })
    assert not any(f["type"] == "version_inconsistency" for f in findings)
    assert any(f["type"] == "node.required_version" and f.get("scope") == "subproject" for f in facts)


def test_malformed_workflow_context_is_ignored_without_crashing():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        ".github/workflows/test.yml": """
        jobs:
          test:
            strategy:
              matrix:
                python-version: [3.11, 3.12
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: ${{ matrix.python-version }}
        """
    })
    assert any(f["type"] == "python.required_version" and f.get("scope") == "project" for f in facts)
    assert not any(f["type"] == "version_inconsistency" for f in findings)
