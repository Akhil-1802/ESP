"""Platform overlap validation: outlines, stairs and track centrelines."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.features.drawing_generation.config import ESPConfig, PlatformRequest
from app.features.drawing_generation.domain.platform.config import PlatformConfig
from app.features.drawing_generation.domain.track.specs import LineSpec
from app.features.drawing_generation.pipeline.generator import ESPGenerator
from app.features.drawing_generation.pipeline.steps.platform import (
    _footprints_strict_overlap,
    _point_strictly_inside,
    _segments_properly_cross,
)

ROOT = Path(__file__).resolve().parent / "fixtures"


def _square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def test_proper_crossing_ignores_touching_and_collinear():
    assert _segments_properly_cross((0, 0), (10, 10), (0, 10), (10, 0))
    assert not _segments_properly_cross((0, 0), (10, 0), (10, 0), (10, 10))
    assert not _segments_properly_cross((0, 0), (10, 0), (5, 0), (15, 0))
    assert not _segments_properly_cross((0, 0), (10, 0), (0, 5), (10, 5))


def test_strict_inside_ignores_boundary():
    ring = _square(0, 0, 10, 10)
    assert _point_strictly_inside(ring, (5, 5))
    assert not _point_strictly_inside(ring, (15, 5))
    assert not _point_strictly_inside(ring, (10, 5))
    assert not _point_strictly_inside(ring, (10 + 1e-7, 5))


def test_strict_footprint_overlap():
    assert _footprints_strict_overlap(_square(0, 0, 10, 10), _square(5, 5, 15, 15))
    assert not _footprints_strict_overlap(_square(0, 0, 10, 10), _square(10, 0, 20, 10))
    assert not _footprints_strict_overlap(_square(0, 0, 10, 10), _square(20, 20, 30, 30))
    assert _footprints_strict_overlap(_square(0, 0, 10, 10), _square(-5, 4.9, 15, 5.1))


def _platform_request(tmp_path, layer, track, side, start, end, stairs=None):
    cfg = PlatformConfig(
        source_dxf=str(tmp_path / "src.dxf"),
        output_dxf=str(tmp_path / "out.dxf"),
        track_layer=track,
        platform_type="SIDE",
        side=side,
        center_on_track=False,
        start_chainage=start,
        end_chainage=end,
        platform_length=None,
        clearance=1.68,
        platform_width=8.5,
        output_layer=layer,
        text_layer=f"{layer}_TEXT",
    )
    if stairs is not None:
        cfg.stair_length = stairs
    return PlatformRequest(track, cfg)


def _base_config(tmp_path, platforms, lines=None):
    return ESPConfig(
        source_path=str(ROOT / "ESP.kml"),
        output_dxf=str(tmp_path / "out.dxf"),
        track_source_layer="MAIN_TRACK",
        additional_lines=lines or [],
        platforms=platforms,
    )


def test_platform_across_track_is_rejected(tmp_path):
    lines = [LineSpec(name="PROPOSED_LINE_1", spacing=5.3, side="LEFT")]
    platforms = [_platform_request(
        tmp_path, "PLATFORM_1", "PROPOSED_LINE_1", "RIGHT", 400.0, 500.0)]
    with pytest.raises(ValueError, match="covers track"):
        ESPGenerator(_base_config(tmp_path, platforms, lines)).run()


def test_platform_stairs_into_neighbour_are_rejected(tmp_path):
    platforms = [
        _platform_request(tmp_path, "PLATFORM_1", "MAIN_LINE", "LEFT", 0.0, 100.0, stairs=10.0),
        _platform_request(tmp_path, "PLATFORM_2", "MAIN_LINE", "LEFT", 105.0, 200.0),
    ]
    with pytest.raises(ValueError, match="stairs"):
        ESPGenerator(_base_config(tmp_path, platforms)).run()


def test_clear_outer_platform_is_accepted(tmp_path):
    lines = [LineSpec(name="PROPOSED_LINE_1", spacing=5.3, side="LEFT")]
    platforms = [_platform_request(
        tmp_path, "PLATFORM_1", "PROPOSED_LINE_1", "LEFT", 400.0, 500.0, stairs=10.0)]
    ESPGenerator(_base_config(tmp_path, platforms, lines)).run()


def test_platform_centers_on_station_point(tmp_path):
    cfg = PlatformConfig(
        source_dxf=str(tmp_path / "src.dxf"),
        output_dxf=str(tmp_path / "out.dxf"),
        track_layer="MAIN_LINE",
        platform_type="SIDE",
        side="LEFT",
        center_on_track=True,
        station_index=0,
        platform_length=400.0,
        clearance=1.68,
        platform_width=8.5,
        output_layer="PLATFORM_1",
        text_layer="PLATFORM_1_TEXT",
    )
    esp_cfg = ESPConfig(
        source_path=str(ROOT / "ESP.kml"),
        output_dxf=str(tmp_path / "out.dxf"),
        track_source_layer="MAIN_TRACK",
        station_markers=[{"name": "DELHI", "km": 1, "m": 0}],
        platforms=[PlatformRequest("MAIN_LINE", cfg)],
    )
    ESPGenerator(esp_cfg).run()

    # Verify that the generated platform was centered on the station (station at 1000m, length 400m -> start 800m, end 1200m)
    assert cfg.center_chainage is not None
    assert abs(cfg.center_chainage - 1000.0) < 5.0
    assert abs(cfg.resolved_start_chainage(5000.0) - 800.0) < 5.0
    assert abs(cfg.resolved_end_chainage(5000.0) - 1200.0) < 5.0
