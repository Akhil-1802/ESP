"""Siding wizard."""

from __future__ import annotations

from cli.base import (
    ask,
    ask_choice,
    ask_count,
    ask_positive,
)
from track.specs import SidingSpec


def _ask_siding_start(source_track: str, extent: tuple[float, float] | None) -> float:
    """Ask one siding start chainage (MAIN datum) within ``extent``.

    ``extent`` is the (lo, hi) MAIN-datum track extent, or None when
    unknown (plain prompt, generation still validates strictly).
    """
    while True:
        if extent is None:
            raw = ask("  Start chainage (MAIN m)")
        else:
            raw = ask(
                f"  Start chainage on {source_track} "
                f"(MAIN m {extent[0]:.0f}-{extent[1]:.0f})")
        try:
            value = float(raw)
        except ValueError:
            print("Enter a chainage in metres.")
            continue
        if extent is not None and not (
                extent[0] - 1e-3 <= value <= extent[1] + 1e-3):
            print(f"Enter a MAIN chainage between {extent[0]:.0f} "
                  f"and {extent[1]:.0f}.")
            continue
        if value < 0:
            print("Chainage must be >= 0.")
            continue
        return value


def _ask_sidings(track_names: list[str], main_center: float | None = None,
                 loop_extents: dict | None = None) -> list[SidingSpec]:
    """Dead-end sidings, asked right after the track setup: no live geometry.

    Only the source track, start chainage, direction, side, turnout and
    clear standing length are asked. The start prompt always shows the
    source track's MAIN-datum extent. Platform clearance cannot be
    checked here (platforms are defined later) -- it is validated
    strictly at generation instead. The ladder geometry, endpoint and
    dead end are calculated at generation; conflicts raise instead of
    moving or shortening anything.
    """
    print("\nDead-End Siding Configuration")
    print("=" * 50)
    print("No end chainage is asked: the siding runs out through one")
    print("turnout, holds the clear standing length parallel, then ends")
    print("in a dead end (never back to any line).")
    print("Platform clearance is validated at generation (platforms are")
    print("defined after this step).")
    total = 2.0 * float(main_center) if main_center else None
    extents = loop_extents or {}
    sidings: list[SidingSpec] = []
    for number in range(1, ask_count("Number of sidings") + 1):
        print(f"\nSiding {number}")
        source = ask_choice("  Source track", track_names, "MAIN_LINE")
        if source in extents:
            extent = (float(extents[source][0]), float(extents[source][1]))
        elif total:
            extent = (0.0, total)
        else:
            extent = None
        sidings.append(SidingSpec(
            source_track=source,
            start_chainage_m=_ask_siding_start(source, extent),
            direction=ask_choice("  Direction", ["FORWARD", "REVERSE"], "FORWARD"),
            side=ask_choice("  Side", ["LEFT", "RIGHT"], "LEFT"),
            turnout_designation=ask_choice("  Turnout", ["1:8.5", "1:12"], "1:8.5"),
            standing_length_m=ask_positive("  Clear standing length (m)", 120.0),
            id=f"S{number}",
        ))
    return sidings
