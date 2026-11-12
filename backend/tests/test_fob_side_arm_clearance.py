"""Tests for FOB landing arm clearance (5.33m) and local rectangular platform widening."""

from __future__ import annotations

import pytest

from fob.deck_geom import build_fob_arms
from platform_gen.config import PlatformConfig, PlatformSide, PlatformType
from platform_gen.side import side_platform
from platform_gen.track import Track


def test_fob_arm_near_edge_distance_is_5_33m_on_side_platform():
    """FOB landing arm near edge must be exactly 5.33m from the adjacent track centerline."""
    origin = (100.0, 0.0)
    tangent = (1.0, 0.0)
    normal = (0.0, 1.0)
    tracks = {
        "MAIN_LINE": [(0.0, 0.0), (200.0, 0.0)],
        "LOOP_1": [(0.0, 5.3), (200.0, 5.3)],
    }
    # Platform 1 on RIGHT side of MAIN_LINE (y from -8.68 to -1.68, clearance 1.68, width 7.0)
    # Platform 2 on LEFT side of LOOP_1 (y from 6.98 to 13.98, clearance 1.68, width 7.0)
    spans_by_layer = {
        "PLATFORM_1": (-8.68, -1.68),
        "PLATFORM_2": (6.98, 13.98),
    }
    arm_specs = {
        "PLATFORM_1": {"length": 20.0, "side": "LEFT"},
        "PLATFORM_2": {"length": 20.0, "side": "RIGHT"},
    }
    arms = build_fob_arms(origin, tangent, normal, spans_by_layer, arm_specs, 3.0, tracks=tracks)
    assert len(arms) == 2

    # Arm 1 on PLATFORM_1 (track is MAIN_LINE at y = 0.0):
    # Near edge must be at y = -5.33 (distance from track = 5.33m)
    # Far edge must be at y = -8.33 (arm width = 3.0m)
    arm1 = arms[0]
    ys_arm1 = sorted(p[1] for p in arm1)
    near_edge_arm1 = max(ys_arm1)  # closest to track (y=0)
    far_edge_arm1 = min(ys_arm1)
    assert near_edge_arm1 == pytest.approx(-5.33)
    assert abs(0.0 - near_edge_arm1) == pytest.approx(5.33)
    assert (near_edge_arm1 - far_edge_arm1) == pytest.approx(3.0)

    # Arm 2 on PLATFORM_2 (track is LOOP_1 at y = 5.3):
    # Near edge must be at y = 5.3 + 5.33 = 10.63 (distance from track = 5.33m)
    # Far edge must be at y = 10.63 + 3.0 = 13.63 (arm width = 3.0m)
    arm2 = arms[1]
    ys_arm2 = sorted(p[1] for p in arm2)
    near_edge_arm2 = min(ys_arm2)  # closest to track (y=5.3)
    far_edge_arm2 = max(ys_arm2)
    assert near_edge_arm2 == pytest.approx(10.63)
    assert abs(near_edge_arm2 - 5.3) == pytest.approx(5.33)
    assert (far_edge_arm2 - near_edge_arm2) == pytest.approx(3.0)


def test_fob_arm_width_never_below_3m():
    """FOB landing arm width must never go below 3.0m even if configured width is smaller."""
    origin = (100.0, 0.0)
    tangent = (1.0, 0.0)
    normal = (0.0, 1.0)
    spans_by_layer = {"PLATFORM_1": (1.68, 8.68)}
    arm_specs = {"PLATFORM_1": {"length": 15.0, "side": "LEFT"}}

    # Even if deck width is 2.0m, arm width must be >= 3.0m
    arms = build_fob_arms(origin, tangent, normal, spans_by_layer, arm_specs, 2.0)
    assert len(arms) == 1
    ys = sorted(p[1] for p in arms[0])
    arm_w = max(ys) - min(ys)
    assert arm_w >= 3.0
    assert arm_w == pytest.approx(3.0)


def test_island_platform_arm_remains_centered():
    """Island platforms (tracks on both sides) keep their arm centered on the platform."""
    origin = (50.0, 0.0)
    tangent = (1.0, 0.0)
    normal = (0.0, 1.0)
    tracks = {
        "TRACK_1": [(0.0, 0.0), (100.0, 0.0)],
        "TRACK_2": [(0.0, 15.0), (100.0, 15.0)],
    }
    spans = {"ISLAND_PLAT": (1.68, 13.32)}
    specs = {"ISLAND_PLAT": {"length": 20.0, "side": "LEFT"}}

    arms = build_fob_arms(origin, tangent, normal, spans, specs, 3.0, tracks=tracks)
    assert len(arms) == 1
    ys = sorted(p[1] for p in arms[0])
    mid_arm = (min(ys) + max(ys)) / 2.0
    mid_plat = (1.68 + 13.32) / 2.0
    assert mid_arm == pytest.approx(mid_plat)


def test_side_platform_local_rectangular_widening_at_fob_arm():
    """Platform back edge steps outward in a small rectangular zone where the FOB arm needs extra width."""
    track = Track("MAIN_LINE", [(0.0, 0.0), (1000.0, 0.0)])
    # 7.0m standard width platform from ch 200 to 750 (clearance 1.68 -> std far edge at y=8.68)
    # FOB arm is at ch 480 to 505, requiring widened offset 10.18 (extra 1.5m width)
    cfg = PlatformConfig(
        source_dxf="src.dxf",
        output_dxf="out.dxf",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        center_on_track=False,
        start_chainage=200.0,
        end_chainage=750.0,
        platform_length=550.0,
        clearance=1.68,
        platform_width=7.0,
        fob_widenings=[{
            "start_chainage": 480.0,
            "end_chainage": 505.0,
            "widened_offset": 10.18,
            "extra_width": 1.5,
        }],
    )
    result = side_platform(track, cfg)
    outline = result.outline
    assert len(outline) > 5

    # Near edge (facing track at y=0) must remain straight at y = 1.68 along the entire platform
    near_ys = [p[1] for p in result.near_edge]
    assert all(abs(y - 1.68) < 1e-4 for y in near_ys)

    # Far edge has standard offset y=8.68 outside the zone, and y=10.18 inside [480, 505]
    far_pts = result.far_edge
    assert len(far_pts) == 6
    assert far_pts[0] == pytest.approx((200.0, 8.68))
    assert far_pts[1] == pytest.approx((480.0, 8.68))
    assert far_pts[2] == pytest.approx((480.0, 10.18))
    assert far_pts[3] == pytest.approx((505.0, 10.18))
    assert far_pts[4] == pytest.approx((505.0, 8.68))
    assert far_pts[5] == pytest.approx((750.0, 8.68))


def test_side_platform_no_widening_needed_if_already_wide():
    """If the platform is already wide enough (e.g. 10m), far edge remains a single straight offset."""
    track = Track("MAIN_LINE", [(0.0, 0.0), (1000.0, 0.0)])
    cfg = PlatformConfig(
        source_dxf="src.dxf",
        output_dxf="out.dxf",
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        center_on_track=False,
        start_chainage=200.0,
        end_chainage=750.0,
        clearance=1.68,
        platform_width=10.0,  # 1.68 + 10 = 11.68m, already wide enough
        fob_widenings=[],
    )
    result = side_platform(track, cfg)
    far_ys = [p[1] for p in result.far_edge]
    assert all(abs(y - 11.68) < 1e-4 for y in far_ys)


def test_fob_automatic_widening_and_fencing(tmp_path):
    """When a platform is narrower than needed by FOB (5.33 + W_arm + 1.0m),

    it automatically widens 1m before the arm and 1m after the FOB,
    and fencing traces the widened outer perimeter.
    """
    import ezdxf
    from config.loader import ESPConfig, PlatformRequest
    from fob.config import FOBConfig
    from pipeline.orchestrator import ESPGenerator
    from track.specs import LoopSpec

    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"

    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_line((0.0, 0.0), (1200.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 200.0, 1000.0, extend_start_m=0.0, extend_end_m=0.0),
    ]

    # Narrow platform (width=4.0m, far edge at 1.68 + 4.0 = 5.68m)
    p_cfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="LOOP_1",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        clearance=1.68,
        platform_width=4.0,
        platform_length=400.0,
        center_on_track=True,
        output_layer="PLATFORM_1",
    )
    platforms = [PlatformRequest("LOOP_1", p_cfg)]

    # FOB at chainage 600m on MAIN_LINE, connecting PLATFORM_1
    # Arm length 15m on LEFT (decreasing chainage)
    fobs = [
        FOBConfig(
            reference_track="MAIN_LINE",
            reference_chainage=600.0,
            platforms=["PLATFORM_1"],
            width=3.0,
            arms={"PLATFORM_1": {"length": 15.0, "side": "LEFT"}},
            output_layer="FOB_1",
        )
    ]

    esp_cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        platforms=platforms,
        fobs=fobs,
    )

    gen = ESPGenerator(esp_cfg)
    gen.run()

    out_doc = ezdxf.readfile(str(out))
    plat_entities = [e for e in out_doc.modelspace() if getattr(e.dxf, "layer", "") == "PLATFORM_1"]
    assert len(plat_entities) >= 1
    plat_pts = list(plat_entities[0].get_points())
    # Platform must have the 9-vertex closed outline (stepped bay)
    assert len(plat_pts) == 9

    # Check the widened offset: LOOP_1 is at y=5.3.
    # Clearance 1.68 + std width 4.0 = 5.68m from LOOP_1 (y = 5.3 + 5.68 = 10.98m).
    # FOB arm near edge = 5.33m from LOOP_1, width 3.0m -> far edge = 8.33m.
    # Required widening +1m = 9.33m from LOOP_1 (y = 5.3 + 9.33 = 14.63m).
    ys = [p[1] for p in plat_pts]
    max_y = max(ys)
    assert max_y == pytest.approx(5.3 + 9.33, abs=0.05)

    # Check FENCING layer lines
    fencing_lines = [
        e for e in out_doc.modelspace()
        if getattr(e.dxf, "layer", "") == "FENCING" and e.dxftype() == "LINE"
    ]
    assert len(fencing_lines) > 0
    # There must be a fencing line on the widened outer edge (y ~ 14.63m)
    widened_fence = [
        e for e in fencing_lines
        if abs(e.dxf.start.y - (5.3 + 9.33)) < 0.1 and abs(e.dxf.end.y - (5.3 + 9.33)) < 0.1
    ]
    assert len(widened_fence) >= 1


def test_fob_widening_only_on_insufficient_platform_and_not_on_sufficient_platform(tmp_path):
    """Widening applies ONLY to platforms where the FOB arm extends beyond the platform.

    A platform with sufficient width (e.g. 7.0m) must NOT be widened.
    """
    import ezdxf
    from config.loader import ESPConfig, PlatformRequest
    from fob.config import FOBConfig
    from pipeline.orchestrator import ESPGenerator
    from track.specs import LoopSpec

    src = tmp_path / "source.dxf"
    out = tmp_path / "result.dxf"

    doc = ezdxf.new("R2010")
    doc.layers.add("MAIN_TRACK", color=1)
    doc.modelspace().add_line((0.0, 0.0), (1200.0, 0.0), dxfattribs={"layer": "MAIN_TRACK"})
    doc.saveas(str(src))

    loops = [
        LoopSpec("LOOP_1", 5.3, "LEFT", 200.0, 1000.0, extend_start_m=0.0, extend_end_m=0.0),
    ]

    # Platform 1: Narrow (4.0m width on LOOP_1, far offset 5.68m < 8.33m) -> Needs widening
    p1_cfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="LOOP_1",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.LEFT,
        clearance=1.68,
        platform_width=4.0,
        platform_length=400.0,
        center_on_track=True,
        output_layer="PLATFORM_1",
    )
    # Platform 2: Standard (7.0m width on MAIN_LINE, far offset 8.68m >= 8.33m) -> Does NOT need widening
    p2_cfg = PlatformConfig(
        source_dxf=str(src),
        output_dxf=str(out),
        track_layer="MAIN_LINE",
        platform_type=PlatformType.SIDE,
        side=PlatformSide.RIGHT,
        clearance=1.68,
        platform_width=7.0,
        platform_length=400.0,
        center_on_track=True,
        output_layer="PLATFORM_2",
    )
    platforms = [PlatformRequest("LOOP_1", p1_cfg), PlatformRequest("MAIN_LINE", p2_cfg)]

    # FOB connecting both platforms with landing arms
    fobs = [
        FOBConfig(
            reference_track="MAIN_LINE",
            reference_chainage=600.0,
            platforms=["PLATFORM_1", "PLATFORM_2"],
            width=3.0,
            arms={
                "PLATFORM_1": {"length": 15.0, "side": "LEFT"},
                "PLATFORM_2": {"length": 15.0, "side": "LEFT"},
            },
            output_layer="FOB_1",
        )
    ]

    esp_cfg = ESPConfig(
        source_path=str(src),
        output_dxf=str(out),
        track_source_layer="MAIN_TRACK",
        loops=loops,
        platforms=platforms,
        fobs=fobs,
    )

    gen = ESPGenerator(esp_cfg)
    gen.run()

    out_doc = ezdxf.readfile(str(out))

    # Platform 1 (narrow) must be widened (stepped 9-vertex polyline)
    plat1 = [e for e in out_doc.modelspace() if getattr(e.dxf, "layer", "") == "PLATFORM_1"]
    assert len(plat1) >= 1
    assert len(list(plat1[0].get_points())) == 9

    # Platform 2 (7m, sufficient) must NOT be widened (standard 4-corner rectangle)
    plat2 = [e for e in out_doc.modelspace() if getattr(e.dxf, "layer", "") == "PLATFORM_2"]
    assert len(plat2) >= 1
    plat2_pts = list(plat2[0].get_points())
    assert len(plat2_pts) in (4, 5)

    # Check FOB label: centered, MIDDLE_CENTER alignment, does not touch track
    fob_texts = [
        e for e in out_doc.modelspace()
        if getattr(e.dxf, "layer", "") == "FOB_1" and e.dxftype() == "TEXT"
    ]
    assert len(fob_texts) >= 1
    fob_label_entity = fob_texts[0]
    assert fob_label_entity.dxf.text == "FOOT OVER BRIDGE"
    # Middle-center alignment in DXF: halign=1, valign=2
    assert fob_label_entity.dxf.halign == 1
    assert fob_label_entity.dxf.valign == 2
    # Check that Y-center is between tracks (MAIN_LINE at y=0, LOOP_1 at y=5.3)
    # The midpoint of the track gap is y = 2.65
    align_y = fob_label_entity.dxf.align_point[1]
    assert align_y == pytest.approx(2.65, abs=0.5)


