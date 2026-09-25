"""Reference for inputconfig.json - READ ONLY, not loaded by the program.

Copy the values you need into inputconfig.json (plain JSON, no comments
allowed there). Run with:  python main.py --config examples/inputconfig.json

Chainage rule: every chainage is a MAIN_LINE chainage in metres.
Bounded loops convert with:  local = MAIN - C1  (must lie in [C1, C2]).

==========================================================================
  TRACK NAMES (use in any track_layer / from_track / to_track field)
==========================================================================

  Track Name          | Description                     | Defined by
  --------------------|---------------------------------|------------------
  MAIN_LINE           | Primary centreline from KML/DXF | source KML/DXF
  LOOP_1              | First bounded loop line          | loops[0].name
  LOOP_2              | Second bounded loop line         | loops[1].name
  LOOP_3, LOOP_4 ...  | Additional loops                 | loops[2], loops[3]
  PROPOSED_LINE_1     | Full-length parallel line        | additional_lines
  PROPOSED_LOOP_1     | Additional bounded loop          | loops / additional

  Names come from the "name" field in "loops" and "additional_lines".
  You can name them anything unique.

==========================================================================
  CONFIGURATION SCENARIOS
==========================================================================

  A: Single MAIN line only (no loops)
     -> "loops": [], "crossovers": [] or omit

  B: MAIN + 1 loop, 2 manual crossovers
     -> "loops": [one entry], "crossovers": [2 entries]

  C: MAIN + 2 loops (standard station) -- MOST COMMON
     -> "loops": [LOOP_1 LEFT, LOOP_2 RIGHT]
     -> "crossover_preset": "DEFAULT" (auto 4 crossovers)

  D: MAIN + additional full-length lines
     -> "additional_lines": [entries], "main_directions": {...}

==========================================================================
  FIELD VALUES ACTUALLY ACCEPTED BY THE CODE
==========================================================================

"""

# --------------------------------------------------------------------------
# Top level
# --------------------------------------------------------------------------
REFERENCE = {
    # KML or DXF holding the MAIN centreline. Relative paths resolve from
    # the folder containing inputconfig.json. KML is auto-converted first.
    "source_path": "ESP.kml",

    # Output drawing (1:1 real-world scale, metres). Overwritten each run -
    # close it in AutoCAD before rerunning.
    "output_dxf": "ESP__22.dxf",

    # Layer of the MAIN centreline. For KML input always "MAIN_TRACK".
    # For DXF input, pick the layer listed by the interactive prompt.
    "track_source_layer": "MAIN_TRACK",

    # ------------------------------------------------------------------
    # loops: Parallel loop lines bounded between two chainages.
    # ------------------------------------------------------------------
    "loops": [
        {
            "name": "LOOP_1",          # unique layer + label name

            "spacing": 5.3,            # centre-to-centre from MAIN (m)
                                        # Values: >= 5.3

            "side": "LEFT",            # which side of MAIN (forward view)
                                        # Values: "LEFT" / "RIGHT"

            "first_crossover_chainage": 175.709,   # C1 (MAIN metres)
            "second_crossover_chainage": 925.709,  # C2 (MAIN metres)
                                                    # If omitted: C1 + crossover_distance_m

            "turnout_designation": "1:12",  # Values: "1:12" / "1:8.5"
            "turnout_variant": "standard",  # Values for 1:12:
                                              #   "standard" (= 60kg)
                                              #   "60kg"
                                              #   "modified_psc"
                                              #   "60kg_modified_psc"
                                              #   "52kg"
                                              #   "52kg_modified_psc"
                                              # Values for 1:8.5:
                                              #   "standard"
                                              #   "modified_psc"

            "crossover_distance_m": 750.0,  # only used when C2 omitted

            # Overrun past the turnouts (0 = none).
            # Effective loop extent = [C1 - start, C2 + end]
            # Extended tips get dead end + "OVER RUN LINE, CAL=..."
            "extend_start_m": 0.0,   # overrun before C1 (>= 0)
            "extend_end_m": 120.0,   # overrun past C2  (>= 0)
        },
    ],

    # ------------------------------------------------------------------
    # additional_lines: Full-length parallel lines (NOT bounded loops).
    # ------------------------------------------------------------------
    "additional_lines": [
        # {
        #     "name": "PROPOSED_LINE_1",   # unique name
        #     "spacing": 5.3,              # centre-to-centre from MAIN (m)
        #     "side": "LEFT",              # Values: "LEFT" / "RIGHT"
        #     "direction": "UP",           # optional
        #                                  # Values: "UP" / "DN" / ""
        #                                  # "UP" = increasing chainage
        #                                  # "DN" = decreasing chainage
        # },
    ],

    # ------------------------------------------------------------------
    # platforms: Station platforms alongside tracks.
    # ------------------------------------------------------------------
    "platforms": [
        {
            "track_layer": "LOOP_1",   # any defined track name
            "platform_type": "SIDE",   # Values: "SIDE" / "ISLAND"
                                        # ISLAND needs "second_track_layer"
            "side": "LEFT",            # Values: "LEFT" / "RIGHT"
            "center_on_track": True,   # centre on track midpoint
            "clearance": 1.68,         # track centre -> near edge (m)
            "platform_width": 8.5,     # near edge -> far edge (m)
            "platform_length": 550.0,  # platform length (m)
            "platform_height": 0.84,   # high level (text only, 2D plan)
            "platform_name": "PLATFORM 1",
            # optional:
            # "stair_length": 10.0,    # > 0 enables stairs, 0/omit = none
            # "stair_width": 3.0,      # > 0, 0/omit = defaults to platform_width
        },
    ],

    # ------------------------------------------------------------------
    # crossovers: Connections between tracks.
    #
    # OPTION 1 (easiest): Use preset for standard 4-crossover layout.
    #   Requires: LOOP_1 + LOOP_2 on opposite sides of MAIN_LINE.
    #   The preset builds:
    #     C1 LOOP_1 C1 -> MAIN_LINE REVERSE
    #     C2 LOOP_1 C2 -> MAIN_LINE FORWARD
    #     C3 MAIN_LINE -> LOOP_2 FORWARD at E1 + 54
    #     C4 MAIN_LINE -> LOOP_2 REVERSE at E2 - 54
    #
    # OPTION 2: Define each crossover manually in the list below.
    # ------------------------------------------------------------------

    # --- OPTION 1: Preset ---
    "crossover_preset": "DEFAULT",       # Values: "DEFAULT" / omit
    "crossover_preset_turnout": "1:12",  # Values: "1:12" / "1:8.5"

    # --- OPTION 2: Manual list (remove preset lines above to use) ---
    # "crossovers": [
    #     {
    #         "id": "C1",                # optional, auto C1..CN
    #
    #         "from_track": "MAIN_LINE", # any defined track name
    #         "to_track": "LOOP_1",      # must differ from from_track
    #
    #         "from_chainage_m": 300.0,  # FIRST SRJ (MAIN m) or "AUTO"
    #
    #         "direction": "FORWARD",    # Values:
    #                                    #   "FORWARD" ->, START + OL
    #                                    #   "REVERSE" <-, START - OL
    #                                    # Aliases accepted:
    #                                    #   "FWD"/"F"/"AHEAD" -> FORWARD
    #                                    #   "REV"/"R"/"BEHIND" -> REVERSE
    #                                    #
    #                                    # Spacing rules (on shared track):
    #                                    #   Same direction: >= 13 m
    #                                    #   Opposite direction: >= 54 m
    #
    #         "position_mode": "FIXED",  # Values:
    #                                    #   "FIXED" = exact chainage
    #                                    #   "AUTO"  = engine finds spot
    #                                    # Aliases: "MANUAL" -> FIXED
    #                                    #          "AUTOMATIC" -> AUTO
    #
    #         "turnout": {
    #             "designation": "1:12", # Values: "1:12" / "1:8.5"
    #             "variant": "standard", # Values for 1:12:
    #                                    #   "standard" / "60kg" /
    #                                    #   "modified_psc" / "60kg_modified_psc" /
    #                                    #   "52kg" / "52kg_modified_psc"
    #                                    # Values for 1:8.5:
    #                                    #   "standard" / "modified_psc"
    #         },
    #         # NOTE: no "placement" key (AHEAD/BEHIND) - it is fully
    #         # determined by "direction" (FORWARD -> second SRJ ahead
    #         # at START + OL, REVERSE -> behind at START - OL), so the
    #         # loader never reads it. Do not write it.
    #         # "to_chainage_m": null,     # legacy: computed value wins
    #     },
    # ],

    # ------------------------------------------------------------------
    # stations: Station buildings alongside platforms.
    # ------------------------------------------------------------------
    "stations": [
        {
            "platform_layer": "PLATFORM_1",  # matches platform order
            "building_length": 40.0,
            "building_width": 10.0,
            "platform_side": "LEFT",  # Values: "LEFT" / "RIGHT"
            "building_name": "STATION BUILDING",
        },
    ],

    # ------------------------------------------------------------------
    # fobs: Foot Over Bridge decks (basic deck only, no stairs).
    # Only 4 inputs per FOB: reference track, reference chainage
    # (MAIN m), platforms to connect, deck width (default 3.0 m). The
    # deck span is derived from the selected platform boundaries; the
    # deck is placed with the track's local tangent/perpendicular at
    # the reference chainage (never global X-Y). Needs platforms in
    # place. Design limits (validated): 6.25 m vertical clearance
    # above rail and a 30 m maximum span. A centred "F.O.B." label is
    # drawn in the widest track gap.
    # ------------------------------------------------------------------
    "fobs": [
        # {
        #     "reference_track": "MAIN_LINE",  # any defined track name:
        #                                      # MAIN_LINE / LOOP_1 / ...
        #     "reference_chainage": 550.0,     # MAIN m, must lie within
        #                                      # the platforms' extent
        #     "platforms": ["PLATFORM_1", "PLATFORM_2"],  # >= 2 platform
        #                                                # output layers
        #     "width": 3.0,                    # deck width in m (> 0,
        #                                      # default 3.0)
        #     # optional design vertical clearance above rail (m,
        #     # default 6.25, must stay >= 6.25):
        #     # "vertical_clearance_m": 6.25,
        #     # NOTE: spans over 30 m are rejected -- split the FOB
        #     # or add intermediate support outside this basic deck.
        #     # optional deck extension past the platform edges (m,
        #     # 0 = none): extend_start_m lengthens the minimum-
        #     # projection span end, extend_end_m the maximum end.
        #     # CLI asks length + START / END / BOTH like loop overruns.
        #     # "extend_start_m": 0.0,
        #     # "extend_end_m": 0.0,
        #     # optional landing arms parallel to the track, one per
        #     # platform: arm runs deck-width wide from the deck edge
        #     # over its platform. Side LEFT = toward lower chainage,
        #     # RIGHT = toward higher chainage.
        #     # "arms": {"PLATFORM_1": {"length": 20.0, "side": "LEFT"}},
        #     # optional: "output_layer": "FOB_1",  # default FOB_1, FOB_2..
        #     # optional: "color": 1,               # ACI, default 1 (red)
        # },
    ],

    # ------------------------------------------------------------------
    # sidings: Dead-end sidings (one turnout, no second connection).
    # Only 6 inputs per siding: source track, start chainage (MAIN m),
    # direction, side, turnout, clear standing length. The ladder
    # (turnout curve + closure + reverse curve) runs the siding out to
    # a parallel offset, holds the standing length, then ends in a
    # DEAD END whose tip is calculated (never asked). SRJ markers are
    # drawn at the switch on the source track and where the turnout
    # curve ends into the siding, like crossover ends.
    # Direction FORWARD = increasing chainage / REVERSE; side LEFT /
    # RIGHT of increasing chainage (loop convention). Spacing defaults
    # to the
    # 5.3 m minimum. Conflicts with tracks, crossover SRJs (13 m same
    # / 54 m opposite direction), platforms, station buildings or other
    # sidings raise an error: nothing is ever moved or shortened.
    # ------------------------------------------------------------------
    "sidings": [
        # {
        #     "id": "S1",                    # optional, auto S1..SN
        #     "source_track": "MAIN_LINE",   # any defined track name
        #     "start_chainage_m": 1050.0,    # turnout switch (MAIN m)
        #     "direction": "FORWARD",        # FORWARD (->) / REVERSE (<-)
        #     "side": "LEFT",                # LEFT / RIGHT of +chainage
        #     "turnout_designation": "1:12", # Values: "1:12" / "1:8.5"
        #     "turnout_variant": "standard", # see loops turnout_variant
        #     "standing_length_m": 200.0,    # clear parallel run (> 0)
        #     "spacing": 5.3,                # parallel offset (>= 5.3)
        # },
    ],

    # ------------------------------------------------------------------
    # main_directions: Map track names to travel direction.
    # Single MAIN line -> bidirectional UP/DN, automatic.
    # ------------------------------------------------------------------
    "main_directions": {
        # "MAIN_LINE": "UP",    # Values: "UP" / "DN"
        # "MAIN_LINE_2": "DN",
    },
}

# --------------------------------------------------------------------------
#  COMPLETE CONFIGURATION EXAMPLES
# --------------------------------------------------------------------------
#
#  Example 1: Single MAIN line (no loops)
#  {
#    "source_path": "track.kml",
#    "output_dxf": "output.dxf",
#    "track_source_layer": "MAIN_TRACK",
#    "loops": [],
#    "additional_lines": [],
#    "platforms": [],
#    "crossovers": [],
#    "stations": [],
#    "main_directions": {}
#  }
#
#  Example 2: MAIN + 1 loop, 2 manual crossovers
#  {
#    "source_path": "track.kml",
#    "output_dxf": "output.dxf",
#    "track_source_layer": "MAIN_TRACK",
#    "loops": [
#      {
#        "name": "LOOP_1",
#        "spacing": 5.3,
#        "side": "LEFT",
#        "first_crossover_chainage": 200.0,
#        "second_crossover_chainage": 950.0,
#        "turnout_designation": "1:12",
#        "turnout_variant": "standard",
#        "crossover_distance_m": 750.0,
#        "extend_start_m": 0.0,
#        "extend_end_m": 120.0
#      }
#    ],
#    "additional_lines": [],
#    "platforms": [],
#    "crossovers": [
#      {
#        "id": "C1",
#        "from_track": "LOOP_1",
#        "to_track": "MAIN_LINE",
#        "from_chainage_m": 200.0,
#        "direction": "REVERSE",
#        "position_mode": "FIXED",
#        "turnout": {"designation": "1:12", "variant": "standard"}
#      },
#      {
#        "id": "C2",
#        "from_track": "LOOP_1",
#        "to_track": "MAIN_LINE",
#        "from_chainage_m": 950.0,
#        "direction": "FORWARD",
#        "position_mode": "FIXED",
#        "turnout": {"designation": "1:12", "variant": "standard"}
#      }
#    ],
#    "stations": [],
#    "main_directions": {}
#  }
#
#  Example 3: MAIN + 2 loops with DEFAULT preset (standard station)
#  {
#    "source_path": "track.kml",
#    "output_dxf": "output.dxf",
#    "track_source_layer": "MAIN_TRACK",
#    "loops": [
#      {
#        "name": "LOOP_1",
#        "spacing": 5.3,
#        "side": "LEFT",
#        "first_crossover_chainage": 175.709,
#        "second_crossover_chainage": 925.709,
#        "turnout_designation": "1:12",
#        "turnout_variant": "standard",
#        "crossover_distance_m": 750.0,
#        "extend_start_m": 0.0,
#        "extend_end_m": 120.0
#      },
#      {
#        "name": "LOOP_2",
#        "spacing": 5.3,
#        "side": "RIGHT",
#        "first_crossover_chainage": 175.709,
#        "second_crossover_chainage": 925.709,
#        "turnout_designation": "1:12",
#        "turnout_variant": "standard",
#        "crossover_distance_m": 750.0,
#        "extend_start_m": 0.0,
#        "extend_end_m": 120.0
#      }
#    ],
#    "additional_lines": [],
#    "platforms": [
#      {
#        "track_layer": "LOOP_1",
#        "platform_type": "SIDE",
#        "side": "LEFT",
#        "center_on_track": true,
#        "clearance": 1.68,
#        "platform_width": 8.5,
#        "platform_length": 550.0,
#        "platform_height": 0.84,
#        "platform_name": "PLATFORM 1"
#      },
#      {
#        "track_layer": "MAIN_LINE",
#        "platform_type": "SIDE",
#        "side": "RIGHT",
#        "center_on_track": true,
#        "clearance": 1.68,
#        "platform_width": 8.5,
#        "platform_length": 550.0,
#        "platform_height": 0.84,
#        "platform_name": "PLATFORM 2"
#      }
#    ],
#    "crossover_preset": "DEFAULT",
#    "crossover_preset_turnout": "1:12",
#    "stations": [],
#    "main_directions": {}
#  }
#
#  Example 4: MAIN + additional proposed line
#  {
#    "source_path": "track.kml",
#    "output_dxf": "output.dxf",
#    "track_source_layer": "MAIN_TRACK",
#    "loops": [],
#    "additional_lines": [
#      {
#        "name": "PROPOSED_LINE_1",
#        "spacing": 5.3,
#        "side": "RIGHT",
#        "direction": "UP"
#      }
#    ],
#    "platforms": [],
#    "crossovers": [],
#    "stations": [],
#    "main_directions": {"MAIN_LINE": "UP", "PROPOSED_LINE_1": "UP"}
#  }
#
# --------------------------------------------------------------------------
#  CROSSOVER SPACING RULES
# --------------------------------------------------------------------------
#
#  | Condition                    | Min Spacing | Measured Between       |
#  |------------------------------|-------------|------------------------|
#  | Same direction (FWD+FWD /   | 13 m        | Nearest SRJs on shared |
#  |   REV+REV)                   |             | track (START or 2nd)   |
#  | Opposite direction (FWD+REV) | 54 m        | Nearest SRJs on shared |
#                              |             | track                  |
#
#  OL = TC * N + 2 * A  (TC <= 8000 mm)
#  where TC = track centre spacing (mm), N = turnout ratio, A = turnout lead
#
#  | Turnout | Spacing | OL (m) |
#  |---------|---------|--------|
#  | 1:12    | 5.3 m   | 97.6   |
#  | 1:12    | 6.3 m   | 109.6  |
#  | 1:12    | 6.7 m   | 114.4  |
#  | 1:8.5   | 5.3 m   | 69.1   |
#  | 1:8.5   | 6.7 m   | 81.0   |
