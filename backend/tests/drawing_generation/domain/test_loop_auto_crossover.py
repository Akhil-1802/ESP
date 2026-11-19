"""Unanchored loop AUTO placement must match the dynamic preview's loop ends."""
import ezdxf
import pytest
from app.features.drawing_generation.config import ESPConfig
from app.features.drawing_generation.domain.constants import COLLISION_PUSH_SEPARATION_M
from app.features.drawing_generation.domain.track.crossover.planner import (
    CrossoverPlanner,
)
from app.features.drawing_generation.domain.track.specs import CrossoverSpec, LoopSpec
from app.features.drawing_generation.pipeline.generator import ESPGenerator

from .helpers_crossover import req, straight_tracks

LOOP_RANGES = {"LOOP_1": (500.0, 1250.0), "LOOP_2": (500.0, 1250.0)}


def four_crossovers(direction):
    other = "REVERSE" if direction == "FORWARD" else "FORWARD"
    first_end = 1250.0 if other == "REVERSE" else 500.0
    second_end = 500.0 if direction == "FORWARD" else 1250.0
    return [
        req("C1", "LOOP_1", "MAIN_LINE", first_end, other, placement=None),
        req("C2", "LOOP_1", "MAIN_LINE", second_end, direction, placement=None),
        req("C3", "LOOP_2", "MAIN_LINE", first_end, other, placement=None),
        req("C4", "LOOP_2", "MAIN_LINE", None, direction, placement=None),
    ]


def main_endpoint(result):
    return result.end_chainage if result.placement == "AHEAD" else result.start_chainage


def nested_anchor_requests(direction, earlier_auto=False):
    sign = 1 if direction == "FORWARD" else -1
    outer_start = 500.0 if sign == 1 else 1250.0
    candidate = outer_start + sign * (97.578 + 13.0)
    if earlier_auto:
        first_two = [
            req("C1", "LOOP_3", "LOOP_1", outer_start, direction, placement=None),
            req("C2", "LOOP_1", "MAIN_LINE", None, direction, placement=None),
        ]
        first_two[1].metadata["auto_anchor_id"] = "C1"
    else:
        first_two = [
            req("C1", "LOOP_1", "MAIN_LINE", candidate, direction, placement=None),
            req("C2", "LOOP_3", "LOOP_1", outer_start, direction, placement=None),
        ]
    requests = first_two + [
        req("C3", "LOOP_4", "LOOP_2", outer_start, direction, placement=None),
        req("C4", "LOOP_2", "MAIN_LINE", None, direction, placement=None),
    ]
    requests[3].metadata["auto_anchor_id"] = "C3"
    return requests, candidate


@pytest.mark.parametrize("direction,sign", [("FORWARD", 1), ("REVERSE", -1)])
@pytest.mark.parametrize("earlier_auto", [False, True])
def test_c4_keeps_13m_anchor_offset_then_pushes_64m_on_collision_with_another_end(direction, sign, earlier_auto):
    tracks = straight_tracks()
    tracks["LOOP_3"] = [(x, 10.6) for x, _ in tracks["MAIN_LINE"]]
    tracks["LOOP_4"] = [(x, -10.6) for x, _ in tracks["MAIN_LINE"]]
    requests, candidate = nested_anchor_requests(direction, earlier_auto)
    results, report = CrossoverPlanner(tracks, loop_ranges=LOOP_RANGES).plan(requests)
    assert report.overall_valid, report.errors
    collider = results[1 if earlier_auto else 0]
    anchor, c4 = results[2:]
    assert collider.chainage == pytest.approx(candidate)
    assert c4.chainage == pytest.approx(candidate + sign * COLLISION_PUSH_SEPARATION_M)
    assert c4.chainage - main_endpoint(anchor) == pytest.approx(sign * (13.0 + COLLISION_PUSH_SEPARATION_M))
    assert main_endpoint(c4) - main_endpoint(collider) == pytest.approx(sign * COLLISION_PUSH_SEPARATION_M)


@pytest.mark.parametrize("direction,sign", [("FORWARD", 1), ("REVERSE", -1)])
def test_fourth_auto_uses_loop_end_and_collides_with_c2_not_last_c3(direction, sign):
    requests = four_crossovers(direction)
    results, report = CrossoverPlanner(straight_tracks(), loop_ranges=LOOP_RANGES).plan(requests)
    assert report.overall_valid, report.errors
    c1, c2, c3, c4 = results
    assert c1.chainage == pytest.approx(1250.0 if sign == 1 else 500.0)
    assert c2.chainage == pytest.approx(500.0 if sign == 1 else 1250.0)
    assert c4.chainage == pytest.approx(c2.chainage + sign * COLLISION_PUSH_SEPARATION_M)
    assert main_endpoint(c4) - main_endpoint(c2) == pytest.approx(sign * COLLISION_PUSH_SEPARATION_M)
    assert c4.ol_m == pytest.approx(c2.ol_m)
    assert c3.chainage == pytest.approx(c1.chainage - sign * COLLISION_PUSH_SEPARATION_M)


@pytest.mark.parametrize("direction,sign", [("FORWARD", 1), ("REVERSE", -1)])
def test_auto_end_collision_is_detected_even_when_start_chainages_differ(direction, sign):
    first = req("C1", "LOOP_1", "MAIN_LINE", 1000.0, direction, placement=None)
    # Different turnout lengths make the ends coincide despite different starts.
    first_ol = 5.3 * 12 + 2 * 16.989
    second_ol = 5.3 * 8.5 + 2 * 12.025
    nominal = 1000.0 + sign * (first_ol - second_ol)
    ranges = {"LOOP_2": (nominal, 1800.0) if sign == 1 else (500.0, nominal)}
    second = req("C2", "LOOP_2", "MAIN_LINE", None, direction, "1:8.5", None)
    results, report = CrossoverPlanner(straight_tracks(length=3000), loop_ranges=ranges).plan([first, second])
    assert report.overall_valid, report.errors
    assert results[0].chainage == pytest.approx(1000.0)
    assert results[1].chainage == pytest.approx(nominal + sign * COLLISION_PUSH_SEPARATION_M)
    assert main_endpoint(results[1]) - main_endpoint(results[0]) == pytest.approx(sign * COLLISION_PUSH_SEPARATION_M)


@pytest.mark.parametrize("loop_start", [527.2, 550.0])
def test_noncolliding_auto_stays_at_loop_end_without_a_64m_shift(loop_start):
    requests = [req("C1", "LOOP_1", "MAIN_LINE", 500.0),
                req("C2", "LOOP_2", "MAIN_LINE", None)]
    results, report = CrossoverPlanner(
        straight_tracks(), loop_ranges={"LOOP_2": (loop_start, 1300.0)},
    ).plan(requests)
    assert report.overall_valid, report.errors
    assert results[0].chainage == pytest.approx(500.0)
    assert results[1].chainage == pytest.approx(loop_start)


@pytest.mark.parametrize("direction,minimum", [("FORWARD", 13.0), ("REVERSE", 54.0)])
def test_explicit_auto_anchor_keeps_existing_spacing_with_loop_ranges(direction, minimum):
    positions = []
    for ranges in [{}, LOOP_RANGES]:
        first = req("C1", "LOOP_1", "MAIN_LINE", 500.0)
        second = req("C2", "LOOP_2", "MAIN_LINE", None, direction, placement=None)
        second.metadata["auto_anchor_id"] = "C1"
        results, report = CrossoverPlanner(straight_tracks(), loop_ranges=ranges).plan([first, second])
        assert report.overall_valid, report.errors
        assert report.spacing_checks[0].required_m == pytest.approx(minimum)
        assert report.spacing_checks[0].actual_m == pytest.approx(minimum, abs=0.001)
        positions.append(results[1].chainage)
    assert positions[0] == pytest.approx(positions[1])


def test_all_four_loop_crossovers_can_use_auto_without_changing_earlier_positions():
    requests = four_crossovers("FORWARD")
    for request in requests:
        request.chainage = None
        request.position_mode = "AUTO"
    results, report = CrossoverPlanner(straight_tracks(), loop_ranges=LOOP_RANGES).plan(requests)
    assert report.overall_valid, report.errors
    assert [result.chainage for result in results] == pytest.approx([1250.0, 500.0, 1186.0, 564.0])


def test_later_explicit_anchor_uses_an_already_shifted_auto_position():
    requests = [req("C1", "LOOP_1", "MAIN_LINE", 500.0),
                req("C2", "LOOP_2", "MAIN_LINE", None),
                req("C3", "MAIN_LINE", "LOOP_2", None)]
    requests[2].metadata["auto_anchor_id"] = "C2"
    results, report = CrossoverPlanner(straight_tracks(), loop_ranges=LOOP_RANGES).plan(requests)
    assert report.overall_valid, report.errors
    assert results[1].chainage == pytest.approx(564.0)
    assert results[2].chainage == pytest.approx(main_endpoint(results[1]) + 13.0)


@pytest.mark.parametrize("direction,sign", [("FORWARD", 1), ("REVERSE", -1)])
def test_pipeline_exports_fourth_auto_at_the_preview_position(tmp_path, direction, sign):
    source, output = tmp_path / "source.dxf", tmp_path / "output.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (2000, 0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)
    requests = four_crossovers(direction)
    specs = [CrossoverSpec(
        r.from_track, r.to_track, r.chainage, None, r.turnout, r.placement,
        id=r.id, direction=r.direction, position_mode=r.position_mode,
    ) for r in requests]
    generator = ESPGenerator(ESPConfig(
        source_path=str(source), output_dxf=str(output), track_source_layer="MAIN_TRACK",
        loops=[LoopSpec("LOOP_1", 5.3, "LEFT", 500, 1250),
               LoopSpec("LOOP_2", 5.3, "RIGHT", 500, 1250)],
        crossovers=specs,
    ))
    generator.run()
    c1, c2, c3, c4 = generator._crossover_results
    assert c4.chainage == pytest.approx(c2.chainage + sign * COLLISION_PUSH_SEPARATION_M)
    assert main_endpoint(c4) - main_endpoint(c2) == pytest.approx(sign * COLLISION_PUSH_SEPARATION_M)
    exported = ezdxf.readfile(output)
    srj_starts = [entity.dxf.start for entity in exported.modelspace().query('LINE[layer=="SRJ"]')]
    assert any(point.x == pytest.approx(c4.chainage) and point.y == pytest.approx(-5.3) for point in srj_starts)
    assert any(point.x == pytest.approx(main_endpoint(c4)) and point.y == pytest.approx(0.0) for point in srj_starts)


@pytest.mark.parametrize("direction,sign", [("FORWARD", 1), ("REVERSE", -1)])
@pytest.mark.parametrize("earlier_auto", [False, True])
def test_exported_dxf_applies_collision_push_after_c4s_c3_anchor_offset(tmp_path, direction, sign, earlier_auto):
    source, output = tmp_path / "source.dxf", tmp_path / "nested.dxf"
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0), (2000, 0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(source)
    requests, candidate = nested_anchor_requests(direction, earlier_auto)
    specs = [CrossoverSpec(
        r.from_track, r.to_track, r.chainage, None, r.turnout, r.placement,
        id=r.id, direction=r.direction, position_mode=r.position_mode,
        auto_anchor_id=r.metadata.get("auto_anchor_id"),
    ) for r in requests]
    generator = ESPGenerator(ESPConfig(
        source_path=str(source), output_dxf=str(output), track_source_layer="MAIN_TRACK",
        loops=[
            LoopSpec("LOOP_1", 5.3, "LEFT", 500, 1250),
            LoopSpec("LOOP_2", 5.3, "RIGHT", 500, 1250),
            LoopSpec("LOOP_3", 5.3, "LEFT", 500, 1250, reference_track="LOOP_1"),
            LoopSpec("LOOP_4", 5.3, "RIGHT", 500, 1250, reference_track="LOOP_2"),
        ],
        crossovers=specs,
    ))
    generator.run()
    collider = generator._crossover_results[1 if earlier_auto else 0]
    c3, c4 = generator._crossover_results[2:]
    assert collider.chainage == pytest.approx(candidate)
    assert c4.chainage == pytest.approx(candidate + sign * COLLISION_PUSH_SEPARATION_M)
    assert c4.chainage - main_endpoint(c3) == pytest.approx(sign * (13 + COLLISION_PUSH_SEPARATION_M))
    srjs = [e.dxf.start for e in ezdxf.readfile(output).modelspace().query('LINE[layer=="SRJ"]')]
    assert any(p.x == pytest.approx(c4.chainage) and p.y == pytest.approx(-5.3) for p in srjs)
    assert any(p.x == pytest.approx(main_endpoint(c4)) and p.y == pytest.approx(0) for p in srjs)
