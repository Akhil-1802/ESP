"""Gradient annotation pipeline step.

Places straight horizontal gradient annotation symbols at the correct location
along the railway track alignment using station center chainage as reference.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Sequence, Tuple

from ...domain.geometry.alignment import point_at_chainage
from ...domain.geometry.operations import Point, nearest_point_on_alignment
from .base import PipelineStep
from .chainage_collect import station_centres_from_dxf


def parse_chainage_val(val: str | float | None) -> Tuple[float, str | None]:
    """Parse a chainage string or number into a numeric value and unit.

    Supported formats:
    - 125.4 or 125.400
    - "125.4 KM", "KM: 125.400", "CH: 125.400 KM"
    - "125+400" (returns (125400.0, "M"))
    - "400 M", "CH: 400 M"
    """
    if val is None:
        raise ValueError("Chainage value cannot be None.")
    s = str(val).strip()
    if not s:
        raise ValueError("Chainage value cannot be empty.")

    if "+" in s:
        parts = s.split("+")
        if len(parts) == 2:
            km = float(parts[0].strip() or 0)
            m = float(parts[1].strip() or 0)
            return km * 1000.0 + m, "M"

    clean = s.upper()
    for prefix in ("CH :", "CH:", "CH", "KM :", "KM:", "KM"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()
            break

    unit: str | None = None
    if clean.endswith("KM"):
        unit = "KM"
        clean = clean[:-2].strip()
    elif clean.endswith("M"):
        unit = "M"
        clean = clean[:-1].strip()

    try:
        num = float(clean)
    except ValueError as exc:
        raise ValueError(f"Invalid chainage value: {val!r}") from exc

    return num, unit


def compute_gradient_offset(grad_ch: str | float, stn_ch: str | float | None) -> float:
    """Calculate relative offset in meters: gradient_chainage - station_center_chainage.

    Respects KM and M units automatically.
    """
    grad_val, grad_unit = parse_chainage_val(grad_ch)
    if stn_ch is None or str(stn_ch).strip() == "":
        stn_val, stn_unit = 0.0, grad_unit
    else:
        stn_val, stn_unit = parse_chainage_val(stn_ch)

    if grad_unit == "KM" and stn_unit == "KM":
        return (grad_val - stn_val) * 1000.0
    if grad_unit == "M" and stn_unit == "M":
        # If station is in route chainage meters (e.g. 70831 M) and gradient is given as local meter (e.g. 831 M)
        if stn_val >= 10000.0 and grad_val < 10000.0:
            stn_km_m = math.floor(stn_val / 1000.0) * 1000.0
            return (grad_val + stn_km_m) - stn_val
        return grad_val - stn_val
    if grad_unit == "M" and (stn_unit == "KM" or (stn_unit is None and stn_val < 1000.0 and grad_val >= 1000.0)):
        return grad_val - (stn_val * 1000.0)
    if (grad_unit == "KM" or (grad_unit is None and grad_val < 1000.0 and stn_val >= 1000.0)) and stn_unit == "M":
        return (grad_val * 1000.0) - stn_val

    # If either has explicit KM unit
    if grad_unit == "KM":
        return (grad_val * 1000.0) - stn_val
    if stn_unit == "KM":
        return grad_val - (stn_val * 1000.0)

    # When neither unit is explicitly given:
    # If the user provides route KM values with a small fractional difference
    # (e.g. grad="125.400", stn="125.000", diff = 0.400; or "128.000" vs "125.000"), diff is in KM.
    diff = grad_val - stn_val
    if abs(diff) <= 4.0 and (stn_val >= 10.0 and grad_val >= 10.0) and ("." in str(grad_ch) or "." in str(stn_ch)):
        return diff * 1000.0

    # Otherwise values are in meters (e.g. grad=400, stn=350 -> offset = +50.0 m)
    return diff


def format_chainage_display(grad_ch: str | float) -> str:
    """Format gradient chainage for drawing label."""
    try:
        val, unit = parse_chainage_val(grad_ch)
        if unit == "KM" or (unit is None and val >= 5.0):
            return f"CH: {val:.3f} KM"
        if unit == "M":
            # Check if large meter value like 125400
            if val >= 10000.0:
                km = val / 1000.0
                return f"CH: {km:.3f} KM"
            return f"CH: {val:.2f} M"
        return f"CH: {val:.2f} M"
    except Exception:
        return f"CH: {grad_ch}"


class GradientReference(PipelineStep):
    """Pipeline step: Draw gradient annotation symbols on railway alignments."""

    def __init__(self, context=None):
        super().__init__(context)
        if context is not None:
            self.config = getattr(context, "config", context)

    def _platform_polygons(self, doc, layer: str) -> list[list[Point]]:
        """Extract platform polygons from a DXF layer."""
        polygons: list[list[Point]] = []
        for entity in doc.modelspace():
            if entity.dxf.layer != layer or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            if hasattr(entity, "get_points"):
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            elif hasattr(entity, "vertices"):
                pts = [(float(v.dxf.location[0]), float(v.dxf.location[1])) for v in entity.vertices]
            else:
                pts = []
            if len(pts) >= 3:
                polygons.append(pts)
        return polygons

    def _resolve_track(
        self, designation: str, tracks: Dict[str, Sequence[Point]]
    ) -> Tuple[str, Sequence[Point]]:
        """Resolve track designation to an existing track in tracks dict."""
        if not tracks:
            raise ValueError("No track geometry available to attach gradient annotation.")

        desig_clean = str(designation or "").strip()
        desig_upper = desig_clean.upper()
        desig_norm = re.sub(r"[\s\-]+", "_", desig_upper)

        # 1. Exact match
        if desig_clean in tracks:
            return desig_clean, tracks[desig_clean]
        if desig_norm in tracks:
            return desig_norm, tracks[desig_norm]

        # 2. Case-insensitive key match
        for k, pts in tracks.items():
            if k.upper() == desig_upper or k.upper() == desig_norm:
                return k, pts

        # 3. Match via direction in main_directions
        main_dirs = getattr(self.config, "main_directions", {}) or {}
        if "UP" in desig_upper and "DN" not in desig_upper and "DOWN" not in desig_upper:
            for k, d in main_dirs.items():
                if str(d).upper() == "UP" and k in tracks:
                    return k, tracks[k]
        elif "DN" in desig_upper or "DOWN" in desig_upper:
            for k, d in main_dirs.items():
                if str(d).upper() in ("DN", "DOWN") and k in tracks:
                    return k, tracks[k]

        # 4. Match substring e.g. MAIN -> MAIN_LINE
        for k, pts in tracks.items():
            if desig_upper in k.upper() or k.upper() in desig_upper:
                return k, pts

        # 5. Fallback to MAIN_LINE or first available track
        if "MAIN_LINE" in tracks:
            return "MAIN_LINE", tracks["MAIN_LINE"]
        first_key = next(iter(tracks.keys()))
        return first_key, tracks[first_key]

    def _get_station_center_coords(
        self, doc, tracks: Dict[str, Sequence[Point]]
    ) -> Point:
        """Find station building center coordinates or alignment fallback."""
        centres = station_centres_from_dxf(doc)
        if centres:
            return centres[0]

        # Try station requests / platform polygons
        for sreq in getattr(self.config, "stations", []) or []:
            polys = self._platform_polygons(doc, sreq.platform_layer)
            if polys:
                pts = polys[0]
                return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

        # Alignment midpoint fallback
        first_track = tracks.get("MAIN_LINE", next(iter(tracks.values())))
        clean_pts = [(float(p[0]), float(p[1])) for p in first_track]
        mid_idx = len(clean_pts) // 2
        return clean_pts[mid_idx]

    def _get_station_flag_distance(
        self, doc, cleaned_main_track: Sequence[Point], stn_center_pt: Point
    ) -> tuple[float, str]:
        """Find transverse distance and side (LEFT/RIGHT) of the station flag from main track."""
        flag_pts = []
        try:
            for e in doc.modelspace():
                if str(e.dxf.get("layer", "")).upper() == "STATION-FLAG":
                    if e.dxftype() == "LINE":
                        flag_pts.extend([(float(e.dxf.start[0]), float(e.dxf.start[1])), (float(e.dxf.end[0]), float(e.dxf.end[1]))])
                    elif e.dxftype() in ("LWPOLYLINE", "POLYLINE"):
                        flag_pts.extend([(float(p[0]), float(p[1])) for p in e.get_points()])
        except Exception:
            pass

        if flag_pts:
            avg_x = sum(p[0] for p in flag_pts) / len(flag_pts)
            avg_y = sum(p[1] for p in flag_pts) / len(flag_pts)
            proj = nearest_point_on_alignment(cleaned_main_track, (avg_x, avg_y))
            st = point_at_chainage(cleaned_main_track, float(proj.chainage))
            tx, ty = st.tangent
            L = math.hypot(tx, ty) or 1.0
            tx, ty = tx / L, ty / L
            nx, ny = -ty, tx  # standard LEFT normal
            vx = avg_x - proj.point[0]
            vy = avg_y - proj.point[1]
            dist = math.hypot(vx, vy)
            side = "LEFT" if (vx * nx + vy * ny) >= 0 else "RIGHT"
            if dist > 1.0:
                return dist, side

        # Fallback using station center point
        proj = nearest_point_on_alignment(cleaned_main_track, stn_center_pt)
        st = point_at_chainage(cleaned_main_track, float(proj.chainage))
        tx, ty = st.tangent
        L = math.hypot(tx, ty) or 1.0
        tx, ty = tx / L, ty / L
        nx, ny = -ty, tx
        vx = stn_center_pt[0] - proj.point[0]
        vy = stn_center_pt[1] - proj.point[1]
        dist = math.hypot(vx, vy)
        side = "LEFT" if (vx * nx + vy * ny) >= 0 else "RIGHT"
        return dist + 45.0, side
