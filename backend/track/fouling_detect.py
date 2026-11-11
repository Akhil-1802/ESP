"""Fouling Mark (FM) detection and chainage calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Dict, List, Sequence

from common.constants import MIN_TRACK_SPACING_M
from common.geometry import (
    Point,
    nearest_point_on_alignment,
    point_at_chainage,
    polyline_length,
)

FM_LAYER: str = "FM"
FM_COLOR: int = 1
FM_STEM_M: float = 2.0
FM_TRI_SIDE_M: float = 2.0
FM_DISK_RADIUS_M: float = 1.0
FM_TICK_HALF_M: float = 1.0
FM_TICK_WIDTH_M: float = 0.25
FM_TICK_LINEWEIGHT: int = 80
FM_TEXT_HEIGHT_M: float = 1.0
FM_SRJ_CLEARANCE_M: float = 4.0

FM_DETECT_MARGIN_M: float = 0.05
FM_CLASS_EPS_M: float = 1e-4
FM_CHAINAGE_TOL_M: float = 0.01
FM_SCAN_STEP_M: float = 2.0
FM_DEDUPE_M: float = 2.0
FM_SEARCH_MARGIN_M: float = 25.0


@dataclass
class FoulingMark:
    """One FM location on ``track`` at ``chainage_main`` (MAIN datum, m)."""

    track: str
    chainage_main: float
    local_chainage: float
    point: Point
    tangent: Point
    other_track: str
    other_chainage_main: float
    other_point: Point
    spacing_m: float = field(default=0.0)
    display_point: Point | None = None
    display_tangent: Point | None = None


def fouling_threshold_m() -> float:
    """Applicable minimum centre-to-centre spacing (m)."""
    return float(MIN_TRACK_SPACING_M)


def _clean(points: Sequence[Point]) -> List[Point]:
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 2:
        raise ValueError("Need at least two points for fouling detection.")
    return pts


def _dist_to_other(
    other_pts: List[Point], query: Point
) -> tuple[float, Point, float]:
    """(distance, nearest point on other, its local chainage)."""
    proj = nearest_point_on_alignment(other_pts, query)
    return (
        float(proj.distance),
        (float(proj.point[0]), float(proj.point[1])),
        float(proj.chainage),
    )


def _local_to_main(track: str, local: float, extents: Dict[str, tuple]) -> float:
    ext = (extents or {}).get(track)
    if ext is None:
        return float(local)
    return float(local) + float(ext[0])


def _main_to_local(
    track: str, main_ch: float, extents: Dict[str, tuple]
) -> float:
    ext = (extents or {}).get(track)
    if ext is None:
        return float(main_ch)
    return float(main_ch) - float(ext[0])


def _is_foul(dist: float, threshold: float) -> bool:
    """Foul when clearly below the minimum (clear inside epsilon)."""
    return float(dist) < float(threshold) - FM_CLASS_EPS_M


def _bisect_boundary(
    track_pts: List[Point],
    other_pts: List[Point],
    lo_ch: float,
    hi_ch: float,
    threshold: float,
) -> float:
    """Refine the fouling boundary between a foul and a clear chainage."""
    total = polyline_length(track_pts)
    lo = min(max(float(lo_ch), 0.0), total)
    hi = min(max(float(hi_ch), 0.0), total)
    d_lo = _dist_to_other(other_pts, point_at_chainage(track_pts, lo).point)[0]
    d_hi = _dist_to_other(other_pts, point_at_chainage(track_pts, hi).point)[0]
    lo_foul = _is_foul(d_lo, threshold)
    hi_foul = _is_foul(d_hi, threshold)
    if lo_foul == hi_foul:
        return lo if abs(d_lo - threshold) <= abs(d_hi - threshold) else hi
    for _ in range(60):
        if abs(hi - lo) <= FM_CHAINAGE_TOL_M:
            break
        mid = 0.5 * (lo + hi)
        d_mid = _dist_to_other(
            other_pts, point_at_chainage(track_pts, mid).point
        )[0]
        if _is_foul(d_mid, threshold) == lo_foul:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _scan_profile(
    track_pts: List[Point],
    other_pts: List[Point],
    threshold: float,
    start: float = 0.0,
    end: float | None = None,
    step: float = FM_SCAN_STEP_M,
) -> tuple[List[float], List[float]]:
    """Sample spacing profile along ``track_pts`` in [start, end]."""
    total = polyline_length(track_pts)
    if end is None:
        end = total
    start = min(max(float(start), 0.0), total)
    end = min(max(float(end), 0.0), total)
    if end < start:
        start, end = end, start
    chs: List[float] = []
    dists: List[float] = []
    ch = start
    while True:
        pt = point_at_chainage(track_pts, min(ch, total)).point
        dists.append(_dist_to_other(other_pts, pt)[0])
        chs.append(min(ch, total))
        if ch >= end - 1e-9:
            break
        ch = min(ch + step, end)
    return chs, dists


def _boundaries_in_range(
    track_pts: List[Point],
    other_pts: List[Point],
    threshold: float,
    start: float,
    end: float,
) -> List[float]:
    """All foul/clear boundary chainages (local) within [start, end]."""
    chs, dists = _scan_profile(track_pts, other_pts, threshold, start, end)
    detect = threshold - FM_DETECT_MARGIN_M
    if not any(d < detect for d in dists):
        return []
    bounds: List[float] = []
    for c0, c1, d0, d1 in zip(chs, chs[1:], dists, dists[1:]):
        if _is_foul(d0, threshold) != _is_foul(d1, threshold):
            bounds.append(
                _bisect_boundary(track_pts, other_pts, c0, c1, threshold)
            )
    return bounds


def _dedupe(marks: List[FoulingMark]) -> List[FoulingMark]:
    """Collapse near-duplicate FMs (keeps first)."""
    kept: List[FoulingMark] = []
    for mark in sorted(marks, key=lambda m: (m.track, m.chainage_main)):
        dup = False
        pt = mark.point
        other_pt = getattr(mark, "other_point", None) or pt
        curr_mid = ((pt[0] + other_pt[0]) * 0.5, (pt[1] + other_pt[1]) * 0.5)
        for prev in kept:
            prev_pt = prev.point
            prev_other = getattr(prev, "other_point", None) or prev_pt
            prev_mid = (
                (prev_pt[0] + prev_other[0]) * 0.5,
                (prev_pt[1] + prev_other[1]) * 0.5,
            )
            if (
                prev.track == mark.track
                and abs(prev.chainage_main - mark.chainage_main) < FM_DEDUPE_M
            ):
                dup = True
                break
            if (
                math.hypot(prev_mid[0] - curr_mid[0], prev_mid[1] - curr_mid[1])
                < 3.0
            ):
                dup = True
                break
        if not dup:
            kept.append(mark)
    return kept


def _turnout_a_m(res) -> float | None:
    """Turnout A (m) for a crossover result (SRJ to PI, ``a_mm``)."""
    for candidate in (
        getattr(res, "a_mm", None),
        getattr(getattr(res, "turnout", None), "a_mm", None),
    ):
        try:
            value = float(candidate) / 1000.0
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            return value
    return None


def _make_mark(
    track: str,
    local_ch: float,
    track_pts: List[Point],
    other_track: str,
    other_pts: List[Point],
    extents: Dict[str, tuple],
    threshold: float,
) -> FoulingMark:
    """Build one FM at ``local_ch`` on ``track`` (nearest point on other)."""
    total = polyline_length(track_pts)
    local_ch = min(max(float(local_ch), 0.0), total)
    station = point_at_chainage(track_pts, local_ch)
    dist, other_pt, other_local = _dist_to_other(other_pts, station.point)
    return FoulingMark(
        track=track,
        chainage_main=_local_to_main(track, local_ch, extents),
        local_chainage=float(local_ch),
        point=(float(station.point[0]), float(station.point[1])),
        tangent=(float(station.tangent[0]), float(station.tangent[1])),
        other_track=other_track,
        other_chainage_main=_local_to_main(other_track, other_local, extents),
        other_point=other_pt,
        spacing_m=float(dist),
    )


def collect_fouling_marks(
    tracks: Dict[str, List[Point]],
    extents: Dict[str, tuple] | None = None,
    crossover_results: Sequence[object] | None = None,
    siding_results: Sequence[tuple] | None = None,
    include_siding_marks: bool = True,
) -> List[FoulingMark]:
    """Automatically derive every FM from finished centreline geometry."""
    extents = dict(extents or {})
    threshold = fouling_threshold_m()
    cleaned: Dict[str, List[Point]] = {}
    for name, pts in (tracks or {}).items():
        try:
            cleaned[name] = _clean(pts)
        except ValueError:
            continue

    marks: List[FoulingMark] = []
    crossover_items = list(crossover_results or [])

    for res in crossover_items:
        try:
            from_track = getattr(res, "from_track", None)
            to_track = getattr(res, "to_track", None)
            start_main = float(
                getattr(res, "chainage", getattr(res, "start_chainage", 0.0))
            )
        except (TypeError, ValueError):
            continue
        if from_track not in cleaned or to_track not in cleaned:
            continue
        a_m = _turnout_a_m(res)
        if a_m is None:
            continue
        try:
            placement = str(getattr(res, "placement", "") or "").strip().upper()
            if placement not in ("AHEAD", "BEHIND"):
                direction = str(
                    getattr(res, "direction", "FORWARD") or "FORWARD"
                ).strip().upper()
                placement = (
                    "BEHIND"
                    if direction in ("REVERSE", "BEHIND", "REV", "R")
                    else "AHEAD"
                )
            second_main = float(
                res.end_chainage
                if placement == "AHEAD"
                else res.start_chainage
            )
        except (TypeError, ValueError, AttributeError):
            continue
        sign = 1.0 if placement == "AHEAD" else -1.0
        tc_m = getattr(res, "track_centre_m", None)
        if tc_m is None:
            tc_m = getattr(res, "tc_m", None)
        if tc_m is None and hasattr(res, "track_centre_mm") and res.track_centre_mm is not None:
            tc_m = float(res.track_centre_mm) / 1000.0
        if tc_m is None:
            try:
                local_s = _main_to_local(from_track, start_main, extents)
                stn = point_at_chainage(cleaned[from_track], local_s)
                dist, _, _ = _dist_to_other(cleaned[to_track], stn.point)
                tc_m = dist
            except Exception:
                tc_m = 5.3

        fm_from_main = start_main
        fm_to_main = second_main

        try:
            local_from = _main_to_local(
                from_track, fm_from_main, extents
            )
            marks.append(
                _make_mark(
                    from_track,
                    local_from,
                    cleaned[from_track],
                    to_track,
                    cleaned[to_track],
                    extents,
                    threshold,
                )
            )
            local_to = _main_to_local(
                to_track, fm_to_main, extents
            )
            marks.append(
                _make_mark(
                    to_track,
                    local_to,
                    cleaned[to_track],
                    from_track,
                    cleaned[from_track],
                    extents,
                    threshold,
                )
            )
        except ValueError:
            continue

    for item in list(siding_results or []) if include_siding_marks else []:
        try:
            spec, result = item
            source = getattr(spec, "source_track", None)
            direction = str(getattr(spec, "direction", "FORWARD")).upper()
            div_pts = _clean(list(getattr(result, "points", None) or []))
        except (ValueError, TypeError, AttributeError):
            continue
        if source not in cleaned:
            continue
        try:
            start_main = float(getattr(spec, "start_chainage_m", 0.0))
            total_src = polyline_length(cleaned[source])
            if direction == "REVERSE":
                lo = _main_to_local(
                    source,
                    start_main
                    - polyline_length(div_pts)
                    - FM_SEARCH_MARGIN_M,
                    extents,
                )
                hi = _main_to_local(source, start_main, extents)
            else:
                lo = _main_to_local(source, start_main, extents)
                hi = _main_to_local(
                    source,
                    start_main
                    + polyline_length(div_pts)
                    + FM_SEARCH_MARGIN_M,
                    extents,
                )
            lo = min(max(lo, 0.0), total_src)
            hi = min(max(hi, 0.0), total_src)
            bounds = _boundaries_in_range(
                cleaned[source], div_pts, threshold, min(lo, hi), max(lo, hi)
            )
        except (ValueError, TypeError):
            bounds = []
        for local in bounds[:1]:
            marks.append(
                _make_mark(
                    source,
                    local,
                    cleaned[source],
                    f"SIDING_{getattr(spec, 'id', '') or ''}".rstrip("_")
                    or "SIDING",
                    div_pts,
                    extents,
                    threshold,
                )
            )

    return _dedupe(marks)
