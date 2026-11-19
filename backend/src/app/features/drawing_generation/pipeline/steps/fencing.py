"""Platform fencing with station-exclusion gaps."""

from __future__ import annotations

import math

from ...domain.geometry.operations import readable_angle_deg
from ...formats.dxf.styles import ensure_text_style as _ensure_text_style
from ...formats.dxf.text import resolve_text_insert as _resolve_text_insert
from .base import PipelineStep

__all__ = ["FencingStep"]


class FencingStep(PipelineStep):
    """Pipeline step: Platform fencing with station-exclusion gaps."""

    @staticmethod
    def _inside_box(x: float, y: float, box, margin: float = 0.0) -> bool:
        minx, miny, maxx, maxy = box
        return (minx - margin) <= x <= (maxx + margin) and (miny - margin) <= y <= (maxy + margin)

    @staticmethod
    def _fencing_segments(far_edge, outline):
        """Extract all linear segments of the outer edge, each with direction and outward normal."""
        pts = [(float(p[0]), float(p[1])) for p in far_edge]
        if len(pts) >= 2 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-6:
            pts = pts[:-1]
        clean = []
        for p in pts:
            if not clean or math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-3:
                clean.append(p)
        if len(clean) < 2:
            return []

        cx = sum(float(p[0]) for p in outline) / len(outline)
        cy = sum(float(p[1]) for p in outline) / len(outline)

        segs = []
        for i in range(len(clean) - 1):
            ax, ay = clean[i]
            bx, by = clean[i + 1]
            dx, dy = bx - ax, by - ay
            el = math.hypot(dx, dy)
            if el < 1e-4:
                continue
            ex, ey = dx / el, dy / el
            nx, ny = -ey, ex
            if ((ax + bx) / 2.0 - cx) * nx + ((ay + by) / 2.0 - cy) * ny < 0.0:
                nx, ny = -nx, -ny
            segs.append((ax, ay, ex, ey, nx, ny, el))
        return segs

    @classmethod
    def _fencing_setup(cls, far_edge, outline):
        """Shared fencing alignment: longest segment of the outer edge plus outward normal."""
        segs = cls._fencing_segments(far_edge, outline)
        if not segs:
            return None
        # Return the longest segment so single-chord callers get the primary alignment
        return max(segs, key=lambda s: s[6])

    def _draw_fencing(
        self,
        doc,
        far_edge,
        outline,
        exclusions,
        ext: float = 0.0,
        frac=None,
    ) -> None:
        """Draw fencing on the platform outer edge, tracing any localized widening steps."""
        layer = "FENCING"
        if layer not in doc.layers:
            doc.layers.add(layer, color=1)

        segs = self._fencing_segments(far_edge, outline)
        if not segs:
            return

        msp = doc.modelspace()
        post_size = 0.6
        post_spacing = 5.0
        half = post_size / 2.0
        rail_off = post_size / 2.0

        for ax, ay, ex, ey, nx, ny, el in segs:
            # Draw boundary line for this segment
            msp.add_line(
                (ax, ay),
                (ax + ex * el, ay + ey * el),
                dxfattribs={"layer": layer, "color": 1},
            )

            # Only place posts and rails on segments long enough to accommodate them
            if el < 3.0:
                continue

            drawn = []
            positions = []
            d = 0.0
            while d <= el + 1e-6:
                positions.append(min(d, el))
                d += post_spacing
            positions.append(half)
            positions.append(el - half)
            for dd in sorted(set(round(p, 6) for p in positions)):
                if dd - half < -1e-9 or dd + half > el + 1e-9:
                    continue
                px = ax + ex * dd
                py = ay + ey * dd
                ccx, ccy = px + nx * post_size / 2.0, py + ny * post_size / 2.0
                if not any(self._inside_box(ccx, ccy, box, 1.0) for box in exclusions):
                    c1 = (px - ex * half, py - ey * half)
                    c2 = (px + ex * half, py + ey * half)
                    c3 = (c2[0] + nx * post_size, c2[1] + ny * post_size)
                    c4 = (c1[0] + nx * post_size, c1[1] + ny * post_size)
                    msp.add_lwpolyline(
                        [(c1[0], c1[1]), (c2[0], c2[1]), (c3[0], c3[1]), (c4[0], c4[1])],
                        close=True,
                        dxfattribs={"layer": layer, "color": 1},
                    )
                    drawn.append(dd)

            def _rail_pt(dd, _ax=ax, _ay=ay, _ex=ex, _ey=ey, _nx=nx, _ny=ny):
                return (_ax + _ex * dd + _nx * rail_off, _ay + _ey * dd + _ny * rail_off)

            if drawn:
                if drawn[0] - half > 1e-9:
                    msp.add_line(_rail_pt(0.0), _rail_pt(drawn[0] - half), dxfattribs={"layer": layer, "color": 1})
                for d0, d1 in zip(drawn, drawn[1:]):
                    if d1 - d0 > post_spacing + 1e-6:
                        continue
                    msp.add_line(_rail_pt(d0 + half), _rail_pt(d1 - half), dxfattribs={"layer": layer, "color": 1})
                if el - (drawn[-1] + half) > 1e-9:
                    msp.add_line(_rail_pt(drawn[-1] + half), _rail_pt(el), dxfattribs={"layer": layer, "color": 1})

        # Place the "FENCING" text label on the longest segment
        longest_seg = max(segs, key=lambda s: s[6])
        ax, ay, ex, ey, nx, ny, el = longest_seg
        tang = readable_angle_deg(math.degrees(math.atan2(ey, ex)))
        order = (0.5, 0.35, 0.65, 0.25, 0.75, 0.15, 0.85)
        if frac is not None:
            order = (frac,) + tuple(f for f in order if abs(f - frac) > 1e-9)
        for frac_choice in order:
            lx = ax + ex * el * frac_choice + nx * (post_size + 3.5)
            ly = ay + ey * el * frac_choice + ny * (post_size + 3.5)
            if any(self._inside_box(lx, ly, box, 6.0) for box in exclusions):
                continue
            text_insert = _resolve_text_insert(doc, "FENCING", 1.0, tang, (lx, ly, 0))
            msp.add_text(
                "FENCING",
                dxfattribs={
                    "layer": layer,
                    "color": 1,
                    "style": _ensure_text_style(doc),
                    "height": 1.0,
                    "rotation": tang,
                    "insert": (text_insert[0], text_insert[1], 0),
                },
            )
            break
        else:
            lx = ax + ex * el / 2.0 + nx * (post_size + 3.5)
            ly = ay + ey * el / 2.0 + ny * (post_size + 3.5)
            text_insert = _resolve_text_insert(doc, "FENCING", 1.0, tang, (lx, ly, 0))
            msp.add_text(
                "FENCING",
                dxfattribs={
                    "layer": layer,
                    "color": 1,
                    "style": _ensure_text_style(doc),
                    "height": 1.0,
                    "rotation": tang,
                    "insert": (text_insert[0], text_insert[1], 0),
                },
            )

    def _generate_fencing(self) -> None:
        """Draw fencing for all recorded SIDE platforms."""
        if not self._fencing_jobs:
            return
        doc = self._load_document()
        exclusions = self._station_footprints(doc)
        setups = []
        for _layer, far_edge, outline, ext in self._fencing_jobs:
            setup = self._fencing_setup(far_edge, outline)
            if setup is not None:
                setups.append((_layer, far_edge, outline, ext, setup))
        common = None
        for frac in (0.5, 0.35, 0.65, 0.25, 0.75, 0.15, 0.85):
            ok = True
            for (_layer, _fe, _ol, _ext, (ax, ay, ex, ey, nx, ny, el)) in setups:
                lx = ax + ex * el * frac + nx * (0.6 + 3.5)
                ly = ay + ey * el * frac + ny * (0.6 + 3.5)
                if any(self._inside_box(lx, ly, box, 6.0) for box in exclusions):
                    ok = False
                    break
            if ok:
                common = frac
                break
        for _layer, far_edge, outline, ext, _setup in setups:
            self._draw_fencing(doc, far_edge, outline, exclusions, ext, common)
        self._save_document(doc)
