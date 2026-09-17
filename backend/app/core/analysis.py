"""Source-neutral access to Radar's deterministic analysis primitives.

The implementation remains in the legacy scanner module for compatibility with
v0.1-v0.8 imports. New application code should depend on this module instead
of importing the scanner directly.
"""

from app.services.scanner import (
    build_component_graph,
    build_repository_graph,
    build_repository_map,
)

__all__ = [
    "build_component_graph",
    "build_repository_graph",
    "build_repository_map",
]
