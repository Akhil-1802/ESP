"""Tests for RDSO / Indian Railways Broad Gauge turnout parameters and radii."""

from __future__ import annotations

from app.features.drawing_generation.domain.track.turnouts import (
    BG_1_8_5_LEAD_RADIUS_M,
    BG_1_8_5_LEAD_RADIUS_MM,
    BG_1_8_5_MIN_LEAD_RADIUS_M,
    BG_1_8_5_MIN_LEAD_RADIUS_MM,
    BG_1_12_LEAD_RADIUS_M,
    BG_1_12_LEAD_RADIUS_MM,
    BG_1_12_MIN_LEAD_RADIUS_M,
    BG_1_12_MIN_LEAD_RADIUS_MM,
    BG_TURN_IN_CURVE_MIN_RADIUS_M,
    BG_TURN_IN_CURVE_REDUCED_RADIUS_M,
    get_turnout_parameters,
    select_turnout,
)


def test_turnout_radii_constants():
    """Verify official RDSO and IRPWM turnout radii and turn-in curve constants."""
    assert BG_1_12_LEAD_RADIUS_M == 441.36
    assert BG_1_12_LEAD_RADIUS_MM == 441_360.0
    assert BG_1_12_MIN_LEAD_RADIUS_M == 410.0
    assert BG_1_12_MIN_LEAD_RADIUS_MM == 410_000.0

    assert BG_1_8_5_LEAD_RADIUS_M == 232.26
    assert BG_1_8_5_LEAD_RADIUS_MM == 232_260.0
    assert BG_1_8_5_MIN_LEAD_RADIUS_M == 218.0
    assert BG_1_8_5_MIN_LEAD_RADIUS_MM == 218_000.0

    assert BG_TURN_IN_CURVE_MIN_RADIUS_M == 350.0
    assert BG_TURN_IN_CURVE_REDUCED_RADIUS_M == 220.0


def test_1_12_turnouts_have_rdso_radius():
    """All standard 1:12 variants must use RDSO T-4218 / T-4732 R=441.36m."""
    t_60kg = get_turnout_parameters("1:12", "60kg")
    assert t_60kg.radius_mm == 441_360.0
    assert "RDSO T-4218" in t_60kg.source_citation

    t_52kg = get_turnout_parameters("1:12", "52kg")
    assert t_52kg.radius_mm == 441_360.0
    assert "RDSO T-4732" in t_52kg.source_citation

    t_std = select_turnout("1:12")
    assert t_std.radius_mm == 441_360.0

    t_min = get_turnout_parameters("1:12", "410m")
    assert t_min.radius_mm == 410_000.0


def test_1_8_5_turnouts_have_rdso_radius():
    """Standard 1:8.5 variants must use RDSO T-4865 R=232.26m."""
    t_std = get_turnout_parameters("1:8.5", "standard")
    assert t_std.radius_mm == 232_260.0
    assert "RDSO T-4865" in t_std.source_citation

    t_sel = select_turnout("1:8.5")
    assert t_sel.radius_mm == 232_260.0

    t_218m = get_turnout_parameters("1:8.5", "218m")
    assert t_218m.radius_mm == 218_000.0
