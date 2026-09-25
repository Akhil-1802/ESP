"""ESP - Clean Railway Drawing Generator.

Root entry point. Run from this directory:

    python main.py --config examples/inputconfig.json
    python main.py            # interactive mode
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend directory is in sys.path when running without pip install -e .
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from cli.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
