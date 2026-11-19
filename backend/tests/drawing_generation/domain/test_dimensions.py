"""Tests for entity width dimensions: Platform, FOB deck, and Platform arms."""

from __future__ import annotations

import math

import ezdxf
import pytest
from app.features.drawing_generation.domain.bridges.fob.config import FOBConfig
from app.features.drawing_generation.domain.bridges.fob.deck import generate_fob
from app.features.drawing_generation.domain.platform.config import (
    PlatformConfig,
    PlatformSide,
    PlatformType,
)
from app.features.drawing_generation.domain.platform.generator import PlatformGenerator
from app.features.drawing_generation.domain.platform.side import side_platform
from app.features.drawing_generation.domain.platform.track import Track
from app.features.drawing_generation.formats.dxf.primitives import draw_arrow_dimension


def _make_track(length=1000.0, name="MAIN_LINE"):
    pts = [(0.0, 0.0), (length, 0.0)]
    return Track(name=name, points=pts)


@pytest.mark.parametrize('angle', [-25, 12, 145])
def test_platform_caption_parallel_to_platform_on_generation(angle):
    from app.features.drawing_generation.formats.dxf.platform_io import write_platform
    a = math.radians(angle)
    track = Track(name='MAIN_LINE', points=[(0, 0), (1000*math.cos(a), 1000*math.sin(a))])
    cfg = PlatformConfig(source_dxf='', output_dxf='', track_layer='MAIN_LINE',
                         platform_type=PlatformType.SIDE, side=PlatformSide.LEFT,
                         platform_width=7, clearance=1.68, platform_length=550,
                         center_on_track=True, center_chainage=500)
    result = side_platform(track, cfg)
    doc = ezdxf.new('R2010')
    write_platform(doc, result, cfg)
    caption = doc.modelspace().query('MTEXT')[0]
    assert math.sin(math.radians(caption.get_rotation()-angle)) == pytest.approx(0, abs=1e-8)
    assert caption.has_xdata('ESP_LABEL')


def test_station_centered_platform_keeps_fixed_chainage_with_survey_noise():
    track = Track(
        name="LOOP_1",
        points=[
            (0.0, 0.0),
            (250.0, 0.04),
            (500.0, -0.03),
            (750.0, 0.05),
            (1000.0, 0.0),
        ],
    )
    cfg = PlatformConfig(
        source_dxf="", output_dxf="", track_layer="LOOP_1",
        platform_type=PlatformType.SIDE, side=PlatformSide.LEFT,
        platform_width=8.5, clearance=1.68, platform_length=550.0,
        center_on_track=True, center_chainage=500.0,
    )

    result = side_platform(track, cfg)

    assert result.computed_length == pytest.approx(550.0)
    assert cfg.resolved_start_chainage(track.length) == pytest.approx(225.0, abs=0.01)
    assert cfg.resolved_end_chainage(track.length) == pytest.approx(775.0, abs=0.01)


def test_platform_generator_prefers_canonical_pipeline_track(tmp_path):
    source = tmp_path / "tracks.dxf"
    doc = ezdxf.new("R2010")
    doc.layers.add("LOOP_1")
    # Deliberately curved drawing entity: the pipeline's canonical track below
    # is the authoritative geometry and must be used instead.
    doc.modelspace().add_lwpolyline(
        [(0.0, 0.0), (250.0, 80.0), (500.0, 0.0), (750.0, -80.0), (1000.0, 0.0)],
        dxfattribs={"layer": "LOOP_1"},
    )
    doc.saveas(source)
    cfg = PlatformConfig(
        source_dxf=str(source), output_dxf=str(tmp_path / "out.dxf"),
        track_layer="LOOP_1", platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT, platform_width=8.5, clearance=1.68,
        platform_length=550.0, center_on_track=True, center_chainage=500.0,
    )

    result, _ = PlatformGenerator(
        cfg,
        track_points={"LOOP_1": [(0.0, 0.0), (1000.0, 0.0)]},
    ).build()

    assert result.computed_length == pytest.approx(550.0)


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
    result = side_platform(track, cfg)
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
    result = side_platform(track, cfg)
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
    result = side_platform(track, cfg)
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
