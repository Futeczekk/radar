# CI Contract

`ci/jobs.json` defines the stable logical jobs and their Make commands. CI
infrastructure may run these through Jenkins, GitHub Actions, or another
executor; this repository defines what is tested, not where Jenkins runs.

Fast PR/push work is `verify-env`, backend tests, harness tests, and smoke. The
nightly workflow runs the complete regression suite, full scan corpus,
representative deep validation, heavy repositories, and archives JSON reports.

Validation requests may use the optional filesystem cache in `RADAR_CACHE_PATH`.
The key is repository plus immutable commit SHA. Cache misses and hits must
produce the same analysis, and corrupted entries are ignored and rebuilt.
Credentials come from CI environment/credential stores and are excluded from
reports.
