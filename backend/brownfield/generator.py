"""Brownfield generator orchestrating track building and DXF export."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

import ezdxf

from .crossover import (
    BrownfieldCrossoverBuilder,
    BrownfieldCrossoverResult,
    BrownfieldCrossoverSpec,
)
from .main_lines import BrownfieldMainLineBuilder
from .models import BrownfieldLayout, BrownfieldMainLineSpec, Point
from common.dxf import add_polyline as _add_polyline
from track.drawing import _add_all_tc_annotations, _draw_direction_mark, _draw_srj_post


class BrownfieldGenerator:
    """Orchestrator for Brownfield track generation with explicit reference tracks and crossovers.

    In Brownfield design:
    - Tracks do NOT end 50m after the last SRJ. Tracks preserve their full surveyed
      and generated alignments.
    - Crossovers only affect their designated from_track and to_track, leaving other
      main lines completely untouched.
    """

    def __init__(
        self,
        base_tracks: Optional[dict[str, Sequence[Point]]] = None,
        main_line_specs: Optional[List[BrownfieldMainLineSpec]] = None,
        crossover_specs: Optional[List[BrownfieldCrossoverSpec]] = None,
        output_dxf: Optional[str] = None,
    ):
        self.builder = BrownfieldMainLineBuilder()
        self.crossover_builder = BrownfieldCrossoverBuilder()
        if base_tracks:
            for name, pts in base_tracks.items():
                self.builder.add_base_track(name, pts)
        if main_line_specs:
            for spec in main_line_specs:
                self.builder.add_main_line(spec)
        if crossover_specs:
            for spec in crossover_specs:
                self.crossover_builder.add_crossover(spec)
        self.output_dxf = output_dxf

    def add_base_track(self, name: str, points: Sequence[Point], direction: str = "") -> BrownfieldGenerator:
        self.builder.add_base_track(name, points, direction=direction)
        return self

    def add_main_line(self, spec: BrownfieldMainLineSpec) -> BrownfieldGenerator:
        self.builder.add_main_line(spec)
        return self

    def add_crossover(self, spec: BrownfieldCrossoverSpec) -> BrownfieldGenerator:
        """Add a crossover between two tracks."""
        self.crossover_builder.add_crossover(spec)
        return self

    def build_layout(self) -> BrownfieldLayout:
        """Build and return the validated BrownfieldLayout with crossovers.

        Neither track is truncated to 50m after the SRJ; all tracks maintain full geometry.
        """
        layout = self.builder.build()
        self.crossover_builder.build(layout)
        return layout

    def run(self, output_dxf: Optional[str] = None) -> BrownfieldLayout:
        """Build all MAIN_LINES and crossovers, and render to DXF file."""
        target_path = output_dxf or self.output_dxf
        layout = self.build_layout()

        if target_path:
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()

            # Render each main line track to its layer without 50m SRJ end-truncation
            for name, track in layout.tracks.items():
                layer_name = name.upper().replace(" ", "_")
                if layer_name not in doc.layers:
                    doc.layers.add(layer_name, color=1)
                _add_polyline(doc, track.points, layer_name, 1)

                if track.direction.upper() in ("UP", "DN"):
                    sign = 1 if track.direction.upper() == "UP" else -1
                    _draw_direction_mark(doc, track.points, track.direction.upper(), False, sign)

            # Render crossovers
            if layout.crossovers:
                if "CROSSOVERS" not in doc.layers:
                    doc.layers.add("CROSSOVERS", color=2)
                for co in layout.crossovers:
                    if co.points:
                        _add_polyline(doc, co.points, "CROSSOVERS", 2)
                    if co.from_srj_point:
                        _draw_srj_post(doc, co.from_srj_point, (1.0, 0.0), True)
                    if co.to_srj_point:
                        _draw_srj_post(doc, co.to_srj_point, (1.0, 0.0), False)

            tracks_dict = layout.to_dict()
            try:
                _add_all_tc_annotations(doc, tracks_dict, layer="TRACK_CENTERS", color=1, height=0.8)
            except Exception:
                pass

            out = Path(target_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            doc.saveas(str(out))

        return layout
