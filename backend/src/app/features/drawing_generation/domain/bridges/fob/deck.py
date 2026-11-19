"""FOB deck generation and DXF output."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from ...constants import (
    DEFAULT_FOB_OFFSET_M,
    DEFAULT_FOB_WIDTH_M,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
)
from ...geometry.alignment import nearest_point_on_alignment, point_at_chainage

from ...geometry.stationing import absolute_track_distance, parse_absolute_chainage

FOB_DEFAULT_WIDTH_M: float = DEFAULT_FOB_WIDTH_M
FOB_LABEL: str = "FOOT OVER BRIDGE"
FOB_LABEL_HEIGHT: float = 1.0
from ....formats.dxf.primitives import add_line as _add_line
from ....formats.dxf.primitives import add_polyline as _add_polyline
from ....formats.dxf.primitives import add_text as _add_text
from ....formats.dxf.primitives import draw_arrow_dimension as _draw_arrow_dimension
from ....formats.dxf.styles import ensure_layer as _ensure_layer
from ...geometry.operations import Point, polyline_length
from .config import FOBConfig, validate_fob_clearance
from .deck_geom import (
    _deck_span,
    _order_outward,
    _subtract_intervals,
    axis_spans,
    build_fob_arms,
    build_fob_outline,
    choose_label_spot,
    track_axis_hits,
    validate_fob_span,
)
from .placement import (
    calculate_fob_chainage,
    determine_station_edge,
    get_fob_track_position,
    normalize_fob_direction,
    validate_fob_conflicts,
    validate_fob_offset,
)


def write_fob_deck(doc, outline: Sequence[Point], layer: str, color: int = 1) -> None:
    """Write the deck outline (closed polyline) on its own layer."""
    _ensure_layer(doc, layer, color)
    _add_polyline(
        doc, [(float(p[0]), float(p[1])) for p in outline], layer, color, close=True
    )


def resolve_fob_chainage(
    cfg: FOBConfig,
    tracks: Dict[str, List[Point]],
    polygons_by_layer: Dict[str, Any] | None = None,
    doc=None,
    station_requests=None,
    station_markers=None,
    alignment_config=None,
) -> float:
    """Resolve and cache the FOB chainage along cfg.reference_track."""
    if getattr(cfg, "fob_chainage", None) is not None:
        return float(cfg.fob_chainage)

    if cfg.absolute_chainage is not None:
        if alignment_config is None:
            raise ValueError("FOB absolute placement requires the alignment start datum.")
        local = absolute_track_distance(
            alignment_config, parse_absolute_chainage(cfg.absolute_chainage), tracks, cfg.reference_track, "FOB"
        )
        cfg.reference_chainage = local
        cfg.fob_chainage = local
        return local

    ref_track = cfg.reference_track if cfg.reference_track in tracks else "MAIN_LINE"
    if ref_track not in tracks:
        ref_track = next(iter(tracks))
    points = tracks[ref_track]
    total = polyline_length(points)

    is_main_center = (
        cfg.reference_chainage is None
        or (
            isinstance(cfg.reference_chainage, str)
            and cfg.reference_chainage.strip().upper() in ("MAIN_CENTER", "AUTO", "")
        )
    )

    polys = polygons_by_layer or {}
    station_geom = None
    for name in ("STATION-BUILDING", "STATION_BUILDING"):
        if name in polys:
            station_geom = polys[name]
            break
    if station_geom is None and doc is not None and hasattr(doc, "modelspace"):
        for e in list(doc.modelspace()):
            try:
                if (
                    getattr(e.dxf, "layer", "") in ("STATION-BUILDING", "STATION_BUILDING")
                    and e.dxftype() in ("LWPOLYLINE", "POLYLINE")
                ):
                    from ...platform.track import _extract_points

                    station_geom = _extract_points(e)
                    if len(station_geom) >= 3:
                        break
            except Exception:
                pass
    if station_geom is None and polys:
        station_geom = [polys[p] for p in cfg.platforms if p in polys]

    center_ch = None
    if (
        station_geom
        and isinstance(station_geom, list)
        and isinstance(station_geom[0], (tuple, list))
    ):
        if len(station_geom[0]) >= 2 and isinstance(
            station_geom[0][0], (int, float)
        ):
            scx = sum(p[0] for p in station_geom) / len(station_geom)
            scy = sum(p[1] for p in station_geom) / len(station_geom)
            center_ch = float(
                nearest_point_on_alignment(points, (scx, scy)).chainage
            )
        else:
            all_pts = [p for poly in station_geom for p in poly]
            if all_pts:
                scx = sum(p[0] for p in all_pts) / len(all_pts)
                scy = sum(p[1] for p in all_pts) / len(all_pts)
                center_ch = float(
                    nearest_point_on_alignment(points, (scx, scy)).chainage
                )

    if center_ch is None and station_requests:
        for s_req in station_requests:
            s_ch = getattr(s_req, "station_chainage", None) or getattr(s_req, "chainage", None)
            if s_ch is not None:
                try:
                    center_ch = float(s_ch)
                    break
                except (ValueError, TypeError):
                    pass

    if center_ch is None or center_ch <= 0.0:
        center_ch = total / 2.0

    if is_main_center:
        ref_chainage = float(center_ch)
    else:
        try:
            ref_chainage = float(cfg.reference_chainage)
        except (ValueError, TypeError):
            ref_chainage = float(center_ch)

    pos_mode = str(getattr(cfg, "position_mode", "") or "").upper()
    is_fixed = pos_mode == "FIXED" or (not pos_mode and cfg.offset is None)

    if is_fixed:
        chainage = ref_chainage
    else:
        off = float(cfg.offset) if cfg.offset is not None else DEFAULT_FOB_OFFSET_M
        dir_norm = normalize_fob_direction(cfg.direction)
        station_edge_ch = None
        if station_geom is not None:
            try:
                station_edge_ch = determine_station_edge(
                    points, station_geom, dir_norm
                )
            except Exception:
                station_edge_ch = None
        if station_edge_ch is None and station_requests:
            try:
                s_req = station_requests[0]
                b_len = float(getattr(s_req, "building_length", 40.0) or 40.0)
                half_len = b_len / 2.0
                if dir_norm == "INCREASING":
                    station_edge_ch = center_ch + half_len
                else:
                    station_edge_ch = center_ch - half_len
            except Exception:
                station_edge_ch = None

        base_ch = (
            station_edge_ch if station_edge_ch is not None else ref_chainage
        )

        arm_towards_station = 0.0
        towards_side = "LEFT" if dir_norm == "INCREASING" else "RIGHT"
        for arm_spec in (cfg.arms or {}).values():
            if (
                isinstance(arm_spec, dict)
                and str(arm_spec.get("side", "")).upper() in (towards_side, "BOTH")
            ):
                arm_towards_station = max(
                    arm_towards_station, float(arm_spec.get("length", 0.0))
                )
        extra_to_center = (float(cfg.width) / 2.0) + arm_towards_station

        if dir_norm == "INCREASING":
            chainage = base_ch + off + extra_to_center
        else:
            chainage = base_ch - (off + extra_to_center)

    cfg.reference_chainage = chainage
    cfg.fob_chainage = chainage
    return chainage


def generate_fob(
    doc,
    tracks: Dict[str, List[Point]],
    extents: Dict[str, tuple],
    polygons_by_layer: Dict[str, List[Point]],
    cfg: FOBConfig,
):
    """Resolve one FOBConfig, build its deck and write it. Returns outline.

    ``tracks`` maps track name -> centreline points (as produced by
    ``TrackGenerator``); ``extents`` maps bounded-loop name -> effective
    (C1, C2) MAIN chainages for MAIN-datum conversion (same convention
    as crossovers); ``polygons_by_layer`` maps platform output layer ->
    platform outline.
    """
    validate_fob_clearance(
        getattr(cfg, "vertical_clearance_m", FOB_VERTICAL_CLEARANCE_M)
    )
    if cfg.reference_track not in tracks:
        known = ", ".join(sorted(tracks)) or "(none)"
        raise ValueError(
            f"FOB references unknown track {cfg.reference_track!r} - "
            f"available: {known}."
        )
    missing = [name for name in cfg.platforms if name not in polygons_by_layer]
    if missing:
        known = ", ".join(sorted(polygons_by_layer)) or "(none)"
        raise ValueError(
            f"FOB references unknown platform(s) {missing!r} - "
            f"available: {known}."
        )
    points = tracks[cfg.reference_track]
    total = polyline_length(points)

    chainage = resolve_fob_chainage(cfg, tracks, polygons_by_layer=polygons_by_layer, doc=doc)

    if not 0.0 <= chainage <= total:
        raise ValueError(
            f"FOB reference chainage {chainage:.3f} m is outside "
            f"{cfg.reference_track} [0, {total:.3f}] MAIN m."
        )
    extent = extents.get(cfg.reference_track)
    local = chainage - extent[0] if extent is not None and cfg.absolute_chainage is None else chainage
    local = min(max(local, 0.0), polyline_length(points))
    station = point_at_chainage(points, local)
    tn = math.hypot(station.tangent[0], station.tangent[1]) or 1.0
    normal = (-station.tangent[1] / tn, station.tangent[0] / tn)
    names = list(cfg.platforms)
    polys = [polygons_by_layer[name] for name in names]
    spans = dict(zip(names, axis_spans(station.point, normal, polys)))
    arms = build_fob_arms(
        station.point, station.tangent, normal, spans, cfg.arms, cfg.width,
        tracks=tracks,
    )
    arm_bounds = None
    if arms:
        ox_tmp, oy_tmp = float(station.point[0]), float(station.point[1])
        arm_projs = [(p[0] - ox_tmp) * normal[0] + (p[1] - oy_tmp) * normal[1] for arm in arms for p in arm]
        if arm_projs:
            arm_bounds = (min(arm_projs), max(arm_projs))

    outline = build_fob_outline(
        station.point,
        station.tangent,
        polys,
        cfg.width,
        cfg.extend_start_m,
        cfg.extend_end_m,
        arm_bounds=arm_bounds,
    )
    layer, color = cfg.output_layer, cfg.color
    _ensure_layer(doc, layer, color)
    ox, oy = float(station.point[0]), float(station.point[1])
    ttn = math.hypot(station.tangent[0], station.tangent[1]) or 1.0
    tx, ty = station.tangent[0] / ttn, station.tangent[1] / ttn
    nx, ny = normal
    hw = float(cfg.width) / 2.0
    lo_span, hi_span = _deck_span(station.point, normal, outline)

    # When platforms have landing arms, terminate the bridge at the outer edge
    # of the arms rather than extending all the way to merge with the platform outer edge.
    valid_spans = [(name, spans[name]) for name in names if spans.get(name) is not None]
    if valid_spans and arms:
        arm_projections = [
            (p[0] - ox) * nx + (p[1] - oy) * ny
            for arm in arms
            for p in arm
        ]
        if arm_projections:
            arm_outer_lo = min(arm_projections)
            arm_outer_hi = max(arm_projections)

            valid_spans.sort(key=lambda item: item[1][0])
            low_plat_name, _ = valid_spans[0]
            high_plat_name, _ = valid_spans[-1]

            if (cfg.arms or {}).get(low_plat_name):
                lo_span = arm_outer_lo - float(getattr(cfg, "extend_start_m", 0.0) or 0.0)
            if (cfg.arms or {}).get(high_plat_name):
                hi_span = arm_outer_hi + float(getattr(cfg, "extend_end_m", 0.0) or 0.0)

    def _wpt(s, a):
        return (ox + tx * s + nx * a, oy + ty * s + ny * a)

    if arms:
        outline = [
            _wpt(-hw, lo_span),
            _wpt(hw, lo_span),
            _wpt(hw, hi_span),
            _wpt(-hw, hi_span),
        ]

    if not arms:
        write_fob_deck(doc, outline, layer, color)
    else:
        left_cuts, right_cuts = [], []
        for arm in arms:
            ts = [(p[0] - ox) * tx + (p[1] - oy) * ty for p in arm]
            aa = [(p[0] - ox) * nx + (p[1] - oy) * ny for p in arm]
            iv = (min(aa), max(aa))
            if max(ts) <= -hw + 1e-6:
                left_cuts.append(iv)
            elif min(ts) >= hw - 1e-6:
                right_cuts.append(iv)
        _add_line(doc, _wpt(-hw, lo_span), _wpt(hw, lo_span), layer, color)
        _add_line(doc, _wpt(-hw, hi_span), _wpt(hw, hi_span), layer, color)
        for side, cuts in ((-hw, left_cuts), (hw, right_cuts)):
            for a0, a1 in _subtract_intervals(lo_span, hi_span, cuts):
                _add_line(doc, _wpt(side, a0), _wpt(side, a1), layer, color)
        for arm in arms:
            _add_polyline(
                doc,
                [(float(p[0]), float(p[1])) for p in arm],
                layer,
                color,
                close=False,
            )

    rot_deg = math.degrees(math.atan2(ny, nx))
    crossings = track_axis_hits(station.point, normal, tracks)
    blocked = []
    for arm in arms:
        proj = [
            (p[0] - station.point[0]) * normal[0]
            + (p[1] - station.point[1]) * normal[1]
            for p in arm
        ]
        blocked.append((min(proj), max(proj)))

    # Determine widest unblocked track gap to size the label appropriately
    inner_cuts = [
        c for c in sorted({min(max(t, lo_span), hi_span) for t in crossings})
        if lo_span + 1e-4 < c < hi_span - 1e-4
    ]
    bounds = [lo_span] + inner_cuts + [hi_span]
    max_gap_len = 0.0
    for s_start, s_end in zip(bounds, bounds[1:]):
        s_mid = (s_start + s_end) / 2.0
        if not any(min(blo, bhi) - 1e-3 <= s_mid <= max(blo, bhi) + 1e-3 for blo, bhi in blocked):
            max_gap_len = max(max_gap_len, s_end - s_start)

    char_count = len(FOB_LABEL)
    cfg_lbl_h = getattr(cfg, "label_height", None)
    if cfg_lbl_h is not None:
        label_h = float(cfg_lbl_h)
    elif max_gap_len > 0:
        # Leave at least 0.8m margin (0.4m on each end) from track centerlines
        avail_len = max(1.5, max_gap_len - 0.8)
        target_h = avail_len / (char_count * 0.7)
        label_h = min(FOB_LABEL_HEIGHT, max(0.25, target_h))
    else:
        label_h = 0.4

    label_h = max(label_h, 0.25)
    text_len = char_count * label_h * 0.7
    spot = choose_label_spot(
        lo_span, hi_span, crossings, text_len, margin=0.4, blocked=blocked
    )

    # Center text both along the bridge span (spot) and across the bridge deck width (ox, oy)
    center_x = ox + nx * spot
    center_y = oy + ny * spot
    _add_text(
        doc,
        FOB_LABEL,
        (center_x, center_y),
        cfg.output_layer,
        cfg.color,
        height=label_h,
        rotation=rot_deg,
        align="MIDDLE_CENTER",
        resolve=False,
    )

    dim_layer = getattr(cfg, "dimension_layer", "") or f"{cfg.output_layer}-DIM"
    _ensure_layer(doc, dim_layer, color)
    dw_a, dw_b = _order_outward(_wpt(-hw, hi_span), _wpt(hw, hi_span), nx, ny)
    _draw_arrow_dimension(
        doc,
        dw_a,
        dw_b,
        dim_offset=2.0,
        text=f"{cfg.width:.2f}",
        layer=dim_layer,
        color=color,
        height=0.8,
    )

    for arm in arms:
        p_in_low, p_out_low, p_out_high, p_in_high = arm
        arm_dx = p_out_low[0] - p_in_low[0]
        arm_dy = p_out_low[1] - p_in_low[1]
        arm_len = math.hypot(arm_dx, arm_dy) or 1.0
        arm_out_x, arm_out_y = arm_dx / arm_len, arm_dy / arm_len
        arm_a, arm_b = _order_outward(
            p_out_low, p_out_high, arm_out_x, arm_out_y
        )
        arm_width = math.hypot(
            p_out_high[0] - p_out_low[0], p_out_high[1] - p_out_low[1]
        )
        _draw_arrow_dimension(
            doc,
            arm_a,
            arm_b,
            dim_offset=-2.0,
            text=f"{arm_width:.2f}",
            layer=dim_layer,
            color=color,
            height=0.8,
        )

    return outline


__all__ = [
    "FOBConfig",
    "FOB_LABEL",
    "FOB_DEFAULT_WIDTH_M",
    "FOB_MAX_SPAN_M",
    "FOB_VERTICAL_CLEARANCE_M",
    "axis_spans",
    "build_fob_arms",
    "build_fob_outline",
    "calculate_fob_chainage",
    "choose_label_spot",
    "determine_station_edge",
    "generate_fob",
    "get_fob_track_position",
    "track_axis_hits",
    "validate_fob_clearance",
    "validate_fob_conflicts",
    "validate_fob_offset",
    "validate_fob_span",
    "write_fob_deck",
]
