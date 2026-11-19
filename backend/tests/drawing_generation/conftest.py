import pytest
from app.features.drawing_generation import artifacts


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "BACKEND_OUTPUT_DIR", tmp_path / "output")
