from app.extractors.configuration import extract_configuration


def test_cmake_minimum_version_parsing():
    facts, findings = extract_configuration({
        "CMakeLists.txt": "cmake_minimum_required(VERSION 3.28)\nproject(Radar)\n"
    })
    fact = next((f for f in facts if f["type"] == "cmake.minimum_version"), None)
    assert fact is not None
    assert fact["value"] == "3.28"
    assert fact["confidence"] == 1.0


def test_cmake_project_name_parsing():
    facts, findings = extract_configuration({
        "CMakeLists.txt": "cmake_minimum_required(VERSION 3.28)\nproject(Radar)\n"
    })
    fact = next((f for f in facts if f["type"] == "project.name"), None)
    assert fact is not None
    assert fact["value"] == "Radar"


def test_docker_base_image_parsing():
    facts, findings = extract_configuration({
        "Dockerfile": "FROM python:3.12-slim AS builder\nRUN echo hi\nFROM python:3.12-slim\n"
    })
    fact = next((f for f in facts if f["type"] == "docker.base_image"), None)
    assert fact is not None
    assert fact["value"] == "python:3.12-slim" or fact["value"] == ["python:3.12-slim"]


def test_dockerfile_multi_stage_parse():
    facts, findings = extract_configuration({
        "Dockerfile": "FROM alpine:3.20 AS builder\nFROM python:3.12-slim\n"
    })
    docker_facts = [f for f in facts if f["type"] == "docker.base_image"]
    assert len(docker_facts) >= 1
    assert any("python:3.12-slim" in str(f["value"]) for f in docker_facts)


def test_pyproject_python_required_version_parsing():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n"
    })
    fact = next((f for f in facts if f["type"] == "python.required_version"), None)
    assert fact is not None
    assert fact["value"] == ">=3.12"


def test_package_json_node_required_version_parsing():
    facts, findings = extract_configuration({
        "package.json": '{"engines": {"node": ">=22"}}'
    })
    fact = next((f for f in facts if f["type"] == "node.required_version"), None)
    assert fact is not None
    assert fact["value"] == ">=22"


def test_github_actions_python_version_parsing():
    facts, findings = extract_configuration({
        ".github/workflows/test.yml": """
        jobs:
          test:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/setup-python@v5
                with:
                  python-version: '3.11'
        """
    })
    fact = next((f for f in facts if f["type"] == "ci.python_version"), None)
    assert fact is not None
    assert fact["value"] == "3.11"


def test_github_actions_node_version_parsing():
    facts, findings = extract_configuration({
        ".github/workflows/test.yml": """
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/setup-node@v4
                with:
                  node-version: '22'
        """
    })
    fact = next((f for f in facts if f["type"] == "ci.node_version"), None)
    assert fact is not None
    assert fact["value"] == "22"


def test_missing_values_are_ignored():
    facts, findings = extract_configuration({
        "README.md": "No config here\n"
    })
    assert facts == []
    assert findings == []


def test_malformed_files_are_ignored():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project\nrequires-python = \">=3.12\"\n",
        "package.json": '{"engines": ',
    })
    assert facts == []


def test_version_inconsistency_detection():
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
    inconsistency = next((f for f in findings if f["type"] == "version_inconsistency"), None)
    assert inconsistency is not None
    assert inconsistency["technology"] == "Python"


def test_ci_version_matrix_is_not_false_positive():
    facts, findings = extract_configuration({
        "pyproject.toml": "[project]\nrequires-python = \">=3.12\"\n",
        ".github/workflows/test.yml": """
        jobs:
          test:
            strategy:
              matrix:
                python-version: ['3.10', '3.11', '3.12']
        """
    })
    assert not any(f["type"] == "version_inconsistency" for f in findings)
