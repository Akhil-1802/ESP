"""Land boundary generation step.

Land boundary (green dashed line, layer LAND_BOUNDARY, color 3):
- 40m away from the station on the side where the station is present.
- 70m away from the last entity present on the other side where there is no station.
- Length of land boundary matches exactly the displayed length of the MAIN_LINE.
"""

from __future__ import annotations

import math
from typing import Sequence

import ezdxf

from common.constants import (
    LAND_BOUNDARY_COLOR,
    LAND_BOUNDARY_DASH_M,
    LAND_BOUNDARY_GAP_M,
    LAND_BOUNDARY_LINETYPE,
)
from common.dxf import ensure_layer
from common.geometry import Point, nearest_point_on_alignment, point_at_chainage
from track.generator import _offset_alignment
from .base import PipelineStep

__all__ = ["BoundaryStep", "BoundaryMixin"]

EXCLUDED_LAYER_SUBSTRINGS = (
    "CHAINAGE",
    "DIRECTION",
    "TRACK_CENTER",
    "CENTER",
    "LAND_BOUNDARY",
    "BOUNDARY",
    "FLAG",
    "DIM",
    "LABEL",
    "TEXT",
    "CAL",
    "SRJ",
    "FM",
    "FOULING",
    "OVER_RUN",
    "OVERRUN",
    "DEAD_END",
    "BUFFER",
    "MARKER",
)

ALLOWED_ENTITY_TYPES = (
    "LINE",
    "LWPOLYLINE",
    "POLYLINE",
    "CIRCLE",
    "ARC",
    "SPLINE",
    "SOLID",
)


def _lateral_offset_on_main(main_points: Sequence[Point], off_pt: Point) -> float | None:
    """Signed lateral offset (m) of a point from MAIN alignment (+LEFT, -RIGHT)."""
    try:
        if len(main_points) < 2:
            return None
        proj = nearest_point_on_alignment(main_points, off_pt)
        sp = point_at_chainage(main_points, proj.chainage)
        tx, ty = sp.tangent
        n = math.hypot(tx, ty) or 1.0
        tx, ty = tx / n, ty / n
        vx, vy = off_pt[0] - proj.point[0], off_pt[1] - proj.point[1]
        return float(-ty * vx + tx * vy)
    except Exception:
        return None


def _extract_entity_points(entity) -> list[tuple[float, float]]:
    """Extract 2D coordinate points from a DXF entity."""
    kind = entity.dxftype()
    pts: list[tuple[float, float]] = []
    try:
        if kind == "LINE":
            pts.append((float(entity.dxf.start.x), float(entity.dxf.start.y)))
            pts.append((float(entity.dxf.end.x), float(entity.dxf.end.y)))
        elif kind == "LWPOLYLINE":
            pts.extend((float(p[0]), float(p[1])) for p in entity.get_points())
        elif kind == "POLYLINE":
            pts.extend((float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices)
        elif kind in ("CIRCLE", "ARC"):
            cx, cy = float(entity.dxf.center.x), float(entity.dxf.center.y)
            r = float(entity.dxf.radius)
            pts.extend([(cx, cy + r), (cx, cy - r), (cx + r, cy), (cx - r, cy)])
        elif kind == "SPLINE":
            for p in getattr(entity, "fit_points", None) or getattr(entity, "control_points", None) or []:
                pts.append((float(p[0]), float(p[1])))
    except Exception:
        pass
    return pts


class BoundaryStep(PipelineStep):
    """Pipeline step: generate green dashed land boundary lines."""

    def _generate_land_boundary(self, tracks: dict) -> None:
        """Draw land boundary lines only when Done (enable_main_line_trim) is activated."""
        if not getattr(self.config, "enable_main_line_trim", False):
            # Land boundary is not shown before the Done button is clicked
            try:
                doc = ezdxf.readfile(self.config.output_dxf)
                removed = False
                for entity in list(doc.modelspace()):
                    if str(getattr(entity.dxf, "layer", "")).strip().upper() == "LAND_BOUNDARY":
                        doc.modelspace().delete_entity(entity)
                        removed = True
                if removed:
                    doc.saveas(self.config.output_dxf)
            except Exception:
                pass
            return

        main_pts = tracks.get("MAIN_LINE")
        if not main_pts or len(main_pts) < 2:
            return

        cleaned_main = [(float(p[0]), float(p[1])) for p in main_pts]

        try:
            doc = ezdxf.readfile(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Land boundary DXF read skipped ({exc})")
            return

        station_points: list[tuple[float, float]] = []
        entity_points: list[tuple[float, float]] = []

        # 1. Collect points from existing DXF physical entities
        for entity in doc.modelspace():
            layer = str(getattr(entity.dxf, "layer", "")).strip().upper()
            if not layer:
                continue
            if any(sub in layer for sub in EXCLUDED_LAYER_SUBSTRINGS):
                continue
            if entity.dxftype() not in ALLOWED_ENTITY_TYPES:
                continue

            pts = _extract_entity_points(entity)
            if not pts:
                continue

            if layer == "STATION-BUILDING":
                station_points.extend(pts)
            else:
                entity_points.extend(pts)

        # 2. Also ensure all generated track points are included
        for trk_pts in tracks.values():
            if trk_pts:
                entity_points.extend((float(p[0]), float(p[1])) for p in trk_pts)

        # 3. Calculate lateral offsets relative to MAIN_LINE (+LEFT, -RIGHT)
        station_offsets: list[float] = []
        for p in station_points:
            off = _lateral_offset_on_main(cleaned_main, p)
            if off is not None and math.isfinite(off):
                station_offsets.append(off)

        entity_offsets: list[float] = []
        for p in entity_points:
            off = _lateral_offset_on_main(cleaned_main, p)
            if off is not None and math.isfinite(off):
                entity_offsets.append(off)

        # 4. Partition by side (LEFT: off > 0, RIGHT: off < 0)
        stn_left = [off for off in station_offsets if off > 0.5]
        stn_right = [abs(off) for off in station_offsets if off < -0.5]

        has_station_left = len(stn_left) > 0
        has_station_right = len(stn_right) > 0

        ent_left = [off for off in entity_offsets if off > 0.0]
        ent_right = [abs(off) for off in entity_offsets if off < -0.0]

        # 5. Compute clearances
        # On the side where station is present: 40m away from the station.
        # On the other side where there is no station: 70m away from the last entity present.
        if has_station_left:
            dist_left = max(stn_left) + 40.0
        else:
            dist_left = max(ent_left, default=0.0) + 70.0

        if has_station_right:
            dist_right = max(stn_right) + 40.0
        else:
            dist_right = max(ent_right, default=0.0) + 70.0

        # 6. Generate offset boundaries spanning the exact length of MAIN_LINE
        left_boundary_pts = _offset_alignment(cleaned_main, dist_left, "LEFT")
        right_boundary_pts = _offset_alignment(cleaned_main, dist_right, "RIGHT")

        # 7. Remove any previous LAND_BOUNDARY entities in DXF
        for entity in list(doc.modelspace()):
            try:
                if str(getattr(entity.dxf, "layer", "")).strip().upper() == "LAND_BOUNDARY":
                    doc.modelspace().delete_entity(entity)
            except Exception:
                pass

        # 8. Store real dashes in the DXF, rather than relying on preview styling.
        global_scale = float(doc.header.get("$LTSCALE", 1.0))
        if not math.isfinite(global_scale) or global_scale <= 0.0:
            global_scale = 1.0
        # Compensate in this dedicated linetype, so the effective dash/gap is
        # always 8m/5m. R12 does not export per-entity linetype scales.
        pattern = [(LAND_BOUNDARY_DASH_M + LAND_BOUNDARY_GAP_M) / global_scale,
                   LAND_BOUNDARY_DASH_M / global_scale, -LAND_BOUNDARY_GAP_M / global_scale]
        if LAND_BOUNDARY_LINETYPE not in doc.linetypes:
            doc.linetypes.add(LAND_BOUNDARY_LINETYPE, pattern=pattern,
                              description="Land boundary: 8m dash, 5m gap")
        else:
            doc.linetypes.get(LAND_BOUNDARY_LINETYPE).setup_pattern(pattern)
        ensure_layer(doc, "LAND_BOUNDARY", color=LAND_BOUNDARY_COLOR,
                     linetype=LAND_BOUNDARY_LINETYPE)
        layer = doc.layers.get("LAND_BOUNDARY")
        # ensure_layer does not reset an existing layer's colour. Clear any
        # true-colour override, which CAD would otherwise prefer to ACI green.
        layer.dxf.color = LAND_BOUNDARY_COLOR
        layer.dxf.discard("true_color")
        layer.dxf.discard("color_name")
        layer.dxf.discard("transparency")
        layer.on()
        layer.thaw()
        attrs = {
            "layer": "LAND_BOUNDARY",
            "color": LAND_BOUNDARY_COLOR,
            "linetype": LAND_BOUNDARY_LINETYPE,
            "ltscale": 1.0,
            # Continue the pattern across short surveyed polyline segments.
            "flags": 128,
        }
        for b_pts in (left_boundary_pts, right_boundary_pts):
            try:
                if doc.dxfversion >= "AC1015":
                    doc.modelspace().add_lwpolyline(
                        b_pts,
                        close=False,
                        dxfattribs=attrs,
                    )
                else:
                    doc.modelspace().add_polyline2d(
                        b_pts,
                        dxfattribs=attrs,
                    )
            except Exception as exc:
                print(f"   ! Failed to write land boundary line ({exc})")

        try:
            doc.saveas(self.config.output_dxf)
            print(
                f"   ✓ Land boundary written (LEFT: {dist_left:.1f}m {'(station+40m)' if has_station_left else '(entity+70m)'}, "
                f"RIGHT: {dist_right:.1f}m {'(station+40m)' if has_station_right else '(entity+70m)'})"
            )
        except Exception as exc:
            print(f"   ! Land boundary DXF save skipped ({exc})")


class BoundaryMixin(BoundaryStep):
    """Mixin for pipeline orchestrator."""
    pass
