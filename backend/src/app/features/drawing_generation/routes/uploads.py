import json
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile


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
