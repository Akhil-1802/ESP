"""Shared track geometry and helpers for crossover tests."""

from __future__ import annotations

import math

from common.geometry import offset_point, point_at_chainage, polyline_length
from track.crossover.models import CrossoverRequest
from track.crossover.planner import CrossoverPlanner
from track.turnouts import select_turnout


def straight_tracks(length: float = 2000.0, tc: float = 5.3, step: float = 10.0):
    main, loop1, loop2 = [], [], []
    x = 0.0
    while x <= length + 1e-9:
        main.append((x, 0.0))
        loop1.append((x, tc))
        loop2.append((x, -tc))
        x += step
    return {"MAIN_LINE": main, "LOOP_1": loop1, "LOOP_2": loop2}


def rotated_tracks(length: float = 2000.0, tc: float = 5.3,
                   angle_deg: float = 30.0, step: float = 10.0):
    """MAIN rotated by angle_deg; LOOP offset along the local normal."""
    ang = math.radians(angle_deg)
    ux, uy = math.cos(ang), math.sin(ang)
    nx, ny = -uy, ux
    tracks = {"MAIN_LINE": [], "LOOP_1": []}
    d = 0.0
    while d <= length + 1e-9:
        mx, my = ux * d, uy * d
        tracks["MAIN_LINE"].append((mx, my))
        tracks["LOOP_1"].append((mx + nx * tc, my + ny * tc))
        d += step
    return tracks


def curved_tracks(length: float = 2000.0, tc: float = 5.3, step: float = 10.0):
    """Gently curved MAIN (circular arc R=1500m); LOOP via local offsets."""
    R = 1500.0
    main = []
    d = 0.0
    while d <= length + 1e-9:
        theta = d / R
        main.append((R * math.sin(theta), R * (1.0 - math.cos(theta))))
        d += step
    total = polyline_length(main)
    loop = []
    d = 0.0
    while d <= total + 1e-9:
        sp = point_at_chainage(main, min(d, total))
        loop.append(offset_point(sp, tc, "LEFT"))
        d += step
    return {"MAIN_LINE": main, "LOOP_1": loop}


def req(cid, fr, to, ch, direction="FORWARD", turnout="1:12", placement="AHEAD"):
    return CrossoverRequest(
        id=cid, from_track=fr, to_track=to, chainage=ch,
        direction=direction, turnout=select_turnout(turnout),
        placement=placement,
        position_mode="AUTO" if ch is None else "FIXED",
    )


def plan_ok(requests, tracks, extents=None):
    planner = CrossoverPlanner(tracks, extents or {}, None)
    results, report = planner.plan(requests)
    return results, report
