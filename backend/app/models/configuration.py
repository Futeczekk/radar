from typing import Any

from pydantic import BaseModel

from app.models.facts import Evidence


class ConfigurationObservation(BaseModel):
    original_value: Any
    normalized_value: dict[str, Any] | None = None
    evidence: list[Evidence]
    scope: str | None = None
    source_type: str | None = None
    environment: str | None = None
    confidence: float


class ConfigurationConflict(BaseModel):
    subject: str
    status: str
    compatibility: str
    observations: list[ConfigurationObservation]
    evidence: list[Evidence]
    scopes: list[str]
    confidence: float
    reason: str