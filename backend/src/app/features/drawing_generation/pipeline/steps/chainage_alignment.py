"""Station-relative chainage labels (final annotation pass)."""

from __future__ import annotations

import logging
import math

from ...domain.geometry.operations import point_at_chainage, polyline_length
from ...domain.station.station_flag import draw_station_flag
from .chainage_text import _calc_text_insert

logger = logging.getLogger(__name__)


class AlignmentChainageLabels:
    def _generate_alignment_interval_chainages(self, tracks: dict) -> None:
        """Draw regular alignment interval chainage tick marks along MAIN track.

        Places ticks every 100m (plus start and end points) with:
          - Top text: CH-1+900 (or CH-4 if only KM was specified and m is 0)
          - Bottom text: Ch. 1900 M
        """
        if not tracks:
            return

        # Hide interval chainages over KML file when loop lines, additional tracks, or other features are configured
        explicit_show = getattr(self.config, "show_alignment_chainages", None)
        if explicit_show is False:
            return
        if explicit_show is None:
            loops = getattr(self.config, "loops", None) or []
            additional_lines = getattr(self.config, "additional_lines", None) or []
            platforms = getattr(self.config, "platforms", None) or []
            if len(loops) > 0 or len(additional_lines) > 0 or len(platforms) > 0:
                return

        try:
            doc = self._load_document()
        except Exception:
            return

        from ...formats.dxf.styles import ensure_layer, ensure_text_style
        layer_name = "CHAINAGE"
        ensure_layer(doc, layer_name, color=1)
        style_name = ensure_text_style(doc)

        main_pts = tracks.get("MAIN_LINE") or next(iter(tracks.values()), None)
        if not main_pts or len(main_pts) < 2:
            return
        cleaned = [(float(p[0]), float(p[1])) for p in main_pts]
        total_len = polyline_length(cleaned)
        if total_len <= 0:
            return

        start_km_raw = getattr(self.config, "start_km", None)
        start_m_raw = getattr(self.config, "start_m", None)

        has_explicit_m = False
        start_ch_m = 0.0

        if start_km_raw is not None and str(start_km_raw).strip() != "":
            try:
                start_km = float(start_km_raw)
            except ValueError:
                start_km = 0.0
            if start_m_raw is not None and str(start_m_raw).strip() != "":
                try:
                    start_m = float(start_m_raw)
                    has_explicit_m = True
                except ValueError:
                    start_m = 0.0
            else:
                has_explicit_m = False
                start_m = 0.0
            sign = -1.0 if (start_km < 0 or str(start_km_raw).strip().startswith("-")) else 1.0
            start_ch_m = sign * (abs(start_km) * 1000.0 + abs(start_m))
        elif getattr(self.config, "start_chainage", None) is not None:
            s = str(self.config.start_chainage).strip()
            if "+" in s:
                parts = s.split("+")
                try:
                    sk = float(parts[0].strip() or 0)
                    sm = float(parts[1].strip() or 0)
                    has_explicit_m = True
                    sign = -1.0 if (sk < 0 or parts[0].strip().startswith("-")) else 1.0
                    start_ch_m = sign * (abs(sk) * 1000.0 + abs(sm))
                except ValueError:
                    start_ch_m = 0.0
            else:
                try:
                    num = float(s)
                    if abs(num) <= 50.0 and "." not in s:
                        start_ch_m = num * 1000.0
                        has_explicit_m = False
                    else:
                        start_ch_m = num
                        has_explicit_m = (abs(num) % 1000 > 0)
                except ValueError:
                    start_ch_m = 0.0

        # Parse station markers in advance to coordinate placement and avoid duplicate interval ticks
        parsed_stations = self._parse_alignment_station_markers(cleaned, start_ch_m, total_len)
        station_dists = [s["d"] for s in parsed_stations]

        step = 100.0
        distances_to_mark = []

        # Only add start chainage (0.0) if not directly on top of a station marker
        if not any(abs(0.0 - sd) < 25.0 for sd in station_dists):
            distances_to_mark.append(0.0)

        first_100 = math.ceil(start_ch_m / step) * step
        curr = first_100
        while (curr - start_ch_m) < total_len - 1e-4:
            d = curr - start_ch_m
            if d > 1.0:
                # Omit interval tick if it falls within 25m of any station marker to prevent collision
                if not any(abs(d - sd) < 25.0 for sd in station_dists):
                    distances_to_mark.append(d)
            curr += step

        # Append end chainage only if separated by at least 25m from previous tick and station markers
        last_d = distances_to_mark[-1] if distances_to_mark else -999.0
        if (total_len - last_d) >= 25.0:
            if not any(abs(total_len - sd) < 25.0 for sd in station_dists):
                distances_to_mark.append(total_len)

        text_h = 1.0
        tick_top_len = 6.0
        tick_bot_len = 14.0

        for d in distances_to_mark:
            ch_m = start_ch_m + d
            if ch_m < -0.005:
                abs_ch = abs(ch_m)
                km_mag = int(abs_ch // 1000)
                m_rem = abs_ch - (km_mag * 1000.0)
                if abs(m_rem) < 0.01:
                    if not has_explicit_m:
                        top_text = f"CH--{km_mag}"
                    else:
                        top_text = f"CH--{km_mag}+000"
                else:
                    top_text = f"CH--{km_mag}+{int(round(m_rem))}"
            else:
                km_val = int(ch_m // 1000)
                m_val = ch_m - (km_val * 1000.0)

                # Top label text:
                # If user filled 4 for KM, and nothing in M, use only 4 when m_val is 0
                if abs(m_val) < 0.01:
                    if not has_explicit_m:
                        top_text = f"CH-{km_val}"
                    else:
                        top_text = f"CH-{km_val}+000"
                else:
                    top_text = f"CH-{km_val}+{int(round(m_val))}"

            # Bottom label text:
            bot_text = f"Ch. {int(round(ch_m))} M"

            st = point_at_chainage(cleaned, d)
            px, py = st.point
            tx, ty = st.tangent
            t_len = math.hypot(tx, ty) or 1.0
            tx, ty = tx / t_len, ty / t_len

            # Normal vector (perpendicular to track)
            nx, ny = -ty, tx

            # Tick line
            p_top = (px + nx * tick_top_len, py + ny * tick_top_len)
            p_bot = (px - nx * tick_bot_len, py - ny * tick_bot_len)
            doc.modelspace().add_line(p_bot, p_top, dxfattribs={"layer": layer_name, "color": 1})

            # Normal angle in degrees: keep in [0, 180) so text always points upwards (along +n)
            norm_deg = math.degrees(math.atan2(ny, nx))
            rot_deg = norm_deg
            while rot_deg >= 180.0:
                rot_deg -= 180.0
            while rot_deg < 0.0:
                rot_deg += 180.0

            # Insert top text (CH-...) along normal at tick_top, offset to left of tick line
            top_len = len(top_text) * (text_h * 0.75)
            ins_top = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                tick_top_len + 1.5,
                top_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                top_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_h,
                    "rotation": rot_deg,
                    "insert": ins_top,
                },
            )

            # Insert bottom text (Ch. 1900 M) along normal below track, offset to left of tick line
            bot_text_len = len(bot_text) * (text_h * 0.75)
            ins_bot = _calc_text_insert(
                (px, py),
                (-nx, -ny),
                (tx, ty),
                tick_bot_len + 1.5,
                bot_text_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                bot_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": text_h,
                    "rotation": rot_deg,
                    "insert": ins_bot,
                },
            )

        # Draw station marker lines at specified station chainages
        try:
            self._generate_alignment_station_markers(tracks, doc, cleaned, start_ch_m, total_len, parsed_stations)
        except Exception as exc:
            logger.info(f"   ! Station marker lines skipped ({exc})")

        self._save_document(doc)
        logger.info(f"   ✓ Alignment interval chainages: {len(distances_to_mark)} markers (start {start_ch_m:.1f} m to {start_ch_m + total_len:.1f} m)")

    def _parse_alignment_station_markers(
        self,
        cleaned_main_pts: list,
        start_ch_m: float,
        total_len: float,
    ) -> list[dict]:
        """Parse station marker configurations into normalized distance and display structures."""
        station_markers = getattr(self.config, "station_markers", None) or []
        if not station_markers:
            return []

        parsed = []
        for idx, stn in enumerate(station_markers, 1):
            if isinstance(stn, dict):
                stn_name = str(stn.get("name") or f"STATION {idx}").strip()
                km_val = stn.get("km")
                m_val = stn.get("m")
                raw_ch = stn.get("chainage")
                show_flag = stn.get("show_flag", True)
            else:
                stn_name = str(getattr(stn, "name", f"STATION {idx}")).strip()
                km_val = getattr(stn, "km", None)
                m_val = getattr(stn, "m", None)
                raw_ch = getattr(stn, "chainage", None)
                show_flag = getattr(stn, "show_flag", True)

            # Determine absolute chainage in meters
            stn_ch_m = None
            km_has = km_val is not None and str(km_val).strip() != ""
            m_has = m_val is not None and str(m_val).strip() != ""
            if km_has or m_has:
                try:
                    km_f = float(km_val) if km_has else 0.0
                    m_f = float(m_val) if m_has else 0.0
                    sign = -1.0 if (km_f < 0 or (km_has and str(km_val).strip().startswith("-"))) else 1.0
                    stn_ch_m = sign * (abs(km_f) * 1000.0 + abs(m_f))
                except ValueError:
                    stn_ch_m = None

            if stn_ch_m is None and raw_ch is not None and str(raw_ch).strip() != "":
                s_ch = str(raw_ch).strip()
                if "+" in s_ch:
                    parts = s_ch.split("+")
                    try:
                        sk = float(parts[0].strip() or 0)
                        sm = float(parts[1].strip() or 0)
                        sign = -1.0 if (sk < 0 or parts[0].strip().startswith("-")) else 1.0
                        stn_ch_m = sign * (abs(sk) * 1000.0 + abs(sm))
                    except ValueError:
                        stn_ch_m = None
                else:
                    try:
                        num = float(s_ch)
                        stn_ch_m = num * 1000.0 if abs(num) <= 50.0 and "." not in s_ch else num
                    except ValueError:
                        stn_ch_m = None

            if stn_ch_m is None:
                continue

            # Calculate distance d along track alignment and display chainage
            if stn_ch_m >= start_ch_m:
                d = stn_ch_m - start_ch_m
                display_ch_m = stn_ch_m
            elif 0.0 <= stn_ch_m <= total_len:
                d = stn_ch_m
                display_ch_m = start_ch_m + d
            else:
                d = stn_ch_m
                display_ch_m = stn_ch_m

            d = max(0.0, min(d, total_len))

            if display_ch_m < -0.005:
                abs_ch = abs(display_ch_m)
                ch_km_mag = int(abs_ch // 1000)
                ch_rem_m = abs_ch - (ch_km_mag * 1000.0)
                if abs(ch_rem_m) < 0.01:
                    ch_disp = f"-{ch_km_mag}+000" if (m_val is not None and str(m_val).strip() != "") else f"-{ch_km_mag}"
                else:
                    ch_disp = f"-{ch_km_mag}+{int(round(ch_rem_m))}"
            else:
                ch_km = int(display_ch_m // 1000)
                ch_rem_m = display_ch_m - (ch_km * 1000.0)
                if abs(ch_rem_m) < 0.01:
                    ch_disp = f"{ch_km}+000" if (m_val is not None and str(m_val).strip() != "") else f"{ch_km}"
                else:
                    ch_disp = f"{ch_km}+{int(round(ch_rem_m))}"

            parsed.append({
                "idx": idx,
                "name": stn_name,
                "d": d,
                "ch_m": display_ch_m,
                "ch_disp": ch_disp,
                "show_flag": show_flag,
            })

        return parsed

    def _generate_alignment_station_markers(
        self,
        tracks: dict,
        doc,
        cleaned_main_pts: list,
        start_ch_m: float,
        total_len: float,
        parsed_stations: list[dict] | None = None,
    ) -> None:
        """Draw station marker lines and labels at specified chainages along MAIN track."""
        if parsed_stations is None:
            parsed_stations = self._parse_alignment_station_markers(cleaned_main_pts, start_ch_m, total_len)

        if not parsed_stations:
            return

        from ...formats.dxf.styles import ensure_layer, ensure_text_style
        layer_name = "STATION"
        ensure_layer(doc, layer_name, color=1)
        style_name = ensure_text_style(doc)

        drawn_count = 0
        for stn in parsed_stations:
            d = stn["d"]
            stn_name = stn["name"]
            ch_disp = stn["ch_disp"]
            ch_m = stn["ch_m"]
            show_flag = stn["show_flag"]

            st = point_at_chainage(cleaned_main_pts, d)
            px, py = st.point
            tx, ty = st.tangent
            t_len = math.hypot(tx, ty) or 1.0
            tx, ty = tx / t_len, ty / t_len

            # Normal vector
            nx, ny = -ty, tx

            # Stagger height if neighbor station is close (< 35m) to avoid any collision
            is_close_neighbor = any(
                other != stn and abs(other["d"] - d) < 35.0
                for other in parsed_stations
            )
            line_top_len = 28.0 if (is_close_neighbor and (stn["idx"] % 2 == 0)) else 22.0
            line_bot_len = 16.0
            p_top = (px + nx * line_top_len, py + ny * line_top_len)
            p_bot = (px - nx * line_bot_len, py - ny * line_bot_len)

            doc.modelspace().add_line(p_bot, p_top, dxfattribs={"layer": layer_name, "color": 1})

            # Check if station flag is requested (defaults to True)
            if show_flag:
                flag_up = (nx, ny)
                flag_right = (tx, ty)
                pole_base = (p_top[0], p_top[1])
                try:
                    draw_station_flag(doc, pole_base, flag_up, flag_right, color=1)
                except Exception as exc:
                    logger.info(f"   ! Station flag skipped for {stn_name} ({exc})")
            else:
                # Terminal crossbar at top of station line when flag is disabled
                bar_w = 3.5
                doc.modelspace().add_line(
                    (p_top[0] - tx * bar_w, p_top[1] - ty * bar_w),
                    (p_top[0] + tx * bar_w, p_top[1] + ty * bar_w),
                    dxfattribs={"layer": layer_name, "color": 1},
                )

            # Normal angle in degrees for readable text rotation: keep in [0, 180) so text always points upwards (along +n)
            norm_deg = math.degrees(math.atan2(ny, nx))
            rot_deg = norm_deg
            while rot_deg >= 180.0:
                rot_deg -= 180.0
            while rot_deg < 0.0:
                rot_deg += 180.0

            # Separation of text: LEFT and RIGHT of the station line to guarantee zero overlap.
            # - Left of line: STATION: <NAME> sits at side_offset -2.5
            # - Right of line: CH: <KM+M> sits at side_offset +2.5
            # - Bottom of line (below track): Ch. <ch_m> M sits below p_bot
            y_start = line_top_len + 3.5 if show_flag else line_top_len + 1.5
            stn_text = f"STATION: {stn_name.upper()}"
            stn_len = len(stn_text) * (1.4 * 0.75)
            ins_left = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                y_start,
                stn_len,
                rot_deg,
                side_offset=-2.5,
            )
            doc.modelspace().add_text(
                stn_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.4,
                    "rotation": rot_deg,
                    "insert": ins_left,
                },
            )

            # CH: <KM+M>
            ch_text = f"CH: {ch_disp}"
            ch_len = len(ch_text) * (1.2 * 0.75)
            ins_right = _calc_text_insert(
                (px, py),
                (nx, ny),
                (tx, ty),
                y_start,
                ch_len,
                rot_deg,
                side_offset=+2.5,
            )
            doc.modelspace().add_text(
                ch_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.2,
                    "rotation": rot_deg,
                    "insert": ins_right,
                },
            )

            # Bottom of line (below track): Ch. <ch_m> M on the left of the line
            stn_bot_text = f"Ch. {int(round(ch_m))} M"
            stn_bot_len = len(stn_bot_text) * (1.0 * 0.75)
            ins_bot = _calc_text_insert(
                (px, py),
                (-nx, -ny),
                (tx, ty),
                line_bot_len + 1.5,
                stn_bot_len,
                rot_deg,
                side_offset=-0.8,
            )
            doc.modelspace().add_text(
                stn_bot_text,
                dxfattribs={
                    "layer": layer_name,
                    "color": 1,
                    "style": style_name,
                    "height": 1.0,
                    "rotation": rot_deg,
                    "insert": ins_bot,
                },
            )
            drawn_count += 1

        if drawn_count > 0:
            logger.info(f"   ✓ Alignment station markers: {drawn_count} station(s) drawn")
