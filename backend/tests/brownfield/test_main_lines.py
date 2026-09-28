"""Unit tests for Brownfield MAIN_LINE addition with explicit reference tracks."""

from __future__ import annotations

import math
from pathlib import Path
import ezdxf
import pytest

from brownfield import (
    BrownfieldGenerator,
    BrownfieldLayout,
    BrownfieldMainLineBuilder,
    BrownfieldMainLineSpec,
    compute_perpendicular_offset,
)


def test_add_single_main_line_with_reference_track():
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("MAIN_LINE", points=[(0, 0), (1000, 0)], direction="UP")
    builder.add_main_line(
        name="MAIN_LINE_1",
        reference_track="MAIN_LINE",
        spacing=5.3,
        side="LEFT",
        direction="DN",
    )

    layout = builder.build()

    assert len(layout.tracks) == 2
    assert "MAIN_LINE" in layout
    assert "MAIN_LINE_1" in layout

    m1 = layout["MAIN_LINE_1"]
    assert m1.reference_track == "MAIN_LINE"
    assert m1.spacing_from_reference == 5.3
    assert m1.side == "LEFT"
    assert m1.direction == "DN"
    assert m1.points == [(0.0, 5.3), (1000.0, 5.3)]

    assert len(layout.relationships) == 1
    rel = layout.relationships[0]
    assert rel.track_name == "MAIN_LINE_1"
    assert rel.reference_track == "MAIN_LINE"
    assert rel.spacing == 5.3
    assert rel.side == "LEFT"


def test_chained_main_lines_resolved_topologically():
    """Verify that tracks referencing other newly added tracks resolve properly."""
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("MAIN_1", points=[(0, 0), (500, 0)], direction="UP")

    # Pass in reverse order to ensure topological sorting works
    builder.add_main_line(
        name="MAIN_3",
        reference_track="MAIN_2",
        spacing=5.3,
        side="LEFT",
        direction="UP",
    )
    builder.add_main_line(
        name="MAIN_2",
        reference_track="MAIN_1",
        spacing=5.3,
        side="LEFT",
        direction="DN",
    )

    layout = builder.build()

    assert len(layout.tracks) == 3
    assert layout["MAIN_2"].points == [(0.0, 5.3), (500.0, 5.3)]
    assert layout["MAIN_3"].points == [(0.0, 10.6), (500.0, 10.6)]
    assert layout["MAIN_3"].reference_track == "MAIN_2"


def test_branching_main_lines_both_sides():
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("CENTER_MAIN", points=[(0, 0), (1000, 0)], direction="BOTH")

    builder.add_main_line(
        name="UP_MAIN",
        reference_track="CENTER_MAIN",
        spacing=5.3,
        side="LEFT",
        direction="UP",
    )
    builder.add_main_line(
        name="DN_MAIN",
        reference_track="CENTER_MAIN",
        spacing=5.3,
        side="RIGHT",
        direction="DN",
    )

    layout = builder.build()

    assert layout["UP_MAIN"].points == [(0.0, 5.3), (1000.0, 5.3)]
    assert layout["DN_MAIN"].points == [(0.0, -5.3), (1000.0, -5.3)]


def test_missing_reference_track_raises_error():
    # Model validation error when reference_track is empty
    with pytest.raises(ValueError, match="must specify a reference_track"):
        BrownfieldMainLineSpec(name="MAIN_2", reference_track="")

    builder = BrownfieldMainLineBuilder()
    with pytest.raises(ValueError, match="reference_track must be specified"):
        builder.add_main_line("MAIN_2")

    # Unknown reference track error
    builder.add_base_track("MAIN_1", points=[(0, 0), (100, 0)])
    builder.add_main_line("MAIN_2", reference_track="NON_EXISTENT")
    with pytest.raises(ValueError, match="references unknown track 'NON_EXISTENT'"):
        builder.build()


def test_circular_reference_detected():
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("BASE", points=[(0, 0), (100, 0)])

    # Circular cycle: A -> B and B -> A
    builder.add_main_line("TRACK_A", reference_track="TRACK_B")
    builder.add_main_line("TRACK_B", reference_track="TRACK_A")

    with pytest.raises(ValueError, match="Circular reference dependency detected"):
        builder.build()


def test_self_reference_detected():
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("BASE", points=[(0, 0), (100, 0)])
    builder.add_main_line("TRACK_A", reference_track="TRACK_A")

    with pytest.raises(ValueError, match="cannot have itself as its reference_track"):
        builder.build()


def test_duplicate_track_name_detected():
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("MAIN_1", points=[(0, 0), (100, 0)])
    builder.add_main_line("MAIN_1", reference_track="MAIN_1")

    with pytest.raises(ValueError, match="track already exists in layout"):
        builder.build()


def test_invalid_spacing_and_side():
    with pytest.raises(ValueError, match="spacing must be greater than zero"):
        BrownfieldMainLineSpec(name="M2", reference_track="M1", spacing=0)

    with pytest.raises(ValueError, match="side must be 'LEFT' or 'RIGHT'"):
        BrownfieldMainLineSpec(name="M2", reference_track="M1", side="MIDDLE")


def test_curved_alignment_perpendicular_offset():
    # 90-degree curve: starts at (0, 0) heading +X, turns left to (100, 100) heading +Y
    curve = []
    num_pts = 19
    for i in range(num_pts):
        angle = -math.pi / 2.0 + (math.pi / 2.0) * (i / (num_pts - 1))
        curve.append((100.0 * math.cos(angle), 100.0 + 100.0 * math.sin(angle)))

    offset = compute_perpendicular_offset(curve, spacing=5.3, side="LEFT")

    assert len(offset) == len(curve)
    # Start: normal is roughly +Y -> y approx 5.3
    assert offset[0][1] == pytest.approx(5.3, abs=0.5)
    # End: normal is roughly -X -> x approx 100 - 5.3 = 94.7 (not naive Y shift)
    assert offset[-1][0] == pytest.approx(100.0 - 5.3, abs=0.5)


def test_brownfield_generator_dxf_rendering(tmp_path):
    output_dxf = tmp_path / "brownfield_output.dxf"

    generator = BrownfieldGenerator(output_dxf=str(output_dxf))
    generator.add_base_track("MAIN_LINE", points=[(0, 0), (500, 0)], direction="UP")
    generator.add_main_line(
        BrownfieldMainLineSpec(
            name="MAIN_LINE_1",
            reference_track="MAIN_LINE",
            spacing=5.3,
            side="LEFT",
            direction="DN",
        )
    )

    layout = generator.run()
    assert output_dxf.is_file()

    doc = ezdxf.readfile(str(output_dxf))
    layers = {layer.dxf.name for layer in doc.layers}

    assert "MAIN_LINE" in layers
    assert "MAIN_LINE_1" in layers
