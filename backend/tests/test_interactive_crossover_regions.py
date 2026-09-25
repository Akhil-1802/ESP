"""Interactive crossover platform/station restriction, reverse, and interactive flow tests."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from cli.crossovers import _ask_crossover_start, _ask_crossovers_live
from config.loader import ESPConfig
from pipeline.orchestrator import ESPGenerator
from track.crossover.conflicts import (
    crossover_track_intervals,
    find_restriction_conflicts,
    stations_to_restricted_regions,
)
from track.crossover.defaults import infer_target_track
from track.specs import CrossoverSpec, LoopSpec
from track.turnouts import select_turnout
from .helpers_interactive import (
    OL_12_53,
    _main_platform_regions,
    main_platform_config,
    mk,
    plan_ok,
    straight_tracks,
)


def test_ic_10_platform_overlap_rejected():
    regions = _main_platform_regions()
    intervals = crossover_track_intervals(
        "MAIN_LINE", "LOOP_2", 720.0, 720.0 + OL_12_53,
        "AHEAD", "FORWARD", 16.989)
    conflicts = find_restriction_conflicts(intervals, regions)
    assert len(conflicts) == 1
    assert conflicts[0].overlap_start == pytest.approx(725.0)
    assert conflicts[0].overlap_end == pytest.approx(736.989, abs=0.01)


def test_ic_11_before_platform_clear():
    regions = _main_platform_regions()
    intervals = crossover_track_intervals(
        "MAIN_LINE", "LOOP_2", 700.0, 700.0 - OL_12_53,
        "BEHIND", "REVERSE", 16.989)
    assert find_restriction_conflicts(intervals, regions) == []


def test_ic_12_after_platform_clear():
    regions = _main_platform_regions()
    intervals = crossover_track_intervals(
        "MAIN_LINE", "LOOP_2", 1400.0, 1400.0 + OL_12_53,
        "AHEAD", "FORWARD", 16.989)
    assert find_restriction_conflicts(intervals, regions) == []


def test_ic_touching_region_boundary_ok():
    regions = _main_platform_regions()
    intervals = {"MAIN_LINE": (627.422, 725.0)}
    assert find_restriction_conflicts(intervals, regions) == []


def test_ic_13_reverse_crossover():
    tracks = straight_tracks()
    results, report = plan_ok(
        [mk("C1", "LOOP_1", "MAIN_LINE", 500.0, "REVERSE")], tracks)
    assert report.overall_valid, report.errors
    res = results[0]
    assert res.placement == "BEHIND"
    assert res.start_chainage == pytest.approx(500.0 - OL_12_53, abs=0.01)
    assert res.end_chainage == pytest.approx(500.0)


def test_ic_14_reverse_near_another():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 229.709, "REVERSE"),
    ], tracks)
    assert not report.overall_valid
    assert any("C2" in e for e in report.errors)


def _live_args(tracks=None, restrictions=None):
    tracks = tracks or straight_tracks()
    metas = [("MAIN_LINE", None, None), ("LOOP_2", 5.3, "RIGHT"),
             ("LOOP_1", 5.3, "LEFT")]
    return (["MAIN_LINE", "LOOP_1", "LOOP_2"], tracks, {},
            metas, 2000.0, restrictions or [])


def _run_live(monkeypatch, tmp_path, inputs, **kw):
    monkeypatch.chdir(tmp_path)
    answers = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    names, tracks, extents, metas, length, regions = _live_args(**kw)
    return _ask_crossovers_live(names, tracks, extents, metas, length,
                                regions)


def test_ic_15_retry_leaves_no_geometry(monkeypatch, tmp_path):
    specs = _run_live(monkeypatch, tmp_path, [
        "2",
        "LOOP_1", "MAIN_LINE", "500", "FORWARD", "1:12",
        "MAIN_LINE", "LOOP_2", "600", "FORWARD", "1:12",
        "700",
    ])
    assert [s.id for s in specs] == ["C1", "C2"]
    assert specs[1].from_chainage_m == pytest.approx(700.0)
    assert list(Path(tmp_path).iterdir()) == []


def test_ic_16_retry_accepted_once(monkeypatch, tmp_path):
    specs = _run_live(monkeypatch, tmp_path, [
        "2",
        "LOOP_1", "MAIN_LINE", "500", "FORWARD", "1:12",
        "MAIN_LINE", "LOOP_2", "600", "FORWARD", "1:12",
        "700",
    ])
    assert len(specs) == 2
    assert specs[1].to_track == "LOOP_2"

    src = tmp_path / "src.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line(
        (0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))
    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 625.0, 1375.0),
        LoopSpec("LOOP_2", 5.3, "RIGHT", 625.0, 1375.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 700.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_2", 860.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]
    out = tmp_path / "out.dxf"
    ESPGenerator(ESPConfig(
        source_path=str(src), output_dxf=str(out),
        track_source_layer="MAIN_TRACK", loops=loops,
        additional_lines=[], platforms=[], stations=[],
        crossovers=xspecs, main_directions={})).run()
    assert os.path.exists(out)
    check = ezdxf.readfile(str(out))
    n_spline = sum(1 for e in check.modelspace()
                   if e.dxftype() == "SPLINE" and e.dxf.layer == "CROSSOVERS")
    assert n_spline == 2


def test_ic_overrun_dead_end_both_tips_one_side_cut(tmp_path):
    src = tmp_path / "src.dxf"
    doc = ezdxf.new()
    doc.modelspace().add_line(
        (0.0, 0.0), (2000.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))
    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 500.0, 1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
        LoopSpec("LOOP_2", 5.3, "RIGHT", 500.0, 1250.0,
                 extend_start_m=120.0, extend_end_m=120.0),
    ]
    xspecs = [
        CrossoverSpec("LOOP_1", "MAIN_LINE", 500.0, None,
                      select_turnout("1:12"), "AHEAD", id="C1",
                      direction="FORWARD", position_mode="FIXED"),
        CrossoverSpec("MAIN_LINE", "LOOP_2", 700.0, None,
                      select_turnout("1:12"), "AHEAD", id="C2",
                      direction="FORWARD", position_mode="FIXED"),
    ]
    out = tmp_path / "out.dxf"
    gen = ESPGenerator(ESPConfig(
        source_path=str(src), output_dxf=str(out),
        track_source_layer="MAIN_TRACK", loops=loops,
        additional_lines=[], platforms=[], stations=[],
        crossovers=xspecs, main_directions={}))
    gen.run()
    assert gen._loop_cuts.get("LOOP_2", (None, None))[0] is not None
    assert gen._loop_cuts.get("LOOP_2", (None, None))[1] is None
    check = ezdxf.readfile(str(out))
    over_texts = [e for e in check.modelspace()
                  if e.dxftype() == "TEXT" and e.dxf.layer == "OVER_RUN"]
    assert len(over_texts) == 8
    cal_texts = [e for e in over_texts if "CAL=" in (e.dxf.text or "")]
    de_texts = [e for e in over_texts if (e.dxf.text or "") == "DE"]
    assert len(cal_texts) == 4 and len(de_texts) == 4
    assert all("CAL=120.00" in (e.dxf.text or "") for e in cal_texts)


def test_ic_17_arbitrary_input_order():
    tracks = straight_tracks()
    results, report = plan_ok([
        mk("C3", "MAIN_LINE", "LOOP_2", 1500.0, "REVERSE"),
        mk("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        mk("C2", "LOOP_1", "MAIN_LINE", 800.0, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert len(report.spacing_checks) == 2
    assert all(r.validation_status == "VALID" for r in results)


def test_ic_18_nonadjacent_conflict():
    tracks = straight_tracks()
    _results, report = plan_ok([
        mk("C1", "LOOP_1", "MAIN_LINE", 200.0, "FORWARD"),
        mk("C2", "MAIN_LINE", "LOOP_2", 1500.0, "REVERSE"),
        mk("C3", "LOOP_1", "MAIN_LINE", 260.0, "FORWARD"),
    ], tracks)
    assert not report.overall_valid
    assert any("C3" in e and "C1" in e for e in report.errors)


def test_ic_target_inference():
    metas = [("MAIN_LINE", None, None), ("LOOP_1", 5.3, "LEFT"),
             ("LOOP_2", 10.0, "RIGHT")]
    assert infer_target_track("LOOP_1", metas) == "MAIN_LINE"
    assert infer_target_track("MAIN_LINE", metas) == "LOOP_1"
    tie = [("MAIN_LINE", None, None), ("LOOP_1", 5.3, "LEFT"),
           ("LOOP_2", 5.3, "RIGHT")]
    assert infer_target_track("MAIN_LINE", tie) == "LOOP_1"
    with pytest.raises(ValueError):
        infer_target_track("MAIN_LINE", [("MAIN_LINE", None, None)])
    with pytest.raises(ValueError):
        infer_target_track("LOOP_1", [("LOOP_1", 5.3, "LEFT")])


def test_ic_loop_to_loop_crossover(monkeypatch, tmp_path):
    tracks = straight_tracks()
    loop3 = [(x, 10.6) for x, _ in tracks["MAIN_LINE"]]
    tracks = dict(tracks, LOOP_3=loop3)
    names = ["MAIN_LINE", "LOOP_1", "LOOP_3"]
    metas = [("MAIN_LINE", None, None), ("LOOP_1", 5.3, "LEFT"),
             ("LOOP_3", 10.6, "LEFT")]
    monkeypatch.chdir(tmp_path)
    answers = iter(["1", "LOOP_1", "LOOP_3", "500", "FORWARD", "1:12"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    specs = _ask_crossovers_live(names, tracks, {}, metas, 2000.0, [])
    assert [s.id for s in specs] == ["C1"]
    assert specs[0].from_track == "LOOP_1"
    assert specs[0].to_track == "LOOP_3"
    results, report = plan_ok(
        [mk("C1", "LOOP_1", "LOOP_3", 500.0, "FORWARD")], tracks)
    assert report.overall_valid, report.errors
    assert results[0].end_chainage == pytest.approx(
        500.0 + OL_12_53, abs=0.05)


def test_ic_start_range_excludes_overrun(monkeypatch):
    answers = iter(["55.709", "500"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    value = _ask_crossover_start(
        "LOOP_1", {"LOOP_1": (175.709, 925.709)})
    assert value == pytest.approx(500.0)


def test_ic_start_inside_platform_rejected(monkeypatch, capsys):
    answers = iter(["500", "100"])

    def echo_input(prompt=""):
        print(prompt, end="")
        return next(answers)

    monkeypatch.setattr("builtins.input", echo_input)
    value = _ask_crossover_start(
        "MAIN_LINE", {},
        blocked=[(275.7, 825.7, "Platform 1 [PLATFORM_1]")],
        full_range=(0.0, 1101.0))
    assert value == pytest.approx(100.0)
    out = capsys.readouterr().out
    assert "0-1101" in out
    assert "[275.700-825.700]" in out


def test_ic_station_regions():
    tracks = straight_tracks()
    main = tracks["MAIN_LINE"]
    preq = SimpleNamespace(
        track_layer="MAIN_LINE",
        config=main_platform_config(output_layer="PLATFORM_1"),
    )
    sreq = SimpleNamespace(platform_layer="PLATFORM_1",
                           building_length=40.0,
                           building_width=10.0,
                           platform_side="LEFT",
                           building_name="STATION BUILDING")
    regions = stations_to_restricted_regions(
        [sreq], [preq], {"MAIN_LINE": main}, {})
    assert len(regions) == 1
    assert regions[0].start_chainage == pytest.approx(980.0)
    assert regions[0].end_chainage == pytest.approx(1020.0)
