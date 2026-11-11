"""Station-relative chainage labels (single centralized implementation).

Station building centre line = chainage 0.000. Every ESP marker shows its
distance along the track alignment from that datum:

* positive in the increasing / forward direction,
* negative in the decreasing / backward direction.

All distances are measured ALONG the alignment (never straight-line XY)
via :mod:`common.geometry` and :mod:`common.alignment`.
"""

from __future__ import annotations

import math
from typing import Dict, List

from common.alignment import nearest_point_on_alignment
from common.constants import TEXT_CLEARANCE_M
from common.dxf import (
    _inflate,
    _register_box,
    ensure_layer as _ensure_layer,
    ensure_text_style as _style,
    estimate_text_aabb as _aabb,
    resolve_text_insert as _resolve,
)
from common.geometry import (
    Point,
    readable_angle_deg,
)

#: DXF layer + colour for every station-relative chainage label (red).
CHAINAGE_LAYER: str = "CHAINAGE"
CHAINAGE_COLOR: int = 1
#: Linetype for chainage leader lines (dotted).
CHAINAGE_LINETYPE: str = "DASHED"
#: Text height (m) of the vertical chainage labels.
CHAINAGE_TEXT_HEIGHT_M: float = 1.0
#: Leader length (m) from the marker base, transverse to the track.
CHAINAGE_LEADER_LEN_M: float = 20.0
#: Suffix clarifying the datum (From Centre of Station Building).
CHAINAGE_SUFFIX: str = "(F/CSB)"
#: Extra lift (m) of the text insert past the leader tip along the leader.
CHAINAGE_TEXT_LIFT_M: float = 0.0
#: Sideways offset (m) of the text from the leader axis.
CHAINAGE_TEXT_SIDE_M: float = 0.6
#: Clearance (m) past the farmost geometry for the shared outer line.
CHAINAGE_OUTER_MARGIN_M: float = 20.0
#: Two markers with the same tag whose relative chainages differ by less than this.
CHAINAGE_PARALLEL_TOL_M: float = 1.0


def format_relative_chainage(rel_m: float) -> str:
    """Format a relative chainage in KML-style plus notation: ``+ 0+291`` / ``- 0+120`` / ``+ 0+000``."""
    try:
        value = float(rel_m)
    except (TypeError, ValueError):
        value = 0.0
    if not math.isfinite(value):
        value = 0.0

    sign = "-" if value < -0.0005 else "+"
    abs_m = abs(value)
    km = int(abs_m // 1000)
    m = int(abs_m % 1000)
    return f"{sign} {km}+{m:03d}"


def format_chainage_label(tag: str, rel_m: float) -> str:
    """Full marker label, e.g. ``RAMP END AT CH + 0+291`` / ``SRJ AT CH - 0+150``."""
    clean = str(tag or "").strip() or "CH"
    return f"{clean} AT CH {format_relative_chainage(rel_m)}"


class StationDatum:
    """Station-centre datum (0.000) for every track.

    ``center`` is the station building centre (x, y). ``tracks`` maps
    track name -> centreline points. For each track the datum
    chainage is the projection of ``center`` onto that track.
    """

    def __init__(
        self,
        center: Point,
        tracks: Dict[str, List[Point]],
        main_track: str = "MAIN_LINE",
    ) -> None:
        self.center: Point = (float(center[0]), float(center[1]))
        self.main_track: str = str(main_track or "MAIN_LINE")
        self.datum: Dict[str, float] = {}
        for name, pts in (tracks or {}).items():
            try:
                cleaned = [(float(p[0]), float(p[1])) for p in pts]
                if len(cleaned) < 2:
                    continue
                proj = nearest_point_on_alignment(cleaned, self.center)
                self.datum[str(name)] = float(proj.chainage)
            except Exception:
                continue

    @property
    def has_datum(self) -> bool:
        return bool(self.datum)

    def station_chainage_on(self, track: str) -> float | None:
        """Absolute datum chainage on ``track`` (None when unknown)."""
        return self.datum.get(str(track))

    def relative_for_main(self, main_chainage: float) -> float:
        """Relative chainage for a MAIN-datum absolute value."""
        base = self.datum.get(self.main_track)
        if base is None:
            base = next(iter(self.datum.values()), 0.0)
        return float(main_chainage) - float(base)

    def relative_for_track(self, track: str, abs_chainage: float) -> float:
        """Relative chainage for an absolute chainage on ``track``."""
        base = self.datum.get(str(track))
        if base is None:
            return self.relative_for_main(float(abs_chainage))
        return float(abs_chainage) - float(base)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v:.3f}" for k, v in sorted(self.datum.items()))
        return f"StationDatum(center={self.center}, {items})"


def relative_for_point_on_track(
    tracks: Dict[str, List[Point]],
    datum: StationDatum,
    track: str,
    point: Point,
) -> float:
    """Relative chainage of ``point`` measured ALONG ``track``."""
    name = str(track)
    pts = (tracks or {}).get(name)
    if pts is None or len(list(pts)) < 2:
        return datum.relative_for_main(0.0)
    cleaned = [(float(p[0]), float(p[1])) for p in pts]
    proj = nearest_point_on_alignment(cleaned, (float(point[0]), float(point[1])))
    return datum.relative_for_track(name, float(proj.chainage))


def draw_chainage_annotation(
    doc,
    base_point: Point,
    tangent: Point,
    relative_m: float,
    tag: str,
    leader_len: float = CHAINAGE_LEADER_LEN_M,
    layer: str = CHAINAGE_LAYER,
    color: int = CHAINAGE_COLOR,
    height: float = CHAINAGE_TEXT_HEIGHT_M,
    lift: float = CHAINAGE_TEXT_LIFT_M,
    linetype: str = CHAINAGE_LINETYPE,
    side: str = "LEFT",
    other_side_tag: str | None = None,
) -> int:
    """Draw one station-relative chainage label (dotted leader + vertical text)."""
    try:
        _ensure_layer(doc, layer, color, linetype=linetype)
        tx, ty = float(tangent[0]), float(tangent[1])
        norm = math.hypot(tx, ty) or 1.0
        tx, ty = tx / norm, ty / norm
        is_right = str(side or "LEFT").strip().upper() == "RIGHT"
        if is_right:
            nx, ny = ty, -tx
        else:
            nx, ny = -ty, tx
        bx, by = float(base_point[0]), float(base_point[1])
        length = float(leader_len) or float(CHAINAGE_LEADER_LEN_M)
        tip = (bx + nx * length, by + ny * length)
        msp = doc.modelspace()
        try:
            msp.add_line(
                (bx, by), tip,
                dxfattribs={
                    "layer": layer,
                    "color": int(color),
                    "linetype": str(linetype or CHAINAGE_LINETYPE),
                },
            )
        except Exception:
            return 0
        label = format_chainage_label(tag, relative_m)
        try:
            ang = readable_angle_deg(90.0)
        except Exception:
            ang = 90.0
        try:
            lift_m = float(lift)
        except (TypeError, ValueError):
            lift_m = float(CHAINAGE_TEXT_LIFT_M)
        try:
            side_m = float(CHAINAGE_TEXT_SIDE_M)
        except (TypeError, ValueError):
            side_m = 0.3

        if is_right:
            insert = (tip[0] - nx * lift_m - tx * side_m,
                      tip[1] - ny * lift_m - ty * side_m)
            halign = 0
            anchor = "left-baseline"
        else:
            insert = (tip[0] + nx * lift_m - tx * side_m,
                      tip[1] + ny * lift_m - ty * side_m)
            halign = 2
            anchor = "right-baseline"

        try:
            style = _style(doc)
        except Exception:
            style = "Standard"
        try:
            pos = _resolve(doc, label, float(height), float(ang), insert,
                           anchor=anchor)
        except Exception:
            pos = insert
        try:
            px, py = float(pos[0]), float(pos[1])
        except Exception:
            px, py = float(insert[0]), float(insert[1])
        try:
            msp.add_text(
                label,
                height=float(height),
                dxfattribs={
                    "layer": layer,
                    "color": int(color),
                    "style": style,
                    "rotation": float(ang),
                    "insert": (px, py, 0),
                    "halign": halign,
                    "valign": 0,
                    "align_point": (px, py, 0),
                },
            )
        except Exception:
            try:
                msp.add_text(
                    label,
                    height=float(height),
                    dxfattribs={
                        "layer": layer,
                        "color": int(color),
                        "style": style,
                        "rotation": float(ang),
                        "insert": (px, py, 0),
                    },
                )
            except Exception:
                return 0
        try:
            box = _inflate(_aabb(label, float(height), float(ang), (px, py),
                                 anchor, 0.7), TEXT_CLEARANCE_M)
            _register_box(doc, box)
        except Exception:
            pass

        if other_side_tag:
            try:
                other_label = format_chainage_label(other_side_tag, relative_m)
                other_side_offset = side_m + float(height) + 0.2
                if is_right:
                    ins_other = (
                        tip[0] - nx * lift_m + tx * other_side_offset,
                        tip[1] - ny * lift_m + ty * other_side_offset,
                    )
                    halign_other = 0
                    anc_other = "left-baseline"
                else:
                    ins_other = (
                        tip[0] + nx * lift_m + tx * other_side_offset,
                        tip[1] + ny * lift_m + ty * other_side_offset,
                    )
                    halign_other = 2
                    anc_other = "right-baseline"
                px_o, py_o = float(ins_other[0]), float(ins_other[1])
                try:
                    msp.add_text(
                        other_label,
                        height=float(height),
                        dxfattribs={
                            "layer": layer,
                            "color": int(color),
                            "style": style,
                            "rotation": float(ang),
                            "insert": (px_o, py_o, 0),
                            "halign": halign_other,
                            "valign": 0,
                            "align_point": (px_o, py_o, 0),
                        },
                    )
                except Exception:
                    try:
                        msp.add_text(
                            other_label,
                            height=float(height),
                            dxfattribs={
                                "layer": layer,
                                "color": int(color),
                                "style": style,
                                "rotation": float(ang),
                                "insert": (px_o, py_o, 0),
                            },
                        )
                    except Exception:
                        pass
                try:
                    box_o = _inflate(_aabb(other_label, float(height), float(ang), (px_o, py_o),
                                           anc_other, 0.7), TEXT_CLEARANCE_M)
                    _register_box(doc, box_o)
                except Exception:
                    pass
            except Exception:
                pass

        return 1
    except Exception:
        return 0


__all__ = [
    "CHAINAGE_LAYER",
    "CHAINAGE_COLOR",
    "CHAINAGE_LINETYPE",
    "CHAINAGE_TEXT_HEIGHT_M",
    "CHAINAGE_LEADER_LEN_M",
    "CHAINAGE_OUTER_MARGIN_M",
    "CHAINAGE_PARALLEL_TOL_M",
    "CHAINAGE_SUFFIX",
    "CHAINAGE_TEXT_LIFT_M",
    "CHAINAGE_TEXT_SIDE_M",
    "StationDatum",
    "draw_chainage_annotation",
    "format_chainage_label",
    "format_relative_chainage",
    "relative_for_point_on_track",
]
