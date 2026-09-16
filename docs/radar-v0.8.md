# Radar Core v0.8

## Status

COMPLETED

## Implementation Summary

Radar Core v0.8 adds reusable deterministic repository snapshots and snapshot comparison on top of the v0.5 repository graph, v0.6 component graph, and v0.7 reverse-impact traversal.

Snapshots preserve repository identity, requested ref, resolved commit SHA, file/blob identity, facts, file relationships, components, component relationships, evidence, scope, and confidence. The diff layer reports added, removed, and content-changed files; added, removed, and value-changed facts; file relationship changes; component additions/removals/membership or type/scope changes; and component relationship changes. Results are stably ordered and deduplicated, and evidence ordering does not create false fact changes.

Changed files use v0.7 reverse impact on the target snapshot. Removed files use the base snapshot graph so previously known dependents remain explainable. The minimal backward-compatible `POST /diff` endpoint accepts `url`, `base_ref`, and `target_ref`; `/health`, `/scan`, and `/impact` remain available.

No AI, risk or severity scoring, Git author/history analytics, ownership, runtime tracing, or semantic breaking-change analysis was added.

## Limitations

The GitHub adapter is the first snapshot source and resolves refs through the GitHub commits API. It supports optional authenticated requests through `GITHUB_TOKEN` while preserving unauthenticated behavior when unset. Source failures distinguish invalid or missing refs/repositories, authentication failures, rate limits, connection failures, and other GitHub failures. Diff comparison itself is source-independent and accepts snapshot structures directly. File changes use tree blob SHAs when available; synthetic snapshots without content identity use their supplied record or deterministic fallback identity. There is no rename detection, AST diff, runtime dependency analysis, alternative-path enumeration, or semantic interpretation. Unauthenticated GitHub validation remains subject to API rate limits.

## Verification

The complete backend regression suite passes:

* `91 passed`

Additional checks:

* `git diff --check` passed
* `/health` returned HTTP `200`
* Controlled `Futii10/radar-test` diff `b5b0a2cb442e264bdbce469f174a5cb31d194099 -> f1021eb25d0f4cfbd0d3f8fc37caeaeab0f31b95` returned HTTP `200`; `.github/workflows/test.yml` preserved `scope: "ci"`, and `ci.python_version` was represented as one semantic changed fact with before/after values and metadata
* Controlled dependency-chain diff `f1021eb25d0f4cfbd0d3f8fc37caeaeab0f31b95 -> d893460cc40474cd605a75ae08c7ca83e722b5e6` reported five backend files and three dependency relationships
* Same-snapshot empty-diff behavior, invalid-ref handling, repository mismatch protection, impact direction, scope preservation, and deterministic ordering are covered by regression tests

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED
Radar Core v0.3 — COMPLETED
Radar Core v0.4 — COMPLETED
Radar Core v0.5 — COMPLETED
Radar Core v0.6 — COMPLETED
Radar Core v0.7 — COMPLETED

v0.8 should answer:

> What technically changed between two known states of a repository?

---

# Goal

Radar should compare two deterministic repository snapshots and report meaningful structural changes.

Example:

```text
Snapshot A
commit: abc123

Snapshot B
commit: def456
```

Radar should be able to report:

```text
FILES

+ backend/cache.py
~ backend/service.py
- backend/legacy.py

RELATIONSHIPS

+ backend/api.py → backend/cache.py
- backend/api.py → backend/legacy.py

COMPONENTS

~ backend

POTENTIAL IMPACT

backend/service.py changed

known dependents:
backend/api.py
backend/main.py
```

Radar must distinguish:

```text
what changed
```

from:

```text
what may be affected according to known dependency paths
```

Do not claim runtime breakage.

---

# Core Principle

v0.8 is deterministic change intelligence.

Conceptually:

```text
Repository
   ↓
Snapshot A
   ↓
Repository changes
   ↓
Snapshot B
   ↓
Deterministic Diff
   ↓
Known Impact
```

Radar should compare known technical state.

It should not guess why a change happened.

---

# Snapshot Model

Introduce a reusable repository snapshot representation.

A snapshot should contain enough information to compare two scans without having to reinterpret their outputs.

Suggested conceptual structure:

```json
{
  "repository": "...",
  "ref": "...",
  "commit_sha": "...",
  "files": [],
  "facts": [],
  "repository_graph": {},
  "component_graph": {}
}
```

Exact schema should follow the existing Radar architecture.

A snapshot should preserve:

* repository identity,
* requested ref when available,
* resolved commit SHA when available,
* files,
* facts,
* file relationships,
* components,
* component relationships,
* evidence,
* scope,
* confidence.

Do not duplicate unnecessary data if existing scan structures can be reused cleanly.

---

# Snapshot Identity

Snapshots must have stable identity.

Prefer:

```text
repository
+
commit SHA
```

when available.

Example:

```json
{
  "repository": "https://github.com/Futii10/radar-test",
  "ref": "main",
  "commit_sha": "abc123..."
}
```

Do not assume branch names identify immutable states.

A branch may move.

Commit SHA should be preferred as the immutable state identifier.

---

# File Changes

Compare files between snapshots.

Supported categories:

```text
added
removed
changed
unchanged
```

The API does not need to return unchanged files unless useful internally.

Example:

```json
{
  "files": {
    "added": [
      "backend/cache.py"
    ],
    "removed": [
      "backend/legacy.py"
    ],
    "changed": [
      "backend/service.py"
    ]
  }
}
```

---

# Detecting Changed Files

Do not mark a file changed only because its metadata ordering changed.

Use deterministic file content identity.

Prefer:

```text
content hash
```

or an equivalent stable representation.

If the source adapter exposes object/blob SHA reliably, it may be reused.

The comparison must not depend on Python object identity or response ordering.

---

# Fact Changes

Compare Radar facts.

Detect:

```text
added facts
removed facts
changed facts
```

Example:

Snapshot A:

```text
python.requires >=3.11
```

Snapshot B:

```text
python.requires >=3.12
```

Radar should identify this as a meaningful configuration change.

Prefer normalized deterministic fact identity.

The implementation should avoid false diffs caused by:

* ordering,
* duplicate evidence,
* serialization differences,
* irrelevant internal IDs.

Preserve:

```text
scope
source_type
environment
confidence
evidence
```

where applicable.

---

# File Relationship Changes

Reuse the v0.5 repository graph.

Compare known file relationships.

Example:

Snapshot A:

```text
api.py → legacy.py
```

Snapshot B:

```text
api.py → cache.py
```

Expected:

```text
removed:
api.py → legacy.py

added:
api.py → cache.py
```

Relationship identity should include at least:

```text
source
target
relationship type
```

Do not classify unchanged edges as changed because evidence formatting differs.

---

# Component Changes

Reuse v0.6 component detection.

Compare components between snapshots.

Detect:

```text
added components
removed components
changed components
```

A component may be considered changed when its deterministic structure changes, for example:

* file membership changes,
* component type changes,
* scope changes,
* component relationships change.

Avoid marking every parent component changed for irrelevant metadata changes.

---

# Component Relationship Changes

Compare component graph edges.

Example:

Snapshot A:

```text
frontend → api
```

Snapshot B:

```text
frontend → gateway
gateway → api
```

Radar should report:

```text
removed:
frontend → api

added:
frontend → gateway
gateway → api
```

Direction must preserve existing Radar semantics.

---

# Change Impact

Reuse v0.7 impact traversal.

For changed files, Radar may attach known dependents.

Example:

```text
backend/database.py changed
```

Known graph:

```text
main.py
→ api.py
→ service.py
→ database.py
```

Expected impact:

```text
database.py

direct dependent:
service.py

transitive:
api.py
main.py
```

The wording must remain conservative.

Correct:

```text
known dependents
potentially affected
reachable dependents
```

Incorrect:

```text
will break
will fail
high-risk change
```

---

# Which Graph Should Impact Use?

Impact should be based on the most appropriate known graph state.

Prefer the current/new snapshot when answering:

> What may be affected after this change?

However, removed nodes and removed relationships may require old-snapshot context.

Therefore v0.8 should preserve enough information to explain changes against both states.

Do not invent edges that exist in neither snapshot.

---

# Removed File Impact

If a removed file had known dependents in Snapshot A, Radar should be able to expose those old known dependents.

Example:

Snapshot A:

```text
api.py → legacy.py
```

Snapshot B:

```text
legacy.py removed
```

Radar may report:

```text
legacy.py removed

previously known dependent:
api.py
```

Clearly distinguish this from current graph state.

---

# Added File Impact

A newly added isolated file may have no dependents.

This is valid.

Do not fabricate impact just because the file was added.

---

# Changed File Impact

For modified files that still exist in Snapshot B, use current known reverse dependency traversal.

Example output:

```json
{
  "file": "backend/service.py",
  "change": "changed",
  "impact": {
    "direct_dependents": [],
    "transitive_dependents": []
  }
}
```

Exact API structure may differ.

---

# Evidence

Every structural change should remain explainable.

For added relationship:

```text
api.py → cache.py
```

include evidence such as:

```json
{
  "file": "backend/api.py",
  "line": 7,
  "snippet": "from backend import cache",
  "reason": "Python import resolves to backend/cache.py"
}
```

For removed relationships, preserve evidence from the old snapshot where available.

---

# Determinism

Given identical Snapshot A and Snapshot B:

```text
diff(A, B)
```

must always return an empty change set.

Ordering of input collections must not create changes.

Results should have deterministic ordering.

Prefer stable sorting where needed.

---

# Duplicate Protection

Facts, relationships, components, and change records must not be duplicated.

If multiple identical evidence entries support the same structural change:

* keep one structural change,
* evidence may be deduplicated separately.

---

# Scope Preservation

v0.8 must retain existing scope information.

Examples:

```text
project
ci
test
example
vendor
subproject
generated
```

A change in:

```text
tests/
```

must not silently become indistinguishable from a project-production change.

Example:

```json
{
  "file": "tests/test_api.py",
  "change": "changed",
  "scope": "test"
}
```

---

# Confidence Preservation

If a changed entity/fact/component already carries confidence, preserve it where relevant.

Do not introduce new confidence scoring for change severity.

---

# No Change Severity

Do NOT introduce:

```text
critical
high
medium
low
risk score
blast radius score
change score
```

v0.8 reports known changes and known dependency impact.

It does not rate them.

---

# No Semantic Change Interpretation

Do NOT claim:

```text
authentication behavior changed
database migration is unsafe
API compatibility is broken
```

unless those facts are deterministically supported.

v0.8 does not perform semantic code review.

---

# API

Expose a minimal backward-compatible API.

Possible endpoint:

```text
POST /diff
```

Suggested request:

```json
{
  "url": "https://github.com/Futii10/radar-test",
  "base_ref": "abc123",
  "target_ref": "def456"
}
```

Possible response:

```json
{
  "repository": "...",
  "base": {
    "ref": "abc123",
    "commit_sha": "..."
  },
  "target": {
    "ref": "def456",
    "commit_sha": "..."
  },
  "changes": {
    "files": {
      "added": [],
      "removed": [],
      "changed": []
    },
    "facts": {
      "added": [],
      "removed": [],
      "changed": []
    },
    "relationships": {
      "added": [],
      "removed": []
    },
    "components": {
      "added": [],
      "removed": [],
      "changed": []
    },
    "component_relationships": {
      "added": [],
      "removed": []
    }
  }
}
```

Exact schema may differ if a cleaner design fits the existing codebase.

Do not break:

```text
/health
/scan
/impact
```

---

# Source Layer

Do not tightly couple the diff engine to GitHub.

The GitHub source may initially provide repository states, refs, and commit SHAs, but:

```text
Snapshot Diff
```

should operate on Radar snapshot structures.

Conceptually:

```text
GitHub Source
     ↓
Snapshot A
Snapshot B
     ↓
Radar Diff Engine
```

not:

```text
GitHub-specific diff logic everywhere
```

This is important for future:

```text
GitLab
Bitbucket
local repositories
other sources
```

---

# Snapshot Comparison Layer

Prefer a dedicated reusable comparison layer.

Conceptually:

```text
SnapshotDiffer
```

or equivalent.

It should compare already-extracted deterministic Radar state.

Avoid mixing:

```text
source fetching
parsing
graph extraction
diff calculation
API formatting
```

inside one large function.

---

# Controlled Validation Repository

Use:

```text
Futii10/radar-test
```

Create or identify two deterministic refs/commits with controlled changes.

The controlled test should include at least:

```text
one added file
one removed file
one modified file
one added relationship
one removed relationship
one fact/configuration change
one change with known v0.7 dependents
```

Example controlled scenario:

Snapshot A:

```text
main.py
→ api.py
→ service.py
→ database.py
```

Snapshot B:

```text
main.py
→ api.py
→ service.py
→ database.py
             ↓
           cache.py
```

or another clear deterministic fixture.

Do not depend only on live moving `main`.

Prefer immutable test commits/tags.

---

# Express Validation

Validate two immutable Express repository states if practical.

Confirm:

* snapshot identity is correct,
* files are classified correctly,
* relationship changes are deterministic,
* no mass false-positive diff appears because of ordering,
* unchanged component structure is not reported as changed without reason.

Do not require every historical code change to be understood semantically.

---

# zlib Validation

Validate two immutable zlib states if practical.

Check especially:

* C/C++ file additions/removals,
* quoted local include relationship changes,
* component membership changes,
* `contrib` scope preservation,
* no false project/subproject mixing.

---

# Same Snapshot Test

Required:

```text
diff(snapshot, snapshot)
```

must return no changes.

This should be tested explicitly.

---

# Ref Resolution

If a requested ref cannot be resolved:

Return a clean failure.

Do not silently fall back to another branch or HEAD.

Example:

```json
{
  "found": false,
  "reason": "ref_not_found"
}
```

Follow existing API error conventions where possible.

---

# Repository Mismatch

Do not compare snapshots from unrelated repositories as if they were versions of the same repository.

If Snapshot A and Snapshot B belong to different repositories:

return a clean mismatch result/error.

---

# Empty Repository / Sparse Snapshot

Handle empty or minimal repositories safely.

Do not assume:

```text
facts exist
components exist
relationships exist
```

An empty collection is valid.

---

# Required Regression Tests

Add tests covering at least:

```text
identical snapshots produce empty diff
added file
removed file
modified file
added fact
removed fact
changed fact
added file relationship
removed file relationship
added component
removed component
changed component membership
added component relationship
removed component relationship
scope preservation
confidence preservation where relevant
deterministic ordering
duplicate suppression
removed-file old-graph impact
changed-file current impact
unknown ref
repository mismatch
```

Preserve all previous tests.

---

# Manual Acceptance

Before marking v0.8 complete:

1. Run full backend test suite.
2. Compare controlled immutable states of `radar-test`.
3. Inspect raw `/diff` output manually.
4. Verify no false changes caused by ordering.
5. Verify added/removed relationship direction.
6. Verify impact direction using v0.7.
7. Validate one Express comparison.
8. Validate one zlib comparison.
9. Run `git diff --check`.
10. Document actual limitations.

Do not treat green tests alone as sufficient acceptance.

---

# Known Limitation Policy

Document limitations explicitly.

Possible acceptable v0.8 limitations:

```text
only languages already supported by repository_graph
no semantic AST diff
no rename detection
no Git author/history analysis
no runtime dependency changes
no API compatibility analysis
no risk prediction
```

Do not hide missing coverage.

---

# Do Not Implement

Do NOT implement in v0.8:

```text
AI explanations
risk scoring
severity scoring
Git author analytics
ownership
CODEOWNERS
Jira
Confluence
Slack
Teams
Jenkins integration
runtime tracing
semantic breaking-change detection
automatic remediation
change recommendations
v0.9 work
```

---

# Definition of Done

Radar Core v0.8 is complete when:

* all previous tests pass,
* repository snapshots have stable identity,
* immutable commit SHA is preserved where available,
* two snapshots can be compared,
* added/removed/changed files are detected,
* fact changes are detected deterministically,
* file relationship changes are detected,
* component changes are detected,
* component relationship changes are detected,
* scope is preserved,
* confidence/evidence are preserved where applicable,
* identical snapshots produce an empty diff,
* ordering does not create false changes,
* repository mismatch is handled safely,
* invalid refs do not silently fall back,
* v0.7 impact is reused for changed/removed nodes,
* controlled `radar-test` comparison is manually validated,
* Express comparison is manually validated,
* zlib comparison is manually validated,
* `/health`, `/scan`, and `/impact` remain backward compatible,
* documentation describes actual implementation and limitations,
* `docs/radar-v0.8.md` is updated,
* status is changed to `COMPLETED`.

---

# Expected Agent Workflow

1. Read `docs/radar-v0.8.md`.
2. Inspect current source abstraction and `/scan`.
3. Inspect v0.5 repository graph.
4. Inspect v0.6 component graph.
5. Inspect v0.7 impact traversal.
6. Design a reusable repository snapshot model.
7. Preserve repository/ref/commit identity.
8. Implement deterministic snapshot comparison.
9. Implement file diff.
10. Implement fact diff.
11. Implement file relationship diff.
12. Implement component diff.
13. Implement component relationship diff.
14. Reuse v0.7 impact for changed/removed nodes where appropriate.
15. Add minimal backward-compatible `/diff` API.
16. Add regression tests.
17. Run the full backend test suite.
18. Validate controlled immutable `radar-test` states.
19. Validate Express.
20. Validate zlib.
21. Inspect output manually for false positives.
22. Run `git diff --check`.
23. Update this document with actual behavior, test count, manual validation, and limitations.
24. Mark v0.8 `COMPLETED`.
25. Stop.

Do not start v0.9.

---

# v0.8 Summary

Radar Core v0.7 answers:

```text
What depends on this?
```

Radar Core v0.8 should add:

```text
What changed between these two states?
```

and combine both capabilities into:

```text
What changed,
where did it change,
and which known parts of the system depend on it?
```

This is the first deterministic repository change-intelligence milestone.
