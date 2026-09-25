"""Crossover geometry helpers: direction normalisation, separations, params, footprints."""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import (
    AUTO_SEARCH_STEP_M,
    CHAINAGE_TOL_M,
    OPPOSITE_DIRECTION_MIN_SEPARATION_M,
    SAME_DIRECTION_MIN_SEPARATION_M,
)
from common.geometry import (
    Point,
    nearest_point_on_alignment,
    point_at_chainage,
    polyline_length,
)
from track.crossover.footprints import (
    _segments_intersect,
    footprints_overlap,
    is_main_track,
    main_track_anchors,
    polyline_self_intersects,
)
from track.crossover.models import CrossoverRequest, CrossoverResult
from track.crossover.normalize import (
    is_auto_chainage,
    normalize_direction,
    normalize_placement,
    normalize_position_mode,
)


def get_required_separation(a, b) -> float:
    """Return the required minimum separation (m) between two crossovers."""
    def _dir(x) -> str:
        if isinstance(x, str):
            return normalize_direction(x)
        d = getattr(x, "direction", "FORWARD")
        return normalize_direction(d)

    da, db = _dir(a), _dir(b)
    if da == db:
        return SAME_DIRECTION_MIN_SEPARATION_M
    return OPPOSITE_DIRECTION_MIN_SEPARATION_M


def actual_separation(chainage_a: float, chainage_b: float) -> float:
    """Longitudinal separation along the reference alignment (chainage)."""
    return abs(float(chainage_b) - float(chainage_a))


def srj_positions_on_tracks(
    req, chainage: float, to_main: float
) -> dict[str, float]:
    """MAIN-datum SRJ position per track."""
    return {
        req.from_track: float(chainage),
        req.to_track: float(to_main),
    }


def _lateral_sign_on_main(main_points, off_pt) -> float | None:
    """Lateral side (+1 LEFT / -1 RIGHT) of an off-MAIN point."""
    off = lateral_offset_on_main(main_points, off_pt)
    if off is None or abs(off) < 1e-9:
        return None
    return 1.0 if off > 0 else -1.0


def lateral_offset_on_main(main_points, off_pt) -> float | None:
    """Signed lateral offset (m) of a point from a reference alignment."""
    try:
        pts = list(main_points or [])
        if len(pts) < 2:
            return None
        proj = nearest_point_on_alignment(pts, off_pt)
        sp = point_at_chainage(pts, proj.chainage)
        tx, ty = sp.tangent
        n = math.hypot(tx, ty) or 1.0
        tx, ty = tx / n, ty / n
        vx, vy = off_pt[0] - proj.point[0], off_pt[1] - proj.point[1]
        return float(-ty * vx + tx * vy)
    except Exception:
        return None


def reference_main_points(tracks):
    """Reference alignment for lateral strips: MAIN_LINE preferred."""
    tracks = tracks or {}
    if "MAIN_LINE" in tracks:
        return tracks["MAIN_LINE"]
    for key in sorted(tracks):
        if str(key).upper().startswith("MAIN"):
            return tracks[key]
    return None


def crossover_lateral_band(req, params, tracks) -> tuple[float, float] | None:
    """Lateral strip (lo, hi) of a crossover body vs the MAIN reference."""
    try:
        ref = reference_main_points(tracks)
        if ref is None:
            return None
        from_pt = params["from_pt"]
        to_pt = params["to_pt"]
        off_a = lateral_offset_on_main(ref, (float(from_pt[0]), float(from_pt[1])))
        off_b = lateral_offset_on_main(ref, (float(to_pt[0]), float(to_pt[1])))
        if off_a is None or off_b is None:
            return None
        return (min(off_a, off_b), max(off_a, off_b))
    except (KeyError, TypeError, ValueError):
        return None
    except Exception:
        return None


def bands_overlap(
    a: tuple[float, float] | None, b: tuple[float, float] | None
) -> bool:
    """True when two lateral strips strictly overlap (touching is OK)."""
    if a is None or b is None:
        return True
    a0, a1 = min(a), max(a)
    b0, b1 = min(b), max(b)
    return max(a0, b0) < min(a1, b1) - 1e-9


def is_opposite_side_pair(req_a, params_a, req_b, params_b, tracks) -> bool:
    """True when the two crossovers share ONLY one main line and their bodies lie on opposite sides."""
    try:
        set_a = {req_a.from_track, req_a.to_track}
        set_b = {req_b.from_track, req_b.to_track}
        shared = set_a & set_b
        if len(shared) != 1:
            return False
        (shared_track,) = tuple(shared)
        if not is_main_track(shared_track):
            return False
        ref_pts = (tracks or {}).get(shared_track)
        if not ref_pts or len(list(ref_pts)) < 2:
            return False
        off_a = (
            params_a["to_pt"]
            if req_a.from_track == shared_track
            else params_a["from_pt"]
        )
        off_b = (
            params_b["to_pt"]
            if req_b.from_track == shared_track
            else params_b["from_pt"]
        )
        sign_a = _lateral_sign_on_main(ref_pts, off_a)
        sign_b = _lateral_sign_on_main(ref_pts, off_b)
        return sign_a is not None and sign_b is not None and sign_a * sign_b < 0
    except (KeyError, TypeError, ValueError):
        return False
    except Exception:
        return False


def _track_length(points: Sequence[Point]) -> float:
    return polyline_length(points)


def _resolve_extents(
    extents: dict[str, tuple[float, float]] | None,
) -> dict[str, tuple[float, float]]:
    return dict(extents or {})


def _to_local(track_name: str, main_ch: float, extents) -> float:
    extent = (extents or {}).get(track_name)
    if extent is None:
        return float(main_ch)
    c1, _c2 = extent
    return float(main_ch) - float(c1)


def _check_chainage_in_extent(
    track_name: str, main_ch: float, extents
) -> tuple[bool, str | None]:
    extent = (extents or {}).get(track_name)
    if extent is None:
        return True, None
    c1, c2 = extent
    if not (c1 - CHAINAGE_TOL_M <= main_ch <= c2 + CHAINAGE_TOL_M):
        return False, (
            f"chainage {main_ch:.2f}m on {track_name} is outside "
            f"loop extent [{c1:.2f}, {c2:.2f}]m (MAIN chainages)."
        )
    return True, None


def compute_crossover_params(
    request: CrossoverRequest,
    chainage: float,
    tracks: dict[str, Sequence[Point]],
    extents: dict[str, tuple[float, float]] | None = None,
) -> dict:
    """Measure TC from real geometry and derive N/F/A/OL/footprint."""
    from track.crossover.core import standard_crossover_lengths
    from track.crossover.turnout import turnout_ratio_n
    from track.turnouts import NORMAL_SPACING_LIMIT_MM

    extents = _resolve_extents(extents)
    from_pts = tracks[request.from_track]
    to_pts = tracks[request.to_track]

    from_local = _to_local(request.from_track, chainage, extents)
    sp_from = point_at_chainage(from_pts, from_local)
    from_pt = sp_from.point

    proj = nearest_point_on_alignment(to_pts, from_pt)
    tc_m = float(proj.distance)
    if not math.isfinite(tc_m) or tc_m <= 1e-9:
        raise ValueError(
            f"Crossover {request.id}: tracks coincide at the START SRJ - "
            f"need two distinct parallel tracks."
        )
    tc_mm = tc_m * 1000.0

    if request.turnout is None:
        raise ValueError(
            f"Crossover {request.id}: no turnout selected - "
            f"select 1:8.5 or 1:12 from the verified turnout library."
        )
    turnout = request.turnout
    n = turnout_ratio_n(turnout)
    f = math.atan(1.0 / n)
    a_mm = float(turnout.a_mm)
    b_mm = float(getattr(turnout, "b_mm", 0.0) or 0.0)
    r_mm = getattr(turnout, "radius_mm", None)
    r_mm = float(r_mm) if r_mm else None

    placement = normalize_placement(request.placement, request.direction)
    sign = 1.0 if placement == "AHEAD" else -1.0

    if tc_mm <= NORMAL_SPACING_LIMIT_MM:
        lens = standard_crossover_lengths(tc_mm, turnout)
        ol_mm = float(lens["ol_mm"])
        crossover_type = "normal_spacing"
        extra: dict = {
            "x_mm": float(lens["x_mm"]),
            "stored_f_deg": lens.get("stored_f_deg"),
            "stored_f_mismatch": bool(lens.get("stored_f_mismatch")),
        }
    else:
        if r_mm is None or not math.isfinite(r_mm) or r_mm <= 0:
            raise ValueError(
                f"Crossover {request.id}: TC={tc_mm:.0f}mm exceeds "
                f"{NORMAL_SPACING_LIMIT_MM:.0f}mm so the reverse-curve "
                f"formulation applies, but turnout "
                f"{getattr(turnout, 'designation', '?')} has no verified "
                f"radius R."
            )
        radius = float(r_mm)
        cos_f, sin_f = math.cos(f), math.sin(f)
        argument = (radius * cos_f + b_mm * sin_f - tc_mm / 2.0) / radius
        if not -1.0 <= argument <= 1.0:
            raise ValueError(
                f"Crossover {request.id}: turnout and TC={tc_mm:.0f}mm "
                f"produce an invalid reverse-curve angle."
            )
        theta = math.acos(argument)
        tangent = radius * math.tan((theta - f) / 2.0)
        x = 2.0 * ((b_mm + tangent) * cos_f + tangent * math.cos(theta))
        if tangent < 0 or x <= 0:
            raise ValueError(
                f"Crossover {request.id}: turnout and TC={tc_mm:.0f}mm "
                f"produce invalid reverse-curve lengths."
            )
        ol_mm = float(x + 2.0 * a_mm)
        crossover_type = "large_spacing_reverse_curves"
        extra = {"theta_rad": theta, "tangent_mm": tangent, "x_mm": float(x)}

    ol_m = ol_mm / 1000.0
    to_main = float(chainage) + sign * ol_m
    if placement == "AHEAD":
        start_ch, end_ch = float(chainage), float(to_main)
    else:
        start_ch, end_ch = float(to_main), float(chainage)

    try:
        to_local = _to_local(request.to_track, to_main, extents)
        sp_to = point_at_chainage(to_pts, to_local)
    except ValueError as exc:
        raise ValueError(
            f"Crossover {request.id}: second SRJ at {to_main:.2f}m "
            f"(START {'+' if sign > 0 else '-'} OL={ol_m:.3f}m) does not "
            f"fit - {exc}"
        ) from exc

    return {
        "tc_m": tc_m,
        "tc_mm": tc_mm,
        "n": n,
        "f_rad": f,
        "f_deg": math.degrees(f),
        "a_mm": a_mm,
        "b_mm": b_mm,
        "r_mm": r_mm,
        "ol_mm": ol_mm,
        "ol_m": ol_m,
        "crossover_type": crossover_type,
        "placement": placement,
        "sign": sign,
        "from_pt": from_pt,
        "from_tangent": sp_from.tangent,
        "to_pt": sp_to.point,
        "to_tangent": sp_to.tangent,
        "to_main": to_main,
        "start_chainage": start_ch,
        "end_chainage": end_ch,
        **extra,
    }


def build_crossover_geometry(
    request: CrossoverRequest,
    params: dict,
) -> tuple[list, dict]:
    """Build the turnout-based centreline for one crossover."""
    from track.crossover.core import (
        _build_reverse_curve_crossover,
        build_standard_crossover,
    )

    turnout = request.turnout
    from_pt = params["from_pt"]
    to_pt = params["to_pt"]
    from_tangent = params["from_tangent"]
    to_tangent = params["to_tangent"]

    placement = params.get("placement", "AHEAD")
    if placement == "BEHIND":
        from_tangent = (-from_tangent[0], -from_tangent[1])
        to_tangent = (-to_tangent[0], -to_tangent[1])

    if params["crossover_type"] == "normal_spacing":
        return build_standard_crossover(
            from_pt, from_tangent, to_pt, to_tangent, turnout
        )

    def _unit(v):
        n = math.hypot(v[0], v[1]) or 1.0
        return (v[0] / n, v[1] / n)

    u = _unit(from_tangent)
    v = _unit(to_tangent)
    if u[0] * v[0] + u[1] * v[1] < 0.0:
        v = (-v[0], -v[1])
    wx, wy = to_pt[0] - from_pt[0], to_pt[1] - from_pt[1]
    cross = u[0] * wy - u[1] * wx
    s = 1.0 if cross >= 0 else -1.0
    alignment = u
    normal = (-u[1] * s, u[0] * s)
    a_m = params["a_mm"] / 1000.0
    b_m = params["b_mm"] / 1000.0
    default_r_mm = 232260.0 if params.get("n") == 8.5 else 441360.0
    r_m = (params["r_mm"] or default_r_mm) / 1000.0
    theta = params.get("theta_rad")
    tangent_m = params.get("tangent_mm", 0.0) / 1000.0
    if theta is None:
        raise ValueError(
            f"Crossover {request.id}: missing reverse-curve angle theta."
        )
    pts = _build_reverse_curve_crossover(
        from_pt,
        to_pt,
        alignment,
        normal,
        a_m=a_m,
        b_m=b_m,
        radius_m=r_m,
        theta=theta,
        tangent_m=tangent_m,
    )
    report = {
        "tc_m": params["tc_m"],
        "tc_mm": params["tc_mm"],
        "n": params["n"],
        "f_rad": params["f_rad"],
        "f_deg": params["f_deg"],
        "side": "LEFT" if s > 0 else "RIGHT",
        "r_lib_m": r_m,
        "r_used_m": r_m,
        "r_constrained": False,
        "diag_len_m": math.hypot(wx, wy),
        "n_points": len(pts),
        "parallel_deg": math.degrees(
            math.acos(min(max(u[0] * v[0] + u[1] * v[1], -1.0), 1.0))
        ),
        "warnings": [],
    }
    return pts, report


__all__ = [
    "_check_chainage_in_extent",
    "_lateral_sign_on_main",
    "_resolve_extents",
    "_segments_intersect",
    "_to_local",
    "_track_length",
    "actual_separation",
    "bands_overlap",
    "build_crossover_geometry",
    "compute_crossover_params",
    "crossover_lateral_band",
    "footprints_overlap",
    "get_required_separation",
    "is_auto_chainage",
    "is_main_track",
    "is_opposite_side_pair",
    "lateral_offset_on_main",
    "main_track_anchors",
    "normalize_direction",
    "normalize_placement",
    "normalize_position_mode",
    "polyline_self_intersects",
    "reference_main_points",
    "srj_positions_on_tracks",
]
