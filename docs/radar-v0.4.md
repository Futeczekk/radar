# Radar Core v0.4

## Status

COMPLETED

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED
Radar Core v0.3 — COMPLETED

v0.1 answers:

> What exists in this repository?

v0.2 answers:

> How is this repository configured?

v0.3 answers:

> Can Radar trust and correctly interpret the facts it finds?

v0.4 should answer:

> What is where in this repository?

---

# Goal

Radar should create a deterministic, evidence-backed map of an unfamiliar repository.

The purpose of v0.4 is to help a developer quickly understand:

* what the major directories are,
* what role they probably serve,
* where important configuration lives,
* where likely application entry points are,
* where tests, documentation, CI, build files, scripts, and infrastructure are located.

Radar must NOT attempt deep code understanding yet.

---

# Core Principle

Repository structure must be inferred conservatively.

Radar should prefer:

```text
UNKNOWN
```

over inventing a role.

Every detected role should have:

* path
* role
* confidence
* evidence

Example:

```json
{
  "path": "backend/",
  "role": "backend",
  "confidence": 0.95,
  "evidence": [
    {
      "file": "backend/app/main.py",
      "reason": "Backend directory contains a likely Python application entry point"
    }
  ]
}
```

---

# Repository Map

Add a repository structure representation.

Keep the implementation minimal.

Suggested conceptual structure:

```text
RepositoryMap

directories
important_files
entry_points
```

Do not build a complete software graph.

---

# Directory Analysis

Analyze repository directories and assign roles when there is enough evidence.

Supported initial roles may include:

```text
source
backend
frontend
api
tests
documentation
scripts
configuration
infrastructure
build
examples
vendor
generated
unknown
```

The taxonomy should stay small and deterministic.

---

# Directory Role Signals

Use path names as one signal, but do not rely only on naming.

Examples:

```text
src/
→ source

backend/
server/
→ backend

frontend/
web/
ui/
→ frontend

api/
→ api

tests/
test/
→ tests

docs/
documentation/
→ documentation

scripts/
tools/
→ scripts

config/
configs/
→ configuration

infra/
infrastructure/
terraform/
k8s/
helm/
→ infrastructure
```

Additional evidence from contained files may increase confidence.

Example:

```text
frontend/
  package.json
  src/
```

is stronger evidence for frontend than the directory name alone.

---

# Important File Detection

Identify important files already known by Radar and expose their structural role.

Examples:

```text
README.md
Dockerfile
docker-compose.yml
CMakeLists.txt
pyproject.toml
package.json
Jenkinsfile
Makefile
.github/workflows/*.yml
```

Possible roles:

```text
documentation
container_build
container_orchestration
build_configuration
project_manifest
ci_pipeline
build_script
```

Preserve existing v0.1-v0.3 facts.

Do not duplicate existing configuration parsing unnecessarily.

---

# Entry Point Detection

Detect likely application entry points using deterministic rules.

Initial examples:

## Python

```text
main.py
app.py
manage.py
__main__.py
```

## JavaScript / TypeScript

```text
index.js
index.ts
server.js
server.ts
main.js
main.ts
```

## C / C++

```text
main.c
main.cpp
```

## Java

```text
Application.java
Main.java
```

Detection must be conservative.

A filename alone may not always justify confidence 1.0.

Where practical, combine filename, location, and existing technology facts.

---

# Entry Point Context

Different entry points may exist for different purposes.

Examples:

```text
backend/app/main.py
frontend/src/main.ts
tools/importer/main.py
```

Do not collapse them into one repository-wide entry point.

Preserve their path and contextual scope.

---

# Important Directory Summary

For each important directory, expose a compact deterministic summary.

Example:

```json
{
  "path": "backend/",
  "role": "backend",
  "confidence": 0.95,
  "file_count": 42,
  "evidence": [
    {
      "file": "backend/app/main.py",
      "reason": "Contains likely Python application entry point"
    },
    {
      "file": "backend/pyproject.toml",
      "reason": "Contains Python project manifest"
    }
  ]
}
```

Do not generate natural-language AI summaries in v0.4.

---

# Repository Tree

Radar may expose a reduced repository tree.

The goal is NOT to return every file in a very large repository.

Prefer a useful structural view.

Example:

```text
backend/
  app/
  tests/
  pyproject.toml

frontend/
  src/
  package.json

.github/
  workflows/

Dockerfile
README.md
```

Generated, vendor, and irrelevant deep paths may be collapsed or excluded.

---

# Reuse v0.3 Context

The v0.3 path/context classifier should be reused where possible.

Do not introduce a second conflicting classification system.

Existing concepts such as:

```text
project
ci
test
example
vendor
subproject
generated
```

should remain compatible with v0.4 structure analysis.

---

# Confidence

Role detection should use conservative confidence.

Example guidance:

```text
0.95–1.0
strong deterministic evidence

0.75–0.94
multiple good structural signals

0.5–0.74
weak or naming-based evidence

below 0.5
prefer UNKNOWN or do not emit
```

Do not introduce complex scoring or machine learning.

---

# Evidence

Every structural claim should have evidence.

Good evidence examples:

```text
path name
manifest file
entry-point filename
CI/build/config file
technology fact already detected by Radar
```

Example:

```json
{
  "path": "frontend/",
  "role": "frontend",
  "confidence": 0.95,
  "evidence": [
    {
      "file": "frontend/package.json",
      "reason": "Node.js project manifest found inside frontend directory"
    }
  ]
}
```

---

# False Positive Protection

v0.4 must preserve the trust principles from v0.3.

Examples:

```text
examples/frontend/
```

must not automatically become the main frontend application.

```text
vendor/src/
```

must not become primary project source.

```text
tests/app.py
```

must not automatically become the primary application entry point.

```text
generated/main.cpp
```

must not become the repository entry point.

Scope and context must be respected.

---

# Monorepo Support

v0.4 should preserve separate structural regions in monorepos.

Example:

```text
apps/frontend/
apps/backend/
tools/migrator/
```

Radar should be able to represent multiple components or subprojects without merging them into one role.

Do not build dependency relationships between components yet.

That belongs to later versions.

---

# API

Extend the existing `/scan` response without breaking existing fields.

Possible new field:

```json
{
  "repository_map": {
    "directories": [],
    "important_files": [],
    "entry_points": []
  }
}
```

Exact internal structure may follow the existing codebase style.

Preserve:

```text
entities
facts
findings
release metadata
```

---

# Required Regression Cases

Add deterministic tests for at least:

```text
simple Python backend
simple Node frontend
backend + frontend repository
Python entry point
Node/TypeScript entry point
C/C++ entry point
test main.py not treated as primary entry point
example application not treated as primary application
vendor source ignored for primary structure
generated source ignored for primary structure
monorepo with multiple subprojects
unknown directory remains unknown
important build/config files detected
large/deep tree reduced to useful structural representation
```

Preserve all previous v0.1-v0.3 tests.

---

# Controlled Repository Test

Use or extend the controlled `Futii10/radar-test` repository when useful.

The expected structure should be deterministic.

Radar should identify at least:

```text
.github/workflows/
→ CI

CMakeLists.txt
→ build configuration

Dockerfile
→ container build

pyproject.toml
→ Python project manifest

package.json
→ Node project manifest
```

If additional source directories are added to the controlled repository, their expected roles should be known before scanning.

---

# Do Not Implement

Do NOT implement in v0.4:

```text
LLM-based repository summaries
AI code explanations
deep source-code understanding
function call graph
dependency graph
code flow analysis
Git history
ownership inference
CODEOWNERS analysis
Jira integration
Confluence integration
GitLab integration
frontend UI
automatic fixes
upgrade recommendations
Company Software Graph
```

These belong to later milestones.

---

# Definition of Done

Radar Core v0.4 is complete when:

* all v0.1 tests pass,
* all v0.2 tests pass,
* all v0.3 tests pass,
* repository directories can be analyzed,
* important directory roles can be identified conservatively,
* important files are classified,
* likely entry points can be detected,
* test/example/vendor/generated entry points do not become primary entry points,
* monorepo/subproject structure is preserved,
* structural claims contain evidence,
* confidence is conservative,
* unknown structures remain unknown rather than guessed,
* `/health` works,
* `/scan` works on a real public repository,
* `/scan` works correctly on the controlled `radar-test` repository.

---

# Expected Agent Workflow

1. Read this document.
2. Inspect the completed v0.3 implementation.
3. Reuse existing repository tree and context logic.
4. Design the smallest repository map representation that fits the current architecture.
5. Implement deterministic directory role detection.
6. Implement important file detection.
7. Implement conservative entry-point detection.
8. Preserve v0.3 scope/context behavior.
9. Add regression tests.
10. Run the full backend test suite.
11. Verify `/health`.
12. Verify `/scan` on at least one real public repository.
13. Verify `/scan` on the controlled `radar-test` repository.
14. Update this document with the actual implementation, limitations, and test results.
15. Mark v0.4 as `COMPLETED`.
16. Stop.

Do not start v0.5.

---

# Actual Implementation

The completed v0.4 implementation adds a deterministic repository structure map to the existing scan response without changing the v0.1-v0.3 behavior.

The implementation is intentionally conservative:

* directory roles are inferred from path names and a small amount of structure evidence,
* important files are surfaced when they match known project/build/CI/documentation roles,
* likely entry points are detected only from clear filenames and weak paths are excluded,
* test/example/vendor/generated paths are not promoted to primary repository entry points,
* monorepo regions remain separate when they live under distinct top-level component directories,
* all structural claims include evidence and conservative confidence values.

The repository map is returned as part of the existing `/scan` payload under:

```json
{
  "repository_map": {
    "directories": [],
    "important_files": [],
    "entry_points": []
  }
}
```

The implementation reuses the existing v0.3 scope-awareness, keeps the original fields (`entities`, `facts`, `findings`, release metadata) intact, and extends the response rather than replacing it.

## Limitations

This milestone remains deliberately narrow and deterministic:

* no deep code understanding,
* no dependency graph or call graph,
* no AI-generated repository summaries,
* no heuristics that guess beyond clear structural evidence,
* role detection is intentionally simple and testable.

## Verification

Verified with:

```bash
cd /var/fpwork/futkowsk/radar && .venv/bin/python -m pytest -q backend/tests
```

Result:

```text
40 passed in 0.15s
```

Also verified with live API checks:

```bash
curl -sS http://localhost:8000/health
curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://localhost:8000/scan -H 'Content-Type: application/json' -d '{"url":"https://github.com/docker/compose"}'
curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://localhost:8000/scan -H 'Content-Type: application/json' -d '{"url":"https://github.com/Futii10/radar-test"}'
```

Observed results:

* `/health` returned `{"status":"ok"}`
* public repo scan returned HTTP status 200
* controlled `Futii10/radar-test` scan returned HTTP status 200
* the repository map, important files, and entry points were included in the scan response for the controlled repository

---

# v0.4 Summary

Radar Core v0.4 moves Radar from:

```text
I know what technologies and configuration exist.
```

to:

```text
I can show you where the important parts of this repository are.
```

This is the first repository navigation milestone.

v0.4 is now marked COMPLETED.
