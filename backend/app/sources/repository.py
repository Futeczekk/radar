from __future__ import annotations

from urllib.parse import quote

from app.sources.github import GitHubError, github_request


IMPORTANT_PATH_HINTS = (
    "CMakeLists.txt",
    "Dockerfile",
    "pyproject.toml",
    "package.json",
    ".github/workflows/",
)


def get_repository_tree_entries(repository: str, ref: str = "HEAD"):
    url = f"https://api.github.com/repos/{repository}/git/trees/{ref}?recursive=1"

    payload = github_request(url, not_found_message="GitHub repository tree/ref not found").json()
    if "tree" not in payload:
        return []

    return [
        {"path": item["path"], "sha": item.get("sha")}
        for item in payload.get("tree", [])
        if item.get("type") == "blob"
    ]


def get_repository_tree(repository: str, ref: str = "HEAD"):
    return [item["path"] for item in get_repository_tree_entries(repository, ref)]


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
        encoded_path = quote(path, safe="/")
        url = f"https://raw.githubusercontent.com/{repository}/{default_branch}/{encoded_path}"
        try:
            response = github_request(url, not_found_message="GitHub file not found")
        except GitHubError as error:
            if error.error_type == "not_found":
                continue
            raise
        if response.status_code == 200:
            contents[path] = response.text
    return contents
