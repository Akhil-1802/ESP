"""Dynamic FOB placement relative to actual station / platform edges.

Derivation flow:
    Station Centre -> Actual Station Edge -> User Offset -> Track Chainage -> Track Position.

The station centre represents chainage 0.000 in the project chainage system.
Station edge is determined dynamically from the actual station or platform polygon
geometry projected along the track alignment.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple, Union

from common.constants import (
    DEFAULT_FOB_DIRECTION,
    DEFAULT_FOB_OFFSET_M,
    MAX_FOB_OFFSET_M,
    MIN_FOB_OFFSET_M,
)
from common.geometry import (
    Point,
    nearest_point_on_alignment,
    point_at_chainage,
    polygons_overlap,
    polyline_length,
)
from fob.config import normalize_fob_direction, validate_fob_offset
from fob.deck_geom import axis_spans, build_fob_outline, validate_fob_span


def determine_station_edge(
    track_points: Sequence[Point],
    station_geometry: Sequence[Point] | Sequence[Sequence[Point]],
    direction: str | int = DEFAULT_FOB_DIRECTION,
) -> float:
    """Determine the actual station/platform edge chainage dynamically."""
    if not station_geometry:
        raise ValueError("station_geometry cannot be empty.")

    pts: List[Point] = []
    first = station_geometry[0]
    if isinstance(first, (list, tuple)) and len(first) > 0 and isinstance(first[0], (list, tuple)):
        for poly in station_geometry:
            pts.extend([(float(p[0]), float(p[1])) for p in poly])
    else:
        pts = [(float(p[0]), float(p[1])) for p in station_geometry]

    cleaned_track = [(float(p[0]), float(p[1])) for p in track_points]
    if len(cleaned_track) < 2:
        raise ValueError("track_points must contain at least 2 points.")

    chainages = [
        float(nearest_point_on_alignment(cleaned_track, p).chainage)
        for p in pts
    ]
    if not chainages:
        raise ValueError("No valid projection chainages found for station_geometry.")

    dir_norm = normalize_fob_direction(direction)
    if dir_norm == "INCREASING":
        return max(chainages)
    else:
        return min(chainages)


def calculate_fob_chainage(
    station_center: float | Point,
    station_edge: Optional[float | Point | Sequence[Point]] = None,
    direction: str | int = DEFAULT_FOB_DIRECTION,
    offset: float = DEFAULT_FOB_OFFSET_M,
    track_points: Optional[Sequence[Point]] = None,
    fob_width: float = 0.0,
    arm_length: float = 0.0,
) -> float:
    """Calculate the FOB chainage relative to station edge or reference / MAIN centre."""
    val_offset = validate_fob_offset(offset)
    dir_norm = normalize_fob_direction(direction)

    if station_edge is not None:
        if isinstance(station_edge, (int, float)):
            base_ch = float(station_edge)
        elif track_points is not None:
            base_ch = determine_station_edge(track_points, station_edge, dir_norm)
        else:
            raise ValueError(
                "track_points must be provided to project station_edge geometry onto the alignment."
            )
    else:
        if isinstance(station_center, (int, float)):
            base_ch = float(station_center)
        elif track_points is not None:
            base_ch = float(nearest_point_on_alignment(track_points, station_center).chainage)
        else:
            base_ch = float(station_center[0])

    extra = (float(fob_width) / 2.0) + float(arm_length)
    if dir_norm == "INCREASING":
        fob_chainage = base_ch + val_offset + extra
    else:
        fob_chainage = base_ch - (val_offset + extra)

    return fob_chainage


def calculate_fob_chainage_from_center(
    reference_chainage: float,
    offset: float = DEFAULT_FOB_OFFSET_M,
    direction: str | int = DEFAULT_FOB_DIRECTION,
) -> float:
    """Calculate FOB chainage directly from reference / MAIN centre chainage."""
    val_offset = validate_fob_offset(offset)
    dir_norm = normalize_fob_direction(direction)
    if dir_norm == "INCREASING":
        return float(reference_chainage) + val_offset
    else:
        return float(reference_chainage) - val_offset


def get_fob_track_position(
    track_points: Sequence[Point],
    fob_chainage: float,
) -> Tuple[Point, Point, Point]:
    """Convert calculated FOB chainage back to actual track position, tangent, and normal."""
    cleaned = [(float(p[0]), float(p[1])) for p in track_points]
    total_len = polyline_length(cleaned)
    if not (0.0 <= fob_chainage <= total_len):
        raise ValueError(
            f"FOB chainage {fob_chainage:.3f} m is outside track limits [0.000, {total_len:.3f}] m."
        )

    st = point_at_chainage(cleaned, float(fob_chainage))
    tn = math.hypot(st.tangent[0], st.tangent[1]) or 1.0
    tx, ty = st.tangent[0] / tn, st.tangent[1] / tn
    nx, ny = -ty, tx
    return st.point, (tx, ty), (nx, ny)


def validate_fob_conflicts(
    fob_chainage: float,
    fob_width: float,
    reference_track: str,
    tracks: Dict[str, Sequence[Point]],
    platform_polygons: Dict[str, Sequence[Point]],
    connected_platforms: Sequence[str],
    station_polygons: Optional[Sequence[Sequence[Point]]] = None,
    restricted_regions: Optional[Sequence] = None,
    arm_specs: Optional[dict] = None,
) -> None:
    """Validate that the resulting FOB does not conflict with platforms, tracks, or restricted areas."""
    track_pts = tracks.get(reference_track)
    if track_pts is None or len(list(track_pts)) < 2:
        raise ValueError(f"FOB reference track {reference_track!r} not found or too short.")

    total_len = polyline_length([(float(p[0]), float(p[1])) for p in track_pts])
    if fob_chainage < 0.0 or fob_chainage > total_len:
        raise ValueError(
            f"FOB placement conflict: chainage {fob_chainage:.3f} m exceeds "
            f"track {reference_track!r} length [0.000, {total_len:.3f}] m."
        )

    origin, tangent, normal = get_fob_track_position(track_pts, fob_chainage)

    # 1. Platform connection validation: FOB axis must cross all connected platforms
    for p_name in connected_platforms:
        poly = platform_polygons.get(p_name)
        if poly is None:
            raise ValueError(
                f"FOB placement conflict: connected platform {p_name!r} not found in drawing."
            )
        spans = axis_spans(origin, normal, [poly])
        if not spans or spans[0] is None:
            raise ValueError(
                f"FOB placement conflict: at chainage {fob_chainage:.3f} m, the FOB axis "
                f"misses connected platform {p_name!r} (outside platform extent)."
            )

    # 2. Span validation
    polys = [platform_polygons[p] for p in connected_platforms if p in platform_polygons]
    spans = [s for s in axis_spans(origin, normal, polys) if s is not None]
    if not spans:
        raise ValueError("FOB placement conflict: FOB axis misses all selected platforms.")
    lo = min(s[0] for s in spans)
    hi = max(s[1] for s in spans)

    if arm_specs:
        try:
            from fob.deck_geom import build_fob_arms
            spans_by_layer = dict(zip(connected_platforms, axis_spans(origin, normal, polys)))
            arms = build_fob_arms(origin, tangent, normal, spans_by_layer, arm_specs, fob_width, tracks=tracks)
            if arms:
                arm_projections = [
                    (p[0] - origin[0]) * normal[0] + (p[1] - origin[1]) * normal[1]
                    for arm in arms
                    for p in arm
                ]
                if arm_projections:
                    lo = min(arm_projections)
                    hi = max(arm_projections)
        except Exception:
            pass

    validate_fob_span(hi - lo)

    # 3. Station building footprint conflict
    deck_outline = build_fob_outline(
        origin, tangent, polys, fob_width,
        arm_bounds=(lo, hi) if arm_specs else None,
    )
    if station_polygons:
        for sb in station_polygons:
            if len(sb) >= 3 and polygons_overlap(deck_outline, sb):
                raise ValueError(
                    f"FOB placement conflict: FOB deck at chainage {fob_chainage:.3f} m "
                    f"conflicts with/overlaps station building footprint."
                )

    # 4. Restricted regions (crossovers, turnouts) conflict
    if restricted_regions:
        fob_lo = fob_chainage - fob_width / 2.0
        fob_hi = fob_chainage + fob_width / 2.0
        for r in restricted_regions:
            r_track = getattr(r, "track", None)
            if r_track == reference_track:
                r_lo = getattr(r, "start_chainage", getattr(r, "lo", None))
                r_hi = getattr(r, "end_chainage", getattr(r, "hi", None))
                if r_lo is not None and r_hi is not None:
                    if max(fob_lo, r_lo) < min(fob_hi, r_hi) - 1e-3:
                        label = getattr(r, "label", "restricted area")
                        raise ValueError(
                            f"FOB placement conflict: FOB deck at chainage {fob_chainage:.3f} m "
                            f"[{fob_lo:.2f}, {fob_hi:.2f}] conflicts with {label} "
                            f"[{r_lo:.2f}, {r_hi:.2f}]."
                        )
