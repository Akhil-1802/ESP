"""Station buildings: footprints, overlap checks, writing."""

from __future__ import annotations

import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

from common.dxf import (
    add_arrow_head as _add_arrow_head,
    draw_arrow_dimension,
    ensure_text_style as _ensure_text_style,
    resolve_text_insert as _resolve_text_insert,
)
from common.geometry import bounds as _bounds
from platform_gen.track import _extract_points
from station.builder import _building_from_platform, _polygon_area
from station.station_flag import draw_station_flag

from .base import PipelineStep
from .station_label import clear_platform_label_from_station

__all__ = ["StationStep", "StationMixin"]


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

        doc = ezdxf.readfile(self.config.output_dxf)

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
            )
            self._check_station_overlap(doc, building.outline, request.platform_layer)

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
            px, py = -math.sin(ang), math.cos(ang)
            cx, cy = building.center
            half, dash, gap = 50.0, 6.0, 2.5
            s = -half
            while s < half:
                e = min(s + dash, half)
                doc.modelspace().add_line(
                    (cx + px * s, cy + py * s),
                    (cx + px * e, cy + py * e),
                    dxfattribs={"layer": cl_layer, "color": 1},
                )
                s = e + gap
            km_label = _format_station_chainage(getattr(request, "station_chainage", None))
            line1_text = f"C/L OF {request.building_name} CH:0.00 KM"

            tx, ty = cx + px * (half + 3.0) - 25.0, cy + py * (half + 3.0)

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
                ch2_x = c1_pos[0] - px * 2.0
                ch2_y = c1_pos[1] - py * 2.0
                c2_pos = _resolve_text_insert(doc, km_label, 1.0, math.degrees(ang), (ch2_x, ch2_y, 0))
                doc.modelspace().add_text(
                    km_label,
                    dxfattribs={
                        "layer": cl_layer,
                        "color": 1,
                        "style": _ensure_text_style(doc),
                        "height": 1.0,
                        "rotation": math.degrees(ang),
                        "insert": (c2_pos[0], c2_pos[1], 0),
                    },
                )

            dir_layer = "DIRECTION"
            if dir_layer not in doc.layers:
                doc.layers.add(dir_layer, color=1)

            s_building_top = float(request.building_width) / 2.0
            s_flag_bottom = float(half) - 15.5
            s_mark = (s_building_top + s_flag_bottom) / 2.0
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
            pole_base = (cx + px * half, cy + py * half)
            try:
                draw_station_flag(doc, pole_base, flag_up, flag_right, color=1)
            except Exception as exc:
                print(f"   ! Station flag skipped ({exc})")

        doc.saveas(self.config.output_dxf)


class StationMixin(StationStep):
    """Mixin for backward compatibility."""
    pass
