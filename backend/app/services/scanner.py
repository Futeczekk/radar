import re

from app.core.database import (
    get_previous_release,
    save_repository_state,
)
from app.extractors.configuration import extract_configuration
from app.extractors.technology import extract_technologies
from app.sources.github import get_repository, get_latest_release
from app.sources.repository import (
    get_repository_file_contents,
    get_repository_tree,
    select_important_file_paths,
)


GITHUB_PREFIX = "https://github.com/"

WEAK_PATH_SEGMENTS = {
    "tests", "test", "fixtures", "testdata",
    "examples", "example", "demo", "samples",
    "docs", "documentation",
    "vendor", "third_party", "external", "deps",
    "build", "dist", "generated", "out", "target",
}

IMPORTANT_FILE_ROLES = {
    "dockerfile": ("container_build", "Dockerfile declares a container build"),
    "docker-compose.yml": ("container_orchestration", "docker-compose file describes local orchestration"),
    "docker-compose.yaml": ("container_orchestration", "docker-compose file describes local orchestration"),
    "cmakelists.txt": ("build_configuration", "CMakeLists.txt declares the build configuration"),
    "pyproject.toml": ("project_manifest", "Python project manifest defines project configuration"),
    "package.json": ("project_manifest", "Node.js project manifest defines project configuration"),
    "makefile": ("build_script", "Makefile defines build automation"),
    "jenkinsfile": ("ci_pipeline", "Jenkinsfile defines CI automation"),
    ".env.example": ("configuration", "Example environment config is a configuration artifact"),
}

ENTRY_POINT_RULES = {
    "main.py": ("python_entry_point", 0.95),
    "app.py": ("python_entry_point", 0.9),
    "manage.py": ("python_entry_point", 0.9),
    "__main__.py": ("python_entry_point", 0.9),
    "index.js": ("node_entry_point", 0.9),
    "index.ts": ("node_entry_point", 0.9),
    "server.js": ("node_entry_point", 0.9),
    "server.ts": ("node_entry_point", 0.9),
    "main.js": ("node_entry_point", 0.9),
    "main.ts": ("node_entry_point", 0.9),
    "main.c": ("c_entry_point", 0.9),
    "main.cpp": ("c_entry_point", 0.9),
    "application.java": ("java_entry_point", 0.9),
    "main.java": ("java_entry_point", 0.9),
}


def _normalize_repo_path(path: str):
    return path.replace("\\", "/").strip("/")


def _directory_role_for_path(dir_path: str):
    cleaned = dir_path.strip("/").lower()
    segments = [segment for segment in cleaned.split("/") if segment]
    if not segments:
        return "unknown"

    if ".github" in segments and "workflows" in segments:
        return "ci"
    if ".github" in segments:
        return "configuration"

    if any(segment in WEAK_PATH_SEGMENTS for segment in segments):
        for segment in segments:
            if segment in WEAK_PATH_SEGMENTS:
                return {
                    "tests": "tests",
                    "test": "tests",
                    "fixtures": "tests",
                    "testdata": "tests",
                    "examples": "examples",
                    "example": "examples",
                    "demo": "examples",
                    "samples": "examples",
                    "docs": "documentation",
                    "documentation": "documentation",
                    "vendor": "vendor",
                    "third_party": "vendor",
                    "external": "vendor",
                    "deps": "vendor",
                    "build": "generated",
                    "dist": "generated",
                    "generated": "generated",
                    "out": "generated",
                    "target": "generated",
                }[segment]

    last_segment = segments[-1]
    known = {
        "backend": "backend",
        "server": "backend",
        "api": "api",
        "frontend": "frontend",
        "web": "frontend",
        "ui": "frontend",
        "src": "source",
        "app": "source",
        "lib": "source",
        "tests": "tests",
        "test": "tests",
        "docs": "documentation",
        "documentation": "documentation",
        "scripts": "scripts",
        "tools": "scripts",
        "config": "configuration",
        "configs": "configuration",
        "infra": "infrastructure",
        "infrastructure": "infrastructure",
        "terraform": "infrastructure",
        "k8s": "infrastructure",
        "helm": "infrastructure",
        "examples": "examples",
        "example": "examples",
        "vendor": "vendor",
        "third_party": "vendor",
        "external": "vendor",
        "deps": "vendor",
        "build": "generated",
        "dist": "generated",
        "generated": "generated",
        "out": "generated",
        "target": "generated",
    }

    if last_segment in known:
        return known[last_segment]

    if any(segment in {"frontend", "web", "ui"} for segment in segments):
        return "frontend"
    if any(segment in {"backend", "server"} for segment in segments):
        return "backend"
    if any(segment in {"tests", "test"} for segment in segments):
        return "tests"
    if any(segment in {"docs", "documentation"} for segment in segments):
        return "documentation"
    if any(segment in {"scripts", "tools"} for segment in segments):
        return "scripts"
    if any(segment in {"config", "configs"} for segment in segments):
        return "configuration"
    if any(segment in {"infra", "infrastructure", "terraform", "k8s", "helm"} for segment in segments):
        return "infrastructure"

    return "unknown"


def _directory_evidence(dir_path: str, files: list[str]):
    evidence = []
    for path in sorted(files):
        file_name = path.rsplit("/", 1)[-1].lower()
        if path == dir_path:
            continue
        if not path.startswith(dir_path.rstrip("/") + "/"):
            continue

        if file_name in {"pyproject.toml", "package.json"}:
            evidence.append({"file": path, "reason": "Project manifest found inside directory"})
        elif file_name in {"main.py", "app.py", "manage.py", "__main__.py", "index.js", "index.ts", "server.js", "server.ts", "main.js", "main.ts"}:
            evidence.append({"file": path, "reason": "Likely application entry point found inside directory"})
        elif file_name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "cmakelists.txt"}:
            evidence.append({"file": path, "reason": "Build or deployment configuration found inside directory"})

        if len(evidence) >= 3:
            break

    if not evidence:
        evidence.append({"file": dir_path, "reason": "Directory path was retained for structural context"})

    return evidence


def _important_file_role(path: str):
    normalized = _normalize_repo_path(path)
    segments = [segment for segment in normalized.split("/") if segment]
    file_name = segments[-1].lower()
    if file_name == "readme.md":
        if normalized.lower() == "readme.md":
            return ("documentation", "README is a repository-level documentation entry")
        if any(segment in {"docs", "documentation"} for segment in segments[:-1]):
            return ("documentation", "README is a documentation entry inside the docs tree")
        if any(segment in {"examples", "example", "demo", "samples"} for segment in segments[:-1]):
            return ("documentation", "README is example documentation for a sample or demo")
        return ("documentation", "README is a nested documentation entry")

    exact_role = IMPORTANT_FILE_ROLES.get(file_name)
    if exact_role:
        return exact_role

    if ".github/workflows/" in normalized.lower() and file_name.endswith((".yml", ".yaml")):
        return ("ci_pipeline", "GitHub Actions workflow defines repository CI")

    return None


def _detect_entry_point(path: str):
    normalized = _normalize_repo_path(path)
    segments = normalized.split("/")
    if any(segment.lower() in WEAK_PATH_SEGMENTS for segment in segments[:-1]):
        return None

    file_name = segments[-1].lower()
    if file_name in ENTRY_POINT_RULES:
        role, confidence = ENTRY_POINT_RULES[file_name]
        return {
            "path": normalized,
            "role": role,
            "confidence": confidence,
            "evidence": [{
                "file": normalized,
                "reason": "Filename matches a likely application entry point"
            }],
        }

    return None


def build_repository_map(paths):
    normalized_paths = []
    seen = set()
    for raw_path in paths or []:
        if not raw_path:
            continue
        normalized = _normalize_repo_path(raw_path)
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_paths.append(normalized)

    files_by_directory = {}
    for path in normalized_paths:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        while parent:
            files_by_directory.setdefault(parent, []).append(path)
            parent = parent.rsplit("/", 1)[0] if "/" in parent else ""

    directories = []
    secondary_roles = {"examples", "tests", "vendor", "generated", "documentation"}
    for directory in sorted(files_by_directory):
        role = _directory_role_for_path(directory)
        file_count = len(files_by_directory[directory])
        evidence = _directory_evidence(directory + "/", files_by_directory[directory])
        directory_depth = len([segment for segment in directory.split("/") if segment])
        if role == "unknown" and directory_depth > 2:
            continue

        if role in secondary_roles and directory_depth > 1:
            continue

        directories.append({
            "path": directory + "/",
            "role": role,
            "confidence": 0.95 if role != "unknown" else 0.45,
            "file_count": file_count,
            "evidence": evidence,
        })

    important_files = []
    for path in sorted(normalized_paths):
        role_info = _important_file_role(path)
        if not role_info:
            continue
        role, reason = role_info
        important_files.append({
            "path": path,
            "role": role,
            "confidence": 0.95,
            "evidence": [{"file": path, "reason": reason}],
        })

    entry_points = []
    for path in sorted(normalized_paths):
        entry_point = _detect_entry_point(path)
        if entry_point is not None:
            entry_points.append(entry_point)

    return {
        "directories": directories,
        "important_files": important_files,
        "entry_points": entry_points,
    }


def _path_scope(path: str):
    imported_segments = [segment for segment in _normalize_repo_path(path).split("/") if segment]
    if "contrib" in imported_segments:
        return "subproject"
    if any(segment in WEAK_PATH_SEGMENTS for segment in imported_segments):
        for segment in imported_segments:
            if segment in WEAK_PATH_SEGMENTS:
                return {
                    "tests": "test",
                    "test": "test",
                    "fixtures": "test",
                    "testdata": "test",
                    "examples": "example",
                    "example": "example",
                    "demo": "example",
                    "samples": "example",
                    "docs": "documentation",
                    "documentation": "documentation",
                    "vendor": "vendor",
                    "third_party": "vendor",
                    "external": "vendor",
                    "deps": "vendor",
                    "build": "generated",
                    "dist": "generated",
                    "generated": "generated",
                    "out": "generated",
                    "target": "generated",
                }[segment]
    return "project"


def _candidate_python_modules(path: str):
    normalized = _normalize_repo_path(path)
    if normalized.endswith("/__init__.py"):
        return [normalized.rsplit("/", 2)[0].replace("/", ".") if "/" in normalized.rsplit("/", 2)[0] else normalized.rsplit("/", 1)[0].replace("/", ".")]
    if normalized.endswith(".py"):
        stem = normalized[:-3]
        if "/" in stem:
            return [stem.replace("/", ".")]
        return [stem]
    return []


def _resolve_python_import(source_path: str, import_name: str, known_files: set[str], imported_name: str | None = None):
    source_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    module_parts = import_name.replace(".", "/")

    if import_name.startswith("."):
        return None

    candidates = []
    if imported_name:
        candidates.append(f"{module_parts}/{imported_name}")
    if source_dir:
        if imported_name:
            candidates.append(f"{source_dir}/{module_parts}/{imported_name}")
    candidates.append(module_parts)
    if source_dir:
        candidates.append(f"{source_dir}/{module_parts}")

    seen_candidates = set()
    for candidate in candidates:
        if candidate in seen_candidates:
            continue
        seen_candidates.add(candidate)
        for suffix in (".py", "/__init__.py"):
            possible = candidate + suffix
            if possible in known_files:
                return possible
            if candidate.endswith("/__init__"):
                package_candidate = candidate[:-9]
                if package_candidate + ".py" in known_files:
                    return package_candidate + ".py"

    return None


def _resolve_js_import(source_path: str, import_path: str, known_files: set[str]):
    if not import_path.startswith("./") and not import_path.startswith("../"):
        return None

    base_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    target = import_path
    if target.startswith("./"):
        target = target[2:]
    elif target.startswith("../"):
        target = target[3:]

    normalized_base = _normalize_repo_path(base_dir)
    potential = []
    if target:
        for suffix in ("", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"):
            potential.append(_normalize_repo_path(f"{normalized_base}/{target}{suffix}"))
            potential.append(_normalize_repo_path(f"{normalized_base}/{target}/index.js"))
            potential.append(_normalize_repo_path(f"{normalized_base}/{target}/index.ts"))
            potential.append(_normalize_repo_path(f"{normalized_base}/{target}/index.jsx"))
            potential.append(_normalize_repo_path(f"{normalized_base}/{target}/index.tsx"))
    for candidate in potential:
        if candidate in known_files:
            return candidate
    return None


def _resolve_cpp_include(source_path: str, include_name: str, known_files: set[str]):
    if include_name.startswith("<"):
        return None
    source_dir = source_path.rsplit("/", 1)[0] if "/" in source_path else ""
    candidates = []
    for prefix in [source_dir, ""]:
        if prefix:
            candidates.append(_normalize_repo_path(f"{prefix}/{include_name}"))
        else:
            candidates.append(_normalize_repo_path(include_name))
    for candidate in candidates:
        if candidate in known_files:
            return candidate
    return None


def _extract_python_relationships(file_contents: dict[str, str]):
    relationships = []
    known_files = set(file_contents)
    for path, content in file_contents.items():
        scope = _path_scope(path)
        for line_number, line in enumerate(content.splitlines(), start=1):
            import_match = re.match(r"^\s*import\s+([A-Za-z0-9_\.]+)", line)
            if import_match:
                import_name = import_match.group(1)
                resolved = _resolve_python_import(path, import_name, known_files)
                if resolved and resolved != path:
                    relationships.append({
                        "source": path,
                        "target": resolved,
                        "type": "imports",
                        "confidence": 1.0,
                        "scope": scope,
                        "evidence": [{
                            "file": path,
                            "line": line_number,
                            "snippet": line.strip(),
                            "reason": f"Python import resolves to {resolved}",
                        }],
                    })
                continue

            from_match = re.match(r"^\s*from\s+([A-Za-z0-9_\.]+)\s+import\s+([A-Za-z0-9_\s,\*]+)", line)
            if from_match:
                import_name = from_match.group(1)
                imported_names = [value.strip() for value in from_match.group(2).split(",") if value.strip() and value.strip() != "*"]
                if not imported_names:
                    continue
                for imported_name in imported_names:
                    resolved = _resolve_python_import(path, import_name, known_files, imported_name)
                    if resolved and resolved != path:
                        relationships.append({
                            "source": path,
                            "target": resolved,
                            "type": "imports",
                            "confidence": 1.0,
                            "scope": scope,
                            "evidence": [{
                                "file": path,
                                "line": line_number,
                                "snippet": line.strip(),
                                "reason": f"Python import resolves to {resolved}",
                            }],
                        })
    return relationships


def _extract_js_relationships(file_contents: dict[str, str]):
    relationships = []
    known_files = set(file_contents)
    for path, content in file_contents.items():
        scope = _path_scope(path)
        for line_number, line in enumerate(content.splitlines(), start=1):
            matches = __import__("re").finditer(r"(?:import\s+(?:[^;]+?\s+from\s+)?|require\s*\()\s*['\"]([^'\"]+)['\"]", line)
            for match in matches:
                target_ref = match.group(1)
                if not target_ref.startswith("./") and not target_ref.startswith("../"):
                    continue
                resolved = _resolve_js_import(path, target_ref, known_files)
                if not resolved or resolved == path:
                    continue
                relationships.append({
                    "source": path,
                    "target": resolved,
                    "type": "imports",
                    "confidence": 1.0,
                    "scope": scope,
                    "evidence": [{
                        "file": path,
                        "line": line_number,
                        "snippet": line.strip(),
                        "reason": f"Relative module import resolves to {resolved}",
                    }],
                })
    return relationships


def _extract_cpp_relationships(file_contents: dict[str, str]):
    relationships = []
    known_files = set(file_contents)
    for path, content in file_contents.items():
        scope = _path_scope(path)
        for line_number, line in enumerate(content.splitlines(), start=1):
            match = __import__("re").search(r'#include\s*["<]([^">]+)[">]', line)
            if not match:
                continue
            include_ref = match.group(1)
            if include_ref.startswith("<"):
                continue
            resolved = _resolve_cpp_include(path, include_ref, known_files)
            if not resolved or resolved == path:
                continue
            relationships.append({
                "source": path,
                "target": resolved,
                "type": "includes",
                "confidence": 1.0,
                "scope": scope,
                "evidence": [{
                    "file": path,
                    "line": line_number,
                    "snippet": line.strip(),
                    "reason": f"Local include resolves to {resolved}",
                }],
            })
    return relationships


def build_repository_graph(file_contents):
    file_contents = file_contents or {}
    relationships = []
    if not file_contents:
        return {"nodes": [], "relationships": []}

    nodes = [{"id": path, "type": "file"} for path in sorted(file_contents)]
    relationships.extend(_extract_python_relationships(file_contents))
    relationships.extend(_extract_js_relationships(file_contents))
    relationships.extend(_extract_cpp_relationships(file_contents))

    deduped = []
    seen = set()
    for relationship in relationships:
        key = (relationship["source"], relationship["target"], relationship["type"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relationship)

    return {
        "nodes": nodes,
        "relationships": deduped,
    }


def scan_repository(url: str):
    if not url.startswith(GITHUB_PREFIX):
        raise ValueError(
            "Currently only GitHub repositories are supported"
        )

    repository = url.removeprefix(GITHUB_PREFIX).rstrip("/")

    data = get_repository(repository)
    files = get_repository_tree(repository)
    important_paths = select_important_file_paths(files)
    important_contents = get_repository_file_contents(repository, data.get("default_branch", "main"), important_paths)
    entities, tech_facts = extract_technologies(files)
    config_facts, findings = extract_configuration(important_contents)
    facts = tech_facts + config_facts
    release_data = get_latest_release(repository)

    latest_release = None
    current_version = None

    if release_data:
        current_version = release_data["tag_name"]

        latest_release = {
            "version": current_version,
            "published_at": release_data["published_at"],
            "url": release_data["html_url"]
        }

    previous_version = get_previous_release(repository)

    new_release = (
        previous_version is not None
        and current_version is not None
        and previous_version != current_version
    )

    save_repository_state(
        repository,
        current_version
    )

    repository_map = build_repository_map(files)
    repository_graph = build_repository_graph({
        path: content
        for path, content in get_repository_file_contents(
            repository,
            data.get("default_branch", "main"),
            files[:200]
        ).items()
    })

    return {
        "repository": data["full_name"],
        "description": data["description"],
        "stars": data["stargazers_count"],
        "open_issues": data["open_issues_count"],
        "default_branch": data["default_branch"],
        "files_scanned": len(files),
        "entities": entities,
        "facts": facts,
        "findings": findings,
        "repository_map": repository_map,
        "repository_graph": repository_graph,
        "latest_release": latest_release,
        "previous_release": previous_version,
        "new_release_detected": new_release,
    }
