"""Platform DXF writing (1:1 real-world scale).

Primitives (layers, polylines, dimensions) live in common.dxf;
this module keeps only platform-specific writing (outlines, stairs,
labels) so the drawing style stays in one place.
"""

from __future__ import annotations

from ezdxf.document import Drawing

from common.dxf import (
    add_polyline as _add_polyline,
    draw_arrow_dimension,
    ensure_layer as _ensure_layer,
    ensure_text_style as _ensure_text_style,
    resolve_text_insert as _resolve_text_insert,
)
from platform_gen.config import PlatformConfig
from platform_gen.models import PlatformResult


def _add_label(doc: Drawing, label, layer: str, color: int):
    if doc.dxfversion >= "AC1015":
        pos = _resolve_text_insert(
            doc, label.text, label.height, label.rotation, label.position, anchor="middle-center"
        )
        mtext = doc.modelspace().add_mtext(
            label.text,
            dxfattribs={
                "layer": layer,
                "color": color,
                "style": _ensure_text_style(doc),
                "char_height": label.height,
                "rotation": label.rotation,
            },
        )
        mtext.set_location(pos, attachment_point=5)
        return mtext
    pos = _resolve_text_insert(
        doc, label.text.replace("\\P", " "), label.height, label.rotation, label.position
    )
    return doc.modelspace().add_text(
        label.text.replace("\\P", " "),
        dxfattribs={
            "layer": layer,
            "color": color,
            "style": _ensure_text_style(doc),
            "height": label.height,
            "rotation": label.rotation,
            "insert": (pos[0], pos[1], pos[2] if len(tuple(pos)) >= 3 else 0),
        },
    )


def write_platform(doc: Drawing, result: PlatformResult, cfg: PlatformConfig) -> None:
    """Write platform outline, stairs, labels and dimensions to DXF."""
    _ensure_layer(doc, cfg.output_layer, cfg.platform_color)
    _ensure_layer(doc, cfg.text_layer, cfg.platform_color)

    msp = doc.modelspace()

    # --- platform outline, true scale, closed polyline -----------------
    outline_pts = [(p[0], p[1]) for p in result.outline]
    _add_polyline(
        doc,
        outline_pts,
        cfg.output_layer,
        cfg.platform_color,
        close=True,
    )

    if cfg.add_hatch:
        if doc.dxfversion < "AC1015":
            raise ValueError("Interior hatch requires a DXF version AC1015 (R2000) or newer")
        hatch = msp.add_hatch(color=cfg.platform_color, dxfattribs={"layer": cfg.output_layer})
        hatch.set_pattern_fill(cfg.hatch_pattern, scale=1.0)
        hatch.paths.add_polyline_path(outline_pts, is_closed=True)

    # --- stairs -------------------------------------------------------
    if result.stairs:
        _ensure_layer(doc, cfg.stair_layer, cfg.stair_color)
        for stair in result.stairs:
            stair_pts = [(p[0], p[1]) for p in stair.outline]
            _add_polyline(
                doc,
                stair_pts,
                cfg.stair_layer,
                cfg.stair_color,
                close=True,
            )
            for tread_line in stair.tread_lines:
                p1, p2 = tread_line
                _add_polyline(
                    doc,
                    [(p1[0], p1[1]), (p2[0], p2[1])],
                    cfg.stair_layer,
                    cfg.stair_color,
                    close=False,
                )

    # --- text labels -------------------------------------------------------
    for label in result.labels:
        _add_label(doc, label, cfg.text_layer, cfg.platform_color)

    # --- dimensions (width / clearance) with arrowheads ------------------
    if result.dimensions:
        _ensure_layer(doc, cfg.dimension_layer, cfg.platform_color)
        for dim in result.dimensions:
            draw_arrow_dimension(
                doc,
                dim.p1,
                dim.p2,
                dim.dim_offset,
                dim.text,
                cfg.dimension_layer,
                cfg.platform_color,
                cfg.dim_text_height,
            )


__all__ = ["write_platform"]
