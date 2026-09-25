"""ESP command-line interface.

Modules:
    main             - argparse entry point + interactive orchestration
    tracks           - MAIN/LOOP/PROPOSED + loop-extension prompts
    crossover_checks - live SRJ-spacing / footprint validation helpers
    crossovers       - DEFAULT/MANUAL crossover wizard
    platforms        - platform wizard
    stations         - station wizard
    fobs             - FOB wizard
    sidings          - siding wizard
"""

from cli.crossovers import _ask_crossover_start, _ask_crossovers_live
from cli.fobs import _ask_fobs
from cli.main import _get_dxf_layers, _main_center, main
from cli.sidings import _ask_sidings

__all__ = [
    "_ask_crossover_start",
    "_ask_crossovers_live",
    "_ask_fobs",
    "_ask_sidings",
    "_get_dxf_layers",
    "_main_center",
    "main",
]
