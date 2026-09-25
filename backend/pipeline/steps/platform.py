"""Platform generation: polygons, overlap checks, writing."""

from __future__ import annotations

import ezdxf

from common.geometry import nearest_point_on_alignment, polygon_contains, polygons_overlap
from platform_gen.config import PlatformType as _PlatformType
from platform_gen.dxf_io import write_platform as _write_platform
from platform_gen.platform import PlatformGenerator
from platform_gen.track import _extract_points
from station.builder import _polygon_area
from track.drawing import _add_track_label

from .base import PipelineStep

__all__ = [
    "PlatformStep",
    "PlatformMixin",
    "_orient2d",
    "_segments_properly_cross",
    "_point_strictly_inside",
    "_ring_edges",
    "_footprints_strict_overlap",
]


def _orient2d(a, b, c) -> float:
    """Cross product (b - a) x (c - a); sign = turn direction."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_properly_cross(a, b, c, d, eps: float = 1e-9) -> bool:
    """True only for a genuine crossing (touching/collinear never counts)."""
    o1, o2 = _orient2d(a, b, c), _orient2d(a, b, d)
    o3, o4 = _orient2d(c, d, a), _orient2d(c, d, b)
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    )


def _point_strictly_inside(outline, pt, eps: float = 1e-6) -> bool:
    """True when pt lies inside outline with clearance from its boundary."""
    try:
        if nearest_point_on_alignment(outline, pt).distance <= eps:
            return False
    except Exception:
        pass
    try:
        return bool(polygon_contains(outline, pt))
    except Exception:
        return False


def _ring_edges(ring):
    """De-duplicated closed edges of a (possibly closed) polygon ring."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return []
    return list(zip(pts, pts[1:] + pts[:1]))


def _footprints_strict_overlap(first, second) -> bool:
    """True when two polygons genuinely overlap (touching is allowed)."""
    edges_first = _ring_edges(first)
    edges_second = _ring_edges(second)
    if not edges_first or not edges_second:
        return False
    pts_first = [a for a, _b in edges_first]
    pts_second = [a for a, _b in edges_second]
    if any(_point_strictly_inside(first, p) for p in pts_second):
        return True
    if any(_point_strictly_inside(second, p) for p in pts_first):
        return True
    return any(
        _segments_properly_cross(a, b, c, d)
        for a, b in edges_first
        for c, d in edges_second
    )


class PlatformStep(PipelineStep):
    """Pipeline step: Platform generation: polygons, overlap checks, writing."""

    def _platform_polygons(self, doc, layer: str):
        """Extract platform polygons from a DXF layer."""
        polygons = []
        for entity in doc.modelspace():
            if entity.dxf.layer != layer or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            points = _extract_points(entity)
            if len(points) >= 3:
                polygons.append(points)
        return sorted(polygons, key=_polygon_area, reverse=True)

    def _check_platform_overlap(self, doc, outline, platform_layer: str) -> None:
        """Verify that a new platform doesn't overlap existing platforms."""
        for entity in doc.modelspace():
            if entity.dxf.layer == platform_layer or not entity.dxf.layer.startswith("PLATFORM_"):
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            if polygons_overlap(outline, _extract_points(entity)):
                raise ValueError(f"Platform {platform_layer!r} overlaps an existing platform")

    def _check_platform_covers_track(self, outline, platform_layer: str, tracks) -> None:
        """Reject a platform drawn across any track centreline."""
        for name, pts in (tracks or {}).items():
            line = [(float(p[0]), float(p[1])) for p in pts]
            if len(line) < 2 or len(outline) < 3:
                continue
            edges = _ring_edges(outline)
            hit = any(_point_strictly_inside(outline, p) for p in line)
            if not hit:
                segments = list(zip(line, line[1:]))
                hit = any(
                    _segments_properly_cross(a, b, c, d)
                    for a, b in segments
                    for c, d in edges
                )
            if hit:
                raise ValueError(
                    f"Platform {platform_layer!r} covers track {name!r} - "
                    f"move it (side/clearance/width) so no track "
                    f"centreline passes through the platform."
                )

    def _check_platform_stair_overlap(self, outline, stair_outlines, platform_layer: str) -> None:
        """Reject stair footprints colliding with other platforms."""
        for layer, prev_outline, prev_stairs in (
            getattr(self, "_platform_footprints", None) or []
        ):
            if polygons_overlap(outline, prev_outline):
                raise ValueError(
                    f"Platform {platform_layer!r} overlaps {layer!r} - "
                    f"move it so the outlines do not intersect."
                )
            for rect in list(prev_stairs or []):
                if _footprints_strict_overlap(outline, rect):
                    raise ValueError(
                        f"Platform {platform_layer!r} overlaps the stairs "
                        f"of {layer!r} - move it so it clears them."
                    )
            for mine in list(stair_outlines or []):
                if _footprints_strict_overlap(mine, prev_outline):
                    raise ValueError(
                        f"Platform {platform_layer!r} stairs overlap "
                        f"{layer!r} - move it so they clear it."
                    )
                for rect in list(prev_stairs or []):
                    if _footprints_strict_overlap(mine, rect):
                        raise ValueError(
                            f"Platform {platform_layer!r} stairs overlap "
                            f"the stairs of {layer!r}."
                        )

    def _generate_platforms(self, tracks=None) -> None:
        """Generate all platforms (outlines, stairs and tracks validated)."""
        self._platform_footprints = []
        for request in self.config.platforms:
            platform_cfg = request.config
            platform_cfg.source_dxf = self.config.output_dxf
            platform_cfg.output_dxf = self.config.output_dxf

            result, doc = PlatformGenerator(platform_cfg).build()
            _write_platform(doc, result, platform_cfg)
            outline = [(p[0], p[1]) for p in result.outline]
            stair_outlines = [
                [(p[0], p[1]) for p in stair.outline]
                for stair in (getattr(result, "stairs", None) or [])
            ]
            self._check_platform_overlap(doc, outline, platform_cfg.output_layer)
            self._check_platform_stair_overlap(
                outline, stair_outlines, platform_cfg.output_layer
            )
            self._check_platform_covers_track(
                outline, platform_cfg.output_layer, tracks
            )
            self._platform_footprints.append(
                (platform_cfg.output_layer, outline, stair_outlines)
            )
            if (
                platform_cfg.platform_type == _PlatformType.SIDE
                and getattr(result, "far_edge", None)
            ):
                self._fencing_jobs.append(
                    (platform_cfg.output_layer, result.far_edge, outline, 0.0)
                )
            doc.saveas(self.config.output_dxf)
            self.platform_layers.append(platform_cfg.output_layer)

        try:
            doc = ezdxf.readfile(self.config.output_dxf)
            for entity in list(doc.modelspace()):
                try:
                    if entity.dxf.layer == "TRACK_LABELS":
                        doc.modelspace().delete_entity(entity)
                except Exception:
                    pass
            for name, points in tracks.items():
                display = name.replace("_", " ").title()
                if name.upper() == "MAIN_LINE":
                    display = "MAIN LINE"
                _add_track_label(doc, display, points, "TRACK_LABELS", color=1, height=1.0)
            doc.saveas(self.config.output_dxf)
        except Exception:
            pass


class PlatformMixin(PlatformStep):
    """Mixin for backward compatibility."""
    pass
