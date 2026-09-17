# Validation subsystem

The pinned corpus and runner validate Radar against immutable public repository
states. The compatibility runner remains available at
`scripts/validate_corpus.py` for v0.8.x users; the stable package entrypoint is:

```bash
python -m validation.runner --mode smoke --base-url http://localhost:8001
```

Profiles are `smoke`, `scan`, `deep`, and a separate heavy run using a larger
request timeout. Reports include repository, resolved SHA, counts, duration,
and status. The optional `SnapshotCache` uses `repository + commit_sha` as its
identity and never stores credentials.
