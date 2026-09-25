"""Centralised engineering and drawing constants.

Single source of truth for magic numbers that were previously scattered
across ``track/*``, ``platform_gen/*``, ``generator.py`` and ``cli.py``.
Import from here; do not hard-code these values elsewhere.

Engineering values (turnout library dimensions in ``track.turnouts`` are
*not* duplicated here) stay in sync with the ESP Rules documentation.
"""

from __future__ import annotations

# --- units -----------------------------------------------------------------
MM_PER_UNIT: float = 1000.0  # DXF drawings are metre-based; geometry in mm
M_PER_MM: float = 0.001

# --- loops -----------------------------------------------------------------
#: Fixed distance between loop crossover points C1 -> C2 (metres).
LOOP_CROSSOVER_DISTANCE_M: float = 750.0
LOOP_HALF_LENGTH_M: float = 375.0
#: Default overrun extension past loop turnouts (metres, 0 = none).
DEFAULT_OVERRUN_M: float = 120.0

# --- track spacing ----------------------------------------------------------
#: Minimum centre-to-centre spacing for any new parallel track (m).
MIN_TRACK_SPACING_M: float = 5.3
#: Normal-spacing limit: TC <= 8000 mm uses OL = TC*N + 2*A (mm).
NORMAL_SPACING_LIMIT_MM: float = 8000.0

# --- crossover spacing rules -------------------------------------------------
#: Minimum separation for two adjacent crossovers, same direction (m).
SAME_DIRECTION_MIN_SEPARATION_M: float = 13.0
#: Minimum separation for two adjacent crossovers, opposite directions (m).
OPPOSITE_DIRECTION_MIN_SEPARATION_M: float = 54.0

# --- chainage tolerances ------------------------------------------------------
#: 1 mm -- covers 3-decimal display rounding (e.g. 175.7094 -> 175.709).
CHAINAGE_TOL_M: float = 1e-3
#: Tight epsilon for pure geometric predicates.
GEOMETRY_EPS: float = 1e-9
#: AUTO placement search step (metres).
AUTO_SEARCH_STEP_M: float = 1.0

# --- crossover geometry ---------------------------------------------------------
PARALLEL_TOLERANCE_DEG: float = 5.0
#: Backward-compatible alias (old name used ``DEGREES`` suffix).
PARALLEL_TOLERANCE_DEGREES: float = PARALLEL_TOLERANCE_DEG
F_DIAG_TOLERANCE_DEG: float = 1.0
MAX_VERTEX_GAP_M: float = 5.0

# --- SRJ-anchored loop overruns ------------------------------------------------
#: A bounded loop's running line ends at the outermost crossover SRJ
#: found strictly inside either loop end (rather than at the defined
#: C1/C2 turnout point); the cut-off outer piece is drawn as an
#: OVER RUN LINE with a dead end + CAL label. Only SRJs within this
#: distance (metres) inside [C1, C2] trigger the cut -- SRJs exactly
#: at C1/C2 or mid-loop crossovers keep the previous behaviour.
#: Default covers a half-loop (375 m of a 750 m loop: centre -> tip),
#: so any crossover placed before the 375 m tip ends the running line
#: there and the remainder to the tip becomes overrun. Callers use
#: half the actual [C1, C2] length when the loop is not 750 m.
LOOP_SRJ_OVERRUN_SEARCH_M: float = 375.0
#: Shorter cut-off stubs than this (metres) keep the loop end instead;
#: avoids degenerate slivers when an SRJ sits ~at the turnout point.
LOOP_SRJ_OVERRUN_MIN_STUB_M: float = 1.0

# --- Main line visible margin past outermost SRJs -----------------------------
#: Visible length of main lines extending outward past the outermost SRJs (metres).
MAIN_LINE_SRJ_MARGIN_M: float = 50.0

# --- platform defaults ------------------------------------------------------------
DEFAULT_CLEARANCE_M: float = 1.68
DEFAULT_PLATFORM_WIDTH_M: float = 8.5
DEFAULT_PLATFORM_LENGTH_M: float = 550.0
DEFAULT_PLATFORM_HEIGHT_M: float = 0.84
#: Default platform arm (stair/ramp) length (metres).
DEFAULT_PLATFORM_ARM_LENGTH_M: float = 16.999

# --- FOB (foot over bridge) ------------------------------------------------------
#: Default deck width (m). The only FOB size input; span/position are derived.
DEFAULT_FOB_WIDTH_M: float = 3.0
#: Design vertical clearance above rail level (m, IRSOD minimum for FOBs).
#: The DXF is a 2D plan so this is a documented design value enforced by
#: validation, not something measured from plan geometry.
FOB_VERTICAL_CLEARANCE_M: float = 6.25
#: Maximum single-span deck length (m) without intermediate support.
#: ``build_fob_outline`` raises when the derived span exceeds this.
FOB_MAX_SPAN_M: float = 30.0
#: Dynamic FOB placement offset from actual station edge (m).
DEFAULT_FOB_OFFSET_M: float = 40.0
MIN_FOB_OFFSET_M: float = 40.0
MAX_FOB_OFFSET_M: float = 60.0
DEFAULT_FOB_DIRECTION: str = "INCREASING"

# --- DXF drawing ----------------------------------------------------------------------
DEFAULT_COLOR: int = 1  # AutoCAD Color Index: red
#: Single shared text style for EVERY annotation (track labels, SRJ tags,
#: T.C / arrow dimensions, overrun labels, platform + station texts):
#: Arial TrueType for all lettering -- letters and numbers alike.
TEXT_STYLE_NAME: str = "ESP_TEXT"
TEXT_STYLE_FONT: str = "Arial.ttf"
#: Thin style for dimension/scaling NUMBER values (overall lengths,
#: T.C / arrow-dimension values): matches the light reference digits.
NUMBER_STYLE_NAME: str = "ESP_NUM"
NUMBER_STYLE_FONT: str = "Arial.ttf"
#: Bold style for emphasised labels (e.g. turnout tags): TrueType bold,
#: since the SHX reference fonts have no bold weight of their own.
BOLD_STYLE_NAME: str = "ESP_TEXT_BOLD"
BOLD_STYLE_FONT: str = "arialbd.ttf"
#: Minimum clearance kept between any two placed texts, in metres,
#: applied in every direction around each text's bounding box.
TEXT_CLEARANCE_M: float = 1.0
DISK_SAMPLES: int = 16
SRJ_STEM_M: float = 2.0
SRJ_DISK_RADIUS_M: float = 1.0
DIRECTION_SHAFT_HALF_M: float = 8.0
ARROW_LENGTH_M: float = 2.0
ARROW_HALF_WIDTH_M: float = 0.7
TEXT_HEIGHT_M: float = 1.0
DIM_TEXT_HEIGHT_M: float = 0.8
