"""Loads a track centerline out of an existing DXF file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import ezdxf
from ezdxf.document import Drawing

from common.geometry import Point, polyline_length


@dataclass
class Track:
    name: str
    points: List[Point]

    @property
    def length(self) -> float:
        return polyline_length(self.points)

    @classmethod
    def from_dxf(
        cls,
        doc: Drawing,
        layer_name: Optional[str] = None,
        handle: Optional[str] = None,
        name: Optional[str] = None,
    ) -> "Track":
        msp = doc.modelspace()

        entity = None
        if handle:
            entity = doc.entitydb.get(handle)
            if entity is None:
                raise ValueError(f"No entity with handle {handle!r} found in DXF")
        elif layer_name:
            candidates = [
                e
                for e in msp
                if e.dxf.layer == layer_name
                and e.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE", "SPLINE")
            ]
            if not candidates:
                raise ValueError(
                    f"No LINE/LWPOLYLINE/POLYLINE/SPLINE entity found on layer "
                    f"{layer_name!r}. Check the layer name (case-sensitive)."
                )
            entity = max(candidates, key=lambda e: _entity_length(e))
        else:
            raise ValueError("Provide either layer_name or handle to locate the track")

        points = _extract_points(entity)
        return cls(name=name or f"track@{entity.dxf.layer}", points=points)


def _extract_points(entity) -> List[Point]:
    etype = entity.dxftype()
    if etype == "LINE":
        return [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
    if etype == "LWPOLYLINE":
        return [(p[0], p[1]) for p in entity.get_points()]
    if etype == "POLYLINE":
        return [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
    if etype == "SPLINE":
        return [(p.x, p.y) for p in entity.flattening(distance=0.05)]
    raise ValueError(f"Unsupported centerline entity type: {etype}")


def _entity_length(entity) -> float:
    try:
        return polyline_length(_extract_points(entity))
    except Exception:
        return 0.0
