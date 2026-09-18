from app.core.technical_changes import evaluate_technical_changes
from app.services.diff import diff_snapshots


def evidence(path, reason="deterministic"):
    return [{"file": path, "line": 1, "snippet": None, "reason": reason}]


def fact(fact_type, subject, value, path, scope="project", **extra):
    return {
        "type": fact_type,
        "subject": subject,
        "value": value,
        "confidence": 1.0,
        "extractor": "test",
        "evidence": evidence(path),
        "scope": scope,
        **extra,
    }


def relationship(source, target, kind="imports", scope="project"):
    return {
        "source": source,
        "target": target,
        "type": kind,
        "scope": scope,
        "confidence": 1.0,
        "evidence": evidence(source),
    }


def snapshot(commit, files=None, facts=None, relationships=None, components=None, component_relationships=None):
    files = files or []
    return {
        "repository": "demo/repo",
        "ref": commit,
        "commit_sha": commit,
        "files": [{"path": path, "sha": f"{commit}-{path}"} for path in files],
        "facts": facts or [],
        "repository_graph": {
            "nodes": [{"id": path, "type": "file"} for path in files],
            "relationships": relationships or [],
        },
        "component_graph": {
            "components": components or [],
            "relationships": component_relationships or [],
        },
    }


def changes(base, target):
    return diff_snapshots(base, target)["technical_changes"]


def change_types(items):
    return [(item["category"], item["subject"], item["change_type"]) for item in items]


def test_same_snapshot_has_no_technical_changes():
    state = snapshot("a", ["README.md"])

    result = diff_snapshots(state, state)

    assert result["technical_changes"] == []


def test_runtime_configuration_changes_are_classified_with_before_after_evidence():
    cases = [
        ("python.required_version", "Python", ">=3.10", ">=3.12", "runtime", "version_changed"),
        ("node.required_version", "Node.js", ">=18", ">=20", "runtime", "version_changed"),
        ("docker.base_image", "Docker", "python:3.10", "python:3.12", "runtime", "base_image_changed"),
        ("cmake.minimum_version", "CMake", "3.20", "3.28", "build", "minimum_version_changed"),
        ("ci.python_version", "Python", "3.10", "3.11", "runtime", "ci_runtime_changed"),
    ]

    for index, (fact_type, subject, before_value, after_value, category, change_type) in enumerate(cases):
        before = snapshot("a", facts=[fact(fact_type, subject, before_value, f"before-{index}.yml", "ci" if fact_type.startswith("ci.") else "project")])
        after = snapshot("b", facts=[fact(fact_type, subject, after_value, f"after-{index}.yml", "ci" if fact_type.startswith("ci.") else "project")])

        result = changes(before, after)

        assert change_types(result) == [(category, subject, change_type)]
        item = result[0]
        assert item["before"] == before_value
        assert item["after"] == after_value
        assert item["evidence"]["before"][0]["file"] == f"before-{index}.yml"
        assert item["evidence"]["after"][0]["file"] == f"after-{index}.yml"


def test_configuration_conflict_introduced_and_resolved_are_classified():
    compatible = [
        fact("python.required_version", "Python", ">=3.11", "pyproject.toml", environment="runtime"),
        fact("ci.python_version", "Python", "3.12", ".github/workflows/test.yml", "ci", source_type="ci_config", environment="runtime"),
    ]
    incompatible = [dict(compatible[0]), dict(compatible[1])]
    incompatible[1]["value"] = "3.10"

    introduced = changes(snapshot("a", facts=compatible), snapshot("b", facts=incompatible))
    assert ("configuration_conflict", "Python", "conflict_introduced") in change_types(introduced)
    introduced_conflict = next(item for item in introduced if item["category"] == "configuration_conflict")
    assert introduced_conflict["after"]["status"] == "incompatible"

    resolved = changes(snapshot("b", facts=incompatible), snapshot("c", facts=compatible))
    assert ("configuration_conflict", "Python", "conflict_resolved") in change_types(resolved)
    resolved_conflict = next(item for item in resolved if item["category"] == "configuration_conflict")
    assert resolved_conflict["before"]["status"] == "incompatible"


def test_configuration_conflict_observation_change_is_classified():
    before = [
        fact("python.required_version", "Python", ">=3.11", "pyproject.toml", environment="runtime"),
        fact("ci.python_version", "Python", "3.10", ".github/workflows/test.yml", "ci", source_type="ci_config", environment="runtime"),
    ]
    after = [dict(before[0]), dict(before[1])]
    after[1]["value"] = "3.9"

    result = changes(snapshot("a", facts=before), snapshot("b", facts=after))

    assert ("configuration_conflict", "Python", "conflict_changed") in change_types(result)


def test_file_dependency_addition_and_removal_reuse_file_impact():
    before_relationship = relationship("service.py", "database.py")
    after_relationship = relationship("service.py", "cache.py")
    base = snapshot("a", ["service.py", "database.py", "cache.py"], relationships=[before_relationship])
    target = snapshot("b", ["service.py", "database.py", "cache.py"], relationships=[after_relationship])

    result = changes(base, target)

    assert change_types(result) == [
        ("dependency", "service.py -> cache.py", "relationship_added"),
        ("dependency", "service.py -> database.py", "relationship_removed"),
    ]
    assert result[0]["affected_elements"] == ["service.py"]


def test_component_addition_removal_type_change_and_relationship_reuse_component_impact():
    base_components = [{"id": "backend", "type": "backend", "scope": "project", "files": ["service.py"], "confidence": 1.0, "evidence": evidence("service.py")}]
    target_components = [
        {"id": "backend", "type": "service", "scope": "project", "files": ["service.py"], "confidence": 1.0, "evidence": evidence("service.py")},
        {"id": "cache", "type": "data", "scope": "project", "files": ["cache.py"], "confidence": 1.0, "evidence": evidence("cache.py")},
    ]
    result = changes(
        snapshot("a", components=base_components),
        snapshot("b", components=target_components, component_relationships=[relationship("backend", "cache", "depends_on")]),
    )

    assert ("component", "cache", "component_added") in change_types(result)
    assert ("component", "backend", "component_type_changed") in change_types(result)
    assert ("component_dependency", "backend -> cache", "relationship_added") in change_types(result)
    component_relationship = next(item for item in result if item["category"] == "component_dependency")
    assert component_relationship["affected_elements"] == ["backend"]


def test_component_relationship_removal_and_cyclic_dependency_impact_are_deterministic():
    components = [
        {"id": "backend", "type": "backend", "scope": "project", "files": ["a.py"], "confidence": 1.0},
        {"id": "data", "type": "data", "scope": "project", "files": ["b.py"], "confidence": 1.0},
    ]
    removed = relationship("backend", "data", "depends_on")
    base = snapshot("a", ["a.py", "b.py"], relationships=[relationship("a.py", "b.py"), relationship("b.py", "a.py")], components=components, component_relationships=[removed])
    target = snapshot("b", ["a.py", "b.py"], relationships=[relationship("a.py", "b.py"), relationship("b.py", "a.py")], components=components)

    result = changes(base, target)

    assert ("component_dependency", "backend -> data", "relationship_removed") in change_types(result)
    dependency = next(item for item in result if item["category"] == "component_dependency")
    assert dependency["affected_elements"] == ["backend"]


def test_readme_and_weak_scope_only_changes_are_not_technical_changes():
    base = snapshot("a", ["README.md", "tests/test.py"], facts=[fact("python.required_version", "Python", ">=3.10", "tests/pyproject.toml", "test")])
    target = snapshot("b", ["README.md", "tests/test.py"], facts=[fact("python.required_version", "Python", ">=3.12", "tests/pyproject.toml", "test")])

    assert changes(base, target) == []


def test_technical_changes_are_deterministically_ordered_and_deduplicated():
    base = snapshot("a", facts=[fact("python.required_version", "Python", ">=3.10", "pyproject.toml")])
    target = snapshot("b", facts=[fact("python.required_version", "Python", ">=3.11", "pyproject.toml")])

    first = changes(base, target)
    second = evaluate_technical_changes(base, target, diff_snapshots(base, target)["changes"])

    assert first == second
    assert len(first) == 1


def test_diff_preserves_existing_changes_fields_and_adds_technical_changes():
    base = snapshot("a", files=["README.md"])
    target = snapshot("b", files=["README.md"])
    result = diff_snapshots(base, target)

    assert set(result["changes"]) == {"files", "facts", "relationships", "components", "component_relationships", "impact"}
    assert result["technical_changes"] == []


def test_source_neutral_core_accepts_plain_snapshot_dicts_and_cache_equivalent_data():
    base = snapshot("a", facts=[fact("node.required_version", "Node.js", ">=18", "package.json")])
    target = snapshot("b", facts=[fact("node.required_version", "Node.js", ">=20", "package.json")])
    cached_base = {key: value for key, value in base.items()}
    cached_target = {key: value for key, value in target.items()}

    assert changes(base, target) == changes(cached_base, cached_target)