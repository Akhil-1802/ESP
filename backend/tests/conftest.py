"""Pytest configuration and common path fixtures."""

import sys
from pathlib import Path

# Ensure backend and esp_refactored root are on sys.path
TESTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TESTS_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)
