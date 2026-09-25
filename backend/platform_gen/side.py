"""Side platform geometry generation."""

from __future__ import annotations

from typing import List

from common.geometry import (
    find_straight_window,
    offset_alignment,
    offset_point,
    point_at_chainage,
    rectangle_from_two_offsets,
)
from platform_gen.config import PlatformConfig
from platform_gen.models import DimensionSpec, LabelSpec, PlatformResult, StairSpec, _order_outward
from platform_gen.stairs import generate_stair
from platform_gen.track import Track


def side_platform(track: Track, cfg: PlatformConfig) -> PlatformResult:
    """Generate geometry for a side platform along one track."""
    start_chainage = cfg.resolved_start_chainage(track.length)
    end_chainage = cfg.resolved_end_chainage(track.length)
    length = end_chainage - start_chainage

    stairs: List[StairSpec] = []
    if (cfg.stair_length is not None or cfg.arm_length is not None) and (cfg.stair_length != 0 and cfg.arm_length != 0):
        arm_len = cfg.effective_arm_length
        if arm_len <= 0:
            raise ValueError("stair_length / arm_length must be greater than zero")

        mid_offset = cfg.clearance + cfg.platform_width / 2.0
        start_point = offset_point(
            point_at_chainage(track.points, start_chainage),
            mid_offset, cfg.side.value,
        )
        end_point = offset_point(
            point_at_chainage(track.points, end_chainage),
            mid_offset, cfg.side.value,
        )
        stair_width = cfg.stair_width if cfg.stair_width is not None else cfg.platform_width

        left_stair = generate_stair(
            platform_start=start_point,
            platform_end=end_point,
            platform_width=cfg.platform_width,
            stair_length=arm_len,
            stair_width=stair_width,
            side=-1,
        )
        right_stair = generate_stair(
            platform_start=start_point,
            platform_end=end_point,
            platform_width=cfg.platform_width,
            stair_length=arm_len,
            stair_width=stair_width,
            side=1,
        )
        stairs = [left_stair, right_stair]

    if cfg.center_on_track:
        start_chainage = find_straight_window(
            track.points,
            end_chainage - start_chainage,
            start_chainage,
            cfg.straight_tolerance_degrees,
        )
        end_chainage = start_chainage + (cfg.platform_length or end_chainage - start_chainage)

    near = offset_alignment(
        track.points, start_chainage, end_chainage,
        cfg.clearance, cfg.side.value, cfg.curve_samples,
    )
    far = offset_alignment(
        track.points, start_chainage, end_chainage,
        cfg.clearance + cfg.platform_width, cfg.side.value, cfg.curve_samples,
    )
    outline = rectangle_from_two_offsets(near, far)

    length = end_chainage - start_chainage
    mid_ch = (start_chainage + end_chainage) / 2.0
    label_ch = min(start_chainage + length * 0.35, max(start_chainage + 15.0, mid_ch - 75.0))
    mid_near = offset_alignment(
        track.points, label_ch, label_ch, cfg.clearance, cfg.side.value, 1
    )[0]
    mid_far = offset_alignment(
        track.points, label_ch, label_ch,
        cfg.clearance + cfg.platform_width, cfg.side.value, 1
    )[0]
    label_position = (
        (mid_near[0] + mid_far[0]) / 2.0,
        (mid_near[1] + mid_far[1]) / 2.0,
    )

    dim_ch_clearance = max(start_chainage + 10.0, min(mid_ch - 25.0, end_chainage - 10.0))
    dim_ch_width = max(start_chainage + 5.0, min(mid_ch - 36.0, end_chainage - 15.0))

    sp_clr = point_at_chainage(track.points, dim_ch_clearance)
    tx_c, ty_c = sp_clr.tangent[0], sp_clr.tangent[1]
    tn_c = (tx_c * tx_c + ty_c * ty_c) ** 0.5 or 1.0
    ux_c, uy_c = tx_c / tn_c, ty_c / tn_c

    dim_near_c = offset_alignment(
        track.points, dim_ch_clearance, dim_ch_clearance, cfg.clearance, cfg.side.value, 1
    )[0]
    cp1, cp2 = _order_outward(sp_clr.point, dim_near_c, ux_c, uy_c)
    clearance_dim = DimensionSpec(
        cp1, cp2, dim_offset=2.0, text=f"{cfg.clearance:.2f}",
    )

    sp_w = point_at_chainage(track.points, dim_ch_width)
    tx_w, ty_w = sp_w.tangent[0], sp_w.tangent[1]
    tn_w = (tx_w * tx_w + ty_w * ty_w) ** 0.5 or 1.0
    ux_w, uy_w = tx_w / tn_w, ty_w / tn_w
    out_x, out_y = -ux_w, -uy_w

    dim_near_w = offset_alignment(
        track.points, dim_ch_width, dim_ch_width, cfg.clearance, cfg.side.value, 1
    )[0]
    dim_far_w = offset_alignment(
        track.points, dim_ch_width, dim_ch_width,
        cfg.clearance + cfg.platform_width, cfg.side.value, 1
    )[0]
    p_near, p_far = _order_outward(dim_near_w, dim_far_w, out_x, out_y)

    if (cfg.stair_length is not None or cfg.arm_length is not None) and stairs:
        left_stair = stairs[0]
        stair_w = cfg.stair_width if cfg.stair_width is not None else cfg.platform_width
        sp_near, sp_far = _order_outward(left_stair.outline[3], left_stair.outline[2], out_x, out_y)

        if cfg.stair_width is not None and abs(cfg.stair_width - cfg.platform_width) > 1e-4:
            dims = [
                DimensionSpec(sp_near, sp_far, dim_offset=2.0, text=f"{stair_w:.2f}"),
                DimensionSpec(p_near, p_far, dim_offset=2.0, text=f"{cfg.platform_width:.2f}"),
                clearance_dim,
            ]
        else:
            dims = [
                DimensionSpec(p_near, p_far, dim_offset=2.0, text=f"{cfg.platform_width:.2f}"),
                clearance_dim,
            ]
    else:
        dims = [
            DimensionSpec(p_near, p_far, dim_offset=2.0, text=f"{cfg.platform_width:.2f}"),
            clearance_dim,
        ]

    label_lines = [f"{cfg.platform_name} ({length:.0f}X{cfg.platform_width:g}m)"]
    if cfg.tag:
        label_lines.append(cfg.tag)

    labels = [
        LabelSpec(label_position, "\\P".join(label_lines), cfg.text_height)
    ]

    return PlatformResult(
        outline=outline,
        near_edge=near,
        far_edge=far,
        dimensions=dims,
        labels=labels,
        stairs=stairs,
        computed_width=cfg.platform_width,
        computed_length=length,
    )
