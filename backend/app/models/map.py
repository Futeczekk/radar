from typing import Any

from pydantic import BaseModel, Field

from app.models.repository import RepositoryRequest


class MapRequest(BaseModel):
    repositories: list[RepositoryRequest]


class RepositoryMapEntry(BaseModel):
    repository_id: str
    requested_url: str
    requested_ref: str | None = None
    resolved_revision: str | None = None
    snapshot_id: str | None = None
    status: str
    error: dict[str, Any] | None = None
    dependencies: list[str] = Field(default_factory=list)
    dependents: list[str] = Field(default_factory=list)


class RepositoryRelationship(BaseModel):
    source_repository: str
    target_repository: str
    type: str
    evidence: list[dict[str, Any]]


class UnresolvedReference(BaseModel):
    source_repository: str
    target_reference: str
    path: str
    reason: str
    value: str


class RepositoryMapResponse(BaseModel):
    status: str
    repositories: list[RepositoryMapEntry]
    relationships: list[RepositoryRelationship]
    unresolved_references: list[UnresolvedReference]