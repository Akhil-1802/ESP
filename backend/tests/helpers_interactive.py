"""Shared helpers and fixtures for interactive crossover tests."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from platform_gen.config import PlatformConfig
from track.crossover.conflicts import platforms_to_restricted_regions
from track.crossover.models import CrossoverRequest
from track.crossover.planner import CrossoverPlanner
from track.turnouts import select_turnout

OL_12_53 = 97.578  # 1:12 at 5.3 m: 5300*12 + 2*16989 mm


def straight_tracks(length: float = 2000.0, tc: float = 5.3, step: float = 10.0):
    main, loop1, loop2 = [], [], []
    x = 0.0
    while x <= length + 1e-9:
        main.append((x, 0.0))
        loop1.append((x, tc))
        loop2.append((x, -tc))
        x += step
    return {"MAIN_LINE": main, "LOOP_1": loop1, "LOOP_2": loop2}


def mk(cid, fr, to, ch, direction="FORWARD", turnout="1:12", placement=None):
    return CrossoverRequest(
        id=cid, from_track=fr, to_track=to, chainage=ch,
        direction=direction, turnout=select_turnout(turnout),
        placement=placement,
        position_mode="AUTO" if ch is None else "FIXED",
    )


def plan_ok(requests, tracks, extents=None):
    planner = CrossoverPlanner(tracks, extents or {}, None)
    return planner.plan(requests)


def main_platform_config(**over):
    kw = dict(source_dxf="s.dxf", output_dxf="o.dxf",
              track_layer="MAIN_LINE", platform_length=550.0)
    kw.update(over)
    return PlatformConfig(**kw)


def _main_platform_regions():
    tracks = straight_tracks()
    main = tracks["MAIN_LINE"]
    req = SimpleNamespace(
        track_layer="MAIN_LINE",
        config=main_platform_config(),
    )
    regions = platforms_to_restricted_regions(
        [req], {"MAIN_LINE": main}, {})
    assert len(regions) == 1
    assert regions[0].start_chainage == pytest.approx(725.0)
    assert regions[0].end_chainage == pytest.approx(1275.0)
    return regions
