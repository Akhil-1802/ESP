"""Shared helpers and fixtures for CAL label tests."""

from __future__ import annotations

import math

from track.cal_labels import CAL_LAYER
from track.fouling import FoulingMark


def _straight(length=776.0, y=0.0, step=5.0):
    pts = []
    x = 0.0
    while x <= length + 1e-9:
        pts.append((float(x), float(y)))
        x += step
    if pts[-1][0] < float(length) - 1e-9:
        pts.append((float(length), float(y)))
    return pts


def _mark(track, local):
    return FoulingMark(
        track=track,
        chainage_main=float(local),
        local_chainage=float(local),
        point=(float(local), 0.0),
        tangent=(1.0, 0.0),
        other_track="OTHER",
        other_chainage_main=float(local),
        other_point=(float(local), 5.3),
        spacing_m=5.3,
    )


def _cal_texts(doc):
    return [e for e in doc.modelspace()
            if e.dxftype() == "TEXT" and e.dxf.layer == CAL_LAYER]


def _cal_tips(doc):
    """Marker tips: first vertex of each leader/arrowhead on CAL layer."""
    tips = []
    seen = set()
    for e in doc.modelspace():
        pt = None
        if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER:
            v = list(e.vertices)
            if v:
                pt = (float(v[0][0]), float(v[0][1]))
        elif e.dxftype() == "LWPOLYLINE" and e.dxf.layer == CAL_LAYER:
            try:
                pts = list(e.get_points())
                if pts:
                    pt = (float(pts[0][0]), float(pts[0][1]))
            except Exception:
                pass
        if pt is not None:
            key = (round(pt[0], 2), round(pt[1], 2))
            if key not in seen:
                seen.add(key)
                tips.append(pt)
    return tips


def _cal_segs(doc):
    segs = []
    for e in doc.modelspace():
        if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER:
            v = [(float(p[0]), float(p[1])) for p in e.vertices]
            for p1, p2 in zip(v, v[1:]):
                segs.append((p1, p2))
        elif e.dxftype() == "LINE" and e.dxf.layer == CAL_LAYER:
            segs.append(((float(e.dxf.start.x), float(e.dxf.start.y)),
                         (float(e.dxf.end.x), float(e.dxf.end.y))))
    return segs


def _orient(p, q, r):
    return ((q[0] - p[0]) * (r[1] - p[1])
            - (q[1] - p[1]) * (r[0] - p[0]))


def _segs_intersect(a, b, c, d):
    return (_orient(a, b, c) * _orient(a, b, d) < 0
            and _orient(c, d, a) * _orient(c, d, b) < 0)


def _seg_seg_dist(a, b, c, d):
    """Distance between segments (0.0 when they cross/touch)."""
    if _segs_intersect(a, b, c, d):
        return 0.0

    def _pt_seg(p, s, e):
        dx, dy = e[0] - s[0], e[1] - s[1]
        denom = dx * dx + dy * dy
        if denom < 1e-12:
            t = 0.0
        else:
            t = ((p[0] - s[0]) * dx + (p[1] - s[1]) * dy) / denom
        t = min(max(t, 0.0), 1.0)
        return math.hypot(p[0] - (s[0] + t * dx),
                          p[1] - (s[1] + t * dy))

    return min(_pt_seg(a, c, d), _pt_seg(b, c, d),
               _pt_seg(c, a, b), _pt_seg(d, a, b))
