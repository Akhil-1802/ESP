"""Station wizard."""

from __future__ import annotations

from cli.base import (
    ask,
    ask_choice,
    ask_count,
    ask_positive,
)
from config.loader import PlatformRequest, StationRequest


def _ask_stations(platforms: list[PlatformRequest]) -> list[StationRequest]:
    """Step 3: ask about each station building (before crossovers, so
    crossover footprints can be checked against them)."""
    print("\nStation Configuration")
    print("=" * 50)

    stations: list[StationRequest] = []
    available_layers = [item.config.output_layer for item in platforms]
    for number in range(1, ask_count("Number of stations") + 1):
        print(f"\nStation {number}")
        platform_layer = ask_choice("  Platform layer", available_layers)
        length = ask_positive("  Building length (m)", 40)
        width = ask_positive("  Building width (m)", 10)
        side = ask_choice("  Building side of platform", ["LEFT", "RIGHT"], "RIGHT")
        name = ask("  Building name", "STATION BUILDING")
        ch_str = ask("  Station chainage (KM) (e.g. 68.48, or blank)", "").strip()
        stations.append(StationRequest(
            platform_layer,
            length,
            width,
            side,
            name,
            station_chainage=ch_str if ch_str else None,
        ))
    return stations
