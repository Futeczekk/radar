We are starting Radar Core v0.10.

Do NOT implement code yet.

First inspect the current repository and understand the product as it exists after `v0.9.0`.

Read at minimum:

* `README.md`
* `docs/radar-v0.9.md`
* `docs/architecture.md`
* `docs/development.md`
* `docs/testing.md`
* `docs/ci.md`
* all ADRs under `docs/decisions/`
* current models for Fact, Evidence, Context and RepositorySnapshot
* configuration extractors
* component/file graph code where relevant
* `/scan` application flow
* validation subsystem
* git history from v0.1.0 through v0.9.0

Then create:

`docs/radar-v0.10.md`

# Radar Core v0.10 — Configuration Conflicts

The primary question for v0.10 is:

> Where does a repository disagree with itself about important technical configuration?

Radar should deterministically detect configuration evidence that is incompatible or potentially contradictory across different parts of the same repository.

Examples:

* `pyproject.toml` declares Python `>=3.11`
* Docker uses `python:3.10`
* CI uses Python `3.12`

or:

* `package.json` declares Node `>=20`
* CI runs Node `18`

Radar must report the observed disagreement together with evidence and context.

Radar must NOT decide:

* which declaration is correct,
* whether the repository is broken,
* whether the mismatch is intentional,
* whether the mismatch will cause a production failure.

The result must remain evidence-backed and conservative.

## Core principles

Preserve all existing Radar principles:

* evidence-first
* deterministic core before AI
* UNKNOWN over guessing
* precision over recall
* source-neutral core
* Fact + Evidence + Context + Confidence
* backward compatibility with v0.1-v0.9
* no GitHub-specific business logic inside Radar Core

## v0.10 scope

Design deterministic configuration-conflict detection using facts Radar already extracts reliably.

Initial supported conflict areas should focus on:

* Python required/runtime versions
* Python project declaration vs CI runtime
* Python project declaration vs Docker runtime where deterministically comparable
* Node required/runtime versions
* Node project declaration vs CI runtime
* Node project declaration vs Docker runtime where deterministically comparable
* CMake minimum version only where multiple meaningful declarations can be compared safely
* other already-supported configuration facts only if the current code proves comparison can be deterministic and useful

Do NOT add support for unrelated technologies merely to make v0.10 larger.

The design should be extensible so later versions can add new conflict subjects without rewriting the entire detector.

## Critical semantic rule

Different strings are NOT automatically conflicts.

Examples:

* Python `>=3.11` and runtime `3.12` → compatible
* Python `>=3.11` and runtime `3.10` → incompatible
* Node `>=20` and runtime `20` → compatible
* Node `>=20` and runtime `18` → incompatible
* identical values from different files → no conflict

The specification must define conservative deterministic normalization and compatibility rules.

Support only a limited, explicit version grammar in v0.10.

At minimum consider:

* exact versions
* major/minor versions
* `>=`
* `>`
* `<=`
* `<`
* simple equality
* forms such as `3.11`
* `3.11.x`
* `20`
* `20.x`

Do NOT create a universal package-manager constraint solver.

Unsupported or ambiguous syntax must result in UNKNOWN / unsupported comparison rather than a confident conflict.

Examples that should be handled conservatively:

* variables
* interpolated versions
* complex OR expressions
* unusual package-manager-specific ranges
* Docker tags that are not clearly versions
* unrelated subprojects
* generated/test/example/vendor configurations

## Conflict model

Design an appropriate model consistent with the existing architecture.

Conceptually it may resemble:

`ConfigurationConflict`

with fields such as:

* subject
* observations
* compatibility/status
* evidence
* scopes
* confidence

Each observation should preserve as much existing context as possible, including:

* original value
* normalized value if applicable
* evidence path
* source_type
* scope
* environment
* confidence

Do not duplicate information unnecessarily if existing Fact/Evidence/Context models can be reused.

## Scope semantics

Existing Radar scopes must matter.

Strong contexts such as:

* project
* CI
* runtime/infrastructure where represented

may participate in top-level conflict analysis.

Weak scopes such as:

* test
* example
* vendor
* generated
* subproject

must not accidentally create a top-level repository conflict.

CI matrices must be treated intentionally.

For example, a CI matrix testing Python:

* 3.10
* 3.11
* 3.12

must not automatically be treated as three mutually conflicting declarations.

The specification must describe how CI matrices are interpreted in relation to project requirements.

## Architecture

The specification must clearly define where v0.10 logic belongs.

Preferred conceptual flow:

`RepositorySnapshot`
→ deterministic facts
→ configuration observations
→ normalization
→ compatibility evaluation
→ conflicts
→ API response

Conflict detection must remain source-neutral.

GitHubSource must only provide repository data.

API routes must remain thin.

Do not move business logic into GitHub adapters or routes.

## API

Specify how v0.10 becomes visible to callers.

Prefer extending the existing `/scan` response with a field such as:

`configuration_conflicts`

if this fits the current architecture.

Preserve all existing response fields and behavior.

Empty conflict results should be represented predictably and deterministically.

The API must never hide the evidence behind a conflict.

## Determinism

Results must be:

* stable in ordering
* deduplicated
* deterministic across repeated scans
* semantically identical between cache hit and cache miss
* independent of GitHub-specific ordering

## Tests

Define focused tests for at least:

1. incompatible Python project requirement vs CI
2. compatible Python project requirement vs CI
3. incompatible Node project requirement vs CI
4. compatible Node project requirement vs CI
5. project vs Docker mismatch where supported
6. same exact value from multiple sources
7. unsupported/ambiguous constraint grammar
8. CI matrices
9. weak scopes
10. unrelated subprojects
11. evidence preservation
12. context preservation
13. deterministic ordering
14. deduplication
15. cache hit/miss semantic equivalence
16. source-neutral core behavior
17. `/scan` regression compatibility

Do not weaken existing tests.

## Controlled validation

The specification should define manual acceptance using a small representative set before running the whole corpus.

Use:

* `Futii10/radar-test`
* one Python repository
* `nodejs/node`
* one JS/TS repository
* one C/C++ repository
* `apache/arrow` if useful

For every detected conflict manually inspect:

* subject
* original values
* normalized values
* compatibility result
* scopes
* evidence paths
* confidence

Do not consider a test successful merely because conflict count is non-zero.

The main concern is false positives.

## Validation corpus

Existing v0.1-v0.9 behavior must remain regression-compatible.

v0.10 acceptance must eventually include:

* focused tests
* full backend tests
* validation harness
* `make check`
* `git diff --check`
* representative controlled live scans
* full existing corpus
* existing heavy repositories with their established longer timeout

Do not change pinned SHAs or historical expected behavior just to make v0.10 pass.

## Performance

Conflict evaluation should operate primarily on existing extracted facts.

Do not introduce another expensive full-repository fetch or another complete parse pass if existing facts/context are sufficient.

Document any expected performance impact.

## Explicit non-goals

v0.10 must NOT implement:

* AI / LLM inference
* automatic recommendations
* deciding which declaration is correct
* risk scoring
* security vulnerability scanning
* Jira
* Confluence
* Slack / Teams
* Jenkins integration
* ownership
* cross-repository company graph
* company-wide technical model
* v0.11 features
* unrelated architectural refactors

## Definition of Done

The v0.10 specification should define a strict completion bar.

At minimum:

* deterministic conflict model exists
* supported compatibility rules are documented
* ambiguous syntax fails conservatively
* strong vs weak scopes are handled correctly
* CI matrices do not create false self-conflicts
* evidence/context is preserved
* API remains backward compatible
* output ordering is deterministic
* focused tests pass
* full existing test suite passes
* existing corpus behavior does not regress
* controlled real-repository results have been manually inspected
* no demonstrated supported-case false positives remain
* documentation is updated
* no unrelated work is included

## Important development rule

Do not modify application code while creating this specification.

Do not commit, push, tag, reset, rebase, checkout or modify git history.

Do not start v0.11.

At the end provide a concise report containing:

1. files inspected
2. current architecture understood
3. proposed v0.10 architecture
4. proposed conflict model
5. compatibility semantics
6. scope semantics
7. API design
8. validation strategy
9. major risks / ambiguity areas
10. confirmation that `docs/radar-v0.10.md` was created

The document should be implementation-ready so another engineer can implement v0.10 without inventing missing product semantics.
