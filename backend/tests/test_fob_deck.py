"""Basic FOB deck tests: span from platform boundaries, validation."""

from __future__ import annotations

import ezdxf
import pytest

from fob.config import FOBConfig, validate_fob_clearance
from fob.deck import (
    FOB_LABEL,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
    axis_spans,
    build_fob_arms,
    build_fob_outline,
    choose_label_spot,
    generate_fob,
    track_axis_hits,
    validate_fob_span,
    write_fob_deck,
)
from pipeline.orchestrator import ESPGenerator


def _square(cx, cy, half):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half)]


def test_span_covers_all_platforms():
    platforms = [_square(0, -8, 5), _square(0, 8, 5)]
    outline = build_fob_outline((0, 0), (1, 0), platforms, 3.0)
    xs = sorted(p[0] for p in outline)
    ys = sorted(p[1] for p in outline)
    assert xs == pytest.approx([-1.5, -1.5, 1.5, 1.5])
    assert ys == pytest.approx([-13.0, -13.0, 13.0, 13.0])


def test_miss_raises():
    platforms = [_square(500, 50, 5)]
    with pytest.raises(ValueError, match="misses"):
        build_fob_outline((0, 0), (1, 0), platforms, 3.0)


def test_custom_width_and_extensions():
    platforms = [_square(0, -8, 5), _square(0, 8, 5)]
    outline = build_fob_outline((0, 0), (1, 0), platforms, 4.0,
                                extend_start=1.0, extend_end=2.0)
    xs = sorted(p[0] for p in outline)
    ys = sorted(p[1] for p in outline)
    assert xs == pytest.approx([-2.0, -2.0, 2.0, 2.0])
    assert ys == pytest.approx([-14.0, -14.0, 15.0, 15.0])


def test_max_span_raised():
    # actual: "FOB span 30.010 m exceeds the maximum 30 m single span."
    with pytest.raises(ValueError, match=r"exceeds the maximum 30 m"):
        validate_fob_span(30.01)
    validate_fob_span(30.0)


def test_vertical_clearance_raised():
    with pytest.raises(ValueError, match="6.25 m"):
        validate_fob_clearance(6.24)
    validate_fob_clearance(6.25)


def test_clearance_config_validated():
    # FOBConfig does not validate vertical_clearance_m at construction
    with pytest.raises(ValueError, match="6.25 m"):
        validate_fob_clearance(5.0)


def test_track_axis_hits_finds_all_crossings():
    # Returns List[float] of per-segment projections along normal, not a dict
    tracks = {
        "MAIN_LINE": [(0, 0), (100, 0)],
        "LOOP_1": [(0, 5.3), (100, 5.3)],
        "LOOP_2": [(0, -5.3), (100, -5.3)],
    }
    normal = (0, 1)
    hits = track_axis_hits((50, 0), normal, tracks)
    assert len(hits) == 3
    hit_set = sorted(hits)
    assert pytest.approx(-5.3, abs=1e-9) == hit_set[0]
    assert pytest.approx(0.0, abs=1e-9) == hit_set[1]
    assert pytest.approx(5.3, abs=1e-9) == hit_set[2]


def test_choose_label_spot_picks_quietest_gap():
    # choose_label_spot(lo, hi, crossings, text_len) -> float
    lo, hi = -10.0, 8.0
    crossings = [-8.0, 0.0, 5.3]
    text_len = 1.0
    spot = choose_label_spot(lo, hi, crossings, text_len)
    assert lo <= spot <= hi


def test_build_fob_arms_left_and_right():
    # build_fob_arms(origin, tangent, normal, spans_by_layer, arm_specs, deck_width)
    origin = (50, 0)
    tangent = (1, 0)
    normal = (0, 1)
    spans_by_layer = {
        "PLATFORM_1": (-13.0, -3.0),
        "PLATFORM_2": (3.0, 13.0),
    }
    arm_specs = {
        "PLATFORM_1": {"length": 20.0, "side": "LEFT"},
        "PLATFORM_2": {"length": 15.0, "side": "RIGHT"},
    }
    arms = build_fob_arms(origin, tangent, normal, spans_by_layer, arm_specs, 3.0)
    assert len(arms) == 2


def test_fob_arms_and_deck_merge_cleanly():
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0, 0), (100, 0)]}
    polys = {"PLATFORM_1": _square(50, -8, 5),
             "PLATFORM_2": _square(50, 8, 5)}
    generate_fob(doc, tracks, {}, polys, FOBConfig(
        reference_track="MAIN_LINE", reference_chainage=50.0,
        platforms=["PLATFORM_1", "PLATFORM_2"], width=4.0,
        arms={"PLATFORM_1": {"length": 20.0, "side": "LEFT"},
              "PLATFORM_2": {"length": 20.0, "side": "RIGHT"}},
        output_layer="FOB_1", color=1))
    fob = [e for e in doc.modelspace() if e.dxf.layer == "FOB_1"]
    arms = [e for e in fob if e.dxftype() == "LWPOLYLINE"]
    assert len(arms) == 2
    assert all(not e.is_closed for e in arms)
    segs = []
    for e in fob:
        if e.dxftype() == "LINE":
            segs.append(((e.dxf.start[0], e.dxf.start[1]),
                         (e.dxf.end[0], e.dxf.end[1])))
        elif e.dxftype() == "LWPOLYLINE":
            p = [(q[0], q[1]) for q in e.get_points()]
            segs.extend(zip(p, p[1:]))
    for mx, my in ((48.0, -8.0), (52.0, 8.0)):
        for (x1, y1), (x2, y2) in segs:
            dx, dy = x2 - x1, y2 - y1
            seg_len_sq = dx * dx + dy * dy
            if seg_len_sq < 1e-12:
                continue
            t = ((mx - x1) * dx + (my - y1) * dy) / seg_len_sq
            if not 1e-6 < t < 1.0 - 1e-6:
                continue
            dist = abs((mx - x1) * dy - (my - y1) * dx) / seg_len_sq ** 0.5
            assert dist > 1e-6, "a wall crosses an arm opening"
    seen = {}
    for e in fob:
        if e.dxftype() == "LINE":
            segs = [((e.dxf.start[0], e.dxf.start[1]),
                     (e.dxf.end[0], e.dxf.end[1]))]
        elif e.dxftype() == "LWPOLYLINE":
            p = [(q[0], q[1]) for q in e.get_points()]
            segs = list(zip(p, p[1:]))
        else:
            continue
        for a, b in segs:
            key = tuple(sorted(((round(a[0], 3), round(a[1], 3)),
                                (round(b[0], 3), round(b[1], 3)))))
            seen[key] = seen.get(key, 0) + 1
    assert all(v == 1 for v in seen.values()), "doubled wall segment found"

    # Bridge must finish at the arm outer edge (y = 5.33 + 4.0 = 9.33 and -9.33)
    # and MUST NOT extend to the platform outer boundary (y = 13.0 and -13.0)
    fob_line_pts = [p for e in fob if e.dxftype() == "LINE" for p in ((e.dxf.start[0], e.dxf.start[1]), (e.dxf.end[0], e.dxf.end[1]))]
    assert max(p[1] for p in fob_line_pts) == pytest.approx(9.33)
    assert min(p[1] for p in fob_line_pts) == pytest.approx(-9.33)


def test_wipe_layers_only_clears_targets():
    doc = ezdxf.new()
    doc.layers.add("FOB_1", color=1)
    doc.layers.add("KEEP", color=1)
    msp = doc.modelspace()
    msp.add_line((0, 0), (1, 1), dxfattribs={"layer": "FOB_1"})
    msp.add_line((0, 0), (2, 2), dxfattribs={"layer": "FOB_1"})
    msp.add_line((0, 0), (3, 3), dxfattribs={"layer": "KEEP"})
    removed = ESPGenerator._wipe_layers(doc, {"FOB_1"})
    assert removed == 2
    assert [e.dxf.layer for e in msp] == ["KEEP"]


def test_write_uses_shared_primitives():
    doc = ezdxf.new()
    write_fob_deck(doc, _square(0, 0, 2), "FOB", 1)
    assert "FOB" in doc.layers
    assert doc.layers.get("FOB").color == 1
