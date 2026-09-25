"""Track wizards: MAIN/LOOP/PROPOSED prompts + loop extensions."""

from __future__ import annotations

from cli.base import (
    ask_choice,
    ask_count,
    ask_nonnegative,
    ask_track_spacing,
)
from track.specs import LineSpec, LoopSpec


def _ask_tracks(main_center: float) -> tuple[list[LineSpec], list[LoopSpec], list[LineSpec | LoopSpec], dict[str, str]]:
    """Step 1: ask about every track (MAIN_LINES, LOOPs, PROPOSED lines).

    Loops are always 750m, centred on the MAIN midpoint: no start/end
    prompts - C1 = centre - 375m, C2 = centre + 375m. With several MAIN
    lines, each is designated UP or DN (UP = +chainage).

    Returns:
        additional_main_lines: full-length MAIN_LINE_N offsets from MAIN_LINE
        loops: bounded LOOP_N definitions
        additional: PROPOSED lines + PROPOSED LOOP lines
        main_directions: MAIN track name -> UP / DN ({} = single line)
    """
    print("\nTrack Configuration")
    print("=" * 50)

    # --- additional MAIN lines ---
    additional_main_lines: list[LineSpec] = []
    for number in range(1, ask_count("Number of additional MAIN lines") + 1):
        additional_main_lines.append(LineSpec(
            f"MAIN_LINE_{number}",
            ask_track_spacing(f"  MAIN_LINE_{number} distance from MAIN_LINE (m)"),
            ask_choice(f"  MAIN_LINE_{number} side", ["LEFT", "RIGHT"], "LEFT"),
        ))

    # --- LOOP lines (fixed 750m, centred) ---
    loops: list[LoopSpec] = []
    for number in range(1, ask_count("Number of LOOP lines") + 1):
        spacing = ask_track_spacing(f"  LOOP_{number} distance from MAIN_LINE (m)")
        side = ask_choice(f"  LOOP_{number} side", ["LEFT", "RIGHT"], "LEFT")
        first_ch, second_ch = main_center - 375.0, main_center + 375.0
        print(f"  LOOP_{number}: [{first_ch:.0f}, {second_ch:.0f}] MAIN m (750m centred)")
        loops.append(LoopSpec(
            f"LOOP_{number}",
            spacing,
            side,
            first_crossover_chainage=first_ch,
            second_crossover_chainage=second_ch,
        ))

    # --- PROPOSED + PROPOSED LOOP lines ---
    additional: list[LineSpec | LoopSpec] = []
    for label, prefix in (("PROPOSED lines", "PROPOSED_LINE"), ("PROPOSED LOOP lines", "PROPOSED_LOOP_LINE")):
        count = ask_count(f"Number of {label}")
        for number in range(1, count + 1):
            spacing = ask_track_spacing(f"  {prefix}_{number} distance from MAIN_LINE (m)")
            side = ask_choice(f"  {prefix}_{number} side", ["LEFT", "RIGHT"], "LEFT")
            if "LOOP" in prefix:
                first_ch, second_ch = main_center - 375.0, main_center + 375.0
                print(f"  {prefix}_{number}: [{first_ch:.0f}, {second_ch:.0f}] MAIN m (750m centred)")
                additional.append(LoopSpec(
                    f"{prefix}_{number}", spacing, side,
                    first_crossover_chainage=first_ch,
                    second_crossover_chainage=second_ch,
                ))
            else:
                additional.append(LineSpec(f"{prefix}_{number}", spacing, side))

    main_directions: dict[str, str] = {}
    if additional_main_lines:
        main_directions["MAIN_LINE"] = ask_choice("  MAIN_LINE direction", ["UP", "DN"], "UP")
        opposite = "DN" if main_directions["MAIN_LINE"] == "UP" else "UP"
        for line in additional_main_lines:
            line.direction = ask_choice(f"  {line.name} direction", ["UP", "DN"], opposite)
            main_directions[line.name] = line.direction

    return additional_main_lines, loops, additional, main_directions


def _loop_extent_info(items) -> tuple[dict, dict]:
    """Effective extents + defined START ranges (MAIN m) from loop specs.

    Effective extent includes overruns ([C1-start, C2+end]); the START
    range is the defined turnout-to-turnout [C1, C2]. Single source for
    both the siding questions (asked early) and the crossover engine
    inputs (asked late).
    """
    extents: dict[str, tuple[float, float]] = {}
    ranges: dict[str, tuple[float, float]] = {}
    for item in items:
        c1 = getattr(item, "first_crossover_chainage", None)
        if c1 is None:
            continue
        c2 = getattr(item, "second_crossover_chainage", None)
        if c2 is None:
            c2 = c1 + getattr(item, "crossover_distance_m", 750.0)
        ranges[item.name] = (float(c1), float(c2))
        extents[item.name] = (
            float(c1) - (getattr(item, "extend_start_m", 0.0) or 0.0),
            float(c2) + (getattr(item, "extend_end_m", 0.0) or 0.0),
        )
    return extents, ranges


def _ask_loop_extensions(bounded_loops: list[LoopSpec]) -> None:
    """Ask, before crossover input, how far to extend each bounded loop
    past its turnouts (overrun). Sets extend_start_m / extend_end_m
    in place: extension length first (default 120m, 0 = none), then
    which side (START / END / BOTH). Final extents are needed to
    validate crossover chainages."""
    if not bounded_loops:
        return
    print("\nLoop Extension (overrun past the turnouts)")
    print("=" * 50)
    for loop in bounded_loops:
        ext = ask_nonnegative(f"  {loop.name} extension length (m, 0 = none)", 120.0)
        if ext <= 0:
            continue
        side = ask_choice(f"  Extend {loop.name} from", ["START", "END", "BOTH"], "BOTH")
        if side in ("START", "BOTH"):
            loop.extend_start_m = ext
        if side in ("END", "BOTH"):
            loop.extend_end_m = ext
        c2 = loop.second_crossover_chainage
        if c2 is None:
            c2 = loop.first_crossover_chainage + loop.crossover_distance_m
        print(f"  {loop.name}: [{loop.first_crossover_chainage - loop.extend_start_m:.0f}, "
              f"{c2 + loop.extend_end_m:.0f}] MAIN m")
