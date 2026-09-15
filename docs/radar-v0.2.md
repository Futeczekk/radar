# Radar Core v0.2

## Status

COMPLETED

## Previous version

Radar Core v0.1 is complete.

v0.1 can:

* scan a GitHub repository tree,
* detect basic technologies,
* return `Entity`, `Fact`, and `Evidence`,
* deduplicate detections,
* reduce obvious false positives,
* preserve existing release scanning,
* expose results through `/scan`.

This v0.2 extends that implementation without replacing it.

---

# Goal

Radar Core v0.2 should answer:

> How is this repository configured?

v0.1 detects that a technology exists.

v0.2 should extract important configuration from selected files.

Example:

```text
v0.1

Python detected
Docker detected
CMake detected
GitHub Actions detected
```

v0.2:

```text
Python requirement: >=3.12

Docker base image:
python:3.12-slim

CMake minimum version:
3.28

Project name:
radar

GitHub Actions Python version:
3.11
```

---

# Main principle

All extracted information must remain evidence-backed.

Every fact should include:

```text
value
confidence
evidence
extractor
```

Prefer deterministic parsing.

Do not use LLMs in v0.2.

---

# Required parsers

Implement parsing for the following files.

## CMakeLists.txt

Extract if present:

```text
cmake_minimum_required(...)
project(...)
```

Example:

```cmake
cmake_minimum_required(VERSION 3.28)

project(Radar)
```

Expected facts:

```text
cmake.minimum_version = 3.28
project.name = Radar
```

---

## Dockerfile

Extract:

```text
FROM
```

Support multiple build stages.

Example:

```dockerfile
FROM python:3.12-slim AS builder
FROM python:3.12-slim
```

Expected facts:

```text
docker.base_image = python:3.12-slim
```

If multiple different images exist, preserve all relevant evidence.

---

## pyproject.toml

Extract if present:

```text
requires-python
```

Example:

```toml
requires-python = ">=3.12"
```

Expected fact:

```text
python.required_version = >=3.12
```

Do not guess Python versions from dependencies.

---

## package.json

Extract if present:

```text
engines.node
```

Example:

```json
{
  "engines": {
    "node": ">=22"
  }
}
```

Expected fact:

```text
node.required_version = >=22
```

---

## GitHub Actions

Inspect:

```text
.github/workflows/*.yml
.github/workflows/*.yaml
```

Extract versions from common actions such as:

```text
actions/setup-python
actions/setup-node
```

Example:

```yaml
uses: actions/setup-python@v5

with:
  python-version: "3.11"
```

Expected fact:

```text
ci.python_version = 3.11
```

Also support Node where practical:

```text
ci.node_version
```

Do not attempt to understand every possible GitHub Actions syntax in v0.2.

Support common deterministic cases only.

---

# RepositorySnapshot

Introduce a small `RepositorySnapshot` abstraction if it fits the current architecture.

It may contain:

```text
repository metadata
file tree
selected file contents
branch
commit SHA
source
```

Keep it minimal.

The goal is to make extractors independent from GitHub-specific networking.

Do not over-engineer it.

---

# Important file retrieval

v0.1 already retrieves repository paths.

v0.2 should fetch file contents only for important files.

Initially prioritize:

```text
CMakeLists.txt
Dockerfile
pyproject.toml
package.json
.github/workflows/*.yml
.github/workflows/*.yaml
```

Do not download the entire repository.

---

# Fact types

Use structured fact names.

Examples:

```text
cmake.minimum_version
project.name

docker.base_image

python.required_version

node.required_version

ci.python_version
ci.node_version
```

Keep names consistent.

---

# Evidence

Every parsed fact must include exact source evidence.

Example:

```json
{
  "type": "python.required_version",
  "subject": "Python",
  "value": ">=3.12",
  "confidence": 1.0,
  "extractor": "pyproject",
  "evidence": [
    {
      "file": "pyproject.toml",
      "line": 12,
      "snippet": "requires-python = \">=3.12\"",
      "reason": "Python requirement declared in pyproject.toml"
    }
  ]
}
```

Line numbers are preferred when practical.

---

# First cross-file analysis

After extracting configuration facts, add basic deterministic comparison.

The first useful finding should be version inconsistency.

Example:

```text
pyproject.toml
Python >=3.12

GitHub Actions
Python 3.11
```

Radar should identify a possible inconsistency.

Suggested finding:

```text
type:
version_inconsistency

technology:
Python

expected:
>=3.12

observed:
3.11

sources:
pyproject.toml
.github/workflows/test.yml
```

Only produce this finding when the contradiction is deterministic enough.

Do not attempt advanced semantic version reasoning beyond simple useful cases.

Avoid false positives.

---

# False-positive rules

Do not treat all version differences as errors.

Examples that may be intentional:

```text
CI version matrix

python-version:
  - 3.10
  - 3.11
  - 3.12
```

This is testing multiple supported versions, not necessarily drift.

Do not report it as an inconsistency without enough evidence.

Similarly:

```text
examples/
tests/
fixtures/
vendor/
third_party/
```

should continue to be treated carefully.

Precision is more important than coverage.

---

# API response

Extend the existing `/scan` response.

Do not remove existing fields.

Add extracted configuration facts and findings.

Example:

```json
{
  "repository": "owner/project",
  "files_scanned": 428,

  "entities": [],

  "facts": [
    {
      "type": "python.required_version",
      "subject": "Python",
      "value": ">=3.12"
    },

    {
      "type": "ci.python_version",
      "subject": "Python",
      "value": "3.11"
    }
  ],

  "findings": [
    {
      "type": "version_inconsistency",
      "technology": "Python"
    }
  ]
}
```

Use the project's existing models and conventions where possible.

---

# Tests

Add tests for:

```text
CMake minimum version parsing

CMake project name parsing

Docker base image parsing

multi-stage Dockerfile

pyproject Python version parsing

package.json Node version parsing

GitHub Actions Python version parsing

GitHub Actions Node version parsing

missing values

malformed files

version inconsistency detection

CI version matrix should not create false positive
```

Preserve all v0.1 tests.

---

# Do not implement

Do NOT implement in v0.2:

```text
AI repository explanations

smart folder descriptions

deep source code understanding

dependency graph

Git history analysis

ownership inference

Jira

Confluence

Excel

Jenkins API integration

GitLab support

Company Graph

frontend work

automatic fixes

upgrade recommendations
```

Those belong to later milestones.

---

# Definition of Done

Radar Core v0.2 is complete when:

* v0.1 still works,
* important configuration files can be fetched,
* CMake configuration can be parsed,
* Docker base images can be parsed,
* Python requirements can be parsed,
* Node requirements can be parsed,
* GitHub Actions runtime versions can be parsed,
* facts contain evidence,
* basic cross-file version inconsistencies can be detected,
* obvious version-matrix false positives are avoided,
* automated tests pass,
* `/health` works,
* `/scan` works on at least one real public repository.

---

# Implemented v0.2 changes

The actual implementation adds deterministic configuration parsing to the existing `/scan` flow without removing v0.1 behavior.

Implemented components:

* repository file selection for important configuration files only
* GitHub raw-content fetching for selected config files
* CMake parsing for `cmake_minimum_required` and `project(...)`
* Dockerfile parsing for `FROM` base images, including multi-stage Dockerfiles
* `pyproject.toml` parsing for `requires-python`
* `package.json` parsing for `engines.node`
* GitHub Actions parsing for `actions/setup-python` and `actions/setup-node`
* evidence-backed `Fact` generation with structured types such as:
  * `cmake.minimum_version`
  * `project.name`
  * `docker.base_image`
  * `python.required_version`
  * `node.required_version`
  * `ci.python_version`
  * `ci.node_version`
* basic deterministic version inconsistency detection as `version_inconsistency`
* safeguards so CI version matrices are not treated as false-positive drift
* `/scan` response now includes both technology facts and configuration facts, as well as `findings`

# Actual test results

Verified with:

```bash
cd /var/fpwork/futkowsk/radar && .venv/bin/python -m pytest -q backend/tests
```

Result:

```text
25 passed in 0.07s
```

# API verification

Verified with:

```bash
curl -sS http://localhost:8000/health
curl -sS -w '\nHTTP_STATUS=%{http_code}\n' -X POST http://localhost:8000/scan -H 'Content-Type: application/json' -d '{"url":"https://github.com/docker/compose"}'
```

Observed result:

* `/health` returned `{"status":"ok"}`
* `/scan` returned `HTTP_STATUS=200`
* the response included repository metadata, technology facts, configuration facts, and release data while preserving v0.1 fields

# Limitations

* this is still deterministic parsing and not deep semantic repository understanding
* only the important config files are fetched; no broad repository content scanning yet
* version inconsistency detection is intentionally conservative and avoids noisy false positives
* GitLab/local repository support is still outside v0.2 scope
* no advanced dependency graph or ownership inference is included

# Definition of Done

Radar Core v0.2 is implemented and verified as complete for the scoped milestone.

Do not automatically continue to v0.3.
