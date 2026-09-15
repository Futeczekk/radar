# Radar Core v0.5

## Status

COMPLETED

## Implementation Summary

Radar Core v0.5 is implemented as a conservative relationship layer built on top of the existing v0.1-v0.4 repository map and fact extraction.

The scanner now emits a deterministic `repository_graph` with:

* file nodes for the scanned repository
* deduplicated `imports` and `includes` relationships
* evidence attached to each relationship (`file`, `line`, `snippet`, `reason`)
* scope awareness for project/subproject/test/example/vendor/generated paths
* external dependency filtering so system and package-level imports are not misrepresented as internal repo links

The implementation remains intentionally narrow and evidence-based:

* Python: `import` and `from ... import ...` resolution for local modules
* JavaScript/TypeScript: relative `import` and `require()` resolution for direct files and `index.js`/`index.ts` modules
* C/C++: local quoted include resolution only
* duplicate relationships removed before response serialization

It preserves the v0.3/v0.4 guardrails by keeping secondary `contrib/`, test, example, vendor, and generated relationships scoped as appropriate. `contrib/` reuses the existing `subproject` scope and its internal relationships remain visible without polluting the primary project graph. The scanner also prevents fake internal targets from being invented when a target cannot be resolved safely.

## Verification

Validated with the project test suite:

* `56 passed in 0.17s`

Validated against live API scans:

* `GET /health` returned `200` with `{"status":"ok"}`
* `POST /scan` on `Futii10/radar-test` returned `200` and a valid graph payload
* `POST /scan` on `expressjs/express` returned `200` with repository relationships emitted in the graph
* `POST /scan` on `madler/zlib` returned `200` and generated local C include relationships without creating false internal targets for system headers

## Previous versions

Radar Core v0.1 — COMPLETED
Radar Core v0.2 — COMPLETED
Radar Core v0.3 — COMPLETED
Radar Core v0.4 — COMPLETED

v0.1 answers:

> What exists in this repository?

v0.2 answers:

> How is this repository configured?

v0.3 answers:

> Can Radar trust and correctly interpret the facts it finds?

v0.4 answers:

> What is where in this repository?

v0.5 should answer:

> How are the important parts of this repository connected?

---

# Goal

Radar should build the first deterministic, evidence-backed relationship graph between files and modules.

The purpose of v0.5 is NOT deep code understanding.

The purpose is to detect simple, reliable relationships such as:

```text
main.py
→ imports
api.py

api.py
→ imports
service.py

service.py
→ imports
database.py
```

or:

```text
main.cpp
→ includes
service.hpp
```

or:

```text
server.ts
→ imports
routes.ts
```

Radar should begin moving from a repository map toward a dependency graph.

---

# Core Principle

Every relationship must be based on deterministic evidence.

Radar must not invent relationships.

Every relationship should have at least:

```text
source
target
type
confidence
evidence
```

Example:

```json
{
  "source": "backend/main.py",
  "target": "backend/api.py",
  "type": "imports",
  "confidence": 1.0,
  "evidence": [
    {
      "file": "backend/main.py",
      "line": 3,
      "snippet": "from backend import api",
      "reason": "Python import statement references backend.api"
    }
  ]
}
```

---

# Supported Relationship Types

Keep the initial taxonomy small.

Suggested types:

```text
imports
includes
requires
references
```

For v0.5 the main focus should be:

```text
imports
includes
```

Do not introduce a large relationship taxonomy yet.

---

# Supported Languages

Initial deterministic support should include:

## Python

Recognize:

```python
import module
import package.module
from package import module
from package.module import symbol
```

Resolve imports to repository files when deterministic.

Examples:

```text
from app import api
→ app/api.py

from app.service import UserService
→ app/service.py
```

Do not attempt full Python runtime import resolution.

---

## JavaScript / TypeScript

Recognize:

```javascript
import x from "./x"
import { x } from "./x"
require("./x")
```

Support common relative file resolution such as:

```text
./api
→ api.js
→ api.ts
→ api/index.js
→ api/index.ts
```

Keep resolution conservative.

Do not attempt npm dependency resolution yet.

---

## C / C++

Recognize:

```cpp
#include "local/header.hpp"
#include "service.h"
```

Focus on repository-local quoted includes.

Do NOT treat standard/system includes as internal dependencies.

Example:

```cpp
#include <vector>
```

must NOT create a repository relationship.

---

# External Dependencies

External dependencies may be recognized as external references, but they must not be mixed with internal repository relationships.

Examples:

```python
import fastapi
```

```javascript
import express from "express"
```

```cpp
#include <boost/asio.hpp>
```

These may later become dependency entities.

For v0.5 it is acceptable to:

* omit unresolved external dependencies, or
* expose them separately as external references.

Do not pretend they are repository files.

---

# Relationship Resolution

Radar should resolve a relationship only when there is enough deterministic evidence.

Example:

```text
import api
```

If there are multiple possible `api.py` files and the target cannot be resolved safely:

```text
UNKNOWN
```

Do not guess.

Precision remains more important than recall.

---

# Repository Graph

Extend `/scan` with a first relationship representation.

Suggested structure:

```json
{
  "repository_graph": {
    "nodes": [],
    "relationships": []
  }
}
```

Exact internal representation may follow the current codebase style.

Nodes may initially represent files only.

Example:

```json
{
  "nodes": [
    {
      "id": "backend/main.py",
      "type": "file"
    },
    {
      "id": "backend/api.py",
      "type": "file"
    }
  ],
  "relationships": [
    {
      "source": "backend/main.py",
      "target": "backend/api.py",
      "type": "imports"
    }
  ]
}
```

Keep it minimal.

Do not build the Company Graph yet.

---

# Reuse v0.4 Repository Map

The v0.5 graph should reuse information already discovered by Radar.

For example:

```text
entry point
source directories
tests
examples
vendor
generated
```

Do not create a second independent repository model.

---

# Context Awareness

Relations must preserve v0.3/v0.4 context.

Example:

```text
examples/demo/main.py
→ imports examples/demo/helper.py
```

is allowed as an example-scope relation.

But it must not be presented as the primary application dependency graph.

Similarly:

```text
tests/test_api.py
→ imports backend/api.py
```

should remain a test relationship.

Context should be visible or inferable.

---

# Primary vs Secondary Relationships

Radar should distinguish relationships coming from:

```text
project/source
test
example
vendor
generated
```

Primary project relationships should be emphasized.

Secondary relationships should not pollute the main dependency graph.

---

# Entry Point Traversal

Where practical, Radar should be able to identify relationships starting from known entry points.

Example:

```text
main.py
 ↓
api.py
 ↓
service.py
 ↓
database.py
```

Do not build sophisticated path analysis yet.

A simple first-hop / multi-hop deterministic traversal is enough if easy to implement.

The raw relationships are more important than advanced traversal.

---

# Evidence

Every relationship must have evidence.

Preferred fields:

```text
file
line
snippet
reason
```

Example:

```json
{
  "file": "backend/main.py",
  "line": 4,
  "snippet": "from backend.api import router",
  "reason": "Python import resolves to backend/api.py"
}
```

If line numbers are easy to provide, include them.

Do not sacrifice correctness for perfect evidence formatting.

---

# False Positive Protection

v0.5 must preserve the trust principles from v0.3 and v0.4.

Examples:

## Tests

```text
tests/test_api.py
```

must not make `tests/` part of the primary runtime graph.

## Examples

```text
examples/demo/main.py
```

must not become the primary application dependency chain.

## Vendor

```text
vendor/library/
```

should not become part of the project's own dependency graph unless explicitly requested later.

## Generated

```text
build/
dist/
generated/
```

should normally be excluded from primary graph analysis.

---

# Cycles

Dependency cycles may exist.

Example:

```text
a.py → b.py
b.py → a.py
```

Radar must handle them without crashing or recursing infinitely.

It is acceptable to represent the cycle directly.

Do not implement cycle diagnosis yet.

---

# Duplicate Relationships

Do not emit duplicate relationships.

Example:

```python
import api
from api import router
```

may still resolve to the same file.

Radar should deduplicate equivalent relationships where appropriate.

Evidence may contain multiple references if useful.

---

# Missing Targets

If a relationship cannot be resolved safely:

```text
do not guess
```

Possible behavior:

* omit the relationship,
* or preserve it as unresolved/external if the architecture supports this cleanly.

Do not fabricate a target.

---

# Performance

Do not download or parse the entire repository unnecessarily if current architecture can avoid it.

However, v0.5 may require fetching source contents for supported source files.

Keep implementation practical.

Do not attempt whole-repository semantic indexing.

---

# Required Regression Cases

Add deterministic tests for at least:

```text
Python local import
Python from-import
Python unresolved import
Python import cycle

JavaScript relative import
JavaScript require()
TypeScript relative import
JavaScript index-file resolution

C local quoted include
C++ local quoted include
system include ignored

test dependency remains test-scoped
example dependency remains example-scoped
vendor/generated source excluded from primary graph

duplicate relationship deduplication
missing target does not create fake relationship
```

Preserve all v0.1-v0.4 tests.

---

# Controlled Repository Test

Extend `Futii10/radar-test` with a small known dependency chain.

Suggested structure:

```text
backend/
  main.py
  api.py
  service.py
  database.py
```

Example:

```python
# main.py
from backend import api
```

```python
# api.py
from backend import service
```

```python
# service.py
from backend import database
```

Expected:

```text
backend/main.py
→ backend/api.py

backend/api.py
→ backend/service.py

backend/service.py
→ backend/database.py
```

Add at least one intentionally unresolved external import such as:

```python
import fastapi
```

Radar must not resolve it to a fake repository file.

---

# Real Repository Validation

After implementation, validate on at least:

```text
expressjs/express
```

and one C/C++ repository such as:

```text
fmtlib/fmt
```

The purpose is to verify that relationship extraction works on real-world repository layouts.

Do not try to achieve perfect coverage.

Look for obvious incorrect relationships and false positives.

---

# API Compatibility

Do not break existing `/scan` fields.

Preserve:

```text
entities
facts
findings
repository_map
release metadata
```

Add repository graph information without changing existing behavior.

---

# Do Not Implement

Do NOT implement in v0.5:

```text
AI code understanding
LLM summaries
component inference
service inference
blast radius scoring
impact prediction
Git history
ownership inference
CODEOWNERS
Jira
Confluence
Jenkins API
GitLab support
frontend UI
automatic fixes
Company Software Graph
```

Those belong to later milestones.

---

# Definition of Done

Radar Core v0.5 is complete when:

* all v0.1 tests pass,
* all v0.2 tests pass,
* all v0.3 tests pass,
* all v0.4 tests pass,
* Python internal imports can be resolved deterministically,
* JavaScript/TypeScript relative imports can be resolved deterministically,
* C/C++ local includes can be resolved deterministically,
* external/system dependencies are not falsely resolved as internal files,
* relationships contain evidence,
* relationships preserve context,
* tests/examples/vendor/generated do not pollute the primary graph,
* duplicate relationships are handled,
* cycles do not crash analysis,
* unresolved targets do not create fake relationships,
* `/health` works,
* `/scan` works on `Futii10/radar-test`,
* `/scan` works on at least one real JavaScript repository,
* `/scan` works on at least one real C/C++ repository.

---

# Expected Agent Workflow

1. Read this document.
2. Inspect the completed v0.4 architecture.
3. Reuse repository-map and context logic.
4. Create the smallest relationship model that fits the current codebase.
5. Implement deterministic Python import extraction.
6. Implement deterministic JS/TS relative import extraction.
7. Implement deterministic C/C++ local include extraction.
8. Resolve targets conservatively.
9. Preserve context.
10. Add regression tests.
11. Run the full backend test suite.
12. Verify `/health`.
13. Verify `/scan` on `Futii10/radar-test`.
14. Verify `/scan` on `expressjs/express`.
15. Verify `/scan` on one C/C++ repository.
16. Update this document with actual implementation, limitations, and test results.
17. Mark v0.5 as `COMPLETED`.
18. Stop.

Do not start v0.6.

---

# v0.5 Summary

Radar Core v0.5 should move Radar from:

```text
I know where the important files are.
```

to:

```text
I know how important files are connected.
```

This is the first dependency-graph milestone.
