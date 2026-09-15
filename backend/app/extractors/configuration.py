import json
import re
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _make_evidence(file_path: str, line_number: int | None, snippet: str | None, reason: str):
    return {
        "file": file_path,
        "line": line_number,
        "snippet": snippet,
        "reason": reason,
    }


def _scope_for_file(file_path: str):
    normalized = file_path.replace("\\", "/").lower()
    segments = [segment for segment in normalized.split("/") if segment]

    if ".github/workflows/" in normalized:
        return "ci"
    if any(segment in {"examples", "example", "demo", "samples", "docs", "documentation"} for segment in segments):
        return "example"
    if any(segment in {"tests", "test", "fixtures", "testdata"} for segment in segments):
        return "test"
    if any(segment in {"vendor", "third_party", "external", "deps"} for segment in segments):
        return "vendor"
    if any(segment in {"build", "dist", "generated", "out", "target"} for segment in segments):
        return "generated"
    if len(segments) > 1 and segments[0] not in {".github", "src", "docs"}:
        return "subproject"
    return "project"


def _source_type_for_file(file_path: str):
    normalized = file_path.replace("\\", "/").lower()
    if ".github/workflows/" in normalized:
        return "ci_config"
    if normalized.endswith("pyproject.toml") or normalized.endswith("package.json"):
        return "manifest"
    if normalized.endswith("cmakelists.txt"):
        return "build_config"
    if normalized.endswith("dockerfile"):
        return "build_config"
    return "unknown"


def _make_fact(fact_type: str, subject: str, value: Any, confidence: float, extractor: str, evidence: list[dict], *, scope: str | None = None, source_type: str | None = None, environment: str | None = None):
    fact = {
        "type": fact_type,
        "subject": subject,
        "value": value,
        "confidence": confidence,
        "extractor": extractor,
        "evidence": evidence,
    }
    if scope is not None:
        fact["scope"] = scope
    if source_type is not None:
        fact["source_type"] = source_type
    if environment is not None:
        fact["environment"] = environment
    return fact


def _deduplicate_facts(facts):
    unique = []
    seen = set()
    for fact in facts:
        key = (fact["type"], repr(fact.get("value")))
        if key in seen:
            continue
        seen.add(key)
        unique.append(fact)
    return unique


def _version_value(raw: Any):
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return str(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return text.replace("'", "").replace('"', "")
    return None


def _extract_numeric_version(value: str):
    match = re.search(r"\d+(?:\.\d+)+|\d+", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _normalize_requirement(value: str):
    cleaned = value.strip()
    if not cleaned:
        return None
    if cleaned.startswith(">="):
        return (">=", cleaned[2:])
    if cleaned.startswith("<="):
        return ("<=", cleaned[2:])
    if cleaned.startswith("=="):
        return ("==", cleaned[2:])
    if cleaned.startswith("="):
        return ("==", cleaned[1:])
    return (None, cleaned)


def _compares_as_mismatch(requirement_value: str, observed_value: str):
    requirement = _normalize_requirement(requirement_value)
    if requirement[0] != ">=":
        return False
    required = _extract_numeric_version(requirement[1])
    observed = _extract_numeric_version(observed_value)
    if required is None or observed is None:
        return False
    return observed < required


def _parse_cmake(file_path: str, content: str):
    facts = []
    lines = content.splitlines()
    scope = _scope_for_file(file_path)
    source_type = _source_type_for_file(file_path)

    match = re.search(r"cmake_minimum_required\s*\(\s*VERSION\s+([^\)]+)\)", content, flags=re.IGNORECASE)
    if match:
        version = match.group(1).strip()
        line_number = None
        for idx, line in enumerate(lines, start=1):
            if "cmake_minimum_required" in line:
                line_number = idx
                break
        facts.append(
            _make_fact(
                "cmake.minimum_version",
                "CMake",
                version,
                1.0,
                "cmake",
                [_make_evidence(file_path, line_number, line_number and lines[line_number - 1].strip(), "CMake minimum version declared in CMakeLists.txt")],
                scope=scope,
                source_type=source_type,
                environment="build",
            )
        )

    project_match = re.search(r"project\s*\(\s*([^\)]+)\)", content, flags=re.IGNORECASE)
    if project_match:
        project_name = project_match.group(1).strip().split()[0]
        line_number = None
        for idx, line in enumerate(lines, start=1):
            if "project(" in line:
                line_number = idx
                break
        facts.append(
            _make_fact(
                "project.name",
                "Project",
                project_name,
                1.0,
                "cmake",
                [_make_evidence(file_path, line_number, line_number and lines[line_number - 1].strip(), "Project name declared in CMakeLists.txt")],
                scope=scope,
                source_type=source_type,
                environment="build",
            )
        )

    return facts


def _parse_docker(file_path: str, content: str):
    facts = []
    images = []
    evidence = []
    scope = _scope_for_file(file_path)
    source_type = _source_type_for_file(file_path)
    for idx, line in enumerate(content.splitlines(), start=1):
        match = re.match(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)(?:\s+AS\s+\S+)?", line, flags=re.IGNORECASE)
        if not match:
            continue
        image = match.group(1).strip()
        if image and image not in images:
            images.append(image)
            evidence.append(
                _make_evidence(file_path, idx, line.strip(), "Docker base image declared in Dockerfile")
            )

    if images:
        value = images[0] if len(images) == 1 else images
        facts.append(
            _make_fact(
                "docker.base_image",
                "Docker",
                value,
                1.0,
                "dockerfile",
                evidence,
                scope=scope,
                source_type=source_type,
                environment="build",
            )
        )
    return facts


def _parse_pyproject(file_path: str, content: str):
    try:
        parsed = tomllib.loads(content)
    except Exception:
        return []

    project = parsed.get("project") or {}
    requires_python = project.get("requires-python")
    if not requires_python:
        return []

    text = _version_value(requires_python)
    if not text:
        return []

    scope = _scope_for_file(file_path)
    source_type = _source_type_for_file(file_path)
    return [
        _make_fact(
            "python.required_version",
            "Python",
            text,
            1.0,
            "pyproject",
            [_make_evidence(file_path, None, None, "Python requirement declared in pyproject.toml")],
            scope=scope,
            source_type=source_type,
            environment="runtime",
        )
    ]


def _parse_package_json(file_path: str, content: str):
    try:
        parsed = json.loads(content)
    except Exception:
        return []

    node_version = (parsed.get("engines") or {}).get("node")
    if not node_version:
        return []

    text = _version_value(node_version)
    if not text:
        return []

    scope = _scope_for_file(file_path)
    source_type = _source_type_for_file(file_path)
    return [
        _make_fact(
            "node.required_version",
            "Node.js",
            text,
            1.0,
            "package_json",
            [_make_evidence(file_path, None, None, "Node.js requirement declared in package.json")],
            scope=scope,
            source_type=source_type,
            environment="runtime",
        )
    ]


def _iter_workflow_steps(node):
    if isinstance(node, dict):
        if isinstance(node.get("steps"), list):
            for item in node["steps"]:
                yield from _iter_workflow_steps(item)
        if isinstance(node.get("uses"), str):
            yield node
        for value in node.values():
            if isinstance(value, (dict, list)):
                yield from _iter_workflow_steps(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_workflow_steps(item)


def _parse_github_actions(file_path: str, content: str):
    try:
        parsed = yaml.safe_load(content) or {}
    except Exception:
        return []

    facts = []
    seen = set()
    matrix_versions = {}

    if isinstance(parsed, dict):
        strategy = parsed.get("jobs", {})
        if isinstance(strategy, dict):
            for job in strategy.values():
                if not isinstance(job, dict):
                    continue
                matrix = job.get("strategy", {}).get("matrix", {}) if isinstance(job.get("strategy", {}), dict) else {}
                if isinstance(matrix, dict):
                    for key, values in matrix.items():
                        if isinstance(values, list):
                            matrix_versions[key] = values

    for step in _iter_workflow_steps(parsed):
        uses = step.get("uses") or ""
        with_values = step.get("with") or {}
        if not isinstance(with_values, dict):
            continue

        if "actions/setup-python" in uses:
            python_version = with_values.get("python-version")
            if isinstance(python_version, list):
                continue
            version = _version_value(python_version)
            if not version:
                continue
            if python_version == "${{ matrix.python-version }}" and "python-version" in matrix_versions:
                fact_value = matrix_versions["python-version"]
                source_type = "test_matrix"
                environment = "test"
            else:
                fact_value = version
                source_type = "ci_config"
                environment = "runtime"

            key_value = tuple(fact_value) if isinstance(fact_value, list) else fact_value
            key = ("ci.python_version", key_value)
            if key not in seen:
                seen.add(key)
                facts.append(
                    _make_fact(
                        "ci.python_version",
                        "Python",
                        fact_value,
                        1.0,
                        "github_actions",
                        [_make_evidence(file_path, None, None, "Python runtime version declared in GitHub Actions workflow")],
                        scope="ci",
                        source_type=source_type,
                        environment=environment,
                    )
                )

        if "actions/setup-node" in uses:
            node_version = with_values.get("node-version")
            if isinstance(node_version, list):
                continue
            version = _version_value(node_version)
            if not version:
                continue
            if node_version == "${{ matrix.node-version }}" and "node-version" in matrix_versions:
                fact_value = matrix_versions["node-version"]
                source_type = "test_matrix"
                environment = "test"
            else:
                fact_value = version
                source_type = "ci_config"
                environment = "runtime"

            key_value = tuple(fact_value) if isinstance(fact_value, list) else fact_value
            key = ("ci.node_version", key_value)
            if key not in seen:
                seen.add(key)
                facts.append(
                    _make_fact(
                        "ci.node_version",
                        "Node.js",
                        fact_value,
                        1.0,
                        "github_actions",
                        [_make_evidence(file_path, None, None, "Node.js runtime version declared in GitHub Actions workflow")],
                        scope="ci",
                        source_type=source_type,
                        environment=environment,
                    )
                )

    return facts


def _collect_version_inconsistencies(facts):
    findings = []
    technology_values = {
        "Python": {
            "requirement": None,
            "observed": [],
        },
        "Node.js": {
            "requirement": None,
            "observed": [],
        },
    }

    for fact in facts:
        if fact.get("source_type") == "test_matrix":
            continue
        if fact.get("scope") in {"example", "test", "vendor", "generated"}:
            continue
        fact_type = fact["type"]
        value = fact["value"]
        if fact_type == "python.required_version":
            technology_values["Python"]["requirement"] = value
        elif fact_type == "ci.python_version":
            technology_values["Python"]["observed"].append(value)
        elif fact_type == "node.required_version":
            technology_values["Node.js"]["requirement"] = value
        elif fact_type == "ci.node_version":
            technology_values["Node.js"]["observed"].append(value)

    for technology, details in technology_values.items():
        requirement = details["requirement"]
        observed_values = details["observed"]
        if not requirement or not observed_values:
            continue

        for observed in observed_values:
            if isinstance(observed, list):
                continue
            if _compares_as_mismatch(str(requirement), str(observed)):
                findings.append(
                    {
                        "type": "version_inconsistency",
                        "technology": technology,
                        "expected": requirement,
                        "observed": observed,
                        "sources": [
                            fact["evidence"][0]["file"]
                            for fact in facts
                            if fact["type"] in {"python.required_version", "ci.python_version", "node.required_version", "ci.node_version"}
                            and fact["subject"] == technology
                            and fact.get("scope") in {"project", "ci"}
                        ],
                    }
                )
                break

    return findings


def extract_configuration(file_contents):
    facts = []
    for file_path, content in (file_contents or {}).items():
        if not content:
            continue
        normalized = file_path.replace("\\", "/").lower()

        if normalized.endswith("cmakelists.txt"):
            facts.extend(_parse_cmake(file_path, content))
        elif normalized.endswith("dockerfile"):
            facts.extend(_parse_docker(file_path, content))
        elif normalized.endswith("pyproject.toml"):
            facts.extend(_parse_pyproject(file_path, content))
        elif normalized.endswith("package.json"):
            facts.extend(_parse_package_json(file_path, content))
        elif normalized.endswith((".yml", ".yaml")) and ".github/workflows/" in normalized:
            facts.extend(_parse_github_actions(file_path, content))

    facts = _deduplicate_facts(facts)
    findings = _collect_version_inconsistencies(facts)
    return facts, findings
