from app.services.scanner import build_repository_graph


def test_python_internal_imports_are_resolved():
    graph = build_repository_graph({
        "backend/main.py": "from backend import api\nimport backend.service\n",
        "backend/api.py": "from backend import service\n",
        "backend/service.py": "VALUE = 1\n",
    })

    relationships = graph["relationships"]
    assert any(
        item["source"] == "backend/main.py" and item["target"] == "backend/api.py" and item["type"] == "imports"
        for item in relationships
    )
    assert any(
        item["source"] == "backend/main.py" and item["target"] == "backend/service.py" and item["type"] == "imports"
        for item in relationships
    )


def test_python_from_import_prefers_matching_submodule_over_package_init():
    graph = build_repository_graph({
        "backend/main.py": "from backend import service\n",
        "backend/__init__.py": "",
        "backend/service.py": "VALUE = 1\n",
    })

    assert any(
        item["source"] == "backend/main.py"
        and item["target"] == "backend/service.py"
        and item["type"] == "imports"
        for item in graph["relationships"]
    )


def test_python_from_import_symbol_falls_back_to_module():
    graph = build_repository_graph({
        "backend/main.py": "from backend.service import UserService\n",
        "backend/service.py": "class UserService: pass\n",
    })

    assert any(
        item["source"] == "backend/main.py"
        and item["target"] == "backend/service.py"
        and item["type"] == "imports"
        for item in graph["relationships"]
    )


def test_javascript_relative_imports_are_resolved():
    graph = build_repository_graph({
        "web/server.js": "const api = require('./api');\nimport x from './lib/x';\n",
        "web/api.js": "module.exports = {}\n",
        "web/lib/x.js": "export default 1;\n",
    })

    relationships = graph["relationships"]
    assert any(
        item["source"] == "web/server.js" and item["target"] == "web/api.js" and item["type"] == "imports"
        for item in relationships
    )
    assert any(
        item["source"] == "web/server.js" and item["target"] == "web/lib/x.js" and item["type"] == "imports"
        for item in relationships
    )


def test_javascript_typescript_relative_file_and_index_imports_are_resolved():
    graph = build_repository_graph({
        "web/server.ts": (
            'import jsFile from "./api.js";\n'
            'import tsFile from "./types.ts";\n'
            'import jsIndex from "./js-package";\n'
            'import tsIndex from "./ts-package";\n'
        ),
        "web/api.js": "export default {};\n",
        "web/types.ts": "export type User = {};\n",
        "web/js-package/index.js": "export default {};\n",
        "web/ts-package/index.ts": "export default {};\n",
    })

    relationships = graph["relationships"]
    expected_targets = {
        "web/api.js",
        "web/types.ts",
        "web/js-package/index.js",
        "web/ts-package/index.ts",
    }
    assert {
        item["target"]
        for item in relationships
        if item["source"] == "web/server.ts" and item["type"] == "imports"
    } == expected_targets


def test_javascript_external_packages_and_node_builtins_are_not_internal_relationships():
    graph = build_repository_graph({
        "web/server.js": (
            'import express from "express";\n'
            'const fs = require("fs");\n'
            'const path = require("node:path");\n'
        ),
        "web/express.js": "export default {};\n",
    })

    assert graph["relationships"] == []


def test_cpp_local_includes_are_resolved_and_system_includes_ignored():
    graph = build_repository_graph({
        "src/main.cpp": '#include "service.hpp"\n#include <vector>\n#include "util/helpers.hpp"\n',
        "src/service.hpp": "struct Service {};\n",
        "src/util/helpers.hpp": "struct Helper {};\n",
    })

    relationships = graph["relationships"]
    assert any(
        item["source"] == "src/main.cpp" and item["target"] == "src/service.hpp" and item["type"] == "includes"
        for item in relationships
    )
    assert any(
        item["source"] == "src/main.cpp" and item["target"] == "src/util/helpers.hpp" and item["type"] == "includes"
        for item in relationships
    )
    assert all(item["source"] != "src/main.cpp" or item["target"] != "vector" for item in relationships)


def test_contrib_relationships_remain_secondary_scoped():
    graph = build_repository_graph({
        "contrib/tool/main.c": '#include "helper.h"\n',
        "contrib/tool/helper.h": "#define VALUE 1\n",
    })

    relationships = graph["relationships"]
    assert any(
        item["source"] == "contrib/tool/main.c"
        and item["target"] == "contrib/tool/helper.h"
        and item["type"] == "includes"
        and item["scope"] == "subproject"
        for item in relationships
    )


def test_unresolved_external_imports_do_not_create_fake_relationships():
    graph = build_repository_graph({
        "backend/main.py": "import fastapi\nfrom fastapi import FastAPI\n",
        "backend/app.py": "import os\n",
    })

    relationships = graph["relationships"]
    assert not any(item["target"] == "fastapi" for item in relationships)
    assert not any(item["target"] == "backend/fastapi.py" for item in relationships)


def test_example_and_test_relationships_remain_secondary_and_do_not_pollute_primary_graph():
    graph = build_repository_graph({
        "examples/demo/main.py": "from helper import value\n",
        "examples/demo/helper.py": "value = 1\n",
        "tests/test_api.py": "from backend.api import router\n",
        "backend/api.py": "router = {}\n",
    })

    relationships = graph["relationships"]
    assert any(
        item["source"] == "examples/demo/main.py" and item["target"] == "examples/demo/helper.py" and item["scope"] == "example"
        for item in relationships
    )
    assert any(
        item["source"] == "tests/test_api.py" and item["target"] == "backend/api.py" and item["scope"] == "test"
        for item in relationships
    )


def test_duplicate_relationships_are_deduplicated():
    graph = build_repository_graph({
        "backend/main.py": "import api\nfrom api import router\n",
        "backend/api.py": "router = {}\n",
    })

    relationships = graph["relationships"]
    matches = [item for item in relationships if item["source"] == "backend/main.py" and item["target"] == "backend/api.py"]
    assert len(matches) == 1
