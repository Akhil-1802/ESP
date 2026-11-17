"""Island platform geometry generation."""

from __future__ import annotations
import math

from common.geometry import (
    find_straight_window,
    nearest_point_on_alignment,
    offset_alignment,
    point_at_chainage,
    point_side,
    rectangle_from_two_offsets,
    validate_straight_interval,
)
from platform_gen.config import PlatformConfig
from platform_gen.models import DimensionSpec, LabelSpec, PlatformResult, _order_outward
from platform_gen.track import Track


def island_platform(track1: Track, track2: Track, cfg: PlatformConfig) -> PlatformResult:
    """Generate geometry for an island platform between two tracks."""
    end_chainage = cfg.resolved_end_chainage(track1.length)
    start_chainage = cfg.resolved_start_chainage(track1.length)
    if cfg.center_on_track and cfg.center_chainage is not None:
        validate_straight_interval(
            track1.points,
            start_chainage,
            end_chainage,
            cfg.straight_tolerance_degrees,
            cfg.track_layer or track1.name,
        )
    elif cfg.center_on_track:
        start_chainage = find_straight_window(
            track1.points,
            end_chainage - start_chainage,
            start_chainage,
            cfg.straight_tolerance_degrees,
        )
        end_chainage = start_chainage + (cfg.platform_length or end_chainage - start_chainage)

    mid_ch1 = (start_chainage + end_chainage) / 2.0
    sp_mid1 = point_at_chainage(track1.points, mid_ch1)
    proj_on_2 = nearest_point_on_alignment(track2.points, sp_mid1.point)
    side1 = point_side(sp_mid1, proj_on_2.point)

    sp_mid2 = point_at_chainage(track2.points, proj_on_2.chainage)
    proj_on_1 = nearest_point_on_alignment(track1.points, sp_mid2.point)
    side2 = point_side(sp_mid2, proj_on_1.point)

    start_pt1 = point_at_chainage(track1.points, start_chainage).point
    end_pt1 = point_at_chainage(track1.points, end_chainage).point
    start_ch2 = nearest_point_on_alignment(track2.points, start_pt1).chainage
    end_ch2 = nearest_point_on_alignment(track2.points, end_pt1).chainage

    edge1 = offset_alignment(
        track1.points, start_chainage, end_chainage,
        cfg.clearance, side1, cfg.curve_samples,
    )
    edge2 = offset_alignment(
        track2.points, start_ch2, end_ch2,
        cfg.clearance, side2, cfg.curve_samples,
    )
    outline = rectangle_from_two_offsets(edge1, edge2)

    length = end_chainage - start_chainage
    computed_width = ((edge1[0][0] - edge2[0][0]) ** 2 + (edge1[0][1] - edge2[0][1]) ** 2) ** 0.5

    label_ch = min(start_chainage + length * 0.35, max(start_chainage + 15.0, mid_ch1 - 75.0))
    pt_lab1 = offset_alignment(track1.points, label_ch, label_ch, cfg.clearance, side1, 1)[0]
    lab_ch2 = nearest_point_on_alignment(track2.points, pt_lab1).chainage
    pt_lab2 = offset_alignment(track2.points, lab_ch2, lab_ch2, cfg.clearance, side2, 1)[0]
    label_position = (
        (pt_lab1[0] + pt_lab2[0]) / 2.0,
        (pt_lab1[1] + pt_lab2[1]) / 2.0,
    )

    dim_ch_clearance = max(start_chainage + 10.0, min(mid_ch1 - 25.0, end_chainage - 10.0))
    dim_ch_width = max(start_chainage + 5.0, min(mid_ch1 - 36.0, end_chainage - 15.0))

    sp_clr1 = point_at_chainage(track1.points, dim_ch_clearance)
    tx_c, ty_c = sp_clr1.tangent[0], sp_clr1.tangent[1]
    tn_c = (tx_c * tx_c + ty_c * ty_c) ** 0.5 or 1.0
    ux_c, uy_c = tx_c / tn_c, ty_c / tn_c

    dim_near1 = offset_alignment(track1.points, dim_ch_clearance, dim_ch_clearance, cfg.clearance, side1, 1)[0]
    cp1, cp2 = _order_outward(sp_clr1.point, dim_near1, ux_c, uy_c)

    clr_ch2 = nearest_point_on_alignment(track2.points, sp_clr1.point).chainage
    sp_clr2 = point_at_chainage(track2.points, clr_ch2)
    dim_near2 = offset_alignment(track2.points, clr_ch2, clr_ch2, cfg.clearance, side2, 1)[0]
    cp3, cp4 = _order_outward(sp_clr2.point, dim_near2, ux_c, uy_c)

    sp_w = point_at_chainage(track1.points, dim_ch_width)
    tx_w, ty_w = sp_w.tangent[0], sp_w.tangent[1]
    tn_w = (tx_w * tx_w + ty_w * ty_w) ** 0.5 or 1.0
    out_x, out_y = -tx_w / tn_w, -ty_w / tn_w

    dim_w1 = offset_alignment(track1.points, dim_ch_width, dim_ch_width, cfg.clearance, side1, 1)[0]
    w_ch2 = nearest_point_on_alignment(track2.points, dim_w1).chainage
    dim_w2 = offset_alignment(track2.points, w_ch2, w_ch2, cfg.clearance, side2, 1)[0]
    p1, p2 = _order_outward(dim_w1, dim_w2, out_x, out_y)

    dims = [
        DimensionSpec(p1, p2, dim_offset=2.0, text=f"{computed_width:.2f}"),
        DimensionSpec(cp1, cp2, dim_offset=2.0, text=f"{cfg.clearance:.2f}"),
        DimensionSpec(cp3, cp4, dim_offset=2.0, text=f"{cfg.clearance:.2f}"),
    ]

    label_lines = [f"{cfg.platform_name} ({length:.0f}X{computed_width:g}m)", "(ISLAND)"]
    if cfg.tag:
        label_lines.append(cfg.tag)

    label_angle = (math.degrees(math.atan2(edge1[-1][1]-edge1[0][1],
                                          edge1[-1][0]-edge1[0][0])) + 90) % 180 - 90
    labels = [LabelSpec(label_position, "\\P".join(label_lines), cfg.text_height,
                        rotation=label_angle)]

    return PlatformResult(
        outline=outline, near_edge=edge1, far_edge=edge2,
        dimensions=dims, labels=labels,
        computed_width=computed_width, computed_length=length,
    )
