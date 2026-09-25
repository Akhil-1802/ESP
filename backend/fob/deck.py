"""FOB deck generation and DXF output."""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from common.alignment import nearest_point_on_alignment, point_at_chainage
from common.constants import (
    DEFAULT_FOB_WIDTH_M,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
)

FOB_DEFAULT_WIDTH_M: float = DEFAULT_FOB_WIDTH_M
FOB_LABEL: str = "FOOT OVER BRIDGE"
FOB_LABEL_HEIGHT: float = 1.0
from common.dxf import (
    add_line as _add_line,
    add_polyline as _add_polyline,
    add_text as _add_text,
    draw_arrow_dimension as _draw_arrow_dimension,
    ensure_layer as _ensure_layer,
)
from common.geometry import Point, polyline_length
from fob.config import FOBConfig, validate_fob_clearance
from fob.deck_geom import (
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
from fob.placement import (
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

    if getattr(cfg, "fob_chainage", None) is not None:
        chainage = float(cfg.fob_chainage)
    else:
        is_main_center = (
            cfg.reference_chainage is None
            or (
                isinstance(cfg.reference_chainage, str)
                and cfg.reference_chainage.strip().upper() in ("MAIN_CENTER", "AUTO", "")
            )
        )
        station_geom = None
        for name in ("STATION-BUILDING", "STATION_BUILDING"):
            if name in polygons_by_layer:
                station_geom = polygons_by_layer[name]
                break
        if station_geom is None and hasattr(doc, "modelspace"):
            for e in list(doc.modelspace()):
                try:
                    if (
                        getattr(e.dxf, "layer", "") in ("STATION-BUILDING", "STATION_BUILDING")
                        and e.dxftype() in ("LWPOLYLINE", "POLYLINE")
                    ):
                        from platform_gen.track import _extract_points

                        station_geom = _extract_points(e)
                        if len(station_geom) >= 3:
                            break
                except Exception:
                    pass
        if station_geom is None:
            station_geom = [
                polygons_by_layer[p] for p in cfg.platforms if p in polygons_by_layer
            ]

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
                scx = sum(p[0] for p in all_pts) / len(all_pts)
                scy = sum(p[1] for p in all_pts) / len(all_pts)
                center_ch = float(
                    nearest_point_on_alignment(points, (scx, scy)).chainage
                )
        else:
            center_ch = total / 2.0

        if center_ch <= 0.0:
            center_ch = total / 2.0

        if is_main_center:
            ref_chainage = float(center_ch)
        else:
            ref_chainage = float(cfg.reference_chainage)

        # Apply station-edge offset when offset is explicitly configured.
        # When offset=None (the default), use ref_chainage verbatim.
        if cfg.offset is not None:
            off = float(cfg.offset)
            dir_norm = normalize_fob_direction(cfg.direction)
            station_edge_ch = None
            if station_geom is not None:
                try:
                    station_edge_ch = determine_station_edge(
                        points, station_geom, dir_norm
                    )
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
                    and str(arm_spec.get("side", "")).upper() == towards_side
                ):
                    arm_towards_station = max(
                        arm_towards_station, float(arm_spec.get("length", 0.0))
                    )
            extra_to_center = (float(cfg.width) / 2.0) + arm_towards_station

            if dir_norm == "INCREASING":
                chainage = base_ch + off + extra_to_center
            else:
                chainage = base_ch - (off + extra_to_center)
        else:
            chainage = ref_chainage
        cfg.reference_chainage = chainage
        cfg.fob_chainage = chainage

    if not 0.0 <= chainage <= total:
        raise ValueError(
            f"FOB reference chainage {chainage:.3f} m is outside "
            f"{cfg.reference_track} [0, {total:.3f}] MAIN m."
        )
    extent = extents.get(cfg.reference_track)
    local = chainage - extent[0] if extent is not None else chainage
    local = min(max(local, 0.0), polyline_length(points))
    station = point_at_chainage(points, local)
    tn = math.hypot(station.tangent[0], station.tangent[1]) or 1.0
    normal = (-station.tangent[1] / tn, station.tangent[0] / tn)
    names = list(cfg.platforms)
    polys = [polygons_by_layer[name] for name in names]
    outline = build_fob_outline(
        station.point,
        station.tangent,
        polys,
        cfg.width,
        cfg.extend_start_m,
        cfg.extend_end_m,
    )
    spans = dict(zip(names, axis_spans(station.point, normal, polys)))
    arms = build_fob_arms(
        station.point, station.tangent, normal, spans, cfg.arms, cfg.width
    )
    layer, color = cfg.output_layer, cfg.color
    _ensure_layer(doc, layer, color)
    ox, oy = float(station.point[0]), float(station.point[1])
    ttn = math.hypot(station.tangent[0], station.tangent[1]) or 1.0
    tx, ty = station.tangent[0] / ttn, station.tangent[1] / ttn
    nx, ny = normal
    hw = float(cfg.width) / 2.0
    lo_span, hi_span = _deck_span(station.point, normal, outline)

    def _wpt(s, a):
        return (ox + tx * s + nx * a, oy + ty * s + ny * a)

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

    rot_deg = 90.0
    label_h = (
        min(FOB_LABEL_HEIGHT, (cfg.width - 0.6) / (len(FOB_LABEL) * 0.7))
        if cfg.width < 4.0
        else FOB_LABEL_HEIGHT
    )
    label_h = max(label_h, 0.4)
    text_len = len(FOB_LABEL) * label_h * 0.7
    crossings = track_axis_hits(station.point, normal, tracks)
    blocked = []
    for arm in arms:
        proj = [
            (p[0] - station.point[0]) * normal[0]
            + (p[1] - station.point[1]) * normal[1]
            for p in arm
        ]
        blocked.append((min(proj), max(proj)))
    spot = choose_label_spot(
        lo_span, hi_span, crossings, text_len, blocked=blocked
    )
    ins_x = station.point[0] + 0.35 * label_h
    ins_y = station.point[1] + normal[1] * spot - text_len / 2.0
    _add_text(
        doc,
        FOB_LABEL,
        (ins_x, ins_y),
        cfg.output_layer,
        cfg.color,
        height=label_h,
        rotation=rot_deg,
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
            dim_offset=2.0,
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
