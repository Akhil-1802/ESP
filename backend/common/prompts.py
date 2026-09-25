"""Shared interactive prompting primitives (single implementation).

Low-level input() helpers used by the ESP CLI. Domain-specific
question flows stay in cli/; only the reusable prompt mechanics
live here.
"""

from __future__ import annotations


class UserAbort(Exception):
    """Raised when the user aborts interactive input (nothing is written)."""


def ask(prompt: str, default=None) -> str:
    """Prompt for input with optional default."""
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or str(default) if default is not None else value


def ask_positive(prompt: str, default: float) -> float:
    """Prompt for a positive number."""
    while True:
        try:
            value = float(ask(prompt, default))
            if value > 0:
                return value
        except ValueError:
            pass
        print("Please enter a number greater than zero.")


def ask_nonnegative(prompt: str, default: float = 0.0) -> float:
    """Prompt for a non-negative number."""
    while True:
        try:
            value = float(ask(prompt, default))
            if value >= 0:
                return value
        except ValueError:
            pass
        print("Please enter zero or a positive number.")


def ask_track_spacing(prompt: str, default: float = 5.3) -> float:
    """Prompt for track spacing (m). Minimum 5.3 m per ESP."""
    while True:
        value = ask_positive(prompt, default)
        if value >= 5.3:
            return value
        print("Track spacing must be at least 5.3 m.")


def ask_choice(prompt: str, choices: list[str], default=None) -> str:
    """Prompt to choose from a list (case-insensitive)."""
    while True:
        value = ask(f"{prompt} ({', '.join(choices)})", default)
        for choice in choices:
            if value.casefold() == choice.casefold():
                return choice
        print(f"Please choose one of: {', '.join(choices)}")


def ask_count(prompt: str, default: int = 0) -> int:
    """Prompt for a non-negative integer."""
    while True:
        try:
            value = int(ask(prompt, default))
            if value >= 0:
                return value
        except ValueError:
            pass
        print("Please enter a whole number zero or greater.")


__all__ = [
    "UserAbort",
    "ask",
    "ask_choice",
    "ask_count",
    "ask_nonnegative",
    "ask_positive",
    "ask_track_spacing",
]
