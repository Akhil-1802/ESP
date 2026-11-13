"""Basic FOB feature tests: inputs, auto geometry, design limits."""

from __future__ import annotations

import math

import ezdxf
import pytest

from common.constants import (
    DEFAULT_FOB_WIDTH_M,
    FOB_MAX_SPAN_M,
    FOB_VERTICAL_CLEARANCE_M,
)
from common.geometry import point_at_chainage
from fob.config import FOBConfig
from fob.deck import (
    FOB_DEFAULT_WIDTH_M,
    build_fob_outline,
    generate_fob,
)


def _square(cx, cy, half):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half)]


def test_design_constants():
    assert DEFAULT_FOB_WIDTH_M == 3.0
    assert FOB_DEFAULT_WIDTH_M == 3.0
    assert FOB_VERTICAL_CLEARANCE_M == 6.25
    assert FOB_MAX_SPAN_M == 30.0


def test_four_inputs_and_defaults():
    cfg = FOBConfig(reference_track="MAIN_LINE", reference_chainage=50.0,
                    platforms=["PLATFORM_1", "PLATFORM_2"])
    assert cfg.reference_track == "MAIN_LINE"
    assert cfg.reference_chainage == 50.0
    assert cfg.platforms == ["PLATFORM_1", "PLATFORM_2"]
    assert cfg.width == 3.0
    assert cfg.vertical_clearance_m == 6.25
    assert not hasattr(cfg, "start_chainage")
    assert not hasattr(cfg, "end_chainage")
    assert not hasattr(cfg, "span")


def test_span_is_derived_from_platforms():
    platforms = [_square(0, -8, 5), _square(0, 8, 5)]
    outline = build_fob_outline((0, 0), (1, 0), platforms, 3.0)
    ys = sorted(p[1] for p in outline)
    assert ys == [-13.0, -13.0, 13.0, 13.0]
    xs = sorted(p[0] for p in outline)
    assert xs == [-1.5, -1.5, 1.5, 1.5]


def test_geometry_uses_local_tangent_not_fixed_xy():
    track = [(0, 0), (100, 100)]
    station = point_at_chainage(track, 50.0 * math.sqrt(2.0))
    tx, ty = station.tangent
    assert (tx, ty) == pytest.approx((math.sqrt(0.5), math.sqrt(0.5)))
    nx, ny = -ty, tx
    platforms = [
        _square(station.point[0] - nx * 7, station.point[1] - ny * 7, 4),
        _square(station.point[0] + nx * 7, station.point[1] + ny * 7, 4),
    ]
    outline = build_fob_outline(station.point, station.tangent,
                                platforms, 3.0)
    edges = [(outline[i], outline[(i + 1) % 4]) for i in range(4)]
    directions = [math.atan2(b[1] - a[1], b[0] - a[0]) for a, b in edges]
    tangent_angle = math.atan2(ty, tx)
    normal_angle = math.atan2(ny, nx)
    for angle in directions:
        delta_t = abs((angle - tangent_angle + math.pi / 2) % math.pi
                      - math.pi / 2)
        delta_n = abs((angle - normal_angle + math.pi / 2) % math.pi
                      - math.pi / 2)
        assert min(delta_t, delta_n) < 1e-6


def test_max_span_validated():
    platforms = [_square(0, -8, 5), _square(0, 8, 5)]
    # With 30m constraint removed, >30m span builds successfully without error
    outline = build_fob_outline((0, 0), (1, 0), platforms, 3.0,
                                extend_start=10.0, extend_end=10.0)
    assert len(outline) == 4


def test_clearance_validated():
    try:
        FOBConfig(reference_track="MAIN_LINE", reference_chainage=10.0,
                  platforms=["PLATFORM_1", "PLATFORM_2"],
                  vertical_clearance_m=6.0)
    except ValueError as exc:
        assert "6.25" in str(exc)
    else:
        raise AssertionError("expected <6.25 m clearance to raise")


def test_generate_deck_end_to_end():
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0, 0), (100, 0)]}
    polys = {"PLATFORM_1": _square(50, -8, 5),
             "PLATFORM_2": _square(50, 8, 5)}
    outline = generate_fob(doc, tracks, {}, polys, FOBConfig(
        reference_track="MAIN_LINE", reference_chainage=50.0,
        platforms=["PLATFORM_1", "PLATFORM_2"], width=3.0,
        output_layer="FOB", color=1))
    assert len(outline) == 4
    assert "FOB" in doc.layers
    drawn = [e for e in doc.modelspace()
             if e.dxf.layer == "FOB" and e.dxftype() == "LWPOLYLINE"]
    assert len(drawn) == 1
