"""Validation and dependency graph sorting for Brownfield MAIN_LINE specifications."""

from __future__ import annotations

from typing import Dict, List, Sequence, Set

from .models import BrownfieldMainLineSpec


def validate_and_sort_main_lines(
    specs: Sequence[BrownfieldMainLineSpec],
    available_tracks: Set[str],
) -> List[BrownfieldMainLineSpec]:
    """Validate reference tracks and sort specifications in dependency order.

    Ensures:
    1. Every added MAIN_LINE mentions a valid, resolvable reference_track.
    2. No duplicate track names exist.
    3. No circular reference dependencies exist between tracks.
    4. Tracks are returned in topological order so each reference_track is built
       before any track depending on it.

    Args:
        specs: Sequence of BrownfieldMainLineSpec instances to add.
        available_tracks: Set of track names already existing in the layout.

    Returns:
        List of specs ordered such that each track's reference_track is guaranteed
        to be available when generating it.

    Raises:
        ValueError: If reference_track is missing, duplicate names exist, or cycles are found.
    """
    if not specs:
        return []

    # 1. Check for duplicate names
    seen_names: Set[str] = set()
    spec_map: Dict[str, BrownfieldMainLineSpec] = {}

    for spec in specs:
        name = spec.name.strip()
        if name in seen_names:
            raise ValueError(f"Duplicate main line name detected: {name!r}.")
        if name in available_tracks:
            raise ValueError(
                f"Cannot add main line {name!r}: track already exists in layout."
            )
        seen_names.add(name)
        spec_map[name] = spec

    all_possible_tracks = available_tracks | seen_names

    # 2. Check reference_track existence
    for spec in specs:
        ref = spec.reference_track.strip()
        if ref == spec.name.strip():
            raise ValueError(
                f"Main line {spec.name!r} cannot have itself as its reference_track."
            )
        if ref not in all_possible_tracks:
            raise ValueError(
                f"Main line {spec.name!r} references unknown track {ref!r}. "
                f"Available tracks: {sorted(all_possible_tracks)}."
            )

    # 3. Topological sort using cycle detection (Kahn's or DFS)
    # Adjacency: ref -> list of tracks depending on ref
    # In-degree: number of unresolved dependencies in specs
    in_degree: Dict[str, int] = {name: 0 for name in seen_names}
    dependents: Dict[str, List[str]] = {name: [] for name in seen_names}

    for spec in specs:
        name = spec.name.strip()
        ref = spec.reference_track.strip()
        if ref in seen_names:
            in_degree[name] += 1
            dependents[ref].append(name)

    # Queue tracks that depend only on already available base tracks
    queue: List[str] = [name for name, deg in in_degree.items() if deg == 0]
    sorted_names: List[str] = []

    while queue:
        current = queue.pop(0)
        sorted_names.append(current)
        for dep in dependents.get(current, []):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(sorted_names) != len(seen_names):
        unresolved = [name for name, deg in in_degree.items() if deg > 0]
        raise ValueError(
            f"Circular reference dependency detected among main lines: {unresolved}."
        )

    return [spec_map[name] for name in sorted_names]
