# Configuration Reference (inputconfig.json)

Reference for `inputconfig.json` - configuration schema and options.
Run with: `python main.py --config examples/inputconfig.json`

Chainage rule: every chainage is a `MAIN_LINE` chainage in metres.
Bounded loops convert with: `local = MAIN - C1` (must lie in `[C1, C2]`).

## Track Names (use in any track_layer / from_track / to_track field)

| Track Name | Description | Defined by |
|---|---|---|
| MAIN_LINE | Primary centreline from KML/DXF | source KML/DXF |
| LOOP_1 | First bounded loop line | loops[0].name |
| LOOP_2 | Second bounded loop line | loops[1].name |
| LOOP_3, LOOP_4 ... | Additional loops | loops[2], loops[3] |
| PROPOSED_LINE_1 | Full-length parallel line | additional_lines |
| PROPOSED_LOOP_1 | Additional bounded loop | loops / additional |

Names come from the "name" field in "loops" and "additional_lines".
You can name them anything unique.

## Configuration Scenarios

- **A: Single MAIN line only (no loops)**
  `"loops": []`, `"crossovers": []` or omit
- **B: MAIN + 1 loop, 2 manual crossovers**
  `"loops": [one entry]`, `"crossovers": [2 entries]`
- **C: MAIN + 2 loops (standard station) -- MOST COMMON**
  `"loops": [LOOP_1 LEFT, LOOP_2 RIGHT]`
  `"crossover_preset": "DEFAULT"` (auto 4 crossovers)
- **D: MAIN + additional full-length lines**
  `"additional_lines": [entries]`, `"main_directions": {...}`

## Top-Level Fields

- `source_path`: Path to input KML or DXF.
- `output_dxf`: Output DXF filepath.
- `track_source_layer`: Layer for main track (default "MAIN_TRACK").
- `loops`: List of loop specifications.
- `additional_lines`: List of parallel line specifications.
- `platforms`: List of platform requests.
- `stations`: List of station building requests.
- `crossovers`: List of crossover specifications, or "DEFAULT".
- `fobs`: List of foot-over-bridge specifications.
- `sidings`: List of siding specifications.
