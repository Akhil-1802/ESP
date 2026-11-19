"""LOOP / MAIN CAL callout label calculations and basic drawing tests."""

from __future__ import annotations

import ezdxf
import pytest
from app.features.drawing_generation.config import ESPConfig
from app.features.drawing_generation.domain.geometry.operations import (
    nearest_point_on_alignment,
    polyline_length,
)
from app.features.drawing_generation.domain.track.cal_labels import (
    CAL_LAYER,
    CAL_TEXT_GAP_M,
    assign_line_numbers,
    draw_cal_labels,
    format_loop_cal,
    format_main_cal,
    main_fm_span_m,
)
from app.features.drawing_generation.domain.track.specs import CrossoverSpec, LoopSpec
from app.features.drawing_generation.domain.track.turnouts import select_turnout
from app.features.drawing_generation.pipeline.generator import ESPGenerator

from .helpers_cal_labels import (
    _cal_segs,
    _cal_texts,
    _cal_tips,
    _mark,
    _seg_seg_dist,
    _straight,
)


def test_loop_format_matches_reference():
    assert format_loop_cal(1, 776.0) == "LOOP LINE NO-1 CAL 776.000M (FM TO FM)"
    assert format_loop_cal(1, 776.0, fm_to_fm=False) == "LOOP LINE NO-1 CAL 776.000M (END TO END)"


def test_main_format_matches_reference():
    assert format_main_cal(2, 822.184) == "MAIN LINE NO-2 CAL 822.184M (FM TO FM)"


def test_numbering_is_loops_first_then_mains():
    tracks = {
        "MAIN_LINE": _straight(),
        "LOOP_1": _straight(y=5.3),
        "MAIN_LINE_2": _straight(y=-5.3),
        "LOOP_2": _straight(y=10.6),
    }
    assert assign_line_numbers(tracks) == [
        ("LOOP_1", "LOOP", 1),
        ("LOOP_2", "LOOP", 2),
        ("MAIN_LINE", "MAIN", 3),
        ("MAIN_LINE_2", "MAIN", 4),
    ]


def test_numbering_skips_non_running_tracks():
    tracks = {"MAIN_LINE": _straight(), "SIDING_S1": _straight(y=10.6)}
    assert assign_line_numbers(tracks) == [("MAIN_LINE", "MAIN", 1)]


def test_main_span_is_last_fm_to_last_fm():
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184),
             _mark("LOOP_1", 200.0)]
    assert main_fm_span_m(marks, "MAIN_LINE") == 822.184


def test_main_span_needs_two_marks():
    assert main_fm_span_m([], "MAIN_LINE") is None
    assert main_fm_span_m([_mark("MAIN_LINE", 100.0)], "MAIN_LINE") is None
    assert main_fm_span_m([_mark("LOOP_1", 100.0)], "MAIN_LINE") is None


def test_leader_keeps_gap_before_text_glyphs():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    draw_cal_labels(doc, tracks, marks)
    texts = _cal_texts(doc)
    assert len(texts) == 2
    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 2
    segs = _cal_segs(doc)
    assert len(segs) == 4
    for text in texts:
        label = text.dxf.text or ""
        cx, cy = float(text.dxf.insert.x), float(text.dxf.insert.y)
        est_left = cx - len(label) * 0.7 / 2.0
        stubs = [s for s in segs
                 if s[0][1] == pytest.approx(cy)
                 and s[1][1] == pytest.approx(cy)]
        assert len(stubs) == 1
        assert max(stubs[0][0][0], stubs[0][1][0]) == pytest.approx(
            est_left - CAL_TEXT_GAP_M)
        half_wide = len(label) * 0.8 / 2.0
        x0, x1, y0, y1 = cx - half_wide, cx + half_wide, cy - 0.5, cy + 0.5
        edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)),
                 ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
        for a, b in segs:
            for c, d in edges:
                assert _seg_seg_dist(a, b, c, d) > 0.0


def test_draw_loop_end_to_end_and_main_fm_to_fm():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert summary["LOOP_1"] == ("LOOP LINE NO-1 CAL 776.000M (END TO END)", 776.0)
    label, span = summary["MAIN_LINE"]
    assert span == 822.184
    assert label == "MAIN LINE NO-2 CAL 822.184M (FM TO FM)"
    texts = {(e.dxf.text or "") for e in _cal_texts(doc)}
    assert "LOOP LINE NO-1 CAL 776.000M (END TO END)" in texts
    assert "MAIN LINE NO-2 CAL 822.184M (FM TO FM)" in texts
    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 2
    for ldr in leaders:
        assert len(list(ldr.vertices)) == 3
    tips = sorted(t[0] for t in _cal_tips(doc))
    lefts = sorted(float(e.dxf.insert.x) - len(e.dxf.text) * 0.7 / 2.0
                   for e in _cal_texts(doc))
    for tip_x, left_x in zip(tips, lefts):
        assert left_x > tip_x


def test_draw_is_idempotent():
    doc = ezdxf.new("R2010")
    tracks = {"LOOP_1": _straight(776.0, y=5.3)}
    first = draw_cal_labels(doc, tracks, [])
    second = draw_cal_labels(doc, tracks, [])
    assert first == second
    assert len(_cal_texts(doc)) == 1


def test_main_without_two_fms_gets_no_label():
    doc = ezdxf.new("R2010")
    tracks = {"MAIN_LINE": _straight(1000.0)}
    assert draw_cal_labels(doc, tracks, [_mark("MAIN_LINE", 100.0)]) == {}
    assert _cal_texts(doc) == []


def test_cut_loop_measures_full_end_to_end_line():
    doc = ezdxf.new("R2010")
    tracks = {"LOOP_1": _straight(814.8, y=5.3)}
    full = _straight(990.0, y=5.3)
    summary = draw_cal_labels(doc, tracks, [], measure_points={"LOOP_1": full})
    label, length = summary["LOOP_1"]
    assert length == 990.0
    assert label == "LOOP LINE NO-1 CAL 990.000M (END TO END)"
    texts = _cal_texts(doc)
    assert len(texts) == 1
    assert texts[0].dxf.text == label
    tips = _cal_tips(doc)
    assert len(tips) == 1
    tip = tips[0]
    assert tip[0] == pytest.approx(357.4)
    assert nearest_point_on_alignment(tracks["LOOP_1"], tip).distance < 1e-9
    left = float(texts[0].dxf.insert.x) - len(texts[0].dxf.text) * 0.7 / 2.0
    assert left > tip[0]


def test_degenerate_override_falls_back_to_track():
    doc = ezdxf.new("R2010")
    tracks = {"LOOP_1": _straight(776.0, y=5.3)}
    summary = draw_cal_labels(doc, tracks, [],
                              measure_points={"LOOP_1": [(0.0, 5.3)]})
    assert summary["LOOP_1"][1] == 776.0


def test_cut_loop_cal_reads_full_line_end_to_end(tmp_path):
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
    full = gen._loop_full_lines.get("LOOP_2")
    assert full is not None and len(full) >= 2
    expected = polyline_length([(float(p[0]), float(p[1])) for p in full])
    check = ezdxf.readfile(str(out))
    found = [e for e in check.modelspace()
             if e.dxftype() == "TEXT" and e.dxf.layer == CAL_LAYER
             and (e.dxf.text or "") == f"LOOP LINE NO-2 CAL {expected:.3f}M (END TO END)"]
    assert len(found) == 1
    running_pts = []
    for e in check.modelspace():
        if e.dxf.layer == "LOOP_2" and e.dxftype() == "LWPOLYLINE":
            running_pts.extend([(float(p[0]), float(p[1]))
                                for p in e.get_points()])
    assert len(running_pts) >= 2
    running = polyline_length(running_pts)
    assert expected > running + 1.0
