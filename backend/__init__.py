"""ESP Backend package."""
import sys
from pathlib import Path

# Ensure the backend directory is in sys.path so subpackages
# (common, track, config, etc.) resolve directly.
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))
