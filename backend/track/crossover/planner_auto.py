"""Low-level ray scanning, seeding, and conflict checks for AUTO crossover placement."""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import (
    AUTO_SEARCH_STEP_M,
    CHAINAGE_TOL_M,
    MAX_VERTEX_GAP_M,
)
from common.geometry import Point
from track.crossover.geometry import (
    _check_chainage_in_extent,
    _track_length,
    bands_overlap,
    build_crossover_geometry,
    compute_crossover_params,
    crossover_lateral_band,
    footprints_overlap,
    get_required_separation,
    is_opposite_side_pair,
    polyline_self_intersects,
    srj_positions_on_tracks,
)
from track.crossover.models import CrossoverRequest
from track.crossover.normalize import normalize_placement

_PARAMS_UNSET: object = object()  # will be replaced by conflict module's sentinel


def _params_or_none(planner, req, chainage):
    try:
        return compute_crossover_params(
            req, chainage, planner.tracks, planner.extents
        )
    except Exception:
        return None


from track.crossover.planner_conflict import (  # noqa: F401 re-export
    _PARAMS_UNSET,
    _candidate_violates_fixed,
    _centreline_buildable,
    _fixed_side_info,
    _params_or_none,
)

def _auto_start_after_prev(
    planner, req, prev_req, prev_ch: float, required: float
) -> float:
    """Earliest AUTO START after the previous crossover on the shared line."""
    try:
        shared = {req.from_track, req.to_track} & {
            prev_req.from_track,
            prev_req.to_track,
        }
        if not shared:
            return 0.0
        prev_p = _params_or_none(planner, prev_req, float(prev_ch))
        if prev_p is None:
            return float(prev_ch) + required
        prev_pos = srj_positions_on_tracks(
            prev_req, float(prev_ch), prev_p["to_main"]
        )
        own_p = _params_or_none(planner, req, float(prev_ch))
        if own_p is None:
            ext = (planner.extents or {}).get(req.from_track)
            probe = float(ext[0]) if ext is not None else 0.0
            own_p = _params_or_none(planner, req, probe)
            if own_p is None:
                return float(prev_ch) + required
            probe_ch = probe
        else:
            probe_ch = float(prev_ch)
        best: float | None = None
        for track in shared:
            if track not in prev_pos:
                continue
            if track == req.from_track:
                off = 0.0
            elif track == req.to_track:
                try:
                    off = float(own_p["to_main"]) - float(probe_ch)
                except (KeyError, TypeError, ValueError):
                    continue
            else:
                continue
            cand = float(prev_pos[track]) + required - off
            best = cand if best is None else max(best, cand)
        return best if best is not None else float(prev_ch) + required
    except Exception:
        return float(prev_ch) + required


def _auto_start_before_prev(
    planner, req, prev_req, prev_ch: float, required: float
) -> float:
    """Latest AUTO START ahead of the previous crossover's SRJs."""
    try:
        shared = {req.from_track, req.to_track} & {
            prev_req.from_track,
            prev_req.to_track,
        }
        if not shared:
            return 0.0
        prev_p = _params_or_none(planner, prev_req, float(prev_ch))
        if prev_p is None:
            return float(prev_ch) - required
        prev_pos = srj_positions_on_tracks(
            prev_req, float(prev_ch), prev_p["to_main"]
        )
        own_p = _params_or_none(planner, req, float(prev_ch))
        if own_p is None:
            ext = (planner.extents or {}).get(req.from_track)
            probe = float(ext[0]) if ext is not None else 0.0
            own_p = _params_or_none(planner, req, probe)
            if own_p is None:
                return float(prev_ch) - required
            probe_ch = probe
        else:
            probe_ch = float(prev_ch)
        best: float | None = None
        for track in shared:
            if track not in prev_pos:
                continue
            if track == req.from_track:
                off = 0.0
            elif track == req.to_track:
                try:
                    off = float(own_p["to_main"]) - float(probe_ch)
                except (KeyError, TypeError, ValueError):
                    continue
            else:
                continue
            cand = float(prev_pos[track]) - required - off
            best = cand if best is None else min(best, cand)
        return best if best is not None else float(prev_ch) - required
    except Exception:
        return float(prev_ch) - required


def _scan_ray(
    planner, req, seed, placed_params, placed_reqs, placed_chainages, upper
) -> float | None:
    """Scan forward from seed for the first fully-valid START."""
    ext = planner.extents.get(req.from_track)
    c = float(seed)
    if ext is not None:
        c = max(c, float(ext[0]))
    try:
        fixed_info = _fixed_side_info(
            planner, req, placed_params, placed_reqs, placed_chainages
        )
    except Exception:
        fixed_info = None
    steps = 0
    found: float | None = None
    while c <= upper + 1e-9 and steps < 20000:
        cand_p = _params_or_none(planner, req, c)
        reason = _candidate_violates_fixed(
            planner,
            req,
            c,
            placed_params,
            placed_reqs,
            placed_chainages,
            _cand_p=cand_p,
            _fixed_info=fixed_info,
        )
        if reason is None:
            found = c
            back = 0
            while back < 1200:
                trial = round(found - 0.001, 3)
                if trial < 0:
                    break
                if (
                    _candidate_violates_fixed(
                        planner,
                        req,
                        trial,
                        placed_params,
                        placed_reqs,
                        placed_chainages,
                        _fixed_info=fixed_info,
                    )
                    is None
                ):
                    found = trial
                    back += 1
                    continue
                break
            return found
        jumped = False
        cand_fp = (
            None
            if cand_p is None
            else (
                min(cand_p["start_chainage"], cand_p["end_chainage"]),
                max(cand_p["start_chainage"], cand_p["end_chainage"]),
            )
        )
        if cand_fp is not None and "footprint overlaps" in reason:
            for _fid, fp in placed_params.items():
                ofp = (
                    min(fp["start_chainage"], fp["end_chainage"]),
                    max(fp["start_chainage"], fp["end_chainage"]),
                )
                if footprints_overlap(cand_fp, ofp):
                    placement = normalize_placement(
                        req.placement, req.direction
                    )
                    if placement == "AHEAD":
                        c = max(c + AUTO_SEARCH_STEP_M, ofp[1])
                    else:
                        ol = cand_fp[1] - cand_fp[0]
                        c = max(c + AUTO_SEARCH_STEP_M, ofp[1] + ol)
                    jumped = True
                    break
        if not jumped:
            c += AUTO_SEARCH_STEP_M
        steps += 1
    return found


def _auto_upper_for(planner, req) -> float:
    """Upper MAIN-datum search bound for an AUTO start on its track."""
    try:
        ext = (planner.extents or {}).get(getattr(req, "from_track", ""))
        if ext is not None:
            return float(ext[1]) + 1.0
    except (TypeError, ValueError):
        pass
    try:
        pts = (planner.tracks or {}).get(getattr(req, "from_track", ""))
        if pts is not None and len(list(pts)) >= 2:
            return float(_track_length(list(pts))) + 1.0
    except Exception:
        pass
    return (planner.main_length + 1.0) if planner.main_length else 10000.0


def _describe_auto_dead_end(
    planner,
    req: CrossoverRequest,
    requests: Sequence[CrossoverRequest],
    earliest: float,
    placed_params: dict[str, dict],
    placed_chainages: dict[str, float],
) -> str:
    """Explain WHY an AUTO crossover has nowhere to go."""
    lines = [
        f"Crossover {req.id} (AUTO): no valid location exists "
        f"satisfying minimum spacing + turnout footprint + "
        f"available track length + other crossover geometry + "
        f"no overlap + design boundary."
    ]
    try:
        placement = normalize_placement(req.placement, req.direction)
        sign_txt = "+ OL" if placement == "AHEAD" else "- OL"
        params = _params_or_none(planner, req, float(earliest))
        ol_m = params["ol_m"] if params else None
        lines.append(
            f"  Earliest start tried: {earliest:.2f} m MAIN "
            f"(shared-line SRJ clear of the previous crossover by "
            f"the required minimum)."
        )
        if ol_m is not None:
            end = earliest + ol_m if placement == "AHEAD" else earliest - ol_m
            lo, hi = min(earliest, end), max(earliest, end)
            lines.append(
                f"  Turnout {getattr(req.turnout, 'designation', '?')}: "
                f"OL = {ol_m:.3f} m, so footprint would be "
                f"[{lo:.2f}, {hi:.2f}] m MAIN (second SRJ at START {sign_txt})."
            )
            bounds: list[str] = []
            if planner.main_length is not None:
                bounds.append(
                    f"MAIN alignment [0, {planner.main_length:.2f}] -> "
                    f"START <= {planner.main_length - ol_m:.2f}"
                    if placement == "AHEAD"
                    else f"MAIN alignment [0, {planner.main_length:.2f}] -> "
                    f"START >= {ol_m:.2f}"
                )
                latest = planner.main_length - ol_m
            else:
                latest = None
            ext_f = planner.extents.get(req.from_track)
            if ext_f is not None:
                bounds.append(
                    f"{req.from_track} extent [{ext_f[0]:.2f}, {ext_f[1]:.2f}] -> START in range"
                )
                latest = (
                    min(latest, ext_f[1]) if latest is not None else ext_f[1]
                )
            ext_t = planner.extents.get(req.to_track)
            if ext_t is not None:
                if placement == "AHEAD":
                    bounds.append(
                        f"{req.to_track} extent [{ext_t[0]:.2f}, {ext_t[1]:.2f}] -> "
                        f"START <= {ext_t[1] - ol_m:.2f} (second SRJ must fit)"
                    )
                    latest = (
                        min(latest, ext_t[1] - ol_m)
                        if latest is not None
                        else ext_t[1] - ol_m
                    )
                else:
                    bounds.append(
                        f"{req.to_track} extent [{ext_t[0]:.2f}, {ext_t[1]:.2f}] -> "
                        f"START >= {ext_t[0] + ol_m:.2f} (second SRJ must fit)"
                    )
            for b in bounds:
                lines.append(f"  Binding limit: {b}.")
            if latest is not None and latest + 1e-9 < earliest:
                lines.append(
                    f"  Latest feasible START ({latest:.2f} m) is before "
                    f"the earliest permitted START ({earliest:.2f} m) - no room."
                )
        if placed_params:
            occ = sorted(
                (
                    (
                        fid,
                        min(fp["start_chainage"], fp["end_chainage"]),
                        max(fp["start_chainage"], fp["end_chainage"]),
                    )
                    for fid, fp in placed_params.items()
                ),
                key=lambda t: t[1],
            )
            lines.append(
                "  Occupied footprints (MAIN m): "
                + ", ".join(f"{fid} [{a:.2f}, {b:.2f}]" for fid, a, b in occ)
                + "."
            )
    except Exception:
        pass
    return "\n".join(lines)


__all__ = [
    "_auto_start_after_prev",
    "_auto_start_before_prev",
    "_auto_upper_for",
    "_candidate_violates_fixed",
    "_centreline_buildable",
    "_describe_auto_dead_end",
    "_fixed_side_info",
    "_params_or_none",
    "_scan_ray",
]
