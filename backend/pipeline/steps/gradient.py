"""Gradient annotation pipeline step.

Places straight horizontal gradient annotation symbols at the correct location
along the railway track alignment using station center chainage as reference.
"""

from __future__ import annotations

import math
import re
from typing import Dict, Sequence, Tuple

import ezdxf
from ezdxf import bbox

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

        all_centres = station_centres_from_dxf(doc)
        station_markers = getattr(self.config, "station_markers", None) or []
        stn_requests = getattr(self.config, "stations", None) or []

        # Find reference main track geometry for station flag transverse axis
        first_track = tracks.get("MAIN_LINE", next(iter(tracks.values())))
        cleaned_main = [(float(p[0]), float(p[1])) for p in first_track]
        default_stn_center = self._get_station_center_coords(doc, tracks)

        for grad in gradients:
            stn_idx = getattr(grad, "station_index", None)
            if stn_idx is None and len(station_markers) == 1:
                stn_idx = 0

            # Determine station reference chainage for this specific station
            stn_ch_input = None
            if stn_idx is not None and 0 <= stn_idx < len(station_markers):
                sm = station_markers[stn_idx]
                if isinstance(sm, dict):
                    stn_ch_input = sm.get("chainage") or (f"{sm.get('km')}+{sm.get('m')}" if sm.get("km") is not None else None)
                else:
                    stn_ch_input = getattr(sm, "chainage", None)

            if stn_ch_input is None and stn_idx is not None and 0 <= stn_idx < len(stn_requests):
                stn_ch_input = getattr(stn_requests[stn_idx], "station_chainage", None)

            if stn_ch_input is None:
                for sreq in stn_requests:
                    if getattr(sreq, "station_chainage", None) is not None:
                        stn_ch_input = sreq.station_chainage
                        break

            # Determine station center point for this specific station
            if stn_idx is not None and all_centres and 0 <= stn_idx < len(all_centres):
                stn_center_pt = all_centres[stn_idx]
            elif stn_idx is not None and 0 <= stn_idx < len(station_markers):
                try:
                    km_val = float(sm.get("km", 0) if isinstance(sm, dict) else getattr(sm, "km", 0) or 0)
                    m_val = float(sm.get("m", 0) if isinstance(sm, dict) else getattr(sm, "m", 0) or 0)
                    start_km = float(getattr(self.config, "start_km", 0) or 0)
                    start_m = float(getattr(self.config, "start_m", 0) or 0)
                    d_m = max(0.0, (km_val * 1000.0 + m_val) - (start_km * 1000.0 + start_m))
                    stn_center_pt = point_at_chainage(cleaned_main, d_m).point
                except Exception:
                    stn_center_pt = default_stn_center
            elif all_centres:
                stn_center_pt = all_centres[0]
            else:
                stn_center_pt = default_stn_center

            flag_dist, flag_side = self._get_station_flag_distance(doc, cleaned_main, stn_center_pt)
            track_name, track_points = self._resolve_track(
                grad.track_designation, tracks
            )
            cleaned_track = [(float(p[0]), float(p[1])) for p in track_points]
            if len(cleaned_track) < 2:
                raise ValueError(f"Track '{track_name}' has insufficient geometry vertices.")

            total_len = polyline_length(cleaned_track)

            # Project station center onto target track to get station reference chainage
            stn_proj = nearest_point_on_alignment(cleaned_track, stn_center_pt)
            stn_track_ch = float(stn_proj.chainage)

            # Compute relative offset along alignment using chainage
            if grad.chainage is not None and str(grad.chainage).strip() != "":
                offset_m = compute_gradient_offset(grad.chainage, stn_ch_input)
            elif getattr(grad, "km", None) is not None and str(grad.km).strip() != "":
                m_val = getattr(grad, "m", None)
                km_m_str = f"{grad.km}+{m_val}" if m_val is not None and str(m_val).strip() != "" else str(grad.km)
                offset_m = compute_gradient_offset(km_m_str, stn_ch_input)
            else:
                offset_m = 0.0

            target_track_ch = stn_track_ch + offset_m

            # Bounds check
            if target_track_ch < -1e-6 or target_track_ch > total_len + 1e-6:
                raise ValueError(
                    f"Gradient chainage '{grad.chainage}' (relative offset {offset_m:+.2f} m, "
                    f"computed target track chainage {target_track_ch:.2f} m) falls outside "
                    f"track '{track_name}' extent [0.00 m, {total_len:.2f} m]."
                )

            # Exact point and tangent on track alignment at the gradient chainage
            target_track_ch = min(max(target_track_ch, 0.0), total_len)
            sp = point_at_chainage(cleaned_track, target_track_ch)
            px, py = sp.point
            tx, ty = sp.tangent
            tangent_len = math.hypot(tx, ty) or 1.0
            tx, ty = tx / tangent_len, ty / tangent_len

            # Normal vector pointing towards the station flag axis
            if flag_side == "LEFT":
                nx, ny = -ty, tx
            else:
                nx, ny = ty, -tx

            # Position along the same transverse axis as the station flag at its proper chainage
            transverse_dist = flag_dist
            gx = px + nx * transverse_dist
            gy = py + ny * transverse_dist

            # Fixed compact gradient line length matching reference image (10.0 m total: 5.0m left, 5.0m right)
            seg_len = 5.0
            slope_delta = 1.2
            p_center = (gx, gy)

            # Resolve Left and Right values and directions
            left_raw = getattr(grad, "left_gradient_value", None)
            right_raw = getattr(grad, "right_gradient_value", None)
            left_dir_str = str(getattr(grad, "left_direction", None) or "STRAIGHT").strip().upper()
            right_dir_str = str(getattr(grad, "right_direction", None) or getattr(grad, "direction", None) or "RISE").strip().upper()

            # Fallback if only gradient_value was provided
            if not left_raw and not right_raw and getattr(grad, "gradient_value", None):
                parts = [p.strip() for p in re.split(r"[/,]", str(grad.gradient_value)) if p.strip()]
                if len(parts) >= 2:
                    left_raw, right_raw = parts[0], parts[1]
                else:
                    right_raw = str(grad.gradient_value).strip()

            # Normalize directions
            def _norm_dir(d: str) -> str:
                d_up = d.upper()
                if d_up in ("RISE", "UP"):
                    return "RISE"
                if d_up in ("DOWN", "DN"):
                    return "DOWN"
                return "STRAIGHT"

            left_dir = _norm_dir(left_dir_str)
            right_dir = _norm_dir(right_dir_str)

            # Center point is the reference:
            # - RISE: goes UPWARD (+nx * slope_delta) from center
            # - DOWN: goes DOWNWARD (-nx * slope_delta) from center
            # - STRAIGHT: straight / horizontal (0 * nx) from center

            # Left endpoint (extending from center to the left)
            if left_dir == "RISE":
                p_left = (p_center[0] - tx * seg_len + nx * slope_delta, p_center[1] - ty * seg_len + ny * slope_delta)
            elif left_dir == "DOWN":
                p_left = (p_center[0] - tx * seg_len - nx * slope_delta, p_center[1] - ty * seg_len - ny * slope_delta)
            else:  # STRAIGHT
                p_left = (p_center[0] - tx * seg_len, p_center[1] - ty * seg_len)

            # Right endpoint (extending from center to the right)
            if right_dir == "RISE":
                p_right = (p_center[0] + tx * seg_len + nx * slope_delta, p_center[1] + ty * seg_len + ny * slope_delta)
            elif right_dir == "DOWN":
                p_right = (p_center[0] + tx * seg_len - nx * slope_delta, p_center[1] + ty * seg_len - ny * slope_delta)
            else:  # STRAIGHT
                p_right = (p_center[0] + tx * seg_len, p_center[1] + ty * seg_len)

            # Create a BLOCK so the gradient is a single, complete component in AutoCAD
            # that can be selected and moved at one time with its base grip at p_center.
            clean_ch_str = re.sub(r"[^A-Za-z0-9_]", "_", str(grad.chainage or target_track_ch))
            base_block_name = f"GRADIENT_{clean_ch_str}"
            block_name = base_block_name
            counter = 1
            while block_name in doc.blocks:
                counter += 1
                block_name = f"{base_block_name}_{counter}"

            block = doc.blocks.new(name=block_name, base_point=(0, 0, 0))

            # Draw left and right slanted/straight line segments inside the block (relative to center 0,0)
            p_left_rel = (p_left[0] - p_center[0], p_left[1] - p_center[1])
            p_center_rel = (0.0, 0.0)
            p_right_rel = (p_right[0] - p_center[0], p_right[1] - p_center[1])

            block.add_line(p_left_rel, p_center_rel, dxfattribs={"layer": layer_name, "color": 1})
            block.add_line(p_center_rel, p_right_rel, dxfattribs={"layer": layer_name, "color": 1})

            style_name = ensure_text_style(doc)

            def _clean_num(val_str: str | None) -> str:
                if not val_str:
                    return ""
                s = str(val_str).strip()
                lower = s.lower()
                if lower.startswith("1 in "):
                    return s[5:].strip()
                if lower.startswith("1 in"):
                    return s[4:].strip()
                if lower.startswith("1:"):
                    return s[2:].strip()
                return s

            # 1. Left gradient value above left segment (close to line with a little space)
            left_val_clean = _clean_num(left_raw)
            text_h_grad = 0.8
            if left_val_clean:
                dx_l = p_center[0] - p_left[0]
                dy_l = p_center[1] - p_left[1]
                hyp_l = math.hypot(dx_l, dy_l) or 1.0
                ux_l, uy_l = dx_l / hyp_l, dy_l / hyp_l
                unx_l, uny_l = -uy_l, ux_l
                if uny_l < 0:
                    unx_l, uny_l = -unx_l, -uny_l
                ang_l = math.degrees(math.atan2(uy_l, ux_l))
                while ang_l > 90.0:
                    ang_l -= 180.0
                while ang_l < -90.0:
                    ang_l += 180.0
                mid_l = ((p_left[0] + p_center[0]) / 2.0, (p_left[1] + p_center[1]) / 2.0)
                w_l = len(left_val_clean) * text_h_grad * 0.75
                ins_l_rel = (
                    (mid_l[0] - ux_l * (w_l / 2.0) + unx_l * 0.40) - p_center[0],
                    (mid_l[1] - uy_l * (w_l / 2.0) + uny_l * 0.40) - p_center[1],
                    0,
                )
                block.add_text(
                    left_val_clean,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 1,
                        "style": style_name,
                        "height": text_h_grad,
                        "rotation": ang_l,
                        "insert": ins_l_rel,
                    },
                )

            # 2. Right gradient value above right segment (close to line with a little space)
            right_val_clean = _clean_num(right_raw)
            if right_val_clean:
                dx_r = p_right[0] - p_center[0]
                dy_r = p_right[1] - p_center[1]
                hyp_r = math.hypot(dx_r, dy_r) or 1.0
                ux_r, uy_r = dx_r / hyp_r, dy_r / hyp_r
                unx_r, uny_r = -uy_r, ux_r
                if uny_r < 0:
                    unx_r, uny_r = -unx_r, -uny_r
                ang_r = math.degrees(math.atan2(uy_r, ux_r))
                while ang_r > 90.0:
                    ang_r -= 180.0
                while ang_r < -90.0:
                    ang_r += 180.0
                mid_r = ((p_center[0] + p_right[0]) / 2.0, (p_center[1] + p_right[1]) / 2.0)
                w_r = len(right_val_clean) * text_h_grad * 0.75
                ins_r_rel = (
                    (mid_r[0] - ux_r * (w_r / 2.0) + unx_r * 0.40) - p_center[0],
                    (mid_r[1] - uy_r * (w_r / 2.0) + uny_r * 0.40) - p_center[1],
                    0,
                )
                block.add_text(
                    right_val_clean,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 1,
                        "style": style_name,
                        "height": text_h_grad,
                        "rotation": ang_r,
                        "insert": ins_r_rel,
                    },
                )

            # Direction / Line text: prioritize user-selected direction ("UP" or "DN")
            grad_dir_attr = str(getattr(grad, "direction", "") or "").strip().upper()
            if grad_dir_attr in ("DN", "DOWN"):
                dir_short = "DN"
            elif grad_dir_attr in ("UP", "RISE"):
                dir_short = "UP"
            else:
                desig_upper = str(grad.track_designation or track_name).upper()
                main_dirs = getattr(self.config, "main_directions", {}) or {}
                track_dir = main_dirs.get(track_name) or main_dirs.get(grad.track_designation)
                if track_dir:
                    dir_short = "UP" if str(track_dir).upper() == "UP" else ("DN" if str(track_dir).upper() in ("DN", "DOWN") else str(track_dir).upper())
                elif "DN" in desig_upper or "DOWN" in desig_upper:
                    dir_short = "DN"
                else:
                    dir_short = "UP"

            dir_line_text = f"{dir_short} LINE"

            # Chainage text
            if grad.chainage is not None and str(grad.chainage).strip() != "":
                ch_num, _ = parse_chainage_val(str(grad.chainage))
                ch_str = f"CH: {ch_num:.2f}"
            else:
                ch_str = f"CH: {target_track_ch:.2f}"

            # Format Left and Right labels matching consistent standard:
            # - Left side of marker: ALWAYS CH only (e.g. "CH: 400.00")
            # - Right side of marker: RL (if present) and Direction LINE (e.g. "RL: 97.53m" and "UP LINE")
            left_text = ch_str
            right_labels = []
            if grad.rl is not None and str(grad.rl).strip() != "":
                rl_clean = str(grad.rl).strip()
                upper_rl = rl_clean.upper()
                if upper_rl.startswith("RL:") or upper_rl.startswith("RL :"):
                    rl_val = rl_clean[3:].strip()
                elif upper_rl.startswith("RL"):
                    rl_val = rl_clean[2:].strip()
                else:
                    rl_val = rl_clean
                if rl_val.upper().endswith("M"):
                    rl_val = rl_val[:-1].strip()

                right_labels.append(f"RL: {rl_val}m" if not rl_val.endswith("m") else f"RL: {rl_val}")
                right_labels.append(dir_line_text)
            else:
                right_labels.append(dir_line_text)

            # Vertical labels & stem geometry:
            # Stem points DOWN from p_center towards the track
            # Text flows UPWARDS towards p_center at vert_ang = 90.0 degrees
            vert_ang = 90.0
            text_h = 0.75
            gap_side = 0.18
            gap_top = 0.18

            # Calculate actual roof line height above the text envelope to prevent poking through slanted lines
            def get_roof_y(x: float) -> float:
                if x <= p_center[0]:
                    dx = p_center[0] - p_left[0]
                    t = (x - p_left[0]) / dx if abs(dx) > 1e-4 else 1.0
                    return p_left[1] + t * (p_center[1] - p_left[1])
                else:
                    dx = p_right[0] - p_center[0]
                    t = (x - p_center[0]) / dx if abs(dx) > 1e-4 else 0.0
                    return p_center[1] + t * (p_right[1] - p_center[1])

            roof_y_left = get_roof_y(p_center[0] - gap_side - text_h * 1.2)
            roof_y_right = get_roof_y(p_center[0] + gap_side + len(right_labels) * (text_h + 0.25))
            y_target_top = min(roof_y_left, roof_y_right, p_center[1]) - gap_top

            all_vert_texts = []

            # 1. Left of vertical marker: CH label inside block
            t_ch = block.add_text(
                left_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_h,
                    "rotation": vert_ang,
                    "insert": (0.0, 0.0, 0),
                },
            )
            bb_ch = None
            try:
                bb_ch = bbox.extents([t_ch])
            except Exception:
                pass

            # 2. Right of vertical marker: RL and/or Direction LINE inside block
            right_ents = []
            bb_r_list = []
            for col_idx, r_label in enumerate(right_labels):
                t_r = block.add_text(
                    r_label,
                    dxfattribs={
                        "layer": layer_name,
                        "color": 1,
                        "style": style_name,
                        "height": text_h,
                        "rotation": vert_ang,
                        "insert": (0.0, 0.0, 0),
                    },
                )
                right_ents.append((t_r, col_idx, r_label))
                try:
                    bb_r_list.append(bbox.extents([t_r]))
                except Exception:
                    pass

            # Both CH and RL/Direction labels must start parallel at the exact same baseline point (aligned at the bottom),
            # with the tallest label reaching just under the junction line.
            all_y_lengths = []
            if bb_ch is not None:
                all_y_lengths.append(bb_ch.extmax[1])
            for b in bb_r_list:
                all_y_lengths.append(b.extmax[1])

            char_w = text_h * 0.8
            if all_y_lengths:
                common_ins_y = y_target_top - max(all_y_lengths)
            else:
                max_chars = max([len(left_text)] + [len(r) for r in right_labels], default=5)
                common_ins_y = y_target_top - max_chars * char_w

            ins_y_rel = common_ins_y - p_center[1]

            # Position CH label inside block at relative coordinates
            if bb_ch is not None:
                ins_x_ch_rel = -gap_side - bb_ch.extmax[0]
            else:
                ins_x_ch_rel = -gap_side - text_h * 0.25
            t_ch.dxf.insert = (ins_x_ch_rel, ins_y_rel, 0)
            all_vert_texts.append(t_ch)

            # Position RL / Direction labels inside block at relative coordinates
            for idx, (t_r, col_idx, r_label) in enumerate(right_ents):
                if idx < len(bb_r_list):
                    ins_x_r_rel = gap_side - bb_r_list[idx].extmin[0] + col_idx * (text_h + 0.25)
                else:
                    ins_x_r_rel = gap_side + text_h + col_idx * (text_h + 0.25)
                t_r.dxf.insert = (ins_x_r_rel, ins_y_rel, 0)
                all_vert_texts.append(t_r)

            # Vertical marker line (stem) inside block
            # Extends from (0,0) down past the common start of the labels by 0.25m
            v_end_rel = (0.0, ins_y_rel - 0.25)
            block.add_line(
                p_center_rel,
                v_end_rel,
                dxfattribs={"layer": layer_name, "color": 1},
            )

            # Insert block reference into modelspace at p_center as a single complete component
            doc.modelspace().add_blockref(
                name=block_name,
                insert=p_center,
                dxfattribs={"layer": layer_name, "color": 1},
            )

        doc.saveas(self.config.output_dxf)


class GradientMixin(GradientStep):
    """Mixin adding gradient generation to ESPGenerator."""
    pass
