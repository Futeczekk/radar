from pydantic import BaseModel


class RepositoryRequest(BaseModel):
    url: str


class ImpactRequest(BaseModel):
    url: str
    target: str | None = None
    component: str | None = None
