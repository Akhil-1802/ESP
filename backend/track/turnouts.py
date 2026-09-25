"""Configurable ESP turnout parameters.

All numeric values stored in this module are taken from the published
Indian Railways Standard Drawings referenced below. They MUST be
verified against the applicable IRSOD before this geometry is relied on
for any construction or operational decision.

Sources cited:
    - IRSOD T-1-8.5  (1:8.5 BG standard turnout)
    - IRSOD T-1-12   (1:12 BG standard turnout, 60 kg and 52 kg rail)
    - ESP Rule Engine Documentation (IRSOD 2022) - minimum spacing,
      minimum lead radius, ordinary crossing, diamond crossing rules.

DO NOT derive F or beta from atan(1/ratio). The ratio classifies the
turnout; F and beta come from the standard drawing.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

NORMAL_SPACING_LIMIT_MM = 8000.0
NEW_TRACK_MIN_SPACING_MM = 5300.0

# Indian Railways Turn-in Curve limits (IRPWM 2020 Para 426, formerly Para 410):
BG_TURN_IN_CURVE_MIN_RADIUS_M = 350.0       # Normal minimum turn-in curve radius (5 deg curve)
BG_TURN_IN_CURVE_REDUCED_RADIUS_M = 220.0   # Relaxed minimum turn-in curve radius (PSC sleepers)

# Retain for backward compatibility with existing imports:
BG_MIN_LEAD_RADIUS_M = 350.0
BG_REDUCED_LEAD_RADIUS_M = 220.0

# RDSO Broad Gauge (1676 mm) Turnout Lead-Rail Radii:
BG_1_12_LEAD_RADIUS_M = 441.36             # RDSO standard drawing nominal lead curve radius (m)
BG_1_12_LEAD_RADIUS_MM = 441_360.0         # in mm
BG_1_12_MIN_LEAD_RADIUS_M = 410.0          # Minimum permissible lead rail radius per IR design criteria (m)
BG_1_12_MIN_LEAD_RADIUS_MM = 410_000.0     # in mm

# 1 in 8.5 Turnout (RDSO Drg. No. T-4865 for 60kg/52kg, 6,400 mm curved switch):
BG_1_8_5_LEAD_RADIUS_M = 232.26            # RDSO standard drawing nominal lead curve radius (m)
BG_1_8_5_LEAD_RADIUS_MM = 232_260.0        # in mm
BG_1_8_5_MIN_LEAD_RADIUS_M = 218.0         # Standard BG minimum curvature without check rails (8 deg curve)
BG_1_8_5_MIN_LEAD_RADIUS_MM = 218_000.0    # in mm

ORDINARY_CROSSING_RATIO = 16.0
DIAMOND_CROSSING_RATIO = 8.5
BG_GAUGE_MM = 1676.0


@dataclass(frozen=True)
class TurnoutParameters:
    """Standard ESP turnout specification."""

    designation: str            # e.g. "1:8.5"
    rail: str                   # e.g. "60kg" or "52kg"
    variant: str                # e.g. "standard" or "modified_psc"
    a_mm: float
    b_mm: float
    m_mm: float
    k_mm: float
    crossing_angle_rad: Optional[float] = None  # F
    switch_angle_rad: Optional[float] = None   # beta
    radius_mm: Optional[float] = None          # R
    ratio: str = ""                             # nominal classification
    gauge_mm: float = BG_GAUGE_MM
    heel_divergence_mm: Optional[float] = None
    crossing_straight_leg_mm: Optional[float] = None
    source_citation: str = ""


def default_crossing_angle_rad() -> float:
    """Documented ordinary-crossing minimum angle, 1 in 16."""
    return math.atan(1.0 / ORDINARY_CROSSING_RATIO)


# RDSO T-4865: 1:8.5 BG standard turnout (6,400 mm curved switch on PSC sleepers).
_T_1_8_5_STANDARD = TurnoutParameters(
    designation="1:8.5",
    rail="standard",
    variant="standard",
    a_mm=12025.0,  # FROM SRJ TO PI(Point of Intersection)
    b_mm=16486.0,  # PI to HOC (back/end of crossing assembly)
    m_mm=14270.0,  # TNC (Theoretical Nose of Crossing) to PI
    k_mm=2216.0,   # TNC to HOC
    crossing_angle_rad=math.radians(6.7098),
    radius_mm=BG_1_8_5_LEAD_RADIUS_MM,  # 232.26 m, RDSO T-4865 nominal lead curve radius
    switch_angle_rad=math.radians(1.5239),
    ratio="1:8.5",
    source_citation="RDSO T-4865 BG 1:8.5 standard turnout on PSC sleepers (R=232.26m)",
)

# RDSO T-4865: 1:8.5 modified PSC variant.
_T_1_8_5_MODIFIED_PSC = TurnoutParameters(
    designation="1:8.5",
    rail="standard",
    variant="modified_psc",
    a_mm=12025.0,
    b_mm=19786.0,
    m_mm=14270.0,
    k_mm=5516.0,
    crossing_angle_rad=math.radians(6.7098),
    radius_mm=BG_1_8_5_LEAD_RADIUS_MM,  # 232.26 m, RDSO T-4865 nominal lead curve radius
    switch_angle_rad=math.radians(1.5239),
    ratio="1:8.5",
    source_citation="RDSO T-4865 BG 1:8.5 modified PSC turnout (R=232.26m)",
)

# IRSOD / IRPWM: 1:8.5 minimum permissible curvature (8-deg curve without check rails).
_T_1_8_5_218M = TurnoutParameters(
    designation="1:8.5",
    rail="standard",
    variant="218m",
    a_mm=12025.0,
    b_mm=16486.0,
    m_mm=14270.0,
    k_mm=2216.0,
    crossing_angle_rad=math.radians(6.7098),
    radius_mm=BG_1_8_5_MIN_LEAD_RADIUS_MM,  # 218.0 m, standard BG 8-deg curve minimum
    switch_angle_rad=math.radians(1.5239),
    ratio="1:8.5",
    source_citation="IRSOD / IRPWM BG 1:8.5 turnout minimum permissible radius (R=218m)",
)

# RDSO T-4218: 1:12 BG 60kg standard turnout (10,125 mm curved switch on PSC sleepers).
_T_1_12_60KG_STANDARD = TurnoutParameters(
    designation="1:12",
    rail="60kg",
    variant="standard",
    a_mm=16989.0,
    b_mm=22912.0,
    m_mm=20111.0,
    k_mm=2801.0,
    crossing_angle_rad=math.radians(4.7636),
    radius_mm=BG_1_12_LEAD_RADIUS_MM,  # 441.36 m, RDSO T-4218 nominal lead curve radius
    switch_angle_rad=math.radians(1.0857),
    ratio="1:12",
    source_citation="RDSO T-4218 BG 1:12 60kg standard turnout on PSC sleepers (R=441.36m)",
)

# RDSO T-4218: 1:12 BG 60kg modified PSC variant.
_T_1_12_60KG_MODIFIED_PSC = TurnoutParameters(
    designation="1:12",
    rail="60kg",
    variant="modified_psc",
    a_mm=16989.0,
    b_mm=28414.0,
    m_mm=20111.0,
    k_mm=8303.0,
    crossing_angle_rad=math.radians(4.7636),
    radius_mm=BG_1_12_LEAD_RADIUS_MM,  # 441.36 m, RDSO T-4218 nominal lead curve radius
    switch_angle_rad=math.radians(1.0857),
    ratio="1:12",
    source_citation="RDSO T-4218 BG 1:12 60kg modified PSC (R=441.36m)",
)

# RDSO T-4732: 1:12 BG 52kg standard turnout (10,125 mm curved switch on PSC sleepers).
_T_1_12_52KG_STANDARD = TurnoutParameters(
    designation="1:12",
    rail="52kg",
    variant="standard",
    a_mm=16989.0,
    b_mm=22914.0,
    m_mm=20111.0,
    k_mm=2803.0,
    crossing_angle_rad=math.radians(4.7636),
    radius_mm=BG_1_12_LEAD_RADIUS_MM,  # 441.36 m, RDSO T-4732 nominal lead curve radius
    switch_angle_rad=math.radians(1.0857),
    ratio="1:12",
    source_citation="RDSO T-4732 BG 1:12 52kg standard turnout on PSC sleepers (R=441.36m)",
)

# RDSO T-4732: 1:12 BG 52kg modified PSC variant.
_T_1_12_52KG_MODIFIED_PSC = TurnoutParameters(
    designation="1:12",
    rail="52kg",
    variant="modified_psc",
    a_mm=16989.0,
    b_mm=28412.0,
    m_mm=20111.0,
    k_mm=8301.0,
    crossing_angle_rad=math.radians(4.7636),
    radius_mm=BG_1_12_LEAD_RADIUS_MM,  # 441.36 m, RDSO T-4732 nominal lead curve radius
    switch_angle_rad=math.radians(1.0857),
    ratio="1:12",
    source_citation="RDSO T-4732 BG 1:12 52kg modified PSC (R=441.36m)",
)

# Indian Railways 1:12 minimum permissible lead rail radius (410 m).
_T_1_12_410M = TurnoutParameters(
    designation="1:12",
    rail="60kg",
    variant="410m",
    a_mm=16989.0,
    b_mm=22912.0,
    m_mm=20111.0,
    k_mm=2801.0,
    crossing_angle_rad=math.radians(4.7636),
    radius_mm=BG_1_12_MIN_LEAD_RADIUS_MM,  # 410.0 m, IR minimum permissible lead radius
    switch_angle_rad=math.radians(1.0857),
    ratio="1:12",
    source_citation="Indian Railways BG 1:12 turnout minimum permissible lead radius (R=410m)",
)

TURNOUT_LIBRARY = {
    "1:8.5": {
        "standard": _T_1_8_5_STANDARD,
        "modified_psc": _T_1_8_5_MODIFIED_PSC,
        "218m": _T_1_8_5_218M,
        "minimum": _T_1_8_5_218M,
    },
    "1:12": {
        "standard": _T_1_12_60KG_STANDARD,        # legacy key
        "60kg": _T_1_12_60KG_STANDARD,
        "modified_psc": _T_1_12_60KG_MODIFIED_PSC,
        "60kg_modified_psc": _T_1_12_60KG_MODIFIED_PSC,
        "52kg": _T_1_12_52KG_STANDARD,
        "52kg_modified_psc": _T_1_12_52KG_MODIFIED_PSC,
        "410m": _T_1_12_410M,
        "minimum": _T_1_12_410M,
    },
}


def get_turnout_parameters(designation: str, variant: str) -> TurnoutParameters:
    try:
        return TURNOUT_LIBRARY[designation][variant]
    except KeyError as exc:
        available = ", ".join(
            f"{name}/{option}" for name, variants in TURNOUT_LIBRARY.items() for option in variants
        )
        raise ValueError(
            f"Unsupported turnout {designation}/{variant}. Available: {available}"
        ) from exc


def require_geometry_parameters(turnout: TurnoutParameters) -> None:
    """Raise if a turnout does not have the verified F / beta / R values."""
    missing = []
    if turnout.crossing_angle_rad is None:
        missing.append("crossing_angle_rad (F)")
    if turnout.radius_mm is None:
        missing.append("radius_mm (R)")
    if turnout.switch_angle_rad is None:
        missing.append("switch_angle_rad (beta)")
    if missing:
        raise ValueError(
            f"Turnout {turnout.designation}/{turnout.variant} is missing "
            f"{', '.join(missing)} from the applicable ESP drawing; "
            f"no engineering value was assumed. Source: {turnout.source_citation}"
        )


def select_turnout(
    selection: str,
    variant: str = "standard",
) -> TurnoutParameters:
    """Resolve AUTO / explicit turnout selection."""
    s = selection.strip().upper()
    if s in {"AUTO", "1:12", "PASSENGER", "DEFAULT"}:
        designation = "1:12"
    elif s in {"1:8.5", "8.5", "FREIGHT"}:
        designation = "1:8.5"
    elif s == "1:16":
        designation = "1:12"
    else:
        raise ValueError(
            f"Unknown turnout selection {selection!r}. Use AUTO, 1:8.5, or 1:12."
        )
    if designation == "1:12" and variant == "standard":
        variant = "60kg"
    return get_turnout_parameters(designation, variant)
