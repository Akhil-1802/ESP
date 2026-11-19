import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..domain.constants import LOOP_HALF_LENGTH_M
from ..formats.kml.center import main_track_center
from ..formats.kml.track_detector import detect_kml_tracks
from .uploads import _save_kml_upload

router = APIRouter()


@router.post("/detect-tracks")
def detect_tracks_endpoint(
    kml: UploadFile = File(...),
    min_length: float = 30.0,
    max_candidates: int = 4,
) -> dict:
    """Detect and topologically group candidate railway tracks from KML."""
    workdir = Path(tempfile.mkdtemp(prefix="esp_detect_"))
    try:
        local_source = _save_kml_upload(kml, workdir)
        tracks = detect_kml_tracks(
            str(local_source),
            min_track_length_m=min_length,
            include_coords=True,
            max_candidates=max_candidates,
        )
        return {"candidate_tracks": tracks}
    except Exception as exc:
        raise HTTPException(422, f"Track detection failed: {exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.post("/main-center")
def main_center(
    kml: UploadFile = File(...),
    selected_track_id: str | None = Form(None),
) -> dict:
    """MAIN midpoint + default 750 m loop extent from an uploaded KML."""
    workdir = Path(tempfile.mkdtemp(prefix="esp_center_"))
    try:
        local_source = _save_kml_upload(kml, workdir)
        try:
            center = main_track_center(local_source, selected_track_id=selected_track_id)
        except ValueError as exc:
            raise HTTPException(422, f"cannot determine MAIN centre: {exc}") from exc
        half = float(LOOP_HALF_LENGTH_M)
        return {
            "main_center_m": round(float(center), 3),
            "main_length_m": round(float(center) * 2.0, 3),
            "default_c1_m": round(float(center) - half, 3),
            "default_c2_m": round(float(center) + half, 3),
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
