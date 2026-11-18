"""Crossover AUTO planner: resolves AUTO chainages satisfying spacing/footprint/geometry."""

from __future__ import annotations

from typing import Sequence

from common.constants import COLLISION_PUSH_SEPARATION_M
from common.geometry import Point
from track.crossover.geometry import (
    _resolve_extents,
    _track_length,
    build_crossover_geometry,
    compute_crossover_params,
    get_required_separation,
    srj_positions_on_tracks,
)
from track.crossover.models import CrossoverRequest, CrossoverResult
from track.crossover.normalize import normalize_placement
from track.crossover.planner_auto import (
    _auto_start_after_prev,
    _auto_start_before_prev,
    _auto_upper_for,
    _candidate_violates_fixed as _candidate_violates_fixed_fn,
    _describe_auto_dead_end,
    _params_or_none,
    _scan_ray,
)
from track.crossover.validator import CrossoverConstraintValidator


class CrossoverPlanner:
    """Turns List[CrossoverRequest] into validated CrossoverResults."""

    def __init__(
        self,
        tracks: dict[str, Sequence[Point]],
        extents: dict[str, tuple[float, float]] | None = None,
        main_length: float | None = None,
        *,
        loop_ranges: dict[str, tuple[float, float]] | None = None,
    ):
        self.tracks = tracks
        self.extents = _resolve_extents(extents)
        # Defined loop ends are distinct from the available overrun extents.
        self.loop_ranges = dict(loop_ranges or {})
        if main_length is None and "MAIN_LINE" in tracks:
            main_length = _track_length(tracks["MAIN_LINE"])
        self.main_length = main_length
        self.validator = CrossoverConstraintValidator(
            tracks, self.extents, self.main_length
        )

    def _params_or_none(self, req, chainage):
        return _params_or_none(self, req, chainage)

    def _candidate_violates_fixed(
        self, req, candidate, fixed_params, fixed_reqs, placed_chainages
    ):
        """Delegate to the module-level helper (method wrapper for tests)."""
        return _candidate_violates_fixed_fn(
            self, req, candidate, fixed_params, fixed_reqs, placed_chainages
        )

    def _auto_upper_for(self, req):
        """Delegate to the module-level helper (method wrapper for tests)."""
        return _auto_upper_for(self, req)

    def _footprint_or_none(self, req, chainage):
        p = self._params_or_none(req, chainage)
        if p is None:
            return None
        return (
            min(p["start_chainage"], p["end_chainage"]),
            max(p["start_chainage"], p["end_chainage"]),
        )

    def resolve_auto(
        self, requests: Sequence[CrossoverRequest]
    ) -> dict[str, float]:
        """Resolve every AUTO chainage to the earliest valid location."""
        resolved: dict[str, float] = {}
        fixed_reqs = {
            r.id: r
            for r in requests
            if not r.is_auto and r.chainage is not None
        }
        fixed_params: dict[str, dict] = {}
        for r in requests:
            if not r.is_auto and r.chainage is not None:
                p = self._params_or_none(r, float(r.chainage))
                if p is not None:
                    fixed_params[r.id] = p

        placed_order: list[str] = []

        for req in requests:
            if not req.is_auto and req.chainage is not None:
                resolved[req.id] = float(req.chainage)
                placed_order.append(req.id)
                continue

            requested_anchor = str((req.metadata or {}).get("auto_anchor_id") or "")
            loop_range = next(
                (self.loop_ranges[name] for name in (req.to_track, req.from_track)
                 if name in self.loop_ranges),
                None,
            )
            if loop_range is not None and requested_anchor not in placed_order:
                # Match the preview: try the connected loop's actual end, then
                # apply the existing collision push only to coincident SRJs.
                resolved[req.id] = float(loop_range[1 if req.direction == "REVERSE" else 0])
                placed = [r for r in requests if r.id in resolved]
                resolved = self._resolve_crossover_collisions(placed, resolved)
                # Subsequent anchored AUTO searches must see corrected positions.
                for placed_req in placed:
                    params = self._params_or_none(placed_req, resolved[placed_req.id])
                    if params is None:
                        fixed_params.pop(placed_req.id, None)
                    else:
                        fixed_params[placed_req.id] = params
                placed_order.append(req.id)
                continue

            if placed_order:
                requested_anchor = (req.metadata or {}).get("auto_anchor_id")
                prev_id = (
                    str(requested_anchor)
                    if requested_anchor
                    and str(requested_anchor) in placed_order
                    else placed_order[-1]
                )
                prev_ch = resolved[prev_id]
                prev_req = next(r for r in requests if r.id == prev_id)
                required = get_required_separation(prev_req, req)
                after = _auto_start_after_prev(
                    self, req, prev_req, float(prev_ch), required
                )
                before = _auto_start_before_prev(
                    self, req, prev_req, float(prev_ch), required
                )
                placement = normalize_placement(req.placement, req.direction)
                if placement == "AHEAD":
                    seeds = [after, before]
                else:
                    seeds = [before, after]
            else:
                seed0 = 0.0
                placement = normalize_placement(req.placement, req.direction)
                if placement == "BEHIND":
                    seed0 = 50.0
                seeds = [seed0]

            found: float | None = None
            upper = _auto_upper_for(self, req)
            placed_params: dict[str, dict] = dict(fixed_params)
            placed_chainages: dict[str, float] = {
                r.id: float(r.chainage)
                for r in requests
                if r.id in fixed_params
                and not r.is_auto
                and r.chainage is not None
            }
            for pid in placed_order:
                if pid in fixed_params:
                    placed_chainages[pid] = resolved[pid]
                    continue
                pr = next(r for r in requests if r.id == pid)
                pp = self._params_or_none(pr, resolved[pid])
                if pp is not None:
                    placed_params[pid] = pp
                placed_chainages[pid] = resolved[pid]
            placed_reqs = {r.id: r for r in requests if r.id in placed_params}
            earlier_requests = [r for r in requests if r.id in placed_order]

            for seed in seeds:
                # Keep the normal 13/54m anchor offset. If that actual candidate
                # meets another crossover, use the same 64m correction as FIXED
                # placement before spacing validation searches past the collision.
                if self._params_or_none(req, seed) is not None:
                    corrected = self._resolve_crossover_collisions(
                        [*earlier_requests, req], {**resolved, req.id: seed},
                        moving_id=req.id,
                    )
                    if corrected[req.id] != seed:
                        found = corrected[req.id]
                        break
                found = _scan_ray(
                    self,
                    req,
                    seed,
                    placed_params,
                    placed_reqs,
                    placed_chainages,
                    upper,
                )
                if found is not None:
                    break

            if found is None:
                raise ValueError(
                    _describe_auto_dead_end(
                        self,
                        req,
                        requests,
                        seeds[0],
                        placed_params,
                        placed_chainages,
                    )
                )
            resolved[req.id] = float(found)
            p_found = self._params_or_none(req, float(found))
            if p_found is not None:
                placed_params[req.id] = p_found
                fixed_params[req.id] = p_found
            placed_order.append(req.id)
        return resolved

    def _resolve_crossover_collisions(
        self,
        requests: Sequence[CrossoverRequest],
        resolved: dict[str, float],
        push_m: float = COLLISION_PUSH_SEPARATION_M,
        *,
        moving_id: str | None = None,
    ) -> dict[str, float]:
        """When two crossovers point at the exact same chainage or point on a shared track,
        keep the earlier placed crossover at its position, and push the second placed crossover
        starting point by push_m (64.0m) along its line of travel.
        """
        resolved = dict(resolved)
        placed_reqs: list[CrossoverRequest] = []

        for req in requests:
            ch = resolved.get(req.id)
            if ch is None:
                continue
            if moving_id is not None and req.id != moving_id:
                placed_reqs.append(req)
                continue

            collision = True
            iterations = 0
            while collision and iterations < 10:
                collision = False
                iterations += 1

                p_curr = self._params_or_none(req, ch)
                to_main_curr = (
                    p_curr["to_main"]
                    if p_curr is not None
                    else ch + (-1.0 if req.direction == "REVERSE" else 1.0) * 97.578
                )
                curr_srjs = srj_positions_on_tracks(req, ch, to_main_curr)

                for prev in placed_reqs:
                    shared_tracks = {req.from_track, req.to_track} & {
                        prev.from_track,
                        prev.to_track,
                    }
                    if not shared_tracks:
                        continue

                    prev_ch = resolved[prev.id]
                    p_prev = self._params_or_none(prev, prev_ch)
                    to_main_prev = (
                        p_prev["to_main"]
                        if p_prev is not None
                        else prev_ch + (-1.0 if prev.direction == "REVERSE" else 1.0) * 97.578
                    )
                    prev_srjs = srj_positions_on_tracks(prev, prev_ch, to_main_prev)

                    collides = False
                    if abs(ch - prev_ch) < 1.0:
                        collides = True
                    else:
                        for trk in shared_tracks:
                            if trk in curr_srjs and trk in prev_srjs:
                                if abs(curr_srjs[trk] - prev_srjs[trk]) < 1.0:
                                    collides = True
                                    break

                    if collides:
                        collision = True
                        if req.direction == "REVERSE":
                            ch -= push_m
                        else:
                            ch += push_m
                        break

            resolved[req.id] = ch
            placed_reqs.append(req)

        return resolved

    def plan(
        self, requests: Sequence[CrossoverRequest]
    ) -> tuple[list[CrossoverResult], object]:
        """Resolve AUTO, compute params/geometry, validate all levels."""
        resolved = (
            self.resolve_auto(requests)
            if any(r.is_auto for r in requests)
            else {r.id: float(r.chainage) for r in requests}
        )

        resolved = self._resolve_crossover_collisions(requests, resolved)

        for req in requests:
            req.chainage = float(resolved[req.id])
            if req.is_auto:
                req.position_mode = "AUTO"

        params_by_id: dict[str, dict] = {}
        geometry_by_id: dict[str, tuple[list, dict]] = {}
        param_errors: dict[str, str] = {}
        for req in requests:
            try:
                params = compute_crossover_params(
                    req, float(resolved[req.id]), self.tracks, self.extents
                )
                params_by_id[req.id] = params
                try:
                    pts, grep = build_crossover_geometry(req, params)
                    geometry_by_id[req.id] = (pts, grep)
                except Exception as exc:
                    geometry_by_id[req.id] = ([], {"warnings": [str(exc)]})
                    param_errors[req.id] = str(exc)
            except Exception as exc:
                param_errors[req.id] = str(exc)

        report = self.validator.validate_all(
            requests,
            resolved_chainages={k: float(v) for k, v in resolved.items()},
            params_by_id=params_by_id or None,
            geometry_by_id=geometry_by_id or None,
        )
        for cid, msg in param_errors.items():
            if not any(cid in e for e in report.errors):
                report.errors.append(f"Crossover {cid}: {msg}")
                report.overall_valid = False
                if "L5_geometry" in report.level_results:
                    report.level_results["L5_geometry"]["valid"] = False

        results: list[CrossoverResult] = []
        for req in requests:
            ch = float(resolved[req.id])
            params = params_by_id.get(req.id)
            geom = geometry_by_id.get(req.id)
            if params is None:
                results.append(
                    CrossoverResult(
                        id=req.id,
                        from_track=req.from_track,
                        to_track=req.to_track,
                        chainage=ch,
                        direction=req.direction,
                        placement=normalize_placement(
                            req.placement, req.direction
                        ),
                        turnout_type=getattr(req.turnout, "designation", None),
                        track_centre_mm=None,
                        track_centre_m=None,
                        n_ratio=None,
                        f_rad=None,
                        f_deg=None,
                        a_mm=None,
                        b_mm=None,
                        r_mm=None,
                        ol_mm=None,
                        ol_m=None,
                        crossover_type=None,
                        start_chainage=None,
                        end_chainage=None,
                        geometry=[],
                        geometry_report={},
                        validation_status="INVALID",
                        warnings=[],
                        errors=[
                            param_errors.get(
                                req.id, "parameter computation failed"
                            )
                        ],
                    )
                )
                continue
            pts, grep = geom if geom is not None else ([], {})
            status = "VALID" if report.overall_valid else "INVALID"
            results.append(
                CrossoverResult(
                    id=req.id,
                    from_track=req.from_track,
                    to_track=req.to_track,
                    chainage=ch,
                    direction=req.direction,
                    placement=params["placement"],
                    turnout_type=getattr(req.turnout, "designation", None),
                    track_centre_mm=params["tc_mm"],
                    track_centre_m=params["tc_m"],
                    n_ratio=params["n"],
                    f_rad=params["f_rad"],
                    f_deg=params["f_deg"],
                    a_mm=params["a_mm"],
                    b_mm=params["b_mm"],
                    r_mm=params["r_mm"],
                    ol_mm=params["ol_mm"],
                    ol_m=params["ol_m"],
                    crossover_type=params["crossover_type"],
                    start_chainage=params["start_chainage"],
                    end_chainage=params["end_chainage"],
                    geometry=list(pts),
                    geometry_report=dict(grep),
                    validation_status=status,
                    warnings=list(grep.get("warnings", [])),
                    errors=[e for e in report.errors if req.id in e],
                )
            )
        return results, report


__all__ = ["CrossoverPlanner"]
