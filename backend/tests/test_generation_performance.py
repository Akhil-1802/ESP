"""Performance regressions checked by I/O counts and drawing parity, not wall time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import ezdxf
from ezdxf.document import Drawing
import pytest

from backend.benchmarks.generation import geometry_digest, yard_config
from common.cache import BoundedCache
from config.loader import ESPConfig
from pipeline.orchestrator import ESPGenerator
from platform_gen import kml_io
from wizard import wizard_main_center


KML = b'''<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><LineString>
<coordinates>77,28,0 77.015,28.004,0 77.03,28.01,0</coordinates>
</LineString></Placemark></kml>'''


def test_cache_byte_budget_lru_expiry_and_oversize():
    now = [0.0]
    cache = BoundedCache(6, 2, 10, clock=lambda: now[0])
    cache.put("a", b"aaa", 3)
    cache.put("b", b"bbb", 3)
    assert cache.get("a") == b"aaa"  # Refresh LRU, not expiry.
    cache.put("c", b"ccc", 3)
    assert cache.get("b") is None
    cache.put("oversize", b"x" * 7, 7)
    assert cache.get("oversize") is None
    assert cache.get("a") == b"aaa"
    now[0] = 10
    assert cache.get("a") is None
    assert cache.get("c") is None


def test_cache_deduplicates_identical_concurrent_requests():
    cache = BoundedCache(100, 4, 60)
    start = Barrier(4)
    computations = []

    def request(_):
        start.wait(timeout=5)
        with cache.single_flight("same"):
            result = cache.get("same")
            if result is None:
                computations.append(1)
                result = b"finished"
                cache.put("same", result, len(result))
            return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(request, range(4))) == [b"finished"] * 4
    assert len(computations) == 1
    assert cache._flights == {}


def test_cache_distinct_jobs_can_run_concurrently_and_failure_releases_lock():
    cache = BoundedCache(100, 4, 60)
    active = Barrier(2)

    def request(key):
        with cache.single_flight(key):
            active.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(request, ["a", "b"]))
    with pytest.raises(ValueError), cache.single_flight("failed"):
        raise ValueError("invalid geometry")
    with cache.single_flight("failed"):
        assert cache.get("failed") is None
    assert cache._flights == {}


@pytest.mark.parametrize("source_kind", ["dxf", "kml"])
def test_pipeline_reads_source_once_and_saves_once(tmp_path, source_kind):
    config = yard_config(tmp_path)
    if source_kind == "kml":
        source = tmp_path / "source.kml"
        source.write_bytes(KML)
        config.source_path = str(source)
    generator = ESPGenerator(config)
    real_save = Drawing.saveas
    with patch("ezdxf.readfile", wraps=ezdxf.readfile) as reads, patch.object(
        Drawing, "saveas", autospec=True, side_effect=real_save
    ) as saves:
        generator.run()
    assert reads.call_count == (1 if source_kind == "dxf" else 0)
    assert saves.call_count == 1
    assert generator.context.document is None
    assert generator.context.polygon_cache == {}
    assert generator.context.tracks == {}
    assert {"source", "tracks", "platforms", "fobs", "save", "total"} <= generator.timings.keys()
    assert all(duration >= 0 for duration in generator.timings.values())
    assert ezdxf.readfile(config.output_dxf).audit().has_errors is False
    assert not list(tmp_path.glob("*_converted.dxf"))


def layer_styles(doc):
    return sorted((layer.dxf.name, layer.dxf.color, layer.dxf.linetype,
                   layer.dxf.lineweight, layer.dxf.get("true_color")) for layer in doc.layers)


@pytest.mark.parametrize("source_kind", ["dxf", "kml"])
def test_memory_pipeline_preserves_disk_geometry_and_styles(tmp_path, source_kind):
    drawings = []
    for memory in [False, True]:
        directory = tmp_path / str(memory)
        directory.mkdir()
        config = yard_config(directory)
        if source_kind == "kml":
            source = directory / "source.kml"
            source.write_bytes(KML)
            config.source_path = str(source)
        ESPGenerator(config).run(in_memory=memory)
        drawings.append(ezdxf.readfile(config.output_dxf))
    disk, memory = drawings
    assert geometry_digest(memory) == geometry_digest(disk)
    assert layer_styles(memory) == layer_styles(disk)
    assert [(t.dxf.name, list(t.pattern_tags.tags)) for t in memory.linetypes] == [
        (t.dxf.name, list(t.pattern_tags.tags)) for t in disk.linetypes]


def test_failed_pipeline_discards_document_and_does_not_write_partial_output(tmp_path, monkeypatch):
    config = yard_config(tmp_path)
    generator = ESPGenerator(config)

    def reject(*_):
        raise ValueError("placement conflict")

    monkeypatch.setattr(generator, "_generate_platforms", reject)
    with pytest.raises(ValueError, match="placement conflict"):
        generator.run()
    assert not Path(config.output_dxf).exists()
    assert generator.context.document is None
    assert generator.context.in_memory is False
    assert "platforms" in generator.timings
    assert "total" in generator.timings


def test_simultaneous_generators_keep_their_own_drawings(tmp_path):
    active = Barrier(2)
    configs = []
    for name, length in [("short", 1000), ("long", 2000)]:
        source = tmp_path / f"{name}.dxf"
        doc = ezdxf.new()
        doc.modelspace().add_line((0, 0), (length, 0), dxfattribs={"layer": "MAIN_TRACK"})
        doc.saveas(source)
        configs.append(ESPConfig(str(source), str(tmp_path / f"{name}_out.dxf"), "MAIN_TRACK"))

    def run(config):
        generator = ESPGenerator(config)
        prepare = generator._prepare_source

        def prepare_together():
            prepare()
            active.wait(timeout=5)

        generator._prepare_source = prepare_together
        generator.run()
        return ezdxf.readfile(config.output_dxf).modelspace().query('LWPOLYLINE[layer=="MAIN_LINE"]')[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        lines = list(pool.map(run, configs))
    assert [list(line.get_points())[-1][0] for line in lines] == [1000, 2000]


def test_kml_cache_keys_by_content_and_options_and_returns_isolated_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(kml_io, "_KML_POINTS_CACHE", BoundedCache(1024, 4, 60))
    loads = []

    def extract(path, horizontal, selection):
        loads.append((Path(path).read_bytes(), horizontal, selection))
        return (((0.0, 0.0), (2000.0, 0.0)),)

    monkeypatch.setattr(kml_io, "_load_kml_points", extract)
    first, duplicate = tmp_path / "a.kml", tmp_path / "b.kml"
    first.write_bytes(KML)
    duplicate.write_bytes(KML)
    doc = kml_io.build_kml_document(str(first))
    doc.modelspace().add_line((0, 0), (1, 1))
    fresh = kml_io.build_kml_document(str(duplicate))
    assert fresh._esp_kml_cache_hit is True
    assert len(fresh.modelspace()) == 1
    assert len(loads) == 1
    kml_io.build_kml_document(str(first), selected_track_id="None")
    kml_io.build_kml_document(str(first), align_horizontal=False)
    duplicate.write_bytes(KML + b" ")
    kml_io.build_kml_document(str(duplicate))
    assert len(loads) == 4


def test_main_center_does_not_write_or_read_intermediate_dxf(tmp_path):
    source = tmp_path / "source.kml"
    source.write_bytes(KML)
    with patch("ezdxf.readfile") as reads, patch.object(Drawing, "saveas") as writes:
        assert wizard_main_center(source, tmp_path) > 750
    reads.assert_not_called()
    writes.assert_not_called()
