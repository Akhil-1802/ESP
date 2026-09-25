"""Wizard module compatibility facade."""

from backend.wizard import wizard_main_center, wizard_needs_center, wizard_to_config_dict

__all__ = [
    "wizard_to_config_dict",
    "wizard_main_center",
    "wizard_needs_center",
]
