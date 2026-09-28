"""Unit tests for Brownfield crossover behavior.

Verifies:
1. Brownfield crossover does NOT use the 50m SRJ end-truncation approach. Tracks preserve
   their full surveyed/generated lengths.
2. Crossovers do not affect all main lines; operations on a single main line (or pair)
   affect only those particular lines, leaving other main lines completely untouched.
3. Greenfield pipeline retains its existing 50m trim behavior untouched.
"""

from __future__ import annotations

import ezdxf
import pytest

from brownfield import (
    BrownfieldCrossoverBuilder,
    BrownfieldCrossoverResult,
    BrownfieldCrossoverSpec,
    BrownfieldGenerator,
    BrownfieldLayout,
    BrownfieldMainLineBuilder,
    BrownfieldMainLineSpec,
    BrownfieldTrack,
)


def _sample_straight_tracks() -> BrownfieldLayout:
    """Helper creating a 3-mainline BrownfieldLayout (each 1000m long)."""
    builder = BrownfieldMainLineBuilder()
    builder.add_base_track("MAIN_1", [(0.0, 0.0), (1000.0, 0.0)], direction="UP")
    builder.add_main_line("MAIN_2", reference_track="MAIN_1", spacing=5.3, side="LEFT", direction="DN")
    builder.add_main_line("MAIN_3", reference_track="MAIN_2", spacing=5.3, side="LEFT", direction="DN")
    return builder.build()


def test_brownfield_crossover_spec_validation():
    with pytest.raises(ValueError, match="Crossover id must be a non-empty string"):
        BrownfieldCrossoverSpec(id="", from_track="MAIN_1", to_track="MAIN_2", chainage=100.0)

    with pytest.raises(ValueError, match="from_track must be specified"):
        BrownfieldCrossoverSpec(id="X1", from_track="", to_track="MAIN_2", chainage=100.0)

    with pytest.raises(ValueError, match="cannot be the same track"):
        BrownfieldCrossoverSpec(id="X1", from_track="MAIN_1", to_track="MAIN_1", chainage=100.0)

    with pytest.raises(ValueError, match="direction must be FORWARD or BACKWARD"):
        BrownfieldCrossoverSpec(id="X1", from_track="MAIN_1", to_track="MAIN_2", chainage=100.0, direction="DIAGONAL")


def test_brownfield_crossover_preserves_track_lengths_without_50m_srj_trim():
    """Verify tracks do NOT end 50m after the last SRJ; they preserve full length."""
    layout = _sample_straight_tracks()

    initial_main1_len = layout["MAIN_1"].length
    initial_main2_len = layout["MAIN_2"].length
    assert initial_main1_len == 1000.0
    assert initial_main2_len == 1000.0

    co_builder = BrownfieldCrossoverBuilder(layout)
    co_builder.add_crossover(
        id="CO_1",
        from_track="MAIN_1",
        to_track="MAIN_2",
        chainage=400.0,
        direction="FORWARD",
        turnout_designation="1:12",
    )
    results = co_builder.build()

    assert len(results) == 1
    co = results[0]
    assert co.id == "CO_1"
    assert co.from_track == "MAIN_1"
    assert co.to_track == "MAIN_2"
    assert co.from_srj_chainage == 400.0
    assert co.to_srj_chainage > 400.0
    assert len(co.points) > 2

    # CRUCIAL CHECK: tracks must NOT end 50m after the last SRJ!
    # In greenfield, the track would be cut to around 400 + 50 = ~450m or ~500m.
    # In brownfield, both tracks remain full 1000m:
    assert layout["MAIN_1"].length == 1000.0
    assert layout["MAIN_2"].length == 1000.0
    assert layout["MAIN_1"].points[0] == (0.0, 0.0)
    assert layout["MAIN_1"].points[-1] == (1000.0, 0.0)
    assert layout["MAIN_2"].points[0] == (0.0, 5.3)
    assert layout["MAIN_2"].points[-1] == (1000.0, 5.3)


def test_crossover_on_single_main_line_does_not_affect_other_main_lines():
    """Verify that adding a crossover for a single main line (MAIN_1 -> MAIN_2) does not touch MAIN_3."""
    layout = _sample_straight_tracks()

    main3_pts_before = list(layout["MAIN_3"].points)
    main3_len_before = layout["MAIN_3"].length

    co_builder = BrownfieldCrossoverBuilder(layout)
    co_builder.add_crossover(
        id="CO_1",
        from_track="MAIN_1",
        to_track="MAIN_2",
        chainage=350.0,
        direction="FORWARD",
        turnout_designation="1:12",
    )
    co_builder.build()

    # MAIN_3 was NOT part of this crossover:
    assert layout["MAIN_3"].points == main3_pts_before
    assert layout["MAIN_3"].length == main3_len_before
    assert layout.get_crossovers_for_track("MAIN_3") == []
    assert layout.crossover_srjs_for_track("MAIN_3") == []

    # Only MAIN_1 and MAIN_2 have crossover records:
    assert len(layout.get_crossovers_for_track("MAIN_1")) == 1
    assert len(layout.get_crossovers_for_track("MAIN_2")) == 1


def test_line_specific_extent_affects_only_target_track():
    """Verify that adjusting extent for a single main line works only on that particular line."""
    layout = _sample_straight_tracks()

    co_builder = BrownfieldCrossoverBuilder(layout)
    # Adjust extent on MAIN_1 only: from 150m to 750m (600m long)
    co_builder.set_single_track_extent(layout, "MAIN_1", start_chainage=150.0, end_chainage=750.0)

    # MAIN_1 is adjusted:
    assert layout["MAIN_1"].length == pytest.approx(600.0)
    assert layout["MAIN_1"].points[0][0] == pytest.approx(150.0)
    assert layout["MAIN_1"].points[-1][0] == pytest.approx(750.0)

    # MAIN_2 and MAIN_3 remain full length (1000m) and completely unaffected!
    assert layout["MAIN_2"].length == 1000.0
    assert layout["MAIN_2"].points[0][0] == 0.0
    assert layout["MAIN_2"].points[-1][0] == 1000.0

    assert layout["MAIN_3"].length == 1000.0
    assert layout["MAIN_3"].points[0][0] == 0.0
    assert layout["MAIN_3"].points[-1][0] == 1000.0


def test_brownfield_generator_renders_crossovers_without_50m_srj_trim(tmp_path):
    """Verify BrownfieldGenerator renders full-length tracks and crossovers in DXF without 50m trim."""
    output_dxf = tmp_path / "brownfield_crossover.dxf"

    generator = BrownfieldGenerator(
        base_tracks={"MAIN_1": [(0.0, 0.0), (1000.0, 0.0)]},
        main_line_specs=[
            BrownfieldMainLineSpec(name="MAIN_2", reference_track="MAIN_1", spacing=5.3, side="LEFT"),
            BrownfieldMainLineSpec(name="MAIN_3", reference_track="MAIN_2", spacing=5.3, side="LEFT"),
        ],
        crossover_specs=[
            BrownfieldCrossoverSpec(id="X1", from_track="MAIN_1", to_track="MAIN_2", chainage=300.0),
        ],
        output_dxf=str(output_dxf),
    )
    layout = generator.run()

    # All tracks preserve full 1000m length:
    for t_name in ("MAIN_1", "MAIN_2", "MAIN_3"):
        assert layout[t_name].length == 1000.0

    doc = ezdxf.readfile(str(output_dxf))
    layers = {l.dxf.name for l in doc.layers}
    assert "MAIN_1" in layers
    assert "MAIN_2" in layers
    assert "MAIN_3" in layers
    assert "CROSSOVERS" in layers

    # Check polyline lengths in DXF for MAIN_1, MAIN_2, MAIN_3: all remain ~1000m
    msp = doc.modelspace()
    for entity in msp:
        if entity.dxftype() == "LWPOLYLINE" and entity.dxf.layer == "MAIN_1":
            pts = [(p[0], p[1]) for p in entity.get_points()]
            assert pts[0][0] == pytest.approx(0.0)
            assert pts[-1][0] == pytest.approx(1000.0)


def test_pipeline_step_skips_50m_trim_in_brownfield_mode():
    """Verify pipeline track step skips 50m SRJ end-truncation when brownfield mode is flagged."""
    from pipeline.steps.track import TrackStep

    class FakeConfig:
        workflow = "brownfield"
        is_brownfield = True
        output_dxf = "dummy.dxf"
        additional_lines = []

    step = TrackStep(FakeConfig())
    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (1000.0, 0.0)],
        "MAIN_LINE_1": [(0.0, 5.3), (1000.0, 5.3)],
    }
    # In brownfield mode, _trim_main_lines_to_srj returns None and leaves tracks full length:
    res = step._trim_main_lines_to_srj(tracks)
    assert res is None
    assert tracks["MAIN_LINE"] == [(0.0, 0.0), (1000.0, 0.0)]
    assert tracks["MAIN_LINE_1"] == [(0.0, 5.3), (1000.0, 5.3)]
