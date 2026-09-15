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
        "latest_release": latest_release,
        "previous_release": previous_version,
        "new_release_detected": new_release,
    }
