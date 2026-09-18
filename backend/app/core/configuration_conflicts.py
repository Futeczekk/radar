from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.configuration import ConfigurationConflict, ConfigurationObservation
from app.models.facts import Evidence


WEAK_SCOPES = {"test", "example", "vendor", "generated", "subproject", "documentation"}
SUPPORTED_SUBJECTS = {"Python", "Node.js", "CMake"}
VERSION_PATTERN = re.compile(r"^(?P<operator>>=|<=|>|<|==|=)?(?P<version>\d+(?:\.\d+)*(?:\.x)?)$")


@dataclass(frozen=True)
class NormalizedVersion:
    operator: str
    parts: tuple[int, ...]
    wildcard: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "version": ".".join(str(part) for part in self.parts),
            "wildcard": self.wildcard,
        }


def normalize_version(value: Any) -> NormalizedVersion | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or any(token in text for token in ("${", "}", "||", " or ", " and ", ",", "^", "~")):
        return None
    match = VERSION_PATTERN.fullmatch(text)
    if match is None:
        return None
    operator = match.group("operator") or "=="
    version_text = match.group("version")
    pieces = version_text.split(".")
    wildcard = pieces[-1].lower() == "x"
    if wildcard:
        pieces.pop()
    if not pieces or len(pieces) > 3:
        return None
    return NormalizedVersion(operator, tuple(int(piece) for piece in pieces), wildcard)


def _padded(parts: tuple[int, ...], length: int = 3) -> tuple[int, ...]:
    return parts + (0,) * (length - len(parts))


def _runtime_range(version: NormalizedVersion) -> tuple[tuple[int, ...], tuple[int, ...]]:
    lower = _padded(version.parts)
    if version.wildcard or len(version.parts) < 3:
        upper = list(lower)
        upper[len(version.parts) - 1] += 1
        for index in range(len(version.parts), 3):
            upper[index] = 0
        return lower, tuple(upper)
    return lower, tuple(lower[:-1]) + (lower[-1] + 1,)


def _satisfies(requirement: NormalizedVersion, runtime: NormalizedVersion) -> bool | None:
    if requirement.operator not in {"==", ">=", ">", "<=", "<"}:
        return None
    runtime_lower, runtime_upper = _runtime_range(runtime)
    required = _padded(requirement.parts)

    if requirement.operator == "==":
        required_lower, required_upper = _runtime_range(requirement)
        return runtime_lower >= required_lower and runtime_upper <= required_upper
    if requirement.operator == ">=":
        return runtime_upper > required or runtime_lower >= required
    if requirement.operator == ">":
        return runtime_upper > required and runtime_lower > required
    if requirement.operator == "<=":
        return runtime_lower <= required
    if requirement.operator == "<":
        return runtime_lower < required
    return None


def compare_versions(left: Any, right: Any) -> str:
    """Return compatible, incompatible, or unknown for two supported values."""
    first = normalize_version(left)
    second = normalize_version(right)
    if first is None or second is None:
        return "unknown"

    first_is_requirement = first.operator != "=="
    second_is_requirement = second.operator != "=="
    if first_is_requirement and not second_is_requirement:
        result = _satisfies(first, second)
        return "unknown" if result is None else ("compatible" if result else "incompatible")
    if second_is_requirement and not first_is_requirement:
        result = _satisfies(second, first)
        return "unknown" if result is None else ("compatible" if result else "incompatible")
    if not first_is_requirement and not second_is_requirement:
        first_lower, first_upper = _runtime_range(first)
        second_lower, second_upper = _runtime_range(second)
        return "compatible" if max(first_lower, second_lower) < min(first_upper, second_upper) else "incompatible"

    # Two constraints are comparable only when their supported intervals overlap.
    probes = [first.parts, second.parts]
    for parts in probes:
        probe = NormalizedVersion("==", parts, False)
        if _satisfies(first, probe) and _satisfies(second, probe):
            return "compatible"
    return "unknown"


def _docker_runtime(value: Any) -> tuple[str, str] | None:
    if not isinstance(value, str) or "@" in value:
        return None
    image, separator, tag = value.rpartition(":")
    if not separator or "/" in tag or not image:
        return None
    image_name = image.rsplit("/", 1)[-1].lower()
    if image_name not in {"python", "node", "nodejs"}:
        return None
    normalized_subject = "Python" if image_name == "python" else "Node.js"
    version = tag.split("-", 1)[0]
    return normalized_subject, version


def _observation(fact: dict[str, Any], value: Any, comparison_value: Any | None = None) -> ConfigurationObservation | None:
    normalized = normalize_version(value if comparison_value is None else comparison_value)
    return ConfigurationObservation(
        original_value=value,
        normalized_value=normalized.as_dict() if normalized else None,
        evidence=[Evidence(**item) for item in fact.get("evidence", [])],
        scope=fact.get("scope"),
        source_type=fact.get("source_type"),
        environment=fact.get("environment"),
        confidence=fact.get("confidence", 0.0),
    )


def _eligible(fact: dict[str, Any]) -> bool:
    return fact.get("scope") not in WEAK_SCOPES and fact.get("source_type") != "test_matrix"


def _observation_role(fact: dict[str, Any]) -> str:
    if fact.get("type") in {"python.required_version", "node.required_version"}:
        return "requirement"
    if fact.get("type") == "cmake.minimum_version":
        return "build_requirement"
    return "runtime"


def _pair_conflict(subject: str, first: tuple[dict[str, Any], Any, Any], second: tuple[dict[str, Any], Any, Any]):
    first_fact, first_value, first_original = first
    second_fact, second_value, second_original = second
    first_role = _observation_role(first_fact)
    second_role = _observation_role(second_fact)
    if subject in {"Python", "Node.js"} and first_role == second_role:
        return None
    if subject == "CMake" and first_role == second_role == "runtime":
        return None
    first_observation = _observation(first_fact, first_original, first_value)
    second_observation = _observation(second_fact, second_original, second_value)
    if first_observation is None or second_observation is None:
        return None
    compatibility = compare_versions(first_value, second_value)
    if compatibility != "incompatible":
        return None
    scope_order = {"project": 0, "ci": 1, "runtime": 2}
    observations = sorted([first_observation, second_observation], key=lambda item: (
        scope_order.get(item.scope or "", 9), item.scope or "", item.source_type or "", str(item.original_value),
        item.evidence[0].file if item.evidence else "",
    ))
    evidence = sorted(
        {item.file: item for observation in observations for item in observation.evidence}.values(),
        key=lambda item: (item.file, item.line or 0, item.reason),
    )
    scopes = sorted({observation.scope for observation in observations if observation.scope})
    return ConfigurationConflict(
        subject=subject,
        status="incompatible",
        compatibility=compatibility,
        observations=observations,
        evidence=evidence,
        scopes=scopes,
        confidence=min(observation.confidence for observation in observations),
        reason="Version observations are incompatible",
    )


def detect_configuration_conflicts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: dict[str, list[tuple[dict[str, Any], Any, Any]]] = {subject: [] for subject in SUPPORTED_SUBJECTS}
    for fact in facts:
        if not _eligible(fact):
            continue
        fact_type = fact.get("type")
        subject = fact.get("subject")
        if fact_type == "python.required_version" and subject == "Python":
            observations["Python"].append((fact, fact.get("value"), fact.get("value")))
        elif fact_type == "node.required_version" and subject == "Node.js":
            observations["Node.js"].append((fact, fact.get("value"), fact.get("value")))
        elif fact_type in {"ci.python_version", "ci.node_version"} and not isinstance(fact.get("value"), list):
            observations[subject].append((fact, fact.get("value"), fact.get("value")))
        elif fact_type == "docker.base_image":
            values = fact.get("value") if isinstance(fact.get("value"), list) else [fact.get("value")]
            for value in values:
                docker_runtime = _docker_runtime(value)
                if docker_runtime:
                    docker_subject, version = docker_runtime
                    observations[docker_subject].append((fact, version, value))
        elif fact_type == "cmake.minimum_version" and subject == "CMake":
            observations["CMake"].append((fact, fact.get("value"), fact.get("value")))

    conflicts = []
    for subject, subject_observations in observations.items():
        for index, first in enumerate(subject_observations):
            for second in subject_observations[index + 1:]:
                conflict = _pair_conflict(subject, first, second)
                if conflict is not None:
                    conflicts.append(conflict)

    unique = {}
    for conflict in conflicts:
        payload = conflict.model_dump() if hasattr(conflict, "model_dump") else conflict.dict()
        key = (
            payload["subject"], payload["compatibility"],
            tuple((item["scope"], item["original_value"], item["evidence"][0]["file"] if item["evidence"] else "") for item in payload["observations"]),
        )
        unique[key] = payload
    return sorted(
        unique.values(),
        key=lambda item: (
            item["subject"], item["status"],
            tuple((observation["scope"] or "", str(observation["original_value"]), observation["evidence"][0]["file"] if observation["evidence"] else "") for observation in item["observations"]),
        ),
    )