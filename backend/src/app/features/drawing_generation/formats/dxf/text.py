"""Text placement and clash avoidance for DXF drawings."""

from __future__ import annotations

import math

from ...domain.constants import NUMBER_STYLE_NAME, TEXT_CLEARANCE_M


def _width_factor_for(style_name: str | None) -> float:
    return 0.55 if style_name == NUMBER_STYLE_NAME else 0.7


def estimate_text_aabb(
    text: str,
    height: float,
    rotation_deg: float = 0.0,
    insert=(0.0, 0.0),
    anchor: str = "left-baseline",
    width_factor: float = 0.7,
):
    """Axis-aligned bounding box of a text at insert (no clearance)."""
    height = float(height) or 1.0
    lines = str(text).split("\\P")
    width = 0.0
    for line in lines:
        plain = line
        while True:
            start = plain.find("\\")
            if start < 0:
                break
            end = plain.find(";", start)
            plain = (plain[:start] + plain[end + 1:]
                     if end >= 0 else plain[:start])
        width = max(width, len(plain) * height * float(width_factor))
    total_h = height * (1.0 + (len(lines) - 1) * 1.3)
    if anchor == "middle-center":
        x0, x1, y0, y1 = -width / 2.0, width / 2.0, -total_h / 2.0, total_h / 2.0
    elif anchor == "top-left":
        x0, x1, y0, y1 = 0.0, width, -total_h, 0.0
    elif anchor == "right-baseline":
        x0, x1, y0, y1 = -width, 0.0, -0.3 * height, -0.3 * height + total_h
    else:  # left-baseline
        x0, x1, y0, y1 = 0.0, width, -0.3 * height, -0.3 * height + total_h
    ang = math.radians(float(rotation_deg or 0.0))
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    xs, ys = [], []
    for cx, cy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        xs.append(insert[0] + cx * cos_a - cy * sin_a)
        ys.append(insert[1] + cx * sin_a + cy * cos_a)
    return (min(xs), min(ys), max(xs), max(ys))


def _inflate(box, margin: float):
    return (box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin)


def _boxes_overlap(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def _box_from_entity(entity):
    """Inflated AABB of an existing TEXT/MTEXT entity."""
    kind = entity.dxftype()
    if kind == "TEXT":
        halign = int(entity.dxf.get("halign", 0) or 0)
        anchor = "right-baseline" if halign == 2 else "left-baseline"
        pt = entity.dxf.get("align_point", None) if halign else None
        ins = (float(pt.x), float(pt.y)) if pt is not None else (
            float(entity.dxf.insert.x), float(entity.dxf.insert.y))
        return _inflate(
            estimate_text_aabb(
                entity.dxf.get("text", ""),
                entity.dxf.get("height", 1.0),
                entity.dxf.get("rotation", 0.0),
                ins,
                anchor,
                _width_factor_for(entity.dxf.get("style", "Standard")),
            ),
            TEXT_CLEARANCE_M,
        )
    if kind == "MTEXT":
        try:
            content = entity.text
        except Exception:
            content = ""
        ap = int(entity.dxf.get("attachment_point", 1) or 1)
        anchor = "middle-center" if ap == 5 else (
            "top-left" if ap == 1 else "middle-center")
        ins = entity.dxf.insert
        return _inflate(
            estimate_text_aabb(
                content,
                entity.dxf.get("char_height", 1.0) or 1.0,
                entity.dxf.get("rotation", 0.0),
                (ins.x, ins.y),
                anchor,
                _width_factor_for(entity.dxf.get("style", "Standard")),
            ),
            TEXT_CLEARANCE_M,
        )
    raise ValueError(f"not a text entity: {kind}")


def _text_registry(doc) -> list:
    """Placed-text boxes for doc (seeded from the file on first use)."""
    boxes = getattr(doc, "_esp_text_boxes", None)
    if boxes is None:
        boxes = []
        try:
            entities = list(doc.modelspace())
        except Exception:
            entities = []
        for entity in entities:
            try:
                if entity.dxftype() in ("TEXT", "MTEXT"):
                    boxes.append(_box_from_entity(entity))
            except Exception:
                continue
        try:
            doc._esp_text_boxes = boxes
        except Exception:
            pass
    return boxes


def _register_box(doc, box) -> None:
    try:
        _text_registry(doc).append(box)
    except Exception:
        pass


def _track_segments(doc) -> list:
    """Cached track polyline/line segments for track collision avoidance."""
    segments = getattr(doc, "_esp_track_segments", None)
    if segments is None:
        segments = []
        try:
            msp = doc.modelspace()
            for e in msp:
                layer = (e.dxf.get("layer", "") or "").upper()
                if any(k in layer for k in ["MAIN", "LOOP", "SIDING", "PROPOSED", "TRACK", "PLATFORM"]):
                    dxftype = e.dxftype()
                    if dxftype == "LWPOLYLINE":
                        pts = list(e.get_points())
                    elif dxftype == "SPLINE":
                        pts = list(e.control_points)
                    elif dxftype == "LINE":
                        pts = [e.dxf.start, e.dxf.end]
                    else:
                        continue
                    for p1, p2 in zip(pts, pts[1:]):
                        segments.append(((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))))
        except Exception:
            pass
        try:
            doc._esp_track_segments = segments
        except Exception:
            pass
    return segments


def _box_overlaps_track(doc, box, clearance: float = 0.5) -> bool:
    """Return True if box (inflated by clearance) overlaps any track segment."""
    segs = _track_segments(doc)
    if not segs:
        return False
    bx0, by0, bx1, by1 = box[0] - clearance, box[1] - clearance, box[2] + clearance, box[3] + clearance
    for (x1, y1), (x2, y2) in segs:
        if bx1 < min(x1, x2) or bx0 > max(x1, x2) or by1 < min(y1, y2) or by0 > max(y1, y2):
            continue
        p1_x, p1_y = x1, y1
        p2_x, p2_y = x2, y2
        if (p1_x < bx0 and p2_x < bx0) or (p1_x > bx1 and p2_x > bx1) or \
           (p1_y < by0 and p2_y < by0) or (p1_y > by1 and p2_y > by1):
            continue
        return True
    return False


def _box_is_clear(doc, box, check_tracks: bool = True) -> bool:
    try:
        existing = _text_registry(doc)
        if not all(not _boxes_overlap(box, other) for other in existing):
            return False
    except Exception:
        pass
    if check_tracks:
        try:
            if _box_overlaps_track(doc, box):
                return False
        except Exception:
            pass
    return True


def resolve_text_insert(
    doc,
    text: str,
    height: float,
    rotation_deg: float = 0.0,
    insert=(0.0, 0.0),
    anchor: str = "left-baseline",
    width_factor: float = 0.7,
    step: float = 2.0,
    rings: int = 3,
    check_tracks: bool = True,
):
    """Return a clash-free insert for a new text (and claim the spot)."""
    bx, by = float(insert[0]), float(insert[1])
    first = _inflate(
        estimate_text_aabb(text, height, rotation_deg, (bx, by), anchor, width_factor),
        TEXT_CLEARANCE_M,
    )
    if _box_is_clear(doc, first, check_tracks=check_tracks):
        _register_box(doc, first)
        return insert
    for ring in range(1, int(rings) + 1):
        for quarter in range(8):
            ang = math.pi / 4.0 * quarter
            cx = bx + math.cos(ang) * step * ring
            cy = by + math.sin(ang) * step * ring
            cand = _inflate(
                estimate_text_aabb(text, height, rotation_deg, (cx, cy), anchor, width_factor),
                TEXT_CLEARANCE_M,
            )
            if _box_is_clear(doc, cand, check_tracks=check_tracks):
                _register_box(doc, cand)
                if len(tuple(insert)) >= 3:
                    return (cx, cy, insert[2])
                return (cx, cy)
    _register_box(doc, first)
    return insert
