from __future__ import annotations

import httpx


class RepositorySourceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def get_repository_tree(repository: str):
    url = f"https://api.github.com/repos/{repository}/git/trees/HEAD?recursive=1"

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.RequestError as exc:
        raise RepositorySourceError("Could not connect to GitHub") from exc

    if response.status_code != 200:
        raise RepositorySourceError(
            "Could not fetch repository tree",
            response.status_code,
        )

    payload = response.json()
    if "tree" not in payload:
        return []

    return [item["path"] for item in payload.get("tree", []) if item.get("type") == "blob"]
