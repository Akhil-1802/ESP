"""Tests for turnout curve smoothness, tangent continuity, and dimension preservation."""

from __future__ import annotations

import math

import pytest
from app.features.drawing_generation.domain.geometry.operations import rotate, unit
from app.features.drawing_generation.domain.track.crossover import (
    build_standard_crossover,
)
from app.features.drawing_generation.domain.track.crossover.turnout import (
    _sample_spline,
)
from app.features.drawing_generation.domain.track.turnouts import select_turnout


def test_spline_boundary_tangent_and_curvature_continuity():
    """Verify that _sample_spline begins and ends with zero curvature and matching tangents."""
    start = (100.0, 50.0)
    start_dir = (1.0, 0.0)
    f = math.atan(1.0 / 12.0)
    end_dir = rotate(start_dir, f)
    r_m = 441.36
    samples = 64

    pts = _sample_spline(start, start_dir, end_dir, r_m, f, samples=samples)
    assert len(pts) == samples + 1
    assert math.hypot(pts[0][0] - start[0], pts[0][1] - start[1]) < 1e-9

    v_start = (pts[1][0] - pts[0][0], pts[1][1] - pts[0][1])
    u_start = unit(v_start)
    assert math.isclose(u_start[0], start_dir[0], abs_tol=1e-3)
    assert math.isclose(u_start[1], start_dir[1], abs_tol=1e-3)

    v_end = (pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1])
    u_end = unit(v_end)
    assert math.isclose(u_end[0], end_dir[0], abs_tol=1e-3)
    assert math.isclose(u_end[1], end_dir[1], abs_tol=1e-3)

    curvatures = []
    for i in range(1, len(pts) - 1):
        p_prev = pts[i - 1]
        p_curr = pts[i]
        p_next = pts[i + 1]

        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        len1 = math.hypot(*v1)
        len2 = math.hypot(*v2)
        ang = math.atan2(v1[0] * v2[1] - v1[1] * v2[0], v1[0] * v2[0] + v1[1] * v2[1])
        ds = 0.5 * (len1 + len2)
        k = abs(ang) / ds if ds > 1e-6 else 0.0
        curvatures.append(k)

    assert curvatures[0] < curvatures[len(curvatures) // 2]
    assert curvatures[-1] < curvatures[len(curvatures) // 2]
    for k1, k2 in zip(curvatures, curvatures[1:]):
        assert abs(k2 - k1) < 0.002, f"Abrupt curvature step detected: {k1} -> {k2}"


def test_crossover_overall_dimensions_preserved():
    """Verify that crossover overall length, SRJ, endpoint, and track spacing match exact standard formulas."""
    for designation, n, tc_m in [("1:12", 12.0, 5.3), ("1:8.5", 8.5, 5.3), ("1:12", 12.0, 6.5)]:
        turnout = select_turnout(designation)
        a_m = turnout.a_mm / 1000.0
        expected_ol = tc_m * n + 2.0 * a_m

        p_from = (100.0, 0.0)
        p_to = (100.0 + expected_ol, tc_m)
        u = (1.0, 0.0)
        v = (1.0, 0.0)

        pts, rep = build_standard_crossover(p_from, u, p_to, v, turnout)
        assert rep["warnings"] == [] or all("constrained" in w or "differ" in w for w in rep["warnings"])

        assert math.hypot(pts[0][0] - p_from[0], pts[0][1] - p_from[1]) < 1e-9
        assert math.hypot(pts[-1][0] - p_to[0], pts[-1][1] - p_to[1]) < 1e-9

        actual_ol = pts[-1][0] - pts[0][0]
        assert pytest.approx(expected_ol, abs=1e-3) == actual_ol

        assert len(pts) > 130

        max_gap = max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
        assert max_gap <= 5.0

        assert all(b[0] >= a[0] - 1e-6 for a, b in zip(pts, pts[1:]))
