# Architecture

Radar is a deterministic repository analysis service. The current flow is:

```text
Source adapter -> RepositorySnapshot -> Application -> Radar Core
                                             |-> facts and evidence
                                             |-> repository graph
                                             |-> component graph
                                             |-> impact
                                             |-> diff
```

## Boundaries

- `app/sources` retrieves source data and produces source-neutral snapshots.
  `GitHubSource` is the current adapter; GitHub is not the analysis model.
- `app/application` coordinates loading, extraction, graph construction, and
  release persistence for API use cases.
- `app/core` contains source-neutral analysis access and persistence primitives.
- `app/core/configuration_conflicts.py` evaluates supported configuration facts
  without source or transport knowledge and returns deterministic,
  evidence-backed conflict observations.
- `app/core/technical_changes.py` classifies deterministic changes from the
  existing snapshot diff, facts, conflict state, graphs, and impact results.
- `app/core/repository_identity.py` performs exact repository identity
  normalization; it never infers identity from names or similarity.
- `app/services/repository_map.py` orchestrates explicit multi-repository map
  requests, immutable scan results, relationship resolution, partial status,
  and deterministic dependency/dependent projections.
- `app/extractors` performs deterministic, defensive parsing and returns facts
  with evidence, confidence, and context.
- `app/services/impact.py` computes dependency reachability. It does not infer
  risk or predict breakage.
- `app/services/diff.py` compares immutable snapshot-shaped data and reuses
  impact analysis for changed files.
- `app/api` parses requests, maps errors to HTTP, and serializes use-case output.
- `validation` owns compatibility workflow documentation and cache policy;
  `scripts/validate_corpus.py` remains the compatibility entrypoint for users
  of v0.8.x.

Legacy analysis helpers remain importable from `app.services.scanner` because
milestone tests and downstream callers use those symbols. New application code
uses `app.core.analysis`; moving the implementation wholesale is intentionally
deferred until a behavior-preserving extraction can be covered separately.

## Invariants

Evidence is retained on facts and relationships. Unknown or unsupported input
is not guessed. Core analysis performs no network access and has no FastAPI
request dependency. New source adapters should implement the snapshot contract,
not add provider logic to the core. Scan responses expose the additive
`configuration_conflicts` field; the legacy `findings` field and extractor
tuple remain unchanged for v0.1-v0.9 callers. Diff responses expose additive
`technical_changes` at the top level while preserving the existing `changes`
object. `/map` is additive and does not alter `/scan`, `/impact`, or `/diff`.
