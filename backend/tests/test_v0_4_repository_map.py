from app.services.scanner import build_repository_map


def test_simple_python_backend_repository_map():
    repository_map = build_repository_map([
        "backend/app/main.py",
        "backend/pyproject.toml",
        "backend/tests/test_app.py",
        "README.md",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["backend/"]["role"] == "backend"
    assert any(item["path"] == "backend/app/main.py" for item in repository_map["entry_points"])
    assert any(item["path"] == "backend/pyproject.toml" for item in repository_map["important_files"])


def test_simple_node_frontend_repository_map():
    repository_map = build_repository_map([
        "frontend/src/index.ts",
        "frontend/package.json",
        "frontend/src/App.tsx",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["frontend/"]["role"] == "frontend"
    assert any(item["path"] == "frontend/src/index.ts" for item in repository_map["entry_points"])


def test_backend_and_frontend_repo_keeps_both_roles():
    repository_map = build_repository_map([
        "backend/app/main.py",
        "backend/pyproject.toml",
        "frontend/src/index.ts",
        "frontend/package.json",
        "README.md",
    ])

    roles = {item["path"]: item["role"] for item in repository_map["directories"]}
    assert roles["backend/"] == "backend"
    assert roles["frontend/"] == "frontend"


def test_test_and_example_main_py_are_not_primary_entry_points():
    repository_map = build_repository_map([
        "tests/app.py",
        "examples/demo/main.py",
        "vendor/src/main.py",
        "build/generated/main.cpp",
    ])

    assert not any(item["path"] == "tests/app.py" for item in repository_map["entry_points"])
    assert not any(item["path"] == "examples/demo/main.py" for item in repository_map["entry_points"])
    assert not any(item["path"] == "vendor/src/main.py" for item in repository_map["entry_points"])
    assert not any(item["path"] == "build/generated/main.cpp" for item in repository_map["entry_points"])


def test_monorepo_keeps_multiple_subprojects_separate():
    repository_map = build_repository_map([
        "apps/backend/app/main.py",
        "apps/backend/pyproject.toml",
        "apps/frontend/src/index.ts",
        "apps/frontend/package.json",
        "tools/migrator/main.py",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["apps/backend/"]["role"] == "backend"
    assert directories["apps/frontend/"]["role"] == "frontend"
    assert directories["tools/"]["role"] == "scripts"


def test_unknown_directory_remains_unknown_and_important_files_are_detected():
    repository_map = build_repository_map([
        "misc/notes.txt",
        "Dockerfile",
        "CMakeLists.txt",
        ".github/workflows/test.yml",
        "Makefile",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["misc/"]["role"] == "unknown"
    assert any(item["path"] == "Dockerfile" for item in repository_map["important_files"])
    assert any(item["path"] == "CMakeLists.txt" for item in repository_map["important_files"])
    assert any(item["path"] == ".github/workflows/test.yml" for item in repository_map["important_files"])


def test_python_entry_point_and_node_entry_point_are_detected():
    python_map = build_repository_map(["service/app.py", "service/README.md"])
    node_map = build_repository_map(["web/server.js", "web/main.ts"])

    assert any(item["path"] == "service/app.py" for item in python_map["entry_points"])
    assert any(item["path"] == "web/server.js" for item in node_map["entry_points"])
    assert any(item["path"] == "web/main.ts" for item in node_map["entry_points"])


def test_github_workflow_directory_is_classified_as_ci():
    repository_map = build_repository_map([
        ".github/workflows/test.yml",
        ".github/workflows/ci.yml",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories[".github/"]["role"] == "configuration"
    assert directories[".github/workflows/"]["role"] == "ci"


def test_weak_parent_context_takes_precedence_over_final_directory_name():
    repository_map = build_repository_map([
        "examples/mvc/lib/service.js",
        "tests/unit/helpers.py",
        "vendor/pkg/lib/index.js",
        "docs/guides/README.md",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["examples/"]["role"] == "examples"
    assert "examples/mvc/" not in directories
    assert "examples/mvc/lib/" not in directories
    assert directories["tests/"]["role"] == "tests"
    assert directories["vendor/"]["role"] == "vendor"
    assert directories["docs/"]["role"] == "documentation"


def test_unknown_deep_descendants_are_pruned_from_directory_map():
    repository_map = build_repository_map([
        "pkg/feature/x/y/z.py",
        "pkg/feature/service/main.py",
        "pkg/feature/README.md",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert "pkg/" in directories
    assert "pkg/feature/" in directories
    assert "pkg/feature/x/" not in directories
    assert "pkg/feature/x/y/" not in directories


def test_nested_readme_evidence_is_not_described_as_repository_level_docs():
    repository_map = build_repository_map([
        "README.md",
        "docs/guides/README.md",
        "examples/demo/README.md",
    ])

    important_files = {item["path"]: item for item in repository_map["important_files"]}
    root_reason = important_files["README.md"]["evidence"][0]["reason"].lower()
    nested_reason = important_files["docs/guides/README.md"]["evidence"][0]["reason"].lower()
    assert "repository-level" in root_reason
    assert "repository-level" not in nested_reason


def test_weak_secondary_descendants_are_collapsed_from_repository_tree():
    repository_map = build_repository_map([
        "examples/demo/app/main.py",
        "examples/demo/README.md",
        "examples/demo/package.json",
        "tests/unit/helpers.py",
        "vendor/foo/lib/index.js",
        "build/generated/main.cpp",
        "backend/app/main.py",
        "backend/pyproject.toml",
    ])

    directories = {item["path"]: item for item in repository_map["directories"]}
    assert directories["examples/"]["role"] == "examples"
    assert "examples/demo/" not in directories
    assert "examples/demo/app/" not in directories
    assert "tests/" in directories
    assert "tests/unit/" not in directories
    assert "vendor/" in directories
    assert "vendor/foo/" not in directories
    assert "build/" in directories
    assert "build/generated/" not in directories
    assert directories["backend/"]["role"] == "backend"
