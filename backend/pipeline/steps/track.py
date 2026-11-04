"""Track building step (parallel LOOP lines via TrackGenerator)."""

from __future__ import annotations

import ezdxf

from common.constants import MAIN_LINE_SRJ_MARGIN_M
from common.dxf import add_polyline as _common_polyline
from common.geometry import nearest_point_on_alignment, polyline_length
from track.drawing import _add_all_tc_annotations, _draw_direction_mark
from track.generator import (
    LineSpec,
    LoopSpec,
    TrackGenerationConfig,
    TrackGenerator,
    _is_main_line,
    _offset_alignment,
)
from track.overrun import slice_polyline
from track.siding import portion_from as _siding_portion

from .base import PipelineStep

__all__ = ["TrackStep", "TrackMixin"]


class TrackStep(PipelineStep):
    """Pipeline step: build full-length tracks and trim main lines to SRJ bounds."""

    def build_tracks(self) -> dict:
        """Build all tracks; return name -> points."""
        track_config = TrackGenerationConfig(
            self.source_dxf,
            self.config.output_dxf,
            self.config.track_source_layer,
            self.config.loops,
            self.config.additional_lines,
            main_directions=getattr(self.config, "main_directions", None) or {},
            station_markers=getattr(self.config, "station_markers", None) or [],
            start_km=getattr(self.config, "start_km", None),
            start_m=getattr(self.config, "start_m", None),
        )
        return TrackGenerator(track_config).run()

    def _collect_all_srj_chainages(self, tracks: dict) -> list[float]:
        """Collect MAIN-datum chainages of every SRJ on the layout."""
        chainages: list[float] = []
        main_pts = tracks.get("MAIN_LINE")
        if not main_pts or len(main_pts) < 2:
            return []

        cleaned_main = [(float(p[0]), float(p[1])) for p in main_pts]

        for res in getattr(self, "_crossover_results", None) or []:
            try:
                ch1 = getattr(res, "chainage", None)
                if ch1 is not None:
                    chainages.append(float(ch1))
                placement = str(getattr(res, "placement", "AHEAD") or "AHEAD").upper()
                ch2 = res.end_chainage if placement == "AHEAD" else res.start_chainage
                if ch2 is not None:
                    chainages.append(float(ch2))
            except (TypeError, ValueError, AttributeError):
                pass

        for item in getattr(self, "_siding_results", None) or []:
            try:
                spec, result = item
                st = getattr(spec, "start_chainage_m", None)
                if st is not None:
                    chainages.append(float(st))
                if hasattr(result, "ladder_length_m") and hasattr(result, "points"):
                    heel = _siding_portion(result.points, result.ladder_length_m)[0]
                    proj = nearest_point_on_alignment(cleaned_main, heel)
                    chainages.append(float(proj.chainage))
            except Exception:
                pass

        try:
            doc = ezdxf.readfile(self.config.output_dxf)
            for entity in doc.modelspace():
                try:
                    if str(getattr(entity.dxf, "layer", "")).upper() == "SRJ":
                        kind = entity.dxftype()
                        if kind == "LINE":
                            pt = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                            proj = nearest_point_on_alignment(cleaned_main, pt)
                            chainages.append(float(proj.chainage))
                        elif kind in ("LWPOLYLINE", "POLYLINE", "CIRCLE"):
                            if kind == "CIRCLE":
                                pt = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                            else:
                                raw = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                                pt = (sum(p[0] for p in raw) / len(raw), sum(p[1] for p in raw) / len(raw))
                            proj = nearest_point_on_alignment(cleaned_main, pt)
                            chainages.append(float(proj.chainage))
                except Exception:
                    continue
        except Exception:
            pass

        return sorted(chainages)

    def _trim_main_lines_to_srj(self, tracks: dict) -> tuple[float, float] | None:
        """Trim main lines past outermost SRJs at both ends (Greenfield only by default)."""
        cfg = getattr(self, "config", None)
        if cfg is not None and (getattr(cfg, "workflow", "greenfield") == "brownfield" or getattr(cfg, "is_brownfield", False)):
            target_track = getattr(cfg, "trim_target_track", None)
            if not target_track:
                print("   ℹ️ Brownfield mode: skipping 50m SRJ end-truncation for main lines.")
                return None
            # If implemented for a single main line, only that line is targeted
            target_names = [target_track] if target_track in tracks else []
            if not target_names:
                return None
        else:
            target_names = None

        if "MAIN_LINE" not in tracks:
            return None

        main_pts = tracks["MAIN_LINE"]
        cleaned_main = [(float(p[0]), float(p[1])) for p in main_pts]
        if len(cleaned_main) < 2:
            return None

        srj_chainages = self._collect_all_srj_chainages(tracks)
        if not srj_chainages:
            print("   ! No SRJs found on layout; main lines kept full length.")
            return None

        min_srj = min(srj_chainages)
        max_srj = max(srj_chainages)

        margin = float(getattr(self.config, "main_line_srj_margin_m", None) or MAIN_LINE_SRJ_MARGIN_M)
        main_length = polyline_length(cleaned_main)

        # Determine reference station center if available
        station_ch = None
        for sm in getattr(self.config, "station_markers", []) or []:
            d = getattr(sm, "distance_along_m", None)
            if d is not None and 0 < float(d) < main_length:
                station_ch = float(d)
                break

        if station_ch is None:
            for st_req in getattr(self.config, "stations", []) or []:
                pl_name = getattr(st_req, "platform_layer", "")
                for p_req in getattr(self.config, "platforms", []) or []:
                    p_cfg = getattr(p_req, "config", None)
                    if p_cfg and getattr(p_req, "track_layer", "") == pl_name:
                        st_p = getattr(p_cfg, "start_chainage", None)
                        lg_p = getattr(p_cfg, "length", 0.0) or 0.0
                        if st_p is not None:
                            station_ch = float(st_p) + float(lg_p) / 2.0
                            break
                if station_ch is not None:
                    break

        # Guard Rule: Require Turnouts on Both Sides
        # If turnouts/crossovers only exist on one side of the layout (e.g. there is no turnout
        # on the other half of the track), do not truncate the far end; keep track extending
        # all the way to its original KML endpoint.
        num_crossovers = len(getattr(self.config, "crossovers", []) or [])
        mid_track = station_ch if station_ch is not None else (main_length / 2.0)

        has_start_turnouts = any(ch < (mid_track - 25.0) for ch in srj_chainages)
        has_end_turnouts = any(ch > (mid_track + 25.0) for ch in srj_chainages)

        if num_crossovers <= 1 or (station_ch is not None and not (has_start_turnouts and has_end_turnouts)):
            if has_start_turnouts and not has_end_turnouts:
                # Turnouts exist only on the start side; do not truncate the far end!
                start_dist = max(0.0, min_srj - margin)
                end_dist = main_length
                print(
                    f"   ℹ️ Guard rule: Turnouts only exist on start side (<= {mid_track:.1f} m); "
                    f"far end kept full length to KML endpoint ({main_length:.1f} m)."
                )
            elif has_end_turnouts and not has_start_turnouts:
                # Turnouts exist only on the end side; do not truncate the near end!
                start_dist = 0.0
                end_dist = min(main_length, max_srj + margin)
                print(
                    f"   ℹ️ Guard rule: Turnouts only exist on end side (>= {mid_track:.1f} m); "
                    f"near end kept full length to KML startpoint (0.0 m)."
                )
            elif num_crossovers <= 1:
                # Single crossover: check which half of the track it is on
                if max_srj <= mid_track:
                    start_dist = max(0.0, min_srj - margin)
                    end_dist = main_length
                    print(
                        f"   ℹ️ Guard rule: Single crossover on start side; "
                        f"far end kept full length to KML endpoint ({main_length:.1f} m)."
                    )
                elif min_srj >= mid_track:
                    start_dist = 0.0
                    end_dist = min(main_length, max_srj + margin)
                    print(
                        f"   ℹ️ Guard rule: Single crossover on end side; "
                        f"near end kept full length to KML startpoint (0.0 m)."
                    )
                else:
                    start_dist = 0.0
                    end_dist = main_length
                    print(
                        f"   ℹ️ Guard rule: Single crossover near center; "
                        f"main lines kept full length ({main_length:.1f} m)."
                    )
            else:
                start_dist = max(0.0, min_srj - margin)
                end_dist = min(main_length, max_srj + margin)
        else:
            # Turnouts exist on both sides of the layout
            start_dist = max(0.0, min_srj - margin)
            end_dist = min(main_length, max_srj + margin)

        if end_dist <= start_dist:
            print(f"   ! Main line trim skipped: degenerate range [{start_dist:.2f}, {end_dist:.2f}].")
            return None

        specs_by_name = {
            getattr(line, "name", ""): line
            for line in getattr(self.config, "additional_lines", []) or []
        }

        if target_names is None:
            def _is_target(name: str) -> bool:
                if _is_main_line(name):
                    return True
                sp = specs_by_name.get(name)
                if sp is not None and isinstance(sp, LineSpec) and not isinstance(sp, LoopSpec):
                    return True
                return False

            target_names = [n for n in tracks if _is_target(n)]
            if "MAIN_LINE" not in target_names:
                target_names.insert(0, "MAIN_LINE")

        sliced_main = slice_polyline(cleaned_main, start_dist, end_dist)
        tracks["MAIN_LINE"] = sliced_main

        processed = {"MAIN_LINE"}
        remaining = [n for n in target_names if n != "MAIN_LINE"]
        while remaining:
            advanced = False
            for name in list(remaining):
                spec = specs_by_name.get(name)
                ref = getattr(spec, "reference_track", "MAIN_LINE") or "MAIN_LINE"
                if ref in processed:
                    base = tracks.get(ref, sliced_main)
                    if spec is not None and hasattr(spec, "spacing") and hasattr(spec, "side"):
                        tracks[name] = _offset_alignment(base, spec.spacing, spec.side)
                    else:
                        tracks[name] = slice_polyline(tracks[name], start_dist, end_dist)
                    processed.add(name)
                    remaining.remove(name)
                    advanced = True
            if not advanced:
                for name in remaining:
                    tracks[name] = slice_polyline(tracks[name], start_dist, end_dist)
                    processed.add(name)
                break

        try:
            doc = ezdxf.readfile(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Main line trim DXF read skipped ({exc})")
            return None

        target_layers = {n.upper().replace(" ", "_") for n in target_names}

        for entity in list(doc.modelspace()):
            try:
                if entity.dxf.layer in target_layers:
                    doc.modelspace().delete_entity(entity)
            except Exception:
                continue

        for name in target_names:
            layer_name = name.upper().replace(" ", "_")
            if layer_name not in doc.layers:
                try:
                    doc.layers.add(layer_name, color=1)
                except Exception:
                    pass
            try:
                _common_polyline(doc, tracks[name], layer_name, 1)
            except Exception as exc:
                print(f"   ! Main line {name} redraw failed ({exc})")

        has_station = bool(getattr(self.config, "stations", None))
        if not has_station:
            for entity in list(doc.modelspace()):
                try:
                    if entity.dxf.layer == "DIRECTION":
                        doc.modelspace().delete_entity(entity)
                except Exception:
                    continue

            _mains = [n for n in target_names if _is_main_line(n)]
            _dirs = {}
            for _ln in getattr(self.config, "additional_lines", []) or []:
                if isinstance(_ln, LineSpec) and (_ln.direction or "").upper() in ("UP", "DN"):
                    _dirs[_ln.name] = _ln.direction.upper()
            _dirs.update(getattr(self.config, "main_directions", None) or {})
            try:
                if len(_mains) == 1 and not _dirs.get(_mains[0]):
                    pass
                else:
                    for _i, _nm in enumerate(_mains):
                        _d = (_dirs.get(_nm) or ("UP" if _i == 0 else "DN")).upper()
                        if _d in ("UP/DN", "BOTH"):
                            continue
                        if _d not in ("UP", "DN"):
                            _d = "UP" if _i == 0 else "DN"
                        _draw_direction_mark(doc, tracks[_nm], _d, False, 1 if _d == "UP" else -1)
            except Exception:
                pass

        for entity in list(doc.modelspace()):
            try:
                if entity.dxf.layer == "TRACK_CENTERS":
                    doc.modelspace().delete_entity(entity)
            except Exception:
                continue

        try:
            _add_all_tc_annotations(doc, tracks, layer="TRACK_CENTERS", color=1, height=0.8)
        except Exception:
            pass

        try:
            doc.saveas(self.config.output_dxf)
        except Exception as exc:
            print(f"   ! Main line trim DXF save skipped ({exc})")

        self._main_line_trim_range = (start_dist, end_dist)
        print(
            f"   OK Main lines trimmed to 50m past outermost SRJs: "
            f"SRJ [{min_srj:.2f}, {max_srj:.2f}]m -> visible [{start_dist:.2f}, {end_dist:.2f}]m "
            f"(length {end_dist - start_dist:.2f}m, was {main_length:.2f}m)"
        )
        return (start_dist, end_dist)


class TrackMixin(TrackStep):
    """Mixin for backward compatibility."""
    pass
