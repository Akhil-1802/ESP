# DXF generation performance

Generation now uses one request-local `ezdxf` document. Tracks, platforms,
crossovers, stations, bridges, labels, boundaries, and the final rotation update
that document before a single final save. Standalone drawing helpers retain
their file-based behavior.

## What changed

- `pipeline/orchestrator.py` owns the document lifetime and records stage times.
- `pipeline/steps/base.py` supplies the shared document to each drawing step and
  caches extracted platform polygons for that request. Transient text-placement
  registries are rebuilt at the same stage boundaries as before.
- `platform_gen/kml_io.py` builds a document directly from projected KML points,
  removing the intermediate converted DXF. Its 8 MiB, four-entry, ten-minute
  cache stores immutable coordinates keyed by source content, track selection,
  and alignment option. Every caller receives a fresh document.
- `wizard/main.py` calculates the main midpoint in memory as well.
- `server.py` caches successful export bytes for five minutes, up to eight
  entries and 8 MiB total. The key includes source content and drawing settings;
  temporary paths and download names are excluded. Identical concurrent requests
  generate once, and each response gets a separate persisted file. Failures are
  never cached. Oversize artifacts are returned normally without caching.

Both caches are local to a running Python process, evict old entries, and clear
on restart. Different workers do not share cache contents. No hosting settings,
new dependencies, geometry simplification, or additional frontend requests are
required. Render service startup and network transfer delays remain separate
from generation time.

## Timing an export

The existing generation endpoints return `X-ESP-Cache: hit` or `miss` and a
`Server-Timing` header. On a cache miss, stages such as `source`, `tracks`,
`platforms`, `crossovers`, `fobs`, `rotation`, `save`, and `total` report
milliseconds in that header. The server logs the same stage durations in
seconds. A completed-export hit reports its cache lookup/wait/write duration.
These timings cover backend processing, not service startup or download time.

## Reproduce the benchmark

From the repository root:

```powershell
python backend/benchmarks/generation.py --disk --repeat 3 --reference baseline.json
python backend/benchmarks/generation.py --repeat 3 --compare baseline.json
python -m pytest backend/tests -q
```

`--disk` retains diagnostic file checkpoints. For a comparison to the original
implementation, run the same benchmark script against that revision first.
`--save-sample output.dxf` optionally preserves a drawing for CAD inspection.

The synthetic yard includes two loops, two platforms, a station, two crossovers,
an FOB, an ROB, trimming, and final rotation. It checks entity attributes,
coordinates, text, and leader annotation targets through a semantic digest;
generated timestamps and entity handles are excluded. Regression tests also
compare layer styles and linetype patterns, audit the resulting DXF, check I/O
counts, and exercise concurrent requests and cache invalidation.

On the development machine, three-run medians against the original revision
were **2.536 s before** and **0.173 s after** (about **14.7× faster**) with 605
entities and the same semantic digest. File reads fell from **19 to 1** and
writes from **18 to 1**. KML-based generation performs zero DXF reads and one
final save. These are local synthetic results, not a Render latency guarantee;
actual gains depend on input size, enabled features, CPU load, and cache hits.
