from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RepositorySnapshot:
    """Immutable source-neutral repository state consumed by Radar Core."""

    repository: str
    ref: str
    commit_sha: str
    files: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    file_contents: dict[str, str] = field(default_factory=dict)
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def paths(self) -> list[str]:
        return [item["path"] for item in self.files if item.get("path")]

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "ref": self.ref,
            "commit_sha": self.commit_sha,
            "files": [dict(item) for item in self.files],
            "file_contents": dict(self.file_contents),
            "source": self.source,
            "metadata": dict(self.metadata),
        }
