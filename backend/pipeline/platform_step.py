"""Compatibility shim for PlatformMixin."""

from pipeline.steps.platform import (
    PlatformMixin,
    PlatformStep,
    _footprints_strict_overlap,
    _orient2d,
    _point_strictly_inside,
    _ring_edges,
    _segments_properly_cross,
)

__all__ = [
    "PlatformMixin",
    "PlatformStep",
    "_orient2d",
    "_segments_properly_cross",
    "_point_strictly_inside",
    "_ring_edges",
    "_footprints_strict_overlap",
]
