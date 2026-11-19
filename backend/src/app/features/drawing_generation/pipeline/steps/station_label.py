"""Station building label collision avoidance helpers.

Relocates platform name labels when covered by station building footprint.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from ...domain.geometry.operations import polygon_contains

Point = Tuple[float, float]

__all__ = ["clear_platform_label_from_station"]


def clear_platform_label_from_station(
    doc,
    platform: Sequence[Point],
    building,
    text_layer: str,
    building_length: float,
) -> None:
    """Move a platform name label inside its platform, clear of its station building."""
    try:
        outline = [(float(p[0]), float(p[1])) for p in building.outline]
        plat = [(float(p[0]), float(p[1])) for p in platform]
        if len(outline) < 3 or len(plat) < 3:
            return
        ang = math.radians(float(building.angle))
        along = (math.cos(ang), math.sin(ang))
        perp = (-along[1], along[0])
        margin = 2.0
        try:
            au = [p[0] * along[0] + p[1] * along[1] for p in plat]
            pv = [p[0] * perp[0] + p[1] * perp[1] for p in plat]
            bu = [p[0] * along[0] + p[1] * along[1] for p in outline]
        except Exception:
            return
        q0, q1 = min(au), max(au)
        pm = (min(pv) + max(pv)) / 2.0
        b0, b1 = min(bu), max(bu)
        try:
            refx = sum(p[0] for p in plat) / len(plat)
            refy = sum(p[1] for p in plat) / len(plat)
        except Exception:
            return
        s_ref = refx * along[0] + refy * along[1]
        p_ref = refx * perp[0] + refy * perp[1]

        def _centre_at(s):
            cx = refx + along[0] * (s - s_ref) + perp[0] * (pm - p_ref)
            cy = refy + along[1] * (s - s_ref) + perp[1] * (pm - p_ref)
            return cx, cy

        def _box_ok(cx, cy, halfw, halfh):
            pts = [(cx, cy)]
            for sa in (-1.0, 1.0):
                for sb in (-1.0, 1.0):
                    pts.append((
                        cx + along[0] * sa * halfw + perp[0] * sb * halfh,
                        cy + along[1] * sa * halfw + perp[1] * sb * halfh,
                    ))
            try:
                if not all(bool(polygon_contains(plat, c)) for c in pts):
                    return False
                if any(bool(polygon_contains(outline, c)) for c in pts):
                    return False
            except Exception:
                return False
            return True

        layer = str(text_layer)
        try:
            entities = list(doc.modelspace())
        except Exception:
            return
        for e in entities:
            try:
                kind = e.dxftype()
                if kind not in ("TEXT", "MTEXT"):
                    continue
                if str(e.dxf.layer) != layer:
                    continue
                if kind == "MTEXT":
                    try:
                        txt = str(e.text or "")
                    except Exception:
                        continue
                    h = float(e.dxf.get("char_height", 1.0) or 1.0)
                else:
                    txt = str(e.dxf.get("text", "") or "")
                    h = float(e.dxf.get("height", 1.0) or 1.0)
                if not txt.strip():
                    continue
                ins = e.dxf.insert
                cx, cy = float(ins.x), float(ins.y)
                try:
                    z = float(ins.z)
                except Exception:
                    z = 0.0
            except Exception:
                continue
            parts = str(txt).split("\\P")
            halfw = max((len(p) for p in parts), default=0) * h * 0.7 / 2.0
            halfh = len(parts) * h / 2.0
            corners = [(cx, cy)]
            for sa in (-1.0, 1.0):
                for sb in (-1.0, 1.0):
                    corners.append((
                        cx + along[0] * sa * halfw + perp[0] * sb * halfh,
                        cy + along[1] * sa * halfw + perp[1] * sb * halfh,
                    ))
            try:
                overlaps = any(bool(polygon_contains(outline, c)) for c in corners)
            except Exception:
                continue
            if not overlaps:
                continue

            s_cur = cx * along[0] + cy * along[1]
            stride = max(2.0 * halfw + margin, 1.0)
            cands = []
            for sign, edge in ((-1.0, b0), (1.0, b1)):
                s = edge + sign * (halfw + margin)
                while (q0 + halfw + 0.5) <= s <= (q1 - halfw - 0.5):
                    cands.append(s)
                    s += sign * stride
            cands.sort(key=lambda s: (abs(s - s_cur), s))
            for s in cands:
                nx, ny = _centre_at(s)
                if not _box_ok(nx, ny, halfw, halfh):
                    continue
                try:
                    if kind == "MTEXT":
                        try:
                            e.set_location((nx, ny), attachment_point=5)
                        except Exception:
                            e.dxf.insert = (nx, ny, z)
                    else:
                        e.dxf.insert = (nx, ny, z)
                except Exception:
                    continue
                break
    except Exception:
        return
