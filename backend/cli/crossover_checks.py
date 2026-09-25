"""Crossover live-validation helpers (shared-track SRJ spacing, footprints)."""

from __future__ import annotations

import random
from typing import Any

from cli.base import ask, polyline_length
from track.crossover.conflicts import (
    crossover_track_intervals,
    find_restriction_conflicts,
)
from track.crossover.defaults import (
    auto_candidates_for_main,
    requests_from_specs,
)
from track.crossover.geometry import (
    compute_crossover_params,
    main_track_anchors,
)
from track.crossover.normalize import normalize_direction
from track.crossover.planner import CrossoverPlanner
from track.crossover.rules import get_required_separation
from track.specs import CrossoverSpec


def _result_positions(result: Any) -> dict[str, float]:
    """MAIN-datum SRJ position per track for an accepted/candidate result."""
    second = (result.end_chainage if result.placement == "AHEAD"
              else result.start_chainage)
    return {
        result.from_track: float(result.chainage),
        result.to_track: float(second),
    }


def _srj_kind(result: Any, track: str) -> str:
    """Whether the SRJ on `track` is the crossover's start or end."""
    pos = _result_positions(result)[track]
    return "starts" if abs(pos - float(result.chainage)) < 1e-6 else "ends"


def _validate_candidate_live(
    spec: CrossoverSpec,
    accepted: list[CrossoverSpec],
    tracks: dict,
    extents: dict[str, tuple[float, float]],
    main_length: float,
    restrictions: list,
) -> tuple[bool, str]:
    """Validate one candidate crossover spec immediately (no drawing).

    Pipeline per candidate: geometry engine calculates the complete
    crossover (endpoint derived, never asked) -> engine L1-L6 validation
    against ALL accepted crossovers -> restricted-region check. Returns
    (valid, message). Engineering rejections never raise; only truly
    unexpected failures propagate.
    """
    planner = CrossoverPlanner(tracks, extents or {}, main_length)
    try:
        results, report = planner.plan(
            requests_from_specs(list(accepted) + [spec]))
    except Exception as exc:
        return False, (
            f"\u274c Crossover {spec.id} rejected\n"
            f"  Geometry error: {exc}"
        )
    by_id = {res.id: res for res in results}
    cand = by_id.get(spec.id)

    if not report.overall_valid or cand is None \
            or cand.start_chainage is None:
        lines = [f"\u274c Crossover {spec.id} rejected"]
        # Shared-track endpoint detail (previous END vs new START on the
        # shared line), then the formal engine errors mentioning it.
        if cand is not None and cand.start_chainage is not None:
            try:
                cpos = _result_positions(cand)
            except (TypeError, ValueError):
                cpos = {}
            for acc in accepted:
                ares = by_id.get(acc.id)
                if ares is None or ares.start_chainage is None:
                    continue
                try:
                    apos = _result_positions(ares)
                except (TypeError, ValueError):
                    continue
                if not (set(cpos) & set(apos)):
                    continue
                required = get_required_separation(
                    cand.direction, ares.direction)
                for track in sorted(set(cpos) & set(apos)):
                    avail = abs(cpos[track] - apos[track])
                    if avail + 1e-9 >= required:
                        continue
                    lines.append(
                        f"  {acc.id} {_srj_kind(ares, track)} on "
                        f"{track} at {apos[track]:.2f} m.")
                    lines.append(
                        f"  {spec.id} {_srj_kind(cand, track)} on "
                        f"{track} at {cpos[track]:.2f} m.")
                    lines.append(
                        f"  Available separation = {avail:.2f} m.")
                    lines.append(
                        f"  Required separation = {required:.2f} m.")
        for err in report.errors:
            if spec.id in err and "required minimum separation" not in err:
                lines.append(f"  {err}")
        if len(lines) == 1:
            for err in report.errors:
                if spec.id in err:
                    lines.append(f"  {err}")
        return False, "\n".join(lines)

    # Engine accepted: check restricted regions (platforms, stations...).
    second = (cand.end_chainage if cand.placement == "AHEAD"
              else cand.start_chainage)
    try:
        a_m = float(spec.turnout.a_mm) / 1000.0  # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        a_m = 0.0
    intervals = crossover_track_intervals(
        spec.from_track, spec.to_track, float(spec.from_chainage_m),  # type: ignore[arg-type]
        float(second), cand.placement, cand.direction, a_m)
    conflicts = find_restriction_conflicts(intervals, restrictions)
    if conflicts:
        lines = [f"\u274c Crossover {spec.id} rejected",
                 "  Crossover conflicts with a restricted region."]
        for cf in conflicts:
            lines.append(
                f"  Crossover footprint: {cf.footprint_start:.1f} m \u2192 "
                f"{cf.footprint_end:.1f} m on {cf.track}")
            lines.append(
                f"  {cf.region.reason}: "
                f"{min(cf.region.start_chainage, cf.region.end_chainage):.1f} m "
                f"\u2192 {max(cf.region.start_chainage, cf.region.end_chainage):.1f} m")
            lines.append(
                f"  Overlap: {cf.overlap_start:.1f} m \u2192 {cf.overlap_end:.1f} m")
        return False, "\n".join(lines)

    arrow = "->" if cand.direction == "FORWARD" else "<-"
    return True, (
        f"\u2713 Crossover {spec.id} accepted\n"
        f"  From: {spec.from_track} @ {float(spec.from_chainage_m):.2f} m\n"  # type: ignore[arg-type]
        f"  To: {spec.to_track} @ {float(second):.2f} m {arrow}\n"
        f"  Direction: {cand.direction}\n"
        f"  Turnout: {spec.turnout.designation if spec.turnout else '?'}"
    )


def _blocked_suffix(blocked: list) -> str:
    """Compact '; not in [a-b], ...' prompt fragment ('' when none)."""
    if not blocked:
        return ""
    return "; not in " + ", ".join(
        f"[{b0:.3f}-{b1:.3f}]" for b0, b1, _reason in blocked)


def _accepted_main_params(accepted: list[CrossoverSpec], tracks: dict, extents: dict):
    """Resolved STARTs + computed params for accepted specs (anchor use).

    Returns (requests, resolved, params_by_id); entries that fail to
    compute are skipped (accepted specs already validated, so this is
    only a guard for anchor collection).
    """
    try:
        reqs = requests_from_specs(list(accepted))
    except Exception:
        return [], {}, {}
    resolved: dict[str, float] = {}
    for req in reqs:
        if req.chainage is None:
            continue
        try:
            resolved[req.id] = float(req.chainage)
        except (TypeError, ValueError):
            continue
    params_by_id: dict[str, dict] = {}
    for req in reqs:
        if req.id not in resolved:
            continue
        try:
            params_by_id[req.id] = compute_crossover_params(
                req, float(resolved[req.id]), tracks, extents)
        except Exception:
            continue
    return reqs, resolved, params_by_id


def _anchor_options_for_track(from_track: str, accepted: list[CrossoverSpec], tracks: dict, extents: dict) -> list[dict]:
    """Describe each accepted crossover's point(s) on ``from_track``.

    Returns one entry per accepted spec: id, from/to, direction, and the
    sorted list of MAIN-datum SRJ positions where that crossover touches
    ``from_track`` (START when it starts there, second SRJ when it ends
    there, empty when it does not touch the line). Used to show the
    AUTO anchor menu so the 13 m / 54 m rule is measured from the
    crossover point on the line we are starting from.
    """
    reqs, resolved, params_by_id = _accepted_main_params(
        accepted, tracks, extents)
    anchors = main_track_anchors(reqs, resolved, params_by_id, from_track)
    pos_by_id: dict[str, list[dict]] = {}
    for anc in anchors:
        pos_by_id.setdefault(str(anc.get("id")), []).append(anc)
    out: list[dict] = []
    for spec in accepted:
        cid = str(getattr(spec, "id", "?"))
        touches = sorted(pos_by_id.get(cid, []), key=lambda a: float(a["pos"]))
        out.append({
            "id": cid,
            "from_track": getattr(spec, "from_track", "?"),
            "to_track": getattr(spec, "to_track", "?"),
            "direction": str(getattr(spec, "direction", "FORWARD")),
            "positions": [float(a["pos"]) for a in touches],
            "kinds": [str(a.get("kind", "")) for a in touches],
        })
    return out


def _ask_auto_anchor(from_track: str, new_direction: str, accepted: list[CrossoverSpec],
                     tracks: dict, extents: dict) -> str | None:
    """Ask which prior crossover an AUTO start is measured from.

    Lists every accepted crossover with its SRJ position(s) on
    ``from_track`` (the line the new crossover starts from) so the user
    picks the anchor explicitly. Shows the 13 m (same direction) /
    54 m (opposite) requirement for each option against the new
    direction. Returns the chosen crossover id, or None when there is
    nothing to anchor to. Defaults to the previous crossover.
    """
    if not accepted:
        return None
    options = _anchor_options_for_track(from_track, accepted, tracks, extents)
    print(f"  AUTO anchor on {from_track} (13 m same direction / 54 m opposite):")
    ids: list[str] = []
    for opt in options:
        ids.append(opt["id"])
        try:
            required = float(get_required_separation(
                new_direction, opt["direction"]))
        except ValueError:
            required = float("nan")
        if opt["positions"]:
            pos_txt = ", ".join(
                f"{p:.2f} m ({k})" for p, k in zip(opt["positions"], opt["kinds"]))
        else:
            pos_txt = f"no point on {from_track} (falls back to START+gap)"
        print(f"    {opt['id']}: {opt['from_track']}->{opt['to_track']} "
              f"{opt['direction']} | {from_track} point(s): {pos_txt} | "
              f"vs new {new_direction}: needs {required:.0f} m")
    default = ids[-1] if ids else None
    while True:
        raw = ask(f"  Anchor crossover for AUTO ({', '.join(ids)})",
                  default)
        choice = str(raw or default or "").strip().upper()
        for cid in ids:
            if choice == str(cid).upper():
                return cid
        print(f"Please choose one of: {', '.join(ids)}")


def _track_search_span(from_track: str, tracks: dict, extents: dict,
                       main_length: float | None) -> tuple[float, float]:
    """(lo, hi) MAIN-datum search span for AUTO starts on ``from_track``.

    Bounded tracks contribute their own extent; full-length tracks
    (MAIN_LINE, MAIN_LINE_N, ...) their own length; the MAIN datum
    length is only the last-resort fallback. AUTO never assumes
    MAIN_LINE -- the span always belongs to the track being started on.
    """
    lo, hi = 0.0, None
    ext = (extents or {}).get(from_track)
    if ext is not None:
        try:
            lo, hi = float(ext[0]), float(ext[1])
        except (TypeError, ValueError):
            lo, hi = 0.0, None
    if hi is None:
        try:
            pts = (tracks or {}).get(from_track)
            if pts is not None and len(list(pts)) >= 2:
                hi = float(polyline_length(list(pts)))
        except Exception:
            hi = None
    if hi is None:
        try:
            hi = float(main_length) if main_length is not None else 10000.0
        except (TypeError, ValueError):
            hi = 10000.0
    return float(lo), float(hi)


def _resolve_auto_start(
    from_track: str,
    to_track: str,
    direction: str,
    turnout: Any,
    accepted: list[CrossoverSpec],
    tracks: dict,
    extents: dict,
    main_length: float,
    restrictions: list,
    cid: str = "AUTO",
    rng: Any = None,
    anchor_id: str | None = None,
) -> tuple[float, str]:
    """Resolve an AUTO start on any track to a concrete chainage.

    The anchor, candidates, bounds and search span all belong to
    ``from_track`` (the line the new crossover starts from) -- MAIN_LINE
    is never assumed. The START is placed exactly the required minimum
    from the anchor crossover's point on ``from_track``: 13 m when the
    anchor and new directions match, 54 m when opposite
    (``get_required_separation``). Both the ahead (anchor + required)
    and behind (anchor - required) candidates are tried with full
    validation (spacing vs ALL accepted + footprint + boundary +
    restricted regions); the first valid wins.

    ``anchor_id`` selects the prior crossover explicitly (the CLI anchor
    menu and the frontend ``auto_anchor_id``). When None/unknown, every
    existing SRJ on ``from_track`` is tried earliest-first (legacy
    closest behaviour). With no SRJ on the line (or every anchor spot
    blocked): random free sampling across ``from_track`` avoiding
    restricted regions -- up to 200 random tries, then a 5 m systematic
    scan.

    Returns (chainage, explanation). Raises ValueError when nothing
    validates (caller falls back to manual input).
    """
    reqs, resolved, params_by_id = _accepted_main_params(
        accepted, tracks, extents)
    all_anchors = main_track_anchors(reqs, resolved, params_by_id, from_track)
    # Explicit anchor first (user-chosen C-id): only its SRJ(s) on
    # from_track are tried ahead/behind; the rest follow as fallback so
    # a blocked chosen spot can still resolve elsewhere.
    ordered_anchors: list[dict] = list(all_anchors)
    if anchor_id is not None:
        chosen = [a for a in all_anchors
                  if str(a.get("id")) == str(anchor_id)]
        rest = [a for a in all_anchors
                if str(a.get("id")) != str(anchor_id)]
        if chosen:
            ordered_anchors = chosen + rest
    anchors = ordered_anchors
    placement = "BEHIND" if normalize_direction(direction) == "REVERSE" else "AHEAD"
    span_lo, span_hi = _track_search_span(
        from_track, tracks, extents, main_length)

    def _try_candidate(cand: float):
        spec = CrossoverSpec(
            from_track=from_track, to_track=to_track,
            from_chainage_m=float(cand), to_chainage_m=None,
            turnout=turnout, placement=placement, id=cid,
            direction=direction, position_mode="FIXED",
        )
        return _validate_candidate_live(
            spec, accepted, tracks, extents, main_length, restrictions)

    if anchors:
        for cand_info in auto_candidates_for_main(direction, anchors):
            cand = float(cand_info["candidate"])
            if not (span_lo - 1e-3 <= cand <= span_hi + 1e-3):
                continue
            valid, _msg = _try_candidate(cand)
            if valid:
                chosen_txt = (
                    f"anchored to {anchor_id} "
                    if anchor_id is not None and
                    str(cand_info['anchor_id']) == str(anchor_id)
                    else "")
                expl = (
                    f"AUTO {chosen_txt}: {cand_info['anchor_id']} "
                    f"{cand_info['anchor_kind']} on {from_track} at "
                    f"{cand_info['anchor_pos']:.2f} m "
                    f"({cand_info['anchor_direction']}) vs new {direction}: "
                    f"required {cand_info['required']:.0f} m (13 same / 54 opposite) "
                    f"-> START {cand:.2f} m ({cand_info['side']})."
                )
                return float(cand), expl

    # --- random fallback: no SRJ on the line yet, or all blocked --
    rng = rng or random
    hi = float(span_hi)
    lo = float(span_lo)
    tried = 0
    for _ in range(200):
        cand = rng.uniform(lo, max(lo + 1.0, hi))
        tried += 1
        valid, _msg = _try_candidate(float(cand))
        if valid:
            expl = (
                f"AUTO: no usable anchor on {from_track} "
                f"({len(all_anchors)} SRJ(s), all blocked or none yet) -- "
                f"random free location {float(cand):.2f} m avoiding "
                f"restricted regions (try {tried})."
            )
            return float(cand), expl
    step = 5.0
    cand = lo
    while cand <= hi + 1e-9:
        valid, _msg = _try_candidate(float(cand))
        if valid:
            return float(cand), (
                f"AUTO: random search found no gap -- systematic scan "
                f"location {float(cand):.2f} m avoiding restricted regions.")
        cand += step
    raise ValueError(
        f"AUTO on {from_track}: no valid start found (tried "
        f"{len(auto_candidates_for_main(direction, anchors))} anchor "
        f"candidate(s) + 200 random + scan). Give a manual chainage.")


#: Backwards-compatible alias (previous MAIN_LINE-centric name).
_resolve_main_auto_start = _resolve_auto_start
