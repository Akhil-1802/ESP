"""Tests for Dynamic FOB Placement."""

from __future__ import annotations

import math

import ezdxf
import pytest

from common.constants import (
    DEFAULT_FOB_OFFSET_M,
    MAX_FOB_OFFSET_M,
    MIN_FOB_OFFSET_M,
)
from fob.config import FOBConfig
from fob.deck import generate_fob
from fob.placement import (
    calculate_fob_chainage,
    determine_station_edge,
    get_fob_track_position,
    normalize_fob_direction,
    validate_fob_conflicts,
    validate_fob_offset,
)


def _rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def test_fob_offset_validation():
    """Offset must be between 40.0 m and 60.0 m."""
    assert validate_fob_offset(40.0) == 40.0
    assert validate_fob_offset(50.0) == 50.0
    assert validate_fob_offset(60.0) == 60.0

    with pytest.raises(ValueError, match="out of allowed range"):
        validate_fob_offset(39.9)

    with pytest.raises(ValueError, match="out of allowed range"):
        validate_fob_offset(60.1)

    with pytest.raises(ValueError, match="must be a number"):
        validate_fob_offset("invalid")


def test_fob_direction_normalization():
    """Supports INCREASING/DECREASING, FORWARD/BACKWARD, etc."""
    assert normalize_fob_direction("INCREASING") == "INCREASING"
    assert normalize_fob_direction("FORWARD") == "INCREASING"
    assert normalize_fob_direction(1) == "INCREASING"

    assert normalize_fob_direction("DECREASING") == "DECREASING"
    assert normalize_fob_direction("BACKWARD") == "DECREASING"
    assert normalize_fob_direction("REVERSE") == "DECREASING"
    assert normalize_fob_direction(-1) == "DECREASING"

    with pytest.raises(ValueError, match="Invalid FOB direction"):
        normalize_fob_direction("SIDEWAYS")


def test_determine_station_edge_dynamically():
    """Finds actual edge from station/platform geometry without fixed assumptions."""
    track_pts = [(0.0, 0.0), (1000.0, 0.0)]
    station_poly = _rect(480.0, -15.0, 535.0, -5.0)

    edge_inc = determine_station_edge(track_pts, station_poly, direction="INCREASING")
    assert edge_inc == pytest.approx(535.0)

    edge_dec = determine_station_edge(track_pts, station_poly, direction="DECREASING")
    assert edge_dec == pytest.approx(480.0)


def test_determine_station_edge_curved_or_skewed():
    """Works along non-axis-aligned track geometry via projection."""
    track_pts = [(0.0, 0.0), (1000.0 * math.sqrt(0.5), 1000.0 * math.sqrt(0.5))]
    p1 = (100.0 * math.sqrt(0.5), 100.0 * math.sqrt(0.5))
    p2 = (250.0 * math.sqrt(0.5), 250.0 * math.sqrt(0.5))
    poly = [p1, (p1[0] - 5, p1[1] + 5), (p2[0] - 5, p2[1] + 5), p2]

    edge_inc = determine_station_edge(track_pts, poly, direction="INCREASING")
    assert edge_inc == pytest.approx(250.0)

    edge_dec = determine_station_edge(track_pts, poly, direction="DECREASING")
    assert edge_dec == pytest.approx(100.0)


def test_calculate_fob_chainage_formula():
    """Increasing: station_edge + offset; Decreasing: station_edge - offset."""
    fob_ch_inc = calculate_fob_chainage(
        station_center=500.0,
        station_edge=540.0,
        direction="INCREASING",
        offset=40.0,
    )
    assert fob_ch_inc == 580.0

    fob_ch_dec = calculate_fob_chainage(
        station_center=500.0,
        station_edge=460.0,
        direction="DECREASING",
        offset=40.0,
    )
    assert fob_ch_dec == 420.0

    fob_ch_custom = calculate_fob_chainage(
        station_center=500.0,
        station_edge=540.0,
        direction="INCREASING",
        offset=55.0,
    )
    assert fob_ch_custom == 595.0


def test_calculate_fob_chainage_from_geometry():
    """calculate_fob_chainage projects geometry dynamically when passed as station_edge."""
    track_pts = [(0.0, 0.0), (1000.0, 0.0)]
    station_poly = _rect(470.0, -10.0, 530.0, -2.0)

    ch_inc = calculate_fob_chainage(
        station_center=500.0,
        station_edge=station_poly,
        direction="INCREASING",
        offset=45.0,
        track_points=track_pts,
    )
    assert ch_inc == pytest.approx(575.0)

    ch_dec = calculate_fob_chainage(
        station_center=500.0,
        station_edge=station_poly,
        direction="DECREASING",
        offset=50.0,
        track_points=track_pts,
    )
    assert ch_dec == pytest.approx(420.0)


def test_get_fob_track_position_uses_tangent_and_normal():
    """Converts calculated FOB chainage back to actual track position, tangent, and normal."""
    track_pts = [(0.0, 0.0), (500.0, 0.0), (500.0, 500.0)]
    origin, tangent, normal = get_fob_track_position(track_pts, 200.0)
    assert origin == pytest.approx((200.0, 0.0))
    assert tangent == pytest.approx((1.0, 0.0))
    assert normal == pytest.approx((0.0, 1.0))

    origin2, tangent2, normal2 = get_fob_track_position(track_pts, 700.0)
    assert origin2 == pytest.approx((500.0, 200.0))
    assert tangent2 == pytest.approx((0.0, 1.0))
    assert normal2 == pytest.approx((-1.0, 0.0))


def test_validate_fob_conflicts_reporting():
    """Reports conflicts with platforms, track limits, and restricted areas instead of silent moves."""
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)]}
    platforms = {
        "PLATFORM_1": _rect(400.0, -12.0, 600.0, -5.0),
        "PLATFORM_2": _rect(400.0, 5.0, 600.0, 12.0),
    }

    validate_fob_conflicts(
        fob_chainage=550.0,
        fob_width=3.0,
        reference_track="MAIN_LINE",
        tracks=tracks,
        platform_polygons=platforms,
        connected_platforms=["PLATFORM_1", "PLATFORM_2"],
    )

    with pytest.raises(ValueError, match="misses connected platform"):
        validate_fob_conflicts(
            fob_chainage=650.0,
            fob_width=3.0,
            reference_track="MAIN_LINE",
            tracks=tracks,
            platform_polygons=platforms,
            connected_platforms=["PLATFORM_1", "PLATFORM_2"],
        )

    with pytest.raises(ValueError, match="exceeds track"):
        validate_fob_conflicts(
            fob_chainage=1100.0,
            fob_width=3.0,
            reference_track="MAIN_LINE",
            tracks=tracks,
            platform_polygons=platforms,
            connected_platforms=["PLATFORM_1", "PLATFORM_2"],
        )

    station_bldg = _rect(480.0, -15.0, 520.0, 15.0)
    with pytest.raises(ValueError, match="overlaps station building footprint"):
        validate_fob_conflicts(
            fob_chainage=500.0,
            fob_width=3.0,
            reference_track="MAIN_LINE",
            tracks=tracks,
            platform_polygons=platforms,
            connected_platforms=["PLATFORM_1", "PLATFORM_2"],
            station_polygons=[station_bldg],
        )


def test_dynamic_fob_end_to_end_generation():
    """FOB generated dynamically with offset 40m from station edge."""
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(400.0, -12.0, 650.0, -5.0),
        "PLATFORM_2": _rect(400.0, 5.0, 650.0, 12.0),
        "STATION-BUILDING": _rect(480.0, -22.0, 520.0, -12.0),
    }
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        platforms=["PLATFORM_1", "PLATFORM_2"],
        offset=40.0,
        direction="INCREASING",
        width=3.0,
        output_layer="FOB_DYNAMIC",
    )
    outline = generate_fob(doc, tracks, {}, polys, cfg)
    assert cfg.fob_chainage == pytest.approx(561.5)
    xs = [p[0] for p in outline]
    assert min(xs) == pytest.approx(520.0 + 40.0)
    assert max(xs) == pytest.approx(520.0 + 40.0 + 3.0)


def test_fob_placement_main_center_offset_increasing():
    """With explicit reference chainage and station building, offset is applied from station edge."""
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(700.0, -12.0, 1000.0, -5.0),
        "PLATFORM_2": _rect(700.0, 5.0, 1000.0, 12.0),
        "STATION-BUILDING": _rect(811.712, -22.0, 851.712, -12.0),
    }
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        reference_chainage=831.712,
        platforms=["PLATFORM_1", "PLATFORM_2"],
        offset=40.0,
        direction="INCREASING",
        width=3.0,
        output_layer="FOB_INC",
    )
    outline = generate_fob(doc, tracks, {}, polys, cfg)
    assert cfg.fob_chainage == pytest.approx(893.212)
    xs = [p[0] for p in outline]
    assert min(xs) == pytest.approx(851.712 + 40.0)
    assert max(xs) == pytest.approx(851.712 + 40.0 + 3.0)


def test_fob_placement_main_center_offset_decreasing():
    """With explicit reference chainage and station building, offset is applied from station edge (decreasing)."""
    doc = ezdxf.new()
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(700.0, -12.0, 1000.0, -5.0),
        "PLATFORM_2": _rect(700.0, 5.0, 1000.0, 12.0),
        "STATION-BUILDING": _rect(811.712, -22.0, 851.712, -12.0),
    }
    cfg = FOBConfig(
        reference_track="MAIN_LINE",
        reference_chainage=831.712,
        platforms=["PLATFORM_1", "PLATFORM_2"],
        offset=40.0,
        direction="DECREASING",
        width=3.0,
        output_layer="FOB_DEC",
    )
    outline = generate_fob(doc, tracks, {}, polys, cfg)
    assert cfg.fob_chainage == pytest.approx(770.212)
    xs = [p[0] for p in outline]
    assert max(xs) == pytest.approx(811.712 - 40.0)
    assert min(xs) == pytest.approx(811.712 - 40.0 - 3.0)


def test_fob_validation_at_final_chainage_avoids_station_overlap():
    """Conflict validation must check the final FOB chainage, not the datum where station building sits."""
    tracks = {"MAIN_LINE": [(0.0, 0.0), (1500.0, 0.0)]}
    polys = {
        "PLATFORM_1": _rect(700.0, -12.0, 1000.0, -5.0),
        "PLATFORM_2": _rect(700.0, 5.0, 1000.0, 12.0),
    }
    station_polys = [_rect(811.712, -22.0, 851.712, -12.0)]
    final_fob_ch = 891.712

    validate_fob_conflicts(
        fob_chainage=final_fob_ch,
        fob_width=3.0,
        reference_track="MAIN_LINE",
        tracks=tracks,
        platform_polygons=polys,
        connected_platforms=["PLATFORM_1", "PLATFORM_2"],
        station_polygons=station_polys,
    )

    with pytest.raises(ValueError, match="conflicts with/overlaps station building footprint"):
        validate_fob_conflicts(
            fob_chainage=831.712,
            fob_width=3.0,
            reference_track="MAIN_LINE",
            tracks=tracks,
            platform_polygons=polys,
            connected_platforms=["PLATFORM_1", "PLATFORM_2"],
            station_polygons=station_polys,
        )
