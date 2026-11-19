"""ROB (Road Over Bridge) geometric calculations and DXF generation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from ....formats.dxf.primitives import add_text, draw_arrow_dimension
from ....formats.dxf.styles import ensure_layer
from ...geometry.operations import Point, nearest_point_on_alignment
from .config import ROBConfig


@dataclass
class ROBGeometry:
    """Calculated 2D geometric segments for an ROB."""

    center_point: Point
    tangent: Point
    normal: Point
    deck_span: Tuple[float, float]  # (lo_deck, hi_deck) transverse
    wing_span: Tuple[float, float]  # (lo_wing, hi_wing) transverse
    segments: List[Tuple[Point, Point]]
    local_segments: List[Tuple[Point, Point]]
    label_point: Point
    width: float
    chainage: float = 0.0
    chainage_text: str = ""


def find_track_transverse_extents(
    origin: Point,
    normal: Point,
    tracks: Dict[str, Sequence[Point]],
    track_filter: Sequence[str] | None = None,
) -> Tuple[float, float]:
    """Find the min and max transverse offset along normal for tracks in the yard."""
    nx, ny = normal
    ox, oy = origin
    hits: List[float] = []

    allowed_tracks = (
        {t.strip().upper() for t in track_filter if t and t.strip().upper() != "ALL"}
        if track_filter
        else set()
    )

    for name, points in tracks.items():
        if allowed_tracks and name.strip().upper() not in allowed_tracks:
            continue
        if len(points) < 2:
            continue

        # 1. Exact line segment intersection with the normal line origin + v * normal
        for i in range(len(points) - 1):
            ax, ay = points[i][0], points[i][1]
            bx, by = points[i + 1][0], points[i + 1][1]
            dx, dy = bx - ax, by - ay
            det = nx * dy - ny * dx
            if abs(det) < 1e-9:
                continue
            rx, ry = ax - ox, ay - oy
            u = (nx * ry - ny * rx) / det
            v = (dx * ry - dy * rx) / det
            if -1e-5 <= u <= 1.0 + 1e-5:
                hits.append(v)

        # 2. Nearest point projection fallback
        try:
            np = nearest_point_on_alignment(points, origin)
            px, py = np.point
            # Along tangent offset:
            tx, ty = -ny, nx
            along = (px - ox) * tx + (py - oy) * ty
            if abs(along) <= 60.0:
                trans = (px - ox) * nx + (py - oy) * ny
                hits.append(trans)
        except Exception:
            pass

    if not hits:
        hits = [0.0]

    return min(hits), max(hits)


def generate_rob_geometry(
    origin: Point,
    tangent: Point,
    tracks: Dict[str, Sequence[Point]],
    cfg: ROBConfig,
    chainage: float = 0.0,
    chainage_text: str = "",
) -> ROBGeometry:
    """Generate all line segments for the ROB matching the CAD standard with flared outer diagonals."""
    t_len = math.hypot(tangent[0], tangent[1]) or 1.0
    tx, ty = tangent[0] / t_len, tangent[1] / t_len
    # Normal pointing left/up (perpendicular to track)
    nx, ny = -ty, tx

    v_min, v_max = find_track_transverse_extents(origin, (nx, ny), tracks, cfg.tracks)

    # Deck extents with clearance beyond outermost included tracks
    lo = v_min - cfg.deck_margin
    hi = v_max + cfg.deck_margin

    hw = cfg.width / 2.0
    lw = max(1.0, float(cfg.wing_length))
    # 45-degree diagonal offsets: sin(45) = cos(45) = sqrt(2)/2
    diag = lw * 0.7071067811865476

    def pt(u: float, v: float) -> Point:
        return (
            origin[0] + tx * u + nx * v,
            origin[1] + ty * u + ny * v,
        )

    # 6 line segments matching reference CAD (two unjoined sides with flared wings):
    # 1-2. Two longitudinal side walls spanning across all included tracks
    left_wall = (pt(-hw, lo), pt(-hw, hi))
    right_wall = (pt(+hw, lo), pt(+hw, hi))

    # 3-6. Four outer diagonal wing walls flaring outward beyond the track ends
    top_left_diag = (pt(-hw, hi), pt(-hw - diag, hi + diag))
    top_right_diag = (pt(+hw, hi), pt(+hw + diag, hi + diag))
    bottom_left_diag = (pt(-hw, lo), pt(-hw - diag, lo - diag))
    bottom_right_diag = (pt(+hw, lo), pt(+hw + diag, lo - diag))

    segments = [
        left_wall,
        right_wall,
        top_left_diag,
        top_right_diag,
        bottom_left_diag,
        bottom_right_diag,
    ]

    local_segments = [
        ((-hw, lo), (-hw, hi)),
        ((+hw, lo), (+hw, hi)),
        ((-hw, hi), (-hw - diag, hi + diag)),
        ((+hw, hi), (+hw + diag, hi + diag)),
        ((-hw, lo), (-hw - diag, lo - diag)),
        ((+hw, lo), (+hw + diag, lo - diag)),
    ]

    label_pos = pt(0.0, hi + diag + 2.5)

    return ROBGeometry(
        center_point=origin,
        tangent=(tx, ty),
        normal=(nx, ny),
        deck_span=(lo, hi),
        wing_span=(lo - diag, hi + diag),
        segments=segments,
        local_segments=local_segments,
        label_point=label_pos,
        width=cfg.width,
        chainage=chainage,
        chainage_text=chainage_text,
    )


def write_rob(doc, geom: ROBGeometry, cfg: ROBConfig) -> None:
    """Write the ROB entities into the DXF document using the SGFD block definition."""
    layer = cfg.output_layer or "SGFD"
    color = cfg.color
    ensure_layer(doc, layer, color)

    block_name = getattr(cfg, "block_name", "") or "SGFD"

    # Create or update the SGFD block definition
    if block_name in doc.blocks:
        block = doc.blocks[block_name]
        for entity in list(block):
            try:
                block.delete_entity(entity)
            except Exception:
                pass
    else:
        block = doc.blocks.new(name=block_name, base_point=(0, 0))

    # Add the 8 CAD lines inside the SGFD block definition
    for p1, p2 in geom.local_segments:
        block.add_line(p1, p2, dxfattribs={"layer": layer, "color": color})

    # Insert block reference into modelspace at the center point with track rotation
    rot_deg = math.degrees(math.atan2(geom.tangent[1], geom.tangent[0]))
    doc.modelspace().add_blockref(
        name=block_name,
        insert=geom.center_point,
        dxfattribs={
            "layer": layer,
            "rotation": rot_deg,
        },
    )

    # Add text label only if explicitly requested
    if getattr(cfg, "add_text", False):
        label_text = f"ROB ({cfg.width:g}m)"
        add_text(
            doc,
            label_text,
            geom.label_point,
            layer,
            color,
            height=1.2,
            rotation=rot_deg,
        )

    # Add width dimension
    if getattr(cfg, "add_dimension", True):
        hw = cfg.width / 2.0
        tx, ty = geom.tangent
        nx, ny = geom.normal
        ox, oy = geom.center_point
        hi = geom.deck_span[1]
        hi_w = geom.wing_span[1]
        diag_offset = hi_w - hi

        dim_p1 = (ox - tx * hw + nx * hi, oy - ty * hw + ny * hi)
        dim_p2 = (ox + tx * hw + nx * hi, oy + ty * hw + ny * hi)
        dim_layer = f"{layer}-DIM"
        ensure_layer(doc, dim_layer, color)
        draw_arrow_dimension(
            doc,
            dim_p1,
            dim_p2,
            dim_offset=diag_offset + 1.5,
            text=f"{cfg.width:.2f}",
            layer=dim_layer,
            color=color,
            height=0.8,
        )

    # Add bridge chainage and centerline (omitted by default since shown on CHAINAGE layer)
    if getattr(cfg, "add_chainage", False):
        lo, hi = geom.deck_span
        ox, oy = geom.center_point
        nx, ny = geom.normal
        tx, ty = geom.tangent

        # 1. Dashed centerline through bridge (omitted by default)
        if getattr(cfg, "add_centerline", False):
            c_layer = f"{layer}-CENTER"
            try:
                from ....formats.dxf.styles import ensure_dashed_linetype
                ensure_dashed_linetype(doc)
                ensure_layer(doc, c_layer, color=7, linetype="DASHED")
                doc.modelspace().add_line(
                    (ox + nx * (lo - 1.5), oy + ny * (lo - 1.5)),
                    (ox + nx * (hi + 1.5), oy + ny * (hi + 1.5)),
                    dxfattribs={"layer": c_layer, "color": 7, "linetype": "DASHED"},
                )
            except Exception:
                ensure_layer(doc, c_layer, color=7)
                doc.modelspace().add_line(
                    (ox + nx * (lo - 1.5), oy + ny * (lo - 1.5)),
                    (ox + nx * (hi + 1.5), oy + ny * (hi + 1.5)),
                    dxfattribs={"layer": c_layer, "color": 7},
                )

        # 2. Vertical chainage text "BR.CH- <chainage>"
        ch_text = geom.chainage_text or (
            f"BR.CH- {cfg.chainage}"
            if getattr(cfg, "chainage", None)
            else f"BR.CH- {geom.chainage:.2f}"
        )
        if not ch_text.upper().startswith("BR.CH"):
            ch_text = f"BR.CH- {ch_text}"

        v_pos = max(lo + 1.0, min(hi - 5.0, 0.5))
        p_text = (ox + tx * 0.8 + nx * v_pos, oy + ty * 0.8 + ny * v_pos)
        rot_normal = math.degrees(math.atan2(ny, nx))

        add_text(
            doc,
            ch_text,
            p_text,
            layer=layer,
            color=1,  # Standard AutoCAD red
            height=1.0,
            rotation=rot_normal,
        )
