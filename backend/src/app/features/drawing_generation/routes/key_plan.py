import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..artifacts import DXF_MEDIA_TYPE, _persist_output
from ..domain.key_plan.generator import generate_key_plan
from ..pipeline import export
from ..schemas import KeyPlanRequest

router = APIRouter()


@router.post("/key-plan")
def key_plan(request: KeyPlanRequest) -> FileResponse:
    """Create a schematic from the exact finalized generation, without replanning."""
    snapshot = export._KEY_PLAN_SNAPSHOTS.get(request.generation_id)
    if snapshot is None:
        raise HTTPException(410, "Finalized design has expired or is unavailable. Finalize the ESP again, then generate the key plan.")
    workdir = Path(tempfile.mkdtemp(prefix="esp_key_plan_"))
    try:
        doc = generate_key_plan(json.loads(snapshot), request.options)
        path = workdir / "ESP_key_plan.dxf"
        doc.saveas(path)
        saved = _persist_output(path, path.name)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"Key plan cannot be laid out: {exc}") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return FileResponse(str(saved), media_type=DXF_MEDIA_TYPE, filename=saved.name)
