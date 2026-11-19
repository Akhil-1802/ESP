"""Tests for configurable platform arm length, stair geometry, and FOB vertical text."""

from __future__ import annotations

import ezdxf
import pytest
from app.features.drawing_generation.domain.bridges.fob.config import FOBConfig
from app.features.drawing_generation.domain.bridges.fob.deck import generate_fob
from app.features.drawing_generation.domain.constants import (
    DEFAULT_PLATFORM_ARM_LENGTH_M,
)
from app.features.drawing_generation.domain.platform.config import (
    PlatformConfig,
    PlatformSide,
    PlatformType,
)
from app.features.drawing_generation.domain.platform.side import side_platform
from app.features.drawing_generation.domain.platform.track import Track
from app.features.drawing_generation.domain.track.crossover.conflicts import (
    platforms_to_restricted_regions,
)


def _make_track(length=1000.0, name="MAIN_LINE"):
    pts = [(0.0, 0.0), (length, 0.0)]
    return Track(name=name, points=pts)


def _rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def test_default_platform_arm_length_constant():
    """Default platform arm length must be 16.999 m."""
    assert DEFAULT_PLATFORM_ARM_LENGTH_M == 16.999


def test_platform_arm_length_configurable():
    """User can configure platform arm length or use default 16.999 m."""
    cfg_default = PlatformConfig(
        source_dxf="", output_dxf="", track_layer="MAIN_LINE",
    )
    assert cfg_default.effective_arm_length == 16.999

    cfg_custom = PlatformConfig(
        source_dxf="", output_dxf="", track_layer="MAIN_LINE",
        arm_length=25.0,
    )
    assert cfg_custom.arm_length == 25.0
    assert cfg_custom.effective_arm_length == 25.0
    assert cfg_custom.stair_length == 25.0

    cfg_stair = PlatformConfig(
        source_dxf="", output_dxf="", track_layer="MAIN_LINE",
        stair_length=18.5,
    )
    assert cfg_stair.effective_arm_length == 18.5
    assert cfg_stair.arm_length == 18.5


def test_platform_geometry_uses_configured_arm_length():
    """side_platform generates stairs of exactly the configured arm length."""
    track = _make_track(length=1000.0)
    arm_len = 16.999
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=8.5,
        clearance=1.68,
        start_chainage=200.0,
        platform_length=400.0,
        center_on_track=False,
        arm_length=arm_len,
    )
    result = side_platform(track, cfg)
    assert len(result.stairs) == 2

    left_stair = result.stairs[0]
    xs_left = [p[0] for p in left_stair.outline]
    stair_measured_len = max(xs_left) - min(xs_left)
    assert stair_measured_len == pytest.approx(arm_len)

    right_stair = result.stairs[1]
    xs_right = [p[0] for p in right_stair.outline]
    stair_measured_len_r = max(xs_right) - min(xs_right)
    assert stair_measured_len_r == pytest.approx(arm_len)


def test_platform_arm_length_custom_override():
    """Overriding arm length to custom 12.5 m correctly updates stair geometry."""
    track = _make_track(length=1000.0)
    custom_len = 12.5
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=8.5,
        clearance=1.68,
        start_chainage=200.0,
        platform_length=400.0,
        center_on_track=False,
        arm_length=custom_len,
    )
    result = side_platform(track, cfg)
    xs_left = [p[0] for p in result.stairs[0].outline]
    assert max(xs_left) - min(xs_left) == pytest.approx(custom_len)


def test_platform_without_arm_stairs_preserved():
    """When arm_length / stair_length is not specified, no stairs are generated."""
    track = _make_track(length=1000.0)
    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        platform_width=8.5,
        clearance=1.68,
        start_chainage=200.0,
        platform_length=400.0,
        center_on_track=False,
    )
    result = side_platform(track, cfg)
    assert len(result.stairs) == 0


def test_crossover_restrictions_account_for_configured_arm_length():
    """platforms_to_restricted_regions uses the configured platform arm length."""
    class MockPlatformReq:
        def __init__(self, cfg):
            self.track_layer = "MAIN_LINE"
            self.config = cfg

    cfg = PlatformConfig(
        source_dxf="", output_dxf="",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        start_chainage=200.0,
        platform_length=400.0,
        center_on_track=False,
        arm_length=16.999,
        output_layer="PLATFORM_1",
    )
    req = MockPlatformReq(cfg)
    tracks_pts = {"MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)]}
    regions = platforms_to_restricted_regions([req], tracks_pts)
    assert len(regions) == 1
    assert regions[0].start_chainage == pytest.approx(200.0 - 16.999)
    assert regions[0].end_chainage == pytest.approx(600.0 + 16.999)


def test_fob_text_aligned_vertically():
    """FOB label text entity must be aligned vertically (rotation == 90.0 degrees)."""
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(400.0, -12.0, 650.0, -5.0),
        "PLATFORM_2": _rect(400.0, 5.0, 650.0, 12.0),
    }
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        reference_chainage=500.0,
        platforms=["PLATFORM_1", "PLATFORM_2"],
        width=3.0,
        output_layer="FOB_TEST",
    )
    generate_fob(doc, tracks, {}, polys, cfg)

    fob_texts = [
        e for e in doc.modelspace()
        if e.dxftype() == "TEXT" and "FOOT OVER BRIDGE" in str(e.dxf.text)
    ]
    assert len(fob_texts) >= 1
    assert fob_texts[0].dxf.rotation == pytest.approx(90.0)


def test_platform_default_label_high_level_passenger_platform():
    """PlatformConfig default platform_name must be HIGH LEVEL PASSENGER PLATFORM."""
    cfg = PlatformConfig(
        source_dxf="", output_dxf="", track_layer="MAIN_LINE",
    )
    assert cfg.platform_name == "HIGH LEVEL PASSENGER PLATFORM"

    track = _make_track(length=1000.0)
    result = side_platform(track, cfg)
    assert len(result.labels) >= 1
    assert "HIGH LEVEL PASSENGER PLATFORM" in result.labels[0].text


def test_fob_reference_chainage_defaults_to_main_center():
    """FOBConfig defaults reference_chainage to MAIN_CENTER and places at track midpoint."""
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        platforms=["PLATFORM_1", "PLATFORM_2"],
    )
    assert cfg.reference_chainage == "MAIN_CENTER"

    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(400.0, -12.0, 650.0, -5.0),
        "PLATFORM_2": _rect(400.0, 5.0, 650.0, 12.0),
    }
    generate_fob(doc, tracks, {}, polys, cfg)
    assert cfg.reference_chainage == pytest.approx(525.0)
