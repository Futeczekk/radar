# Radar Core v0.7

## Status

COMPLETED

## Implementation Summary

Radar Core v0.7 adds deterministic reverse-dependency impact traversal on top of the completed v0.5 repository graph and v0.6 component graph.

The reusable impact engine provides:

* direct and transitive dependents for file or component targets
* hop distance and one deterministic evidence path per affected node
* relationship/component scope preservation for project, test, example, subproject, vendor, and generated dependents
* visited-node cycle protection and duplicate suppression
* clean `found: false` results for unknown targets without fabricated dependencies

The minimal API surface is `POST /impact` with `url` and exactly one of `target` or `component`. Existing `/scan` output and all previous response fields are unchanged. The endpoint rescans once to obtain the existing graphs, then traverses those graphs without rescanning source files during impact calculation.

No AI, risk scoring, Git history, ownership, runtime tracing, or semantic impact claims were added.

## Limitations

Impact means graph reachability only: it identifies nodes that depend on the selected target through known Radar relationships and does not claim that a change will break them. Results are limited by the v0.5 file graph and v0.6 component graph coverage, which intentionally omit unresolved external dependencies and ambiguous relationships. One shortest deterministic path is retained per affected node; the engine does not yet report alternative paths or rank impact severity.

## Verification

The complete backend regression suite passes:

* `69 passed in 0.19s`

Live validation used a writable temporary SQLite path because `/data` is not writable in the local environment:

* `GET /health` returned HTTP `200`
* `POST /scan` and `POST /impact` on `Futii10/radar-test` returned HTTP `200`; `backend/database.py` had one direct and two transitive dependents
* `POST /scan` and `POST /impact` on `expressjs/express` returned HTTP `200` for `lib/express.js`
* `POST /scan` and `POST /impact` on `madler/zlib` returned HTTP `200` for a resolved local header target

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED
Radar Core v0.3 — COMPLETED
Radar Core v0.4 — COMPLETED
Radar Core v0.5 — COMPLETED
Radar Core v0.6 — COMPLETED

v0.7 should answer:

> What can be affected by changing this part of the system?

---

# Goal

Radar should use the existing repository and component graphs to calculate deterministic dependency impact.

Example:

```text
main.py
→ api.py
→ service.py
→ database.py
```

If `database.py` changes, Radar should be able to return:

```text
directly dependent:
service.py

transitively dependent:
api.py
main.py
```

At component level:

```text
Data Layer
→ Service
→ API
→ Application
```

Radar must describe these as dependency reachability, not guaranteed breakage.

---

# Core Principle

Do not claim:

> this change will break X

unless there is deterministic evidence for such a conclusion.

Use language equivalent to:

```text
depends_on
potentially_affected
reachable_from
```

Impact in v0.7 means:

> Elements that depend directly or transitively on the selected node through known Radar relationships.

---

# Impact Model

Suggested output:

```json
{
  "impact": {
    "target": "backend/database.py",
    "direct_dependents": [
      "backend/service.py"
    ],
    "transitive_dependents": [
      "backend/api.py",
      "backend/main.py"
    ]
  }
}
```

Exact shape may follow existing architecture.

Each result should preserve evidence.

---

# Direction of Impact

If:

```text
A → B
```

means:

```text
A depends on B
```

then changing B potentially affects A.

Example:

```text
main.py → api.py
```

Changing `api.py` may affect:

```text
main.py
```

Do not reverse this logic.

---

# Direct Impact

Radar should identify first-order dependents.

Example:

```text
service.py → database.py
```

Query:

```text
impact(database.py)
```

returns:

```text
service.py
```

as direct impact.

---

# Transitive Impact

Radar should follow known graph edges backwards.

Example:

```text
main.py
→ api.py
→ service.py
→ database.py
```

For:

```text
database.py
```

return:

```text
direct:
service.py

transitive:
api.py
main.py
```

Preserve hop distance if practical.

Example:

```json
{
  "node": "backend/main.py",
  "distance": 3
}
```

---

# Component Impact

Reuse `component_graph` from v0.6.

If:

```text
API → Service
Service → Data
```

then changing `Data` may potentially affect:

```text
Service
API
```

Component impact should be derived from existing component relationships.

Do not create new guessed architecture.

---

# Evidence Paths

Impact results should explain why a node is considered affected.

Example:

```text
database.py
← service.py
← api.py
← main.py
```

Suggested structure:

```json
{
  "target": "backend/database.py",
  "affected": "backend/main.py",
  "distance": 3,
  "path": [
    "backend/main.py",
    "backend/api.py",
    "backend/service.py",
    "backend/database.py"
  ]
}
```

The path itself is evidence.

---

# Cycles

Graphs may contain cycles.

Example:

```text
A → B
B → C
C → A
```

Impact traversal must:

* terminate,
* avoid infinite recursion,
* avoid duplicate nodes.

Use visited-node protection.

---

# Scope Awareness

Preserve v0.3-v0.6 scopes.

Example:

```text
tests/test_api.py → api.py
```

Changing `api.py` may have a test dependent.

But Radar should distinguish:

```text
project impact
test impact
example impact
subproject impact
```

Do not mix all scopes into one undifferentiated list.

---

# Primary Impact

Primary project dependents should be easy to distinguish from secondary dependents.

Example:

```json
{
  "scope": "project"
}
```

versus:

```json
{
  "scope": "test"
}
```

This becomes important later for UI and prioritization.

---

# No Risk Scoring Yet

Do NOT produce:

```text
critical
high risk
medium risk
low risk
87% chance of breakage
```

v0.7 is graph reachability, not predictive risk scoring.

---

# No Semantic Claims

Do NOT infer:

```text
API change will break authentication
```

unless such a relationship exists explicitly.

v0.7 should say:

```text
authentication module depends on API
```

not:

```text
authentication will fail
```

---

# File-Level Query

Implement a clean internal API/function for queries such as:

```text
impact(file_path)
```

Example:

```text
backend/database.py
```

Expected:

```text
backend/service.py
backend/api.py
backend/main.py
```

---

# Component-Level Query

Support the same concept for component IDs.

Example:

```text
impact(component=data)
```

Expected:

```text
service
api
application
```

when supported by component graph edges.

---

# API Exposure

Expose impact in a minimal API form.

Possible approaches:

```text
POST /impact
```

or integrate it into `/scan`.

Prefer the smallest design consistent with the existing FastAPI architecture.

Example request:

```json
{
  "url": "https://github.com/Futii10/radar-test",
  "target": "backend/database.py"
}
```

Example response:

```json
{
  "target": "backend/database.py",
  "direct_dependents": [],
  "transitive_dependents": []
}
```

Exact schema may differ.

Do not break `/scan`.

---

# Controlled Repository Test

Use `Futii10/radar-test`.

Current chain:

```text
backend/main.py
→ backend/api.py
→ backend/service.py
→ backend/database.py
```

Expected impact for:

```text
backend/database.py
```

is:

```text
distance 1:
backend/service.py

distance 2:
backend/api.py

distance 3:
backend/main.py
```

Expected impact for:

```text
backend/service.py
```

is:

```text
backend/api.py
backend/main.py
```

Expected impact for:

```text
backend/main.py
```

is empty.

---

# Real Repository Validation

Validate on:

```text
expressjs/express
madler/zlib
```

Examples:

For Express, selecting an internal library file should return known reverse dependents where v0.5 relationships support them.

For zlib, selecting a commonly included header should show deterministic dependents.

Do not expect perfect whole-repo coverage.

---

# Component Validation

Use zlib's existing:

```text
contrib → root
```

component relationship.

If the semantics are:

```text
contrib depends_on root
```

then impact on `root` should include `contrib`.

Impact on `contrib` should not automatically include `root`.

This validates directionality.

---

# Deduplication

A dependent reachable through multiple paths should appear once.

Optionally retain multiple evidence paths later.

For v0.7, one deterministic path is enough.

---

# Missing Target

If the requested file/component does not exist:

Return a clean unknown/not-found result.

Do not fabricate impact.

---

# Isolated Nodes

A valid target may have no dependents.

Example:

```json
{
  "target": "backend/main.py",
  "direct_dependents": [],
  "transitive_dependents": []
}
```

This is a valid result.

---

# Performance

Use graph traversal over already-extracted Radar relationships.

Do not repeatedly rescan code during impact traversal if the graph is already available.

The impact engine should operate primarily on:

```text
repository_graph
component_graph
```

---

# Required Regression Tests

Add at least:

```text
direct file dependent
multi-hop file impact
component impact
correct reverse-edge direction
isolated node
unknown target
cycle handling
duplicate path deduplication
test-scope dependent preserved
example-scope dependent preserved
subproject scope preserved
component directionality
```

Preserve all previous tests.

---

# Do Not Implement

Do NOT implement in v0.7:

```text
AI predictions
risk scoring
change probability
Git history
ownership
Jira
Confluence
CODEOWNERS
runtime tracing
dynamic call graph
semantic code understanding
automatic remediation
```

---

# Definition of Done

v0.7 is complete when:

* all previous tests pass,
* file-level reverse dependency impact works,
* transitive traversal works,
* component-level impact works,
* graph direction is correct,
* cycles terminate safely,
* duplicates are removed,
* scope/context is preserved,
* paths/evidence are available,
* unknown targets do not produce guesses,
* API remains backward compatible,
* controlled `radar-test` impact works,
* Express validation works,
* zlib validation works,
* documentation matches implementation,
* v0.7 is marked `COMPLETED`.

---

# Expected Agent Workflow

1. Read this document.
2. Inspect v0.5 repository graph and v0.6 component graph.
3. Implement a small reusable impact traversal layer.
4. Traverse dependency edges in reverse.
5. Preserve hop distance and scope.
6. Add evidence paths.
7. Add file impact.
8. Add component impact.
9. Add minimal API exposure.
10. Add regression tests.
11. Run full backend suite.
12. Validate `radar-test`.
13. Validate Express.
14. Validate zlib.
15. Inspect real output for incorrect directionality.
16. Update this document with actual behavior and limitations.
17. Mark v0.7 `COMPLETED`.
18. Stop.

Do not start v0.8.

---

# v0.7 Summary

Radar Core v0.7 should move Radar from:

```text
I know how the system is connected.
```

to:

```text
I can trace what depends on a selected part of the system.
```

This is the first deterministic impact-analysis milestone.
