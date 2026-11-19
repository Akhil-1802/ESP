"""Automatic fouling-mark detection + drawing."""

from __future__ import annotations

import logging

from ...domain.track.fouling import collect_fouling_marks as _collect_fouling_marks
from ...domain.track.fouling import draw_fouling_marks as _draw_fouling_marks
from ...domain.track.generator import _generate_bounded_loop as _gen_loop
from .base import PipelineStep

logger = logging.getLogger(__name__)

__all__ = ["FoulingStep"]


class FoulingStep(PipelineStep):
    """Pipeline step: Automatic fouling-mark detection and drawing."""

    def _generate_fouling_marks(self, tracks: dict) -> None:
        """Automatic Fouling Marks: no user input, purely from geometry."""
        try:
            doc = self._load_document()
        except Exception:
            return
        self._wipe_layers(doc, {"FM", "FOULING_MARK", "FOULING"})
        self._save_document(doc)
        doc = self._load_document()
        try:
            extents = self._loop_main_extents()
            fm_tracks = dict(tracks)
            fm_extents = dict(extents)
            try:
                from .crossover_cuts import resolve_net_offset_and_side

                ranges = (getattr(self, "_bounded_loop_defined_ranges", None) or (lambda: {}))()
                main_points = tracks.get("MAIN_LINE")
                specs_by_name = {
                    getattr(loop, "name", None): loop
                    for loop in list(self.config.loops) + list(self.config.additional_lines)
                    if getattr(loop, "name", None)
                }
                for _name, (_c1, _c2, _eff_s, _eff_e) in (ranges or {}).items():
                    if _name not in tracks or main_points is None:
                        continue
                    _spec = specs_by_name.get(_name)
                    if _spec is None:
                        continue
                    try:
                        net_spacing, net_side = resolve_net_offset_and_side(_name, specs_by_name)
                        fm_tracks[_name] = _gen_loop(
                            main_points,
                            float(_eff_s),
                            float(_eff_e),
                            net_spacing,
                            net_side,
                        )
                        fm_extents[_name] = (float(_eff_s), float(_eff_e))
                    except Exception:
                        continue
            except Exception:
                pass
            marks = _collect_fouling_marks(
                fm_tracks,
                fm_extents,
                getattr(self, "_crossover_results", None) or [],
                getattr(self, "_siding_results", None) or [],
                include_siding_marks=True,
            )
        except Exception as exc:
            logger.info(f"   ! Fouling-mark detection skipped ({exc})")
            self._fouling_marks = []
            return
        self._fouling_marks = list(marks)
        if not marks:
            self._save_document(doc)
            return
        try:
            count = _draw_fouling_marks(doc, marks)
        except Exception as exc:
            logger.info(f"   ! Fouling-mark drawing skipped ({exc})")
            return
        self._save_document(doc)
        for mark in marks:
            logger.info(
                f"   OK FM ({mark.track}@"
                f"{float(mark.chainage_main):.3f}m <-> "
                f"{mark.other_track}) spacing={float(mark.spacing_m):.3f}m"
            )
        logger.info(f"   ✓ Fouling marks: {count}")
