"""Crossover validation rules (L1 to L6)."""

from __future__ import annotations

import math
from typing import Sequence

from ...constants import CHAINAGE_TOL_M
from ...geometry.operations import Point
from .geometry import (
    _check_chainage_in_extent,
    actual_separation,
    bands_overlap,
    crossover_lateral_band,
    footprints_overlap,
    get_required_separation,
    is_opposite_side_pair,
    polyline_self_intersects,
)
from .models import AdjacentSpacingCheck, CrossoverRequest, FootprintCheck
from .normalize import normalize_direction


def validate_tracks_rule(
    tracks: dict[str, Sequence[Point]],
    requests: Sequence[CrossoverRequest],
) -> tuple[bool, list[str], list[str]]:
    """LEVEL 1: track validity."""
    errors, warnings = [], []
    ok = True
    for req in requests:
        if req.from_track not in tracks:
            errors.append(
                f"Crossover {req.id}: unknown FROM track "
                f"{req.from_track!r} (available: {sorted(tracks)})."
            )
            ok = False
        if req.to_track not in tracks:
            errors.append(
                f"Crossover {req.id}: unknown TO track "
                f"{req.to_track!r} (available: {sorted(tracks)})."
            )
            ok = False
        if req.from_track == req.to_track:
            errors.append(
                f"Crossover {req.id}: FROM and TO tracks must differ."
            )
            ok = False
        for name in (req.from_track, req.to_track):
            pts = tracks.get(name)
            if pts is not None and len(list(pts)) < 2:
                errors.append(
                    f"Crossover {req.id}: track {name!r} geometry "
                    f"is unavailable (needs >= 2 points)."
                )
                ok = False
    return ok, errors, warnings


def validate_chainages_rule(
    requests: Sequence[CrossoverRequest],
    main_length: float | None,
    extents: dict[str, tuple[float, float]],
) -> tuple[bool, list[str], list[str]]:
    """LEVEL 2: chainage validity."""
    errors, warnings = [], []
    ok = True
    for req in requests:
        if req.chainage is None:
            errors.append(
                f"Crossover {req.id}: chainage is AUTO but was not "
                f"resolved - planner must resolve AUTO before validation."
            )
            ok = False
            continue
        ch = float(req.chainage)
        if not math.isfinite(ch):
            errors.append(f"Crossover {req.id}: chainage is not finite.")
            ok = False
            continue
        if main_length is not None and (
            ch < -CHAINAGE_TOL_M or ch > main_length + CHAINAGE_TOL_M
        ):
            errors.append(
                f"Crossover {req.id}: chainage {ch:.2f}m is outside the "
                f"available MAIN alignment [0, {main_length:.2f}]m."
            )
            ok = False
            continue
        good, msg = _check_chainage_in_extent(req.from_track, ch, extents)
        if not good:
            errors.append(f"Crossover {req.id}: {msg}")
            ok = False
    return ok, errors, warnings


def validate_spacing_rule(
    resolved: Sequence[tuple[CrossoverRequest, float]],
    positions_by_id: dict[str, dict[str, float]] | None = None,
) -> tuple[bool, list[AdjacentSpacingCheck], list[str], list[str]]:
    """LEVEL 3: minimum spacing (chainage-based, N crossovers)."""
    errors, warnings = [], []
    checks: list[AdjacentSpacingCheck] = []
    if len(resolved) < 2:
        return True, checks, errors, warnings
    positions_by_id = positions_by_id or {}
    ordered = sorted(resolved, key=lambda item: float(item[1]))

    def _tracks_of(req, pos) -> set:
        if pos:
            try:
                return set(pos.keys())
            except Exception:
                pass
        return {req.from_track, req.to_track}

    ok = True
    n = len(ordered)
    for i in range(n):
        cur_req, cur_ch = ordered[i]
        pos_c = positions_by_id.get(cur_req.id, {})
        set_c = _tracks_of(cur_req, pos_c)
        nxt_idx = None
        for j in range(i + 1, n):
            cand_req, _cand_ch = ordered[j]
            pos_n = positions_by_id.get(cand_req.id, {})
            if set_c & _tracks_of(cand_req, pos_n):
                nxt_idx = j
                break
        if nxt_idx is None:
            continue
        nxt_req, nxt_ch = ordered[nxt_idx]
        required = get_required_separation(cur_req, nxt_req)
        pos_c = positions_by_id.get(cur_req.id, {})
        pos_n = positions_by_id.get(nxt_req.id, {})
        shared_gaps: dict[str, float] = {}
        for track in set(pos_c) & set(pos_n):
            try:
                gap = abs(float(pos_n[track]) - float(pos_c[track]))
            except (TypeError, ValueError):
                continue
            shared_gaps[track] = gap
        if shared_gaps:
            actual = min(shared_gaps.values())
            binding = (
                f"shared-track "
                f"{min(shared_gaps, key=shared_gaps.get)} SRJs"
            )
        else:
            actual = actual_separation(cur_ch, nxt_ch)
            binding = "START chainages (SRJ positions unavailable)"
        deficit = max(0.0, required - actual)
        valid = actual + 1e-9 >= required
        earlier_ch = min(float(cur_ch), float(nxt_ch))
        if float(nxt_ch) >= float(cur_ch):
            later_req, later_ch = nxt_req, float(nxt_ch)
            later_is_nxt = True
        else:
            later_req, later_ch = cur_req, float(cur_ch)
            later_is_nxt = False
        later_id = later_req.id
        suggested = earlier_ch + required
        pos_later_all = positions_by_id.get(later_req.id, {})
        for track, gap in shared_gaps.items():
            if gap + 1e-9 >= required:
                continue
            pos_later = pos_later_all.get(track)
            other_req = nxt_req if later_req is cur_req else cur_req
            pos_other = positions_by_id.get(other_req.id, {}).get(track)
            if pos_later is None or pos_other is None:
                continue
            off = float(pos_later) - float(later_ch)
            if float(pos_later) < float(pos_other):
                suggested = max(suggested, float(pos_other) + required - off)
        same = (
            normalize_direction(cur_req.direction)
            == normalize_direction(nxt_req.direction)
        )
        checks.append(
            AdjacentSpacingCheck(
                a_id=cur_req.id,
                b_id=nxt_req.id,
                required_m=required,
                actual_m=actual,
                deficit_m=deficit,
                valid=valid,
                suggested_min_chainage_b=(
                    suggested if later_is_nxt else float(nxt_ch)
                ),
                same_direction=same,
            )
        )
        if not valid:
            ok = False
            errors.append(
                f"Crossover {cur_req.id} -> {nxt_req.id}: "
                f"required minimum separation {required:.2f} m, "
                f"actual separation {actual:.2f} m ({binding}), "
                f"deficit {deficit:.2f} m. "
                f"Suggested earliest chainage: "
                f"{later_id} >= {suggested:.2f} m."
            )
    return ok, checks, errors, warnings


def validate_footprints_rule(
    footprints: dict[str, tuple[float, float]],
    order: Sequence[str],
    tracks: dict[str, Sequence[Point]],
    requests: Sequence[CrossoverRequest] | None = None,
    params_by_id: dict[str, dict] | None = None,
) -> tuple[bool, list[FootprintCheck], list[str], list[str]]:
    """LEVEL 4: physical footprint overlap."""
    errors, warnings = [], []
    checks: list[FootprintCheck] = []
    ok = True
    req_by_id = {r.id: r for r in (requests or [])}

    def _band(cid: str) -> tuple[float, float] | None:
        if params_by_id is None:
            return None
        req = req_by_id.get(cid)
        par = params_by_id.get(cid)
        if req is None or par is None:
            return None
        try:
            return crossover_lateral_band(req, par, tracks)
        except Exception:
            return None

    def _judge(a_id: str, b_id: str) -> None:
        nonlocal ok
        fa, fb = footprints[a_id], footprints[b_id]
        overlap = footprints_overlap(fa, fb)
        cleared = False
        clear_reason = ""
        if overlap and params_by_id is not None:
            band_a, band_b = _band(a_id), _band(b_id)
            if not bands_overlap(band_a, band_b):
                cleared = True
                clear_reason = (
                    f"Crossover {a_id} x {b_id}: MAIN-datum footprints "
                    f"overlap ([{min(fa):.2f}, {max(fa):.2f}] vs "
                    f"[{min(fb):.2f}, {max(fb):.2f}]) but the bodies run "
                    f"in different lateral strips -- no physical clash."
                )
            else:
                req_a, req_b = req_by_id.get(a_id), req_by_id.get(b_id)
                par_a, par_b = params_by_id.get(a_id), params_by_id.get(b_id)
                if (
                    req_a is not None
                    and req_b is not None
                    and par_a is not None
                    and par_b is not None
                    and is_opposite_side_pair(
                        req_a, par_a, req_b, par_b, tracks
                    )
                ):
                    cleared = True
                    clear_reason = (
                        f"Crossover {a_id} x {b_id}: MAIN-datum footprints "
                        f"overlap ([{min(fa):.2f}, {max(fa):.2f}] vs "
                        f"[{min(fb):.2f}, {max(fb):.2f}]) but the bodies lie "
                        f"on opposite sides of their shared main line -- cleared by the "
                        f"shared-track SRJ separation (see spacing checks)."
                    )
        valid = (not overlap) or cleared
        checks.append(
            FootprintCheck(
                a_id=a_id,
                b_id=b_id,
                a_start=min(fa),
                a_end=max(fa),
                b_start=min(fb),
                b_end=max(fb),
                overlaps=overlap,
                valid=valid,
            )
        )
        if overlap and not cleared:
            ok = False
            errors.append(
                f"ERROR: Crossover {a_id} and {b_id} physical "
                f"geometries overlap "
                f"([{min(fa):.2f}, {max(fa):.2f}] vs "
                f"[{min(fb):.2f}, {max(fb):.2f}] MAIN m)."
            )
        elif overlap and cleared:
            warnings.append(clear_reason)

    for a_id, b_id in zip(order, order[1:]):
        _judge(a_id, b_id)
    seen = {(c.a_id, c.b_id) for c in checks}
    for i in range(len(order)):
        for j in range(i + 2, len(order)):
            a_id, b_id = order[i], order[j]
            if (a_id, b_id) in seen:
                continue
            fa, fb = footprints[a_id], footprints[b_id]
            if not footprints_overlap(fa, fb):
                continue
            if params_by_id is not None and not bands_overlap(
                _band(a_id), _band(b_id)
            ):
                continue
            _judge(a_id, b_id)
            seen.add((a_id, b_id))
    return ok, checks, errors, warnings


def validate_geometry_rule(
    request: CrossoverRequest,
    params: dict,
    points: Sequence[Point],
    geom_report: dict,
) -> tuple[bool, list[str], list[str]]:
    """LEVEL 5: geometry validity."""
    errors, warnings = [], []
    ok = True
    pts = list(points)
    if len(pts) < 2:
        return False, [f"Crossover {request.id}: empty geometry."], warnings

    from_pt = params["from_pt"]
    to_pt = params["to_pt"]

    def _d(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    if _d(pts[0], from_pt) > 0.05:
        errors.append(
            f"Crossover {request.id}: geometry does not start on the "
            f"FROM track SRJ (gap {_d(pts[0], from_pt):.3f} m)."
        )
        ok = False
    if _d(pts[-1], to_pt) > 0.05:
        errors.append(
            f"Crossover {request.id}: geometry does not end on the "
            f"TO track SRJ (gap {_d(pts[-1], to_pt):.3f} m)."
        )
        ok = False

    def _unit(v):
        n = math.hypot(v[0], v[1]) or 1.0
        return (v[0] / n, v[1] / n)

    def _collinear_deg(seg, track_tangent) -> float:
        dot = min(
            max(seg[0] * track_tangent[0] + seg[1] * track_tangent[1], -1.0),
            1.0,
        )
        ang = math.degrees(math.acos(dot))
        return min(ang, 180.0 - ang)

    if len(pts) >= 2:
        seg0 = _unit((pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
        segN = _unit((pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]))
        tu = _unit(params["from_tangent"])
        tv = _unit(params["to_tangent"])
        ang0 = _collinear_deg(seg0, tu)
        angN = _collinear_deg(segN, tv)
        if ang0 > 5.0:
            errors.append(
                f"Crossover {request.id}: start tangent off track "
                f"tangent by {ang0:.2f} deg (limit 5 deg)."
            )
            ok = False
        if angN > 5.0:
            errors.append(
                f"Crossover {request.id}: end tangent off track "
                f"tangent by {angN:.2f} deg (limit 5 deg)."
            )
            ok = False

    max_gap = (
        max(_d(a, b) for a, b in zip(pts, pts[1:])) if len(pts) > 1 else 0.0
    )
    if max_gap > 5.0 + 1e-9:
        errors.append(
            f"Crossover {request.id}: polyline vertex gap "
            f"{max_gap:.2f} m exceeds 5 m (discontinuity)."
        )
        ok = False

    for w in geom_report.get("warnings", []):
        if "folds back" in w or "leaves the corridor" in w:
            errors.append(f"Crossover {request.id}: {w}.")
            ok = False
        else:
            warnings.append(f"Crossover {request.id}: {w}")

    try:
        if polyline_self_intersects(pts):
            errors.append(f"Crossover {request.id}: centreline self-intersects.")
            ok = False
    except Exception:
        pass
    return ok, errors, warnings


def validate_boundary_rule(
    request: CrossoverRequest,
    params: dict,
    main_length: float | None,
    extents: dict[str, tuple[float, float]],
) -> tuple[bool, list[str], list[str]]:
    """LEVEL 6: design boundary."""
    errors, warnings = [], []
    ok = True
    start, end = params["start_chainage"], params["end_chainage"]
    lo, hi = min(start, end), max(start, end)
    if main_length is not None:
        if lo < -CHAINAGE_TOL_M or hi > main_length + CHAINAGE_TOL_M:
            errors.append(
                f"Crossover {request.id}: footprint [{lo:.2f}, "
                f"{hi:.2f}]m lies outside the available MAIN "
                f"alignment [0, {main_length:.2f}]m - the main "
                f"track must not be silently extended."
            )
            ok = False
    ch = params.get("_chainage", (start if params.get("sign", 1.0) > 0 else end))
    good, msg = _check_chainage_in_extent(request.from_track, ch, extents)
    if not good:
        errors.append(f"Crossover {request.id}: {msg}")
        ok = False
    good2, msg2 = _check_chainage_in_extent(
        request.to_track, params["to_main"], extents
    )
    if not good2:
        errors.append(f"Crossover {request.id}: {msg2}")
        ok = False
    return ok, errors, warnings
