# Cross-Repository Validation Corpus

Radar has a pinned public-repository corpus for robustness validation. It is test infrastructure, not a product milestone.

## Corpus

The corpus is defined in [scripts/radar_validation_corpus.json](../scripts/radar_validation_corpus.json). Each entry contains:

- `repository`: GitHub `owner/name`
- `ref`: immutable commit SHA
- `tags`: language and structure coverage notes

The initial corpus contains 18 repositories covering Python, JavaScript/TypeScript, C/C++, Go, Rust, mixed-language repositories, monorepo-like layouts, CI-heavy projects, subprojects, examples/tests, and unusual filenames.

## Run Locally

Start the backend with a writable database path. If `GITHUB_TOKEN` is set, the GitHub source layer uses it without printing or storing the token:

```bash
RADAR_DB_PATH=/tmp/radar.db \
GITHUB_TOKEN="$GITHUB_TOKEN" \
.venv/bin/python -m uvicorn app.main:app \
  --app-dir backend \
  --host 0.0.0.0 \
  --port 8001
```

In another terminal, run the corpus validator:

```bash
.venv/bin/python scripts/validate_corpus.py \
  --base-url http://localhost:8001 \
  --json-out /tmp/radar-corpus-report.json
```

The runner performs a preflight `GET /health` and a controlled `Futii10/radar-test` scan before processing the selected corpus. Validation profiles are:

* `--mode smoke`: a small representative tag-based subset for quick local verification
* `--mode scan`: `/scan` only, the normal broad compatibility check for large corpora
* `--mode deep`: `/scan`, `/impact`, and same-snapshot `/diff` for representative semantic regression

Example commands:

```bash
# Frequent/local validation
.venv/bin/python scripts/validate_corpus.py --mode smoke --base-url http://localhost:8001

# Broad compatibility, capped while iterating
.venv/bin/python scripts/validate_corpus.py --mode scan --limit 3 --base-url http://localhost:8001

# Deep validation for selected repositories or a separate heavy run
.venv/bin/python scripts/validate_corpus.py --mode deep --tag large --base-url http://localhost:8001
```

Use `--only owner/name`, `--limit N`, `--tag TAG`, and `--exclude-tag TAG` to select practical slices. Use `--resume report.json` to skip repositories already recorded as `PASS` for the same mode; failed entries are retried and replace their previous result. Reports are written incrementally after each repository, so an interrupted run remains reusable.

The console output contains one concise PASS, FAIL, or UNSUPPORTED row per repository and names the selected mode in the header and JSON report. Each operation includes its duration. FAIL means an API or runtime failure that should be investigated. UNSUPPORTED is reserved for a valid scan where an operation cannot be meaningfully run, such as scan-only mode or a graph with no target nodes. The process exits nonzero when any repository is FAIL; it does not silently discard failures.

The JSON report contains counts and operation metadata, including resolved commit SHA, durations, and typed source/API errors. It intentionally excludes response bodies and tokens.

## Baseline Results

The baseline corpus contains 18 pinned public repositories:

* `Futii10/radar-test`
* `expressjs/express`
* `madler/zlib`
* `pallets/flask`
* `psf/requests`
* `django/django`
* `fastapi/fastapi`
* `microsoft/TypeScript`
* `nodejs/node`
* `curl/curl`
* `redis/redis`
* `kubernetes/kubernetes`
* `ansible/ansible`
* `apache/arrow`
* `denoland/deno`
* `tensorflow/tensorflow`
* `numpy/numpy`
* `llvm/llvm-project`

All 18 repositories successfully complete Radar scan after the defensive Node package.json parser fix. Sixteen of the 18 complete within the standard 180-second validation timeout. `denoland/deno` and `llvm/llvm-project` complete successfully with a 600-second timeout and are classified as performance-heavy validation cases, not compatibility failures.

`nodejs/node` originally exposed a real Radar parser bug: its `package.json` contained an `engines` value that was not a JSON object. The parser now ignores unsupported shapes without guessing a Node version. The pinned Node scan passes with:

* files: `51,794`
* facts: `67`
* repository relationships: `7`
* components: `21`
* unknown components: `8`

These baseline results distinguish compatibility failures from performance cases. A scan that completes with the standard or explicitly selected heavy timeout is a compatibility PASS; a timeout is recorded as a performance limitation and should be rerun separately with the larger timeout.

Current validation state:

* backend suite: `93 passed`
* validation harness suite: `11 passed`
* `git diff --check`: passed

The intended workflow is:

* `smoke` for frequent local development
* `scan` for broad compatibility validation
* `deep` for representative semantic validation
* a separate run with a larger timeout for performance-heavy repositories

## Maintenance

To update the corpus, add an entry with a full immutable commit SHA and descriptive tags. Do not replace SHAs with branch names. Keep the corpus broad and reasonably sized; changing Radar semantics to make a corpus row pass is not part of this harness.
