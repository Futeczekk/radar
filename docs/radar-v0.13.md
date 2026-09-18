We are starting Radar Core v0.13.

Do NOT implement code yet.

First inspect the repository as it exists after `v0.12.0`.

Read at minimum:

* `README.md`
* `docs/radar-v0.11.md`
* `docs/radar-v0.12.md`
* `docs/architecture.md`
* `docs/development.md`
* `docs/testing.md`
* `docs/ci.md`
* all ADRs under `docs/decisions/`
* repository identity normalization
* multi-repository map implementation
* repository relationship model
* snapshot/cache semantics
* v0.7 impact analysis
* v0.8 diff implementation
* v0.11 technical changes
* validation subsystem
* relevant tests
* git history through `v0.12.0`

Then create:

`docs/radar-v0.13.md`

# Radar Core v0.13 — Cross-Repository Impact Analysis

Primary question:

> If repository X changes, which known repositories may be affected, and what deterministic evidence connects them?

v0.12 introduced an explicit multi-repository technical map.

v0.13 should add deterministic impact analysis over that repository graph.

This is NOT risk scoring.

This is NOT change prediction.

This is NOT AI inference.

It is graph-based propagation over relationships Radar already knows and can prove.

## Product goal

Given a technical estate and a target repository, Radar should answer:

* whether the repository exists in the estate,
* which repositories directly depend on it,
* which repositories transitively depend on it,
* the hop distance,
* the deterministic relationship path,
* evidence supporting every hop,
* which repositories are NOT known to be affected.

Example:

```text
shared-sdk

direct dependents:
- service-a
- web-app

transitive dependents:
- service-b

paths:
service-a → shared-sdk

service-b → service-a → shared-sdk

web-app → shared-sdk
```

Radar must say:

> these repositories are known dependents

not:

> these repositories will definitely break

Use conservative language.

## Core philosophy

Preserve all Radar principles:

* evidence-first
* deterministic core before AI
* UNKNOWN over guessing
* precision over recall
* source-neutral core
* immutable snapshots
* stable identities
* deterministic ordering
* Fact + Evidence + Context + Confidence
* backward compatibility with v0.1-v0.12

## Reuse existing semantics

v0.13 should build on:

* v0.7 file/component impact traversal
* v0.12 repository relationships
* existing graph traversal concepts

Do NOT create a completely separate impact engine if existing graph traversal logic can be reused or generalized.

Prefer shared graph semantics where reasonable.

## Repository-level impact

Impact direction must be explicit.

If:

```text
A → B
```

means:

> A depends on B

then impact for target B should return:

```text
direct dependent: A
```

For:

```text
C → A → B
```

impact for B should return:

```text
A distance 1
C distance 2
```

Do not invert relationship direction accidentally.

## Output model

Design a source-neutral repository impact result.

Conceptually it should include:

* target repository identity
* target snapshot identity if relevant
* found/not found
* direct dependents
* transitive dependents
* distance
* relationship path
* evidence path
* source estate/map identity if introduced
* scope/context only if meaningful at repository level

Example conceptual result:

```json
{
  "target": "https://github.com/acme/shared",
  "found": true,
  "direct_dependents": [
    {
      "repository": "https://github.com/acme/api",
      "distance": 1,
      "path": [
        "https://github.com/acme/api",
        "https://github.com/acme/shared"
      ],
      "evidence": []
    }
  ],
  "transitive_dependents": []
}
```

Do not finalize the exact schema blindly; align it with current v0.7 and v0.12 models.

## Evidence paths

Every returned impact path must be explainable.

For:

```text
C → A → B
```

Radar must preserve evidence for:

```text
C → A
A → B
```

Do not flatten evidence in a way that loses which hop it belongs to.

The specification should decide whether evidence is represented:

* per path edge,
* as ordered evidence groups,
* or another deterministic structure.

The result must make the path auditable.

## Cycles

Repository graphs may contain cycles.

Example:

```text
A → B
B → C
C → A
```

Impact traversal must:

* terminate,
* never recurse forever,
* never duplicate semantic repository results,
* preserve shortest deterministic distance,
* produce deterministic paths,
* not list the target as its own dependent.

Define expected behavior explicitly.

## Multiple paths

A repository may depend on the target through multiple routes.

Example:

```text
D → B → A
D → C → A
```

Define deterministic behavior.

Prefer:

* one semantic dependent result,
* shortest path,
* deterministic tie-breaking,
* evidence for the selected path,

unless existing impact semantics strongly justify another approach.

Do not duplicate D merely because multiple paths exist.

## Direct vs transitive

Define clearly:

* distance 1 = direct
* distance >1 = transitive

A repository must not appear in both lists.

## Unknown target

If requested target repository is not present in the supplied estate:

Return an explicit not-found result.

Do not guess based on name similarity.

Do not auto-add a repository.

## Failed/unavailable repositories

Reuse v0.12 partial-failure semantics.

If some estate members failed to resolve:

* impact may still be computed over known successful nodes,
* the result must not imply completeness beyond known data,
* failed members must not create fabricated paths.

Consider whether the impact result should expose estate completeness/status.

Define this explicitly.

## Snapshot semantics

Impact must operate on one explicit technical estate state.

Do not mix:

```text
repo A @ old SHA
repo B @ new SHA
```

unless those exact states were explicitly supplied in the estate request.

Repository identity and repository snapshot identity remain distinct.

## API

Choose the smallest API change.

Prefer extending the existing multi-repository API model rather than introducing unnecessary endpoints.

Possible options:

### Option A

`POST /map/impact`

Request:

```json
{
  "repositories": [...],
  "target": "https://github.com/acme/shared"
}
```

### Option B

extend `/impact` with an explicit repository-level mode

Only choose this if it remains clean and backward compatible.

The specification must decide which design best matches current architecture.

Existing:

* `/scan`
* `/impact`
* `/diff`
* `/map`

must remain backward compatible.

## No estate persistence yet

Do not introduce a database-backed permanent organization/estate object unless current architecture already requires it.

The caller may continue to supply the explicit repository collection.

v0.13 is about impact semantics, not estate management.

## Controlled fixture

Define a deterministic controlled topology.

Use something like:

```text
repo-shared

repo-api    → repo-shared
repo-web    → repo-shared
repo-worker → repo-api
repo-other  isolated
```

Expected impact for `repo-shared`:

```text
direct:
- repo-api
- repo-web

transitive:
- repo-worker

isolated:
- repo-other
```

Expected evidence paths:

```text
repo-api → repo-shared
repo-web → repo-shared
repo-worker → repo-api → repo-shared
```

Also define a cycle case.

Do NOT create/push fixture repositories while writing the specification.

## Tests

Define strong tests for at least:

1. target with no dependents
2. one direct dependent
3. multiple direct dependents
4. transitive dependent
5. direct + transitive separation
6. correct hop distance
7. deterministic path
8. evidence preserved per relationship hop
9. unrelated repository excluded
10. unknown target
11. cycle protection
12. no target-as-own-dependent
13. duplicate relationship deduplication
14. multiple possible paths
15. deterministic shortest-path selection
16. collection ordering does not affect result
17. failed estate member does not invent impact
18. partial estate status remains visible
19. repository identity normalization
20. snapshot identity preserved
21. no name-based guessing
22. existing v0.7 file impact remains unchanged
23. existing `/map` remains unchanged
24. existing `/scan` remains unchanged
25. existing `/diff` remains unchanged
26. existing `/impact` compatibility remains unchanged

## Manual acceptance

After implementation, manually validate at least:

### Case 1 — controlled chain

```text
C → B → A
```

Impact(A):

```text
B direct distance=1
C transitive distance=2
```

### Case 2 — isolated repository

No impact result.

### Case 3 — cycle

Traversal terminates and output is deduplicated.

### Case 4 — removed relationship

If one snapshot contains:

```text
B → A
```

and a later snapshot does not:

impact results must differ accordingly.

No stale relationship may survive from cache.

### Case 5 — real repository map

Use existing v0.12 controlled fixture where possible.

If only A → B exists, impact(B) should include A as direct dependent.

Impact(A) should not include B.

## Performance

Impact traversal should operate over repository graph edges, not full file collections.

Target complexity should be approximately graph traversal complexity:

```text
O(V + E)
```

for a supplied estate.

Do not perform pairwise file comparisons during impact traversal.

Record basic metrics where useful:

* repository count
* relationship count
* visited repositories
* impact result count

Do not add performance scoring.

## Explicit non-goals

v0.13 must NOT implement:

* risk scores
* severity scores
* migration recommendations
* AI inference
* Ask Radar
* semantic repository matching
* fuzzy dependency matching
* API compatibility prediction
* breaking-change detection
* runtime traffic analysis
* Kubernetes/service discovery
* Jira
* Confluence
* Jenkins
* Slack/Teams
* ownership
* team graph
* business hierarchy
* persisted company graph
* estate diff
* migration dashboard
* v0.14 work

## Product boundary

v0.13 answers:

> Which known repositories depend on this repository, directly or transitively, based on deterministic evidence?

It does NOT answer:

> Which repositories will break?

and does NOT answer:

> How risky is this change?

Make this distinction explicit.

## Definition of Done

At minimum:

* repository-level impact model exists
* direct dependents work
* transitive dependents work
* hop distance works
* deterministic evidence path works
* cycles terminate safely
* duplicates are suppressed
* shortest deterministic path is selected
* target is not its own dependent
* unknown target is explicit
* partial estate semantics are preserved
* snapshot semantics remain correct
* stale relationships are not reused
* repository ordering does not change output
* no name-based inference
* source-neutral core preserved
* existing v0.1-v0.12 behavior remains compatible
* focused tests pass
* backend suite passes
* validation harness passes
* controlled acceptance passes
* real v0.12 fixture is manually validated
* existing 18-repository corpus remains compatible
* heavy repositories remain compatible
* `make check` passes
* `git diff --check` passes
* documentation updated
* no unrelated functionality added

Do not implement code.

Do not commit, push, tag, reset, rebase or modify git history.

At the end report:

1. files inspected
2. architecture understood
3. proposed repository-impact model
4. traversal semantics
5. relationship direction semantics
6. evidence-path representation
7. cycle handling
8. multiple-path handling
9. API design
10. partial failure semantics
11. snapshot/cache semantics
12. controlled fixture strategy
13. manual acceptance plan
14. performance characteristics
15. risks/ambiguities
16. confirmation that `docs/radar-v0.13.md` was created
