"""Tests for entity width dimensions: Platform, FOB deck, and Platform arms."""

from __future__ import annotations

import ezdxf
import pytest

from common.dxf import draw_arrow_dimension
from fob.config import FOBConfig
from fob.deck import generate_fob
from platform_gen.config import PlatformConfig, PlatformSide, PlatformType
from platform_gen.platform import PlatformGenerator, _island_platform, _side_platform
from platform_gen.track import Track


def _make_track(length=1000.0, name="MAIN_LINE"):
    pts = [(0.0, 0.0), (length, 0.0)]
    return Track(name=name, points=pts)


def test_platform_width_dimension_without_stairs():
    track = _make_track()
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=10.0,
        clearance=1.68,
        start_chainage=100.0,
        platform_length=400.0,
        center_on_track=False,
    )
    result = _side_platform(track, cfg)
    texts = [d.text for d in result.dimensions if d.text]
    assert "10.00" in texts
    assert "1.68" in texts


def test_platform_width_dimension_with_stairs():
    track = _make_track()
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=8.5,
        clearance=1.68,
        start_chainage=100.0,
        platform_length=400.0,
        center_on_track=False,
        stair_length=15.0,
    )
    result = _side_platform(track, cfg)
    texts = [d.text for d in result.dimensions if d.text]
    assert "8.50" in texts
    assert "1.68" in texts


def test_platform_stair_arm_width_when_narrower():
    track = _make_track()
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=10.0,
        stair_width=3.5,
        stair_length=12.0,
        clearance=1.68,
        start_chainage=100.0,
        platform_length=400.0,
        center_on_track=False,
    )
    result = _side_platform(track, cfg)
    texts = [d.text for d in result.dimensions if d.text]
    assert "3.50" in texts
    assert "10.00" in texts
    assert "1.68" in texts


def test_fob_deck_and_arm_width_dimensions():
    def _sq(cx, cy, half):
        return [(cx - half, cy - half), (cx + half, cy - half),
                (cx + half, cy + half), (cx - half, cy + half)]

    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (200.0, 0.0)]}
    polys = {
        "PLATFORM_1": _sq(100.0, -8.0, 5.0),
        "PLATFORM_2": _sq(100.0, 8.0, 5.0),
    }
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        reference_chainage=100.0,
        platforms=["PLATFORM_1", "PLATFORM_2"],
        width=6.0,
        arms={
            "PLATFORM_1": {"length": 20.0, "side": "LEFT"},
            "PLATFORM_2": {"length": 20.0, "side": "RIGHT"},
        },
        output_layer="FOB_1",
        color=1,
    )
    generate_fob(doc, tracks, {}, polys, cfg)

    dim_layer = "FOB_1-DIM"
    dims = [e for e in doc.modelspace()
            if e.dxf.layer == dim_layer and e.dxftype() in ("DIMENSION", "TEXT")]

    assert len(dims) == 3


def test_oblique_ticks_for_entity_widths():
    doc = ezdxf.new("R2010")
    draw_arrow_dimension(doc, (0, 0), (40, 0), 2.0, "40.00", layer="STATION-BUILDING")
    draw_arrow_dimension(doc, (0, 0), (10, 0), 2.0, "10.00", layer="PLATFORM-DIM")
    draw_arrow_dimension(doc, (0, 0), (6, 0), 2.0, "6.00", layer="FOB_1-DIM")
    draw_arrow_dimension(doc, (0, 0), (5.3, 0), 0.0, "T.C=5.3M", layer="TRACK_CENTERS")

    dims = {d.dxf.layer: d for d in doc.modelspace() if d.dxftype() == "DIMENSION"}
    assert len(dims) == 4

    for layer in ("STATION-BUILDING", "PLATFORM-DIM", "FOB_1-DIM", "TRACK_CENTERS"):
        blk = doc.blocks[dims[layer].dxf.geometry]
        inserts = [e.dxf.name for e in blk if e.dxftype() == "INSERT"]
        assert inserts == ["_OBLIQUE", "_OBLIQUE"]
