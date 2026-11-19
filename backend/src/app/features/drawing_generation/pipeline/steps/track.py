"""Track building step (parallel LOOP lines via TrackGenerator)."""

from __future__ import annotations

import logging

from ...domain.constants import MAIN_LINE_SRJ_MARGIN_M
from ...domain.geometry.operations import nearest_point_on_alignment, polyline_length
from ...domain.track.generator import (
    LineSpec,
    LoopSpec,
    TrackGenerationConfig,
    TrackGenerator,
    _is_main_line,
    _offset_alignment,
)
from ...domain.track.overrun import slice_polyline
from ...domain.track.siding import portion_from as _siding_portion
from ...formats.dxf.primitives import add_polyline as _common_polyline
from ...formats.dxf.tracks import _add_all_tc_annotations, _draw_direction_mark
from .base import PipelineStep

logger = logging.getLogger(__name__)

__all__ = ["TrackStep"]


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
        document = self._active_document()
        tracks = TrackGenerator(track_config).run(document=document, save=document is None)
        if document is not None:
            self.context.tracks = tracks
        return tracks

    def _collect_main_line_srj_chainages(self, tracks: dict) -> list[float]:
        """Collect MAIN-datum chainages of every SRJ located on a MAIN LINE track."""
        chainages: list[float] = []
        main_pts = tracks.get("MAIN_LINE")
        if not main_pts or len(main_pts) < 2:
            return []

        cleaned_main = [(float(p[0]), float(p[1])) for p in main_pts]

        main_alignments = [
            [(float(p[0]), float(p[1])) for p in pts]
            for name, pts in tracks.items()
            if _is_main_line(name) and len(pts) >= 2
        ]

        # 1. From crossover results: only include SRJs on tracks that are MAIN lines
        for res in getattr(self, "_crossover_results", None) or []:
            try:
                from_trk = getattr(res, "from_track", "")
                to_trk = getattr(res, "to_track", "")

                # SRJ on from_track
                if _is_main_line(from_trk):
                    ch1 = getattr(res, "chainage", None)
                    if ch1 is not None:
                        chainages.append(float(ch1))

                # SRJ on to_track
                if _is_main_line(to_trk):
                    placement = str(getattr(res, "placement", "AHEAD") or "AHEAD").upper()
                    ch2 = res.end_chainage if placement == "AHEAD" else res.start_chainage
                    if ch2 is not None:
                        chainages.append(float(ch2))
            except (TypeError, ValueError, AttributeError):
                pass

        # 2. From siding results: only include sidings branching from a MAIN line
        for item in getattr(self, "_siding_results", None) or []:
            try:
                spec, result = item
                source_track = getattr(spec, "source_track", "")
                if _is_main_line(source_track):
                    st = getattr(spec, "start_chainage_m", None)
                    if st is not None:
                        chainages.append(float(st))
                    if hasattr(result, "ladder_length_m") and hasattr(result, "points"):
                        heel = _siding_portion(result.points, result.ladder_length_m)[0]
                        proj = nearest_point_on_alignment(cleaned_main, heel)
                        chainages.append(float(proj.chainage))
            except Exception:
                pass

        # 3. From output DXF (layer "SRJ"): fallback if in-memory results are not present
        if not chainages:
            try:
                doc = self._load_document()
                for entity in doc.modelspace():
                    try:
                        if str(getattr(entity.dxf, "layer", "")).upper() == "SRJ":
                            kind = entity.dxftype()
                            pt = None
                            if kind == "LINE":
                                # The SRJ post stem starts at the track centerline (tip)
                                pt_start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
                                pt_end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
                                for candidate in (pt_start, pt_end):
                                    if any(nearest_point_on_alignment(al, candidate).distance <= 0.5 for al in main_alignments):
                                        pt = candidate
                                        break
                            elif kind in ("LWPOLYLINE", "POLYLINE", "CIRCLE"):
                                if kind == "CIRCLE":
                                    c = (float(entity.dxf.center.x), float(entity.dxf.center.y))
                                else:
                                    raw = [(float(p[0]), float(p[1])) for p in entity.get_points()]
                                    c = (sum(p[0] for p in raw) / len(raw), sum(p[1] for p in raw) / len(raw))
                                if any(nearest_point_on_alignment(al, c).distance <= 3.5 for al in main_alignments):
                                    loop_alignments = [
                                        [(float(p[0]), float(p[1])) for p in pts]
                                        for name, pts in tracks.items()
                                        if not _is_main_line(name) and len(pts) >= 2
                                    ]
                                    min_main_d = min(nearest_point_on_alignment(al, c).distance for al in main_alignments)
                                    min_loop_d = min((nearest_point_on_alignment(al, c).distance for al in loop_alignments), default=999.0)
                                    if min_main_d < min_loop_d:
                                        pt = c
                            if pt is not None:
                                proj = nearest_point_on_alignment(cleaned_main, pt)
                                chainages.append(float(proj.chainage))
                    except Exception:
                        continue
            except Exception:
                pass

        if not chainages:
            return []
        sorted_ch = sorted(chainages)
        deduped = [sorted_ch[0]]
        for ch in sorted_ch[1:]:
            if ch - deduped[-1] > 0.1:
                deduped.append(ch)
        return deduped

    def _trim_main_lines_to_srj(self, tracks: dict) -> tuple[float, float] | None:
        """Trim main lines past outermost SRJs at both ends (Greenfield only by default, disabled by default)."""
        cfg = getattr(self, "config", None)
        if not getattr(cfg, "enable_main_line_trim", False):
            logger.info("   ℹ️ Main line 50m SRJ trim disabled: main lines remain full surveyed length.")
            return None

        if cfg is not None and (getattr(cfg, "workflow", "greenfield") == "brownfield" or getattr(cfg, "is_brownfield", False)):
            target_track = getattr(cfg, "trim_target_track", None)
            if not target_track:
                logger.info("   ℹ️ Brownfield mode: skipping 50m SRJ end-truncation for main lines.")
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

        srj_chainages = self._collect_main_line_srj_chainages(tracks)
        if not srj_chainages:
            logger.info("   ! No main line SRJs found on layout; main lines kept full length.")
            return None

        min_srj = min(srj_chainages)
        max_srj = max(srj_chainages)

        margin = float(getattr(self.config, "main_line_srj_margin_m", None) or MAIN_LINE_SRJ_MARGIN_M)
        main_length = polyline_length(cleaned_main)

        # Both sides trimmed 50m from outermost main line SRJs
        start_dist = max(0.0, min_srj - margin)
        end_dist = min(main_length, max_srj + margin)

        if end_dist <= start_dist:
            logger.info(f"   ! Main line trim skipped: degenerate range [{start_dist:.2f}, {end_dist:.2f}].")
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
            doc = self._load_document()
        except Exception as exc:
            logger.info(f"   ! Main line trim DXF read skipped ({exc})")
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
                logger.info(f"   ! Main line {name} redraw failed ({exc})")

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
            self._save_document(doc)
        except Exception as exc:
            logger.info(f"   ! Main line trim DXF save skipped ({exc})")

        self._main_line_trim_range = (start_dist, end_dist)
        logger.info(
            f"   OK Main lines trimmed to 50m past outermost SRJs: "
            f"SRJ [{min_srj:.2f}, {max_srj:.2f}]m -> visible [{start_dist:.2f}, {end_dist:.2f}]m "
            f"(length {end_dist - start_dist:.2f}m, was {main_length:.2f}m)"
        )

        try:
            if hasattr(self, "_generate_land_boundary"):
                self._generate_land_boundary(tracks)
        except Exception:
            pass

        return (start_dist, end_dist)
