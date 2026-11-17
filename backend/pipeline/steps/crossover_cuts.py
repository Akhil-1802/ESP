"""Loop overrun cuts and trimming at crossover SRJs."""

from __future__ import annotations

import copy
import dataclasses
from typing import Dict, Tuple

import ezdxf

from common.constants import DEFAULT_OVERRUN_M
from common.dxf import add_polyline as _add_loop_polyline
from common.geometry import polyline_length as _plen
from track.drawing import _add_track_label as _add_label
from track.drawing import _annotate_overrun as _annotate_ext
from track.drawing import draw_srj_overrun_stub as _draw_stub
from track.generator import _generate_bounded_loop as _gen_loop
from track.overrun import (
    crossover_srjs_on_track as _srjs_on_track,
    loop_end_srj_cuts as _end_cuts,
    split_loop_for_overrun as _split_loop,
)

__all__ = ["apply_loop_overrun_cuts", "resolve_net_offset_and_side", "count_outer_loops"]


def resolve_net_offset_and_side(
    name: str, specs_by_name: dict[str, object]
) -> tuple[float, str]:
    """Calculate the total perpendicular distance and net side from MAIN_LINE.

    Walks up the reference_track chain, accumulating lateral offsets.
    Convention: LEFT is positive (+), RIGHT is negative (-).
    """
    total_signed = 0.0
    curr = name
    visited = set()
    while curr and curr != "MAIN_LINE" and curr not in visited:
        visited.add(curr)
        spec = specs_by_name.get(curr)
        if spec is None:
            break
        spacing = float(getattr(spec, "spacing", 0.0) or 0.0)
        side = str(getattr(spec, "side", "LEFT")).upper()
        sign = 1.0 if side == "LEFT" else -1.0
        total_signed += sign * spacing
        curr = getattr(spec, "reference_track", "MAIN_LINE") or "MAIN_LINE"

    net_spacing = abs(total_signed)
    net_side = "LEFT" if total_signed >= 0 else "RIGHT"
    return net_spacing, net_side


def count_outer_loops(name: str, specs_by_name: dict[str, object]) -> int:
    """Count how many loops on the same side are further from MAIN_LINE than this loop.

    Uses net lateral offset from MAIN_LINE. LEFT and RIGHT are evaluated separately.
    """
    if name not in specs_by_name:
        return 0
    my_spacing, my_side = resolve_net_offset_and_side(name, specs_by_name)
    count = 0
    for other_name in specs_by_name:
        if other_name == name or other_name == "MAIN_LINE" or str(other_name).startswith("MAIN_LINE_"):
            continue
        other_spacing, other_side = resolve_net_offset_and_side(other_name, specs_by_name)
        if other_side == my_side and other_spacing > my_spacing + 1e-3:
            count += 1
    return count


def apply_loop_overrun_cuts(
    doc_path: str,
    tracks: dict,
    crossover_results: list,
    loops_spec: list,
    additional_lines_spec: list,
    ranges: Dict[str, Tuple[float, float, float, float]],
    document=None,
) -> Tuple[dict, dict, dict, dict]:
    """Trim bounded loops at crossover SRJs into running + overrun.

    Returns (cuts, trim_extents, full_lines, splits).
    """
    if not ranges or not crossover_results:
        return {}, {}, {}, {}

    cuts: dict[str, tuple] = {}
    for name, (c1, c2, _eff_s, _eff_e) in ranges.items():
        if name not in tracks:
            continue
        try:
            srjs = _srjs_on_track(crossover_results, name)
        except Exception as exc:
            print(f"   ! Loop {name} SRJ collect skipped ({exc})")
            continue
        if not srjs:
            cuts[name] = (None, None)
            continue
        try:
            cut_start, cut_end = _end_cuts(c1, c2, srjs)
        except Exception as exc:
            print(f"   ! Loop {name} cut compute skipped ({exc})")
            continue
        cuts[name] = (cut_start, cut_end)

    if not cuts:
        return {}, {}, {}, {}

    splits: dict[str, tuple] = {}
    full_lines: dict[str, list] = {}
    trim_extents: dict[str, tuple[float, float]] = {}
    split_full_extents: dict[str, tuple[float, float]] = {}
    specs_by_name: dict[str, object] = {}
    for loop in list(loops_spec) + list(additional_lines_spec):
        lname = getattr(loop, "name", None)
        if lname:
            specs_by_name[lname] = loop

    main_points = tracks.get("MAIN_LINE")
    try:
        main_length = float(_plen(main_points)) if (_plen is not None and main_points) else None
    except Exception:
        main_length = None

    # Group all loops by net side (LEFT vs RIGHT)
    loops_by_side: dict[str, list[str]] = {"LEFT": [], "RIGHT": []}
    for name in ranges:
        if name not in tracks:
            continue
        _spacing, side = resolve_net_offset_and_side(name, specs_by_name)
        loops_by_side.setdefault(side, []).append(name)

    # Sort each side from outermost (num_outer == 0) to innermost (num_outer > 0)
    for side in ("LEFT", "RIGHT"):
        loops_by_side[side].sort(
            key=lambda n: count_outer_loops(n, specs_by_name)
        )

    target_extents: dict[str, tuple[float, float]] = {}
    for side, side_loop_names in loops_by_side.items():
        prev_s: float | None = None
        prev_e: float | None = None
        for name in side_loop_names:
            c1, c2, _eff_s, _eff_e = ranges[name]
            cut_start, cut_end = cuts.get(name, (None, None))
            num_outer = count_outer_loops(name, specs_by_name)
            spec = specs_by_name.get(name)
            ladder_step = 110.578
            t_des = str(getattr(spec, "turnout_designation", "1:12") or "1:12")
            if "8.5" in t_des:
                ladder_step = 78.0

            # Running START
            if cut_start is not None:
                run_s = float(cut_start)
            elif prev_s is not None:
                run_s = min(float(c1) - num_outer * ladder_step, prev_s - ladder_step)
            else:
                run_s = float(c1)

            srjs = _srjs_on_track(crossover_results, name)
            start_srjs = [ch for ch in srjs if ch <= (c1 + c2) / 2.0]
            if start_srjs:
                min_srj = min(start_srjs)
                if min_srj < run_s:
                    run_s = min_srj

            if prev_s is not None and run_s > prev_s:
                run_s = prev_s

            # Running END
            if cut_end is not None:
                run_e = float(cut_end)
            elif prev_e is not None:
                run_e = max(float(c2) + num_outer * ladder_step, prev_e + ladder_step)
            else:
                run_e = float(c2)

            end_srjs = [ch for ch in srjs if ch > (c1 + c2) / 2.0]
            if end_srjs:
                max_srj = max(end_srjs)
                if max_srj > run_e:
                    run_e = max_srj

            if prev_e is not None and run_e < prev_e:
                run_e = prev_e

            target_extents[name] = (run_s, run_e)
            prev_s = run_s
            prev_e = run_e

    for name in ranges:
        if name not in target_extents:
            continue
        c1, c2, eff_s, eff_e = ranges[name]
        spec = specs_by_name.get(name)
        net_spacing, net_side = resolve_net_offset_and_side(name, specs_by_name)
        if not (net_spacing > 0 and main_points and len(main_points) >= 2):
            continue
        ov_start_val = getattr(spec, "extend_start_m", None) if spec else None
        ov_end_val = getattr(spec, "extend_end_m", None) if spec else None
        ov_start = float(ov_start_val) if ov_start_val is not None else float(DEFAULT_OVERRUN_M)
        ov_end = float(ov_end_val) if ov_end_val is not None else float(DEFAULT_OVERRUN_M)

        run_s, run_e = target_extents[name]
        new_s = run_s - ov_start
        new_e = run_e + ov_end

        if main_length is not None:
            if new_s < 0:
                print(f"   ! Loop {name} START overrun clamped to MAIN start (wanted {new_s:.2f}m).")
                new_s = 0.0
                ov_start = run_s - new_s
            if new_e > main_length:
                print(f"   ! Loop {name} END overrun clamped to MAIN end (wanted {new_e:.2f}m).")
                new_e = float(main_length)
                ov_end = new_e - run_e

        if new_e <= new_s:
            print(f"   ! Loop {name} overrun cut skipped (empty extent)")
            continue
        try:
            full = _gen_loop(main_points, new_s, new_e, net_spacing, net_side)
            running, start_stub, end_stub = _split_loop(full, new_s, run_s, run_e)
        except Exception as exc:
            print(f"   ! Loop {name} overrun cut skipped ({exc})")
            continue
        if len(running) < 2:
            print(f"   ! Loop {name} overrun cut skipped (running line degenerate)")
            continue
        splits[name] = (running, start_stub, end_stub)
        full_lines[name] = [tuple(map(float, p[:2])) for p in full]
        split_full_extents[name] = (float(new_s), float(new_e))
        trim_extents[name] = (float(run_s), float(run_e))

    if not splits:
        return {}, {}, {}, {}

    try:
        doc = document if document is not None else ezdxf.readfile(doc_path)
    except Exception as exc:
        print(f"   ! Loop overrun redraw skipped ({exc})")
        return {}, {}, {}, {}

    loop_layers = {name.upper().replace(" ", "_") for name in ranges}
    for entity in list(doc.modelspace()):
        try:
            layer = entity.dxf.layer
        except Exception:
            continue
        if layer in loop_layers or layer in ("OVER_RUN", "TRACK_LABELS"):
            try:
                doc.modelspace().delete_entity(entity)
            except Exception:
                continue

    if "OVER_RUN" not in doc.layers:
        try:
            doc.layers.add("OVER_RUN", color=1)
        except Exception:
            pass
    if "TRACK_LABELS" not in doc.layers:
        try:
            doc.layers.add("TRACK_LABELS", color=1)
        except Exception:
            pass

    for name, (running, start_stub, end_stub) in splits.items():
        layer_name = name.upper().replace(" ", "_")
        if layer_name not in doc.layers:
            try:
                doc.layers.add(layer_name, color=1)
            except Exception:
                pass
        try:
            _add_loop_polyline(doc, running, layer_name, 1)
        except Exception as exc:
            print(f"   ! Loop {name} running redraw skipped ({exc})")
            continue
        spec = specs_by_name.get(name)
        _s_spacing, net_side = resolve_net_offset_and_side(name, specs_by_name)
        outward_left = net_side == "LEFT"
        ov_s_val = getattr(spec, "extend_start_m", None) if spec else None
        ov_e_val = getattr(spec, "extend_end_m", None) if spec else None
        ov_s = float(ov_s_val) if ov_s_val is not None else float(DEFAULT_OVERRUN_M)
        ov_e = float(ov_e_val) if ov_e_val is not None else float(DEFAULT_OVERRUN_M)
        if start_stub is not None and len(start_stub) >= 2 and ov_s > 0:
            try:
                _draw_stub(doc, start_stub, True, outward_left)
            except Exception:
                pass
        if end_stub is not None and len(end_stub) >= 2 and ov_e > 0:
            try:
                _draw_stub(doc, end_stub, False, outward_left)
            except Exception:
                pass

        tracks[name] = list(running)

    for name, points in tracks.items():
        spec = specs_by_name.get(name)
        if spec is not None and name not in splits:
            try:
                c1, c2, eff_s, eff_e = ranges[name]
                s_ann = float(getattr(spec, "extend_start_m", 0.0) or 0.0)
                e_ann = float(getattr(spec, "extend_end_m", 0.0) or 0.0)
                if s_ann > 0 or e_ann > 0:
                    _annotate_ext(doc, spec, points, c1, c2, eff_s, eff_e)
            except Exception:
                pass
        try:
            display = name.replace("_", " ").title()
            if name.upper() == "MAIN_LINE":
                display = "MAIN LINE"
            _add_label(doc, display, points, "TRACK_LABELS", color=1, height=1.0)
        except Exception:
            pass

    try:
        if document is None:
            doc.saveas(doc_path)
    except Exception as exc:
        print(f"   ! Loop overrun redraw save skipped ({exc})")

    for name, (cut_start, cut_end) in sorted(cuts.items()):
        c1, c2, eff_s, eff_e = ranges[name]
        run_s, run_e = trim_extents.get(name, (eff_s, eff_e))
        running, s_stub, e_stub = splits.get(name, (None, None, None))
        bits = []
        if cut_start is not None:
            try:
                cal = float(_plen(s_stub)) if (_plen is not None and s_stub) else None
            except Exception:
                cal = None
            bits.append(
                f"START cut @{cut_start:.2f}m (overrun CAL={cal:.2f})"
                if cal is not None
                else f"START cut @{cut_start:.2f}m"
            )
        if cut_end is not None:
            try:
                cal = float(_plen(e_stub)) if (_plen is not None and e_stub) else None
            except Exception:
                cal = None
            bits.append(
                f"END cut @{cut_end:.2f}m (overrun CAL={cal:.2f})"
                if cal is not None
                else f"END cut @{cut_end:.2f}m"
            )
        print(
            f"   OK Loop {name} [{c1:.2f}, {c2:.2f}] -> "
            f"running [{run_s:.2f}, {run_e:.2f}] MAIN m; "
            + "; ".join(bits)
        )

    return cuts, trim_extents, full_lines, splits
