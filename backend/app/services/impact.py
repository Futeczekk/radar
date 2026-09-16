from collections import deque


def _reverse_adjacency(graph):
    reverse = {}
    for relationship in (graph or {}).get("relationships", []):
        source = relationship.get("source")
        target = relationship.get("target")
        if not source or not target:
            continue
        reverse.setdefault(target, []).append(relationship)
    for relationships in reverse.values():
        relationships.sort(key=lambda item: (item.get("source", ""), item.get("type", "")))
    return reverse


def _impact(graph, target, node_scopes=None):
    nodes = {node.get("id") for node in (graph or {}).get("nodes", []) if node.get("id")}
    if target not in nodes:
        return {"target": target, "found": False, "direct_dependents": [], "transitive_dependents": []}

    reverse = _reverse_adjacency(graph)
    queue = deque([(target, 0, [target], None)])
    visited = {target}
    direct_dependents = []
    transitive_dependents = []

    while queue:
        current, distance, path_to_target, inherited_scope = queue.popleft()
        for relationship in reverse.get(current, []):
            dependent = relationship["source"]
            if dependent in visited:
                continue
            visited.add(dependent)
            next_distance = distance + 1
            next_path = [dependent] + path_to_target
            scope = relationship.get("scope") or inherited_scope or (node_scopes or {}).get(dependent, "project")
            result = {
                "node": dependent,
                "distance": next_distance,
                "scope": scope,
                "path": next_path,
                "evidence": relationship.get("evidence", []),
            }
            if next_distance == 1:
                direct_dependents.append(result)
            else:
                transitive_dependents.append(result)
            queue.append((dependent, next_distance, next_path, scope))

    return {
        "target": target,
        "found": True,
        "direct_dependents": direct_dependents,
        "transitive_dependents": transitive_dependents,
    }


def build_file_impact(repository_graph, target):
    node_scopes = {
        relationship.get("source"): relationship.get("scope", "project")
        for relationship in (repository_graph or {}).get("relationships", [])
        if relationship.get("source")
    }
    return _impact(repository_graph, target, node_scopes)


def build_component_impact(component_graph, target):
    components = (component_graph or {}).get("components", [])
    nodes = [{"id": component.get("id")} for component in components if component.get("id")]
    graph = {
        "nodes": nodes,
        "relationships": (component_graph or {}).get("relationships", []),
    }
    node_scopes = {
        component.get("id"): component.get("scope", "project")
        for component in components
        if component.get("id")
    }
    return _impact(graph, target, node_scopes)
