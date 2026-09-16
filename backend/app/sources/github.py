import os

import httpx


class GitHubError(Exception):
    def __init__(self, message: str, status_code: int = 502, error_type: str = "source_error"):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type


def github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "radar-core",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_request(
    url: str,
    *,
    not_found_message: str = "GitHub resource not found",
    not_found_type: str = "not_found",
):
    try:
        response = httpx.get(url, headers=github_headers(), timeout=10.0)
    except httpx.RequestError as exc:
           raise GitHubError("Could not connect to GitHub", error_type="github_source_error") from exc

    if response.status_code == 401:
           raise GitHubError("GitHub authentication failed", 401, "github_auth_failed")

    headers = getattr(response, "headers", {}) or {}
    response_text = getattr(response, "text", "") or ""
    remaining = headers.get("x-ratelimit-remaining")
    if response.status_code == 403 and (remaining == "0" or "rate limit" in response_text.lower()):
           raise GitHubError("GitHub API rate limit exceeded", 403, "github_rate_limited")

    if response.status_code == 404:
        raise GitHubError(not_found_message, 404, not_found_type)

    if response.status_code == 422 and not_found_type == "ref_not_found":
        raise GitHubError(not_found_message, 422, "ref_not_found")

    if response.status_code >= 400:
        raise GitHubError("GitHub source request failed", response.status_code, "github_source_error")

    return response


def get_repository(repository: str):
    url = f"https://api.github.com/repos/{repository}"

    return github_request(
        url,
        not_found_message="GitHub repository not found",
        not_found_type="repository_not_found",
    ).json()


def get_latest_release(repository: str):
    url = f"https://api.github.com/repos/{repository}/releases/latest"

    try:
        response = github_request(url, not_found_message="GitHub release not found")
    except GitHubError as error:
        if error.error_type == "not_found":
            return None
        raise

    if response.status_code == 404:
        return None

    return response.json()


def get_commit(repository: str, ref: str):
    url = f"https://api.github.com/repos/{repository}/commits/{ref}"

    return github_request(
        url,
        not_found_message="GitHub repository ref not found",
        not_found_type="ref_not_found",
    ).json()
