from pydantic import BaseModel


class RepositoryRequest(BaseModel):
    url: str
    ref: str | None = None


class ImpactRequest(BaseModel):
    url: str
    target: str | None = None
    component: str | None = None


class DiffRequest(BaseModel):
    url: str
    base_ref: str
    target_ref: str
