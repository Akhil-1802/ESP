"""Station flag symbol drawn as pure DXF geometry."""

from __future__ import annotations

from typing import Tuple

from common.dxf import ensure_layer as _ensure_layer

Point = Tuple[float, float]

FLAG_HEIGHT: float = 10.0
FLAG_WIDTH: float = 15.0
FLAG_LAYER: str = "STATION-FLAG"
FLAG_COLOR: int = 1  # Red (ACI 1)


def _waving_flag_points(
    width: float = FLAG_WIDTH,
    height: float = FLAG_HEIGHT,
    n_samples: int = 24,
) -> list[Point]:
    """Generate the local (x, y) vertices for the closed waving flag outline."""
    W, H = width, height
    p0 = (0.0, 0.0)
    p1 = (0.30 * W, 0.15 * H)
    p2 = (0.65 * W, -0.55 * H)
    p3 = (W, -0.30 * H)

    top_curve = []
    for i in range(n_samples + 1):
        t = i / n_samples
        omt = 1.0 - t
        x = omt**3 * p0[0] + 3 * omt**2 * t * p1[0] + 3 * omt * t**2 * p2[0] + t**3 * p3[0]
        y = omt**3 * p0[1] + 3 * omt**2 * t * p1[1] + 3 * omt * t**2 * p2[1] + t**3 * p3[1]
        top_curve.append((x, y))

    bottom_curve = [(x, y - H) for (x, y) in reversed(top_curve)]
    return top_curve + bottom_curve


def _transform(local: Point, base: Point, up: Point, right: Point) -> Point:
    """Map a local (x_right, y_up) coordinate to global DXF."""
    lx, ly = local
    return (
        base[0] + right[0] * lx + up[0] * ly,
        base[1] + right[1] * lx + up[1] * ly,
    )


def draw_station_flag(
    doc,
    pole_base: Point,
    up: Point,
    right: Point,
    *,
    layer: str = FLAG_LAYER,
    color: int = FLAG_COLOR,
    scale: float = 1.0,
) -> None:
    """Draw the red waving station flag symbol into doc."""
    _ensure_layer(doc, layer, color)
    msp = doc.modelspace()

    w = FLAG_WIDTH * scale
    h = FLAG_HEIGHT * scale
    local_pts = _waving_flag_points(w, h)

    u = (up[0], up[1])
    r = (right[0], right[1])

    global_pts = [_transform(p, pole_base, u, r) for p in local_pts]

    attrs = {"layer": layer, "color": color}
    if doc.dxfversion >= "AC1015":
        msp.add_lwpolyline(global_pts, close=True, dxfattribs=attrs)
    else:
        poly = msp.add_polyline2d(global_pts, dxfattribs=attrs)
        poly.close(True)
