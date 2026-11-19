import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..artifacts import DXF_MEDIA_TYPE, _persist_output
from ..config import load_config_from_json
from ..formats.kml.conversion import convert_kml_direct
from ..pipeline import export
from .uploads import _read_json_upload, _save_kml_upload

router = APIRouter()


def _execute_config_dict(payload: dict, workdir: Path, download_name: str) -> FileResponse:
    """Run the standard config through loader + pipeline; return the DXF."""
    config_file = workdir / "inputconfig.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    try:
        esp_config = load_config_from_json(str(config_file))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"invalid config: {exc}") from exc
    except Exception as exc:
        raise HTTPException(500, f"config load failed: {exc}") from exc

    try:
        cache_hit, timings, snapshot = export._generate_or_cached(esp_config, payload)
    except UnicodeError as exc:
        raise HTTPException(500, f"server output encoding failed: {exc}") from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"generation rejected: {exc}") from exc
    except Exception as exc:
        raise HTTPException(500, f"generation failed: {exc}") from exc

    dxf_path = workdir / download_name
    if not dxf_path.is_file():
        raise HTTPException(500, "generator finished but produced no DXF.")

    saved_path = _persist_output(dxf_path, download_name)
    headers = {
        "X-ESP-Cache": "hit" if cache_hit else "miss",
        "Server-Timing": ", ".join(f"{name};dur={seconds * 1000:.2f}" for name, seconds in timings.items()),
    }
    if snapshot is not None:
        generation_id = uuid4().hex
        export._KEY_PLAN_SNAPSHOTS.put(generation_id, snapshot, len(snapshot))
        if export._KEY_PLAN_SNAPSHOTS.get(generation_id) is not None:
            headers["X-ESP-Generation-ID"] = generation_id
    return FileResponse(
        path=str(saved_path),
        media_type=DXF_MEDIA_TYPE,
        filename=saved_path.name,
        headers=headers,
    )


@router.post("/generate")
def generate(
    config: UploadFile = File(...),
    kml: UploadFile = File(...),
) -> FileResponse:
    """Generate the ESP DXF from an uploaded config JSON + KML file."""
    config_data = _read_json_upload(config, "config")

    with tempfile.TemporaryDirectory(prefix="esp_") as temp_dir:
        workdir = Path(temp_dir)
        local_source = _save_kml_upload(kml, workdir)

        download_name = Path(str(config_data.get("output_dxf") or "ESP_output.dxf").strip() or "ESP_output.dxf").name

        # Check for direct 1:1 KML replication mode
        if config_data.get("direct_kml") or config_data.get("kml_mode") == "direct":
            out_file = workdir / download_name 
            try:
                convert_kml_direct(str(local_source), str(out_file))
            except Exception as exc:
                raise HTTPException(422, f"KML direct conversion failed: {exc}") from exc
            saved_path = _persist_output(out_file, download_name)
            return FileResponse(
                path=str(saved_path),
                media_type=DXF_MEDIA_TYPE,
                filename=saved_path.name,
            )

        payload = dict(config_data)
        payload["source_path"] = str(local_source)
        payload["output_dxf"] = str(workdir / download_name)
        return _execute_config_dict(payload, workdir, download_name)


@router.post("/convert-kml-direct")
def convert_kml_direct_endpoint(
    kml: UploadFile = File(...),
) -> FileResponse:
    """Direct 1:1 conversion of KML file to DXF (all lines, North-up / geographic orientation)."""
    workdir = Path(tempfile.mkdtemp(prefix="esp_direct_"))
    try:
        local_source = _save_kml_upload(kml, workdir)
        download_name = f"{local_source.stem}_direct.dxf"
        out_file = workdir / download_name
        convert_kml_direct(str(local_source), str(out_file))
        saved_path = _persist_output(out_file, download_name)
        return FileResponse(
            path=str(saved_path),
            media_type=DXF_MEDIA_TYPE,
            filename=saved_path.name,
        )
    except Exception as exc:
        raise HTTPException(422, f"KML direct conversion failed: {exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
