"""N-crossover engine advanced geometry, rotation, curve, and anchoring tests."""

from __future__ import annotations

import math
import pytest

from track.crossover.defaults import format_debug_block
from track.crossover.geometry import compute_crossover_params
from track.crossover.models import CrossoverResult
from track.crossover.planner import CrossoverPlanner
from track.crossover.rules import get_required_separation
from .helpers_crossover import (
    curved_tracks,
    plan_ok,
    req,
    rotated_tracks,
    straight_tracks,
)


def test_14_rotated_main_track():
    tracks = rotated_tracks(angle_deg=30.0)
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    r = results[0]
    assert r.track_centre_m == pytest.approx(5.3, abs=0.05)
    p0, p1 = r.geometry[0], r.geometry[1]
    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    assert ang == pytest.approx(30.0, abs=5.0)


def test_15_curved_main_track():
    tracks = curved_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD"),
        req("C2", "LOOP_1", "MAIN_LINE", 1200.0, "FORWARD"),
    ], tracks)
    assert report.overall_valid, report.errors
    for r in results:
        assert r.track_centre_m == pytest.approx(5.3, abs=0.15)
        assert r.validation_status == "VALID"


def test_16_standard_reference_values():
    tracks = straight_tracks(tc=5.3)
    params = compute_crossover_params(
        req("C1", "LOOP_1", "MAIN_LINE", 500.0, "FORWARD", "1:12"),
        500.0, tracks, {})
    assert params["f_deg"] == pytest.approx(4.7636, abs=0.001)
    assert params["ol_mm"] == pytest.approx(97578.0, abs=1.0)
    assert params["ol_mm"] == pytest.approx(
        5300.0 * 12.0 + 2.0 * 16989.0, abs=1.0)


def test_17_opposite_side_shared_track_gap():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 327.287, "REVERSE",
            "1:12", "BEHIND"),
    ], tracks)
    assert report.overall_valid, report.errors
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(54.0)
    assert chk.actual_m == pytest.approx(54.0, abs=0.01)
    assert chk.valid
    assert all(r.validation_status == "VALID" for r in results)


def test_18_opposite_side_shared_track_gap_invalid():
    tracks = straight_tracks()
    _results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", 229.709, "REVERSE",
            "1:12", "BEHIND"),
    ], tracks)
    assert not report.overall_valid
    chk = report.spacing_checks[0]
    assert chk.required_m == pytest.approx(54.0)
    assert chk.actual_m == pytest.approx(43.58, abs=0.05)
    assert chk.deficit_m == pytest.approx(10.42, abs=0.05)
    assert chk.suggested_min_chainage_b == pytest.approx(327.287, abs=0.01)


def test_19_auto_places_shared_track_gap():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 175.709, "FORWARD"),
        req("C2", "MAIN_LINE", "LOOP_2", None, "REVERSE",
            "1:12", None),
    ], tracks)
    assert report.overall_valid, report.errors
    c2 = next(r for r in results if r.id == "C2")
    assert c2.placement == "BEHIND"
    assert c2.chainage == pytest.approx(219.287, abs=0.01)
    chk = report.spacing_checks[0]
    assert chk.actual_m == pytest.approx(54.0, abs=0.001)


def test_20_auto_follows_shared_line():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 175.709, "REVERSE",
            "1:12", "BEHIND"),
        req("C2", "MAIN_LINE", "LOOP_2", None, "FORWARD",
            "1:12", None),
    ], tracks)
    assert report.overall_valid, report.errors
    c2 = next(r for r in results if r.id == "C2")
    assert c2.placement == "AHEAD"
    assert c2.chainage == pytest.approx(132.131, abs=0.01)
    chk = report.spacing_checks[0]
    assert chk.actual_m == pytest.approx(54.0, abs=0.01)


def test_21_start_gap_ignored_across_tracks():
    tracks = straight_tracks()
    results, report = plan_ok([
        req("C1", "LOOP_1", "MAIN_LINE", 175.709, "REVERSE",
            "1:12", "BEHIND"),
        req("C2", "MAIN_LINE", "LOOP_2", 132.131, "FORWARD",
            "1:12", "AHEAD"),
    ], tracks)
    assert report.overall_valid, report.errors
    assert all(r.validation_status == "VALID" for r in results)


def test_spacing_rule_centralised():
    assert get_required_separation("FORWARD", "FORWARD") == pytest.approx(13.0)
    assert get_required_separation("REVERSE", "REVERSE") == pytest.approx(13.0)
    assert get_required_separation("FORWARD", "REVERSE") == pytest.approx(54.0)
    assert get_required_separation("REVERSE", "FORWARD") == pytest.approx(54.0)


def test_debug_block_tolerates_missing_params():
    res = CrossoverResult(
        id="C1", from_track="NOPE", to_track="MAIN_LINE",
        chainage=175.709, direction="REVERSE", placement="BEHIND",
        turnout_type="1:12", track_centre_mm=None, track_centre_m=None,
        n_ratio=None, f_rad=None, f_deg=None, a_mm=None, b_mm=None,
        r_mm=None, ol_mm=None, ol_m=None, crossover_type=None,
        start_chainage=None, end_chainage=None, geometry=[],
        geometry_report={}, validation_status="INVALID", warnings=[],
        errors=["unknown FROM track 'NOPE'"],
    )
    block = format_debug_block(res)
    assert "NOPE -> MAIN_LINE" in block
    assert "INVALID" in block
    assert "?" in block


def test_diverged_zone_crossover_rejected_for_discontinuity():
    main = [(float(x), 0.0) for x in range(0, 1201, 5)]
    loop = [(float(x), 5.3 if x <= 800 else 5.3 + (x - 800) * (10.7 / 200.0))
            for x in range(0, 1201, 5)]
    tracks = {"MAIN_LINE": main, "LOOP_1": loop}

    good, good_rep = plan_ok(
        [req("C1", "MAIN_LINE", "LOOP_1", 500.0, "FORWARD", "1:12", None)],
        tracks)
    assert good_rep.overall_valid, good_rep.errors

    _bad, bad_rep = plan_ok(
        [req("C1", "MAIN_LINE", "LOOP_1", 1000.0, "REVERSE", "1:12", None)],
        tracks)
    assert not bad_rep.overall_valid
    assert any("vertex gap" in e for e in bad_rep.errors)


def test_auto_candidate_rejects_unbuildable_geometry():
    main = [(float(x), 0.0) for x in range(0, 1201, 5)]
    loop = [(float(x), 5.3 if x <= 800 else 5.3 + (x - 800) * (10.7 / 200.0))
            for x in range(0, 1201, 5)]
    tracks = {"MAIN_LINE": main, "LOOP_1": loop}
    planner = CrossoverPlanner(tracks, {}, 1200.0)
    auto = req("C1", "MAIN_LINE", "LOOP_1", None, "REVERSE", "1:12", None)

    assert planner._candidate_violates_fixed(auto, 500.0, {}, {}, {}) is None
    assert planner._candidate_violates_fixed(
        auto, 1000.0, {}, {}, {}) == "geometry does not fit at candidate"


def test_auto_reverse_anchors_before_previous():
    tracks = straight_tracks()
    fixed = req("C1", "MAIN_LINE", "LOOP_1", 500.0, "FORWARD", "1:12", None)
    auto = req("C2", "MAIN_LINE", "LOOP_1", None, "REVERSE", "1:12", None)
    results, report = plan_ok([fixed, auto], tracks)
    assert report.overall_valid, report.errors
    placed = next(r.chainage for r in results if r.id == "C2")
    assert placed == pytest.approx(446.0, abs=0.001)


def test_auto_forward_anchors_after_previous():
    tracks = straight_tracks()
    fixed = req("C1", "MAIN_LINE", "LOOP_1", 500.0, "FORWARD", "1:12", None)
    auto = req("C2", "MAIN_LINE", "LOOP_1", None, "FORWARD", "1:12", None)
    results, report = plan_ok([fixed, auto], tracks)
    assert report.overall_valid, report.errors
    placed = next(r.chainage for r in results if r.id == "C2")
    assert placed > 500.0


def test_centerline_distance_curved_long_mainline_with_local_parallel_loop():
    from track.crossover.core import centerline_distance_mm
    # Mainline: straight from 0 to 5000, then bends by 15 deg between 5000 and 10000
    main = [(float(x), 0.0) for x in range(0, 5001, 100)]
    rad = math.radians(15.0)
    for x in range(5100, 10001, 100):
        dx = x - 5000.0
        main.append((5000.0 + dx * math.cos(rad), dx * math.sin(rad)))
    # Loop line: parallel to mainline between 2000 and 2750 at 5.3m offset
    loop = [(float(x), 5.3) for x in range(2000, 2751, 50)]
    dist_mm = centerline_distance_mm(main, loop)
    assert dist_mm == pytest.approx(5300.0, abs=10.0)


def test_centerline_distance_antiparallel_tracks():
    from track.crossover.core import centerline_distance_mm
    from_pts = [(0.0, 0.0), (1000.0, 0.0)]
    to_pts = [(1000.0, 5.3), (0.0, 5.3)]
    dist_mm = centerline_distance_mm(from_pts, to_pts)
    assert dist_mm == pytest.approx(5300.0, abs=1.0)


def test_crossover_collision_push_64m():
    """When two crossovers point at the exact same chainage or point on a shared track,
    the first placed crossover stays in place, and the second is pushed by 64.0 m along its direction.
    """
    tracks = straight_tracks(tc=5.3, length=3000.0)
    # Both C1 and C2 start at chainage 500.0 on MAIN_LINE (C1 to LOOP_1 on LEFT, C2 to LOOP_2 on RIGHT)
    c1_req = req("C1", "MAIN_LINE", "LOOP_1", 500.0, "FORWARD", "1:12", None)
    c2_req = req("C2", "MAIN_LINE", "LOOP_2", 500.0, "FORWARD", "1:12", None)

    results, report = plan_ok([c1_req, c2_req], tracks)
    assert report.overall_valid, report.errors

    res_c1 = next(r for r in results if r.id == "C1")
    res_c2 = next(r for r in results if r.id == "C2")

    # C1 stays at 500.0
    assert res_c1.chainage == pytest.approx(500.0, abs=0.001)

    # C2 is pushed by exactly 64.0 m
    assert res_c2.chainage == pytest.approx(564.0, abs=0.001)

    # End point (end_chainage) of C2 is also shifted by 64.0 m relative to C1
    assert (res_c2.end_chainage - res_c1.end_chainage) == pytest.approx(64.0, abs=0.001)
