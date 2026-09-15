from __future__ import annotations

from collections import OrderedDict


WEAK_PATH_SEGMENTS = {
    "examples",
    "example",
    "docs",
    "test",
    "tests",
    "fixtures",
    "testdata",
    "vendor",
    "third_party",
    "samples",
    "demo",
}


TECHNOLOGY_DEFINITIONS = {
    "CMake": {
        "type": "build_system",
        "identifier": "cmake",
        "matchers": ("cmakelists.txt",),
        "reason": "CMakeLists.txt exists in repository",
    },
    "Docker": {
        "type": "container",
        "identifier": "docker",
        "matchers": ("dockerfile",),
        "reason": "Dockerfile exists in repository",
    },
    "Docker Compose": {
        "type": "container",
        "identifier": "docker-compose",
        "matchers": (
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ),
        "reason": "Docker Compose configuration exists in repository",
    },
    "Python": {
        "type": "runtime",
        "identifier": "python",
        "matchers": (
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            "pipfile",
        ),
        "reason": "Python project configuration detected",
    },
    "Node.js": {
        "type": "runtime",
        "identifier": "nodejs",
        "matchers": ("package.json",),
        "reason": "Node.js project metadata detected",
    },
    "Jenkins": {
        "type": "ci",
        "identifier": "jenkins",
        "matchers": ("jenkinsfile",),
        "reason": "Jenkinsfile exists in repository",
    },
    "GitHub Actions": {
        "type": "ci",
        "identifier": "github-actions",
        "matchers": (".github/workflows/",),
        "reason": "GitHub Actions workflow detected in repository",
    },
    "Maven": {
        "type": "build_system",
        "identifier": "maven",
        "matchers": ("pom.xml",),
        "reason": "Maven project configuration detected",
    },
    "Gradle": {
        "type": "build_system",
        "identifier": "gradle",
        "matchers": ("build.gradle", "build.gradle.kts"),
        "reason": "Gradle build file detected",
    },
    "Yocto / BitBake": {
        "type": "build_system",
        "identifier": "yocto-bitbake",
        "matchers": (
            ".bb",
            ".bbappend",
            ".bbclass",
            "conf/layer.conf",
        ),
        "reason": "Yocto / BitBake metadata exists in repository",
    },
}


def _normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").lower()


def _is_weak_path(path: str) -> bool:
    normalized = _normalize_path(path)
    segments = [segment for segment in normalized.split("/") if segment]
    return any(segment in WEAK_PATH_SEGMENTS for segment in segments)


def _has_match(path: str, matcher: str) -> bool:
    normalized = _normalize_path(path)
    if matcher.startswith("."):
        return matcher in normalized or matcher.replace(".", "") in normalized
    if matcher.endswith(".bb"):
        return normalized.endswith(matcher)
    if matcher == "conf/layer.conf":
        return normalized.endswith(matcher)
    if matcher == ".github/workflows/":
        return ".github/workflows/" in normalized
    return normalized.endswith(matcher)


def _confidence_for_path(path: str) -> float:
    return 0.55 if _is_weak_path(path) else 1.0


def extract_technologies(file_paths):
    grouped = OrderedDict()

    for file_path in file_paths:
        normalized = _normalize_path(file_path)
        for name, definition in TECHNOLOGY_DEFINITIONS.items():
            if any(_has_match(normalized, matcher) for matcher in definition["matchers"]):
                entry = grouped.setdefault(
                    name,
                    {
                        "type": definition["type"],
                        "name": name,
                        "identifier": definition["identifier"],
                        "evidence": [],
                        "confidence": 0.0,
                    },
                )

                confidence = _confidence_for_path(normalized)
                entry["confidence"] = max(entry["confidence"], confidence)
                entry["evidence"].append(
                    {
                        "file": file_path,
                        "line": None,
                        "snippet": None,
                        "reason": definition["reason"],
                    }
                )

    entities = []
    facts = []

    for name, values in grouped.items():
        entities.append(
            {
                "type": values["type"],
                "name": values["name"],
                "identifier": values["identifier"],
            }
        )

        facts.append(
            {
                "type": "technology_detected",
                "subject": values["name"],
                "value": True,
                "confidence": values["confidence"],
                "extractor": "file_presence",
                "evidence": values["evidence"],
            }
        )

    return entities, facts
