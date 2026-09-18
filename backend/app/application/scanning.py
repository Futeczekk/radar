from __future__ import annotations

from app.core.analysis import (
    build_component_graph,
    build_repository_graph,
    build_repository_map,
)
from app.core.configuration_conflicts import detect_configuration_conflicts
from app.core.database import get_previous_release, save_repository_state
from app.extractors.configuration import extract_configuration
from app.extractors.technology import extract_technologies
from app.models.snapshot import RepositorySnapshot
from app.sources.github_adapter import GitHubSource
from app.sources.repository import select_important_file_paths


class ScanApplication:
    """Coordinates source loading, deterministic analysis, and persistence."""

    def __init__(self, source: GitHubSource | None = None):
        self.source = source or GitHubSource()

    def scan(self, url: str, ref: str | None = None) -> dict:
        snapshot, metadata = self.source.load_snapshot(url, ref)
        files = snapshot.paths
        important_paths = select_important_file_paths(files)
        important_contents = {
            path: snapshot.file_contents[path]
            for path in important_paths
            if path in snapshot.file_contents
        }
        entities, technology_facts = extract_technologies(files)
        configuration_facts, findings = extract_configuration(important_contents)
        configuration_conflicts = detect_configuration_conflicts(configuration_facts)
        facts = technology_facts + configuration_facts

        release_data = self.source.latest_release(metadata["repository"])
        current_version = release_data.get("tag_name") if release_data else None
        latest_release = None
        if release_data:
            latest_release = {
                "version": current_version,
                "published_at": release_data["published_at"],
                "url": release_data["html_url"],
            }

        previous_version = get_previous_release(metadata["repository"])
        new_release = (
            previous_version is not None
            and current_version is not None
            and previous_version != current_version
        )
        save_repository_state(metadata["repository"], current_version)

        repository_map = build_repository_map(files)
        repository_graph = build_repository_graph(snapshot.file_contents)
        component_graph = build_component_graph(files, repository_map, repository_graph)
        snapshot_data = {
            "repository": snapshot.repository,
            "ref": snapshot.ref,
            "commit_sha": snapshot.commit_sha,
            "files": list(snapshot.files),
            "facts": facts,
            "repository_graph": repository_graph,
            "component_graph": component_graph,
        }

        return {
            "repository": metadata["full_name"],
            "description": metadata["description"],
            "stars": metadata["stargazers_count"],
            "open_issues": metadata["open_issues_count"],
            "default_branch": metadata["default_branch"],
            "ref": snapshot.ref,
            "commit_sha": snapshot.commit_sha,
            "files_scanned": len(files),
            "entities": entities,
            "facts": facts,
            "findings": findings,
            "configuration_conflicts": configuration_conflicts,
            "repository_map": repository_map,
            "repository_graph": repository_graph,
            "component_graph": component_graph,
            "snapshot": snapshot_data,
            "latest_release": latest_release,
            "previous_release": previous_version,
            "new_release_detected": new_release,
        }


_default_application = ScanApplication()


def scan_repository(url: str, ref: str | None = None) -> dict:
    return _default_application.scan(url, ref)
