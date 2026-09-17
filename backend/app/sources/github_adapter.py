from __future__ import annotations

from app.models.snapshot import RepositorySnapshot
from app.sources.github import get_commit, get_latest_release, get_repository
from app.sources.repository import (
    get_repository_file_contents,
    get_repository_tree_entries,
    select_important_file_paths,
)


class GitHubSource:
    """GitHub adapter. It returns snapshots; it does not analyze repositories."""

    def load_snapshot(self, url: str, ref: str | None = None) -> tuple[RepositorySnapshot, dict]:
        prefix = "https://github.com/"
        if not url.startswith(prefix):
            raise ValueError("Currently only GitHub repositories are supported")

        repository = url.removeprefix(prefix).rstrip("/")
        metadata = get_repository(repository)
        requested_ref = ref or metadata.get("default_branch", "main")
        commit_sha = get_commit(repository, requested_ref).get("sha")
        tree_entries = get_repository_tree_entries(repository, commit_sha)
        paths = [entry["path"] for entry in tree_entries]
        important_paths = select_important_file_paths(paths)
        content_paths = list(dict.fromkeys(paths[:200] + important_paths))
        file_contents = get_repository_file_contents(repository, commit_sha, content_paths)
        snapshot = RepositorySnapshot(
            repository=metadata["full_name"],
            ref=requested_ref,
            commit_sha=commit_sha,
            files=tuple(sorted(tree_entries, key=lambda item: item["path"])),
            file_contents=file_contents,
            source="github",
            metadata={"repository": repository},
        )
        metadata = dict(metadata)
        metadata["repository"] = repository
        return snapshot, metadata

    def latest_release(self, repository: str):
        return get_latest_release(repository)
