"""Gradient annotation pipeline step.

Places straight horizontal gradient annotation symbols at the correct location
along the railway track alignment using station center chainage as reference.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Sequence, Tuple

import ezdxf

from common.alignment import point_at_chainage
from common.dxf import ensure_layer, ensure_text_style, resolve_text_insert
from common.geometry import Point, nearest_point_on_alignment, polyline_length

from .base import PipelineStep
from .chainage_collect import station_centres_from_dxf

__all__ = ["GradientStep", "GradientMixin", "compute_gradient_offset", "parse_chainage_val"]


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
        return grad_val - stn_val
    if grad_unit == "M" and stn_unit == "KM":
        return grad_val - (stn_val * 1000.0)
    if grad_unit == "KM" and stn_unit == "M":
        return (grad_val * 1000.0) - stn_val

    # When neither unit is explicitly given:
    # If values are in typical route KM range (>= 5.0) and close, difference is in KM.
    if abs(grad_val - stn_val) <= 50.0 and (stn_val >= 5.0 or grad_val >= 5.0):
        return (grad_val - stn_val) * 1000.0

    # Otherwise assume values are given in meters.
    return grad_val - stn_val


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


class GradientStep(PipelineStep):
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

    def _generate_gradients(self, tracks: Dict[str, Sequence[Point]]) -> None:
        """Generate gradient annotations on railway track alignments."""
        gradients = getattr(self.config, "gradients", None)
        if not gradients:
            return

        doc = ezdxf.readfile(self.config.output_dxf)

        # Wipe existing gradient layer
        layer_name = "GRADIENT"
        self._wipe_layers(doc, {layer_name})
        ensure_layer(doc, layer_name, color=1)

        # Determine station center reference chainage
        stn_ch_input = None
        for sreq in getattr(self.config, "stations", []) or []:
            if getattr(sreq, "station_chainage", None) is not None:
                stn_ch_input = sreq.station_chainage
                break

        stn_center_pt = self._get_station_center_coords(doc, tracks)

        for grad in gradients:
            track_name, track_points = self._resolve_track(
                grad.track_designation, tracks
            )
            cleaned_track = [(float(p[0]), float(p[1])) for p in track_points]
            if len(cleaned_track) < 2:
                raise ValueError(f"Track '{track_name}' has insufficient geometry vertices.")

            total_len = polyline_length(cleaned_track)

            # Project station center onto target track
            stn_proj = nearest_point_on_alignment(cleaned_track, stn_center_pt)
            stn_track_ch = float(stn_proj.chainage)

            # Compute relative offset along alignment
            offset_m = compute_gradient_offset(grad.chainage, stn_ch_input)
            target_track_ch = stn_track_ch + offset_m

            # Bounds check
            if target_track_ch < -1e-6 or target_track_ch > total_len + 1e-6:
                raise ValueError(
                    f"Gradient chainage '{grad.chainage}' (relative offset {offset_m:+.2f} m, "
                    f"computed target track chainage {target_track_ch:.2f} m) falls outside "
                    f"track '{track_name}' extent [0.00 m, {total_len:.2f} m]."
                )

            # Exact point on track alignment
            target_track_ch = min(max(target_track_ch, 0.0), total_len)
            sp = point_at_chainage(cleaned_track, target_track_ch)
            px, py = sp.point

            # Configurable offset and line length
            off_dist = float(grad.offset) if grad.offset is not None else 12.0
            line_len = float(grad.line_length) if grad.line_length is not None else 24.0

            # Annotation bar location
            bar_y = py + off_dist
            x_start = px - line_len / 2.0
            x_end = px + line_len / 2.0

            # 1. Connecting stem / leader line from track to horizontal bar
            doc.modelspace().add_line(
                (px, py),
                (px, bar_y),
                dxfattribs={"layer": layer_name, "color": 1},
            )

            # Small 0.6m cross tick at alignment connection point
            doc.modelspace().add_line(
                (px - 0.6, py),
                (px + 0.6, py),
                dxfattribs={"layer": layer_name, "color": 1},
            )

            # 2. Straight horizontal annotation line
            doc.modelspace().add_line(
                (x_start, bar_y),
                (x_end, bar_y),
                dxfattribs={"layer": layer_name, "color": 1},
            )

            # 3. Text labels
            style_name = ensure_text_style(doc)
            text_height = 1.0
            text_x = x_start + 1.0  # inset 1.0 m from line start

            # Above line: Gradient value and direction
            grad_val_str = str(grad.gradient_value or "").strip()
            direction_str = str(grad.direction or "UP").strip().upper()
            line1_above = f"{grad_val_str} {direction_str}".strip() if grad_val_str else direction_str
            ins1 = resolve_text_insert(
                doc, line1_above, text_height, 0.0, (text_x, bar_y + 1.2, 0)
            )
            doc.modelspace().add_text(
                line1_above,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_height,
                    "rotation": 0.0,
                    "insert": (ins1[0], ins1[1], 0),
                },
            )

            # Track designation label (above line1 or alongside)
            track_desig_str = str(grad.track_designation or track_name).strip()
            if track_desig_str:
                ins_track = resolve_text_insert(
                    doc, track_desig_str, 0.8, 0.0, (text_x, bar_y + 2.8, 0)
                )
                doc.modelspace().add_text(
                    track_desig_str,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 1,
                        "style": style_name,
                        "height": 0.8,
                        "rotation": 0.0,
                        "insert": (ins_track[0], ins_track[1], 0),
                    },
                )

            # Below line: Gradient chainage label
            ch_label = format_chainage_display(grad.chainage)
            ins_ch = resolve_text_insert(
                doc, ch_label, text_height, 0.0, (text_x, bar_y - 2.0, 0)
            )
            doc.modelspace().add_text(
                ch_label,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_height,
                    "rotation": 0.0,
                    "insert": (ins_ch[0], ins_ch[1], 0),
                },
            )

            # Below line: RL label (if provided)
            if grad.rl is not None and str(grad.rl).strip() != "":
                rl_clean = str(grad.rl).strip()
                upper_rl = rl_clean.upper()
                if upper_rl.startswith("RL:") or upper_rl.startswith("RL :"):
                    rl_val = rl_clean[3:].strip()
                elif upper_rl.startswith("RL"):
                    rl_val = rl_clean[2:].strip()
                else:
                    rl_val = rl_clean
                if not rl_val.upper().endswith("M"):
                    rl_val = f"{rl_val} M"
                rl_label = f"RL: {rl_val}"
                ins_rl = resolve_text_insert(
                    doc, rl_label, 0.8, 0.0, (text_x, bar_y - 3.4, 0)
                )
                doc.modelspace().add_text(
                    rl_label,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 1,
                        "style": style_name,
                        "height": 0.8,
                        "rotation": 0.0,
                        "insert": (ins_rl[0], ins_rl[1], 0),
                    },
                )

        doc.saveas(self.config.output_dxf)


class GradientMixin(GradientStep):
    """Mixin adding gradient generation to ESPGenerator."""
    pass
