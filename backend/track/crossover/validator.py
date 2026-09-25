"""Crossover constraint validation engine (L1 to L6 orchestration)."""

from __future__ import annotations

from typing import Sequence

from common.geometry import Point
from track.crossover.geometry import (
    _resolve_extents,
    _track_length,
    srj_positions_on_tracks,
)
from track.crossover.models import (
    AdjacentSpacingCheck,
    CrossoverRequest,
    CrossoverValidationReport,
    FootprintCheck,
)
from track.crossover.rules import (
    validate_boundary_rule,
    validate_chainages_rule,
    validate_footprints_rule,
    validate_geometry_rule,
    validate_spacing_rule,
    validate_tracks_rule,
)


class CrossoverConstraintValidator:
    """Six-level validation for an arbitrary list of crossover requests."""

    def __init__(
        self,
        tracks: dict[str, Sequence[Point]] | None = None,
        extents: dict[str, tuple[float, float]] | None = None,
        main_length: float | None = None,
    ):
        self.tracks = tracks or {}
        self.extents = _resolve_extents(extents)
        if main_length is None and "MAIN_LINE" in self.tracks:
            try:
                main_length = _track_length(self.tracks["MAIN_LINE"])
            except Exception:
                main_length = None
        self.main_length = main_length

    def validate_tracks(
        self, requests: Sequence[CrossoverRequest]
    ) -> tuple[bool, list[str], list[str]]:
        """LEVEL 1: track validity."""
        return validate_tracks_rule(self.tracks, requests)

    def validate_chainages(
        self, requests: Sequence[CrossoverRequest]
    ) -> tuple[bool, list[str], list[str]]:
        """LEVEL 2: chainage validity."""
        return validate_chainages_rule(requests, self.main_length, self.extents)

    def validate_spacing(
        self,
        resolved: Sequence[tuple[CrossoverRequest, float]],
        positions_by_id: dict[str, dict[str, float]] | None = None,
    ) -> tuple[bool, list[AdjacentSpacingCheck], list[str], list[str]]:
        """LEVEL 3: minimum spacing."""
        return validate_spacing_rule(resolved, positions_by_id)

    def validate_footprints(
        self,
        footprints: dict[str, tuple[float, float]],
        order: Sequence[str],
        requests: Sequence[CrossoverRequest] | None = None,
        params_by_id: dict[str, dict] | None = None,
    ) -> tuple[bool, list[FootprintCheck], list[str], list[str]]:
        """LEVEL 4: physical footprint overlap."""
        return validate_footprints_rule(
            footprints, order, self.tracks, requests, params_by_id
        )

    def validate_geometry(
        self,
        request: CrossoverRequest,
        params: dict,
        points: Sequence[Point],
        geom_report: dict,
    ) -> tuple[bool, list[str], list[str]]:
        """LEVEL 5: geometry validity."""
        return validate_geometry_rule(request, params, points, geom_report)

    def validate_boundary(
        self, request: CrossoverRequest, params: dict
    ) -> tuple[bool, list[str], list[str]]:
        """LEVEL 6: design boundary."""
        return validate_boundary_rule(
            request, params, self.main_length, self.extents
        )

    def validate_all(
        self,
        requests: Sequence[CrossoverRequest],
        resolved_chainages: dict[str, float] | None = None,
        params_by_id: dict[str, dict] | None = None,
        geometry_by_id: dict[str, tuple[list, dict]] | None = None,
    ) -> CrossoverValidationReport:
        report = CrossoverValidationReport(overall_valid=True)
        errors: list[str] = []
        warnings: list[str] = []
        levels: dict = {}

        l1_ok, l1_err, l1_warn = self.validate_tracks(requests)
        levels["L1_tracks"] = {"valid": l1_ok, "errors": l1_err}
        errors.extend(l1_err)
        warnings.extend(l1_warn)

        l2_ok, l2_err, l2_warn = self.validate_chainages(requests)
        levels["L2_chainage"] = {"valid": l2_ok, "errors": l2_err}
        errors.extend(l2_err)
        warnings.extend(l2_warn)

        resolved = resolved_chainages or {
            r.id: float(r.chainage) for r in requests if r.chainage is not None
        }
        pairs = [(r, resolved[r.id]) for r in requests if r.id in resolved]
        positions_by_id: dict[str, dict[str, float]] = {}
        if params_by_id:
            for req in requests:
                par = params_by_id.get(req.id)
                if par is None or req.id not in resolved:
                    continue
                try:
                    positions_by_id[req.id] = srj_positions_on_tracks(
                        req, float(resolved[req.id]), par["to_main"]
                    )
                except (KeyError, TypeError, ValueError):
                    continue
        if len(pairs) >= 2:
            l3_ok, checks, l3_err, l3_warn = self.validate_spacing(
                pairs, positions_by_id or None
            )
        else:
            l3_ok, checks, l3_err, l3_warn = True, [], [], []
        levels["L3_spacing"] = {"valid": l3_ok, "errors": l3_err}
        errors.extend(l3_err)
        warnings.extend(l3_warn)

        fp_checks: list[FootprintCheck] = []
        if params_by_id:
            footprints = {
                cid: (p["start_chainage"], p["end_chainage"])
                for cid, p in params_by_id.items()
            }
            order = [r.id for r, _ch in sorted(pairs, key=lambda t: t[1])]
            order = [cid for cid in order if cid in footprints]
            if len(order) >= 2:
                l4_ok, fp_checks, l4_err, l4_warn = self.validate_footprints(
                    footprints, order, requests, params_by_id
                )
            else:
                l4_ok, l4_err, l4_warn = True, [], []
            levels["L4_footprint"] = {"valid": l4_ok, "errors": l4_err}
            errors.extend(l4_err)
            warnings.extend(l4_warn)
        else:
            levels["L4_footprint"] = {"valid": True, "errors": []}

        per_geom: dict[str, bool] = {}
        if params_by_id is not None and geometry_by_id is not None:
            l5_ok_all, l6_ok_all = True, True
            l5_err_all: list[str] = []
            l6_err_all: list[str] = []
            for req in requests:
                if req.id not in params_by_id or req.id not in geometry_by_id:
                    continue
                params = dict(params_by_id[req.id])
                params["_chainage"] = resolved.get(req.id, req.chainage)
                pts, grep = geometry_by_id[req.id]
                g_ok, g_err, g_warn = self.validate_geometry(
                    req, params, pts, grep
                )
                per_geom[req.id] = bool(g_ok)
                if not g_ok:
                    l5_ok_all = False
                l5_err_all.extend(g_err)
                warnings.extend(g_warn)
                b_ok, b_err, b_warn = self.validate_boundary(req, params)
                if not b_ok:
                    l6_ok_all = False
                l6_err_all.extend(b_err)
                warnings.extend(b_warn)
            levels["L5_geometry"] = {
                "valid": l5_ok_all,
                "errors": l5_err_all,
                "per_crossover": per_geom,
            }
            levels["L6_boundary"] = {"valid": l6_ok_all, "errors": l6_err_all}
            errors.extend(l5_err_all)
            errors.extend(l6_err_all)
        else:
            levels["L5_geometry"] = {
                "valid": True,
                "errors": [],
                "per_crossover": {},
            }
            levels["L6_boundary"] = {"valid": True, "errors": []}

        report.level_results = levels
        report.spacing_checks = checks
        report.footprint_checks = fp_checks
        report.errors = errors
        report.warnings = warnings
        report.overall_valid = len(errors) == 0
        return report


__all__ = ["CrossoverConstraintValidator"]
