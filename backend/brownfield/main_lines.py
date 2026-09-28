"""Main line builder for Brownfield layouts with reference track dependency resolution."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union

from .geometry import compute_perpendicular_offset
from .models import (
    BrownfieldLayout,
    BrownfieldMainLineSpec,
    BrownfieldTrack,
    Point,
    TrackRelationship,
)
from .validation import validate_and_sort_main_lines


class BrownfieldMainLineBuilder:
    """Builder for constructing Brownfield layouts by adding MAIN_LINES with reference tracks.

    Usage:
        builder = BrownfieldMainLineBuilder()
        builder.add_base_track("MAIN_1", points=[(0, 0), (1000, 0)], direction="UP")
        builder.add_main_line(
            name="MAIN_2",
            reference_track="MAIN_1",
            spacing=5.3,
            side="LEFT",
            direction="DN",
        )
        builder.add_main_line(
            name="MAIN_3",
            reference_track="MAIN_2",
            spacing=5.3,
            side="LEFT",
            direction="DN",
        )
        layout = builder.build()
    """

    def __init__(self) -> None:
        self._base_tracks: Dict[str, BrownfieldTrack] = {}
        self._specs: List[BrownfieldMainLineSpec] = []

    def add_base_track(
        self,
        name: str,
        points: Sequence[Point],
        direction: str = "",
        is_existing: bool = True,
        metadata: Optional[dict] = None,
    ) -> BrownfieldMainLineBuilder:
        """Register an existing surveyed base track (datum alignment)."""
        clean_pts = [(float(p[0]), float(p[1])) for p in points]
        if len(clean_pts) < 2:
            raise ValueError(f"Base track {name!r} must have at least 2 points.")
        track = BrownfieldTrack(
            name=name.strip(),
            points=clean_pts,
            direction=direction,
            is_existing=is_existing,
            metadata=metadata or {},
        )
        self._base_tracks[track.name] = track
        return self

    def add_main_line(
        self,
        spec_or_name: Optional[Union[BrownfieldMainLineSpec, str]] = None,
        reference_track: Optional[str] = None,
        spacing: float = 5.3,
        side: str = "LEFT",
        direction: str = "",
        is_existing: bool = False,
        metadata: Optional[dict] = None,
        name: Optional[str] = None,
    ) -> BrownfieldMainLineBuilder:
        """Add a new MAIN_LINE mentioning its reference track.

        Can be called with a BrownfieldMainLineSpec instance, positionally, or via keyword arguments.
        """
        if isinstance(spec_or_name, BrownfieldMainLineSpec):
            spec = spec_or_name
        else:
            actual_name = name or (spec_or_name if isinstance(spec_or_name, str) else None)
            if not actual_name:
                raise ValueError("Main line name must be specified.")
            if reference_track is None:
                raise ValueError(
                    f"When adding main line {actual_name!r}, reference_track must be specified."
                )
            spec = BrownfieldMainLineSpec(
                name=actual_name,
                reference_track=reference_track,
                spacing=spacing,
                side=side,
                direction=direction,
                is_existing=is_existing,
                metadata=metadata or {},
            )
        self._specs.append(spec)
        return self

    def build(self) -> BrownfieldLayout:
        """Validate reference tracks, resolve dependencies, and generate all MAIN_LINES."""
        layout = BrownfieldLayout(metadata={"workflow": "brownfield"})

        # 1. Add all base tracks
        for track in self._base_tracks.values():
            layout.add_track(track)

        available_tracks = set(layout.tracks.keys())

        # 2. Validate and topologically sort all MAIN_LINE specs
        ordered_specs = validate_and_sort_main_lines(self._specs, available_tracks)

        # 3. Progressively generate each MAIN_LINE from its reference track
        for spec in ordered_specs:
            ref_track = layout.get_track(spec.reference_track)
            if ref_track is None:
                raise ValueError(
                    f"Internal error: reference track {spec.reference_track!r} was not built."
                )

            offset_points = compute_perpendicular_offset(
                points=ref_track.points,
                spacing=spec.spacing,
                side=spec.side,
            )

            new_track = BrownfieldTrack(
                name=spec.name,
                points=offset_points,
                reference_track=spec.reference_track,
                spacing_from_reference=spec.spacing,
                side=spec.side,
                direction=spec.direction,
                is_existing=spec.is_existing,
                metadata=dict(spec.metadata),
            )

            layout.add_track(new_track)
            layout.relationships.append(
                TrackRelationship(
                    track_name=spec.name,
                    reference_track=spec.reference_track,
                    spacing=spec.spacing,
                    side=spec.side,
                )
            )

        return layout
