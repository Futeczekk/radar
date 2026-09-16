from app.services.impact import build_component_impact, build_file_impact


def file_graph(relationships, nodes):
    return {"nodes": [{"id": node, "type": "file"} for node in nodes], "relationships": relationships}


def relationship(source, target, scope="project"):
    return {
        "source": source,
        "target": target,
        "type": "imports",
        "confidence": 1.0,
        "scope": scope,
        "evidence": [{"source_file": source, "target_file": target}],
    }


def test_file_impact_returns_direct_and_transitive_dependents_with_paths():
    graph = file_graph([
        relationship("backend/main.py", "backend/api.py"),
        relationship("backend/api.py", "backend/service.py"),
        relationship("backend/service.py", "backend/database.py"),
    ], [
        "backend/main.py", "backend/api.py", "backend/service.py", "backend/database.py",
    ])

    impact = build_file_impact(graph, "backend/database.py")

    assert impact["found"] is True
    assert [item["node"] for item in impact["direct_dependents"]] == ["backend/service.py"]
    assert [(item["node"], item["distance"]) for item in impact["transitive_dependents"]] == [
        ("backend/api.py", 2),
        ("backend/main.py", 3),
    ]
    assert impact["transitive_dependents"][1]["path"] == [
        "backend/main.py", "backend/api.py", "backend/service.py", "backend/database.py",
    ]


def test_file_impact_uses_reverse_direction_and_isolated_nodes_are_empty():
    graph = file_graph([relationship("backend/main.py", "backend/api.py")], [
        "backend/main.py", "backend/api.py", "backend/isolated.py",
    ])

    assert build_file_impact(graph, "backend/main.py")["direct_dependents"] == []
    assert build_file_impact(graph, "backend/isolated.py")["transitive_dependents"] == []
    assert [item["node"] for item in build_file_impact(graph, "backend/api.py")["direct_dependents"]] == [
        "backend/main.py",
    ]


def test_file_impact_handles_cycles_and_deduplicates_nodes():
    graph = file_graph([
        relationship("a.py", "b.py"),
        relationship("b.py", "c.py"),
        relationship("c.py", "a.py"),
        relationship("a.py", "c.py"),
    ], ["a.py", "b.py", "c.py"])

    impact = build_file_impact(graph, "a.py")

    assert {item["node"] for item in impact["direct_dependents"] + impact["transitive_dependents"]} == {"b.py", "c.py"}
    assert len(impact["direct_dependents"] + impact["transitive_dependents"]) == 2


def test_file_impact_preserves_secondary_scopes():
    graph = file_graph([
        relationship("tests/test_api.py", "backend/api.py", "test"),
        relationship("examples/demo/main.py", "backend/api.py", "example"),
        relationship("contrib/tool/main.c", "backend/api.py", "subproject"),
    ], [
        "tests/test_api.py", "examples/demo/main.py", "contrib/tool/main.c", "backend/api.py",
    ])

    impact = build_file_impact(graph, "backend/api.py")
    scopes = {item["node"]: item["scope"] for item in impact["direct_dependents"]}
    assert scopes == {
        "contrib/tool/main.c": "subproject",
        "examples/demo/main.py": "example",
        "tests/test_api.py": "test",
    }


def test_unknown_file_target_returns_clean_not_found_result():
    impact = build_file_impact(file_graph([], ["backend/api.py"]), "backend/missing.py")

    assert impact == {
        "target": "backend/missing.py",
        "found": False,
        "direct_dependents": [],
        "transitive_dependents": [],
    }


def test_component_impact_preserves_direction_scope_and_paths():
    graph = {
        "components": [
            {"id": "root", "scope": "project"},
            {"id": "contrib", "scope": "subproject"},
            {"id": "tests", "scope": "test"},
        ],
        "relationships": [
            {"source": "contrib", "target": "root", "type": "depends_on", "scope": "subproject"},
            {"source": "tests", "target": "root", "type": "depends_on", "scope": "test"},
        ],
    }

    impact = build_component_impact(graph, "root")

    assert {item["node"] for item in impact["direct_dependents"]} == {"contrib", "tests"}
    assert {item["scope"] for item in impact["direct_dependents"]} == {"subproject", "test"}
    assert build_component_impact(graph, "contrib")["direct_dependents"] == []
    assert build_component_impact(graph, "missing")["found"] is False
