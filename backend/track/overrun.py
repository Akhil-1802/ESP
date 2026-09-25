"""SRJ-anchored loop overruns (single definition).

A bounded loop's *running* line ends at the outermost crossover SRJ
found strictly inside either loop end -- even a few metres inside the
defined [C1, C2] turnout points. The cut-off outer piece is not loop
line anymore: it is drawn as an OVER RUN LINE (dead-end marker at the
outer tip + ``OVER RUN LINE, CAL=xx.xx`` label), exactly like the
configured overrun extensions.

By default the search covers a half-loop (375 m of a 750 m loop:
centre -> tip), so a crossover placed before the 375 m tip ends the
running line there and the remainder to the tip becomes overrun --
on each side independently (``(C1, centre]`` for the START side,
``[centre, C2)`` for the END side). An SRJ exactly at C1/C2 (the
normal turnout point, e.g. the DEFAULT preset) never triggers.
A single mid-loop SRJ that would collapse the running line to ~zero
(``cut_start >= cut_end``) is ignored so mid-loop crossovers keep the
previous turnout-to-turnout behaviour.
Cut-off stubs shorter than ``LOOP_SRJ_OVERRUN_MIN_STUB_M`` are ignored
so an SRJ sitting ~at the turnout point changes nothing.

Chainages here are MAIN-datum metres, matching the crossover engine
(``CrossoverResult.chainage`` / ``start_chainage`` / ``end_chainage``)
and the loop specs. Loop polylines are addressed by local arclength
(main chainage minus the loop's effective start), the same convention
as the crossover drawing (``_local``) and the overrun midpoint helper.
"""

from __future__ import annotations

import math
from typing import Sequence

from common.constants import (
    LOOP_SRJ_OVERRUN_MIN_STUB_M,
    LOOP_SRJ_OVERRUN_SEARCH_M,
)
from common.geometry import Point

__all__ = [
    "LOOP_SRJ_OVERRUN_MIN_STUB_M",
    "LOOP_SRJ_OVERRUN_SEARCH_M",
    "crossover_srjs_on_track",
    "loop_end_srj_cuts",
    "slice_polyline",
    "split_loop_for_overrun",
]


def crossover_srjs_on_track(results, track: str) -> list[float]:
    """Sorted MAIN-datum chainages of accepted crossover SRJs on ``track``.

    Mirrors the siding step's legacy rule: the START SRJ for
    ``from_track`` (``chainage``), and the second SRJ for ``to_track``
    (``end_chainage`` for AHEAD placement, ``start_chainage`` for
    BEHIND).
    """
    chainages: list[float] = []
    for res in results or []:
        if getattr(res, "from_track", None) == track:
            try:
                chainages.append(float(res.chainage))
            except (TypeError, ValueError):
                continue
        if getattr(res, "to_track", None) == track:
            second = (
                res.end_chainage
                if getattr(res, "placement", None) == "AHEAD"
                else res.start_chainage
            )
            try:
                chainages.append(float(second))
            except (TypeError, ValueError):
                continue
    return sorted(chainages)


def loop_end_srj_cuts(
    c1: float,
    c2: float,
    srj_chainages: Sequence[float],
    window_m: float | None = None,
) -> tuple[float | None, float | None]:
    """Outermost in-window SRJ per loop end, or ``None`` when no cut.

    Returns ``(cut_start, cut_end)`` in MAIN-datum metres: the smallest
    SRJ strictly inside ``(c1, c1 + window]`` and the largest SRJ
    strictly inside ``[c2 - window, c2)``. An SRJ exactly at C1/C2 (the
    normal turnout point, e.g. the DEFAULT preset) never triggers, and
    neither do mid-loop SRJs outside the windows.

    ``window_m`` defaults to half the loop length ``(c2 - c1) / 2``
    (375 m for a standard 750 m loop: centre -> tip on each side), so
    any crossover before the tip ends the running line there. An
    explicit window (e.g. ``LOOP_SRJ_OVERRUN_SEARCH_M``) is honoured
    when given. Outer pieces shorter than
    ``LOOP_SRJ_OVERRUN_MIN_STUB_M`` are ignored, and a pair that would
    collapse the running line (``cut_start >= cut_end``) returns
    ``(None, None)``.
    """
    c1 = float(c1)
    c2 = float(c2)
    if c2 <= c1:
        return None, None
    if window_m is None:
        window_m = (c2 - c1) / 2.0
    else:
        window_m = float(window_m)
        if window_m <= 0:
            return None, None
        window_m = min(window_m, (c2 - c1) / 2.0)
    cut_start: float | None = None
    cut_end: float | None = None
    for chainage in srj_chainages:
        try:
            ch = float(chainage)
        except (TypeError, ValueError):
            continue
        if c1 < ch <= c1 + window_m:
            if cut_start is None or ch < cut_start:
                cut_start = ch
        if c2 - window_m <= ch < c2:
            if cut_end is None or ch > cut_end:
                cut_end = ch
    if cut_start is not None and (cut_start - c1) < LOOP_SRJ_OVERRUN_MIN_STUB_M:
        cut_start = None
    if cut_end is not None and (c2 - cut_end) < LOOP_SRJ_OVERRUN_MIN_STUB_M:
        cut_end = None
    if cut_start is not None and cut_end is not None:
        if cut_end - cut_start < LOOP_SRJ_OVERRUN_MIN_STUB_M:
            return None, None
    return cut_start, cut_end


def slice_polyline(
    points: Sequence[Point],
    start_dist: float,
    end_dist: float,
) -> list[Point]:
    """Centreline subset between arclengths ``[start_dist, end_dist]``.

    Distances are clamped to ``[0, total]``; endpoints are interpolated
    onto segments so the cut point belongs to both neighbours. An empty
    or inverted range returns the nearest single point (never empty).
    """
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 2:
        return list(pts)
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    total = sum(lengths)
    start = min(max(float(start_dist), 0.0), total)
    end = min(max(float(end_dist), 0.0), total)
    if end < start:
        start, end = end, start

    def _at(dist: float) -> tuple[Point, int]:
        travelled = 0.0
        for i, (first, second, length) in enumerate(zip(pts, pts[1:], lengths)):
            if travelled + length >= dist:
                ratio = (dist - travelled) / (length or 1.0)
                return (
                    (
                        first[0] + ratio * (second[0] - first[0]),
                        first[1] + ratio * (second[1] - first[1]),
                    ),
                    i,
                )
            travelled += length
        return pts[-1], len(pts) - 2

    start_pt, start_idx = _at(start)
    end_pt, end_idx = _at(end)
    if start_idx == end_idx:
        return [start_pt, end_pt]
    return [start_pt] + pts[start_idx + 1 : end_idx + 1] + [end_pt]


def split_loop_for_overrun(
    loop_points: Sequence[Point],
    eff_start: float,
    cut_start_main: float | None,
    cut_end_main: float | None,
) -> tuple[list[Point], list[Point] | None, list[Point] | None]:
    """Split a loop centreline into running line + overrun stubs.

    ``eff_start`` is the loop's effective-start MAIN chainage (C1 minus
    any configured start overrun); local arclengths are MAIN minus
    ``eff_start``. Returns ``(running, start_stub, end_stub)`` where a
    stub is ``None`` when that end has no cut. Both the running line
    and the adjacent stub contain the shared cut point.
    """
    pts = [(float(p[0]), float(p[1])) for p in loop_points]
    total = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    start_local = cut_start_main - eff_start if cut_start_main is not None else 0.0
    end_local = cut_end_main - eff_start if cut_end_main is not None else total
    start_local = min(max(start_local, 0.0), total)
    end_local = min(max(end_local, 0.0), total)
    running = slice_polyline(pts, start_local, end_local)
    start_stub = slice_polyline(pts, 0.0, start_local) if start_local > 0.0 else None
    end_stub = slice_polyline(pts, end_local, total) if end_local < total else None
    return running, start_stub, end_stub
