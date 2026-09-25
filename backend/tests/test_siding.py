"""Dead-end siding tests: ladder geometry, validation, loader, CLI."""

from __future__ import annotations

import ezdxf
import pytest

from cli.sidings import _ask_sidings
from config.loader import load_config_from_json
from track.siding import (
    build_siding_points,
    corridor_polygon,
    draw_siding_dead_end,
    min_separation,
    portion_from,
    required_separation,
    validate_siding,
)
from track.specs import SidingSpec
from track.turnouts import select_turnout


def _main(length=2000.0):
    return [(0.0, 0.0), (float(length), 0.0)]


def _cfg(**over):
    kw = dict(source_track="MAIN_LINE", start_chainage_m=100.0,
              direction="FORWARD", side="LEFT",
              turnout_designation="1:12", turnout_variant="standard",
              standing_length_m=100.0, spacing=5.3, id="S1")
    kw.update(over)
    return SidingSpec(**kw)


def _result(**over):
    cfg = _cfg(**over)
    turnout = select_turnout(cfg.turnout_designation, cfg.turnout_variant)
    return cfg, build_siding_points(
        _main(), cfg.start_chainage_m, cfg.direction, cfg.side,
        turnout, cfg.spacing, cfg.standing_length_m)


def test_forward_left_runs_parallel():
    cfg, res = _result()
    assert res.tip[1] == abs(res.tip[1])
    assert abs(res.tip[1] - 5.3) < 0.05
    assert res.tip_tangent == (1.0, 0.0)
    assert res.total_length_m == res.ladder_length_m + 100.0
    assert 85.0 < res.ladder_length_m < 115.0
    assert res.tip[0] > cfg.start_chainage_m + res.ladder_length_m


def test_reverse_right_mirrors():
    _cfg2, res = _result(direction="REVERSE", side="RIGHT")
    assert abs(res.tip[1] - 5.3) < 0.05 or abs(res.tip[1] + 5.3) < 0.05
    assert res.tip_tangent == (-1.0, 0.0)
    assert res.tip[0] < 100.0


def test_each_side_lands_on_its_side():
    _cfg_l, left = _result(side="LEFT")
    _cfg_r, right = _result(side="RIGHT")
    assert left.tip[1] > 0 > right.tip[1]
    assert abs(abs(left.tip[1]) - 5.3) < 0.05
    assert abs(abs(right.tip[1]) - 5.3) < 0.05


def test_small_spacing_raises():
    cfg = _cfg(turnout_designation="1:8.5", spacing=2.5)
    turnout = select_turnout(cfg.turnout_designation, cfg.turnout_variant)
    try:
        build_siding_points(_main(), 100.0, "FORWARD", "LEFT",
                            turnout, 2.5, 100.0)
    except ValueError as exc:
        assert "too small" in str(exc)
    else:
        raise AssertionError("expected ValueError for tight spacing")


def test_bad_inputs_raise():
    turnout = select_turnout("1:12")
    for kwargs in ({"direction": "SIDEWAYS"}, {"side": "UP"}):
        base = dict(direction="FORWARD", side="LEFT")
        base.update(kwargs)
        try:
            build_siding_points(_main(), 100.0, base["direction"],
                                base["side"], turnout, 5.3, 100.0)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {kwargs}")
    try:
        build_siding_points(_main(), 100.0, "FORWARD", "LEFT",
                            turnout, 5.3, 0.0)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for zero standing")


def test_required_separation_rule():
    assert required_separation("FORWARD", "FORWARD") == 13.0
    assert required_separation("FORWARD", "REVERSE") == 54.0
    assert required_separation("REVERSE", "REVERSE") == 13.0


def test_min_separation_parallel():
    assert abs(min_separation([(0, 0), (100, 0)], [(0, 5.3), (100, 5.3)])
               - 5.3) < 0.01


def test_portion_from_splits_ladder():
    _cfg, res = _result()
    parallel = portion_from(res.points, res.ladder_length_m)
    assert len(parallel) >= 2
    assert abs(parallel[0][1] - 5.3) < 0.1
    assert portion_from(res.points, 0.0) == res.points


def test_corridor_covers_centreline():
    _cfg, res = _result()
    poly = corridor_polygon(res.points, 2.5)
    assert len(poly) == 2 * len(res.points)
    assert abs(poly[0][1] - (res.points[0][1] + 2.5)) < 0.5


def _world():
    tracks = {"MAIN_LINE": _main()}
    return tracks


def test_validate_clear_passes():
    cfg, res = _result()
    validate_siding("S1", "MAIN_LINE", 100.0, "FORWARD", res, _world(),
                    [], [], [], [])


def test_validate_turnout_spacing_raises():
    cfg, res = _result()
    try:
        validate_siding("S1", "MAIN_LINE", 100.0, "FORWARD", res, _world(),
                        [(105.0, "FORWARD", "crossover C9 START")],
                        [], [], [])
    except ValueError as exc:
        assert "5.00 m" in str(exc) and "never moved" in str(exc)
    else:
        raise AssertionError("expected turnout spacing error")


def test_validate_platform_overlap_raises():
    cfg, res = _result()
    platform = [(150, 0), (250, 0), (250, 12), (150, 12)]
    try:
        validate_siding("S1", "MAIN_LINE", 100.0, "FORWARD", res, _world(),
                        [], [("PLATFORM_9", platform)], [], [])
    except ValueError as exc:
        assert "PLATFORM_9" in str(exc)
    else:
        raise AssertionError("expected platform overlap error")


def test_dead_end_draws_marker():
    _cfg, res = _result()
    doc = ezdxf.new()
    doc.layers.add("SIDING_1", color=1)
    draw_siding_dead_end(doc, res.tip, res.tip_tangent, "SIDING_1", 1, standing_length_m=res.standing_length_m)
    entities = [e for e in doc.modelspace()
                if e.dxf.layer == "SIDING_1"]
    texts = [e for e in entities if e.dxftype() == "TEXT"]
    assert any(t.dxf.text == "DE" for t in texts)
    csl_texts = [t for t in texts if t.dxf.text == f"CSL={res.standing_length_m:g}M"]
    assert len(csl_texts) == 1
    csl_entity = csl_texts[0]
    align = csl_entity.dxf.align_point
    assert align[0] < res.tip[0]
    assert align[1] < res.tip[1]


def test_loader_sidings(tmp_path):
    cfg_file = tmp_path / "cfg.json"
    cfg_file.write_text(
        '{"source_path": "ESP.kml", "output_dxf": "o.dxf", '
        '"loops": [], "platforms": [], '
        '"sidings": [{"source_track": "MAIN_LINE", "start_chainage_m": 50, '
        '"direction": "forward", "side": "left", '
        '"turnout": "1:8.5", "standing_length_m": 120}]}',
        encoding="utf-8")
    cfg = load_config_from_json(str(cfg_file))
    assert len(cfg.sidings) == 1
    spec = cfg.sidings[0]
    assert spec.id == "S1"
    assert (spec.source_track, spec.direction, spec.side) == \
        ("MAIN_LINE", "FORWARD", "LEFT")
    assert spec.turnout_designation == "1:8.5"
    assert spec.standing_length_m == 120.0
    assert spec.spacing == 5.3


def test_cli_sidings(monkeypatch):
    answers = iter(["1", "MAIN_LINE", "950", "FORWARD", "LEFT",
                    "1:12", "200"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(answers))
    sidings = _ask_sidings(["MAIN_LINE", "LOOP_1"], 550.5, {})
    assert len(sidings) == 1
    spec = sidings[0]
    assert (spec.source_track, spec.start_chainage_m, spec.direction,
            spec.side, spec.turnout_designation,
            spec.standing_length_m, spec.id) == \
        ("MAIN_LINE", 950.0, "FORWARD", "LEFT", "1:12", 200.0, "S1")


def test_cli_siding_range_enforced(monkeypatch, capsys):
    answers = iter(["1", "LOOP_1", "50", "500", "FORWARD", "LEFT",
                    "1:12", "200"])

    def echo_input(prompt=""):
        print(prompt, end="")
        return next(answers)

    monkeypatch.setattr("builtins.input", echo_input)
    sidings = _ask_sidings(["MAIN_LINE", "LOOP_1"], 550.5,
                           {"LOOP_1": (100.0, 900.0)})
    assert sidings[0].start_chainage_m == 500.0
    out = capsys.readouterr().out
    assert "100-900" in out
