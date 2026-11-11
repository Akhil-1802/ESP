"""LOOP / MAIN CAL callout labels (single definition).

Reference-image style labels drawn just above each running line:
* LOOP: ``LOOP LINE NO-n`` + ``CAL 776.000M (END TO END)``;
* MAIN: ``MAIN LINE NO-n`` + ``CAL 822.184M (FM TO FM)``.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from common.dxf import ensure_layer as _ensure_layer
from common.geometry import (
    Point,
    point_at_chainage as _chainage_point,
    polyline_length as _polyline_length,
    readable_angle_deg as _readable_angle,
)
from track.cal_calc import (
    CAL_COLOR,
    CAL_COLUMN_GAP_M,
    CAL_FRACTION,
    CAL_LAYER,
    CAL_MARK_BEFORE_CENTRE_M,
    CAL_STACK_BASE_M,
    CAL_STACK_STEP_M,
    CAL_SURVEY_HALF_M,
    CAL_TEXT_BACK_M,
    CAL_TEXT_GAP_M,
    CAL_TEXT_HEIGHT_M,
    CAL_TEXT_LIFT_M,
    CAL_TEXT_RUN_M,
    _is_loop_line,
    _is_main_line,
    _point_at_u,
    _top_rail_above,
    _track_frame,
    assign_line_numbers,
    format_loop_cal,
    format_loop_cal_value,
    format_loop_name,
    format_main_cal,
    format_main_cal_value,
    format_main_name,
    main_fm_span_m,
    split_cal_label,
)
from track.cal_layout import (
    _add_cal_text,
    _draw_cal_callout,
    _draw_cal_row,
    _draw_cal_text_only,
)


def draw_cal_labels(
    doc,
    tracks: Dict[str, Sequence[Point]],
    marks: Sequence[object] | None = None,
    measure_points: Dict[str, Sequence[Point]] | None = None,
) -> Dict[str, Tuple[str, float]]:
    """Draw every LOOP end-to-end + MAIN FM-to-FM CAL callout dynamically."""
    drawn: Dict[str, Tuple[str, float]] = {}
    try:
        for entity in list(doc.modelspace()):
            try:
                if entity.dxf.layer == CAL_LAYER:
                    doc.modelspace().delete_entity(entity)
            except Exception:
                continue
    except Exception:
        return drawn
    _ensure_layer(doc, CAL_LAYER, CAL_COLOR)

    jobs: list[dict] = []
    measure = measure_points or {}
    for name, kind, number in assign_line_numbers(tracks or {}):
        pts = (tracks or {}).get(name)
        if pts is None or len(list(pts)) < 2:
            continue
        mpts = measure.get(name) or pts
        try:
            if len(list(mpts)) < 2:
                mpts = pts
        except TypeError:
            mpts = pts
        if kind == "LOOP":
            span = main_fm_span_m(marks or [], name)
            if span is not None:
                length = float(span)
                cal_part = format_loop_cal_value(length, fm_to_fm=True)
            else:
                try:
                    length = float(
                        _polyline_length(
                            [(float(p[0]), float(p[1])) for p in mpts]
                        )
                    )
                except Exception:
                    continue
                cal_part = format_loop_cal_value(length, fm_to_fm=False)
            name_part = format_loop_name(number)
            label = f"{name_part} {cal_part}"
        else:
            span = main_fm_span_m(marks or [], name)
            if span is None:
                continue
            length = float(span)
            name_part = format_main_name(number)
            cal_part = format_main_cal_value(length)
            label = f"{name_part} {cal_part}"
        frame = _track_frame(mpts)
        if frame is None:
            frame = _track_frame(pts)
        if frame is None:
            continue
        tip, tangent, normal, ang, total = frame
        height = float(CAL_TEXT_HEIGHT_M)
        jobs.append(
            {
                "name": name,
                "label": label,
                "length": length,
                "name_part": name_part,
                "cal_part": cal_part,
                "tip": tip,
                "tangent": tangent,
                "normal": normal,
                "ang": ang,
                "total": total,
                "pts": pts,
                "width": len(label) * height * 0.7,
                "width_name": len(name_part) * height * 0.7,
                "width_cal": len(cal_part) * height * 0.7,
            }
        )
    if not jobs:
        return drawn

    before = float(CAL_MARK_BEFORE_CENTRE_M)
    valid_jobs: list[dict] = []
    for job in jobs:
        try:
            pts = [(float(p[0]), float(p[1])) for p in job["pts"]]
            run_total = float(_polyline_length(pts))
            if run_total < 1e-9:
                continue
            mid = run_total * float(CAL_FRACTION)
            tip_dist = min(max(mid - before, 5.0), max(run_total - 5.0, 5.0))
            station = _chainage_point(pts, tip_dist)
            tip = (float(station.point[0]), float(station.point[1]))
            tx, ty = float(station.tangent[0]), float(station.tangent[1])
            tn = math.hypot(tx, ty) or 1.0
            tx, ty = tx / tn, ty / tn
            nx, ny = -ty, tx
            try:
                ang = _readable_angle(math.degrees(math.atan2(ty, tx)))
            except Exception:
                ang = float(job["ang"])
            job["tip"] = tip
            job["tangent"] = (tx, ty)
            job["normal"] = (nx, ny)
            job["ang"] = float(ang)
            valid_jobs.append(job)
        except Exception:
            continue
    if not valid_jobs:
        return drawn

    running_names = [
        n for n in (tracks or {}) if _is_loop_line(n) or _is_main_line(n)
    ]

    ref_name = (
        "MAIN_LINE"
        if "MAIN_LINE" in running_names
        else (running_names[0] if running_names else None)
    )
    ref_frame = (
        _track_frame(tracks[ref_name])
        if ref_name and ref_name in (tracks or {})
        else None
    )
    if ref_frame is not None:
        ref_origin, ref_tangent, ref_normal = (
            ref_frame[0],
            ref_frame[1],
            ref_frame[2],
        )
    elif valid_jobs:
        ref_origin, ref_tangent, ref_normal = (
            valid_jobs[0]["tip"],
            valid_jobs[0]["tangent"],
            valid_jobs[0]["normal"],
        )
    else:
        ref_origin, ref_tangent, ref_normal = (
            (0.0, 0.0),
            (1.0, 0.0),
            (0.0, 1.0),
        )

    track_levels: dict[str, float] = {}
    for n in running_names:
        pts = (tracks or {}).get(n)
        if pts and len(pts) >= 2:
            res = _point_at_u(pts, 0.0, ref_origin, ref_tangent)
            if res is not None:
                pt, _ = res
                dx = pt[0] - ref_origin[0]
                dy = pt[1] - ref_origin[1]
                track_levels[n] = dx * ref_normal[0] + dy * ref_normal[1]
            else:
                p_mid = pts[len(pts) // 2]
                dx = p_mid[0] - ref_origin[0]
                dy = p_mid[1] - ref_origin[1]
                track_levels[n] = dx * ref_normal[0] + dy * ref_normal[1]

    sorted_tracks = sorted(
        [n for n in running_names if n in track_levels],
        key=lambda n: track_levels[n],
        reverse=True,
    )

    gaps: list[dict] = []
    for i in range(len(sorted_tracks) - 1):
        t_up, t_low = sorted_tracks[i], sorted_tracks[i + 1]
        v_up, v_low = track_levels[t_up], track_levels[t_low]
        h = v_up - v_low
        if h > 0.1:
            gaps.append(
                {
                    "idx": i,
                    "upper": t_up,
                    "lower": t_low,
                    "v_upper": v_up,
                    "v_lower": v_low,
                    "h": h,
                }
            )

    job_map = {j["name"]: j for j in valid_jobs}
    unplaced_tracks = [t for t in sorted_tracks if t in job_map]

    for gap_idx, gap in enumerate(gaps):
        if not unplaced_tracks:
            break

        t_up = gap["upper"]
        t_low = gap["lower"]
        h = float(gap["h"])

        can_fit_pair = h >= 4.2
        can_fit_single = h >= 3.0

        if not can_fit_single:
            continue

        has_up = t_up in unplaced_tracks
        has_low = t_low in unplaced_tracks

        if has_up and has_low and can_fit_pair:
            job_up = job_map[t_up]
            job_low = job_map[t_low]

            margin_top = 1.4 if h >= 5.0 else 1.2
            spacing = 1.8 if h >= 5.0 else 1.6
            v1 = gap["v_upper"] - margin_top
            v2 = v1 - spacing
            if v2 - gap["v_lower"] < 1.0:
                v2 = gap["v_lower"] + 1.0
                v1 = min(gap["v_upper"] - 1.2, v2 + spacing)

            track_v_up = track_levels.get(t_up, gap["v_upper"])
            track_v_low = track_levels.get(t_low, gap["v_lower"])

            delta_v_up = v1 - track_v_up
            delta_v_low = v2 - track_v_low

            drawn_up = _draw_cal_row(
                doc,
                job_up["name_part"],
                job_up["cal_part"],
                job_up["tip"],
                job_up["tangent"],
                job_up["normal"],
                job_up["ang"],
                job_up["width_name"],
                job_up["width_cal"],
                job_up["tip"],
                job_up["tip"],
                job_up["tip"],
                delta_v=delta_v_up,
            )
            if drawn_up:
                drawn[t_up] = (job_up["label"], job_up["length"])
                unplaced_tracks.remove(t_up)

            drawn_low = _draw_cal_row(
                doc,
                job_low["name_part"],
                job_low["cal_part"],
                job_low["tip"],
                job_low["tangent"],
                job_low["normal"],
                job_low["ang"],
                job_low["width_name"],
                job_low["width_cal"],
                job_low["tip"],
                job_low["tip"],
                job_low["tip"],
                delta_v=delta_v_low,
            )
            if drawn_low:
                drawn[t_low] = (job_low["label"], job_low["length"])
                unplaced_tracks.remove(t_low)

        elif has_up and has_low and not can_fit_pair:
            job = job_map[t_up]
            clearance_offset = 0.65
            v_text = gap["v_upper"] - clearance_offset
            track_v = track_levels.get(t_up, gap["v_upper"])
            delta_v = v_text - track_v
            if _draw_cal_text_only(
                doc,
                job["label"],
                job["tip"],
                job["tangent"],
                job["normal"],
                job["ang"],
                delta_v,
            ):
                drawn[t_up] = (job["label"], job["length"])
                unplaced_tracks.remove(t_up)

        elif has_up:
            job = job_map[t_up]
            clearance_offset = 0.65
            v_text = gap["v_upper"] - clearance_offset
            track_v = track_levels.get(t_up, gap["v_upper"])
            delta_v = v_text - track_v
            if _draw_cal_text_only(
                doc,
                job["label"],
                job["tip"],
                job["tangent"],
                job["normal"],
                job["ang"],
                delta_v,
            ):
                drawn[t_up] = (job["label"], job["length"])
                unplaced_tracks.remove(t_up)

        elif has_low:
            can_pair_below = False
            if gap_idx + 1 < len(gaps):
                next_gap = gaps[gap_idx + 1]
                if next_gap["upper"] == t_low:
                    t_next = next_gap["lower"]
                    if t_next in unplaced_tracks and next_gap["h"] >= 4.2:
                        can_pair_below = True

            if not can_pair_below:
                job = job_map[t_low]
                clearance_offset = 0.65
                v_text = gap["v_lower"] + clearance_offset
                track_v = track_levels.get(t_low, gap["v_lower"])
                delta_v = v_text - track_v
                if _draw_cal_text_only(
                    doc,
                    job["label"],
                    job["tip"],
                    job["tangent"],
                    job["normal"],
                    job["ang"],
                    delta_v,
                ):
                    drawn[t_low] = (job["label"], job["length"])
                    unplaced_tracks.remove(t_low)

    for t in list(unplaced_tracks):
        job = job_map[t]
        try:
            delta_v = float(CAL_TEXT_LIFT_M)
            if _draw_cal_row(
                doc,
                job["name_part"],
                job["cal_part"],
                job["tip"],
                job["tangent"],
                job["normal"],
                job["ang"],
                job["width_name"],
                job["width_cal"],
                job["tip"],
                job["tip"],
                job["tip"],
                delta_v=delta_v,
            ):
                drawn[t] = (job["label"], job["length"])
                unplaced_tracks.remove(t)
        except Exception:
            continue

    return drawn


__all__ = [
    "CAL_COLUMN_GAP_M",
    "CAL_COLOR",
    "CAL_FRACTION",
    "CAL_LAYER",
    "CAL_MARK_BEFORE_CENTRE_M",
    "CAL_STACK_BASE_M",
    "CAL_STACK_STEP_M",
    "CAL_SURVEY_HALF_M",
    "CAL_TEXT_BACK_M",
    "CAL_TEXT_GAP_M",
    "CAL_TEXT_HEIGHT_M",
    "CAL_TEXT_LIFT_M",
    "CAL_TEXT_RUN_M",
    "assign_line_numbers",
    "draw_cal_labels",
    "format_loop_cal",
    "format_loop_cal_value",
    "format_loop_name",
    "format_main_cal",
    "format_main_cal_value",
    "format_main_name",
    "main_fm_span_m",
    "split_cal_label",
]
