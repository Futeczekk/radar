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


def _make_fact(fact_type: str, subject: str, value: Any, confidence: float, extractor: str, evidence: list[dict]):
    return {
        "type": fact_type,
        "subject": subject,
        "value": value,
        "confidence": confidence,
        "extractor": extractor,
        "evidence": evidence,
    }


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
            )
        )

    return facts


def _parse_docker(file_path: str, content: str):
    facts = []
    images = []
    evidence = []
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

    return [
        _make_fact(
            "python.required_version",
            "Python",
            text,
            1.0,
            "pyproject",
            [_make_evidence(file_path, None, None, "Python requirement declared in pyproject.toml")],
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

    return [
        _make_fact(
            "node.required_version",
            "Node.js",
            text,
            1.0,
            "package_json",
            [_make_evidence(file_path, None, None, "Node.js requirement declared in package.json")],
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
            key = ("ci.python_version", version)
            if key not in seen:
                seen.add(key)
                facts.append(
                    _make_fact(
                        "ci.python_version",
                        "Python",
                        version,
                        1.0,
                        "github_actions",
                        [_make_evidence(file_path, None, None, "Python runtime version declared in GitHub Actions workflow")],
                    )
                )

        if "actions/setup-node" in uses:
            node_version = with_values.get("node-version")
            if isinstance(node_version, list):
                continue
            version = _version_value(node_version)
            if not version:
                continue
            key = ("ci.node_version", version)
            if key not in seen:
                seen.add(key)
                facts.append(
                    _make_fact(
                        "ci.node_version",
                        "Node.js",
                        version,
                        1.0,
                        "github_actions",
                        [_make_evidence(file_path, None, None, "Node.js runtime version declared in GitHub Actions workflow")],
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
                            if fact["type"] in {"python.required_version", "ci.python_version"} and fact["subject"] == technology
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
