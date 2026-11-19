"""Storage and retention for completed drawing downloads."""
import asyncio
import contextlib
import os
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI

BACKEND_OUTPUT_DIR = Path(os.environ.get("ESP_OUTPUT_DIR", "output")).resolve()
DXF_MEDIA_TYPE = "image/vnd.dxf"
OUTPUT_FILE_TTL_SECONDS = 600.0
CLEANUP_INTERVAL_SECONDS = 60.0

def cleanup_expired_outputs(
    output_dir: Path | None = None,
    ttl_seconds: float = OUTPUT_FILE_TTL_SECONDS,
) -> int:
    """Delete files in output_dir that are older than ttl_seconds, preserving .gitkeep."""
    output_dir = BACKEND_OUTPUT_DIR if output_dir is None else output_dir
    if not output_dir.is_dir():
        return 0
    now = time.time()
    deleted = 0
    for item in output_dir.iterdir():
        if item.is_file() and item.name != ".gitkeep":
            try:
                mtime = item.stat().st_mtime
                if (now - mtime) >= ttl_seconds:
                    item.unlink(missing_ok=True)
                    deleted += 1
            except OSError:
                pass
    return deleted


async def _janitor_sweeper():
    """Background periodic loop to clean up expired output DXF files."""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            cleanup_expired_outputs()
        except asyncio.CancelledError:
            break
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run once at startup to sweep any files left from previous downtime
    cleanup_expired_outputs()
    task = asyncio.create_task(_janitor_sweeper())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def _persist_output(dxf_path: Path, download_name: str) -> Path:
    """Copy the finished DXF into output directory (never overwritten) and prune expired files."""
    cleanup_expired_outputs()
    BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(download_name).stem, Path(download_name).suffix or ".dxf"
    candidate = BACKEND_OUTPUT_DIR / f"{stem}{suffix}"
    while True:
        try:
            target = candidate.open("xb")
        except FileExistsError:
            candidate = BACKEND_OUTPUT_DIR / f"{stem}_{uuid4().hex}{suffix}"
            continue
        try:
            with target, dxf_path.open("rb") as source:
                shutil.copyfileobj(source, target)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise
        return candidate
