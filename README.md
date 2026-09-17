# RADAR

## Start Here

Radar is a deterministic, evidence-backed repository analysis service. The
current architecture and developer workflow are documented in
[docs/architecture.md](docs/architecture.md) and
[docs/development.md](docs/development.md).

```bash
make setup
make verify-env
make check
make run
```

Run `make smoke` in a second terminal after the API starts. Testing profiles,
validation reports, and the CI contract are described in
[docs/testing.md](docs/testing.md), [docs/validation-corpus.md](docs/validation-corpus.md),
and [docs/ci.md](docs/ci.md).

## Project Purpose

Radar is a software intelligence platform.

Its long-term goal is to build a live, evidence-backed model of a company's technical environment.

Radar should help users understand:

* what repositories exist,
* what each repository does,
* what technologies it uses,
* how repositories and components depend on each other,
* who owns or works on them,
* what is currently happening around them,
* what they support,
* what is legacy,
* where documentation exists,
* which information across the company is inconsistent or outdated.

Future data sources may include:

* GitHub
* GitLab
* Bitbucket
* Jira
* Confluence
* Excel / CSV
* Jenkins
* GitHub Actions
* GitLab CI
* Slack
* Microsoft Teams
* internal documentation
* training materials

However, the current milestone is intentionally much smaller.

---

# Current Goal

The current goal is:

## RADAR CORE v0.1

Build a reliable repository scanner.

The scanner should inspect a repository and produce structured, evidence-backed facts about it.

Do NOT attempt to build the full company intelligence platform yet.

---

# Core Principle

Radar must not guess.

Every important statement should be based on evidence.

The basic model should be:

```text
FACT
+
EVIDENCE
+
CONFIDENCE
```

Example:

```text
Fact:
Repository uses CMake

Confidence:
1.0

Evidence:
CMakeLists.txt exists
```

If information cannot be determined reliably:

```text
UNKNOWN
```

is better than hallucinating an answer.

---

# Precision Over Recall

False positives are dangerous.

Radar should prefer:

```text
fewer findings
+
higher confidence
```

over:

```text
many findings
+
many incorrect assumptions
```

General rule:

> It is better to miss an uncertain fact than repeatedly show users incorrect information.

Possible confidence interpretation:

```text
1.00
Deterministic evidence.

0.90 - 0.99
Extremely strong evidence.

0.70 - 0.89
Probable, but may require review.

Below 0.70
Do not expose as an established fact unless clearly marked as uncertain.
```

This system may evolve later.

---

# First Instruction For The AI Agent

Before modifying any code:

## Inspect the entire repository.

Understand:

* current directory structure,
* FastAPI application,
* existing `/scan` endpoint,
* existing GitHub integration,
* existing database,
* existing SQLite usage,
* existing release scanning,
* Docker setup,
* Python dependencies,
* models,
* services,
* repository sources,
* existing tests.

Do NOT immediately rewrite the project.

Do NOT delete existing functionality.

Existing release scanning functionality may later become another Radar data source.

---

# Current Architecture Direction

Radar Core should not depend directly on GitHub.

Preferred architecture:

```text
GitHub
   \
GitLab
     \
Local  ---> RepositorySnapshot ---> Radar Core ---> Facts / Entities
     /
Other
```

GitHub is a source.

Radar Core is the analysis engine.

The analysis engine should eventually work with:

* GitHub repositories,
* GitLab repositories,
* local repositories,
* enterprise repositories,
* other repository providers.

---

# Repository Snapshot

Consider introducing an abstraction such as:

```text
RepositorySnapshot
```

It may eventually contain:

```text
repository metadata
repository identifier
source
branch
commit SHA
file tree
selected file contents
```

Do not over-engineer it.

The goal is simply to prevent extractors from depending directly on GitHub.

---

# Core Data Model

Radar Core should introduce at least the following concepts.

---

## Entity

An Entity represents something that exists.

Possible future entity types:

```text
repository
technology
build_system
runtime
container
ci
component
dependency
person
team
system
product
work_item
document
pipeline
release
```

For Radar Core v0.1 only implement what is currently required.

Suggested initial model:

```python
class Entity(BaseModel):
    type: str
    name: str
    identifier: str | None = None
```

Keep it simple.

---

## Evidence

Evidence explains why Radar believes something is true.

Suggested model:

```python
class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str | None = None
    reason: str
```

Example:

```json
{
  "file": "CMakeLists.txt",
  "line": null,
  "snippet": null,
  "reason": "CMakeLists.txt exists in repository"
}
```

---

## Fact

A Fact represents a structured observation.

Suggested model:

```python
from typing import Any

class Fact(BaseModel):
    type: str
    subject: str
    value: Any
    confidence: float
    extractor: str
    evidence: list[Evidence]
```

Example:

```json
{
  "type": "technology_detected",
  "subject": "CMake",
  "value": true,
  "confidence": 1.0,
  "extractor": "file_presence",
  "evidence": [
    {
      "file": "CMakeLists.txt",
      "line": null,
      "snippet": null,
      "reason": "CMakeLists.txt exists in repository"
    }
  ]
}
```

---

# Extractor Architecture

Repository analysis should be modular.

Preferred structure:

```text
app/
  extractors/
    technologies.py
    build_system.py
    ci.py
    dependencies.py
    ownership.py
```

Not all modules need to exist immediately.

Each extractor should approximately follow:

```text
INPUT

RepositorySnapshot
or repository files

        ↓

EXTRACTOR

        ↓

OUTPUT

Entities
Facts
Relations later
```

Extractors should NOT:

* depend on FastAPI,
* directly build HTTP responses,
* contain frontend logic,
* directly call GitHub APIs,
* write unrelated data to the database,
* use AI where deterministic parsing is sufficient.

---

# Current Scanner Flow

The intended scanning architecture is:

```text
Repository URL
      ↓
Repository Source
      ↓
Repository Tree
      ↓
RepositorySnapshot
      ↓
Extractors
      ↓
Facts
Entities
      ↓
API Response
```

Later:

```text
Facts
Entities
Relations
      ↓
Company Software Graph
```

---

# Repository Tree

Radar should first retrieve the repository file tree.

Example:

```text
CMakeLists.txt
Dockerfile
Jenkinsfile
README.md
src/main.cpp
src/Dispatcher.cpp
include/Dispatcher.hpp
meta/recipes/lim.bb
.github/workflows/build.yml
```

Do not download every file immediately.

First:

1. retrieve file paths,
2. classify important files,
3. download only files needed for deeper analysis.

This is important for:

* performance,
* API limits,
* large enterprise repositories,
* future scanning of hundreds of repositories.

---

# Important Files

Radar should eventually prioritize files such as:

```text
README
README.md

CMakeLists.txt

Dockerfile

docker-compose.yml
docker-compose.yaml
compose.yml
compose.yaml

Jenkinsfile

package.json

pyproject.toml
requirements.txt
setup.py
setup.cfg
Pipfile

CODEOWNERS

.github/workflows/*.yml
.github/workflows/*.yaml

*.bb
*.bbappend
*.bbclass
conf/layer.conf

pom.xml

build.gradle
build.gradle.kts

Makefile
```

For v0.1 only read file contents when actually necessary.

---

# Initial Technology Detection

Radar Core v0.1 should detect technologies deterministically.

---

## CMake

Strong evidence:

```text
CMakeLists.txt
```

Expected result:

```text
CMake
type: build_system
confidence: 1.0
```

---

## Docker

Strong evidence:

```text
Dockerfile
```

Expected result:

```text
Docker
type: container
confidence: 1.0
```

---

## Docker Compose

Evidence:

```text
docker-compose.yml
docker-compose.yaml
compose.yml
compose.yaml
```

Expected result:

```text
Docker Compose
type: container
```

---

## Python

Evidence may include:

```text
pyproject.toml
requirements.txt
setup.py
setup.cfg
Pipfile
```

Do NOT claim a Python version unless an explicit version can be detected.

---

## Node.js

Strong evidence:

```text
package.json
```

Do NOT claim a Node version unless an explicit version can be detected.

---

## Jenkins

Strong evidence:

```text
Jenkinsfile
```

Expected result:

```text
Jenkins
type: ci
confidence: 1.0
```

---

## GitHub Actions

Strong evidence:

```text
.github/workflows/*.yml
.github/workflows/*.yaml
```

Expected result:

```text
GitHub Actions
type: ci
```

---

## Maven

Strong evidence:

```text
pom.xml
```

Expected result:

```text
Maven
type: build_system
```

---

## Gradle

Strong evidence:

```text
build.gradle
build.gradle.kts
```

Expected result:

```text
Gradle
type: build_system
```

---

## Yocto / BitBake

Strong evidence includes:

```text
*.bb
*.bbappend
*.bbclass
conf/layer.conf
```

For v0.1 only detect that Yocto / BitBake metadata exists.

Do NOT attempt deep Yocto analysis yet.

Expected result:

```text
Yocto / BitBake
type: build_system
```

---

# Deduplication

Do not return duplicate technology entities.

Bad:

```text
Python
Python
Python
Python
```

because the repository contains:

```text
requirements.txt
pyproject.toml
setup.py
Dockerfile
```

Instead return:

```text
Python
```

with multiple evidence entries.

Example:

```json
{
  "type": "technology_detected",
  "subject": "Python",
  "value": true,
  "confidence": 1.0,
  "evidence": [
    {
      "file": "pyproject.toml",
      "reason": "Python project configuration detected"
    },
    {
      "file": "requirements.txt",
      "reason": "Python dependency file detected"
    }
  ]
}
```

---

# False Positive Protection

Radar must consider file location.

Example:

```text
docs/examples/package.json
```

should NOT automatically mean:

```text
This repository is primarily a Node.js project.
```

Possible low-confidence or scoped locations include:

```text
examples/
example/
docs/
test/
tests/
fixtures/
testdata/
vendor/
third_party/
samples/
demo/
```

For v0.1:

* preserve the evidence,
* preserve the exact path,
* reduce confidence if appropriate,
* avoid claiming the repository's main technology from weak evidence.

Future Radar versions may classify scopes such as:

```text
production
development
tests
examples
legacy
vendor
CI
documentation
```

The current architecture should not make this impossible later.

---

# Current API Goal

Extend the existing `/scan` flow.

Do not create an incompatible parallel system without a strong reason.

Example desired response:

```json
{
  "repository": "owner/project",
  "files_scanned": 428,
  "entities": [
    {
      "type": "build_system",
      "name": "CMake",
      "identifier": "cmake"
    },
    {
      "type": "container",
      "name": "Docker",
      "identifier": "docker"
    },
    {
      "type": "ci",
      "name": "Jenkins",
      "identifier": "jenkins"
    }
  ],
  "facts": [
    {
      "type": "technology_detected",
      "subject": "CMake",
      "value": true,
      "confidence": 1.0,
      "extractor": "file_presence",
      "evidence": [
        {
          "file": "CMakeLists.txt",
          "line": null,
          "snippet": null,
          "reason": "CMakeLists.txt exists in repository"
        }
      ]
    }
  ]
}
```

Existing release information may remain in the response if already implemented.

Do not delete working release functionality.

---

# Tests Required

Add tests for at least:

```text
CMake detection

Docker detection

Docker Compose detection

Python detection

Node.js detection

Jenkins detection

GitHub Actions detection

Maven detection

Gradle detection

Yocto / BitBake detection

technology deduplication

repository containing no known technologies
```

Also create false-positive tests.

Example:

```text
docs/examples/package.json
```

should not automatically produce a high-confidence claim that the entire repository is a Node.js application.

---

# Validation

After implementation:

Run all existing tests.

Run all new tests.

Start the application.

Verify:

```bash
curl http://localhost:8000/health
```

Then test:

```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/docker/compose"}'
```

Do not claim that implementation works unless the actual endpoint has been tested.

---

# AI Usage Rules

AI is NOT the source of truth.

Preferred future architecture:

```text
deterministic scanners
+
parsers
+
Git metadata
+
CI metadata
+
Jira
+
Confluence
+
other verified sources
        ↓
structured facts
        ↓
AI
        ↓
human-readable explanation
```

Bad architecture:

```text
entire repository
      ↓
LLM
      ↓
"this probably does X"
```

AI may later help with:

* explaining repositories,
* explaining folders,
* summarizing components,
* answering natural-language questions,
* onboarding,
* describing architecture,
* interpreting verified facts,
* translating technical information for non-technical users.

AI must not silently invent company facts.

---

# Future Product Vision

Radar should eventually build a:

## Company Software Graph

Possible entities:

```text
Person

Team

Product

Project

System

Component

Repository

File

Technology

Dependency

WorkItem

Feature

Change

Release

Document

Pipeline
```

Possible relationships:

```text
Person WORKS_ON Component

Person CONTRIBUTED_TO Repository

Team OWNS Component

Team SUPPORTS System

Product CONTAINS System

System CONTAINS Component

Component IMPLEMENTED_BY Repository

Component DEPENDS_ON Component

Repository USES Technology

Repository BUILT_BY Pipeline

JiraIssue IMPLEMENTS Feature

PullRequest CHANGES Component

Document DESCRIBES Component
```

Do NOT implement all of this now.

This exists only to guide current architecture.

---

# Future Integrations

Radar may eventually connect:

```text
GitHub
GitLab
Bitbucket

Jira

Confluence

Excel
CSV

Jenkins

GitHub Actions

GitLab CI

Slack

Microsoft Teams

internal documentation

training videos
```

These sources should contribute to the same company model.

---

# Future User Questions

Radar should eventually answer questions such as:

```text
What is LIM?

What does this repository do?

How does LIM communicate with SICPLUS?

Who owns this component?

Who manages JAPCO Jenkins?

Which team should I contact?

Who uses this repository?

Who are our internal customers?

Who knows this component best?

Which repositories use Poky 6?

What still supports Poky 5?

Where is authentication implemented?

How is this repository built?

What changed this week?

Which documentation is outdated?

Which systems depend on this component?

What happens if this component changes?
```

These future questions should influence architecture.

They should NOT increase the current implementation scope unnecessarily.

---

# Future Support Information

Radar should eventually understand information such as:

```text
SUPPORTED

LEGACY

DEPRECATED

UNSUPPORTED

UNKNOWN
```

Example:

```text
LIM

Poky 6
SUPPORTED

Poky 5
LEGACY

FSM3
SUPPORTED

FSM2
DEPRECATED
```

Support information should be evidence-backed.

Radar should not claim something is supported simply because an AI model thinks it probably is.

---

# Future Contradiction Detection

One important future feature is detecting inconsistent company knowledge.

Example:

```text
Confluence:
Python 3.11

README:
Python 3.11

Dockerfile:
Python 3.12

CI:
Python 3.12
```

Radar could eventually report:

```text
KNOWLEDGE CONFLICT

Observed runtime:
Python 3.12

Documentation:
Python 3.11

Likely outdated:
README
Confluence
```

This feature is NOT part of v0.1.

Current architecture should simply preserve evidence well enough to support it later.

---

# Future Code Understanding

Radar should eventually provide a smart repository tree.

Example:

```text
LIM/
│
├── src/
│   └── Main implementation
│
├── tests/
│   └── Tests
│
├── cmake/
│   └── Build helpers
│
├── CMakeLists.txt
│   └── Main CMake configuration
│
├── lim.bb
│   └── Yocto recipe
│
└── Jenkinsfile
    └── CI pipeline
```

Future users may click:

```text
src/dispatcher/
```

and receive:

```text
Handles communication between LIM and SICPLUS.
```

Such explanations should eventually be based on code analysis plus evidence.

Do NOT implement deep source-code understanding during v0.1.

---

# Future People Understanding

Git history may later allow Radar to infer:

```text
active contributors

likely maintainers

knowledge areas

ownership candidates
```

Future external data may add:

```text
Jira assignments

team membership

CODEOWNERS

Confluence ownership

CI ownership
```

Radar should not generate simplistic employee productivity scores.

The goal is understanding:

```text
who works on what

who knows what

who owns what
```

not:

```text
employee score = 73/100
```

---

# Future Company Search

A future Radar interface may provide:

```text
Search your company...
```

Users could search:

```text
LIM

SICPLUS

@John Smith

Team Platform

JAPCO Jenkins

Poky 6

Authentication

Payments
```

Radar should return a unified entity page with:

```text
What is it?

What does it do?

Who owns it?

Who uses it?

What does it depend on?

What supports it?

What is happening now?

Where is the code?

Where is the documentation?

Who should I contact?
```

---

# Main Product Philosophy

Radar should eventually connect:

```text
CODE
+
PEOPLE
+
WORK
+
DOCUMENTATION
+
INFRASTRUCTURE
```

into one understandable model.

Radar should become:

> One place to understand the technical side of a software company.

But the entire product depends on one thing first:

# Radar must understand repositories reliably.

---

# Current Agent Task

Perform the following steps IN ORDER.

---

## STEP 1 — Inspect

Inspect the existing repository.

Report:

```text
Current architecture

Directory structure

Existing endpoints

Existing models

Existing services

Existing GitHub integration

Database usage

Docker setup

Existing scan flow

Existing release flow

Existing tests

Technical debt relevant to this task
```

Do NOT modify files yet.

---

## STEP 2 — Propose

Propose the smallest clean implementation for Radar Core v0.1.

Explain:

```text
Files to create

Files to modify

Models to add

Extractor architecture

Repository tree retrieval

How existing /scan will change

How existing release functionality will be preserved
```

Do not over-engineer.

---

## STEP 3 — Implement

Implement Radar Core v0.1.

At minimum:

```text
Entity

Fact

Evidence

Repository tree retrieval

Technology extractor

Deduplication

Basic false-positive protection

Extended /scan response
```

Detect at minimum:

```text
CMake

Docker

Docker Compose

Python

Node.js

Jenkins

GitHub Actions

Maven

Gradle

Yocto / BitBake
```

---

## STEP 4 — Test

Add automated tests.

Test:

```text
technology detection

deduplication

empty repository

false-positive cases
```

Run the full test suite.

---

## STEP 5 — Verify

Start the application.

Verify:

```bash
curl http://localhost:8000/health
```

Then:

```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"url":"https://github.com/docker/compose"}'
```

Inspect the real response.

---

## STEP 6 — Report

After implementation provide:

```text
1. Summary

2. Files created

3. Files modified

4. Architecture decisions

5. Tests added

6. Test results

7. Example /scan output

8. Known limitations

9. Recommended next step
```

Do NOT automatically start implementing the next major milestone.

Stop after Radar Core v0.1 is working and verified.

---

# Agent Rules

## ALWAYS

1. Read the existing repository first.
2. Preserve working functionality.
3. Make small coherent changes.
4. Prefer deterministic analysis.
5. Store evidence.
6. Keep modules testable.
7. Avoid unnecessary dependencies.
8. Test every implementation.
9. Verify real API behavior.
10. Explain important architectural decisions.
11. Keep future GitLab/local-repository support possible.
12. Prefer UNKNOWN over guessing.

---

## NEVER

1. Rewrite the entire project without a strong reason.
2. Delete working release functionality.
3. Add LLM calls where parsing is enough.
4. Invent repository facts.
5. Hardcode one specific repository.
6. Couple Radar Core permanently to GitHub.
7. Build frontend before Radar Core works.
8. Implement Jira integration yet.
9. Implement Confluence integration yet.
10. Implement employee scoring.
11. Implement the entire Company Graph now.
12. Hide errors.
13. Claim tests passed without running them.
14. Claim `/scan` works without verifying it.

---

# Definition Of Done — Radar Core v0.1

Radar Core v0.1 is complete when:

* existing backend still runs,
* existing useful functionality still works,
* `/health` works,
* `/scan` works,
* GitHub repository tree can be retrieved,
* supported technologies are detected,
* findings contain evidence,
* duplicate entities are merged,
* obvious false positives are reduced,
* automated tests exist,
* tests pass,
* one real public repository has been scanned successfully,
* no LLM is required for basic detection.

Do not continue to a larger milestone until these conditions are satisfied.
