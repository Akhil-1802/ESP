"""Fouling Mark (FM) tests: automatic geometry-based detection + DXF drawing."""

from __future__ import annotations

import math
import ezdxf
import pytest

from common.constants import MIN_TRACK_SPACING_M
from common.geometry import point_at_chainage
from track.crossover.core import build_standard_crossover
from track.fouling import (
    FM_LAYER,
    FoulingMark,
    collect_fouling_marks,
    draw_fouling_marks,
    fouling_threshold_m,
)
from track.siding import build_siding_points
from track.specs import SidingSpec
from track.turnouts import select_turnout


def _straight(length=600.0, y=0.0, step=5.0):
    pts = []
    x = 0.0
    while x <= length + 1e-9:
        pts.append((float(x), float(y)))
        x += step
    return pts


def _siding_pair(spacing=5.3, standing=200.0):
    tracks = {"MAIN_LINE": _straight()}
    turnout = select_turnout("1:12")
    result = build_siding_points(
        tracks["MAIN_LINE"], 100.0, "FORWARD", "LEFT",
        turnout, spacing, standing)
    spec = SidingSpec(source_track="MAIN_LINE", start_chainage_m=100.0,
                      direction="FORWARD", side="LEFT",
                      turnout_designation="1:12", standing_length_m=standing,
                      spacing=spacing, id="S1")
    return tracks, spec, result


def _crossover_res(start=100.0, tc=5.3, side="LEFT", a_mm=16989.0):
    y = tc if str(side).upper() == "LEFT" else -tc
    tracks = {"MAIN_LINE": _straight(), "LOOP_1": _straight(y=y)}
    turnout = select_turnout("1:12")
    ol_m = (tc * 1000.0 * 12.0 + 2.0 * turnout.a_mm) / 1000.0
    sp_f = point_at_chainage(tracks["MAIN_LINE"], start)
    sp_t = point_at_chainage(tracks["LOOP_1"], start + ol_m)
    geom, _rep = build_standard_crossover(
        sp_f.point, sp_f.tangent, sp_t.point, sp_t.tangent, turnout)

    class _Res:
        pass

    res = _Res()
    res.id = "C1"
    res.from_track = "MAIN_LINE"
    res.to_track = "LOOP_1"
    res.chainage = start
    res.start_chainage = start
    res.end_chainage = start + ol_m
    res.placement = "AHEAD"
    res.a_mm = a_mm
    res.geometry = geom
    return tracks, res, ol_m


A_12_M = 16989.0 / 1000.0  # 1:12 turnout A
A_85_M = 12025.0 / 1000.0  # 1:8.5 turnout A


def test_threshold_is_minimum_spacing():
    assert fouling_threshold_m() == pytest.approx(float(MIN_TRACK_SPACING_M))
    assert fouling_threshold_m() == pytest.approx(5.3)


def test_parallel_tracks_have_no_fm():
    tracks = {"MAIN_LINE": _straight(), "LOOP_1": _straight(y=5.3)}
    assert collect_fouling_marks(tracks, {}, [], []) == []


def test_single_track_has_no_fm():
    assert collect_fouling_marks({"MAIN_LINE": _straight()}, {}, [], []) == []


def test_siding_gives_single_fm():
    tracks, spec, result = _siding_pair()
    marks = collect_fouling_marks(tracks, {}, [], [(spec, result)], True)
    assert len(marks) == 1, "Siding must have a single FM"
    mark = marks[0]
    assert mark.track == "MAIN_LINE", "FM expected on source track facing siding"
    assert mark.spacing_m == pytest.approx(5.3, abs=0.05)


def test_siding_fm_chainages_are_geometric():
    tracks, spec, result = _siding_pair()
    marks = collect_fouling_marks(tracks, {}, [], [(spec, result)], True)
    assert len(marks) == 1
    src = marks[0]
    assert src.track == "MAIN_LINE"
    assert src.chainage_main > spec.start_chainage_m
    assert src.chainage_main == pytest.approx(
        spec.start_chainage_m + result.ladder_length_m, abs=5.0)


def test_siding_fm_moves_with_spacing():
    _, spec_n, res_n = _siding_pair(spacing=5.3)
    _, spec_w, res_w = _siding_pair(spacing=6.5)
    tracks_n = {"MAIN_LINE": _straight()}
    tracks_w = {"MAIN_LINE": _straight()}
    fm_n = collect_fouling_marks(tracks_n, {}, [], [(spec_n, res_n)], True)
    fm_w = collect_fouling_marks(tracks_w, {}, [], [(spec_w, res_w)], True)
    src_n = next(m for m in fm_n if m.track == "MAIN_LINE")
    src_w = next(m for m in fm_w if m.track == "MAIN_LINE")
    assert abs(src_w.chainage_main - src_n.chainage_main) > 1.0


def test_crossover_gives_two_fixed_fms_at_a_offsets():
    tracks, res, _ol = _crossover_res()
    marks = collect_fouling_marks(tracks, {}, [res], [])
    assert len(marks) == 2, "exactly two FMs per crossover"
    by_track = {m.track: m for m in marks}
    assert set(by_track) == {"MAIN_LINE", "LOOP_1"}
    assert by_track["MAIN_LINE"].chainage_main == pytest.approx(
        res.chainage + A_12_M)
    assert by_track["LOOP_1"].chainage_main == pytest.approx(
        res.end_chainage - A_12_M)


def test_crossover_fm_uses_own_turnout_a():
    tracks, res, _ol = _crossover_res(a_mm=12025.0)
    marks = collect_fouling_marks(tracks, {}, [res], [])
    assert len(marks) == 2
    by_track = {m.track: m for m in marks}
    assert by_track["MAIN_LINE"].chainage_main == pytest.approx(
        res.chainage + A_85_M)
    assert by_track["LOOP_1"].chainage_main == pytest.approx(
        res.end_chainage - A_85_M)


def test_crossover_fm_ignores_geometry_shape():
    tracks = {"FROM": _straight(y=0.0), "TO": _straight(y=6.3)}

    class _Res:
        id = "C-LATE"
        from_track = "FROM"
        to_track = "TO"
        chainage = 100.0
        start_chainage = 100.0
        end_chainage = 160.0
        placement = "AHEAD"
        a_mm = 16989.0
        geometry = [(100.0, 0.0), (120.0, 0.0), (140.0, 2.0), (160.0, 6.3)]

    marks = collect_fouling_marks(tracks, {}, [_Res()], [])
    assert len(marks) == 2
    by_track = {m.track: m for m in marks}
    assert by_track["FROM"].chainage_main == pytest.approx(100.0 + A_12_M)
    assert by_track["TO"].chainage_main == pytest.approx(160.0 - A_12_M)


def test_reverse_crossover_mirrors_a_offsets():
    tracks, _res_fwd, ol = _crossover_res(start=100.0)

    class _Res:
        id = "C2"
        from_track = "LOOP_1"
        to_track = "MAIN_LINE"
        chainage = 400.0
        start_chainage = 400.0 - ol
        end_chainage = 400.0
        placement = "BEHIND"
        direction = "REVERSE"
        a_mm = 16989.0
        geometry = []

    marks = collect_fouling_marks(tracks, {}, [_Res()], [])
    assert len(marks) == 2
    by_track = {m.track: m for m in marks}
    assert by_track["LOOP_1"].chainage_main == pytest.approx(400.0 - A_12_M)
    assert by_track["MAIN_LINE"].chainage_main == pytest.approx(
        400.0 - ol + A_12_M)


def test_every_crossover_gets_both_marks():
    tracks, res1, _ol = _crossover_res(start=100.0)

    class _Res2:
        id = "C2"
        from_track = "LOOP_1"
        to_track = "MAIN_LINE"
        chainage = 400.0
        start_chainage = 400.0 - _ol
        end_chainage = 400.0
        placement = "BEHIND"
        a_mm = 16989.0
        geometry = []

    marks = collect_fouling_marks(tracks, {}, [res1, _Res2()], [])
    assert len(marks) == 4, "two FMs for every crossover"


def test_no_duplicate_fms():
    tracks, res, _ol = _crossover_res()
    marks = collect_fouling_marks(tracks, {}, [res], [])
    for first, second in zip(marks, marks[1:]):
        if first.track == second.track:
            assert abs(first.chainage_main - second.chainage_main) >= 2.0 - 1e-9


def test_draw_fm_layer_and_compact_label():
    tracks, spec, result = _siding_pair()
    marks = collect_fouling_marks(tracks, {}, [], [(spec, result)], True)
    assert marks
    doc = ezdxf.new()
    count = draw_fouling_marks(doc, marks)
    assert count == len(marks)
    assert FM_LAYER in doc.layers
    msp = doc.modelspace()
    texts = [e for e in msp if e.dxf.layer == FM_LAYER
             and e.dxftype() in ("TEXT", "MTEXT")]
    assert texts, "FM label expected"
    blob = " ".join(
        (e.dxf.get("text", "") if e.dxftype() == "TEXT" else str(getattr(e, "text", "")))
        for e in texts)
    assert "FM" in blob and "CH:" not in blob
    ticks = [e for e in msp if e.dxf.layer == FM_LAYER
             and e.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE")]
    open_ticks = []
    for e in ticks:
        try:
            if e.dxftype() == "LINE":
                open_ticks.append(e)
            elif bool(getattr(e, "is_closed", False)):
                continue
            elif bool(e.dxf.get("flags", 0) & 1):
                continue
            else:
                open_ticks.append(e)
        except Exception:
            open_ticks.append(e)
    assert len(open_ticks) == len(marks), "one FM centre tick expected per mark"
    for tick, mark in zip(open_ticks, marks):
        assert int(tick.dxf.get("color", 1)) == 1
        if tick.dxftype() in ("LWPOLYLINE", "POLYLINE"):
            assert float(tick.dxf.get("const_width", 0.25)) == pytest.approx(0.25)
            assert int(tick.dxf.get("lineweight", 80)) == 80
        else:
            assert int(tick.dxf.get("lineweight", 80)) == 80
        if tick.dxftype() == "LINE":
            sx, sy = float(tick.dxf.start.x), float(tick.dxf.start.y)
            ex, ey = float(tick.dxf.end.x), float(tick.dxf.end.y)
        else:
            pts = [(float(p[0]), float(p[1])) for p in tick.get_points()[:2]]
            (sx, sy), (ex, ey) = pts[0], pts[1]
        length = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5
        assert length <= 2.0 + 1e-6 and length >= 0.3 - 1e-6
        cx, cy = (sx + ex) / 2.0, (sy + ey) / 2.0
        mx = (float(mark.point[0]) + float(mark.other_point[0])) / 2.0
        my = (float(mark.point[1]) + float(mark.other_point[1])) / 2.0
        assert (cx, cy) == pytest.approx((mx, my))
        _dist = math.hypot(cx - float(mark.point[0]), cy - float(mark.point[1]))
        assert _dist > 0.5
    assert not [e for e in msp if e.dxf.layer == FM_LAYER
                and e.dxftype() == "HATCH"], "no FM fill"


def test_draw_empty_is_noop():
    doc = ezdxf.new()
    assert draw_fouling_marks(doc, []) == 0


def test_fm_leader_points_toward_conflicting_track():
    for other, expect_sign in (((10.0, 5.0), 1.0), ((10.0, -5.0), -1.0)):
        mark = FoulingMark(
            track="MAIN_LINE", chainage_main=0.0, local_chainage=0.0,
            point=(0.0, 0.0), tangent=(1.0, 0.0),
            other_track="XOVER_C1", other_chainage_main=10.0,
            other_point=other, spacing_m=5.3,
            display_point=(0.0, 0.0), display_tangent=(1.0, 0.0))
        doc = ezdxf.new()
        assert draw_fouling_marks(doc, [mark]) == 1
        ticks = [e for e in doc.modelspace()
                 if e.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE")]
        assert len(ticks) == 1
        tick = ticks[0]
        if tick.dxftype() == "LINE":
            sx, sy = float(tick.dxf.start.x), float(tick.dxf.start.y)
            ex, ey = float(tick.dxf.end.x), float(tick.dxf.end.y)
            assert int(tick.dxf.get("lineweight", 80)) == 80
        else:
            pts = [(float(p[0]), float(p[1])) for p in tick.get_points()[:2]]
            (sx, sy), (ex, ey) = pts[0], pts[1]
            assert float(tick.dxf.get("const_width", 0.25)) == pytest.approx(0.25)
            assert int(tick.dxf.get("lineweight", 80)) == 80
        mx, my = (0.0 + float(other[0])) / 2.0, (0.0 + float(other[1])) / 2.0
        assert ((sx + ex) / 2.0, (sy + ey) / 2.0) == pytest.approx((mx, my))
        assert float(sx) == pytest.approx(float(ex))
        assert abs(float(sy) - float(ey)) == pytest.approx(2.0)
        assert math.hypot((sx + ex) / 2.0 - 0.0, (sy + ey) / 2.0 - 0.0) > 0.5
        assert not [e for e in doc.modelspace()
                    if e.dxftype() == "HATCH"], "no FM fill expected"
        texts = [e for e in doc.modelspace() if e.dxftype() == "TEXT"]
        assert len(texts) == 1
        assert texts[0].dxf.text == "FM"
        insert = texts[0].dxf.insert
        assert (float(insert[0]), float(insert[1])) == pytest.approx(
            (mx + 1.6, my))
        assert float(texts[0].dxf.rotation) == pytest.approx(0.0)


def test_fm_labels_stay_inside_for_both_loop_sides():
    for side in ("LEFT", "RIGHT"):
        tracks, res, _ol = _crossover_res(side=side)
        marks = collect_fouling_marks(tracks, {}, [res], [])
        assert len(marks) == 2
        for mark in marks:
            doc = ezdxf.new()
            assert draw_fouling_marks(doc, [mark]) == 1
            texts = [e for e in doc.modelspace()
                     if e.dxftype() in ("TEXT", "MTEXT")]
            assert len(texts) == 1
            base = mark.display_point or mark.point
            tangent = mark.display_tangent or mark.tangent
            label = texts[0].dxf.insert
            cross_label = (tangent[0] * (float(label[1]) - base[1])
                           - tangent[1] * (float(label[0]) - base[0]))
            cross_other = (tangent[0] * (mark.other_point[1] - base[1])
                           - tangent[1] * (mark.other_point[0] - base[0]))
            assert cross_label * cross_other > 0, (
                f"FM label outside the tracks ({side} loop)")


def test_collect_fouling_marks_defaults_include_siding_marks():
    tracks, spec, result = _siding_pair()
    marks = collect_fouling_marks(tracks, {}, [], [(spec, result)])
    assert len(marks) == 1
    assert marks[0].track == "MAIN_LINE"


def test_reverse_siding_on_loop_draws_fm_marker():
    loop_pts = [(float(x), 5.3) for x in range(0, 1000, 5)]
    tracks = {
        "MAIN_LINE": [(float(x), 0.0) for x in range(0, 1000, 5)],
        "LOOP_1": loop_pts,
    }
    extents = {"LOOP_1": (0.0, 1000.0)}
    turnout = select_turnout("1:8.5")
    res = build_siding_points(loop_pts, 500.0, "REVERSE", "LEFT", turnout, 5.3, 120.0)
    spec = SidingSpec(
        source_track="LOOP_1", start_chainage_m=500.0,
        direction="REVERSE", side="LEFT", turnout_designation="1:8.5",
        standing_length_m=120.0, spacing=5.3, id="1",
    )
    marks = collect_fouling_marks(tracks, extents, [], [(spec, res)])
    assert marks
    doc = ezdxf.new()
    drawn = draw_fouling_marks(doc, marks)
    assert drawn > 0
    msp = doc.modelspace()
    fm_ticks = [e for e in msp if e.dxf.layer == FM_LAYER and e.dxftype() in ("LINE", "LWPOLYLINE")]
    fm_texts = [e for e in msp if e.dxf.layer == FM_LAYER and e.dxftype() == "TEXT"]
    assert fm_ticks and fm_texts
    assert any(7.0 < (p[0][1] + p[1][1]) / 2.0 < 9.0 for p in [e.get_points() for e in fm_ticks if hasattr(e, "get_points")])
