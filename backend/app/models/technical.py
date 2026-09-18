from typing import Any

from pydantic import BaseModel, Field


class TechnicalChange(BaseModel):
    category: str
    subject: str
    change_type: str
    before: Any = None
    after: Any = None
    evidence: dict[str, list[dict[str, Any]]]
    scopes: list[str]
    confidence: float
    affected_elements: list[str] = Field(default_factory=list)