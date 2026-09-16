# Radar Core v0.6

## Status

COMPLETED

## Implementation Summary

Radar Core v0.6 adds a deterministic `component_graph` on top of the existing v0.4 repository map and v0.5 file relationship graph. The existing response fields remain unchanged and continue to be emitted alongside the new graph.

Each component includes:

* `id`, `name`, and a small deterministic `type` taxonomy
* `scope` preserving project, test, example, subproject, vendor, and generated context
* explicit one-component-per-file `files` membership
* confidence and evidence for directory roles, entry points, manifests, or root placement

The component detector uses directory structure as its strongest signal, gives secondary parent directories precedence over misleading child names, keeps weak directories as `unknown`, and recognizes conservative root/library and monorepo-style `apps/` and `packages/` components. When a root manifest and recognized root entry point directly delegate into exactly one project-scoped top-level `lib/` or `src/` directory, those files are merged into one root library component. Component relationships are derived only from existing v0.5 file relationships, deduplicated, and retain evidence pointing to the underlying source and target files.

No LLM or AI calls were added.

## Limitations

Component detection does not infer architecture from arbitrary names or graph topology. Files in weak or ambiguous directories may be assigned to an `unknown` component, and the current model allows one primary component per file. Root/library merging is intentionally limited to a single top-level `lib/` or `src/` directory with clear root manifest, entry-point, and direct delegation evidence; monorepo and secondary directories are not merged. Component relationships are emitted only when the existing deterministic file graph resolves a cross-component relationship.

## Verification

The complete backend regression suite passes:

* `63 passed in 0.18s`

Live API validation used a writable temporary SQLite path because `/data` is not writable in the local environment:

* `GET /health` returned HTTP `200` with `{"status":"ok"}`
* `POST /scan` on `Futii10/radar-test` returned HTTP `200` with project components including `backend`
* `POST /scan` on `expressjs/express` returned HTTP `200` with primary and secondary components
* `POST /scan` on `madler/zlib` returned HTTP `200`; `contrib` was retained as `scope: subproject` and was not merged into the primary project components

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED
Radar Core v0.3 — COMPLETED
Radar Core v0.4 — COMPLETED
Radar Core v0.5 — COMPLETED

v0.1 answers:

> What exists in this repository?

v0.2 answers:

> How is this repository configured?

v0.3 answers:

> Can Radar trust and correctly interpret the facts it finds?

v0.4 answers:

> What is where in this repository?

v0.5 answers:

> How are the important parts of this repository connected?

v0.6 should answer:

> What are the logical components of this system?

---

# Goal

Radar should move from a low-level file graph toward a higher-level system model.

Today Radar can see:

```text
backend/main.py
backend/api.py
backend/service.py
backend/database.py
```

and their relationships.

v0.6 should begin grouping repository files into logical components such as:

```text
Backend
API
Service Layer
Data Layer
Frontend
CLI
Library
Build System
Infrastructure
```

The goal is NOT perfect architectural understanding.

The goal is to create conservative, evidence-backed component candidates.

---

# Core Principle

Component detection must remain:

```text
deterministic first
evidence-backed
conservative
context-aware
```

Radar must not invent architecture.

If a component cannot be identified reliably:

```text
UNKNOWN
```

is acceptable.

Precision remains more important than recall.

---

# Component Model

Introduce a component representation.

Suggested shape:

```json
{
  "id": "backend",
  "name": "Backend",
  "type": "backend",
  "scope": "project",
  "confidence": 0.95,
  "files": [
    "backend/main.py",
    "backend/api.py",
    "backend/service.py"
  ],
  "evidence": [
    {
      "type": "directory_role",
      "value": "backend/"
    }
  ]
}
```

Exact model may follow the current project architecture.

A component should have at least:

```text
id
name
type
scope
confidence
files
evidence
```

---

# Initial Component Types

Keep the taxonomy small.

Suggested component types:

```text
backend
frontend
api
service
data
library
cli
configuration
build
infrastructure
test
example
subproject
unknown
```

Do not create dozens of highly specific architectural labels yet.

---

# Detection Signals

Component detection should combine existing evidence from previous milestones.

Potential signals include:

```text
directory role
important files
entry points
file types
repository graph relationships
manifest location
known framework/config files
scope/context
```

The strongest signal should usually be existing repository structure.

---

# Directory-Based Components

A directory with a strong known role may become a component candidate.

Examples:

```text
backend/
frontend/
api/
service/
services/
db/
database/
cli/
src/
```

Examples:

```text
backend/
→ backend component
```

```text
frontend/
→ frontend component
```

```text
services/payments/
→ service component candidate
```

Do not classify only from the directory name when context contradicts it.

---

# Root-Level Components

Repositories may not have clean top-level directories.

Example:

```text
index.js
lib/
package.json
```

Radar should still be able to represent a root application/library component when evidence supports it.

Example:

```text
Express Core
type: library
files:
index.js
lib/*
```

Do not require every component to map to exactly one directory.

---

# Relationship-Aware Detection

Reuse v0.5 graph relationships.

Example:

```text
main.py
→ api.py
→ service.py
→ database.py
```

These files may belong to separate logical components or grouped layers depending on structure.

The first implementation should remain conservative.

Do not invent architecture purely from graph topology.

Relationships should support classification, not replace deterministic structure evidence.

---

# Component Membership

Each file may belong to:

```text
one primary component
```

for the initial implementation.

Avoid overlapping component membership unless the existing architecture makes it unavoidable.

Do not build complex multi-membership logic in v0.6.

---

# Component Relationships

Where deterministic file relationships exist between components, create higher-level component edges.

Example:

```text
backend/main.py → backend/api.py
```

If:

```text
backend/main.py ∈ Backend
backend/api.py ∈ API
```

then Radar may derive:

```text
Backend → API
```

with evidence pointing back to the underlying file relationship.

Example:

```json
{
  "source": "backend",
  "target": "api",
  "type": "depends_on",
  "confidence": 1.0,
  "evidence": [
    {
      "source_file": "backend/main.py",
      "target_file": "backend/api.py",
      "relationship": "imports"
    }
  ]
}
```

Deduplicate component relationships.

---

# Primary vs Secondary Components

Preserve v0.3-v0.5 scope rules.

Examples:

```text
examples/demo/
→ example component
```

```text
tests/
→ test component
```

```text
contrib/
→ subproject component
```

These should remain separate from the primary project architecture.

Do not allow example/test/subproject code to dominate primary component detection.

---

# Monorepo Support

v0.6 should be conservative but aware of monorepos.

Example:

```text
apps/web/
apps/api/
packages/common/
```

Radar should not collapse everything into one component if there is strong evidence of separate subprojects.

Possible result:

```text
web
type: frontend

api
type: backend

common
type: library
```

Do not attempt full workspace understanding yet.

---

# Framework Signals

Known configuration files may strengthen classification.

Examples:

```text
package.json
pyproject.toml
CMakeLists.txt
Dockerfile
```

Framework-specific signals may be used only if already easy to identify.

Do NOT expand v0.6 into broad framework detection.

---

# Entry Points

Entry points discovered in v0.4 may strengthen component identity.

Example:

```text
backend/main.py
```

inside a backend directory may increase confidence that this directory represents an executable backend component.

Entry points should be evidence, not a mandatory requirement.

---

# Libraries

A repository or directory may represent a reusable library.

Potential signals:

```text
package manifest
public headers
library-style entry point
absence of application entry point
imported by other internal files
```

Keep detection conservative.

Do not infer library status from one weak signal.

---

# Component Confidence

Confidence should reflect evidence strength.

Example:

```text
backend/ directory
+
main.py
+
internal relationships
→ high confidence
```

Unknown or ambiguous directories should have lower confidence or remain unknown.

Do not assign high confidence to weak guesses.

---

# Evidence

Every component must explain why it exists.

Preferred evidence types:

```text
directory_role
entry_point
important_file
manifest
relationship
file_pattern
```

Example:

```json
{
  "type": "directory_role",
  "file": "backend/",
  "reason": "Directory classified as backend"
}
```

---

# Repository Component Graph

Extend `/scan` with:

```json
{
  "component_graph": {
    "components": [],
    "relationships": []
  }
}
```

Do not remove or replace:

```text
repository_map
repository_graph
```

The component graph is a higher-level view built on top of them.

---

# Controlled Repository Test

Use `Futii10/radar-test`.

Current structure:

```text
backend/
  __init__.py
  main.py
  api.py
  service.py
  database.py
```

A minimal acceptable v0.6 output could be:

```text
Backend
```

containing all backend files.

A stronger output may separate:

```text
API
Service
Data
```

but only if deterministic evidence supports this reliably.

Do not force architectural separation just because filenames happen to be:

```text
api.py
service.py
database.py
```

The purpose of the controlled test is to verify:

```text
component creation
membership
scope
evidence
component relationships
```

---

# Real Repository Validation

Validate on:

```text
expressjs/express
madler/zlib
```

Expected behavior:

### Express

Radar should identify a sensible primary Express component or small set of components around:

```text
index.js
lib/
```

Examples and tests should remain secondary.

### zlib

Main source should remain distinct from:

```text
contrib/
examples/
```

Do not collapse `contrib` into the main component.

---

# AI Fallback — NOT YET ACTIVE

v0.6 should prepare for future AI-assisted classification, but AI should not be required for core component detection.

Important architectural distinction:

```text
DETERMINISTIC
INFERRED
UNKNOWN
```

The current milestone should primarily emit:

```text
DETERMINISTIC
UNKNOWN
```

Do not call an LLM in the core v0.6 path.

However, structure the component model so that a future field such as:

```text
source_type: deterministic
```

can later support:

```text
source_type: ai_inference
```

without redesigning the entire model.

---

# Why AI Is Deferred

AI will later be useful for ambiguous structures such as:

```text
orion/
engine/
platform/
runtime/
```

where directory names alone are weak evidence.

Future flow:

```text
deterministic classification
        ↓
unknown / ambiguous
        ↓
AI fallback
        ↓
inferred component
```

But v0.6 should first measure how much can be classified reliably without AI.

---

# Unknown Metrics

If practical, expose enough information to later measure:

```text
files classified into components
files unclassified
directories classified
directories unknown
```

Do not build analytics infrastructure yet.

The goal is simply to make future evaluation of AI fallback possible.

---

# False Positive Protection

Component detection must preserve previous scope protections.

Examples:

```text
tests/api/
```

must not become the primary API component.

```text
examples/backend/
```

must not become the project's backend component.

```text
contrib/service/
```

must remain a subproject/secondary component.

Parent context takes precedence over misleading child directory names.

---

# Required Regression Cases

Add tests for at least:

```text
backend directory component
frontend directory component
test directory remains secondary
example directory remains secondary
contrib directory remains subproject
generated/vendor content excluded from primary components
component contains expected files
component scope preserved
root-level project component
monorepo-like separate app directories
component relationship derived from file relationship
duplicate component relationships deduplicated
unknown directory stays unknown when evidence is weak
```

Preserve all v0.1-v0.5 tests.

---

# API Compatibility

Do not break existing output.

Preserve:

```text
entities
facts
findings
repository_map
repository_graph
release metadata
```

Add:

```text
component_graph
```

---

# Do Not Implement

Do NOT implement in v0.6:

```text
LLM calls
AI classification
blast radius
impact prediction
Git history
ownership
CODEOWNERS
Jira
Confluence
Jenkins API
GitLab
frontend UI
Company Graph
Ask Radar
employee scoring
```

Those belong to later milestones.

---

# Definition of Done

Radar Core v0.6 is complete when:

* all previous tests pass,
* component candidates are generated deterministically,
* component membership is explicit,
* component scope is preserved,
* component evidence exists,
* component relationships can be derived from file relationships,
* tests/examples/subprojects do not pollute the main architecture,
* ambiguous areas remain unknown rather than guessed,
* `/scan` remains backward compatible,
* `/scan` works on `Futii10/radar-test`,
* `/scan` works on `expressjs/express`,
* `/scan` works on `madler/zlib`,
* documentation reflects actual implementation,
* v0.6 is marked `COMPLETED`.

---

# Expected Agent Workflow

1. Read this document.
2. Inspect v0.4 repository-map and v0.5 relationship graph architecture.
3. Design the smallest component model compatible with the existing codebase.
4. Implement deterministic component candidate detection.
5. Implement file membership.
6. Preserve scope/context.
7. Derive component relationships from file relationships.
8. Add regression tests.
9. Run the full backend suite.
10. Verify `/health`.
11. Verify `/scan` on `Futii10/radar-test`.
12. Verify `/scan` on `expressjs/express`.
13. Verify `/scan` on `madler/zlib`.
14. Inspect actual output for false positives.
15. Update this document with implementation details, limitations, and test results.
16. Mark v0.6 `COMPLETED`.
17. Stop.

Do not start v0.7.

---

# v0.6 Summary

Radar Core v0.6 should move Radar from:

```text
I know which files depend on which files.
```

to:

```text
I know the main logical building blocks of the system and how they connect.
```

This is the first system-level abstraction milestone.
