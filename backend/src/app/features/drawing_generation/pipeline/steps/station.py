"""Station buildings: footprints, overlap checks, writing."""

from __future__ import annotations

import logging
import math

from ezdxf.enums import TextEntityAlignment

from ...domain.geometry.operations import bounds as _bounds
from ...domain.platform.track import _extract_points
from ...domain.station.builder import _building_from_platform, _polygon_area
from ...domain.station.station_flag import draw_station_flag
from ...formats.dxf.primitives import add_arrow_head as _add_arrow_head
from ...formats.dxf.primitives import draw_arrow_dimension
from ...formats.dxf.styles import ensure_text_style as _ensure_text_style
from ...formats.dxf.text import _inflate, _register_box, estimate_text_aabb
from ...formats.dxf.text import resolve_text_insert as _resolve_text_insert
from .base import PipelineStep
from .station_label import clear_platform_label_from_station

logger = logging.getLogger(__name__)

__all__ = ["StationStep"]


def _format_station_chainage(val: str | float | None) -> str | None:
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None

    cleaned = val_str
    upper = cleaned.upper()
    for prefix in ("CH :", "CH:", "CH", "KM :", "KM:", "KM"):
        if upper.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            upper = cleaned.upper()
            break

    if upper.endswith("KM"):
        cleaned = cleaned[:-2].strip()
    elif upper.endswith("M"):
        cleaned = cleaned[:-1].strip()

    try:
        num = float(cleaned)
        return f"KM: {num:.3f}"
    except (ValueError, TypeError):
        if "." not in cleaned and "+" not in cleaned:
            return f"KM: {cleaned}.000"
        return f"KM: {cleaned}"


class StationStep(PipelineStep):
    """Pipeline step: Station buildings: footprints, overlap checks, writing."""

    def _check_station_overlap(self, doc, outline, platform_layer: str) -> None:
        """Verify that a new station doesn't overlap existing stations."""
        candidate = _bounds(outline)
        for entity in doc.modelspace():
            if entity.dxf.layer != "STATION-BUILDING" or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            points = _extract_points(entity)
            other = _bounds(points)
            if candidate[0] < other[2] and candidate[2] > other[0] and candidate[1] < other[3] and candidate[3] > other[1]:
                raise ValueError(f"Station overlaps an existing station on platform layer {platform_layer!r}")

    @staticmethod
    def _inside_box(x: float, y: float, box, margin: float = 0.0) -> bool:
        minx, miny, maxx, maxy = box
        return (minx - margin) <= x <= (maxx + margin) and (miny - margin) <= y <= (maxy + margin)

    def _station_footprints(self, doc) -> list:
        """Bounding boxes of station building outlines in the DXF."""
        boxes = []
        for entity in doc.modelspace():
            if entity.dxf.layer != "STATION-BUILDING":
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            pts = _extract_points(entity)
            if len(pts) < 4 or _polygon_area(pts) < 5.0:
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        return boxes

    @staticmethod
    def _clear_platform_label_from_station(
        doc,
        platform,
        building,
        text_layer: str,
        building_length: float,
    ) -> None:
        clear_platform_label_from_station(doc, platform, building, text_layer, building_length)

    def _generate_stations(self) -> None:
        """Generate all stations."""
        if not self.config.stations:
            return

        doc = self._load_document()

        try:
            platform_text_layers = {}
            for preq in getattr(self.config, "platforms", None) or []:
                try:
                    platform_text_layers[str(preq.config.output_layer)] = str(preq.config.text_layer)
                except Exception:
                    continue
        except Exception:
            platform_text_layers = {}

        for index, request in enumerate(self.config.stations, 1):
            polygons = self._platform_polygons(doc, request.platform_layer)
            if not polygons:
                raise ValueError(f"No platform geometry found on layer {request.platform_layer!r}")

            platform = polygons[index - 1] if index <= len(polygons) else polygons[0]
            building = _building_from_platform(
                platform,
                request.building_length,
                request.building_width,
                request.platform_side,
            ) #calculate the exact 4-corner rectangular footprint of the Station Building so it sits flush against the rear edge of the passenger platform
            self._check_station_overlap(doc, building.outline, request.platform_layer)
            request._bridge_outline = list(building.outline)
            if hasattr(self, "_key_plan_building_results"):
                self._key_plan_building_results.append((request, building))

            layer = "STATION-BUILDING"
            if layer not in doc.layers:
                doc.layers.add(layer, color=1)

            if doc.dxfversion >= "AC1015":
                doc.modelspace().add_lwpolyline(building.outline, close=True, dxfattribs={"layer": layer, "color": 1})
                sb_pos = _resolve_text_insert(
                    doc, request.building_name, 1.0, building.angle, building.center, anchor="middle-center"
                )
                label = doc.modelspace().add_mtext(
                    request.building_name,
                    dxfattribs={
                        "layer": layer,
                        "color": 1,
                        "style": _ensure_text_style(doc),
                        "char_height": 1.0,
                        "rotation": building.angle,
                    },
                )
                label.set_location(sb_pos, attachment_point=5)
            else:
                polyline = doc.modelspace().add_polyline2d(building.outline, dxfattribs={"layer": layer, "color": 1})
                polyline.close(True)
                sb_pos = _resolve_text_insert(doc, request.building_name, 1.0, 0.0, building.center)
                doc.modelspace().add_text(
                    request.building_name,
                    dxfattribs={
                        "layer": layer,
                        "color": 1,
                        "style": _ensure_text_style(doc),
                        "height": 1.0,
                        "insert": (sb_pos[0], sb_pos[1], sb_pos[2] if len(tuple(sb_pos)) >= 3 else 0),
                    },
                )

            c0, c1, c2, c3 = building.outline[:4]
            bcx, bcy = building.center

            def _order_outward(a, b, ox, oy):
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy) or 1.0
                if (-dy / L) * ox + (dx / L) * oy < 0:
                    return b, a
                return a, b

            omx, omy = (c2[0] + c3[0]) / 2.0 - bcx, (c2[1] + c3[1]) / 2.0 - bcy
            q1, q2 = _order_outward(c3, c2, omx, omy)
            draw_arrow_dimension(
                doc, q1, q2, 2.0, f"{request.building_length:.2f}", layer, 1, 0.8
            )
            smx, smy = (c0[0] + c3[0]) / 2.0 - bcx, (c0[1] + c3[1]) / 2.0 - bcy
            r1, r2 = _order_outward(c0, c3, smx, smy)
            draw_arrow_dimension(
                doc, r1, r2, 2.0, f"{request.building_width:.2f}", layer, 1, 0.8
            )

            cl_layer = "STATION-CENTER"
            if cl_layer not in doc.layers:
                doc.layers.add(cl_layer, color=1)
            ang = math.radians(building.angle)
            tx_tangent, ty_tangent = math.cos(ang), math.sin(ang)
            px, py = -math.sin(ang), math.cos(ang)
            cx, cy = building.center

            # Station outer edge along perpendicular outward vector (px, py)
            s_building_top = float(request.building_width) / 2.0

            # Keep flag, labels, and centerline strictly under the 40m boundary (s_building_top + 40.0)
            s_top = s_building_top + 32.0
            s_bottom = -50.0
            dash, gap = 6.0, 2.5
            s = s_bottom
            while s < s_top:
                e = min(s + dash, s_top)
                doc.modelspace().add_line(
                    (cx + px * s, cy + py * s),
                    (cx + px * e, cy + py * e),
                    dxfattribs={"layer": cl_layer, "color": 1},
                )
                s = e + gap
            km_label = _format_station_chainage(getattr(request, "station_chainage", None))
            line1_text = f"C/L OF {request.building_name} CH:0.00 KM"

            tx = cx + px * (s_top + 3.0) - tx_tangent * 25.0
            ty = cy + py * (s_top + 3.0) - ty_tangent * 25.0

            c1_pos = _resolve_text_insert(doc, line1_text, 1.0, math.degrees(ang), (tx, ty, 0))
            doc.modelspace().add_text(
                line1_text,
                dxfattribs={
                    "layer": cl_layer,
                    "color": 1,
                    "style": _ensure_text_style(doc),
                    "height": 1.0,
                    "rotation": math.degrees(ang),
                    "insert": (c1_pos[0], c1_pos[1], 0),
                },
            )

            if km_label:
                # Center the KM label relative to line 1
                w1 = len(line1_text) * 1.0 * 0.7
                w2 = len(km_label) * 1.0 * 0.7
                center_offset = (w1 - w2) / 2.0
                ch2_x = c1_pos[0] - px * 2.0 + tx_tangent * center_offset
                ch2_y = c1_pos[1] - py * 2.0 + ty_tangent * center_offset
                c2_pos = (ch2_x, ch2_y, 0)
                doc.modelspace().add_text(
                    km_label,
                    dxfattribs={
                        "layer": cl_layer,
                        "color": 1,
                        "style": _ensure_text_style(doc),
                        "height": 1.0,
                        "rotation": math.degrees(ang),
                        "insert": c2_pos,
                    },
                )
                box = _inflate(estimate_text_aabb(km_label, 1.0, math.degrees(ang), (ch2_x, ch2_y)), 0.5)
                _register_box(doc, box)

            dir_layer = "DIRECTION"
            if dir_layer not in doc.layers:
                doc.layers.add(dir_layer, color=1)

            s_flag_bottom = float(s_top) - 12.0
            s_mark = (s_building_top + s_flag_bottom) / 2.0
            if s_mark < 18.0:
                s_mark = min(18.0, s_flag_bottom - 4.0)
            mc_x = cx + px * s_mark
            mc_y = cy + py * s_mark

            tx_tangent, ty_tangent = math.cos(ang), math.sin(ang)
            half_shaft = 8.0

            p_left = (mc_x - tx_tangent * half_shaft, mc_y - ty_tangent * half_shaft)
            p_right = (mc_x + tx_tangent * half_shaft, mc_y + ty_tangent * half_shaft)

            doc.modelspace().add_line(p_left, p_right, dxfattribs={"layer": dir_layer, "color": 1})
            _add_arrow_head(doc, p_left, (-tx_tangent, -ty_tangent), dir_layer, color=1, length=2.0, half_width=0.7)
            _add_arrow_head(doc, p_right, (tx_tangent, ty_tangent), dir_layer, color=1, length=2.0, half_width=0.7)

            main_dir = (getattr(self.config, "main_directions", None) or {}).get("MAIN_LINE", "").upper()
            if main_dir == "UP":
                left_label, right_label = "DN", "UP"
            else:
                left_label, right_label = "UP", "DN"

            ang_deg = math.degrees(math.atan2(ty_tangent, tx_tangent))
            while ang_deg > 90.0:
                ang_deg -= 180.0
            while ang_deg < -90.0:
                ang_deg += 180.0

            text_gap = 1.2
            pt_left = (p_left[0] - tx_tangent * text_gap, p_left[1] - ty_tangent * text_gap)
            pt_right = (p_right[0] + tx_tangent * text_gap, p_right[1] + ty_tangent * text_gap)

            t_left = doc.modelspace().add_text(
                left_label,
                dxfattribs={
                    "layer": dir_layer,
                    "color": 1,
                    "style": _ensure_text_style(doc),
                    "height": 1.0,
                    "rotation": ang_deg,
                },
            )
            t_left.set_placement(pt_left, align=TextEntityAlignment.MIDDLE_RIGHT)

            t_right = doc.modelspace().add_text(
                right_label,
                dxfattribs={
                    "layer": dir_layer,
                    "color": 1,
                    "style": _ensure_text_style(doc),
                    "height": 1.0,
                    "rotation": ang_deg,
                },
            )
            t_right.set_placement(pt_right, align=TextEntityAlignment.MIDDLE_LEFT)

            try:
                text_layer = platform_text_layers.get(
                    str(request.platform_layer), f"{request.platform_layer}_TEXT"
                )
                self._clear_platform_label_from_station(
                    doc, platform, building, text_layer, request.building_length
                )
            except Exception:
                pass

            flag_right = (math.cos(ang), math.sin(ang))
            flag_up = (px, py)
            pole_base = (cx + px * s_top, cy + py * s_top)
            try:
                draw_station_flag(doc, pole_base, flag_up, flag_right, color=1)
            except Exception as exc:
                logger.info(f"   ! Station flag skipped ({exc})")

        self._save_document(doc)
