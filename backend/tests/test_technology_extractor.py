from app.extractors.technology import extract_technologies


def _fact_by_subject(facts, subject):
    for fact in facts:
        if fact["subject"] == subject:
            return fact
    return None


def test_cmake_detection():
    entities, facts = extract_technologies(["CMakeLists.txt"])
    fact = _fact_by_subject(facts, "CMake")
    assert fact is not None
    assert fact["value"] is True
    assert fact["confidence"] == 1.0
    assert any(entity["name"] == "CMake" for entity in entities)


def test_docker_detection():
    entities, facts = extract_technologies(["Dockerfile"])
    fact = _fact_by_subject(facts, "Docker")
    assert fact is not None
    assert fact["confidence"] == 1.0
    assert any(entity["name"] == "Docker" for entity in entities)


def test_docker_compose_detection():
    entities, facts = extract_technologies(["docker-compose.yml"])
    fact = _fact_by_subject(facts, "Docker Compose")
    assert fact is not None
    assert any(entity["name"] == "Docker Compose" for entity in entities)


def test_python_detection():
    entities, facts = extract_technologies(["pyproject.toml", "requirements.txt", "setup.py"])
    fact = _fact_by_subject(facts, "Python")
    assert fact is not None
    assert fact["confidence"] == 1.0
    assert len(fact["evidence"]) >= 2
    assert any(entity["name"] == "Python" for entity in entities)


def test_nodejs_detection():
    entities, facts = extract_technologies(["package.json"])
    fact = _fact_by_subject(facts, "Node.js")
    assert fact is not None
    assert fact["confidence"] == 1.0
    assert any(entity["name"] == "Node.js" for entity in entities)


def test_jenkins_detection():
    entities, facts = extract_technologies(["Jenkinsfile"])
    fact = _fact_by_subject(facts, "Jenkins")
    assert fact is not None
    assert fact["confidence"] == 1.0
    assert any(entity["name"] == "Jenkins" for entity in entities)


def test_github_actions_detection():
    entities, facts = extract_technologies([".github/workflows/build.yml"])
    fact = _fact_by_subject(facts, "GitHub Actions")
    assert fact is not None
    assert any(entity["name"] == "GitHub Actions" for entity in entities)


def test_maven_detection():
    entities, facts = extract_technologies(["pom.xml"])
    fact = _fact_by_subject(facts, "Maven")
    assert fact is not None
    assert any(entity["name"] == "Maven" for entity in entities)


def test_gradle_detection():
    entities, facts = extract_technologies(["build.gradle.kts"])
    fact = _fact_by_subject(facts, "Gradle")
    assert fact is not None
    assert any(entity["name"] == "Gradle" for entity in entities)


def test_yocto_bitbake_detection():
    entities, facts = extract_technologies(["meta/recipes/lim/lim.bb", "conf/layer.conf"])
    fact = _fact_by_subject(facts, "Yocto / BitBake")
    assert fact is not None
    assert any(entity["name"] == "Yocto / BitBake" for entity in entities)


def test_technology_deduplication():
    entities, facts = extract_technologies([
        "pyproject.toml",
        "requirements.txt",
        "setup.py",
        "Dockerfile",
    ])
    python_fact = _fact_by_subject(facts, "Python")
    docker_fact = _fact_by_subject(facts, "Docker")
    assert python_fact is not None
    assert docker_fact is not None
    assert len([fact for fact in facts if fact["subject"] == "Python"]) == 1
    assert len([fact for fact in facts if fact["subject"] == "Docker"]) == 1
    assert len(entities) == 2


def test_empty_repository_has_no_known_technologies():
    entities, facts = extract_technologies(["README.md", "docs/notes.txt"])
    assert entities == []
    assert facts == []


def test_false_positive_package_json_in_docs_examples_is_not_high_confidence():
    entities, facts = extract_technologies(["docs/examples/package.json"])
    fact = _fact_by_subject(facts, "Node.js")
    assert fact is not None
    assert fact["confidence"] < 0.9
    assert any("docs/examples" in evidence["file"] for evidence in fact["evidence"])
