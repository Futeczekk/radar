import hashlib
import json

from app.services.impact import build_file_impact


class SnapshotMismatchError(ValueError):
    pass


def _snapshot_data(value):
    return value.get("snapshot", value) if isinstance(value, dict) else {}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _dedupe_records(records, key):
    unique = {}
    for record in records:
        unique[key(record)] = record
    return [unique[item] for item in sorted(unique)]


def _file_records(snapshot):
    records = {}
    for item in _snapshot_data(snapshot).get("files", []):
        if isinstance(item, str):
            path = item
            identity = hashlib.sha256(item.encode()).hexdigest()
            record = {"path": path, "sha": identity}
        else:
            path = item.get("path")
            if not path:
                continue
            record = dict(item)
            identity = item.get("sha") or item.get("hash") or hashlib.sha256(_canonical(item).encode()).hexdigest()
        records[path] = {"record": record, "identity": identity}
    return records


def _scope_for_path(path):
    normalized = path.replace("\\", "/").lower()
    if ".github/workflows/" in normalized:
        return "ci"
    segments = [segment for segment in normalized.split("/") if segment]
    scope_map = {
        "tests": "test", "test": "test", "fixtures": "test",
        "examples": "example", "example": "example", "demo": "example",
        "contrib": "subproject", "vendor": "vendor", "third_party": "vendor",
        "external": "vendor", "deps": "vendor", "build": "generated",
        "dist": "generated", "generated": "generated", "out": "generated",
        "target": "generated", "docs": "documentation",
    }
    return next((scope_map[item] for item in segments if item in scope_map), "project")


def _with_file_scope(record):
    result = dict(record)
    result.setdefault("scope", _scope_for_path(result["path"]))
    return result


def _diff_files(base, target):
    before = _file_records(base)
    after = _file_records(target)
    added = [_with_file_scope(after[path]["record"]) for path in sorted(set(after) - set(before))]
    removed = [_with_file_scope(before[path]["record"]) for path in sorted(set(before) - set(after))]
    changed = []
    for path in sorted(set(before) & set(after)):
        if before[path]["identity"] != after[path]["identity"]:
            changed.append({
                "path": path,
                "scope": _scope_for_path(path),
                "before": before[path]["record"],
                "after": after[path]["record"],
            })
    return {"added": added, "removed": removed, "changed": changed}


def _fact_key(fact):
    return (fact.get("type"), fact.get("subject"))


def _fact_semantics(fact):
    return {
        "type": fact.get("type"),
        "subject": fact.get("subject"),
        "value": fact.get("value"),
        "scope": fact.get("scope"),
        "source_type": fact.get("source_type"),
        "environment": fact.get("environment"),
        "confidence": fact.get("confidence"),
    }


def _facts_by_key(facts):
    result = {}
    for fact in facts:
        key = _fact_key(fact)
        current = result.get(key)
        if current is None or _canonical(fact) < _canonical(current):
            result[key] = fact
    return result


def _diff_facts(base, target):
    before = _facts_by_key(_snapshot_data(base).get("facts", []))
    after = _facts_by_key(_snapshot_data(target).get("facts", []))
    added = [after[key] for key in sorted(set(after) - set(before), key=_canonical)]
    removed = [before[key] for key in sorted(set(before) - set(after), key=_canonical)]
    changed = []
    for key in sorted(set(before) & set(after), key=_canonical):
        if _canonical(_fact_semantics(before[key])) != _canonical(_fact_semantics(after[key])):
            changed.append({"key": key, "before": before[key], "after": after[key]})
    return {"added": added, "removed": removed, "changed": changed}


def _relationship_key(item):
    return (item.get("source"), item.get("target"), item.get("type"))


def _diff_relationships(base_graph, target_graph):
    before = {_relationship_key(item): item for item in (base_graph or {}).get("relationships", [])}
    after = {_relationship_key(item): item for item in (target_graph or {}).get("relationships", [])}
    return {
        "added": [after[key] for key in sorted(set(after) - set(before), key=_canonical)],
        "removed": [before[key] for key in sorted(set(before) - set(after), key=_canonical)],
    }


def _component_key(item):
    return item.get("id")


def _component_signature(item):
    return _canonical({
        "type": item.get("type"), "scope": item.get("scope"),
        "files": sorted(item.get("files", [])),
    })


def _diff_components(base_graph, target_graph):
    before = {_component_key(item): item for item in (base_graph or {}).get("components", []) if _component_key(item)}
    after = {_component_key(item): item for item in (target_graph or {}).get("components", []) if _component_key(item)}
    added = [after[key] for key in sorted(set(after) - set(before))]
    removed = [before[key] for key in sorted(set(before) - set(after))]
    changed = []
    for key in sorted(set(before) & set(after)):
        if _component_signature(before[key]) != _component_signature(after[key]):
            changed.append({"id": key, "before": before[key], "after": after[key]})
    return {"added": added, "removed": removed, "changed": changed}


def _impact_changes(file_changes, base, target):
    impacts = []
    for item in file_changes["changed"]:
        result = build_file_impact(_snapshot_data(target).get("repository_graph", {}), item["path"])
        impacts.append({"file": item["path"], "change": "changed", "impact": result})
    for item in file_changes["removed"]:
        result = build_file_impact(_snapshot_data(base).get("repository_graph", {}), item["path"])
        impacts.append({"file": item["path"], "change": "removed", "impact": result})
    return impacts


def diff_snapshots(base, target):
    base_data = _snapshot_data(base)
    target_data = _snapshot_data(target)
    base_repository = base_data.get("repository")
    target_repository = target_data.get("repository")
    if base_repository and target_repository and base_repository != target_repository:
        raise SnapshotMismatchError("Snapshots belong to different repositories")

    files = _diff_files(base_data, target_data)
    facts = _diff_facts(base_data, target_data)
    relationships = _diff_relationships(
        base_data.get("repository_graph"), target_data.get("repository_graph")
    )
    components = _diff_components(
        base_data.get("component_graph"), target_data.get("component_graph")
    )
    component_relationships = _diff_relationships(
        base_data.get("component_graph"), target_data.get("component_graph")
    )
    return {
        "repository": target_repository or base_repository,
        "base": {"ref": base_data.get("ref"), "commit_sha": base_data.get("commit_sha")},
        "target": {"ref": target_data.get("ref"), "commit_sha": target_data.get("commit_sha")},
        "changes": {
            "files": files,
            "facts": facts,
            "relationships": relationships,
            "components": components,
            "component_relationships": component_relationships,
            "impact": _impact_changes(files, base_data, target_data),
        },
    }
