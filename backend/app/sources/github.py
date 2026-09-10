import httpx


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def get_repository(repository: str):
    url = f"https://api.github.com/repos/{repository}"

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.RequestError:
        raise GitHubError("Could not connect to GitHub")

    if response.status_code != 200:
        raise GitHubError(
            "Could not fetch repository",
            response.status_code
        )

    return response.json()


def get_latest_release(repository: str):
    url = f"https://api.github.com/repos/{repository}/releases/latest"

    try:
        response = httpx.get(url, timeout=10.0)
    except httpx.RequestError:
        raise GitHubError("Could not connect to GitHub")

    if response.status_code == 404:
        return None

    if response.status_code != 200:
        raise GitHubError(
            "Could not fetch latest release",
            response.status_code
        )

    return response.json()
