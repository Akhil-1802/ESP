"""Crossover request/result models (single definition)."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Sequence

from common.constants import (
    AUTO_SEARCH_STEP_M,
    CHAINAGE_TOL_M,
    OPPOSITE_DIRECTION_MIN_SEPARATION_M,
    SAME_DIRECTION_MIN_SEPARATION_M,
)
from common.geometry import Point
from track.crossover.normalize import (
    is_auto_chainage,
    normalize_direction,
    normalize_placement,
    normalize_position_mode,
)


@dataclass
class CrossoverRequest:
    """Generic input for ONE crossover (works for 1..N crossovers)."""

    id: str
    from_track: str
    to_track: str
    chainage: float | None
    direction: str = "FORWARD"
    turnout: object | None = None
    placement: str | None = None
    position_mode: str = "FIXED"
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.direction = normalize_direction(self.direction)
        try:
            self.placement = normalize_placement(self.placement, self.direction)
        except ValueError:
            raise
        if is_auto_chainage(self.chainage):
            self.chainage = None
            self.position_mode = "AUTO"
        else:
            if self.chainage is not None:
                self.chainage = float(self.chainage)
            self.position_mode = normalize_position_mode(
                self.position_mode, self.chainage
            )
            if self.position_mode == "AUTO":
                self.chainage = None

    @property
    def is_auto(self) -> bool:
        return self.position_mode == "AUTO" or self.chainage is None

    def debug_dict(self) -> dict:
        return {
            "id": self.id,
            "from_track": self.from_track,
            "to_track": self.to_track,
            "chainage": self.chainage,
            "direction": self.direction,
            "placement": self.placement,
            "position_mode": self.position_mode,
            "turnout": getattr(self.turnout, "designation", None),
        }


@dataclass
class CrossoverResult:
    """Engineering output for ONE generated crossover."""

    id: str
    from_track: str
    to_track: str
    chainage: float
    direction: str
    placement: str
    turnout_type: str | None
    track_centre_mm: float | None
    track_centre_m: float | None
    n_ratio: float | None
    f_rad: float | None
    f_deg: float | None
    a_mm: float | None
    b_mm: float | None
    r_mm: float | None
    ol_mm: float | None
    ol_m: float | None
    crossover_type: str | None
    start_chainage: float | None
    end_chainage: float | None
    geometry: list = field(default_factory=list)
    geometry_report: dict = field(default_factory=dict)
    validation_status: str = "UNKNOWN"
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def debug_dict(self) -> dict:
        return {
            "id": self.id,
            "from_track": self.from_track,
            "to_track": self.to_track,
            "chainage": self.chainage,
            "direction": self.direction,
            "placement": self.placement,
            "turnout": self.turnout_type,
            "TC_m": self.track_centre_m,
            "N": self.n_ratio,
            "F_deg": self.f_deg,
            "A_mm": self.a_mm,
            "OL_mm": self.ol_mm,
            "OL_m": self.ol_m,
            "type": self.crossover_type,
            "start": self.start_chainage,
            "end": self.end_chainage,
            "status": self.validation_status,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass
class AdjacentSpacingCheck:
    a_id: str
    b_id: str
    required_m: float
    actual_m: float
    deficit_m: float
    valid: bool
    suggested_min_chainage_b: float
    same_direction: bool


@dataclass
class FootprintCheck:
    a_id: str
    b_id: str
    a_start: float
    a_end: float
    b_start: float
    b_end: float
    overlaps: bool
    valid: bool


@dataclass
class CrossoverValidationReport:
    overall_valid: bool
    level_results: dict = field(default_factory=dict)
    spacing_checks: list = field(default_factory=list)
    footprint_checks: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def format(self) -> str:
        lines = [
            "==========================================",
            "         CROSSOVER VALIDATION",
            "==========================================",
            "",
        ]
        if self.spacing_checks:
            for chk in self.spacing_checks:
                lines.append(f"{chk.a_id} -> {chk.b_id}")
                lines.append(f"Required minimum: {chk.required_m:.2f} m")
                lines.append(f"Actual separation: {chk.actual_m:.2f} m")
                if chk.valid:
                    lines.append("Status: VALID")
                else:
                    lines.append("Status: INVALID")
                    lines.append(f"Deficit: {chk.deficit_m:.2f} m")
                    lines.append(
                        "Suggested earliest chainage:\n"
                        f"    {chk.b_id} >= {chk.suggested_min_chainage_b:.2f} m"
                    )
                lines.append("")
        else:
            lines.append("(no shared-track pairs - no spacing rule applies)")
            lines.append("")
        lines.append("------------------------------------------")
        lines.append("")
        lines.append("Physical footprint:")
        fp_ok = self.level_results.get("L4_footprint", {}).get("valid", None)
        if self.footprint_checks:
            for chk in self.footprint_checks:
                mark = "OK" if chk.valid else "OVERLAP"
                lines.append(
                    f"    {chk.a_id} [{chk.a_start:.2f}, {chk.a_end:.2f}] "
                    f"x {chk.b_id} [{chk.b_start:.2f}, {chk.b_end:.2f}]: {mark}"
                )
        else:
            lines.append(f"    {'OK' if fp_ok else '(see errors)'}")
        lines.append("")
        lines.append("Geometry:")
        geom = self.level_results.get("L5_geometry", {})
        per = geom.get("per_crossover", {})
        if per:
            for cid, ok in per.items():
                lines.append(f"    {cid}: {'OK' if ok else 'FAIL'}")
        else:
            lines.append("    (see errors)")
        lines.append("")
        lines.append("Overall result:")
        if self.overall_valid:
            lines.append("    CROSSOVER LAYOUT VALID")
        else:
            lines.append("    CROSSOVER LAYOUT INVALID")
            lines.append("")
            lines.append("No geometry should be generated until")
            lines.append("the conflict is resolved.")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


@dataclass(frozen=True)
class RestrictedRegion:
    """One prohibited chainage interval on one track (MAIN datum, metres)."""

    track: str
    start_chainage: float
    end_chainage: float
    reason: str


@dataclass(frozen=True)
class RestrictedConflict:
    """One overlap between a crossover footprint and a restricted region."""

    track: str
    footprint_start: float
    footprint_end: float
    region: RestrictedRegion
    overlap_start: float
    overlap_end: float


__all__ = [
    "AdjacentSpacingCheck",
    "CrossoverRequest",
    "CrossoverResult",
    "CrossoverValidationReport",
    "FootprintCheck",
    "RestrictedConflict",
    "RestrictedRegion",
]
