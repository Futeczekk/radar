# Radar Core v0.3

## Status

COMPLETED

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED

v0.1 answers:

> What exists in this repository?

v0.2 answers:

> How is this repository configured?

v0.3 should answer:

> Can Radar trust and correctly interpret the facts it finds?

The main goal of v0.3 is reducing false positives by introducing context and scope awareness.

---

# Goal

Radar must stop treating every different value as a conflict.

Example:

```text
Project requirement:
Python >=3.12

CI compatibility matrix:
Python 3.11
Python 3.12
Python 3.13
```

This is NOT necessarily a version inconsistency.

Radar must understand that these facts have different contexts.

---

# Core Principle

A fact is not only:

```text
value
evidence
confidence
```

It also needs context.

Radar should be able to distinguish facts by concepts such as:

```text
scope
source_type
environment
```

Keep the implementation minimal.

Do not over-engineer the model.

---

# Fact Context

Extend the existing Fact model where appropriate.

Suggested optional fields:

```python
scope: str | None = None
source_type: str | None = None
environment: str | None = None
```

Examples:

```text
scope:
project
ci
test
example
vendor
subproject
documentation
generated
```

```text
source_type:
manifest
build_config
ci_config
test_matrix
documentation
generated_file
```

```text
environment:
runtime
build
test
compatibility
development
production
unknown
```

These values may evolve later.

Do not build a large taxonomy now.

---

# Context-Aware Findings

The finding engine must not compare facts blindly.

Before creating a finding, Radar should consider:

```text
Are these facts about the same technology?

Are their scopes comparable?

Are their environments comparable?

Is one value part of an intentional compatibility matrix?

Is one source only an example, fixture, vendor file, or generated file?

Is this actually a contradiction?
```

Only create findings when the conflict is sufficiently deterministic.

---

# Required False Positive Cases

v0.3 must handle at least the following classes.

---

## 1. CI Version Matrix

Example:

```yaml
strategy:
  matrix:
    python-version:
      - "3.11"
      - "3.12"
      - "3.13"
```

Used through:

```yaml
python-version: ${{ matrix.python-version }}
```

This should be treated as intentional compatibility testing.

Do NOT report:

```text
Python 3.11 conflicts with >=3.12
```

simply because 3.11 appears in the matrix.

The matrix should be represented as contextual evidence.

---

## 2. Examples / Demo / Documentation

Files under locations such as:

```text
examples/
example/
demo/
samples/
docs/
documentation/
```

should not automatically define the repository's primary runtime or configuration.

Example:

```text
package.json
→ Node 22

examples/legacy/package.json
→ Node 18
```

This should not automatically create a main-project version inconsistency.

---

## 3. Vendor / Third Party

Files under:

```text
vendor/
third_party/
external/
deps/
```

should normally have low relevance to the repository's own configuration.

Do not treat vendor configuration as the project's primary configuration.

---

## 4. Tests / Fixtures

Files under:

```text
tests/
test/
fixtures/
testdata/
```

may intentionally contain different configurations.

Do not automatically treat them as production configuration.

---

## 5. Generated Artifacts

Files under locations such as:

```text
build/
dist/
generated/
out/
target/
```

should normally be ignored or strongly deprioritized for primary configuration analysis.

---

## 6. Multi-stage Dockerfiles

Example:

```dockerfile
FROM node:22 AS frontend
FROM python:3.12 AS backend
```

These are different stages.

Do not report them as conflicting runtime versions.

Preserve each stage as evidence.

---

## 7. Monorepo / Subprojects

Example:

```text
frontend/package.json
backend/pyproject.toml
legacy-admin/package.json
```

Different subprojects may legitimately use different technologies or versions.

Radar should preserve subproject context.

Do not automatically merge unrelated subproject facts into one conflict.

---

## 8. Real Version Drift

False-positive protection must NOT suppress real findings.

Example:

```text
root pyproject.toml:
requires-python = ">=3.12"

main CI workflow:
python-version: "3.11"
```

with no version matrix and no special test context.

Radar SHOULD still report a version inconsistency.

---

# Scope Detection

Introduce a small deterministic path classifier.

Example idea:

```text
src/
root config
→ project

.github/workflows/
→ ci

tests/
fixtures/
→ test

examples/
docs/
→ example/documentation

vendor/
third_party/
→ vendor

build/
dist/
generated/
→ generated
```

Do not make scope detection dependent on AI.

Keep it easy to test.

---

# Intentional Variation

Radar should explicitly recognize some intentional variation signals.

Initial examples:

```text
GitHub Actions strategy.matrix

multi-stage Docker builds

separate monorepo subprojects
```

These should not generate conflicts unless there is additional evidence that they represent an actual problem.

---

# Evidence

Do not remove existing evidence behavior.

Context should enrich evidence-backed facts, not replace them.

Where practical, improve evidence quality by including:

```text
file
line
snippet
reason
scope/context
```

Do not require perfect line numbers for every parser if the implementation becomes unnecessarily complex.

---

# Regression Test Fixtures

Create deterministic test cases for false-positive protection.

At minimum cover:

```text
true-python-drift
python-ci-matrix
example-old-version
vendor-project
test-fixture-version
multi-stage-docker
monorepo
generated-files
```

Each case must have a known expected result.

Examples:

```text
python-ci-matrix
expected version_inconsistency findings: 0
```

```text
true-python-drift
expected version_inconsistency findings: 1
```

---

# Quality Metrics

Tests should distinguish:

```text
true positives
false positives
false negatives
```

At minimum, keep explicit expected findings in tests.

If practical, produce a simple summary such as:

```text
Expected findings: 8
Correct findings: 8
Unexpected findings: 0
Missed findings: 0
```

Do not build a large analytics framework.

---

# API Compatibility

Do not break existing `/scan` output.

Existing fields must remain usable.

Facts may gain optional context fields.

Findings may gain additional context if useful.

Preserve:

```text
entities
facts
findings
release metadata
```

---

# Do Not Implement

Do NOT implement in v0.3:

```text
AI code explanations
smart repository tree descriptions
deep source-code analysis
dependency graph
ownership inference
Git history analysis
Jira integration
Confluence integration
Excel integration
GitLab support
frontend
automatic fixes
upgrade recommendations
Company Software Graph
```

Those belong to later versions.

---

# Required Tests

Preserve all v0.1 and v0.2 tests.

Add tests for at least:

```text
CI Python version matrix does not produce false positive

CI Node version matrix does not produce false positive

real Python drift is still detected

example subdirectory does not define main project runtime

vendor configuration does not define main project runtime

test fixture does not create main project conflict

generated files are ignored or deprioritized

multi-stage Docker does not create false conflict

monorepo subprojects remain separated

malformed context data does not crash scan
```

---

# Definition of Done

Radar Core v0.3 is complete when:

* all v0.1 tests still pass,
* all v0.2 tests still pass,
* the current CI matrix false positive is fixed,
* facts contain enough context to avoid blind comparisons,
* common weak scopes are classified,
* intentional CI matrices are recognized,
* monorepo/subproject context is preserved,
* vendor/example/test/generated files do not incorrectly define the main project,
* true version drift is still detected,
* false-positive regression tests pass,
* `/health` works,
* `/scan` works on a real public repository,
* `/scan` works correctly on the controlled `radar-test` repository.

This milestone was implemented and verified.

---

# Expected Agent Workflow

1. Read this file.
2. Inspect the current v0.2 implementation.
3. Identify where findings currently lose context.
4. Make the smallest architectural changes necessary.
5. Add context/scope handling.
6. Fix the current CI matrix false positive.
7. Add regression tests.
8. Run the complete test suite.
9. Verify `/health`.
10. Verify `/scan`.
11. Update this document with the actual implementation and mark it `COMPLETED`.
12. Stop.

Do not start v0.4.

---

# v0.3 Summary

Radar Core v0.3 moves the scanner from:

```text
I found two different values.
Therefore there is a problem.
```

to:

```text
I found two different values.

I understand where they came from.

I understand what context they belong to.

I only report a problem when those values are actually expected to agree.
```

This is a critical trust milestone for Radar.

## Actual implementation

The completed v0.3 implementation adds context to fact generation and filters findings by scope and source type:

* `scope` is now classified as `project`, `ci`, `test`, `example`, `vendor`, `subproject`, or `generated`
* `source_type` is now classified as `manifest`, `build_config`, `ci_config`, or `test_matrix`
* `environment` is tracked as `runtime`, `build`, or `test`
* CI matrix values are explicitly treated as compatibility testing, not as project drift
* weak or non-primary scopes are filtered out before inconsistency findings are produced
* real version drift still triggers `version_inconsistency` when the project requirement and CI runtime are genuinely mismatched

## Tests and verification

Verified with:

```bash
cd /var/fpwork/futkowsk/radar && .venv/bin/python -m pytest -q backend/tests
```

Result:

```text
29 passed in 0.08s
```

Also verified with:

```bash
curl -sS http://localhost:8000/health
curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://localhost:8000/scan -H 'Content-Type: application/json' -d '{"url":"https://github.com/docker/compose"}'
```

Observed result:

* `/health` returned `{"status":"ok"}`
* `/scan` returned HTTP status 200

## Limitations

* This remains deterministic and conservative; it does not attempt deep semantic level matching
* Scope classification is intentionally simple and testable rather than exhaustive
* The project still uses the same GitHub-only scanner scope defined in earlier milestones

Do not start v0.4.
