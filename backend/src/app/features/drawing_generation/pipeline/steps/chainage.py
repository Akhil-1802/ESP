"""Station-relative chainage labels (final annotation pass)."""

from __future__ import annotations

from .base import PipelineStep
from .chainage_alignment import AlignmentChainageLabels
from .chainage_collect import (
    collect_dead_ends,
    collect_fm,
    collect_optional_layers,
    collect_platform_ends,
    collect_robs,
    collect_siding,
    collect_srj_turnout_crossover,
    determine_side,
    station_centres_from_dxf,
)
from .chainage_labels import StationChainageLabels


class ChainageStep(StationChainageLabels, AlignmentChainageLabels, PipelineStep):
    """Pipeline step: station-relative chainage labels."""

    def _station_centres_from_dxf(self, doc) -> list:
        return station_centres_from_dxf(doc)

    def _determine_side(self, pt, host_track: str | None = None, configured_side: str | None = None) -> str:
        return determine_side(
            pt,
            main_line_points=getattr(self, "_main_line_points", None),
            config=self.config,
            host_track=host_track,
            configured_side=configured_side,
        )

    def _collect_platform_ends(self, doc, tracks, datum) -> list:
        return collect_platform_ends(
            doc, tracks, datum, self.config, getattr(self, "_main_line_points", None)
        )

    def _collect_srj_turnout_crossover(self, tracks, extents, datum) -> list:
        return collect_srj_turnout_crossover(
            tracks,
            extents,
            datum,
            getattr(self, "_crossover_results", None) or [],
            getattr(self, "_siding_results", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_siding(self, tracks, extents, datum, tracks_for_datum) -> list:
        return collect_siding(
            tracks,
            extents,
            datum,
            getattr(self, "_siding_results", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_fm(self, datum) -> list:
        return collect_fm(
            datum,
            getattr(self, "_fouling_marks", None) or [],
            self.config,
            getattr(self, "_main_line_points", None),
        )

    def _collect_dead_ends(self, doc, tracks_for_datum, datum) -> list:
        return collect_dead_ends(
            doc, tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None)
        )

    def _collect_robs(self, tracks_for_datum, datum) -> list:
        return collect_robs(tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None))

    def _collect_optional_layers(self, doc, tracks_for_datum, datum) -> list:
        return collect_optional_layers(doc, tracks_for_datum, datum, self.config, getattr(self, "_main_line_points", None))
