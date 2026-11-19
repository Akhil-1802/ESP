"""Conflict checking helpers extracted from planner_auto.py (keep files <= 500 lines)."""

from __future__ import annotations

import math

from ...constants import CHAINAGE_TOL_M, MAX_VERTEX_GAP_M
from .geometry import (
    _check_chainage_in_extent,
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
from .models import CrossoverRequest

_PARAMS_UNSET: object = object()


def _params_or_none(planner, req, chainage):
    """Try to compute crossover params; return None on failure."""
    try:
        return compute_crossover_params(
            req, chainage, planner.tracks, planner.extents
        )
    except Exception:
        return None


def _centreline_buildable(req, params) -> bool:
    """True when the crossover centreline actually builds cleanly here."""
    try:
        pts, _rep = build_crossover_geometry(req, params)
    except Exception:
        return False
    if len(pts) < 2:
        return False
    try:
        if (
            max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
            > MAX_VERTEX_GAP_M + 1e-9
        ):
            return False
    except Exception:
        return False
    try:
        return not polyline_self_intersects(pts)
    except Exception:
        return True


def _fixed_side_info(
    planner,
    req,
    placed_params: dict[str, dict],
    placed_reqs: dict,
    placed_chainages: dict[str, float],
) -> dict:
    """Per-placed-crossover data that is constant for a whole ray."""
    info: dict = {}
    for fid, fp in placed_params.items():
        fre = placed_reqs[fid]
        required = get_required_separation(req, fre)
        try:
            other_pos = srj_positions_on_tracks(
                fre, float(placed_chainages[fid]), fp["to_main"]
            )
        except (KeyError, TypeError, ValueError):
            other_pos = {}
        ofp = (
            min(fp["start_chainage"], fp["end_chainage"]),
            max(fp["start_chainage"], fp["end_chainage"]),
        )
        try:
            placed_band = crossover_lateral_band(fre, fp, planner.tracks)
        except Exception:
            placed_band = None
        info[fid] = (fre, fp, required, other_pos, ofp, placed_band)
    return info


def _candidate_violates_fixed(
    planner,
    req,
    candidate,
    fixed_params: dict[str, dict],
    fixed_reqs: dict[str, CrossoverRequest],
    placed_chainages: dict[str, float],
    _cand_p=_PARAMS_UNSET,
    _fixed_info=None,
) -> str | None:
    """Return a reason string when candidate conflicts with any placed."""
    cand_p = (
        _params_or_none(planner, req, candidate)
        if _cand_p is _PARAMS_UNSET
        else _cand_p
    )
    if cand_p is None:
        return "geometry does not fit at candidate"
    cand_fp = (
        min(cand_p["start_chainage"], cand_p["end_chainage"]),
        max(cand_p["start_chainage"], cand_p["end_chainage"]),
    )
    ok1, _m1 = _check_chainage_in_extent(req.from_track, candidate, planner.extents)
    if not ok1:
        return "START outside FROM extent"
    ok2, _m2 = _check_chainage_in_extent(
        req.to_track, cand_p["to_main"], planner.extents
    )
    if not ok2:
        return "second SRJ outside TO extent"
    lo, hi = cand_fp
    if planner.main_length is not None and (
        lo < -CHAINAGE_TOL_M or hi > planner.main_length + CHAINAGE_TOL_M
    ):
        return "outside MAIN alignment"
    try:
        cand_pos = srj_positions_on_tracks(
            req, float(candidate), cand_p["to_main"]
        )
    except (KeyError, TypeError, ValueError):
        cand_pos = {req.from_track: float(candidate)}
    overlap_fid: str | None = None
    if _fixed_info is None:
        for fid, fp in fixed_params.items():
            fre = fixed_reqs[fid]
            required = get_required_separation(req, fre)
            try:
                other_pos = srj_positions_on_tracks(
                    fre, float(placed_chainages[fid]), fp["to_main"]
                )
            except (KeyError, TypeError, ValueError):
                other_pos = {}
            shared = set(cand_pos) & set(other_pos)
            for track in shared:
                try:
                    gap = abs(float(cand_pos[track]) - float(other_pos[track]))
                except (TypeError, ValueError):
                    continue
                if gap + 1e-9 < required:
                    return (
                        f"shared-track {track} SRJ gap {gap:.2f}m < "
                        f"{required:.2f}m vs {fid}"
                    )
            ofp = (
                min(fp["start_chainage"], fp["end_chainage"]),
                max(fp["start_chainage"], fp["end_chainage"]),
            )
            if footprints_overlap(cand_fp, ofp):
                try:
                    cand_band = crossover_lateral_band(
                        req, cand_p, planner.tracks
                    )
                    placed_band = crossover_lateral_band(
                        fre, fp, planner.tracks
                    )
                except Exception:
                    cand_band, placed_band = None, None
                if not bands_overlap(cand_band, placed_band):
                    pass
                elif is_opposite_side_pair(
                    req, cand_p, fre, fp, planner.tracks
                ):
                    pass
                else:
                    overlap_fid = fid
                    break
    else:
        for fid, (
            fre,
            fp,
            required,
            other_pos,
            ofp,
            placed_band,
        ) in _fixed_info.items():
            shared = set(cand_pos) & set(other_pos)
            for track in shared:
                try:
                    gap = abs(float(cand_pos[track]) - float(other_pos[track]))
                except (TypeError, ValueError):
                    continue
                if gap + 1e-9 < required:
                    return (
                        f"shared-track {track} SRJ gap {gap:.2f}m < "
                        f"{required:.2f}m vs {fid}"
                    )
            if footprints_overlap(cand_fp, ofp):
                try:
                    cand_band = crossover_lateral_band(
                        req, cand_p, planner.tracks
                    )
                except Exception:
                    cand_band = None
                if not bands_overlap(cand_band, placed_band):
                    pass
                elif is_opposite_side_pair(
                    req, cand_p, fre, fp, planner.tracks
                ):
                    pass
                else:
                    overlap_fid = fid
                    break
    if overlap_fid is not None:
        if not _centreline_buildable(req, cand_p):
            return "geometry does not fit at candidate"
        return f"footprint overlaps {overlap_fid}"
    if not _centreline_buildable(req, cand_p):
        return "geometry does not fit at candidate"
    return None



__all__ = ['_fixed_side_info', '_candidate_violates_fixed']
