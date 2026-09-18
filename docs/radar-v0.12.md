# Radar v0.12 — Multi-Repository Technical Map

Status: Draft for implementation
Baseline: Radar v0.11.0
Baseline commit/tag: `483286f`

---

# 1. Context

Radar v0.11 understands one repository at a time.

The current system can:

* scan repositories,
* build deterministic facts,
* preserve evidence and context,
* identify repository components,
* model dependencies,
* perform impact analysis,
* compare repository snapshots,
* detect configuration conflicts,
* detect technically meaningful changes,
* reuse existing repository analysis where supported,
* prefer `UNKNOWN` over unsupported inference.

v0.12 extends this model from a single repository to an explicitly supplied collection of repositories.

The goal is not to build a company-wide graph.

The goal is to allow Radar to answer:

> What repositories are present in this explicitly supplied technical area, what immutable snapshots were analyzed, and which evidence-backed technical relationships exist between them?

Radar must remain conservative.

A missing relationship is preferable to a false relationship.

---

# 2. Problem statement

The current Radar data model is repository-centric.

This works for:

* repository maps,
* component dependencies,
* impact analysis,
* snapshot diffs,
* configuration conflicts,
* technical change intelligence.

However, real systems are often split across multiple repositories.

Examples include:

* service + shared library,
* frontend + backend,
* application + infrastructure,
* client + protocol definitions,
* library + consumer,
* multiple services in one product area.

Radar currently has no first-class concept representing several repositories as one technical analysis boundary.

v0.12 introduces this capability.

The new layer must not weaken Radar's existing guarantees.

In particular:

* repositories must be explicitly supplied,
* snapshots must be immutable,
* cross-repository relationships must be deterministic,
* every confirmed relationship must have evidence,
* repository names alone are never sufficient evidence,
* ambiguity must produce unresolved/UNKNOWN state,
* failures must be explicit,
* collection order must not affect the result.

---

# 3. Goal

Radar v0.12 introduces a:

# Multi-Repository Technical Map

A technical map represents an explicitly supplied set of repository snapshots together with deterministic technical relationships between them.

The core transition is:

Before:

> Radar understands one repository snapshot.

After:

> Radar understands a defined collection of repository snapshots as one technical area.

---

# 4. Goals

v0.12 MUST support:

1. explicit repository collections,
2. repository identity separated from snapshot identity,
3. pinned immutable snapshots,
4. source-neutral repository identities,
5. deterministic cross-repository relationship resolution,
6. evidence attached to every confirmed relationship,
7. repository-level outgoing dependencies,
8. repository-level incoming dependents,
9. unresolved/UNKNOWN relationship states,
10. snapshot-level cache reuse,
11. repository-level partial failure,
12. deterministic map serialization,
13. request-order independence,
14. backward compatibility with current single-repository APIs.

---

# 5. Non-goals

v0.12 does NOT implement:

* AI,
* Ask Radar,
* natural-language repository queries,
* Jira,
* Confluence,
* Jenkins,
* CI pipeline discovery,
* ownership,
* teams,
* developers,
* organization charts,
* full company graphs,
* automatic organization crawling,
* arbitrary repository discovery,
* fuzzy repository matching,
* fuzzy package matching,
* semantic similarity,
* name similarity inference,
* risk scoring,
* technical risk ranking,
* migration dashboards,
* recommendations,
* deployment discovery,
* Kubernetes topology,
* observability integrations,
* runtime call graphs,
* service ownership inference,
* v0.13 features.

The implementation MUST NOT add speculative architecture solely to support these future areas.

---

# 6. Core design principle

A cross-repository relationship exists only when Radar can prove it from deterministic evidence.

The system MUST follow:

> evidence → deterministic resolution → relationship

Never:

> similar name → likely repository → relationship

A zero-edge map is valid.

Radar does not need to find relationships merely because multiple repositories were supplied.

Precision is more important than edge count.

---

# 7. Terminology

## Repository

A logical source repository independent of a specific revision.

Example conceptually:

```text
github.com/example/api
```

The exact internal representation is source-neutral.

---

## Repository identity

The stable normalized identity of a repository.

It answers:

> Which repository is this?

It MUST NOT include the currently scanned commit.

Repository identity is used for:

* deduplication,
* target resolution,
* collection membership,
* relationship addressing.

---

## Requested ref

The ref supplied by the caller.

Examples:

```text
main
v2.3.0
feature/foo
1a2b3c...
```

Requested refs may be mutable.

They are input metadata only.

They MUST NOT define final snapshot identity unless already immutable and verified.

---

## Resolved revision

The immutable revision obtained from the source adapter.

For Git-backed repositories this is the resolved commit SHA.

Example:

```text
483286f0...
```

---

## Snapshot identity

The identity of one immutable repository state.

Conceptually:

```text
(repository_identity, resolved_revision)
```

It answers:

> Which exact repository state is this?

---

## Repository snapshot

A repository identity together with one immutable resolved revision and the existing Radar scan result associated with it.

---

## Repository collection

An explicitly provided set of repository requests forming one analysis boundary.

Radar MUST NOT silently add repositories outside this collection.

---

## Technical map

The normalized result of analyzing the repository collection.

It contains:

* repository entries,
* immutable snapshots,
* statuses,
* confirmed cross-repository relationships,
* unresolved references,
* outgoing dependencies,
* incoming dependents,
* completeness information.

---

## Cross-repository relationship

A directional technical relationship between two repositories in the current collection.

Example:

```text
A -> B
```

means repository A contains deterministic evidence resolving to repository B.

---

## Relationship evidence

The provenance showing why Radar created a relationship.

Every confirmed edge MUST contain evidence.

---

## Unresolved reference

Evidence exists that appears to reference another repository, but Radar cannot uniquely resolve it to a repository snapshot/member of the supplied collection.

No confirmed edge is emitted.

---

# 8. Required invariants

The following are hard invariants for v0.12.

## I1. Deterministic result

Same:

* repository collection,
* resolved immutable snapshots,
* Radar version,
* analysis rules

must produce the same semantic technical map.

---

## I2. Input order independence

These requests:

```text
[A, B, C]
```

and:

```text
[C, A, B]
```

must produce the same semantic result.

Serialized ordering must be normalized.

---

## I3. Immutable snapshot identity

Every successfully analyzed repository entry must identify its immutable resolved snapshot.

---

## I4. Relationship evidence

Every confirmed cross-repository relationship must contain at least one evidence record.

An evidence-free confirmed edge is invalid.

---

## I5. No name-based guessing

Repository basenames, package names, directory names, component names or textual similarity MUST NOT independently create relationships.

---

## I6. No arbitrary ambiguity resolution

When evidence maps to more than one possible target, Radar MUST NOT arbitrarily choose one.

Result:

```text
UNRESOLVED / UNKNOWN
```

---

## I7. Explicit failure

A requested repository that fails MUST remain visible in the map response.

It must not disappear silently.

---

## I8. Partial availability

One failed repository must not invalidate successful repository snapshots when a meaningful partial map can still be returned.

---

## I9. Snapshot-based cache identity

Snapshot cache reuse is keyed by immutable snapshot identity rather than map/collection identity.

---

## I10. Semantic edge deduplication

Multiple evidence records supporting the same relationship must result in one semantic edge with multiple evidence entries.

---

## I11. Dependency/dependent consistency

For confirmed edge:

```text
A -> B
```

A must expose B as an outgoing relationship and B must expose A as an incoming dependent.

Both views derive from the same normalized edge set.

---

## I12. No scan mutation

Building a technical map must not mutate the underlying single-repository scan results.

---

## I13. Backward compatibility

Existing single-repository behavior remains valid.

At minimum:

* `/scan`
* `/impact`
* `/diff`

must keep their existing semantics.

---

# 9. Repository identity

Repository identity and snapshot identity must remain separate concepts.

## 9.1 Requirements

Repository identity MUST be:

* deterministic,
* canonical,
* source-neutral at the domain layer,
* stable across different commits,
* independent of requested ref.

Repository identity MUST NOT be based only on:

* repository basename,
* local checkout directory,
* component name,
* package name.

---

# 10. Source-neutral repository reference

The core model SHOULD represent repository identity using a structure that does not require GitHub-specific semantics.

Conceptually:

```json
{
  "source": "git",
  "canonical": "https://example.com/org/repository.git"
}
```

or an equivalent normalized representation fitting the current architecture.

GitHub-specific details such as:

```text
owner
repo
github repository id
```

may be retained as source metadata, but they must not become the core domain abstraction.

---

# 11. Repository normalization

Source adapters are responsible for canonicalizing source-specific repository inputs.

For equivalent inputs such as:

```text
https://github.com/org/repo
https://github.com/org/repo.git
git@github.com:org/repo.git
```

the source layer SHOULD resolve them to one canonical repository identity when existing architecture permits this safely.

Normalization must be deterministic.

No normalization rule may use fuzzy similarity.

---

# 12. Snapshot identity

Snapshot identity represents one immutable state.

Conceptually:

```text
snapshot_id = repository_identity + resolved_revision
```

For Git repositories:

```text
resolved_revision = full commit SHA
```

Branch names or tags are not sufficient snapshot identity by themselves.

---

# 13. Requested ref versus resolved revision

Radar must preserve the distinction between:

```text
requested_ref
```

and:

```text
resolved_revision
```

Example:

```json
{
  "requested_ref": "main",
  "resolved_revision": "483286f..."
}
```

The map operates on:

```text
resolved_revision
```

not the mutable ref.

---

# 14. Snapshot pinning lifecycle

The expected lifecycle is:

```text
repository request
        ↓
source adapter
        ↓
canonical repository identity
        ↓
requested ref resolution
        ↓
immutable revision
        ↓
snapshot identity
        ↓
cache lookup
        ↓
scan if needed
        ↓
repository analysis
        ↓
multi-repository relationship resolution
```

Once the immutable revision has been resolved, all downstream v0.12 work must operate against that pinned snapshot.

---

# 15. Explicit collection model

The repository collection is defined entirely by the request.

Radar MUST NOT:

* crawl a GitHub organization,
* query for similarly named repositories,
* recursively scan repository references,
* automatically include dependency repositories,
* silently expand the collection.

The collection is a hard analysis boundary.

---

# 16. Proposed API

v0.12 introduces:

```http
POST /map
```

This endpoint builds a multi-repository technical map.

Existing endpoints remain unchanged.

---

# 17. Proposed request contract

Conceptual request:

```json
{
  "repositories": [
    {
      "url": "https://github.com/example/service-a",
      "ref": "main"
    },
    {
      "url": "https://github.com/example/library-b",
      "ref": "v2.1.0"
    }
  ]
}
```

The exact field naming should reuse current source/scan request models wherever practical.

Do not introduce a second incompatible repository request representation without reason.

---

# 18. Request validation

At request level:

* `repositories` must exist,
* collection must not be empty,
* repository entries must follow supported source input rules.

Individual repository resolution/scanning failure does not automatically imply HTTP-level failure.

Invalid overall request shape remains an API validation failure.

---

# 19. Duplicate repository inputs

Duplicate input is normalized after repository and snapshot resolution where possible.

## Same repository + same immutable snapshot

Example:

```text
repo A @ SHA1
repo A @ SHA1
```

Expected:

* one semantic repository snapshot in the map,
* deterministic deduplication,
* no duplicate scan,
* no duplicate relationships.

Input duplication MAY be represented as request metadata if existing architecture makes this useful, but must not create duplicated semantic nodes.

---

## Same repository + different immutable snapshots

A single technical map SHOULD NOT treat two snapshots of the same repository as two independent repository nodes unless the approved implementation requires explicit historical comparison.

For v0.12 the preferred behavior is:

> one repository identity may appear at most once in one map request.

If duplicate entries for the same repository resolve to different immutable snapshots, return a deterministic repository-level/request-level conflict rather than treating them as separate technical repositories.

Reason:

A technical map represents one technical area at one chosen state per repository.

Historical comparison already belongs to snapshot/diff semantics.

Example failure:

```text
DUPLICATE_REPOSITORY_CONFLICT
```

with both resolved revisions available in structured diagnostic metadata where possible.

This avoids ambiguous relationships and dependent calculations.

---

# 20. Collection identity

v0.12 does not require a globally persistent collection entity.

A technical map can be derived from normalized repository snapshot identities.

If an identifier is useful for output/debugging, it may be calculated deterministically from the normalized ordered snapshot identities.

However:

* map identity must not become the snapshot cache key,
* maps need not be persisted as first-class objects,
* no collection database is required for v0.12.

---

# 21. Repository status

Every requested repository must produce an observable status.

Suggested states:

```text
SUCCESS
FAILED
```

Optionally:

```text
DUPLICATE
CONFLICT
```

if useful internally.

The external response should remain minimal.

A success contains:

* repository identity,
* requested ref,
* resolved revision,
* snapshot identity,
* analysis availability.

A failure contains:

* repository request identity where known,
* requested ref where known,
* structured failure code,
* concise message.

---

# 22. Map completeness

The technical map must expose whether all requested repositories were successfully available.

Suggested result:

```text
COMPLETE
PARTIAL
```

A map is `COMPLETE` when all unique requested repository entries were successfully resolved and analyzed.

A map is `PARTIAL` when at least one requested repository failed but successful repository snapshots are still available.

A request may fail entirely when no usable map can reasonably be constructed.

Examples:

* request validation failure,
* no repositories supplied,
* all repositories fail and current API conventions prefer a request failure,
* internal invariant violation.

The implementation should follow current Radar API error conventions.

---

# 23. Cross-repository relationship model

A relationship is directional.

Core representation conceptually:

```json
{
  "source_repository": "...",
  "target_repository": "...",
  "type": "repository_dependency",
  "evidence": []
}
```

The final exact model should align with existing Radar naming conventions.

---

# 24. Relationship creation rule

A confirmed relationship may only be created when:

1. source snapshot contains recognized deterministic evidence,
2. evidence yields a canonical repository reference,
3. reference resolution is exact,
4. exactly one repository in the current collection matches that canonical identity.

If any step fails:

```text
NO CONFIRMED EDGE
```

---

# 25. Supported evidence strategy

v0.12 must reuse facts already extracted by Radar where possible.

Do not create a broad new repository-reference crawler.

The relationship resolver should operate on normalized facts/evidence already produced during repository analysis or on very small deterministic extensions to existing extraction.

The implementation spec must inspect current facts before deciding exact supported rules.

The preferred v0.12 evidence types are explicit machine-readable repository references.

Examples may include deterministic repository URLs present in recognized dependency/configuration structures.

The implementation MUST document exactly which evidence rules were actually added.

---

# 26. Allowed relationship evidence

A rule is acceptable when all of the following are true:

* evidence is machine-readable,
* source path is known,
* extracted value is explicit,
* target repository identity can be canonicalized,
* resolution is exact.

For example, a dependency entry containing a full Git repository URL may qualify.

Conceptually:

```text
git+https://github.com/example/library-b.git
```

can normalize to repository identity:

```text
https://github.com/example/library-b
```

If that identity exactly matches one repository in the supplied collection:

```text
A -> B
```

may be emitted.

---

# 27. Forbidden relationship evidence

The following MUST NOT create confirmed cross-repository relationships on their own:

```text
package name == repository name
component name == repository name
folder name == repository name
README mentions repository name
service name resembles repository name
import namespace resembles repository name
substring match
Levenshtein similarity
GitHub search result
organization membership
common prefix
common owner
common topic/tag
```

These may be useful in future versions but are out of scope for v0.12.

---

# 28. Relationship target resolution

Given normalized reference:

```text
R
```

and supplied collection repository identities:

```text
C = {R1, R2, ... Rn}
```

resolution must behave as follows.

## Exactly one match

```text
count(matches(R, C)) == 1
```

Result:

```text
CONFIRMED RELATIONSHIP
```

---

## Zero matches

```text
count(matches(R, C)) == 0
```

Result:

```text
UNRESOLVED
```

Possible reason:

```text
OUTSIDE_COLLECTION
```

No edge.

---

## More than one match

```text
count(matches(R, C)) > 1
```

Result:

```text
AMBIGUOUS
```

No edge.

Radar must not select one.

---

# 29. Relationship types

v0.12 should use the smallest meaningful relationship vocabulary.

Preferred initial type:

```text
repository_dependency
```

or the equivalent naming already consistent with Radar.

Avoid introducing a broad taxonomy unless current evidence requires it.

Do not add:

* owns,
* deploys,
* maintained-by,
* communicates-with,
* same-team,
* same-product,
* runtime-calls,
* migration-risk.

---

# 30. Evidence model

Every confirmed relationship must contain at least one evidence record.

Conceptual evidence structure:

```json
{
  "snapshot_id": "...",
  "path": "package.json",
  "kind": "git_repository_reference",
  "value": "git+https://github.com/example/library-b.git"
}
```

Exact fields should reuse current Radar evidence models when possible.

---

# 31. Evidence requirements

Evidence SHOULD preserve enough provenance to answer:

> Why does Radar believe A depends on B?

At minimum this requires:

* source repository/snapshot,
* source file/path or equivalent origin,
* extracted reference value,
* rule/fact type.

Optional existing context such as line numbers may be retained when already available.

v0.12 must not introduce expensive source duplication merely to enrich evidence.

---

# 32. Evidence normalization

Evidence lists must be deterministically normalized.

Rules:

* identical evidence records deduplicated,
* stable sort order,
* no dependence on filesystem enumeration,
* no dependence on asynchronous completion order.

Multiple evidence records may support one edge.

Example:

```text
A -> B
```

supported by:

```text
package.json
config/dependencies.yaml
```

still produces one edge with two evidence records.

---

# 33. Unresolved reference model

v0.12 must distinguish between:

1. confirmed relationship,
2. explicit repository reference outside collection,
3. explicit reference that cannot be normalized,
4. ambiguous target resolution,
5. absence of repository-reference evidence.

These states are not equivalent.

---

# 34. Confirmed relationship

Example:

```text
A contains exact URL of B
B exists in supplied collection
```

Result:

```text
CONFIRMED A -> B
```

---

# 35. Outside collection

Example:

```text
A explicitly references X
collection contains only A, B
```

Result:

```text
unresolved reference to X
```

No edge to B.

---

# 36. Unresolvable reference

Example:

Radar has explicit repository-like evidence but cannot safely canonicalize it using supported rules.

Result:

```text
UNKNOWN / UNRESOLVED
```

No edge.

---

# 37. Ambiguous reference

If one reference could map to more than one supplied repository under current deterministic normalization:

Result:

```text
AMBIGUOUS
```

No edge.

---

# 38. No evidence

If A contains no supported cross-repository evidence:

Result:

```text
no relationship
```

Do not emit UNKNOWN merely because no dependency exists.

UNKNOWN is for evidence whose meaning/target cannot be resolved safely, not for total lack of evidence.

---

# 39. Repository-level dependencies

For each repository, Radar should expose confirmed outgoing repository relationships.

Example:

```text
A -> B
A -> C
```

A has dependencies:

```text
[B, C]
```

The canonical relationship records remain the source of truth.

Repository convenience views must be derived from them.

---

# 40. Repository-level dependents

For confirmed edges:

```text
A -> B
C -> B
```

B has dependents:

```text
[A, C]
```

Dependents must be computed from the same confirmed normalized edge set.

No separate inference rules are allowed.

---

# 41. Partial failure handling

Multi-repository analysis introduces independent failure domains.

Failure of B must not automatically discard successful A.

Example:

```text
A SUCCESS
B FAILED
C SUCCESS
```

Result:

```text
PARTIAL
```

with A and C available.

---

# 42. Failure categories

Reuse current errors where possible.

Potential categories include:

```text
SOURCE_RESOLUTION_FAILED
REPOSITORY_UNAVAILABLE
INVALID_REF
SNAPSHOT_RESOLUTION_FAILED
SCAN_FAILED
DUPLICATE_REPOSITORY_CONFLICT
```

Do not create a large new failure hierarchy unless required.

---

# 43. Failure visibility

A failed repository must appear in repository results.

Example conceptually:

```json
{
  "repository": {
    "requested_url": "...",
    "requested_ref": "main"
  },
  "status": "FAILED",
  "error": {
    "code": "INVALID_REF",
    "message": "..."
  }
}
```

Radar must never silently remove failed repositories from the response.

---

# 44. Relationship behavior under partial failure

Cross-repository relationships are built only using available snapshots and explicit collection identities.

Suppose:

```text
A SUCCESS
B FAILED
```

and A explicitly references B.

If B's canonical repository identity is known from input but its snapshot is unavailable, Radar must not claim a fully analyzed dependency edge if the approved relationship model requires a valid target snapshot.

The preferred v0.12 behavior is:

```text
reference exists
target repository is part of collection
target snapshot unavailable
```

represented as unresolved/unavailable rather than confirmed map edge.

This keeps confirmed edges restricted to successfully represented map nodes.

The unresolved reason may be:

```text
TARGET_UNAVAILABLE
```

---

# 45. Cache reuse

Multi-repository mapping must reuse the current repository snapshot analysis pipeline.

Do not create a second scan cache.

---

# 46. Cache key

The semantic cache key is based on immutable snapshot identity.

Conceptually:

```text
(repository_identity, resolved_revision)
```

not:

```text
collection_id
request_index
branch_name
```

---

# 47. Cache reuse across collections

Example:

Map 1:

```text
[A@SHA1, B@SHA2]
```

Map 2:

```text
[A@SHA1, C@SHA3]
```

A@SHA1 should reuse its existing snapshot analysis.

It must not be rescanned solely because the collection changed.

---

# 48. Collection-level recomputation

Cross-repository relationship resolution depends on collection membership.

Therefore snapshot analysis may be reused, but collection-level resolution must be recomputed as needed.

Example:

A contains explicit reference to B.

Map:

```text
[A]
```

Result:

```text
reference outside collection
no confirmed edge
```

Map:

```text
[A, B]
```

Result:

```text
A -> B
```

Same A snapshot.

Different collection-level relationship result.

This is expected.

---

# 49. No stale relationship caching

Relationships must not be stored inside reusable snapshot analysis in a way that assumes collection membership.

Snapshot cache stores source-local analysis.

The cross-repository map layer resolves references against the current collection.

---

# 50. Source-neutral architecture

v0.12 must preserve the current architectural separation.

Expected responsibilities:

## `api/`

* validate requests,
* call orchestration service,
* serialize response.

No relationship-resolution business logic.

---

## `models/`

Contains models for:

* repository map request,
* repository identity,
* snapshot identity,
* repository map entry,
* relationship,
* relationship evidence,
* unresolved reference,
* partial failure,
* map response.

Reuse current types wherever possible.

---

## `services/`

Responsible for:

* map orchestration,
* repository normalization coordination,
* snapshot resolution coordination,
* cache reuse,
* relationship resolution,
* outgoing/incoming relationship views,
* deterministic normalization.

---

## `sources/`

Responsible for source-specific operations:

* canonicalizing repository input,
* resolving refs,
* obtaining immutable revisions,
* retrieving repository contents where existing scan flow requires it.

GitHub-specific behavior stays here.

---

## `core/`

Only shared deterministic primitives where appropriate.

Do not move high-level orchestration into core merely for v0.12.

---

## `main.py`

Router/application registration only.

No map business logic.

---

# 51. Proposed service flow

Conceptually:

```text
POST /map
    ↓
MultiRepositoryMapService
    ↓
normalize requested repositories
    ↓
resolve repository identity + immutable revision
    ↓
deduplicate/conflict check
    ↓
lookup snapshot cache
    ↓
existing repository scan pipeline
    ↓
collect successful repository analyses
    ↓
extract supported repository references
    ↓
resolve references against supplied collection
    ↓
build canonical relationship set
    ↓
derive dependencies/dependents
    ↓
normalize ordering
    ↓
return COMPLETE/PARTIAL map
```

---

# 52. API response

Conceptual response:

```json
{
  "status": "COMPLETE",
  "repositories": [
    {
      "repository_id": "https://github.com/example/service-a",
      "requested_ref": "main",
      "resolved_revision": "aaaaaaaa...",
      "snapshot_id": "..."
    },
    {
      "repository_id": "https://github.com/example/library-b",
      "requested_ref": "main",
      "resolved_revision": "bbbbbbbb...",
      "snapshot_id": "..."
    }
  ],
  "relationships": [
    {
      "source_repository": "https://github.com/example/service-a",
      "target_repository": "https://github.com/example/library-b",
      "type": "repository_dependency",
      "evidence": [
        {
          "path": "package.json",
          "kind": "git_repository_reference",
          "value": "git+https://github.com/example/library-b.git"
        }
      ]
    }
  ],
  "unresolved_references": []
}
```

The actual response may include compact repository-level dependency/dependent views as long as they are derived from the same canonical relationships.

---

# 53. Successful two-repository example

Request:

```json
{
  "repositories": [
    {
      "url": "https://github.com/acme/api",
      "ref": "main"
    },
    {
      "url": "https://github.com/acme/shared",
      "ref": "main"
    }
  ]
}
```

Suppose api contains explicit supported evidence:

```text
https://github.com/acme/shared.git
```

Response conceptually:

```json
{
  "status": "COMPLETE",
  "repositories": [
    {
      "repository_id": "https://github.com/acme/api",
      "resolved_revision": "111111...",
      "dependencies": [
        "https://github.com/acme/shared"
      ],
      "dependents": []
    },
    {
      "repository_id": "https://github.com/acme/shared",
      "resolved_revision": "222222...",
      "dependencies": [],
      "dependents": [
        "https://github.com/acme/api"
      ]
    }
  ],
  "relationships": [
    {
      "source_repository": "https://github.com/acme/api",
      "target_repository": "https://github.com/acme/shared",
      "type": "repository_dependency",
      "evidence": [
        {
          "path": "package.json",
          "value": "https://github.com/acme/shared.git"
        }
      ]
    }
  ],
  "unresolved_references": []
}
```

---

# 54. Similar-name negative example

Collection:

```text
payments-api
payments-shared
```

Suppose `payments-api` has a package/component called:

```text
payments-shared
```

but no approved explicit repository reference.

Expected:

```json
{
  "relationships": []
}
```

No edge.

---

# 55. Outside-collection example

Collection:

```text
A
B
```

A explicitly references repository X.

Expected:

```json
{
  "relationships": [],
  "unresolved_references": [
    {
      "source_repository": "A",
      "target_reference": "X",
      "reason": "OUTSIDE_COLLECTION"
    }
  ]
}
```

Radar must not map X to B because their names or package names appear similar.

---

# 56. Partial failure example

Request:

```text
A
B
C
```

Results:

```text
A SUCCESS
B INVALID_REF
C SUCCESS
```

Map:

```json
{
  "status": "PARTIAL",
  "repositories": [
    {
      "repository_id": "A",
      "status": "SUCCESS"
    },
    {
      "repository_id": "B",
      "status": "FAILED",
      "error": {
        "code": "INVALID_REF"
      }
    },
    {
      "repository_id": "C",
      "status": "SUCCESS"
    }
  ]
}
```

A and C remain usable.

---

# 57. Duplicate repository example

Request:

```text
A@main
A@main
B@main
```

Both A entries resolve to:

```text
A@SHA1
```

Expected semantic map:

```text
A@SHA1
B@SHA2
```

No duplicate A node.

No duplicate scan.

No duplicate edge.

---

# 58. Conflicting duplicate example

Request:

```text
A@release-1
A@release-2
```

Resolved:

```text
A@SHA1
A@SHA2
```

Preferred v0.12 result:

```text
duplicate repository conflict
```

rather than representing two active states of A in one map.

---

# 59. Determinism requirements

All semantically unordered structures must be sorted deterministically.

This includes, where applicable:

* repositories,
* relationship edges,
* evidence records,
* dependencies,
* dependents,
* unresolved references,
* failure records.

Do not rely on:

* request order,
* dictionary order assumptions,
* async task completion order,
* filesystem traversal order,
* source API ordering.

---

# 60. Stable relationship key

A canonical semantic relationship may be identified by:

```text
(source_repository_identity,
 target_repository_identity,
 relationship_type)
```

Evidence does not change semantic edge identity.

Evidence is aggregated beneath the canonical edge.

---

# 61. Backward compatibility

v0.12 adds functionality.

It does not replace the single-repository model.

Existing endpoints remain:

```text
/scan
/impact
/diff
```

Existing behavior for:

* facts,
* evidence,
* repository maps,
* configuration conflict detection,
* technical change intelligence

must remain compatible.

Internal refactoring is permitted only when behavior remains covered by regression tests.

---

# 62. Testing strategy

Tests must be added before v0.12 is considered complete.

---

# 63. Unit tests — repository identity

Required coverage:

* canonical normalization,
* equivalent source URL forms,
* distinct repositories remain distinct,
* repository identity excludes ref,
* repository identity excludes commit SHA.

---

# 64. Unit tests — snapshot identity

Required coverage:

* requested branch resolves to SHA,
* requested tag resolves to SHA,
* snapshot identity contains immutable revision semantics,
* same repository + same SHA => same snapshot identity,
* same repository + different SHA => different snapshot identity.

---

# 65. Unit tests — duplicate collection entries

Required:

* duplicate same repository/same snapshot,
* deduplication deterministic,
* no duplicate scan,
* conflicting duplicate snapshots handled explicitly.

---

# 66. Unit tests — relationship resolution

Required:

* exact supported reference resolves,
* zero target matches,
* target outside collection,
* ambiguous match,
* similar repository names do not resolve,
* unsupported evidence does not create edge.

---

# 67. Unit tests — evidence

Required:

* every confirmed edge has evidence,
* duplicate evidence deduplicated,
* multiple evidence records aggregate under one edge,
* evidence ordering deterministic,
* evidence provenance preserved.

---

# 68. Unit tests — dependents

Given:

```text
A -> B
C -> B
```

assert:

```text
A dependencies = [B]
C dependencies = [B]
B dependents = [A, C]
```

Ordering deterministic.

---

# 69. Unit tests — partial failure

Required:

* one success + one failure => PARTIAL,
* failed repository remains in output,
* successful repository remains available,
* no relationship created against unavailable target snapshot,
* unresolved reason is deterministic.

---

# 70. Unit tests — cache reuse

Required:

* same snapshot requested twice uses cached analysis,
* same snapshot reused across different map collections,
* changing only collection membership does not rescan existing snapshot,
* cross-repo resolution still recomputed for each collection.

---

# 71. Unit tests — deterministic ordering

Required:

```text
[A, B, C]
```

versus:

```text
[C, B, A]
```

must produce equivalent normalized map result.

---

# 72. API tests

Add tests for:

```http
POST /map
```

At minimum:

* valid complete map,
* valid partial map,
* request validation,
* duplicate entry,
* conflicting duplicate,
* unresolved reference,
* confirmed relationship,
* no false relationship.

---

# 73. Regression tests

All existing v0.11 tests remain green.

Current baseline:

```text
133 PASS
```

The exact v0.12 count will be larger.

No existing assertion should be weakened merely to make v0.12 pass.

---

# 74. Controlled acceptance fixtures

v0.12 must include a deterministic controlled acceptance set.

---

## Case A — explicit A → B

Repository A contains supported explicit repository evidence pointing to B.

Collection:

```text
A
B
```

Expected:

```text
exactly one A -> B relationship
```

Relationship contains evidence.

B contains A in dependents.

---

## Case B — name similarity only

Repositories:

```text
service-core
service-core-utils
```

A contains textual/package/component names resembling B but no supported repository evidence.

Expected:

```text
0 edges
```

---

## Case C — target outside collection

A explicitly references X.

Collection:

```text
A
B
```

Expected:

```text
0 confirmed edges
1 unresolved/outside-collection reference
```

---

## Case D — unrelated third repository

Collection:

```text
A
B
C
```

Only A references B.

Expected:

```text
exactly 1 edge:
A -> B
```

No A -> C.

No B -> C.

No C -> anything.

---

## Case E — partial failure

Collection:

```text
A
B
```

B cannot resolve or scan.

Expected:

```text
status = PARTIAL
A SUCCESS
B FAILED
```

No invented relationship to unavailable B snapshot.

---

## Case F — duplicate same snapshot

Request contains A twice.

Both resolve to same SHA.

Expected:

```text
one semantic A snapshot
cache reused
stable output
```

---

## Case G — order permutation

Run:

```text
[A, B, C]
```

and:

```text
[C, A, B]
```

Expected:

```text
semantic output identical
```

---

## Case H — relationship removed between snapshots

A@SHA1 contains explicit B reference.

A@SHA2 removes it.

Expected:

Map using SHA1:

```text
A -> B
```

Map using SHA2:

```text
no A -> B
```

No stale relationship due to caching.

---

## Case I — ambiguous target

Construct deterministic test case where supported normalized evidence cannot uniquely identify one target.

Expected:

```text
AMBIGUOUS / UNKNOWN
0 confirmed edges
```

Radar never chooses arbitrarily.

---

# 75. Controlled acceptance output

Acceptance should produce a compact matrix similar to:

| Case | Expected                | Result |
| ---- | ----------------------- | ------ |
| A    | A -> B                  | PASS   |
| B    | 0 edges                 | PASS   |
| C    | outside collection      | PASS   |
| D    | exactly one edge        | PASS   |
| E    | partial map             | PASS   |
| F    | dedupe/cache reuse      | PASS   |
| G    | identical semantics     | PASS   |
| H    | removed edge disappears | PASS   |
| I    | ambiguity unresolved    | PASS   |

---

# 76. Real repository validation

After controlled fixtures pass, run v0.12 against real repositories.

The objective is not maximum relationship coverage.

The objective is to validate:

* no obvious false positives,
* repository identity correctness,
* immutable snapshot pinning,
* deterministic output,
* evidence provenance,
* unresolved-reference behavior,
* cache reuse,
* partial failure handling.

A real-world collection returning:

```text
0 confirmed relationships
```

is valid when no supported deterministic evidence exists.

Do not add heuristics merely to produce a more interesting graph.

---

# 77. Heavy repository validation

Existing heavy repository coverage must remain green.

At minimum revalidate the established cases:

* Node,
* Deno,
* LLVM.

Multi-repository changes must not regress single-repository scanning.

---

# 78. Existing validation harness

Current baseline:

```text
13 PASS
```

The existing validation harness must continue passing.

New v0.12 validation may extend the harness or exist as a focused additional harness depending on current architecture.

Do not unnecessarily rewrite the existing harness.

---

# 79. Full corpus validation

Current baseline:

```text
18/18 functionally PASS
```

All existing corpus cases must remain functionally green.

v0.12 acceptance includes:

1. backend test suite,
2. controlled v0.12 acceptance,
3. existing validation harness,
4. existing full corpus,
5. heavy repositories,
6. deterministic rerun,
7. request-order permutation,
8. partial failure,
9. cache reuse.

---

# 80. Same-SHA stability

Existing v0.11 invariant:

```text
same SHA diff = 0 technical changes
```

must remain unaffected.

v0.12 must not alter Technical Change Intelligence semantics.

---

# 81. No-noise principle

The existing Express real-world acceptance demonstrated that Radar should not generate technical-change noise when nothing meaningful happened.

v0.12 follows the same philosophy for repository relationships.

No cross-repository relationship is better than a guessed relationship.

---

# 82. Expected architecture changes

Exact files depend on current repository structure.

Likely affected areas:

```text
backend/app/api/
backend/app/models/
backend/app/services/
backend/app/sources/
backend/app/core/
backend/tests/
docs/
```

Possible additions may include concepts equivalent to:

```text
multi_repository_map models
multi_repository_map service
repository relationship resolver
repository identity normalization helpers
/map API route
```

Names should follow existing project conventions rather than forcing these exact names.

---

# 83. Minimal-change requirement

Implementation should prefer:

* extending existing models,
* reusing scan pipeline,
* reusing snapshot/cache behavior,
* pure relationship resolution,
* small API additions.

Avoid:

* replacing working scan architecture,
* creating a separate repository scanner,
* broad source abstraction rewrites,
* database introduction,
* event architecture,
* graph database,
* async distributed workers,
* future-facing plugin systems.

---

# 84. Source responsibilities

Source layer may need small extensions to expose:

* canonical repository identity,
* requested ref,
* resolved immutable revision.

Any new source API should remain generic enough to support non-GitHub Git repositories later.

Do not introduce GitHub GraphQL/org discovery for v0.12.

---

# 85. Relationship resolver responsibilities

The relationship resolver should ideally be a deterministic transformation over:

```text
available repository analyses
+
collection repository identities
```

Input:

```text
repository-local facts/evidence
```

Output:

```text
confirmed relationships
unresolved references
```

This keeps relationship logic testable independently of network/source access.

---

# 86. Dependency/dependent projection

After relationships are normalized:

```text
relationships
    ↓
outgoing dependencies
incoming dependents
```

These are projections.

They must not invoke relationship inference again.

---

# 87. Performance constraints

v0.12 should not require rescanning all repositories if immutable snapshots are already cached.

Collection-level complexity should primarily depend on:

* number of repository-local references,
* number of supplied repositories.

Avoid all-to-all content comparison.

No fuzzy similarity scans.

---

# 88. Security and isolation

Multi-repository mapping must not cause Radar to fetch arbitrary URLs extracted from repository contents.

An explicit reference discovered inside A is used only for identity comparison against repositories already supplied in the request.

Radar MUST NOT:

```text
see URL in A
→ clone URL automatically
```

This is both a scope and safety boundary.

---

# 89. Serialization discipline

Public API should avoid leaking internal implementation objects.

Response models must be explicit and deterministic.

Avoid returning huge duplicate scan payloads inside `/map`.

The map should summarize repository-level technical relationships rather than embedding every full `/scan` result unless current architecture has a compelling reusable representation.

---

# 90. Map payload size

The `/map` response should contain enough information to identify:

* repository,
* snapshot,
* status,
* relationships,
* evidence,
* unresolved references,
* dependents.

It should not duplicate all file-level facts from every repository.

Detailed single-repository inspection remains available through existing APIs.

---

# 91. Error philosophy

Radar must continue to prefer explicit uncertainty.

Bad:

```text
"probably repository B"
```

Good:

```text
{
  "status": "UNRESOLVED",
  "reason": "OUTSIDE_COLLECTION"
}
```

Bad:

```text
select first matching candidate
```

Good:

```text
AMBIGUOUS
```

---

# 92. Deterministic normalization order

Recommended semantic sort keys:

Repositories:

```text
repository_identity
```

Relationships:

```text
source_repository_identity
target_repository_identity
relationship_type
```

Evidence:

```text
path
kind
value
```

Unresolved references:

```text
source_repository_identity
path
target_reference
reason
```

Exact keys may adapt to existing model fields.

---

# 93. Implementation boundaries

A `/map` call should not:

* alter repository contents,
* alter refs,
* create commits,
* modify caches incorrectly,
* mutate prior scan results,
* discover new repositories,
* invoke AI,
* query Jira/Confluence/Jenkins.

It is a deterministic analysis operation.

---

# 94. Observability for acceptance

Implementation should expose enough data/tests to verify:

* whether a snapshot was reused,
* whether repositories resolved to expected SHAs,
* whether map output is order-independent.

This does not require a new production observability subsystem.

Tests or debug-safe internal hooks are sufficient.

---

# 95. Definition of Done

Radar v0.12 is complete when all of the following hold.

## Domain

* repository identity exists separately from snapshot identity,
* snapshots are pinned to immutable revisions,
* explicit collections are supported,
* same repository cannot ambiguously exist at two active snapshots in one map.

## Relationships

* deterministic cross-repository resolution exists,
* every confirmed relationship has evidence,
* no name-based guessing exists,
* ambiguity produces no edge,
* outside-collection references produce no invented edge.

## Graph views

* repository-level dependencies exist,
* repository-level dependents exist,
* both derive from the same confirmed relationship set.

## Reliability

* partial failure is represented explicitly,
* successful repositories survive unrelated failures,
* cache reuse works at immutable snapshot level.

## Determinism

* repeated map produces same semantic result,
* reordered input produces same semantic result,
* evidence/relationships serialize deterministically.

## Compatibility

* `/scan` remains compatible,
* `/impact` remains compatible,
* `/diff` remains compatible,
* v0.11 Technical Change Intelligence remains compatible,
* v0.10 configuration conflict detection remains compatible.

## Validation

* new v0.12 tests pass,
* complete backend suite passes,
* existing validation harness passes,
* controlled acceptance passes,
* full corpus passes,
* Node/Deno/LLVM heavy cases pass,
* cache reuse case passes,
* partial failure case passes,
* permutation test passes.

---

# 96. Release workflow

The intended workflow is:

```text
1. finalize docs/radar-v0.12.md
2. review specification
3. implement v0.12
4. run focused tests
5. run controlled acceptance
6. validate real repositories
7. run full corpus
8. final review
9. tag v0.12.0
```

The implementation agent MUST NOT create the final release tag unless explicitly instructed after acceptance.

---

# 97. Explicitly deferred work

Potential future areas are intentionally deferred:

* repository discovery,
* organization crawling,
* package registry identity resolution,
* fuzzy matching,
* runtime service topology,
* ownership,
* teams,
* deployment graph,
* Jira links,
* Confluence links,
* Jenkins/build graph,
* risk models,
* migration planning,
* natural-language querying,
* AI reasoning.

v0.12 should not build partial versions of these features.

---

# 98. Product principle

The defining principle of v0.12 is:

> Radar may connect two repositories only when it can show why.

A technically empty map that contains no false assumptions is a better result than a dense graph built from guesses.

---

# 99. Final acceptance statement

Radar v0.12 should be considered successful when the following statement is true:

> Given an explicit collection of repositories, Radar deterministically resolves their immutable snapshots, reuses repository analysis where possible, produces evidence-backed cross-repository relationships only when they can be proven, exposes incoming and outgoing repository dependencies, represents uncertainty and partial failures explicitly, and preserves all existing single-repository behavior.

---

# 100. v0.12 scope summary

The complete intended scope is:

```text
explicit repositories
+
immutable snapshots
+
repository identity
+
snapshot identity
+
existing scan reuse
+
deterministic repository references
+
evidence-backed cross-repo edges
+
dependencies
+
dependents
+
unresolved states
+
partial failures
+
cache reuse
+
deterministic output
```

Nothing beyond this is required for v0.12.
