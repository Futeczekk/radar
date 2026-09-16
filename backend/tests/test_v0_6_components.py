from app.services.scanner import build_component_graph, build_repository_graph, build_repository_map


def _component_graph(paths, relationships=None):
    repository_map = build_repository_map(paths)
    repository_graph = build_repository_graph(relationships or {})
    return build_component_graph(paths, repository_map, repository_graph)


def _component(graph, component_id):
    return next(item for item in graph["components"] if item["id"] == component_id)


def test_backend_component_has_explicit_project_membership_and_evidence():
    paths = ["backend/main.py", "backend/api.py", "README.md"]
    graph = _component_graph(paths)

    backend = _component(graph, "backend")
    assert backend["type"] == "backend"
    assert backend["scope"] == "project"
    assert backend["files"] == ["backend/api.py", "backend/main.py"]
    assert backend["evidence"]
    assert all(item["id"] != "README.md" for item in graph["components"])


def test_secondary_directories_keep_scope_and_do_not_become_primary_components():
    paths = [
        "tests/api/test_api.py",
        "examples/backend/main.py",
        "contrib/service/main.c",
        "build/generated.c",
        "vendor/library/lib.c",
    ]
    graph = _component_graph(paths)

    assert _component(graph, "tests")["scope"] == "test"
    assert _component(graph, "examples")["scope"] == "example"
    assert _component(graph, "contrib")["scope"] == "subproject"
    assert _component(graph, "build")["scope"] == "generated"
    assert _component(graph, "vendor")["scope"] == "vendor"
    assert all(item["scope"] != "project" for item in graph["components"])


def test_root_library_and_monorepo_components_remain_separate():
    paths = [
        "package.json",
        "index.js",
        "apps/api/main.py",
        "apps/web/index.ts",
        "packages/common/index.ts",
    ]
    graph = _component_graph(paths)

    assert _component(graph, "root")["type"] == "library"
    assert _component(graph, "apps/api")["type"] == "api"
    assert _component(graph, "apps/web")["type"] == "frontend"
    assert _component(graph, "packages/common")["type"] == "library"


def test_express_like_root_library_merges_with_delegated_lib_directory():
    paths = [
        "package.json",
        "index.js",
        "lib/express.js",
        "lib/application.js",
        "test/app.js",
        "examples/hello/index.js",
    ]
    graph = _component_graph(paths, {
        "index.js": "module.exports = require('./lib/express');\n",
        "lib/express.js": "module.exports = require('./application');\n",
        "lib/application.js": "module.exports = {};\n",
        "test/app.js": "require('../lib/express');\n",
        "examples/hello/index.js": "require('../../lib/express');\n",
    })

    root = _component(graph, "root")
    assert root["type"] == "library"
    assert set(root["files"]) == {
        "index.js",
        "lib/application.js",
        "lib/express.js",
        "package.json",
    }
    assert all(item["id"] != "lib" for item in graph["components"])
    assert all(item["source"] != "root" or item["target"] != "lib" for item in graph["relationships"])
    assert _component(graph, "test")["scope"] == "test"
    assert _component(graph, "examples")["scope"] == "example"


def test_root_library_does_not_merge_without_direct_entrypoint_delegation():
    paths = ["package.json", "index.js", "lib/express.js"]
    graph = _component_graph(paths, {
        "index.js": "module.exports = {};\n",
        "lib/express.js": "module.exports = {};\n",
    })

    assert _component(graph, "root")["files"] == ["index.js", "package.json"]
    assert _component(graph, "lib")["files"] == ["lib/express.js"]


def test_weak_directory_remains_unknown():
    graph = _component_graph(["orion/engine/runtime.py"])

    unknown = _component(graph, "orion")
    assert unknown["type"] == "unknown"
    assert unknown["confidence"] < 0.95


def test_component_relationships_derive_from_file_relationships_and_deduplicate():
    paths = ["apps/api/main.py", "apps/web/index.ts"]
    repository_graph = {
        "relationships": [
            {
                "source": "apps/api/main.py",
                "target": "apps/web/index.ts",
                "type": "imports",
                "confidence": 1.0,
            },
            {
                "source": "apps/api/main.py",
                "target": "apps/web/index.ts",
                "type": "imports",
                "confidence": 1.0,
            },
        ]
    }
    graph = build_component_graph(paths, build_repository_map(paths), repository_graph)

    assert graph["relationships"] == [{
        "source": "apps/api",
        "target": "apps/web",
        "type": "depends_on",
        "confidence": 1.0,
        "scope": "project",
        "evidence": [{
            "source_file": "apps/api/main.py",
            "target_file": "apps/web/index.ts",
            "relationship": "imports",
        }, {
            "source_file": "apps/api/main.py",
            "target_file": "apps/web/index.ts",
            "relationship": "imports",
        }],
    }]