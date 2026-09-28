"""Brownfield crossover domain models, geometric calculations, and builder.

Key design principles for Brownfield Crossovers:
1. Tracks do NOT end 50m after the last SRJ. Unlike Greenfield where all main lines
   are globally sliced to [min_srj - 50m, max_srj + 50m], Brownfield tracks preserve
   their full surveyed alignments and natural geometry.
2. Crossovers are scoped to their specific connecting lines (from_track, to_track).
   Operations on a single main line affect only that particular line, leaving other
   main lines in the layout completely untouched.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, List, Optional, Sequence, Tuple, Union

from .models import BrownfieldLayout, BrownfieldTrack, Point
from common.geometry import (
    nearest_point_on_alignment,
    point_at_chainage,
    polyline_length,
)
from track.overrun import slice_polyline
from track.crossover.core import calculate_crossover, generate_crossover_coordinates
from track.turnouts import TurnoutParameters, select_turnout


@dataclass
class BrownfieldCrossoverSpec:
    """Specification for adding a crossover connection in a Brownfield layout."""

    id: str
    from_track: str
    to_track: str
    chainage: float  # Chainage along from_track for the start SRJ
    direction: str = "FORWARD"  # "FORWARD" or "BACKWARD"
    turnout_designation: str = "1:12"
    turnout_variant: str = "standard"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id or not str(self.id).strip():
            raise ValueError("Crossover id must be a non-empty string.")
        if not self.from_track or not str(self.from_track).strip():
            raise ValueError(f"Crossover {self.id!r}: from_track must be specified.")
        if not self.to_track or not str(self.to_track).strip():
            raise ValueError(f"Crossover {self.id!r}: to_track must be specified.")
        if self.from_track.strip() == self.to_track.strip():
            raise ValueError(
                f"Crossover {self.id!r}: from_track and to_track cannot be the same track ({self.from_track!r})."
            )
        self.chainage = float(self.chainage)
        d = str(self.direction).strip().upper()
        if d not in ("FORWARD", "BACKWARD", "TRAILING", "FACING"):
            raise ValueError(
                f"Crossover {self.id!r}: direction must be FORWARD or BACKWARD, got {self.direction!r}."
            )
        self.direction = "FORWARD" if d in ("FORWARD", "FACING") else "BACKWARD"


@dataclass
class BrownfieldCrossoverResult:
    """Engineering result of a built Brownfield crossover."""

    id: str
    from_track: str
    to_track: str
    chainage: float
    direction: str
    turnout_designation: str
    turnout_variant: str
    points: List[Point] = field(default_factory=list)
    from_srj_point: Optional[Point] = None
    to_srj_point: Optional[Point] = None
    from_srj_chainage: float = 0.0
    to_srj_chainage: float = 0.0
    overall_length_m: float = 0.0
    track_centre_distance_m: float = 0.0
    affected_tracks: List[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> float:
        """Polyline length of the crossover path."""
        if len(self.points) < 2:
            return 0.0
        return sum(
            math.hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.points, self.points[1:])
        )


def build_brownfield_crossover(
    layout: BrownfieldLayout,
    spec: BrownfieldCrossoverSpec,
) -> BrownfieldCrossoverResult:
    """Calculate and construct a crossover between two tracks in a Brownfield layout.

    Note:
        Does NOT truncate or end either track after 50m of the last SRJ.
        Only the specified tracks (spec.from_track and spec.to_track) are connected.
        All other tracks in the layout remain completely untouched.
    """
    from_track = layout.get_track(spec.from_track)
    if from_track is None:
        raise ValueError(
            f"Crossover {spec.id!r}: from_track {spec.from_track!r} not found in layout. "
            f"Available tracks: {list(layout.keys())}"
        )
    to_track = layout.get_track(spec.to_track)
    if to_track is None:
        raise ValueError(
            f"Crossover {spec.id!r}: to_track {spec.to_track!r} not found in layout. "
            f"Available tracks: {list(layout.keys())}"
        )

    if len(from_track.points) < 2:
        raise ValueError(f"from_track {spec.from_track!r} has fewer than 2 points.")
    if len(to_track.points) < 2:
        raise ValueError(f"to_track {spec.to_track!r} has fewer than 2 points.")

    from_len = from_track.length
    if spec.chainage < 0 or spec.chainage > from_len:
        raise ValueError(
            f"Crossover {spec.id!r} chainage {spec.chainage:.2f} m lies outside "
            f"from_track {spec.from_track!r} range [0.0, {from_len:.2f} m]."
        )

    turnout = select_turnout(spec.turnout_designation, spec.turnout_variant)

    from_pts = [(float(p[0]), float(p[1])) for p in from_track.points]
    to_pts = [(float(p[0]), float(p[1])) for p in to_track.points]

    geom = calculate_crossover(spec.from_track, spec.to_track, from_pts, to_pts, turnout)

    # Determine SRJ connection points along the alignments
    horiz_dist_m = float(geom.horizontal_distance_mm) / 1000.0
    overall_len_m = float(geom.overall_length_mm) / 1000.0

    from_end_ch = float(spec.chainage)
    if spec.direction == "FORWARD":
        to_end_ch = from_end_ch + horiz_dist_m
    else:
        to_end_ch = from_end_ch - horiz_dist_m

    to_len = to_track.length
    if to_end_ch < 0 or to_end_ch > to_len:
        raise ValueError(
            f"Crossover {spec.id!r} connects to {spec.to_track!r} at chainage {to_end_ch:.2f} m, "
            f"which lies outside {spec.to_track!r} range [0.0, {to_len:.2f} m]."
        )

    pts = generate_crossover_coordinates(
        geom,
        from_pts,
        to_pts,
        from_endpoint_chainage_m=from_end_ch,
        to_endpoint_chainage_m=to_end_ch,
    )

    from_srj_pt = pts[0] if pts else None
    to_srj_pt = pts[-1] if pts else None

    # Measure actual track centre distance at crossover location
    if from_srj_pt is not None:
        proj = nearest_point_on_alignment(to_pts, from_srj_pt)
        tc_m = float(proj.distance)
    else:
        tc_m = float(geom.distance_mm) / 1000.0

    return BrownfieldCrossoverResult(
        id=spec.id,
        from_track=spec.from_track,
        to_track=spec.to_track,
        chainage=spec.chainage,
        direction=spec.direction,
        turnout_designation=spec.turnout_designation,
        turnout_variant=spec.turnout_variant,
        points=pts,
        from_srj_point=from_srj_pt,
        to_srj_point=to_srj_pt,
        from_srj_chainage=from_end_ch,
        to_srj_chainage=to_end_ch,
        overall_length_m=overall_len_m,
        track_centre_distance_m=tc_m,
        affected_tracks=[spec.from_track, spec.to_track],
        metadata=dict(spec.metadata),
    )


class BrownfieldCrossoverBuilder:
    """Manages adding and building crossovers for Brownfield layouts.

    Guarantees:
    - No 50m SRJ end-truncation is applied to tracks.
    - Crossovers only affect their designated from_track and to_track.
    - Individual main line extents can be adjusted on a per-line basis without
      affecting any other main line in the layout.
    """

    def __init__(self, layout: Optional[BrownfieldLayout] = None) -> None:
        self.layout = layout
        self._specs: List[BrownfieldCrossoverSpec] = []

    def add_crossover(
        self,
        spec_or_id: Optional[Union[BrownfieldCrossoverSpec, str]] = None,
        from_track: Optional[str] = None,
        to_track: Optional[str] = None,
        chainage: Optional[float] = None,
        direction: str = "FORWARD",
        turnout_designation: str = "1:12",
        turnout_variant: str = "standard",
        metadata: Optional[dict] = None,
        id: Optional[str] = None,
    ) -> BrownfieldCrossoverBuilder:
        """Register a crossover specification to be built."""
        if isinstance(spec_or_id, BrownfieldCrossoverSpec):
            spec = spec_or_id
        else:
            actual_id = id or (spec_or_id if isinstance(spec_or_id, str) else None)
            if not actual_id:
                raise ValueError("Crossover id must be specified.")
            if from_track is None or to_track is None or chainage is None:
                raise ValueError("from_track, to_track, and chainage must be specified.")
            spec = BrownfieldCrossoverSpec(
                id=actual_id,
                from_track=from_track,
                to_track=to_track,
                chainage=float(chainage),
                direction=direction,
                turnout_designation=turnout_designation,
                turnout_variant=turnout_variant,
                metadata=metadata or {},
            )
        self._specs.append(spec)
        return self

    def build(self, layout: Optional[BrownfieldLayout] = None) -> List[BrownfieldCrossoverResult]:
        """Compute all crossovers and return their results.

        Neither track is truncated past the SRJ; each preserves its full alignment.
        """
        target_layout = layout or self.layout
        if target_layout is None:
            raise ValueError("A BrownfieldLayout must be provided to build crossovers.")

        results: List[BrownfieldCrossoverResult] = []
        for spec in self._specs:
            res = build_brownfield_crossover(target_layout, spec)
            results.append(res)
            target_layout.add_crossover(res)

        return results

    def set_single_track_extent(
        self,
        layout: BrownfieldLayout,
        track_name: str,
        start_chainage: Optional[float] = None,
        end_chainage: Optional[float] = None,
    ) -> BrownfieldTrack:
        """Explicitly adjust the extent of ONE single track without affecting any other main lines.

        Args:
            layout: The BrownfieldLayout containing the track.
            track_name: Target line to adjust (e.g. "MAIN_LINE_1").
            start_chainage: Optional new start distance along this line.
            end_chainage: Optional new end distance along this line.

        Returns:
            The modified BrownfieldTrack.
        """
        target = layout.get_track(track_name)
        if target is None:
            raise ValueError(f"Track {track_name!r} not found in layout.")

        total_len = target.length
        s = 0.0 if start_chainage is None else max(0.0, float(start_chainage))
        e = total_len if end_chainage is None else min(total_len, float(end_chainage))

        if e <= s:
            raise ValueError(
                f"Invalid extent range for {track_name!r}: [{s:.2f}, {e:.2f}] (length={total_len:.2f})"
            )

        sliced_pts = slice_polyline(target.points, s, e)
        target.points = [(float(p[0]), float(p[1])) for p in sliced_pts]
        target.metadata["custom_extent"] = (s, e)
        return target
