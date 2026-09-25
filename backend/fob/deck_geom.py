"""FOB deck geometric calculation and layout routines."""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from common.constants import FOB_MAX_SPAN_M
from common.geometry import Point


def validate_fob_span(span_m: float) -> float:
    """Raise when a derived deck span exceeds the 30 m maximum."""
    try:
        span = float(span_m)
    except (TypeError, ValueError):
        raise ValueError(f"FOB span must be a number, got {span_m!r}.")
    if span > FOB_MAX_SPAN_M:
        raise ValueError(
            f"FOB span {span:.3f} m exceeds the maximum "
            f"{FOB_MAX_SPAN_M:g} m single span."
        )
    return span


def _order_outward(a: Point, b: Point, ox: float, oy: float) -> tuple[Point, Point]:
    """Order segment (a, b) so that its left-normal (-dy, dx) points in direction (ox, oy)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy) or 1.0
    if (-dy / length) * ox + (dx / length) * oy < 0:
        return b, a
    return a, b


def _line_param(
    origin: Point, direction: Point, edge_start: Point, edge_end: Point
) -> float | None:
    """Parameter t where origin + t*direction meets edge_start-end."""
    dx, dy = direction
    ex, ey = edge_end[0] - edge_start[0], edge_end[1] - edge_start[1]
    det = ex * dy - dx * ey
    if abs(det) < 1e-12:
        return None
    rx, ry = edge_start[0] - origin[0], edge_start[1] - origin[1]
    u = (dx * ry - dy * rx) / det
    if u < -1e-9 or u > 1.0 + 1e-9:
        return None
    t = (ex * ry - ey * rx) / det
    return t


def _axis_hits(origin: Point, normal: Point, polygon: Sequence[Point]) -> List[float]:
    """Projections (along normal) where the axis crosses a polygon."""
    ring = [(float(p[0]), float(p[1])) for p in polygon]
    if len(ring) >= 2 and math.hypot(ring[0][0] - ring[-1][0], ring[0][1] - ring[-1][1]) < 1e-6:
        ring = ring[:-1]
    hits: List[float] = []
    for start, end in zip(ring, ring[1:] + ring[:1]):
        t = _line_param(origin, normal, start, end)
        if t is not None:
            hits.append(t)
    return hits


def axis_spans(
    origin: Point, normal: Point, platform_polygons: Sequence[Sequence[Point]]
) -> List:
    """Per-platform (min, max) axis projections (None when missed)."""
    spans: List = []
    for polygon in platform_polygons:
        hits = _axis_hits(origin, normal, polygon)
        spans.append((min(hits), max(hits)) if len(hits) >= 2 else None)
    return spans


def build_fob_outline(
    origin: Point,
    tangent: Point,
    platform_polygons: Sequence[Sequence[Point]],
    width: float,
    extend_start: float = 0.0,
    extend_end: float = 0.0,
) -> List[Point]:
    """Closed 4-corner FOB deck outline (not repeated: writer closes it)."""
    try:
        width = float(width)
    except (TypeError, ValueError):
        raise ValueError(f"FOB width must be a number, got {width!r}.")
    if width <= 0:
        raise ValueError("FOB width must be > 0.")
    try:
        extend_start, extend_end = float(extend_start), float(extend_end)
    except (TypeError, ValueError):
        raise ValueError("FOB extensions must be numbers (metres, 0 = none).")
    if extend_start < 0 or extend_end < 0:
        raise ValueError("FOB extensions must be >= 0.")
    if not platform_polygons:
        raise ValueError("FOB needs at least one platform polygon.")
    tn = math.hypot(tangent[0], tangent[1])
    if tn < 1e-12:
        raise ValueError("FOB reference tangent must not be zero-length.")
    tx, ty = tangent[0] / tn, tangent[1] / tn
    nx, ny = -ty, tx
    spans = [span for span in axis_spans(origin, (nx, ny), platform_polygons) if span is not None]
    if not spans:
        raise ValueError(
            "FOB axis (perpendicular at the reference chainage) misses "
            "every selected platform - pick a chainage within the "
            "platforms' extent."
        )
    lo = min(span[0] for span in spans) - extend_start
    hi = max(span[1] for span in spans) + extend_end
    validate_fob_span(hi - lo)
    ox, oy = float(origin[0]), float(origin[1])
    hw = width / 2.0
    return [
        (ox - tx * hw + nx * lo, oy - ty * hw + ny * lo),
        (ox + tx * hw + nx * lo, oy + ty * hw + ny * lo),
        (ox + tx * hw + nx * hi, oy + ty * hw + ny * hi),
        (ox - tx * hw + nx * hi, oy - ty * hw + ny * hi),
    ]


def track_axis_hits(
    origin: Point, normal: Point, tracks: Dict[str, List[Point]]
) -> List[float]:
    """Projections (along normal) where any track crosses the axis."""
    hits: List[float] = []
    for points in tracks.values():
        ring = [(float(p[0]), float(p[1])) for p in points]
        for start, end in zip(ring, ring[1:]):
            t = _line_param(origin, normal, start, end)
            if t is not None:
                hits.append(t)
    return hits


def choose_label_spot(
    lo: float,
    hi: float,
    crossings: Sequence[float],
    text_len: float,
    margin: float = 1.0,
    blocked: Sequence[tuple] = (),
) -> float:
    """Axis projection for the deck label: midpoint of the widest track gap."""
    cuts = sorted({min(max(t, lo), hi) for t in crossings})
    bounds = [lo] + cuts + [hi]
    gaps = []
    for start, end in zip(bounds, bounds[1:]):
        if end - start >= text_len + 2.0 * margin:
            gaps.append(((start + end) / 2.0, end - start))
    gaps.sort(key=lambda gap: -gap[1])
    for mid, _length in gaps:
        if not any(blo - margin <= mid <= bhi + margin for blo, bhi in blocked):
            return mid
    return (lo + hi) / 2.0


def build_fob_arms(
    origin: Point,
    tangent: Point,
    normal: Point,
    spans_by_layer: Dict[str, object],
    arm_specs: Dict[str, dict],
    deck_width: float,
) -> List[List[Point]]:
    """Landing-arm outlines, one closed rectangle per specified platform."""
    tn = math.hypot(tangent[0], tangent[1])
    if tn < 1e-12:
        raise ValueError("FOB reference tangent must not be zero-length.")
    tx, ty = tangent[0] / tn, tangent[1] / tn
    nn = math.hypot(normal[0], normal[1]) or 1.0
    nx, ny = normal[0] / nn, normal[1] / nn
    ox, oy = float(origin[0]), float(origin[1])
    s0 = ox * tx + oy * ty
    hw = deck_width / 2.0

    def _pt(s, a):
        return (ox + tx * (s - s0) + nx * a, oy + ty * (s - s0) + ny * a)

    arms: List[List[Point]] = []
    for layer, span in spans_by_layer.items():
        spec = arm_specs.get(layer)
        if spec is None or span is None:
            continue
        length = float(spec["length"])
        stride = -1.0 if spec["side"] == "LEFT" else 1.0
        mid = (span[0] + span[1]) / 2.0
        s_in = s0 - hw if stride < 0 else s0 + hw
        s_out = s_in + stride * length
        low, high = mid - hw, mid + hw
        arms.append([_pt(s_in, low), _pt(s_out, low), _pt(s_out, high), _pt(s_in, high)])
    return arms


def _subtract_intervals(lo: float, hi: float, cuts: Sequence[tuple]) -> List[tuple]:
    """Pieces of [lo, hi] with the cuts axis intervals removed."""
    edges = sorted(set([lo, hi] + [c for iv in cuts for c in iv]))
    pieces = []
    for start, end in zip(edges, edges[1:]):
        if end - start > 1e-9 and not any(
            c0 - 1e-9 <= (start + end) / 2.0 <= c1 + 1e-9 for c0, c1 in cuts
        ):
            pieces.append((start, end))
    return pieces


def _deck_span(origin: Point, normal: Point, outline: Sequence[Point]) -> tuple:
    """Min/max axis projection of the deck corners."""
    projections = [(p[0] - origin[0]) * normal[0] + (p[1] - origin[1]) * normal[1] for p in outline]
    return min(projections), max(projections)
