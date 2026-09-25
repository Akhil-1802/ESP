"""ESP generation API - upload the input files, download the DXF."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from common.constants import LOOP_HALF_LENGTH_M
from config.loader import load_config_from_json
from pipeline.orchestrator import ESPGenerator
from wizard import wizard_main_center, wizard_needs_center, wizard_to_config_dict

BACKEND_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
BACKEND_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DXF_MEDIA_TYPE = "image/vnd.dxf"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

app = FastAPI(
    title="ESP Generation API",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _persist_output(dxf_path: Path, download_name: str) -> Path:
    """Copy the finished DXF into output directory (never overwritten)."""
    stem, suffix = Path(download_name).stem, Path(download_name).suffix or ".dxf"
    candidate = BACKEND_OUTPUT_DIR / f"{stem}{suffix}"
    if candidate.exists():
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = BACKEND_OUTPUT_DIR / f"{stem}_{stamp}{suffix}"
    shutil.copyfile(dxf_path, candidate)
    return candidate


def _read_json_upload(upload: UploadFile, field: str) -> dict:
    try:
        data = json.loads(upload.file.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, f"{field} file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(422, f"{field} file must hold a JSON object.")
    return data


def _save_kml_upload(upload: UploadFile, workdir: Path, field: str = "kml") -> Path:
    name = Path(upload.filename or "source.kml").name
    if Path(name).suffix.lower() != ".kml":
        raise HTTPException(422, f"{field} file must be a .kml file.")
    local_source = workdir / name
    with local_source.open("wb") as stream:
        shutil.copyfileobj(upload.file, stream)
    return local_source


def _execute_config_dict(payload: dict, workdir: Path, download_name: str) -> FileResponse:
    """Run the standard config through loader + pipeline; return the DXF."""
    config_file = workdir / "inputconfig.json"
    config_file.write_text(json.dumps(payload), encoding="utf-8")

    try:
        esp_config = load_config_from_json(str(config_file))
    except (ValueError, KeyError, TypeError) as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(422, f"invalid config: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, f"config load failed: {exc}") from exc

    try:
        ESPGenerator(esp_config).run()
    except UnicodeError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, f"server output encoding failed: {exc}") from exc
    except (ValueError, KeyError) as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(422, f"generation rejected: {exc}") from exc
    except Exception as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, f"generation failed: {exc}") from exc

    dxf_path = workdir / download_name
    if not dxf_path.is_file():
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, "generator finished but produced no DXF.")

    saved_path = _persist_output(dxf_path, download_name)
    shutil.rmtree(workdir, ignore_errors=True)
    return FileResponse(
        path=str(saved_path),
        media_type=DXF_MEDIA_TYPE,
        filename=saved_path.name,
    )


@app.post("/main-center")
def main_center(kml: UploadFile = File(...)) -> dict:
    """MAIN midpoint + default 750 m loop extent from an uploaded KML."""
    workdir = Path(tempfile.mkdtemp(prefix="esp_center_"))
    try:
        local_source = _save_kml_upload(kml, workdir)
        try:
            center = wizard_main_center(local_source, workdir)
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


@app.post("/generate")
def generate(
    config: UploadFile = File(...),
    kml: UploadFile = File(...),
) -> FileResponse:
    """Generate the ESP DXF from an uploaded config JSON + KML file."""
    config_data = _read_json_upload(config, "config")

    workdir = Path(tempfile.mkdtemp(prefix="esp_"))
    local_source = _save_kml_upload(kml, workdir)

    download_name = Path(str(config_data.get("output_dxf") or "ESP_output.dxf").strip() or "ESP_output.dxf").name
    payload = dict(config_data)
    payload["source_path"] = str(local_source)
    payload["output_dxf"] = str(workdir / download_name)
    return _execute_config_dict(payload, workdir, download_name)


@app.post("/generate-wizard")
def generate_wizard(
    spec: UploadFile = File(...),
    kml: UploadFile = File(...),
) -> FileResponse:
    """Generate the ESP DXF from an interactive-style wizard spec + KML."""
    spec_data = _read_json_upload(spec, "spec")

    workdir = Path(tempfile.mkdtemp(prefix="esp_"))
    local_source = _save_kml_upload(kml, workdir)

    try:
        center = (
            wizard_main_center(local_source, workdir)
            if wizard_needs_center(spec_data)
            else None
        )
    except ValueError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(422, f"cannot place centred loops/FOBs: {exc}") from exc
    try:
        payload = wizard_to_config_dict(spec_data, center)
    except (ValueError, KeyError, TypeError) as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(422, f"invalid wizard spec: {exc}") from exc

    download_name = Path(str(payload.get("output_dxf") or "ESP_wizard.dxf").strip() or "ESP_wizard.dxf").name
    payload["source_path"] = str(local_source)
    payload["output_dxf"] = str(workdir / download_name)
    return _execute_config_dict(payload, workdir, download_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.server:app", host="127.0.0.1", port=8000)
