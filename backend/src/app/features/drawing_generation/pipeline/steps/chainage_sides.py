"""Marker collectors for station-relative chainage annotations."""

from __future__ import annotations

import math
from typing import Tuple

from ...domain.geometry.operations import nearest_point_on_alignment, point_at_chainage
from ...domain.platform.track import _extract_points as _pts

Point = Tuple[float, float]

def station_centres_from_dxf(doc) -> list:
    """Centroids of STATION-BUILDING outlines (largest first)."""
    centres: list = []
    try:
        entities = list(doc.modelspace())
    except Exception:
        return []
    for entity in entities:
        try:
            if entity.dxf.layer != "STATION-BUILDING":
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            pts = _pts(entity) if _pts is not None else list(entity.get_points())
            pts = [(float(p[0]), float(p[1])) for p in pts]
            if len(pts) < 3:
                continue
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2.0
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            centres.append((area, (cx, cy)))
        except Exception:
            continue
    centres.sort(key=lambda item: item[0], reverse=True)
    return [c for _, c in centres]


def _clean_pts(pts) -> list:
    return [(float(p[0]), float(p[1])) for p in (pts or [])]


def determine_side(
    pt: Point,
    main_line_points: list | None = None,
    config=None,
    host_track: str | None = None,
    configured_side: str | None = None,
) -> str:
    """Determine whether a point lies on the LEFT or RIGHT side of main alignment."""
    if configured_side:
        s = str(configured_side).strip().upper()
        if s in ("LEFT", "RIGHT"):
            return s
    if host_track and config is not None:
        ht = str(host_track).upper()
        all_tracks = list(getattr(config, "loops", None) or []) + list(getattr(config, "additional_lines", None) or [])
        for item in all_tracks:
            if getattr(item, "name", "").upper() == ht and getattr(item, "side", None):
                return str(item.side).strip().upper()
        for sid in list(getattr(config, "sidings", None) or []):
            if getattr(sid, "source_track", "").upper() == ht and getattr(sid, "side", None):
                return str(sid.side).strip().upper()
    if main_line_points and len(main_line_points) >= 2:
        try:
            cleaned = [(float(p[0]), float(p[1])) for p in main_line_points]
            proj = nearest_point_on_alignment(cleaned, (float(pt[0]), float(pt[1])))
            st = point_at_chainage(cleaned, float(proj.chainage))
            tx, ty = st.tangent
            an = math.hypot(tx, ty) or 1.0
            tx, ty = tx / an, ty / an
            vx, vy = float(pt[0]) - float(proj.point[0]), float(pt[1]) - float(proj.point[1])
            lat_off = -ty * vx + tx * vy
            if lat_off < -0.05:
                return "RIGHT"
            elif lat_off > 0.05:
                return "LEFT"
        except Exception:
            pass
    return "LEFT"


def determine_track_side(
    track_name: str | None,
    config,
    default_to: str | None = None,
    configured_side: str | None = None,
    pt: Point | None = None,
    main_line_points: list | None = None,
) -> str:
    """Look up or compute side (LEFT/RIGHT) for a given track name."""
    if configured_side:
        s = str(configured_side).strip().upper()
        if s in ("LEFT", "RIGHT"):
            return s
    if track_name:
        tn = str(track_name).upper()
        all_tracks = list(getattr(config, "loops", None) or []) + list(getattr(config, "additional_lines", None) or [])
        for item in all_tracks:
            if getattr(item, "name", "").upper() == tn and getattr(item, "side", None):
                return str(item.side).strip().upper()
        for sid in list(getattr(config, "sidings", None) or []):
            if getattr(sid, "source_track", "").upper() == tn and getattr(sid, "side", None):
                return str(sid.side).strip().upper()
        if "MAIN" in tn and default_to:
            dt = str(default_to).upper()
            for item in all_tracks:
                if getattr(item, "name", "").upper() == dt and getattr(item, "side", None):
                    return str(item.side).strip().upper()
            for sid in list(getattr(config, "sidings", None) or []):
                if getattr(sid, "source_track", "").upper() == dt and getattr(sid, "side", None):
                    return str(sid.side).strip().upper()
                if getattr(sid, "source_track", "").upper() == dt and getattr(sid, "side", None):
                    return str(sid.side).strip().upper()
    if pt is not None:
        return determine_side(pt, main_line_points=main_line_points, config=config, host_track=track_name)
    return "LEFT"
