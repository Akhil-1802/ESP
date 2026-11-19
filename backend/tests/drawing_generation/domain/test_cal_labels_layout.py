"""LOOP / MAIN CAL callout label layout, collision, and leader tests."""

from __future__ import annotations

import math

import ezdxf
import pytest
from app.features.drawing_generation.domain.geometry.operations import (
    nearest_point_on_alignment,
)
from app.features.drawing_generation.domain.track.cal_labels import (
    CAL_LAYER,
    draw_cal_labels,
)

from .helpers_cal_labels import (
    _cal_segs,
    _cal_texts,
    _cal_tips,
    _mark,
    _straight,
)


def test_tips_sit_at_track_centre():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    draw_cal_labels(doc, tracks, marks)
    tips = {}
    for t in _cal_tips(doc):
        tips[round(t[1], 1)] = t
    assert tips[0.0][0] == pytest.approx(450.0)
    assert tips[5.3][0] == pytest.approx(338.0)
    for (name, y) in (("MAIN_LINE", 0.0), ("LOOP_1", 5.3)):
        tip = tips[y]
        assert nearest_point_on_alignment(tracks[name], tip).distance < 1e-9
    for e in doc.modelspace():
        if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER:
            v = [(float(p[0]), float(p[1])) for p in e.vertices]
            tip_p, elbow_p = v[0], v[1]
            dx, dy = tip_p[0] - elbow_p[0], tip_p[1] - elbow_p[1]
            assert dx < 0
            if tip_p[1] == pytest.approx(0.0):
                assert dy < 0
            else:
                assert dy > 0


def test_cal_leaders_do_not_overlap_tracks():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
        "LOOP_2": _straight(776.0, y=10.6),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    draw_cal_labels(doc, tracks, marks)
    segs = _cal_segs(doc)
    assert len(segs) == 4
    run = {n: [(float(p[0]), float(p[1])) for p in pts]
           for n, pts in tracks.items()}

    def _on_track(point):
        for name, pts in run.items():
            if nearest_point_on_alignment(pts, point).distance < 1e-9:
                return name
        return None

    for a, b in segs:
        hit_a, hit_b = _on_track(a), _on_track(b)
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        if hit_a is not None or hit_b is not None:
            own = hit_a if hit_a is not None else hit_b
            far = b if hit_a == own else a
            assert nearest_point_on_alignment(run[own], far).distance >= 1.0
            others = [n for n in run if n != own]
        else:
            others = list(run)
        for name in others:
            d = nearest_point_on_alignment(run[name], mid).distance
            assert d >= 1.0


def test_texts_stack_above_top_rail():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
        "LOOP_2": _straight(776.0, y=10.6),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 3
    texts = _cal_texts(doc)
    assert len(texts) == 3
    rows: dict[float, list] = {}
    for e in texts:
        rows.setdefault(round(float(e.dxf.insert.y), 3), []).append(e)
    assert sorted(rows) == pytest.approx([0.65, 7.4, 9.2])
    for y, parts in rows.items():
        assert len(parts) == 1
    by_y = {y: parts[0].dxf.text for y, parts in rows.items()}
    assert by_y[9.2] == summary["LOOP_2"][0]
    assert by_y[7.4] == summary["LOOP_1"][0]
    assert by_y[0.65] == summary["MAIN_LINE"][0]


def test_case_1_single_label_in_gap_no_marker_no_leader():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    summary = draw_cal_labels(doc, tracks, marks=[])
    assert "LOOP_1" in summary
    assert "MAIN_LINE" not in summary

    texts = _cal_texts(doc)
    assert len(texts) == 1
    text = texts[0]
    assert text.dxf.text == "LOOP LINE NO-1 CAL 776.000M (END TO END)"

    cy = float(text.dxf.insert.y)
    assert 0.0 < cy < 5.3
    assert cy == pytest.approx(4.65)

    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 0
    tips = _cal_tips(doc)
    assert len(tips) == 0
    segs = _cal_segs(doc)
    assert len(segs) == 0


def test_case_2_multiple_labels_in_gap_with_markers_pointing_to_tracks():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 2

    texts = _cal_texts(doc)
    assert len(texts) == 2

    for t in texts:
        cy = float(t.dxf.insert.y)
        assert 0.0 < cy < 5.3

    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 2

    tips = _cal_tips(doc)
    tip_ys = sorted([t[1] for t in tips])
    assert tip_ys == pytest.approx([0.0, 5.3])


def test_case_3_insufficient_space_fallback_above_track():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=2.0),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 2

    texts = _cal_texts(doc)
    assert len(texts) == 2

    for t in texts:
        cy = float(t.dxf.insert.y)
        assert cy == pytest.approx(3.0) or cy == pytest.approx(5.0)

    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 2


def test_two_column_layout_any_number_of_rows():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "MAIN_LINE_2": _straight(1000.0, y=-5.3),
        "LOOP_1": _straight(776.0, y=5.3),
        "LOOP_2": _straight(790.0, y=10.6),
        "LOOP_3": _straight(805.0, y=15.9),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184),
             _mark("MAIN_LINE_2", 100.0), _mark("MAIN_LINE_2", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 5
    texts = _cal_texts(doc)
    assert len(texts) == 5
    rows: dict[float, list] = {}
    for e in texts:
        rows.setdefault(round(float(e.dxf.insert.y), 3), []).append(e)
    assert len(rows) == 5
    for parts in rows.values():
        assert len(parts) == 1
    got = {e.dxf.text for e in texts}
    for _name, (label, _length) in summary.items():
        assert label in got


def test_top_down_filling_pairs_and_arrow_orientations():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0),
        "LOOP_1": _straight(776.0, y=5.3),
        "LOOP_2": _straight(776.0, y=10.6),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 3

    texts = _cal_texts(doc)
    assert len(texts) == 3

    by_text = {e.dxf.text: float(e.dxf.insert.y) for e in texts}
    assert by_text[summary["LOOP_2"][0]] == pytest.approx(9.2)
    assert by_text[summary["LOOP_1"][0]] == pytest.approx(7.4)
    assert by_text[summary["MAIN_LINE"][0]] == pytest.approx(0.65)

    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 2

    for ldr in leaders:
        v = [(float(p[0]), float(p[1])) for p in ldr.vertices]
        tip_p, elbow_p = v[0], v[1]
        dx = tip_p[0] - elbow_p[0]
        dy = tip_p[1] - elbow_p[1]
        assert dx < 0
        if tip_p[1] == pytest.approx(10.6):
            assert dy > 0
        elif tip_p[1] == pytest.approx(5.3):
            assert dy < 0


def test_top_down_four_tracks_forms_two_pairs():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0, y=0.0),
        "MAIN_LINE_2": _straight(1000.0, y=-5.3),
        "LOOP_1": _straight(776.0, y=5.3),
        "LOOP_2": _straight(776.0, y=10.6),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184),
             _mark("MAIN_LINE_2", 100.0), _mark("MAIN_LINE_2", 922.184)]
    summary = draw_cal_labels(doc, tracks, marks)
    assert len(summary) == 4

    texts = _cal_texts(doc)
    assert len(texts) == 4

    by_text = {e.dxf.text: float(e.dxf.insert.y) for e in texts}
    assert by_text[summary["LOOP_2"][0]] == pytest.approx(9.2)
    assert by_text[summary["LOOP_1"][0]] == pytest.approx(7.4)
    assert by_text[summary["MAIN_LINE"][0]] == pytest.approx(-1.4)
    assert by_text[summary["MAIN_LINE_2"][0]] == pytest.approx(-3.2)

    leaders = [e for e in doc.modelspace()
               if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    assert len(leaders) == 4


def test_no_duplicate_arrowheads_on_leaders():
    doc = ezdxf.new("R2010")
    tracks = {
        "MAIN_LINE": _straight(1000.0, y=0.0),
        "LOOP_1": _straight(776.0, y=5.3),
    }
    marks = [_mark("MAIN_LINE", 100.0), _mark("MAIN_LINE", 922.184)]
    draw_cal_labels(doc, tracks, marks)

    msp = doc.modelspace()
    leaders = [e for e in msp if e.dxftype() == "LEADER" and e.dxf.layer == CAL_LAYER]
    hatches = [e for e in msp if e.dxftype() == "HATCH" and e.dxf.layer == CAL_LAYER]
    polylines = [e for e in msp if e.dxftype() in ("LWPOLYLINE", "POLYLINE") and e.dxf.layer == CAL_LAYER]

    assert len(leaders) == 2
    assert len(hatches) == 0
    assert len(polylines) == 0

    for ldr in leaders:
        assert len([e for e in ldr.virtual_entities() if e.dxftype() == "LINE"]) == 2
        v = list(ldr.vertices)
        seg_len = math.hypot(v[0][0] - v[1][0], v[0][1] - v[1][1])
        assert seg_len >= 4.0
