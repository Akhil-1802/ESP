"""MAIN_LINE AUTO snap + DEFAULT 4-crossover preset tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from cli.crossover_checks import _track_search_span
from cli.crossovers import _ask_crossovers_live
from config.loader import load_config_from_json
from track.crossover.defaults import (
    auto_candidates_for_main,
    compute_default_chainages,
    main_track_anchors,
)
from track.crossover.geometry import compute_crossover_params
from track.crossover.models import CrossoverRequest
from track.crossover.planner import CrossoverPlanner
from track.turnouts import select_turnout

OL_12_53 = 97.578  # 1:12 at 5.3 m


def straight_tracks(length: float = 2000.0, tc: float = 5.3, step: float = 10.0):
    main, loop1, loop2 = [], [], []
    x = 0.0
    while x <= length + 1e-9:
        main.append((x, 0.0))
        loop1.append((x, tc))
        loop2.append((x, -tc))
        x += step
    return {"MAIN_LINE": main, "LOOP_1": loop1, "LOOP_2": loop2}


def bounded_tracks(c1: float, c2: float, over: float = 120.0, length: float = 2000.0):
    main = [(float(x), 0.0) for x in range(0, int(length) + 1)]
    xs = []
    x = c1 - over
    while x <= c2 + over + 1e-9:
        xs.append(x)
        x += 5.0
    return {"MAIN_LINE": main,
            "LOOP_1": [(x, 5.3) for x in xs],
            "LOOP_2": [(x, -5.3) for x in xs]}


def req(cid, fr, to, ch, direction="FORWARD", turnout="1:12", placement=None):
    return CrossoverRequest(
        id=cid, from_track=fr, to_track=to, chainage=ch,
        direction=direction, turnout=select_turnout(turnout),
        placement=placement,
        position_mode="AUTO" if ch is None else "FIXED",
    )


def test_auto_candidates_opposite_54_same_13():
    anchors = [{"pos": 597.578, "direction": "FORWARD",
                "id": "C1", "kind": "ends"}]
    opp = auto_candidates_for_main("REVERSE", anchors)
    assert opp[0]["candidate"] == pytest.approx(597.578 + 54.0)
    assert opp[0]["required"] == pytest.approx(54.0)
    assert opp[0]["side"] == "AHEAD"
    same = auto_candidates_for_main("FORWARD", anchors)
    assert same[0]["candidate"] == pytest.approx(597.578 + 13.0)
    assert same[0]["required"] == pytest.approx(13.0)
    assert auto_candidates_for_main("FORWARD", []) == []


def test_main_track_anchors_collects_ends_and_starts():
    tracks = straight_tracks()
    r1 = req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD")
    resolved = {"C1": 500.0}
    params = {"C1": compute_crossover_params(r1, 500.0, tracks, {})}
    anchors = main_track_anchors([r1], resolved, params, "MAIN_LINE")
    assert len(anchors) == 1
    assert anchors[0]["kind"] == "ends"
    assert anchors[0]["pos"] == pytest.approx(500.0 + OL_12_53, abs=0.01)


def test_default_chainages_centre_ward():
    tracks = bounded_tracks(175.709, 925.709)
    ext = {"LOOP_1": (55.709, 1045.709), "LOOP_2": (55.709, 1045.709)}
    dd = compute_default_chainages(175.709, 925.709, select_turnout("1:12"),
                                   tracks, extents=ext, main_length=2000.0)
    assert dd["c1"] == pytest.approx(175.709)
    assert dd["c2"] == pytest.approx(925.709)
    assert dd["e1"] == pytest.approx(175.709 - OL_12_53, abs=0.05)
    assert dd["e2"] == pytest.approx(925.709 + OL_12_53, abs=0.05)
    assert dd["c3"] == pytest.approx(dd["e1"] + 54.0, abs=0.05)
    assert dd["c4"] == pytest.approx(dd["e2"] - 54.0, abs=0.05)


def test_default_layout_validates():
    tracks = bounded_tracks(175.709, 925.709)
    ext = {"LOOP_1": (55.709, 1045.709), "LOOP_2": (55.709, 1045.709)}
    to = select_turnout("1:12")
    dd = compute_default_chainages(175.709, 925.709, to, tracks,
                                   extents=ext, main_length=2000.0)
    reqs = [
        req("C1", "LOOP_1", "MAIN_LINE", dd["c1"], "REVERSE", placement="BEHIND"),
        req("C2", "LOOP_1", "MAIN_LINE", dd["c2"], "FORWARD", placement="AHEAD"),
        req("C3", "MAIN_LINE", "LOOP_2", dd["c3"], "FORWARD", placement="AHEAD"),
        req("C4", "MAIN_LINE", "LOOP_2", dd["c4"], "REVERSE", placement="BEHIND"),
    ]
    _results, report = CrossoverPlanner(tracks, ext, 2000.0).plan(reqs)
    assert report.overall_valid, report.errors
    gaps = sorted(c.actual_m for c in report.spacing_checks)
    assert gaps[0] == pytest.approx(54.0, abs=0.05)


def _live(names, tracks, extents, metas, inputs, ranges=None):
    answers = iter(inputs)
    with patch("builtins.input", lambda *a, **k: next(answers)):
        return _ask_crossovers_live(names, tracks, extents, metas, 2000.0,
                                    [], ranges)


def test_live_main_auto_snaps_54_opposite():
    tracks = straight_tracks()
    metas = [("MAIN_LINE", None, None), ("LOOP_2", 5.3, "RIGHT"),
             ("LOOP_1", 5.3, "LEFT")]
    specs = _live(["MAIN_LINE", "LOOP_1", "LOOP_2"], tracks, {}, metas,
                  ["2", "LOOP_1", "MAIN_LINE", "500", "FORWARD", "1:12",
                   "MAIN_LINE", "LOOP_2", "AUTO", "REVERSE", "1:12", "C1"])
    assert specs[1].from_chainage_m == pytest.approx(
        500.0 + OL_12_53 + 54.0, abs=0.05)


def test_live_main_auto_snaps_13_same():
    tracks = straight_tracks()
    metas = [("MAIN_LINE", None, None), ("LOOP_2", 5.3, "RIGHT"),
             ("LOOP_1", 5.3, "LEFT")]
    specs = _live(["MAIN_LINE", "LOOP_1", "LOOP_2"], tracks, {}, metas,
                  ["2", "LOOP_1", "MAIN_LINE", "500", "FORWARD", "1:12",
                   "MAIN_LINE", "LOOP_2", "AUTO", "FORWARD", "1:12", "C1"])
    assert specs[1].from_chainage_m == pytest.approx(
        500.0 + OL_12_53 + 13.0, abs=0.05)


def test_live_main_auto_anchor_choice():
    tracks = straight_tracks()
    metas = [("MAIN_LINE", None, None), ("LOOP_2", 5.3, "RIGHT"),
             ("LOOP_1", 5.3, "LEFT")]
    specs = _live(["MAIN_LINE", "LOOP_1", "LOOP_2"], tracks, {}, metas,
                  ["2", "LOOP_1", "MAIN_LINE", "175", "FORWARD", "1:12",
                   "MAIN_LINE", "LOOP_2", "AUTO", "REVERSE", "1:12", "C1"])
    assert specs[0].from_chainage_m == pytest.approx(175.0)
    assert specs[1].auto_anchor_id == "C1"
    assert specs[1].from_chainage_m == pytest.approx(
        175.0 + OL_12_53 + 54.0, abs=0.05)


def test_live_default_four(tmp_path):
    tracks = bounded_tracks(175.709, 925.709)
    metas = [("MAIN_LINE", None, None), ("LOOP_1", 5.3, "LEFT"),
             ("LOOP_2", 5.3, "RIGHT")]
    ranges = {"LOOP_1": (175.709, 925.709), "LOOP_2": (175.709, 925.709)}
    ext = {"LOOP_1": (55.709, 1045.709), "LOOP_2": (55.709, 1045.709)}
    specs = _live(["MAIN_LINE", "LOOP_1", "LOOP_2"], tracks, ext, metas,
                  ["4", "DEFAULT", "1:12"], ranges)
    assert [s.id for s in specs] == ["C1", "C2", "C3", "C4"]
    assert (specs[0].from_track, specs[0].direction) == ("LOOP_1", "REVERSE")
    assert (specs[1].from_track, specs[1].direction) == ("LOOP_1", "FORWARD")
    assert (specs[2].from_track, specs[2].direction) == ("MAIN_LINE", "FORWARD")
    assert (specs[3].from_track, specs[3].direction) == ("MAIN_LINE", "REVERSE")
    assert float(specs[2].from_chainage_m) == pytest.approx(
        175.709 - OL_12_53 + 54.0, abs=0.05)


def double_main_tracks(length: float = 2000.0, step: float = 10.0):
    main, main1, loop_in, loop_out = [], [], [], []
    x = 0.0
    while x <= length + 1e-9:
        main.append((x, 0.0))
        main1.append((x, 5.3))
        loop_in.append((x, 2.65))
        loop_out.append((x, 10.6))
        x += step
    return {"MAIN_LINE": main, "MAIN_LINE_1": main1,
            "LOOP_IN": loop_in, "LOOP_OUT": loop_out}


OL_12_265 = (2650.0 * 12.0 + 2.0 * 16989.0) / 1000.0  # 1:12 at 2.65 m


def test_live_second_main_auto_anchors_on_own_track():
    tracks = double_main_tracks()
    metas = [("MAIN_LINE", None, None), ("MAIN_LINE_1", 5.3, "LEFT"),
             ("LOOP_IN", 2.65, "RIGHT"), ("LOOP_OUT", 10.6, "LEFT")]
    specs = _live(
        ["MAIN_LINE", "MAIN_LINE_1", "LOOP_IN", "LOOP_OUT"],
        tracks, {}, metas,
        ["2", "LOOP_IN", "MAIN_LINE_1", "500", "FORWARD", "1:12",
         "MAIN_LINE_1", "LOOP_OUT", "AUTO", "REVERSE", "1:12", "C1"])
    assert specs[1].from_track == "MAIN_LINE_1"
    assert specs[1].auto_anchor_id == "C1"
    assert specs[1].from_chainage_m == pytest.approx(
        500.0 + OL_12_265 + 54.0, abs=0.05)


def test_planner_auto_second_main_uses_anchor():
    tracks = double_main_tracks()
    to = select_turnout("1:12")
    r1 = req("C1", "LOOP_IN", "MAIN_LINE_1", 500.0, "FORWARD")
    r2 = CrossoverRequest(
        id="C2", from_track="MAIN_LINE_1", to_track="LOOP_OUT",
        chainage=None, direction="FORWARD", turnout=to,
        placement=None, position_mode="AUTO",
        metadata={"auto_anchor_id": "C1"})
    results, report = CrossoverPlanner(tracks, {}, 2000.0).plan([r1, r2])
    assert report.overall_valid, report.errors
    assert results[1].chainage == pytest.approx(
        500.0 + OL_12_265 + 13.0, abs=0.05)


def test_auto_span_belongs_to_starting_track():
    tracks = double_main_tracks()
    short = {k: ([(x, y) for x, y in v if x <= 800.0 + 1e-9] if k == "MAIN_LINE_1" else v)
             for k, v in tracks.items()}
    lo, hi = _track_search_span("MAIN_LINE_1", short, {}, 2000.0)
    assert (lo, hi) == pytest.approx((0.0, 800.0), abs=0.5)
    lo, hi = _track_search_span(
        "LOOP_IN", tracks, {"LOOP_IN": (380.0, 1620.0)}, 2000.0)
    assert (lo, hi) == pytest.approx((380.0, 1620.0))
    planner = CrossoverPlanner(
        tracks, {"LOOP_IN": (380.0, 1620.0)}, 2000.0)
    assert planner._auto_upper_for(
        CrossoverRequest(id="C9", from_track="LOOP_IN", to_track="MAIN_LINE_1",
                         chainage=None, direction="FORWARD",
                         turnout=select_turnout("1:12"), placement=None,
                         position_mode="AUTO")) == pytest.approx(1621.0)


def test_opposite_side_pair_second_main():
    tracks = double_main_tracks()
    results, report = CrossoverPlanner(tracks, {}, 2000.0).plan([
        req("C1", "MAIN_LINE_1", "LOOP_IN", 500.0, "FORWARD"),
        req("C2", "MAIN_LINE_1", "LOOP_OUT", 520.0, "FORWARD"),
    ])
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_loader_preset(tmp_path):
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(
        '{"source_path": "ESP.kml", "output_dxf": "o.dxf", '
        '"loops": [], "crossover_preset": "DEFAULT", '
        '"crossover_preset_turnout": "1:8.5"}',
        encoding="utf-8")
    cfg = load_config_from_json(str(cfg_file))
    assert cfg.crossover_preset == "DEFAULT"
    assert cfg.crossover_preset_turnout == "1:8.5"
    assert cfg.crossovers == []
