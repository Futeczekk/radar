We are starting Radar Core v0.11.

Do NOT implement code yet.

First inspect the repository as it exists after `v0.10.0`.

Read at minimum:

* `README.md`
* `docs/radar-v0.9.md`
* `docs/radar-v0.10.md`
* `docs/architecture.md`
* `docs/development.md`
* `docs/testing.md`
* `docs/ci.md`
* all ADRs under `docs/decisions/`
* snapshot/diff implementation
* impact analysis
* facts/evidence/context models
* configuration conflict implementation
* component and file dependency graphs
* `/scan`, `/diff`, and `/impact`
* validation subsystem
* git history from v0.1.0 through v0.10.0

Then create:

`docs/radar-v0.11.md`

# Radar Core v0.11 — Technical Change Intelligence

Primary question:

> What technically important changes happened between two known states of a repository, and what known parts of the system may be affected?

v0.8 already answers:

> What changed?

v0.11 should build on that and answer:

> Which changes are technically meaningful?

The goal is NOT to create AI summaries or subjective risk scores.

The goal is deterministic classification of meaningful technical changes using information Radar already knows.

## Core philosophy

Preserve all Radar principles:

* evidence-first
* deterministic core before AI
* UNKNOWN over guessing
* precision over recall
* source-neutral core
* Fact + Evidence + Context + Confidence
* backward compatibility
* deterministic output
* no unsupported risk claims

## Scope

v0.11 should classify important technical changes between two immutable repository snapshots.

Candidate change categories should include only things Radar already models reliably.

Examples:

### Runtime/configuration changes

* Python required version changed
* Node required version changed
* Docker base image changed
* CMake minimum version changed
* CI runtime version changed

### Configuration conflict changes

* new deterministic configuration conflict appeared
* existing conflict disappeared
* conflict observations changed

### Component changes

* component added
* component removed
* component type changed where deterministic
* important component relationship added/removed

### Dependency changes

* file dependency relationship added
* file dependency relationship removed
* component dependency relationship added/removed

Do not report every raw file edit as a meaningful technical change.

Raw file changes remain available through existing diff behavior.

## Technical change model

Design a source-neutral model such as:

`TechnicalChange`

with fields conceptually including:

* category
* subject
* change_type
* before
* after
* evidence
* scopes/context
* confidence
* affected_elements / impact summary where deterministically available

Use names that fit the current codebase.

Examples:

```text
category: runtime
subject: Python
change_type: version_changed
before: >=3.10
after: >=3.12
```

```text
category: configuration_conflict
subject: Python
change_type: conflict_introduced
```

```text
category: dependency
subject: backend/service.py -> backend/database.py
change_type: relationship_added
```

## Impact integration

v0.7 already provides impact analysis.

v0.11 should reuse it rather than implement another dependency engine.

For changed or removed technical elements, Radar may attach deterministic known dependents where appropriate.

Do NOT convert impact into a risk score.

Do NOT claim:

* production outage likely
* high-risk change
* safe change
* breaking change

unless the evidence deterministically supports such wording.

Prefer:

> Known dependents: X, Y, Z

rather than:

> This is dangerous.

## Importance

Do not introduce arbitrary numeric importance/risk scores.

A technical change should be included because it belongs to a documented deterministic category, not because of a guessed severity.

If useful, categories may have descriptive classes such as:

* runtime_change
* build_change
* configuration_change
* dependency_change
* component_change
* conflict_change

but do not rank them.

## Noise control

v0.11 must avoid becoming a prettier raw git diff.

Do not emit technical-change entries for:

* arbitrary README text edits
* formatting changes
* unrelated documentation changes
* source file content changes that do not alter a modeled Radar fact/relation/component
* test/example/vendor/generated-only changes unless explicitly relevant

Existing raw diff remains the fallback for those changes.

## Before/after semantics

Technical changes must be derived from two immutable snapshots.

Preserve:

* base repository/ref/SHA
* target repository/ref/SHA
* evidence from both states where applicable

The same snapshot compared to itself must produce zero technical changes.

Repository mismatch and invalid refs must preserve existing typed behavior.

## Configuration conflicts

Integrate v0.10 carefully.

Examples:

Before:

* Python requirement `>=3.11`
* CI `3.12`
* no conflict

After:

* Python requirement `>=3.11`
* CI `3.10`
* conflict exists

v0.11 should report:

`configuration_conflict_introduced`

Similarly, if the repository becomes compatible:

`configuration_conflict_resolved`

Do not infer intent or whether the resolution was deliberate.

## API

Specify how technical changes are exposed.

Prefer extending `/diff` with something like:

`technical_changes`

while keeping all existing v0.8 diff fields backward compatible.

Do not create unnecessary endpoints.

## Determinism

Output must be:

* stable
* sorted deterministically
* deduplicated
* independent of source ordering
* semantically identical across cache hit/miss

## Tests

Define strong tests for at least:

1. same snapshot → zero technical changes
2. Python version changed
3. Node version changed
4. Docker base image changed
5. CMake minimum version changed
6. CI runtime version changed
7. configuration conflict introduced
8. configuration conflict resolved
9. file dependency added
10. file dependency removed
11. component relationship added
12. component relationship removed
13. component added/removed
14. unrelated README edit does not become technical change
15. weak-scope-only change does not pollute project-level summary
16. evidence preserved from before/after
17. impact reused correctly
18. cycles do not break impact
19. deterministic ordering
20. cache hit/miss equivalence
21. source-neutral core behavior
22. `/diff` backward compatibility

## Controlled fixture

Use `Futii10/radar-test` for deterministic acceptance.

The specification should define controlled commits for at least:

* compatible Python configuration
* incompatible Python configuration
* runtime upgrade
* dependency relationship change

Reuse existing pinned fixtures where useful.

Do not automatically modify the external controlled repository while writing the specification.

Document exactly what fixtures are required.

## Real repository validation

After controlled validation, inspect representative real repositories.

Suggested:

* `nodejs/node`
* `apache/arrow`
* one Python project
* one C/C++ project
* one JS/TS project

Validation must inspect actual emitted technical changes, not just counts.

## Performance

Technical change intelligence should primarily reuse:

* existing snapshots
* existing facts
* existing diff
* existing dependency/component graphs
* existing impact analysis

Do not add another complete repository scan when existing snapshot data is sufficient.

Document performance implications.

## Explicit non-goals

v0.11 must NOT include:

* AI summaries
* natural-language Ask Radar
* migration dashboards
* migration progress scoring
* risk scoring
* recommendations
* Jira
* Confluence
* Jenkins integration
* ownership
* cross-repository company graph
* security scanning
* automatic breaking-change prediction
* v0.12 work
* unrelated architecture refactors

## Definition of Done

At minimum:

* source-neutral TechnicalChange model exists
* deterministic categories documented
* technical changes derive from immutable snapshots
* existing raw diff remains backward compatible
* v0.10 conflict changes are supported
* impact is reused rather than reimplemented
* no subjective severity/risk scoring
* noise is controlled
* evidence/context/confidence are preserved
* focused tests pass
* full backend tests pass
* validation harness passes
* controlled fixtures are manually validated
* real repositories are manually inspected
* existing validation corpus remains regression-compatible
* heavy repositories remain compatible
* `make check` passes
* `git diff --check` passes
* documentation is updated
* no unrelated work is included

Do not modify application code while creating this specification.

Do not commit, push, tag, reset, rebase, checkout or modify git history.

At the end report:

1. files inspected
2. current architecture understood
3. proposed v0.11 architecture
4. TechnicalChange model
5. deterministic change categories
6. noise-control rules
7. impact integration
8. API design
9. controlled fixture strategy
10. validation strategy
11. major risks/ambiguities
12. confirmation that `docs/radar-v0.11.md` was created
