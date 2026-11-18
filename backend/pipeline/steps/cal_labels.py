"""LOOP / MAIN CAL callout labels (final annotation pass)."""

from __future__ import annotations

import ezdxf

from track.cal_labels import draw_cal_labels as _draw_cal_labels

from .base import PipelineStep

__all__ = ["CalLabelStep", "CalLabelMixin"]


class CalLabelStep(PipelineStep):
    """Pipeline step: LOOP end-to-end + MAIN FM-to-FM CAL callouts."""

    def _generate_cal_labels(self, tracks: dict) -> None:
        """Draw per-line CAL labels just above each LOOP/MAIN line."""
        try:
            doc = self._load_document()
        except Exception:
            return
        try:
            full_lines = dict(getattr(self, "_loop_full_lines", None) or {})
        except Exception:
            full_lines = {}
        try:
            summary = _draw_cal_labels(
                doc,
                tracks,
                getattr(self, "_fouling_marks", None) or [],
                measure_points=full_lines,
            )
        except Exception as exc:
            print(f"   ! CAL labels skipped ({exc})")
            return

        try:
            redundant = set()
            for name in summary or {}:
                upper = str(name).upper()
                if upper.startswith("LOOP") or upper == "MAIN_LINE" or upper.startswith("MAIN_LINE_"):
                    display = name.replace("_", " ").title()
                    if upper == "MAIN_LINE":
                        display = "MAIN LINE"
                    redundant.add(display.strip().upper())
            if redundant:
                for entity in list(doc.modelspace()):
                    try:
                        if entity.dxftype() not in ("TEXT", "MTEXT"):
                            continue
                        if str(entity.dxf.layer or "").upper() != "TRACK_LABELS":
                            continue
                        try:
                            txt = (
                                str(entity.dxf.text or "").strip().upper()
                                if entity.dxftype() == "TEXT"
                                else str(entity.text or "").strip().upper()
                            )
                        except Exception:
                            continue
                        if txt in redundant:
                            doc.modelspace().delete_entity(entity)
                    except Exception:
                        continue
        except Exception:
            pass
        self._cal_summary = summary
        self._save_document(doc)
        for _name, (_label, _length) in summary.items():
            print(f"   OK {_label}")
        print(f"   ✓ CAL labels: {len(summary)}")


class CalLabelMixin(CalLabelStep):
    """Mixin for backward compatibility."""
    pass
