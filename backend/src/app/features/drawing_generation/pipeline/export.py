import hashlib
import json
import logging
import time
from pathlib import Path

from ..cache import BoundedCache, file_digest
from .generator import ESPGenerator

logger = logging.getLogger(__name__)

_DXF_CACHE = BoundedCache(max_bytes=8 * 1024 * 1024, max_entries=8, ttl=300)
_GENERATION_CACHE_VERSION = "key-plan-overruns-directions-v2"
_KEY_PLAN_SNAPSHOTS = BoundedCache(max_bytes=4 * 1024 * 1024, max_entries=32, ttl=600)


def _generate_or_cached(esp_config, payload: dict):
    """Reuse exact successful exports; paths/names are request-local, not geometry."""
    start = time.perf_counter()
    drawing_config = {k: v for k, v in payload.items() if k not in ("source_path", "output_dxf")}
    key = hashlib.sha256(json.dumps(
        [_GENERATION_CACHE_VERSION, file_digest(esp_config.source_path), drawing_config],
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    output = Path(esp_config.output_dxf)
    with _DXF_CACHE.single_flight(key):
        cached = _DXF_CACHE.get(key)
        if cached is not None:
            artifact, snapshot = cached
            output.write_bytes(artifact)
            timings = {"cache": time.perf_counter() - start}
            logger.info(f"   [cache] DXF export: hit ({timings['cache']:.3f}s)")
            return True, timings, snapshot
        generator = ESPGenerator(esp_config)
        generator.run()
        snapshot = json.dumps(generator.key_plan_snapshot, allow_nan=False).encode() if generator.key_plan_snapshot else None
        # Preserve the API's existing missing-output error; never cache failures.
        if output.is_file() and output.stat().st_size <= _DXF_CACHE.max_bytes:
            artifact = output.read_bytes()
            _DXF_CACHE.put(key, (artifact, snapshot), len(artifact) + len(snapshot or b""))
        logger.info("   [cache] DXF export: miss")
        return False, generator.timings, snapshot
