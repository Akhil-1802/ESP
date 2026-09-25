"""Automatic fouling-mark detection + drawing."""

from __future__ import annotations

import ezdxf

from track.fouling import collect_fouling_marks as _collect_fouling_marks, draw_fouling_marks as _draw_fouling_marks
from track.generator import _generate_bounded_loop as _gen_loop

from .base import PipelineStep

__all__ = ["FoulingStep", "FoulingMixin"]


class FoulingStep(PipelineStep):
    """Pipeline step: Automatic fouling-mark detection and drawing."""

    def _generate_fouling_marks(self, tracks: dict) -> None:
        """Automatic Fouling Marks: no user input, purely from geometry."""
        try:
            doc = ezdxf.readfile(self.config.output_dxf)
        except Exception:
            return
        self._wipe_layers(doc, {"FM", "FOULING_MARK", "FOULING"})
        doc.saveas(self.config.output_dxf)
        doc = ezdxf.readfile(self.config.output_dxf)
        try:
            extents = self._loop_main_extents()
            fm_tracks = dict(tracks)
            fm_extents = dict(extents)
            try:
                ranges = (getattr(self, "_bounded_loop_defined_ranges", None) or (lambda: {}))()
                main_points = tracks.get("MAIN_LINE")
                specs_by_name = {
                    getattr(loop, "name", None): loop
                    for loop in list(self.config.loops) + list(self.config.additional_lines)
                }
                for _name, (_c1, _c2, _eff_s, _eff_e) in (ranges or {}).items():
                    if _name not in tracks or main_points is None:
                        continue
                    _spec = specs_by_name.get(_name)
                    if _spec is None:
                        continue
                    try:
                        fm_tracks[_name] = _gen_loop(
                            main_points,
                            float(_eff_s),
                            float(_eff_e),
                            float(getattr(_spec, "spacing", 0.0) or 0.0),
                            str(getattr(_spec, "side", "LEFT")),
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
            print(f"   ! Fouling-mark detection skipped ({exc})")
            self._fouling_marks = []
            return
        self._fouling_marks = list(marks)
        if not marks:
            doc.saveas(self.config.output_dxf)
            return
        try:
            count = _draw_fouling_marks(doc, marks)
        except Exception as exc:
            print(f"   ! Fouling-mark drawing skipped ({exc})")
            return
        doc.saveas(self.config.output_dxf)
        for mark in marks:
            print(
                f"   OK FM ({mark.track}@"
                f"{float(mark.chainage_main):.3f}m <-> "
                f"{mark.other_track}) spacing={float(mark.spacing_m):.3f}m"
            )
        print(f"   ✓ Fouling marks: {count}")


class FoulingMixin(FoulingStep):
    """Mixin for backward compatibility."""
    pass
