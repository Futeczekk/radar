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

Configuration-conflict tests cover supported version grammar, compatibility,
scope filtering, CI matrices, evidence/context preservation, deterministic
ordering, deduplication, cache equivalence, and `/scan` compatibility. Live
v0.10 review inspects every reported conflict manually; a non-zero count alone
is not acceptance.

v0.11 technical-change tests cover runtime and build fact transitions,
configuration-conflict lifecycle, dependency and component graph changes,
known impact, weak-scope and README noise suppression, evidence preservation,
deterministic ordering, cache-equivalent snapshots, and `/diff` compatibility.
Controlled review must inspect each emitted change's category, subject,
before/after values, evidence, scopes, confidence, and known affected elements.
