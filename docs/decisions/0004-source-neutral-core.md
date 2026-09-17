# ADR 0004: Source-Neutral Core

Providers are adapters that load `RepositorySnapshot`. Core analysis does not
know about GitHub HTTP, FastAPI, or credentials. GitHub is the first adapter,
not the domain model.
