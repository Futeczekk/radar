from __future__ import annotations

import httpx


IMPORTANT_PATH_HINTS = (
    "CMakeLists.txt",
    "Dockerfile",
    "pyproject.toml",
    "package.json",
    ".github/workflows/",
)


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


def select_important_file_paths(paths):
    selected = []
    for path in paths:
        normalized = path.replace("\\", "/").lower()
        if normalized.endswith("cmakelists.txt"):
            selected.append(path)
        elif normalized.endswith("dockerfile"):
            selected.append(path)
        elif normalized.endswith("pyproject.toml"):
            selected.append(path)
        elif normalized.endswith("package.json"):
            selected.append(path)
        elif ".github/workflows/" in normalized and normalized.endswith((".yml", ".yaml")):
            selected.append(path)
    return selected


def get_repository_file_contents(repository: str, default_branch: str, paths):
    contents = {}
    for path in paths:
        url = f"https://raw.githubusercontent.com/{repository}/{default_branch}/{path}"
        try:
            response = httpx.get(url, timeout=10.0)
        except httpx.RequestError:
            continue
        if response.status_code == 200:
            contents[path] = response.text
    return contents
