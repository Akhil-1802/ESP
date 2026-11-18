"""Drawing and layout primitives for CAL labels."""

from __future__ import annotations

import math
from typing import Tuple

from common.constants import TEXT_CLEARANCE_M as _clr
from common.dxf import (
    _inflate as _inf,
    _register_box as _reg,
    add_arrow_head as _arrow_head,
    add_line as _add_line,
    ensure_layer as _ensure_layer,
    ensure_text_style as _ensure_text_style,
    estimate_text_aabb as _aabb,
)
from common.geometry import Point
from track.cal_calc import (
    CAL_COLOR,
    CAL_COLUMN_GAP_M,
    CAL_LAYER,
    CAL_TEXT_GAP_M,
    CAL_TEXT_HEIGHT_M,
    CAL_TEXT_LIFT_M,
    CAL_TEXT_RUN_M,
    split_cal_label,
)


def _add_cal_text(doc, text: str, ang: float, centre: Point):
    """Draw one middle-centre CAL text part and register its box."""
    height = float(CAL_TEXT_HEIGHT_M)
    cx, cy = float(centre[0]), float(centre[1])
    msp = doc.modelspace()
    txt_entity = None
    try:
        txt_entity = msp.add_text(
            text,
            height=height,
            dxfattribs={
                "layer": CAL_LAYER,
                "color": CAL_COLOR,
                "style": _ensure_text_style(doc),
                "rotation": ang,
                "insert": (cx, cy, 0),
                "halign": 1,
                "valign": 2,
                "align_point": (cx, cy, 0),
            },
        )
    except Exception:
        txt_entity = msp.add_text(
            text,
            height=height,
            dxfattribs={
                "layer": CAL_LAYER,
                "color": CAL_COLOR,
                "style": _ensure_text_style(doc),
                "rotation": ang,
                "insert": (cx, cy, 0),
            },
        )
    try:
        box = _inf(
            _aabb(
                text,
                height,
                ang,
                (cx, cy),
                "middle-center",
                0.7,
            ),
            _clr,
        )
        _reg(doc, box)
    except Exception:
        pass
    return txt_entity


def _draw_cal_text_only(
    doc,
    full: str,
    tip: Point,
    tangent: Point,
    normal: Point,
    ang: float,
    delta_v: float,
) -> bool:
    """Draw one CAL label directly inside the track gap (Case 1: no leader, no marker)."""
    try:
        _ensure_layer(doc, CAL_LAYER, CAL_COLOR)
        nx, ny = float(normal[0]), float(normal[1])
        tipx, tipy = float(tip[0]), float(tip[1])
        centre = (tipx + nx * float(delta_v), tipy + ny * float(delta_v))
        txt_entity = _add_cal_text(doc, full, ang, centre)
        return txt_entity is not None
    except Exception:
        return False


def _draw_cal_row(
    doc,
    name: str,
    cal_value: str,
    tip: Point,
    tangent: Point,
    normal: Point,
    ang: float,
    width_name: float,
    width_cal: float,
    want_name: Point,
    want_cal: Point,
    above: Point,
    delta_v: float | None = None,
) -> bool:
    """Draw one per-line CAL label with its callout arrow onto the line."""
    try:
        _ensure_layer(doc, CAL_LAYER, CAL_COLOR)
        full = f"{name} {cal_value}".strip()
        tx, ty = float(tangent[0]), float(tangent[1])
        nx, ny = float(normal[0]), float(normal[1])
        tn = math.hypot(tx, ty) or 1.0
        tx, ty = tx / tn, ty / tn
        height = float(CAL_TEXT_HEIGHT_M)
        width_full = len(full) * height * 0.7
        lift = float(CAL_TEXT_LIFT_M) if delta_v is None else float(delta_v)
        run = float(CAL_TEXT_RUN_M)
        gap = float(CAL_TEXT_GAP_M)
        tipx, tipy = float(tip[0]), float(tip[1])

        dimasz = 2.0
        min_diag = 2.0 * dimasz + 0.6
        dx_diag = math.sqrt(max(min_diag**2 - lift**2, 0.0))
        dx_diag = max(dx_diag, 4.5)
        back = float(dx_diag + gap + run)

        left = (tipx + tx * back + nx * lift, tipy + ty * back + ny * lift)
        centre = (
            left[0] + tx * width_full / 2.0,
            left[1] + ty * width_full / 2.0,
        )
        txt_entity = _add_cal_text(doc, full, ang, centre)
        start = (left[0] - tx * gap, left[1] - ty * gap)
        elbow = (start[0] - tx * run, start[1] - ty * run)

        msp = doc.modelspace()
        dx, dy = tipx - elbow[0], tipy - elbow[1]
        dn = math.hypot(dx, dy) or 1.0
        arrow_dir = (dx / dn, dy / dn)

        try:
            ds_name = "Standard"
            if "Standard" not in doc.dimstyles and len(doc.dimstyles):
                ds_name = doc.dimstyles[0].dxf.name
            leader = msp.add_leader(
                vertices=[
                    (tipx, tipy),
                    (elbow[0], elbow[1]),
                    (start[0], start[1]),
                ],
                dimstyle=ds_name,
                override={
                    "dimclrd": CAL_COLOR,
                    "dimasz": 2.0,
                    "dimtxsty": _ensure_text_style(doc),
                    "dimtxt": height,
                },
                dxfattribs={
                    "layer": CAL_LAYER,
                    "color": CAL_COLOR,
                    "has_arrowhead": 1,
                    # The third vertex already supplies the landing beside the
                    # text; a native hook would add another, differently
                    # oriented segment when the final plan is rotated.
                    "has_hookline": 0,
                    "horizontal_direction": (tx, ty, 0),
                },
            )
            if txt_entity is not None:
                try:
                    leader.dxf.annotation_type = 0
                    leader.dxf.annotation_handle = txt_entity.dxf.handle
                except Exception:
                    pass
        except Exception:
            _add_line(doc, start, elbow, CAL_LAYER, CAL_COLOR)
            _add_line(doc, elbow, tip, CAL_LAYER, CAL_COLOR)
            _arrow_head(
                doc,
                tip,
                arrow_dir,
                CAL_LAYER,
                CAL_COLOR,
                length=1.8,
                half_width=0.45,
            )
        return True
    except Exception:
        return False


def finalize_cal_leaders(doc) -> None:
    """Match CAL landings to horizontal text after the final plan rotation."""
    for leader in doc.modelspace().query(f'LEADER[layer=="{CAL_LAYER}"]'):
        text = doc.entitydb.get(leader.dxf.get("annotation_handle", "0"))
        if text is None or text.dxftype() != "TEXT" or len(leader.vertices) != 3:
            continue
        tip, elbow, landing = leader.vertices
        run = landing - elbow
        length = run.magnitude
        if length < 1e-9:
            continue
        # CAL text is middle-centred. Recover the existing half-width + gap
        # along its original landing rather than estimating the font again.
        centre = text.dxf.align_point
        clearance = (centre - landing).dot(run / length)
        landing = centre.replace(x=centre.x - clearance)
        elbow = landing.replace(x=landing.x - length)
        leader.set_vertices([tip, elbow, landing])
        leader.dxf.horizontal_direction = (1, 0, 0)
        leader.dxf.has_hookline = 0


def _draw_cal_callout(
    doc,
    label: str,
    tip: Point,
    tangent: Point,
    ang: float,
    width: float,
    want: Point,
    elbow: Point,
) -> bool:
    """Backwards-compatible single-label wrapper."""
    try:
        name, cal_value = split_cal_label(label)
        if not cal_value:
            name, cal_value = label, ""
        try:
            tx, ty = float(tangent[0]), float(tangent[1])
            normal = (-ty, tx)
        except Exception:
            normal = (0.0, 1.0)
        tx, ty = float(tangent[0]), float(tangent[1])
        w_name = len(name) * float(CAL_TEXT_HEIGHT_M) * 0.7
        w_cal = (
            len(cal_value) * float(CAL_TEXT_HEIGHT_M) * 0.7 if cal_value else 0.0
        )
        cx, cy = float(want[0]), float(want[1])
        total = w_name + CAL_COLUMN_GAP_M + w_cal
        c_name = (
            cx - tx * (total / 2.0 - w_name / 2.0),
            cy - ty * (total / 2.0 - w_name / 2.0),
        )
        c_cal = (
            cx + tx * (total / 2.0 - w_cal / 2.0),
            cy + ty * (total / 2.0 - w_cal / 2.0),
        )
        above = (float(want[0]), float(want[1]))
        if not cal_value:
            return _draw_cal_row(
                doc,
                name,
                "",
                tip,
                tangent,
                normal,
                ang,
                w_name,
                0.0,
                c_name,
                c_name,
                above,
            )
        return _draw_cal_row(
            doc,
            name,
            cal_value,
            tip,
            tangent,
            normal,
            ang,
            w_name,
            w_cal,
            c_name,
            c_cal,
            above,
        )
    except Exception:
        return False


__all__ = [
    "_add_cal_text",
    "_draw_cal_callout",
    "_draw_cal_row",
    "_draw_cal_text_only",
    "finalize_cal_leaders",
]
