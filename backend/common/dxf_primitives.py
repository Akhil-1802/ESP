"""Drawing primitives for DXF output: polylines, splines, disks, text, dimensions."""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import DEFAULT_COLOR
from common.dxf_styles import ensure_layer, ensure_number_style, ensure_text_style
from common.dxf_text import _inflate, _register_box, estimate_text_aabb, resolve_text_insert
from common.geometry import Point, disk_points, readable_angle_deg


def add_polyline(doc, points: Sequence[Point], layer: str, color: int, close: bool = False):
    """Add an LWPOLYLINE (or legacy POLYLINE) through points."""
    attributes = {"layer": layer, "color": color}
    if doc.dxfversion >= "AC1015":
        return doc.modelspace().add_lwpolyline(points, close=close, dxfattribs=attributes)
    polyline = doc.modelspace().add_polyline2d(points, dxfattribs=attributes)
    if close:
        polyline.close(True)
    return polyline


def add_spline(doc, points: Sequence[Point], layer: str, color: int):
    """Add a smooth cubic B-spline through points (polyline fallback)."""
    if len(points) < 2:
        return None
    ensure_layer(doc, layer, color)
    try:
        from ezdxf.math import BSpline, Vec3

        cpts = [Vec3(x, y, 0) for (x, y) in points]
        bspline = BSpline.from_fit_points(cpts, degree=3)
        entity = doc.modelspace().add_spline(dxfattribs={"layer": layer, "color": color})
        entity.apply_construction_tool(bspline)
        entity.fit_points = cpts
        return entity
    except Exception:
        return add_polyline(doc, list(points), layer, color)


def add_filled_disk(doc, center: Point, radius: float, layer: str, color: int, samples: int = 16):
    """Draw a solid filled disk (outline + hatch)."""
    ensure_layer(doc, layer, color)
    outline = disk_points(center, radius, samples)
    doc.modelspace().add_lwpolyline(
        outline, close=True, dxfattribs={"layer": layer, "color": color}
    )
    try:
        hatch = doc.modelspace().add_hatch(dxfattribs={"layer": layer, "color": color})
        hatch.set_solid_fill(color=color)
        hatch.paths.add_polyline_path(outline, is_closed=True)
    except Exception:
        pass
    return outline


def add_text(
    doc,
    text: str,
    insert: Point,
    layer: str,
    color: int,
    height: float = 1.0,
    rotation: float = 0.0,
    align: str | None = None,
    resolve: bool = True,
):
    """Add TEXT with a readable rotation (1 m clear of other texts)."""
    from ezdxf.enums import TextEntityAlignment

    ensure_layer(doc, layer, color)
    ang = readable_angle_deg(rotation)
    if resolve:
        insert = resolve_text_insert(doc, text, height, ang, insert)
    entity = doc.modelspace().add_text(
        text,
        dxfattribs={
            "layer": layer,
            "color": color,
            "style": ensure_text_style(doc),
            "height": height,
            "rotation": ang,
            "insert": (insert[0], insert[1], 0),
        },
    )
    if align is not None:
        if isinstance(align, str):
            align_enum = getattr(TextEntityAlignment, align.upper(), None)
        else:
            align_enum = align
        if align_enum is not None:
            entity.set_placement((insert[0], insert[1]), align=align_enum)
    return entity


def add_line(doc, p1: Point, p2: Point, layer: str, color: int):
    """Add a LINE entity from p1 to p2."""
    ensure_layer(doc, layer, color)
    return doc.modelspace().add_line(p1, p2, dxfattribs={"layer": layer, "color": color})


def add_arrow_head(
    doc,
    tip: Point,
    direction: Point,
    layer: str,
    color: int = DEFAULT_COLOR,
    length: float = 2.0,
    half_width: float = 0.7,
):
    """Filled triangular arrowhead with its tip at tip."""
    n = math.hypot(direction[0], direction[1]) or 1.0
    dx, dy = direction[0] / n, direction[1] / n
    base = (tip[0] - dx * length, tip[1] - dy * length)
    tri = [
        tip,
        (base[0] - dy * half_width, base[1] + dx * half_width),
        (base[0] + dy * half_width, base[1] - dx * half_width),
    ]
    ensure_layer(doc, layer, color)
    doc.modelspace().add_lwpolyline(
        tri, close=True, dxfattribs={"layer": layer, "color": color}
    )
    try:
        hatch = doc.modelspace().add_hatch(dxfattribs={"layer": layer, "color": color})
        hatch.set_solid_fill(color=color)
        hatch.paths.add_polyline_path(tri, is_closed=True)
    except Exception:
        pass


def draw_arrow_dimension(
    doc,
    p1: Point,
    p2: Point,
    dim_offset: float = 0.0,
    text=None,
    layer: str = "DIMENSIONS",
    color: int = DEFAULT_COLOR,
    height: float = 0.8,
    tick: bool = True,
) -> None:
    """AutoCAD native associative dimension with stretch grips and dynamic measurement.

    Uses AutoCAD's native DIMENSION entity (aligned dimension) so clicking
    on it in AutoCAD activates stretch grips on definition points and markers,
    and moving/stretching grips automatically updates the measurement text.
    """
    from common.constants import TEXT_CLEARANCE_M

    msp = doc.modelspace()
    ensure_layer(doc, layer, color)
    dx, dy = float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1])
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return

    dim_text = "<>"
    if text is not None:
        raw_str = str(text).strip()
        if not raw_str or raw_str == "<>":
            dim_text = "<>"
        else:
            try:
                float(raw_str)
                dim_text = "<>"
            except ValueError:
                import re
                if "<>" in raw_str:
                    dim_text = raw_str
                elif re.search(r"\d", raw_str):
                    dim_text = re.sub(r"[-+]?\d*\.?\d+", "<>", raw_str, count=1)
                else:
                    dim_text = raw_str

    use_tick = bool(tick)

    try:
        try:
            for ds in doc.dimstyles:
                if ds.dxf.get("dimrnd", 0.0) == 0.0:
                    ds.dxf.dimrnd = 0.01
        except Exception:
            pass
        num_style = ensure_number_style(doc)
        offset_val = float(dim_offset)
        dim_override = {
            "dimtxsty": num_style,
            "dimclrd": color,
            "dimclre": color,
            "dimclrt": color,
            "dimtxt": float(height),
            "dimexe": 0.5,
            "dimexo": 0.2,
            "dimtad": 1 if abs(offset_val) > 1e-6 else 0,
            "dimtih": 0 if abs(offset_val) > 1e-6 else 1,
            "dimtoh": 0 if abs(offset_val) > 1e-6 else 1,
            "dimdec": 2,
            "dimrnd": 0.01,
            "dimzin": 8 if "T.C" in dim_text else 0,
            "dimdsep": ord("."),
            "dimlfac": 1.0,
        }
        if use_tick:
            dim_override["dimtsz"] = float(height) * 0.8
            dim_override["dimdle"] = 0.5
        else:
            dim_override["dimtsz"] = 0.0
            dim_override["dimasz"] = float(height)
            dim_override["dimdle"] = 0.0

        dim = msp.add_aligned_dim(
            p1=(float(p1[0]), float(p1[1])),
            p2=(float(p2[0]), float(p2[1])),
            distance=offset_val,
            text=dim_text,
            override=dim_override,
            dxfattribs={"layer": layer, "color": color},
        )
        dim.render()

        try:
            ux, uy = dx / length, dy / length
            nx, ny = -uy, ux
            mid_x = (float(p1[0]) + float(p2[0])) / 2.0 + nx * offset_val
            mid_y = (float(p1[1]) + float(p2[1])) / 2.0 + ny * offset_val
            box = _inflate(
                estimate_text_aabb(
                    f"{length:.2f}", float(height), 0.0, (mid_x, mid_y), "middle-center", 0.55
                ),
                TEXT_CLEARANCE_M,
            )
            _register_box(doc, box)
        except Exception:
            pass
        return
    except Exception:
        pass

    # Fallback to primitive lines + text if DIMENSION rendering fails
    ux, uy = dx / length, dy / length
    nx, ny = -uy, ux
    q1 = (p1[0] + nx * dim_offset, p1[1] + ny * dim_offset)
    q2 = (p2[0] + nx * dim_offset, p2[1] + ny * dim_offset)

    if abs(dim_offset) > 1e-9:
        sign = 1.0 if dim_offset > 0 else -1.0
        e1 = (q1[0] + nx * sign * 0.5, q1[1] + ny * sign * 0.5)
        e2 = (q2[0] + nx * sign * 0.5, q2[1] + ny * sign * 0.5)
        msp.add_line((p1[0], p1[1]), e1, dxfattribs={"layer": layer, "color": color})
        msp.add_line((p2[0], p2[1]), e2, dxfattribs={"layer": layer, "color": color})

    if use_tick:
        dle = 0.5
        d1 = (q1[0] - ux * dle, q1[1] - uy * dle)
        d2 = (q2[0] + ux * dle, q2[1] + uy * dle)
        msp.add_line(d1, d2, dxfattribs={"layer": layer, "color": color})
        ts = float(height) * 0.8
        inv_sqrt2 = 0.70710678
        sx = (ux + nx) * inv_sqrt2 * (ts * 0.8)
        sy = (uy + ny) * inv_sqrt2 * (ts * 0.8)
        for q in (q1, q2):
            msp.add_line(
                (q[0] - sx, q[1] - sy),
                (q[0] + sx, q[1] + sy),
                dxfattribs={"layer": layer, "color": color},
            )
    else:
        msp.add_line(q1, q2, dxfattribs={"layer": layer, "color": color})
        al = min(1.2, length * 0.25)
        aw = al * 0.3
        for tip_pt, inward in ((q1, (ux, uy)), (q2, (-ux, -uy))):
            base = (tip_pt[0] + inward[0] * al, tip_pt[1] + inward[1] * al)
            tri = [
                tip_pt,
                (base[0] + nx * aw, base[1] + ny * aw),
                (base[0] - nx * aw, base[1] - ny * aw),
            ]
            msp.add_lwpolyline(tri, close=True, dxfattribs={"layer": layer, "color": color})
            try:
                hatch = msp.add_hatch(dxfattribs={"layer": layer, "color": color})
                hatch.set_solid_fill(color=color)
                hatch.paths.add_polyline_path(tri, is_closed=True)
            except Exception:
                pass

    label = text if text is not None else f"{length:.2f}"
    raw_angle = math.degrees(math.atan2(uy, ux))
    if raw_angle <= -90.0 + 1e-4 or raw_angle > 90.0 + 1e-4:
        tx_dir, ty_dir = -ux, -uy
        norm_x, norm_y = -nx, -ny
    else:
        tx_dir, ty_dir = ux, uy
        norm_x, norm_y = nx, ny

    ang = readable_angle_deg(math.degrees(math.atan2(ty_dir, tx_dir)))
    est_half = len(label) * height * 0.35
    mid = (
        (q1[0] + q2[0]) / 2.0 - tx_dir * est_half + norm_x * 1.0,
        (q1[1] + q2[1]) / 2.0 - ty_dir * est_half + norm_y * 1.0,
    )
    mid = resolve_text_insert(doc, label, height, ang, mid, width_factor=0.55)
    msp.add_text(
        label,
        dxfattribs={
            "layer": layer,
            "color": color,
            "height": height,
            "style": ensure_number_style(doc),
            "rotation": ang,
            "insert": (mid[0], mid[1], 0),
        },
    )
