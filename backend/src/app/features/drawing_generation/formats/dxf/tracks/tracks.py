"""Track DXF drawing coordinator.

Draws all track centrelines, labels, T.Cs, overruns, and direction marks.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Set

from ....domain.track.overrun import split_loop_for_overrun
from ....domain.track.specs import LineSpec
from ..primitives import add_polyline as _common_polyline
from .annotations import _add_all_tc_annotations, _add_track_label
from .markers import _annotate_overrun, _draw_direction_mark, draw_srj_overrun_stub

__all__ = ["draw_tracks"]


def _is_main_line(name: str) -> bool:
    """Whether ``name`` is the base or an added full-length MAIN line."""
    normalized = str(name).upper()
    return normalized == "MAIN_LINE" or normalized.startswith("MAIN_LINE_")


def _bounded_loop_info(config) -> dict[str, tuple]:
    """Bounded-loop name -> (spec, c1, c2, eff_c1, eff_c2), MAIN datum."""
    info: dict[str, tuple] = {}
    for loop in list(config.loops) + list(config.additional_lines):
        c1 = getattr(loop, "first_crossover_chainage", None)
        if c1 is None or not hasattr(loop, "spacing"):
            continue
        c2 = getattr(loop, "second_crossover_chainage", None)
        if c2 is None:
            c2 = c1 + getattr(loop, "crossover_distance_m", 750.0)
        ext_s = getattr(loop, "extend_start_m", 0.0) or 0.0
        ext_e = getattr(loop, "extend_end_m", 0.0) or 0.0
        info[loop.name] = (
            loop,
            float(c1),
            float(c2),
            float(c1) - ext_s,
            float(c2) + ext_e,
        )
    return info


def draw_tracks(
    doc,
    tracks: dict,
    config,
    loop_results: dict,
    overrun_jobs: list,
    loop_cuts: dict[str, tuple[float | None, float | None]] | None = None,
) -> Set[str]:
    """Draw all track centrelines + labels + T.Cs + overruns + directions."""
    cuts = loop_cuts or {}
    label_layer = "TRACK_LABELS"
    tc_layer = "TRACK_CENTERS"
    if label_layer not in doc.layers:
        doc.layers.add(label_layer, color=1)
    if tc_layer not in doc.layers:
        doc.layers.add(tc_layer, color=1)
    info = _bounded_loop_info(config)
    srj_cut_names: Set[str] = set()

    for name, points in tracks.items():
        layer_name = name.upper().replace(" ", "_")
        if layer_name not in doc.layers:
            doc.layers.add(layer_name, color=1)
        cut = cuts.get(name)
        bounded = info.get(name)
        if (
            cut is not None
            and bounded is not None
            and (cut[0] is not None or cut[1] is not None)
        ):
            spec, _c1, _c2, eff_c1, _eff_c2 = bounded
            running, start_stub, end_stub = split_loop_for_overrun(
                points, eff_c1, cut[0], cut[1]
            )
            _common_polyline(doc, running, layer_name, 1)
            outward_left = str(getattr(spec, "side", "LEFT")).upper() == "LEFT"
            if start_stub is not None:
                draw_srj_overrun_stub(doc, start_stub, True, outward_left, track_name=name)
            if end_stub is not None:
                draw_srj_overrun_stub(doc, end_stub, False, outward_left, track_name=name)
            if cut[0] is None or cut[1] is None:
                try:
                    try:
                        _spec_one = dataclasses.replace(
                            spec,
                            extend_start_m=(
                                0.0
                                if cut[0] is not None
                                else getattr(spec, "extend_start_m", 0.0)
                            ),
                            extend_end_m=(
                                0.0
                                if cut[1] is not None
                                else getattr(spec, "extend_end_m", 0.0)
                            ),
                        )
                    except Exception:
                        _spec_one = copy.copy(spec)
                        if cut[0] is not None:
                            try:
                                _spec_one.extend_start_m = 0.0
                            except Exception:
                                pass
                        if cut[1] is not None:
                            try:
                                _spec_one.extend_end_m = 0.0
                            except Exception:
                                pass
                    _annotate_overrun(
                        doc, _spec_one, running, _c1, _c2, eff_c1, _eff_c2
                    )
                except Exception:
                    pass
            srj_cut_names.add(name)
            points = running
        elif name.upper().startswith("LOOP"):
            _common_polyline(doc, points, layer_name, 1)
        else:
            _common_polyline(doc, points, layer_name, 1)

        if not _is_main_line(name):
            display = name.replace("_", " ").title()
            _add_track_label(doc, display, points, label_layer, color=1, height=1.0)

    _add_all_tc_annotations(doc, tracks, layer=tc_layer, color=1, height=0.8)

    if loop_results:
        for layer in ("TURNOUT", "TURNOUT_SWITCH", "TURNOUT_CROSSING"):
            if layer not in doc.layers:
                doc.layers.add(layer, color=1)
        if "LOOP_CROSSOVER" not in doc.layers:
            doc.layers.add("LOOP_CROSSOVER", color=1)

    for spec, c1, c2, eff_c1, eff_c2 in overrun_jobs:
        if spec.name in srj_cut_names:
            continue
        _annotate_overrun(doc, spec, tracks[spec.name], c1, c2, eff_c1, eff_c2)

    _mains: list[str] = []
    if "MAIN_LINE" in tracks:
        _mains.append("MAIN_LINE")
    for _ln in config.additional_lines:
        if (
            isinstance(_ln, LineSpec)
            and _ln.name.startswith("MAIN_LINE_")
            and _ln.name in tracks
        ):
            _mains.append(_ln.name)
    _dirs: dict[str, str] = {}
    for _ln in config.additional_lines:
        if isinstance(_ln, LineSpec) and (_ln.direction or "").upper() in ("UP", "DN"):
            _dirs[_ln.name] = _ln.direction.upper()
    _dirs.update(getattr(config, "main_directions", None) or {})
    has_stations = bool(getattr(config, "stations", None))
    if has_stations or (len(_mains) == 1 and not _dirs.get(_mains[0])):
        pass
    else:
        for _i, _nm in enumerate(_mains):
            _d = (_dirs.get(_nm) or ("UP" if _i == 0 else "DN")).upper()
            if _d in ("UP/DN", "BOTH"):
                continue
            if _d not in ("UP", "DN"):
                _d = "UP" if _i == 0 else "DN"
            _draw_direction_mark(doc, tracks[_nm], _d, False, 1 if _d == "UP" else -1)
    return srj_cut_names
