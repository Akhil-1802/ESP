"""Station flag symbol drawn as pure DXF geometry."""

from __future__ import annotations

from typing import Tuple

from common.dxf import ensure_layer as _ensure_layer

Point = Tuple[float, float]

FLAG_HEIGHT: float = 10.0
FLAG_WIDTH: float = 15.0
FLAG_LAYER: str = "STATION-FLAG"
FLAG_COLOR: int = 1  # Red (ACI 1)
HATCH_SPACING: float = 1.0
POLE_EXTENSION: float = 2.0


def _waving_flag_points(
    width: float = FLAG_WIDTH,
    height: float = FLAG_HEIGHT,
    n_samples: int = 24,
) -> list[Point]:
    """Generate the local (x, y) vertices for the closed waving flag outline."""
    W, H = width, height
    # Top edge Bézier control points: slight dip near pole, crest around mid-span, droop to tip
    top_p0 = (0.0, 0.0)
    top_p1 = (0.28 * W, -0.22 * H)
    top_p2 = (0.55 * W, 0.05 * H)
    top_p3 = (W, -0.73 * H)

    # Bottom edge Bézier control points: rises from lower ring, crests, dips to meet tip
    bot_p0 = (0.0, -H)
    bot_p1 = (0.35 * W, -0.50 * H)
    bot_p2 = (0.75 * W, -0.85 * H)
    bot_p3 = (W, -0.73 * H)

    def _eval_bezier(p0: Point, p1: Point, p2: Point, p3: Point, t: float) -> Point:
        omt = 1.0 - t
        return (
            omt**3 * p0[0] + 3 * omt**2 * t * p1[0] + 3 * omt * t**2 * p2[0] + t**3 * p3[0],
            omt**3 * p0[1] + 3 * omt**2 * t * p1[1] + 3 * omt * t**2 * p2[1] + t**3 * p3[1],
        )

    top_curve = [_eval_bezier(top_p0, top_p1, top_p2, top_p3, i / n_samples) for i in range(n_samples + 1)]
    bot_curve = [_eval_bezier(bot_p0, bot_p1, bot_p2, bot_p3, i / n_samples) for i in range(n_samples + 1)]

    # Closed polygon: top curve (0,0) -> (W, -0.73H), reversed bottom curve (W, -0.73H) -> (0, -H)
    return top_curve + list(reversed(bot_curve))


def _clip_diagonal_to_polygon(
    poly: list[Point],
    c: float,
) -> list[Tuple[Point, Point]]:
    """Clip diagonal line y = x + c against polygon poly, returning interior segments."""
    intersections: list[Point] = []
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        f1 = p1[1] - p1[0] - c
        f2 = p2[1] - p2[0] - c
        if abs(f2 - f1) < 1e-9:
            continue
        t = -f1 / (f2 - f1)
        if 0.0 <= t <= 1.0:
            ix = p1[0] + t * (p2[0] - p1[0])
            iy = p1[1] + t * (p2[1] - p1[1])
            intersections.append((ix, iy))

    unique: list[Point] = []
    for pt in intersections:
        if not any(abs(pt[0] - u[0]) < 1e-3 and abs(pt[1] - u[1]) < 1e-3 for u in unique):
            unique.append(pt)

    unique.sort(key=lambda p: p[0])
    segments: list[Tuple[Point, Point]] = []
    for i in range(0, len(unique) - 1, 2):
        segments.append((unique[i], unique[i + 1]))
    return segments


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
    """Draw the red waving station flag symbol with rings and diagonal hatching into doc."""
    _ensure_layer(doc, layer, color)
    msp = doc.modelspace()

    w = FLAG_WIDTH * scale
    h = FLAG_HEIGHT * scale
    pole_ext = POLE_EXTENSION * scale
    local_pts = _waving_flag_points(w, h)

    u = (up[0], up[1])
    r = (right[0], right[1])

    global_pts = [_transform(p, pole_base, u, r) for p in local_pts]
    attrs = {"layer": layer, "color": color}

    # 1. Closed outline of the flag body
    if doc.dxfversion >= "AC1015":
        msp.add_lwpolyline(global_pts, close=True, dxfattribs=attrs)
    else:
        poly = msp.add_polyline2d(global_pts, dxfattribs=attrs)
        poly.close(True)

    # 2. Vertical pole line
    pole_top = _transform((0.0, pole_ext), pole_base, u, r)
    pole_bot = _transform((0.0, -h - pole_ext), pole_base, u, r)
    msp.add_line(pole_top, pole_bot, dxfattribs=attrs)

    # 3. Interior 45-degree diagonal hatch lines
    spacing = HATCH_SPACING * scale
    min_c = -h - w
    max_c = 0.0
    c = min_c
    while c <= max_c:
        segs = _clip_diagonal_to_polygon(local_pts, c)
        for s0, s1 in segs:
            g0 = _transform(s0, pole_base, u, r)
            g1 = _transform(s1, pole_base, u, r)
            msp.add_line(g0, g1, dxfattribs=attrs)
        c += spacing
