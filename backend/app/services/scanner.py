from app.core.database import (
    get_previous_release,
    save_repository_state,
)
from app.sources.github import get_repository, get_latest_release


GITHUB_PREFIX = "https://github.com/"


def scan_repository(url: str):
    if not url.startswith(GITHUB_PREFIX):
        raise ValueError(
            "Currently only GitHub repositories are supported"
        )

    repository = url.removeprefix(GITHUB_PREFIX).rstrip("/")

    data = get_repository(repository)
    release_data = get_latest_release(repository)

    latest_release = None
    current_version = None

    if release_data:
        current_version = release_data["tag_name"]

        latest_release = {
            "version": current_version,
            "published_at": release_data["published_at"],
            "url": release_data["html_url"]
        }

    previous_version = get_previous_release(repository)

    new_release = (
        previous_version is not None
        and current_version is not None
        and previous_version != current_version
    )

    save_repository_state(
        repository,
        current_version
    )

    return {
        "repository": data["full_name"],
        "description": data["description"],
        "stars": data["stargazers_count"],
        "open_issues": data["open_issues_count"],
        "default_branch": data["default_branch"],
        "latest_release": latest_release,
        "previous_release": previous_version,
        "new_release_detected": new_release
    }
