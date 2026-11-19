"""Tests for Gradient Annotation feature."""

import pytest
from app.features.drawing_generation.pipeline.steps.gradient_reference import (
    compute_gradient_offset,
    format_chainage_display,
    parse_chainage_val,
)


def test_parse_chainage_val():
    num, unit = parse_chainage_val("125.400")
    assert num == pytest.approx(125.4)
    assert unit is None

    num, unit = parse_chainage_val("125.400 KM")
    assert num == pytest.approx(125.4)
    assert unit == "KM"

    num, unit = parse_chainage_val("CH: 125.400 KM")
    assert num == pytest.approx(125.4)
    assert unit == "KM"

    num, unit = parse_chainage_val("KM: 125.400")
    assert num == pytest.approx(125.4)
    assert unit is None

    num, unit = parse_chainage_val("125+400")
    assert num == pytest.approx(125400.0)
    assert unit == "M"

    num, unit = parse_chainage_val("500 M")
    assert num == pytest.approx(500.0)
    assert unit == "M"

    with pytest.raises(ValueError):
        parse_chainage_val("")


def test_compute_gradient_offset():
    # Equal chainages
    assert compute_gradient_offset("125.000", "125.000") == pytest.approx(0.0)
    assert compute_gradient_offset("125", "125") == pytest.approx(0.0)

    # Greater chainage (ahead of station center)
    assert compute_gradient_offset("125.400", "125.000") == pytest.approx(400.0)
    assert compute_gradient_offset("125.400 KM", "125 KM") == pytest.approx(400.0)

    # Lesser chainage (behind station center)
    assert compute_gradient_offset("124.700", "125.000") == pytest.approx(-300.0)
    assert compute_gradient_offset("124.700 KM", "125.000 KM") == pytest.approx(-300.0)

    # Station center 0, gradient in meters
    assert compute_gradient_offset("350 M", "0") == pytest.approx(350.0)

    # Yard chainages in meters (e.g. gradient 400, station 350 -> +50 m)
    assert compute_gradient_offset("400", "350") == pytest.approx(50.0)
    assert compute_gradient_offset("400.000", "350.000") == pytest.approx(50.0)
    assert compute_gradient_offset("400.000", "375.000") == pytest.approx(25.0)
    assert compute_gradient_offset("300", "350") == pytest.approx(-50.0)


def test_format_chainage_display():
    assert format_chainage_display("125.400") == "CH: 125.400 KM"
    assert format_chainage_display("125.4") == "CH: 125.400 KM"
    assert format_chainage_display("125+400") == "CH: 125.400 KM"
    assert format_chainage_display("450 M") == "CH: 450.00 M"
