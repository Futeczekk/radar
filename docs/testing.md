# Testing

Backend tests cover deterministic extractors, source adapters, repository maps,
relationships, components, impact, and diff behavior. Validation harness tests
cover runner error handling, selection, resume, and report behavior.

`smoke` is a small representative compatibility run. `scan` exercises `/scan`
for the pinned corpus. `deep` adds impact and same-snapshot diff. Heavy tagged
repositories, currently Deno and LLVM, run separately with a larger timeout.

A semantic change in a pinned result requires investigation before updating any
expected behavior. The corpus is a compatibility guard, not a source of new
product semantics.
