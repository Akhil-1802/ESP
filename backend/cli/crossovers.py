"""Crossover wizard: DEFAULT/MANUAL prompts with live validation."""

from __future__ import annotations

import math
from typing import Any

from cli.base import (
    UserAbort,
    ask,
    ask_choice,
    ask_count,
    polyline_length,
)
from cli.crossover_checks import (
    _accepted_main_params,
    _ask_auto_anchor,
    _blocked_suffix,
    _resolve_auto_start,
    _validate_candidate_live,
)
from track.crossover.defaults import (
    compute_default_chainages,
    infer_target_track,
)
from track.crossover.turnout import turnout_angle_f_rad
from track.specs import CrossoverSpec
from track.turnouts import select_turnout


def _ask_crossover_start(from_track: str, start_ranges: dict | None,
                         blocked: list | None = None, full_range: tuple[float, float] | None = None):
    """Ask for one explicit start chainage (MAIN datum, never AUTO).

    The allowed range on a bounded loop is the loop's defined [C1, C2]
    (turnout to turnout) -- overrun extensions are NOT included: the
    overrun is dead-end track past the loop turnouts, not a place to
    start a crossover. (The engine still allows the calculated second
    SRJ to land in an overrun.) On other tracks the full [0, N] MAIN
    extent is shown. ``blocked`` lists (start, end, reason) MAIN-datum
    intervals on this track covered by platforms/stations: a turnout
    can never start inside one, so such values are re-asked here.
    Invalid values are re-asked here; a start chainage is never moved,
    derived, or defaulted.

    Exception: on any track (MAIN_LINE, MAIN_LINE_N, loops, ...) the
    user may type AUTO instead of a number. The caller resolves it AFTER
    the direction is known: exactly 13 m past the closest SRJ on the
    starting line when the directions match, 54 m when opposite; with
    no SRJ on that line yet, a random free location on that same line
    avoiding restricted regions (platforms / stations). When prior
    crossovers exist the caller first asks WHICH crossover to anchor to
    (C1..CN listed with their points on this line).
    """
    extent = (start_ranges or {}).get(from_track)
    blocked_list = list(blocked or [])
    allow_auto = True
    while True:
        if extent is None:
            if full_range is not None:
                raw = ask(
                    f"  Start chainage on {from_track} "
                    f"(MAIN m {full_range[0]:.0f}-{full_range[1]:.0f}"
                    f"{_blocked_suffix(blocked_list)})"
                    + (" or AUTO" if allow_auto else ""))
            else:
                raw = ask("  Start chainage (m)" + (" or AUTO" if allow_auto else ""))
        else:
            raw = ask(
                f"  Start chainage on {from_track} "
                f"(MAIN m {extent[0]:.3f}-{extent[1]:.3f}"
                f"{_blocked_suffix(blocked_list)})"
                + (" or AUTO" if allow_auto else ""))
        if allow_auto and raw.strip().upper() == "AUTO":
            return "AUTO"
        try:
            value = float(raw)
        except ValueError:
            print("Enter a chainage in metres" + (" or AUTO" if allow_auto else "") + ".")
            continue
        if extent is not None and not (
                extent[0] - 1e-3 <= value <= extent[1] + 1e-3):
            print(f"Enter a MAIN chainage between {extent[0]:.3f} "
                  f"and {extent[1]:.3f}.")
            continue
        if value < 0:
            print("Chainage must be >= 0.")
            continue
        hit = None
        for b0, b1, reason in blocked_list:
            if b0 - 1e-3 <= value <= b1 + 1e-3:
                hit = (b0, b1, reason)
                break
        if hit is not None:
            b0, b1, reason = hit
            print(f"Chainage {value:.3f} m is inside {reason} "
                  f"[{b0:.3f}, {b1:.3f}] - no turnout can start there. "
                  f"Pick a chainage outside it.")
            continue
        return value


def _build_default_specs(
    turnout: Any,
    tracks: dict,
    extents: dict,
    start_ranges: dict | None,
    main_length: float,
    restrictions: list,
) -> tuple[list[CrossoverSpec], str]:
    """Build the DEFAULT 4-crossover layout (centre-ward, 54 m).

    C1 LOOP_1 C1 -> MAIN REVERSE, C2 LOOP_1 C2 -> MAIN FORWARD (C1/C2
    are the DEFINED turnouts -- overrun ignored), C3 MAIN -> LOOP_2
    FORWARD at E1 + 54, C4 MAIN -> LOOP_2 REVERSE at E2 - 54. Needs
    LOOP_1 and LOOP_2 (opposite sides of MAIN for the footprint
    clearance). Each candidate is validated in order; the first failure
    raises ValueError so the caller can fall back to MANUAL.
    """
    if "LOOP_1" not in tracks or "LOOP_2" not in tracks:
        raise ValueError("DEFAULT needs LOOP_1 and LOOP_2 tracks.")
    if "MAIN_LINE" not in tracks:
        raise ValueError("DEFAULT needs MAIN_LINE.")
    defined = start_ranges or {}
    if "LOOP_1" not in defined:
        raise ValueError("DEFAULT needs LOOP_1 defined [C1, C2] (no overrun).")
    c1_def, c2_def = float(defined["LOOP_1"][0]), float(defined["LOOP_1"][1])
    try:
        dd = compute_default_chainages(
            c1_def, c2_def, turnout, tracks,
            loop1="LOOP_1", loop2="LOOP_2", main="MAIN_LINE",
            extents=extents, main_length=main_length)
    except ValueError as exc:
        raise ValueError(f"DEFAULT layout does not fit: {exc}") from exc
    plan = [
        ("C1", "LOOP_1", "MAIN_LINE", dd["c1"], "REVERSE", "BEHIND"),
        ("C2", "LOOP_1", "MAIN_LINE", dd["c2"], "FORWARD", "AHEAD"),
        ("C3", "MAIN_LINE", "LOOP_2", dd["c3"], "FORWARD", "AHEAD"),
        ("C4", "MAIN_LINE", "LOOP_2", dd["c4"], "REVERSE", "BEHIND"),
    ]
    specs: list[CrossoverSpec] = []
    for cid, fr, to, ch, direction, placement in plan:
        spec = CrossoverSpec(
            from_track=fr, to_track=to, from_chainage_m=float(ch),
            to_chainage_m=None, turnout=turnout, placement=placement,
            id=cid, direction=direction, position_mode="FIXED")
        valid, message = _validate_candidate_live(
            spec, specs, tracks, extents, main_length, restrictions)
        print(message)
        if not valid:
            raise ValueError(
                f"DEFAULT {cid} invalid -- falling back to MANUAL.\n{message}")
        specs.append(spec)
    summary = (
        f"DEFAULT 4-crossover layout ({turnout.designation}): "
        f"LOOP_1 [{c1_def:.2f}, {c2_def:.2f}] (defined, overrun ignored); "
        f"C1 {dd['c1']:.2f}->E1 {dd['e1']:.2f} (OL {dd['ol1_m']:.2f}); "
        f"C2 {dd['c2']:.2f}->E2 {dd['e2']:.2f} (OL {dd['ol2_m']:.2f}); "
        f"C3 MAIN {dd['c3']:.2f} (E1+{dd['required_m']:.0f}) FORWARD; "
        f"C4 MAIN {dd['c4']:.2f} (E2-{dd['required_m']:.0f}) REVERSE.")
    return specs, summary


def _ask_retry_chainage(from_track: str | None = None):
    """Ask for a replacement start chainage (range and conflicts are
    judged by the engine so the reason stays exact). AUTO may be typed
    to re-resolve (13/54 m snap from the chosen anchor, or random free)."""
    while True:
        raw = ask("Enter a new start chainage or AUTO")
        if raw.strip().upper() == "AUTO":
            return "AUTO"
        try:
            value = float(raw)
        except ValueError:
            print("Enter a chainage in metres or AUTO.")
            continue
        if value < 0:
            print("Chainage must be >= 0.")
            continue
        return value


def _ask_crossovers_live(
    track_names: list[str],
    tracks: dict,
    loop_extents: dict[str, tuple[float, float]] | None = None,
    track_metas: list[tuple] | None = None,
    main_length: float | None = None,
    restrictions: list | None = None,
    start_ranges: dict[str, tuple[float, float]] | None = None,
) -> list[CrossoverSpec]:
    """Step 4: ask about crossovers with immediate calculate+validate+retry."""
    print("\nCrossover Configuration")
    print("Only FROM track, TO track, START chainage, direction and turnout are asked.")
    print("Any parallel track may connect to any other (LOOP-LOOP allowed).")
    print("The endpoint is calculated by the engine, never asked.")
    print("  FORWARD (->): increasing chainage, second SRJ at START + OL.")
    print("  REVERSE (<-): decreasing chainage, second SRJ at START - OL.")
    print("  Spacing 13 m (same) / 54 m (opposite): nearest SRJs on the SHARED line.")
    print("  START may be AUTO (anchor to a prior crossover: 13/54 m snap, else random free).")
    print("All chainages are MAIN_LINE chainages (m).")
    print("=" * 50)

    extents = loop_extents or {}
    metas = track_metas or [(name, None, None) for name in track_names]
    restrictions_list = restrictions or []
    ranges = start_ranges if start_ranges is not None else extents

    blocked_by_track: dict[str, list] = {}
    for region in restrictions_list:
        track = getattr(region, "track", None)
        try:
            b0 = min(float(region.start_chainage), float(region.end_chainage))
            b1 = max(float(region.start_chainage), float(region.end_chainage))
        except (TypeError, ValueError):
            continue
        blocked_by_track.setdefault(track, []).append(
            (b0, b1, str(getattr(region, "reason", "restricted region"))))
    for blocked in blocked_by_track.values():
        blocked.sort()
    full_by_track: dict[str, tuple[float, float]] = {}
    for name in track_names:
        if name in extents:
            full_by_track[name] = (float(extents[name][0]),
                                   float(extents[name][1]))
        elif main_length is not None:
            full_by_track[name] = (0.0, float(main_length))
        elif name in tracks:
            full_by_track[name] = (0.0, polyline_length(tracks[name]))

    if len(track_names) < 2:
        print("Need at least two tracks for a crossover - skipping.")
        return []

    specs: list[CrossoverSpec] = []
    total = ask_count("Number of crossovers", 0)
    if total == 4 and "LOOP_1" in track_names and "LOOP_2" in track_names:
        mode = ask_choice("  4 crossovers: DEFAULT layout or MANUAL input",
                          ["DEFAULT", "MANUAL"], "DEFAULT")
        if mode == "DEFAULT":
            turnout_choice = ask_choice("  Turnout for all 4 crossovers",
                                        ["1:8.5", "1:12"], "1:12")
            turnout = select_turnout(turnout_choice)
            try:
                default_specs, summary = _build_default_specs(
                    turnout, tracks, extents, ranges,
                    main_length if main_length is not None else 0.0,
                    restrictions_list)
                print(f"  {summary}")
                print(f"\n  Accepted {len(default_specs)} crossover(s): "
                      + ", ".join(s.id for s in default_specs))
                return default_specs
            except ValueError as exc:
                print(f"  DEFAULT failed: {exc}")
                print("  Falling back to MANUAL input.")
    while len(specs) < total:
        cid = f"C{len(specs) + 1}"
        print(f"\nCROSSOVER {len(specs) + 1} [{cid}]")
        print("-------------------------")
        default_from = next(
            (m[0] for m in metas
             if m[0] != "MAIN_LINE" and not m[0].startswith("MAIN_LINE")),
            track_names[0],
        )
        from_track = ask_choice("  From track", track_names, default_from)
        try:
            suggested_to = infer_target_track(from_track, metas)
        except ValueError:
            suggested_to = None
        to_choices = [name for name in track_names if name != from_track]
        to_track = ask_choice("  To track", to_choices, suggested_to)
        start = _ask_crossover_start(
            from_track, ranges, blocked_by_track.get(from_track, []),
            full_by_track.get(from_track))
        direction = ask_choice(
            "  Direction (FORWARD=-> ahead, REVERSE=<- behind)",
            ["FORWARD", "REVERSE"], "FORWARD")
        turnout_choice = ask_choice("  Turnout", ["1:8.5", "1:12"], "1:12")
        turnout = select_turnout(turnout_choice)
        print(f"  Turnout {turnout.designation}: F = atan(1/N) = "
              f"{math.degrees(turnout_angle_f_rad(turnout)):.4f} deg "
              f"(endpoint calculated, not asked)")
        placement = "AHEAD" if direction == "FORWARD" else "BEHIND"

        auto_anchor_id: str | None = None

        def _ensure_anchor() -> None:
            nonlocal auto_anchor_id
            if not specs:
                auto_anchor_id = None
                return
            valid_ids = {str(getattr(s, "id", "")) for s in specs}
            if auto_anchor_id not in valid_ids:
                auto_anchor_id = _ask_auto_anchor(
                    from_track, direction, specs, tracks, extents)

        def _maybe_resolve_auto(value: Any):
            """Resolve an AUTO marker via the chosen anchor (or raise)."""
            if not (isinstance(value, str) and value.strip().upper() == "AUTO"):
                return float(value)
            _ensure_anchor()
            resolved, expl = _resolve_auto_start(
                from_track, to_track, direction, turnout, specs,
                tracks, extents,
                main_length if main_length is not None else 0.0,
                restrictions_list, cid=cid, anchor_id=auto_anchor_id)
            print(f"  {expl}")
            return float(resolved)

        try:
            start = _maybe_resolve_auto(start)
        except ValueError as exc:
            print(f"\u274c Crossover {cid} AUTO failed\n  {exc}")
            start = _ask_retry_chainage(from_track)
            auto_anchor_id = None

        fails = 0
        while True:
            if isinstance(start, str) and start.strip().upper() == "AUTO":
                try:
                    start = _maybe_resolve_auto(start)
                except ValueError as exc:
                    print(f"\u274c Crossover {cid} AUTO failed\n  {exc}")
                    fails += 1
                    if fails % 3 == 0:
                        action = ask_choice(
                            "  Action (RETRY new chainage / RESTART this crossover "
                            "/ SKIP it / ABORT)",
                            ["RETRY", "RESTART", "SKIP", "ABORT"], "RETRY")
                        if action == "ABORT":
                            raise UserAbort(
                                "Crossover input aborted by the user.")
                        if action == "SKIP":
                            total -= 1
                            break
                        if action == "RESTART":
                            break
                    start = _ask_retry_chainage(from_track)
                    auto_anchor_id = None
                    continue
            spec = CrossoverSpec(
                from_track=from_track,
                to_track=to_track,
                from_chainage_m=start,
                to_chainage_m=None,
                turnout=turnout,
                placement=placement,
                id=cid,
                direction=direction,
                position_mode="FIXED",
                auto_anchor_id=auto_anchor_id,
            )
            print("Calculating crossover...")
            valid, message = _validate_candidate_live(
                spec, specs, tracks, extents,
                main_length if main_length is not None else 0.0,
                restrictions_list)
            print(message)
            if valid:
                specs.append(spec)
                break
            fails += 1
            if fails % 3 == 0:
                action = ask_choice(
                    "  Action (RETRY new chainage / RESTART this crossover "
                    "/ SKIP it / ABORT)",
                    ["RETRY", "RESTART", "SKIP", "ABORT"], "RETRY")
                if action == "ABORT":
                    raise UserAbort(
                        "Crossover input aborted by the user.")
                if action == "SKIP":
                    total -= 1
                    break
                if action == "RESTART":
                    break
            start = _ask_retry_chainage(from_track)
            auto_anchor_id = None

    if specs:
        print(f"\n  Accepted {len(specs)} crossover(s): "
              + ", ".join(s.id for s in specs))
    return specs
