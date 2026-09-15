from typing import Any

from pydantic import BaseModel


class Entity(BaseModel):
    type: str
    name: str
    identifier: str | None = None


class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str | None = None
    reason: str


class Fact(BaseModel):
    type: str
    subject: str
    value: Any
    confidence: float
    extractor: str
    evidence: list[Evidence]
