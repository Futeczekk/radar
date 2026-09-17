from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class SnapshotCache:
    """Optional filesystem cache keyed by repository and immutable commit SHA."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("RADAR_CACHE_PATH", "/tmp/radar-cache"))

    def _path(self, repository: str, commit_sha: str) -> Path:
        identity = f"{repository}\n{commit_sha}".encode("utf-8")
        return self.root / f"{hashlib.sha256(identity).hexdigest()}.json"

    def get(self, repository: str, commit_sha: str) -> dict[str, Any] | None:
        path = self._path(repository, commit_sha)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None
        if payload.get("repository") != repository or payload.get("commit_sha") != commit_sha:
            return None
        return payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else None

    def put(self, repository: str, commit_sha: str, snapshot: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(repository, commit_sha)
        payload = {"repository": repository, "commit_sha": commit_sha, "snapshot": snapshot}
        fd, temporary = tempfile.mkstemp(dir=self.root, prefix=".snapshot-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
