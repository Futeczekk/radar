# Development

## Setup

```bash
make setup
make verify-env
```

The backend runs on port 8001 and uses `/tmp/radar.db` by default. Set
`RADAR_DB_PATH` for another writable location. `GITHUB_TOKEN` is optional and
is never printed or stored.

## Commands

- `make test` runs backend regression tests.
- `make harness-test` runs validation runner tests.
- `make check` runs environment, backend, and harness checks.
- `make run` starts the local API.
- `make smoke` runs the representative pinned corpus profile against a running API.
- `make corpus-scan` and `make corpus-deep` run broader profiles.
- `make corpus-heavy` runs large tagged repositories with a 600 second timeout.

Run `make run` in one terminal and a validation command in another. Add a new
extractor under `backend/app/extractors`; add a source integration under
`backend/app/sources` that returns `RepositorySnapshot`.

Configuration conflicts are evaluated from extracted facts in
`backend/app/core/configuration_conflicts.py`. Keep version grammar explicit
and conservative, preserve observation evidence/context, and keep source and
HTTP concerns outside the evaluator.
