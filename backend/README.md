# ESP drawing API

This package serves the five HTTP operations used by the ESP frontend. Run these commands from `backend_new/` with your Python environment activated.

```console
python -m pip install -e ".[test]"
python -m uvicorn app.main:app --port 8000
```

| POST endpoint | Input | Result |
| --- | --- | --- |
| `/detect-tracks` | Multipart `kml`, optional track detection query parameters | Candidate tracks |
| `/main-center` | Multipart `kml`, optional `selected_track_id` | Midpoint and default loop extent |
| `/generate` | Multipart `config` JSON file and `kml` file | DXF download |
| `/convert-kml-direct` | Multipart `kml` | DXF preserving the KML linework |
| `/key-plan` | JSON with `generation_id` and optional `options` | Key-plan DXF for a finalized drawing |

### Mount in an existing FastAPI app

Copy `src/app/features/drawing_generation/` into the host package and install the runtime dependencies from `pyproject.toml`. Import the feature router from its new location. Its internal imports are relative.

```python
from .features.drawing_generation.router import router as drawing_router

app.include_router(drawing_router)
```

Mount the router at the API base URL used by the frontend. If the frontend runs on another origin, configure the host's CORS middleware to allow that origin and expose `Content-Disposition`, `X-ESP-Generation-ID`, `X-ESP-Cache`, and `Server-Timing`.

Set `ESP_OUTPUT_DIR` to a dedicated directory for generated files. It defaults to `output/` under the server's working directory. The retention task removes files older than ten minutes. Finalized snapshots are held in process memory, so route a generation and its subsequent key-plan request to the same worker.

Run `python -m pytest` from this directory for the API, drawing pipeline, and geometry regression tests.

## Follow a drawing request

The feature initializer, [drawing_generation/__init__.py](src/app/features/drawing_generation/__init__.py), is empty. It marks the directory as a Python package. The host imports [router.py](src/app/features/drawing_generation/router.py) to register the endpoints. For a normal `POST /generate`, follow these files in order:

1. [routes/generation.py](src/app/features/drawing_generation/routes/generation.py) accepts the config and KML uploads and creates a temporary workspace.
2. [config.py](src/app/features/drawing_generation/config.py) turns the uploaded settings into an `ESPConfig` that the drawing engine understands. [schemas.py](src/app/features/drawing_generation/schemas.py) serves a different purpose: it describes the JSON body for `/key-plan`.
3. [pipeline/export.py](src/app/features/drawing_generation/pipeline/export.py) checks for an existing result for the same source and settings. On a miss, [pipeline/generator.py](src/app/features/drawing_generation/pipeline/generator.py) runs the steps that build the tracks, place yard features, and annotate the drawing.
4. [artifacts.py](src/app/features/drawing_generation/artifacts.py) saves the finished DXF. The route returns the download and, when a finalized snapshot is available, a generation ID. [routes/key_plan.py](src/app/features/drawing_generation/routes/key_plan.py) can later use that ID to draw a schematic of the same design.

For a concrete maintenance example, a change to **siding clearance** belongs in [domain/track/siding.py](src/app/features/drawing_generation/domain/track/siding.py). A change to **how the dead end looks** belongs in [formats/dxf/siding.py](src/app/features/drawing_generation/formats/dxf/siding.py). [pipeline/steps/siding.py](src/app/features/drawing_generation/pipeline/steps/siding.py) connects the two during generation.

## High-level design (HLD)

The current drawing flow is a React frontend calling a FastAPI backend. Drawings are generated within HTTP requests and returned as DXF bytes. This flow has no database, cloud object storage, or background generation queue. The background task handles output-file cleanup.

```text
React frontend (App.jsx)
  |
  +-- Upload/select KML --> POST /detect-tracks --> Candidate coordinates
  |                              |
  |                        Frontend calculates centre/default extents
  |
  +-- Edit design -------> Browser live SVG preview
  |
  +-- Generate/Finalize -> POST /generate
  |                              |
  |                        Load ESPConfig
  |                              |
  |                        Check completed-export cache
  |                          | hit             | miss
  |                          |                 v
  |                          |           ESPGenerator pipeline
  |                          |                 |
  |                          +----- DXF + optional snapshot
  |                                    |
  |                        Copy DXF to output directory
  |                        Store snapshot under generation ID
  |                                    |
  |<------------------- DXF response + generation ID header
  |
  +-- Generate key plan -> POST /key-plan (generation ID + options)
  |                              |
  |                        Retrieve snapshot from RAM
  |                              |
  |                        Build schematic scene and DXF
  |                              |
  |<------------------- Separate key-plan DXF response
  |
  +-- View/download ----> Browser-held DXF Blob, SVG preview, PNG export
```

Additional paths are `POST /main-center`, used as a centre-position fallback before generation, and `POST /convert-kml-direct`, which converts KML linework without running the engineering pipeline.

### Component responsibilities

| Component | Responsibility | Implementation |
| --- | --- | --- |
| Frontend controller | Form state, actions, invalidation, selected drawing | [App.jsx](../frontend/src/App.jsx) |
| API client | Uploads, JSON requests, response Blobs and IDs | [api.js](../frontend/src/lib/api.js) |
| Application | FastAPI setup, CORS, exposed download headers | [main.py](src/app/main.py) |
| Feature router | Mount endpoints and cleanup lifespan | [router.py](src/app/features/drawing_generation/router.py) |
| HTTP handlers | Upload processing, local paths, errors, responses | [routes/](src/app/features/drawing_generation/routes/) |
| Configuration loader | Convert JSON into ESPConfig and domain objects | [config.py](src/app/features/drawing_generation/config.py) |
| Pipeline | Order engineering stages and measure timings | [generator.py](src/app/features/drawing_generation/pipeline/generator.py) |
| Domain and drawing modules | Calculate geometry and render DXF entities | [domain/](src/app/features/drawing_generation/domain/), [formats/dxf/](src/app/features/drawing_generation/formats/dxf/) |
| Snapshot and schematic modules | Capture resolved results and build key plans | [domain/key_plan/](src/app/features/drawing_generation/domain/key_plan/) |
| Export and cache | Reuse exports and retain finalized snapshots | [export.py](src/app/features/drawing_generation/pipeline/export.py), [cache.py](src/app/features/drawing_generation/cache.py) |
| Output lifecycle | Copy completed files and remove expired outputs | [artifacts.py](src/app/features/drawing_generation/artifacts.py) |

These are modules within one backend application, not independently deployed services.

## Low-level design (LLD)

### 1. KML upload and alignment selection

1. [SourceSection.jsx](../frontend/src/components/SourceSection.jsx) calls `loadKmlAlignment()` in [kmlAlignment.js](../frontend/src/lib/kmlAlignment.js).
2. The API client uploads the KML to `POST /detect-tracks`.
3. `inspection.py` creates a temporary directory and saves the upload through `_save_kml_upload()`.
4. `detect_kml_tracks()` returns candidate IDs and projected track coordinates.
5. The route deletes its temporary directory in a `finally` block.
6. The frontend stores the selected candidate ID and alignment points, then computes centre/default extents using `getTrackCentre()`.

```text
main_length_m = sum of metric alignment segment lengths
main_center_m = main_length_m / 2
default_c1_m  = main_center_m - 375
default_c2_m  = main_center_m + 375
```

Choosing another returned candidate reuses its coordinates. Normal upload/selection does not call `/main-center`. Before generation, `onGenerate()` calls `fetchMainCenter()` if `loopsNeedingCentre()` or `fobsNeedingCentre()` finds unresolved centre-based positions. This fallback sends the KML and selected track ID to `/main-center` and fills the returned positions into the form.

### 2. Editing, configuration, and previews

React state holds alignment, tracks, loops, crossovers, platforms, stations, sidings, bridges, gradients, and chainage settings. `buildConfig(form)` converts them to backend configuration.

| Preview | Implementation | Backend generation required? |
| --- | --- | --- |
| Live editing preview | `generateDynamicPreview(form)` builds SVG in the browser | No |
| Generated ESP/key-plan preview | `dxfToSvg()` converts a returned DXF Blob into SVG | Yes |

Design edits clear previous generated ESP and key-plan results. Key-plan presentation edits clear only the key-plan result. Revision counters discard responses for superseded designs/options. Editing alone does not automatically submit generation requests.

### 3. ESP generation request

`App.jsx → onGenerate()` fills missing centre-based values if needed, validates the form, builds configuration, and calls `generateDxf()`. The client sends multipart fields `config` (a JSON file) and `kml` to `POST /generate`.

In [generation.py](src/app/features/drawing_generation/routes/generation.py):

1. `_read_json_upload()` decodes and checks the JSON object.
2. Create a temporary working directory and save the uploaded KML.
3. Replace `source_path` and `output_dxf` with request-local paths.
4. `_execute_config_dict()` writes `inputconfig.json` and calls `load_config_from_json()`.
5. The loader constructs `ESPConfig` and nested loop/crossover specs and platform/bridge requests.
6. Call `export._generate_or_cached(esp_config, payload)`, returning `(cache_hit, timings, snapshot)`.

Invalid configuration or rejected generation values produce HTTP 422. Unexpected generation/encoding failures and a missing output DXF produce HTTP 500.

### 4. Completed-export cache

`_generate_or_cached()` calculates a SHA-256 key from the generation-cache version, source-file content digest, and drawing payload excluding `source_path` and `output_dxf`. Temporary paths and download names do not determine drawing identity.

- **Hit:** retrieve `(DXF bytes, snapshot bytes)`, write the DXF to the current output path, and return the associated snapshot.
- **Miss:** run `ESPGenerator`, serialize its snapshot to JSON bytes if present, and cache the successful DXF plus snapshot if the combined entry fits the byte budget.

`single_flight(key)` coordinates identical concurrent requests. Waiting requests can reuse the first result if it is successfully cached. The cache never stores the mutable working DXF document.

### 5. ESP pipeline and working state

`ESPGenerator.run()` creates a `GenerationContext`. By default, an `ezdxf` document stays in RAM while stages modify it, and the completed drawing is saved to disk at the end. Disk-checkpoint mode also exists for diagnostics.

```text
Prepare KML/source document
  → Build tracks
  → Platforms
  → Crossovers and resolved connections/cuts
  → Station buildings
  → Sidings
  → Fouling marks
  → Fencing
  → Foot over bridges (FOBs)
  → Bridges (bridges)
  → Gradients
  → Alignment and station chainage labels
  → Main-line trimming, when enabled
  → CAL labels
  → Land boundary
  → Key-plan snapshot, when both finalization flags are enabled
  → Final rotation/alignment, when enabled
  → Save DXF
```

Optional stages depend on configuration. Some annotation, trimming, and boundary stages log failures and continue, so a successful response does not imply every optional stage completed. Timings are recorded per executed stage. After the run, the generator clears working document and geometry references.

Ordering preserves dependencies: sidings use crossover/station results, bridges use tracks/platforms, and the snapshot captures resolved results before final rotation.

### 6. Finalization and snapshot capture

**Finalize Plan uses the same `POST /generate` endpoint.** The frontend sets both `enable_main_line_trim` and `align_final_plan_to_x_axis` when finalizing. This is a generation mode, not a database commit.

The current pipeline captures a key-plan snapshot only when both flags are true. Ordinary generation can therefore return a DXF without a snapshot or generation ID.

[capture_snapshot()](src/app/features/drawing_generation/domain/key_plan/snapshot.py) builds a Python dictionary containing displayed track extents, CAL lengths, directions, crossover endpoint chainages, platform/building results, station markers, bridges, overruns, north orientation, and overall bounds. It uses the original MAIN datum so trimming does not reset chainages.

The snapshot is engineering data extracted from generated results and drawing geometry, not an image or complete DXF copy. `export.py` serializes it through `json.dumps(...).encode()` and stores it alongside successful DXF bytes in the completed-export cache.

### 7. File response and browser result

After checking the DXF exists, `_persist_output()` copies it into `ESP_OUTPUT_DIR`, defaulting to `output/` under the server working directory. Filename collisions get a different name instead of overwriting an existing file.

The copy supports the current `FileResponse` lifecycle: the temporary workspace is removed when its directory context exits, while the response sends its file afterward. The copied output remains available for that transfer.

When a snapshot exists, the route creates a fresh UUID generation ID, stores snapshot bytes in `_KEY_PLAN_SNAPSHOTS`, and verifies the cache accepted the entry before exposing the ID. This happens on export-cache hits as well as misses.

| Response element | Meaning |
| --- | --- |
| Body | Generated DXF bytes |
| `Content-Disposition` | Download filename |
| `X-ESP-Cache` | Completed-export cache hit or miss |
| `Server-Timing` | Durations in milliseconds |
| `X-ESP-Generation-ID` | Snapshot lookup ID, when storage succeeds |

CORS exposes these headers. The frontend retains the DXF Blob, filename, generation ID, and SVG preview in state. Later DXF downloads use that Blob; PNG export uses the SVG in the browser. Neither needs another backend download request once the drawing is loaded.

### 8. Key-plan generation

The frontend enables key-plan generation when its backend result is finalized and has a generation ID. It sends JSON containing `generation_id` and presentation `options` to `POST /key-plan`.

In [key_plan.py](src/app/features/drawing_generation/routes/key_plan.py):

1. Retrieve snapshot bytes from `_KEY_PLAN_SNAPSHOTS` using the ID.
2. Return HTTP 410 with a re-finalization instruction if unavailable.
3. Decode JSON through `json.loads(snapshot)`.
4. Call `generate_key_plan(snapshot, options)`.
5. `build_scene()` maps engineering chainages and relationships into the schematic frame.
6. `draw_scene()` renders the scene into a separate DXF.
7. Save in a temporary directory, copy through `_persist_output()`, remove the temporary directory, and return the copied DXF.

The key plan uses resolved ESP results without reopening the ESP DXF or rerunning automatic crossover placement. Width, height, captions, and north-angle options control presentation. The schematic is marked NOT TO SCALE; actual measurements remain available in labels. Invalid layout values can produce HTTP 422.

The frontend stores and previews the key-plan DXF separately from the ESP. Presentation changes reuse the same snapshot; engineering changes require a new finalization.

### 9. Direct KML conversion

`POST /convert-kml-direct` converts KML linework directly into DXF. `/generate` can also choose this branch when configuration requests direct mode. It bypasses the standard engineering pipeline and completed-export/snapshot flow, then copies the output through `_persist_output()` for its response.

### 10. Storage, retention, and concurrency

| Data | Location | Lifetime / bounds |
| --- | --- | --- |
| Form, alignment, generated DXF Blobs and SVG previews | Browser React state | Until replaced/cleared or page state is lost |
| Uploaded KML and request configuration | Server temporary directory | Removed after use |
| Mutable working DXF document | Backend process RAM | Generation run |
| `_KML_POINTS_CACHE` | Backend process RAM | 4 entries, 8 MiB total, 600-second TTL |
| `_DXF_CACHE`: input hash → DXF bytes + optional snapshot | Backend process RAM | 8 entries, 8 MiB total, 300-second TTL |
| `_KEY_PLAN_SNAPSHOTS`: generation ID → JSON bytes | Backend process RAM | 32 entries, 4 MiB total, 600-second TTL |
| Copied completed ESP/key-plan DXFs | Server output directory | Eligible for removal after 600 seconds |

`BoundedCache` uses a locked Python `OrderedDict`, least-recently-used eviction, and time-to-live expiry. Expired entries are removed on cache access/insertion. Capacity pressure can evict entries earlier; reads update recency without extending expiry. Entries larger than the byte budget are rejected.

Memory caches are process-local and disappear on restart. Workers do not share generation IDs/snapshots, so key-plan requests must reach the worker holding their snapshot.

Output cleanup runs on startup, when persisting another output, and in a background sweeper every 60 seconds. Ten minutes is the file-age threshold, not an exact deletion deadline. Disk retention and memory-cache expiry are independent.

### 11. Storage responsibilities and future replacement points

- Working document: mutable state for engineering generation.
- Completed-export cache: speed up identical requests.
- Snapshot lookup: engineering data for a later key-plan request.
- Output-directory copy: file availability for the current response lifecycle.

A future database can retain snapshots and generation metadata across restarts/workers. Cloud object storage can retain DXFs for later downloads. The export cache remains an optional performance choice. Removing the output copy requires adapting response delivery or temporary-file cleanup so files remain available until transmission/upload finishes. These alternatives are not implemented in the current flow.

## Bridges

The station-yard editor supports **PSC Slab**, **RCC Box**, and **Other**. Other requires a custom type/name (up to 80 characters). The selected type supplies the drawing caption. These types currently share the same six-line bridge symbol; type selection does not imply a separate structural design.

Choose one placement method:

- **Offset from station edge:** select a station building, increasing/decreasing chainage direction, and a nonnegative offset. The distance is measured along MAIN from the corresponding edge of the actual generated building to the bridge centreline. It is not a platform-end offset or an edge-to-edge bridge clearance.
- **Absolute chainage:** enter railway stationing such as `12+850`, absolute metres such as `12850`, or an explicit unit such as `12.850 KM`. With an alignment start of `12+000`, these examples resolve to 850 m along MAIN. Plain numbers always mean metres in the bridge input.

Both modes use the original MAIN alignment datum before final trimming/rotation. Invalid references and positions outside the alignment are rejected rather than silently moved. Fixed placement needs no station or platform. Offset placement requires a generated station building.

The generation payload uses the `bridges` array:

```json
{
  "start_km": 12,
  "start_m": 0,
  "bridges": [
    {
      "id": "BRIDGE_1",
      "bridge_type": "PSC_SLAB",
      "position_mode": "OFFSET",
      "station_index": 0,
      "direction": "INCREASING",
      "offset": 100,
      "width": 10
    },
    {
      "id": "BRIDGE_2",
      "bridge_type": "OTHER",
      "custom_type": "Steel girder",
      "position_mode": "FIXED",
      "chainage": "12+850",
      "width": 12
    }
  ]
}
```

`station_index` is the zero-based index into the payload's `stations` building requests, not the station-marker index. The frontend maps the selected building explicitly. Only the selected placement mode's fields are submitted. Existing platform-end bridge configurations must be reconfigured using one of these methods.

Each bridge gets an independent DXF block so dimensions cannot overwrite another instance. Finalized key-plan snapshots retain the resolved centre, absolute chainage, identifier, and bridge type.

Implementation: [configuration](src/app/features/drawing_generation/domain/bridges/bridge/config.py), [placement resolver](src/app/features/drawing_generation/domain/bridges/bridge/placement.py), [geometry and captions](src/app/features/drawing_generation/domain/bridges/bridge/geometry.py), and [pipeline step](src/app/features/drawing_generation/pipeline/steps/bridge.py).


## FOB absolute chainage

The FOB fixed-placement option uses the same absolute MAIN railway datum as Bridges. Enter km+metres (for example 12+850), absolute metres (12850), or an explicit unit (12.850 KM). The alignment range appears below the input. Centre-fill controls also write absolute chainage. Offset-from-station-edge placement retains its existing behavior.

Fixed FOB requests carry position_mode: FIXED and absolute_chainage. The backend subtracts the alignment start datum, then resolves the selected reference track at that MAIN cross-section. Bounded reference tracks use their local resolved distance without subtracting their start twice. Invalid chainages and positions outside MAIN or beyond the selected reference track are rejected. Existing reference_chainage-only API configurations retain their local-distance semantics.

## Directory and file guide

Jump to the [HTTP routes](#http-routes), [pipeline](#drawing-pipeline), [railway domain](#railway-domain), [file formats](#file-formats), or [tests and fixtures](#tests-and-fixtures). Each filename below links to its implementation. Paths beginning with `domain/`, `formats/`, `pipeline/`, or `routes/` are relative to `src/app/features/drawing_generation/`.

#### backend_new/

Project root. Run the installation, server, and test commands above from here.

| File | Responsibility |
| --- | --- |
| [README.md](README.md) | Setup, integration, and the file guide you are reading. |
| [pyproject.toml](pyproject.toml) | Defines the installable package, Python version, runtime and test dependencies, source discovery, and pytest settings. |

#### src/

Source root used by the package builder. Installed imports start at `app`.

#### src/app/

Standalone FastAPI application. A host that already has an app can mount the feature router directly.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/__init__.py) | Empty package marker for this directory. |
| [main.py](src/app/main.py) | Creates the FastAPI app, configures browser CORS and exposed download headers, and registers the drawing router. |

#### src/app/features/

Groups features that can be mounted in a host application.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/__init__.py) | Empty package marker for this directory. |

#### src/app/features/drawing_generation/

The drawing feature’s public HTTP entry point and the services its routes share.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/__init__.py) | Empty package marker for this directory. |
| [router.py](src/app/features/drawing_generation/router.py) | Combines generation, inspection, and key-plan routes. Attaches the lifespan handler that manages output cleanup. |
| [schemas.py](src/app/features/drawing_generation/schemas.py) | Defines `KeyPlanRequest`, the JSON body for a key-plan request, including its generation ID and layout options. |
| [config.py](src/app/features/drawing_generation/config.py) | Reads the uploaded drawing configuration into `ESPConfig` and converts nested track, station, platform, and bridge requests into Python objects. |
| [artifacts.py](src/app/features/drawing_generation/artifacts.py) | Persists completed DXFs under unique filenames, sets the download media type, and removes expired output files. |
| [cache.py](src/app/features/drawing_generation/cache.py) | Provides file-content hashing and a bounded in-memory cache with expiry and locking for simultaneous requests for the same result. |

### HTTP routes

#### routes/

HTTP handlers. Start here for upload fields, status codes, response headers, and download filenames.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/routes/__init__.py) | Empty package marker for this directory. |
| [uploads.py](src/app/features/drawing_generation/routes/uploads.py) | Reads an uploaded JSON object and saves a validated KML upload in the request’s working directory. |
| [inspection.py](src/app/features/drawing_generation/routes/inspection.py) | Serves `/detect-tracks` and `/main-center`. Returns candidate tracks or the selected alignment’s midpoint and default loop limits. |
| [generation.py](src/app/features/drawing_generation/routes/generation.py) | Serves `/generate` and `/convert-kml-direct`. Chooses the generation path, persists the DXF, and returns the download. |
| [key_plan.py](src/app/features/drawing_generation/routes/key_plan.py) | Serves `/key-plan`. Looks up the finalized snapshot by ID, returns HTTP 410 if unavailable, and exports the schematic. |

### Drawing pipeline

#### pipeline/

Coordinates one drawing run, from source preparation through drawing and export.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/pipeline/__init__.py) | Empty package marker for this directory. |
| [generator.py](src/app/features/drawing_generation/pipeline/generator.py) | Defines `ESPGenerator`. Its `run()` method orders the drawing stages and records their timings. |
| [context.py](src/app/features/drawing_generation/pipeline/context.py) | Holds the mutable state shared by stages in one generation, including its in-memory DXF document. |
| [export.py](src/app/features/drawing_generation/pipeline/export.py) | Keys reusable exports by source content and settings, runs the generator on a cache miss, and holds the finalized snapshot cache. |

#### pipeline/steps/

Drawing stages and their helpers. A stage reads the current drawing and configuration, applies a feature, and makes the result available to later stages.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/pipeline/steps/__init__.py) | Exports the step classes used by the pipeline orchestrator. |
| [base.py](src/app/features/drawing_generation/pipeline/steps/base.py) | Provides shared layer cleanup, polygon caching, and document access for in-memory and disk-backed runs. |
| [track.py](src/app/features/drawing_generation/pipeline/steps/track.py) | Builds the main and loop tracks used by later stages and handles trimming the main alignment. |
| [platform.py](src/app/features/drawing_generation/pipeline/steps/platform.py) | Builds platform footprints, checks intersections with tracks and other platforms, and writes the accepted geometry. |
| [crossover.py](src/app/features/drawing_generation/pipeline/steps/crossover.py) | Expands crossover presets and runs planning and generation for the configured connections. |
| [crossover_cuts.py](src/app/features/drawing_generation/pipeline/steps/crossover_cuts.py) | Trims loop geometry at crossover switch joints and applies the overrun cuts. |
| [siding.py](src/app/features/drawing_generation/pipeline/steps/siding.py) | Selects and validates a turnout and siding path, then draws the siding, dead end, and annotations. |
| [station.py](src/app/features/drawing_generation/pipeline/steps/station.py) | Places station buildings relative to platforms, checks their footprints, and writes station features and labels. |
| [station_label.py](src/app/features/drawing_generation/pipeline/steps/station_label.py) | Moves a platform label when it clashes with a station building. |
| [fob.py](src/app/features/drawing_generation/pipeline/steps/fob.py) | Resolves footbridge placement from track, station, and platform geometry and generates the bridge deck. |
| [bridge.py](src/app/features/drawing_generation/pipeline/steps/bridge.py) | Places a bridge at its requested reference position and writes its geometry into the drawing. |
| [fouling.py](src/app/features/drawing_generation/pipeline/steps/fouling.py) | Runs fouling-mark detection on the generated tracks and draws the resulting marks. |
| [fencing.py](src/app/features/drawing_generation/pipeline/steps/fencing.py) | Draws platform fencing with gaps where station buildings occupy the edge. |
| [boundary.py](src/app/features/drawing_generation/pipeline/steps/boundary.py) | Derives the land boundary from drawing features and the main alignment. |
| [gradient.py](src/app/features/drawing_generation/pipeline/steps/gradient.py) | Draws gradient symbols and labels on the appropriate track at the resolved chainage. |
| [gradient_reference.py](src/app/features/drawing_generation/pipeline/steps/gradient_reference.py) | Parses kilometre and metre values and resolves the track and station references used to position gradient annotations. |
| [cal_labels.py](src/app/features/drawing_generation/pipeline/steps/cal_labels.py) | Runs the final CAL callout pass for loop and main lines. |
| [chainage.py](src/app/features/drawing_generation/pipeline/steps/chainage.py) | Combines marker collection, alignment ticks, and station-relative labels into the chainage step. |
| [chainage_alignment.py](src/app/features/drawing_generation/pipeline/steps/chainage_alignment.py) | Draws regularly spaced chainage ticks and configured station markers along the main alignment. |
| [chainage_collect.py](src/app/features/drawing_generation/pipeline/steps/chainage_collect.py) | Collects annotation positions from features such as platform ends, turnouts, sidings, fouling marks, and bridges. |
| [chainage_sides.py](src/app/features/drawing_generation/pipeline/steps/chainage_sides.py) | Finds station centres in the DXF and determines which side of a track or alignment a marker belongs on. |
| [chainage_labels.py](src/app/features/drawing_generation/pipeline/steps/chainage_labels.py) | Lays out and draws station-relative labels and their leaders around the yard. |
| [chainage_text.py](src/app/features/drawing_generation/pipeline/steps/chainage_text.py) | Defines text offsets and calculates the insertion point for text alongside a chainage leader. |

### Railway domain

#### domain/

Railway calculations and feature builders. Some builders also draw their results, especially bridges and chainage annotations.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/__init__.py) | Empty package marker for this directory. |
| [constants.py](src/app/features/drawing_generation/domain/constants.py) | Shared engineering dimensions, tolerances, and drawing defaults used across features. |

#### domain/geometry/

Geometry shared by tracks, platforms, and annotations. Chainage is distance measured along an alignment.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/geometry/__init__.py) | Empty package marker for this directory. |
| [alignment.py](src/app/features/drawing_generation/domain/geometry/alignment.py) | Measures distance along a polyline, interpolates points and tangents, computes offsets, and projects points onto an alignment. |
| [operations.py](src/app/features/drawing_generation/domain/geometry/operations.py) | Supplies common 2D operations such as distances, intersections, bounds, and polygon overlap. Also exposes the alignment helpers. |
| [chainage.py](src/app/features/drawing_generation/domain/geometry/chainage.py) | Defines the station datum, formats station-relative distances, and draws individual chainage annotations. |

#### domain/track/

Track definitions, construction, clearance calculations, and track-specific drawing rules.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/track/__init__.py) | Empty package marker for this directory. |
| [specs.py](src/app/features/drawing_generation/domain/track/specs.py) | Defines the input records for main lines, loops, sidings, crossovers, and track generation. |
| [generator.py](src/app/features/drawing_generation/domain/track/generator.py) | Builds main and loop alignments from reference tracks, offsets, configured extents, and extensions. |
| [directions.py](src/app/features/drawing_generation/domain/track/directions.py) | Resolves the UP or DOWN directions used for main-line annotations. |
| [turnouts.py](src/app/features/drawing_generation/domain/track/turnouts.py) | Defines turnout parameters and selects the geometry values for a requested turnout. |
| [siding.py](src/app/features/drawing_generation/domain/track/siding.py) | Builds a dead-end siding path and checks its footprint and separation from neighbouring features. |
| [overrun.py](src/app/features/drawing_generation/domain/track/overrun.py) | Finds loop-end switch joints and splits track polylines into running and overrun portions. |
| [overrun_metadata.py](src/app/features/drawing_generation/domain/track/overrun_metadata.py) | Attaches resolved overrun information to DXF labels and reads it back for downstream use. |
| [fouling_detect.py](src/app/features/drawing_generation/domain/track/fouling_detect.py) | Locates fouling marks by measuring where the clearance between tracks crosses its threshold. |
| [fouling.py](src/app/features/drawing_generation/domain/track/fouling.py) | Draws marks and annotations at the detected fouling positions. |
| [cal_calc.py](src/app/features/drawing_generation/domain/track/cal_calc.py) | Calculates line numbering and lengths for CAL callouts and formats their displayed values. |
| [cal_layout.py](src/app/features/drawing_generation/domain/track/cal_layout.py) | Positions CAL text, rows, and leaders relative to the tracks. |
| [cal_labels.py](src/app/features/drawing_generation/domain/track/cal_labels.py) | Combines CAL calculations and layout to draw callouts for main and loop lines. |

#### domain/track/crossover/

Plans and validates connections between tracks, then builds their geometry.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/track/crossover/__init__.py) | Exposes the package’s crossover planning, geometry, and validation functions and types. |
| [models.py](src/app/features/drawing_generation/domain/track/crossover/models.py) | Defines requests, results, validation reports, restricted regions, and conflicts. |
| [normalize.py](src/app/features/drawing_generation/domain/track/crossover/normalize.py) | Normalizes direction, placement, and position-mode inputs, including automatic chainages. |
| [defaults.py](src/app/features/drawing_generation/domain/track/crossover/defaults.py) | Converts specifications into planning requests and computes default crossover chainages. |
| [planner.py](src/app/features/drawing_generation/domain/track/crossover/planner.py) | Coordinates automatic placement against track geometry, spacing constraints, and fixed requests. |
| [planner_auto.py](src/app/features/drawing_generation/domain/track/crossover/planner_auto.py) | Scans candidate positions and selects starting points and search limits for automatic placement. |
| [planner_conflict.py](src/app/features/drawing_generation/domain/track/crossover/planner_conflict.py) | Checks whether candidate centrelines can be built and whether they conflict with fixed placements. |
| [validator.py](src/app/features/drawing_generation/domain/track/crossover/validator.py) | Runs the constraint checks and assembles a crossover validation report. |
| [rules.py](src/app/features/drawing_generation/domain/track/crossover/rules.py) | Implements checks for track selection, chainages, spacing, footprints, geometry, and boundaries. |
| [conflicts.py](src/app/features/drawing_generation/domain/track/crossover/conflicts.py) | Converts platform and station extents into restricted intervals and finds conflicts with a crossover. |
| [footprints.py](src/app/features/drawing_generation/domain/track/crossover/footprints.py) | Tests footprint overlap and polyline self-intersection and identifies main-track anchors. |
| [geometry.py](src/app/features/drawing_generation/domain/track/crossover/geometry.py) | Computes separations, switch-joint positions, and lateral bands used by planning and validation. |
| [core.py](src/app/features/drawing_generation/domain/track/crossover/core.py) | Calculates crossover dimensions and generates coordinates against the source and target alignments. |
| [core_build.py](src/app/features/drawing_generation/domain/track/crossover/core_build.py) | Builds the standard crossover centreline between its two switch joints. |
| [reverse_curve.py](src/app/features/drawing_generation/domain/track/crossover/reverse_curve.py) | Builds reverse-curve crossover geometry for widely spaced tracks. |
| [loops.py](src/app/features/drawing_generation/domain/track/crossover/loops.py) | Builds a loop alignment connecting two turnouts. |
| [turnout.py](src/app/features/drawing_generation/domain/track/crossover/turnout.py) | Samples the tangent, arc, and spline portions of a turnout and transforms them into drawing coordinates. |

#### domain/platform/

Constructs platform outlines and their stairs, labels, and dimensions.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/platform/__init__.py) | Empty package marker for this directory. |
| [config.py](src/app/features/drawing_generation/domain/platform/config.py) | Defines platform type, side, and configuration values. |
| [generator.py](src/app/features/drawing_generation/domain/platform/generator.py) | Coordinates platform generation from the selected track and platform settings. |
| [island.py](src/app/features/drawing_generation/domain/platform/island.py) | Builds the outline of an island platform between tracks. |
| [side.py](src/app/features/drawing_generation/domain/platform/side.py) | Builds a side platform, including local widenings along its outer edge. |
| [models.py](src/app/features/drawing_generation/domain/platform/models.py) | Defines the platform result and specifications for dimensions, labels, and stairs. |
| [stairs.py](src/app/features/drawing_generation/domain/platform/stairs.py) | Generates the stair or arm geometry attached to a platform. |
| [track.py](src/app/features/drawing_generation/domain/platform/track.py) | Reads a track centreline from DXF entities and exposes it to the platform builder. |

#### domain/station/

Builds the station features drawn next to a platform.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/station/__init__.py) | Empty package marker for this directory. |
| [builder.py](src/app/features/drawing_generation/domain/station/builder.py) | Calculates a station-building footprint centred on a platform polygon. |
| [station_flag.py](src/app/features/drawing_generation/domain/station/station_flag.py) | Builds and draws the station flag symbol using DXF geometry. |

#### domain/bridges/

Groups the two bridge types used in a yard drawing.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/bridges/__init__.py) | Empty package marker for this directory. |

#### domain/bridges/fob/

Foot overbridge (FOB) placement, deck geometry, and rendering.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/bridges/fob/__init__.py) | Empty package marker for this directory. |
| [config.py](src/app/features/drawing_generation/domain/bridges/fob/config.py) | Defines footbridge options and validates clearance, offset, and direction. |
| [placement.py](src/app/features/drawing_generation/domain/bridges/fob/placement.py) | Locates the station edge, resolves bridge chainage relative to it, and checks placement conflicts. |
| [deck_geom.py](src/app/features/drawing_generation/domain/bridges/fob/deck_geom.py) | Computes deck spans, track crossings, outlines, landing arms, and label positions. |
| [deck.py](src/app/features/drawing_generation/domain/bridges/fob/deck.py) | Resolves the deck location, invokes the geometry calculations, and writes the footbridge to the DXF. |

#### domain/bridges/bridge/

Bridge settings and geometry.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/bridges/bridge/__init__.py) | Empty package marker for this directory. |
| [config.py](src/app/features/drawing_generation/domain/bridges/bridge/config.py) | Defines bridge configuration values. |
| [geometry.py](src/app/features/drawing_generation/domain/bridges/bridge/geometry.py) | Measures the cross-track extent, builds the bridge geometry, and writes it to the drawing. |

#### domain/key_plan/

Turns a finalized yard design into a schematic while retaining the design’s actual measurements.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/domain/key_plan/__init__.py) | Empty package marker for this directory. |
| [snapshot.py](src/app/features/drawing_generation/domain/key_plan/snapshot.py) | Captures resolved tracks and yard features before final rotation and cleanup. |
| [config.py](src/app/features/drawing_generation/domain/key_plan/config.py) | Validates schematic dimensions, captions, and other presentation options. |
| [normalize.py](src/app/features/drawing_generation/domain/key_plan/normalize.py) | Maps real chainages and ordered track levels to schematic coordinates. |
| [models.py](src/app/features/drawing_generation/domain/key_plan/models.py) | Defines `Scene`, the in-memory collection of lines, polygons, text, and feature metadata. |
| [layout.py](src/app/features/drawing_generation/domain/key_plan/layout.py) | Builds a scene within the requested dimensions from the snapshot and layout options. |
| [generator.py](src/app/features/drawing_generation/domain/key_plan/generator.py) | Takes the snapshot and options, builds the scene, and renders the key-plan DXF. |

### File formats

#### formats/

Groups the readers and writers for the two external drawing formats.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/formats/__init__.py) | Empty package marker for this directory. |

#### formats/kml/

Reads geographic linework from KML uploads.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/formats/kml/__init__.py) | Empty package marker for this directory. |
| [track_detector.py](src/app/features/drawing_generation/formats/kml/track_detector.py) | Joins connected segments, filters short features, and ranks candidate railway tracks. |
| [center.py](src/app/features/drawing_generation/formats/kml/center.py) | Finds the midpoint chainage of the longest matching main alignment and checks it can fit the default loop. |
| [conversion.py](src/app/features/drawing_generation/formats/kml/conversion.py) | Projects geographic coordinates into metres. Builds the aligned source drawing for generation or preserves the original orientation for direct conversion. |

#### formats/dxf/

Shared DXF rendering, style management, and final drawing transformations.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/formats/dxf/__init__.py) | Empty package marker for this directory. |
| [primitives.py](src/app/features/drawing_generation/formats/dxf/primitives.py) | Adds basic DXF entities such as polylines, splines, text, and dimension arrows. |
| [styles.py](src/app/features/drawing_generation/formats/dxf/styles.py) | Creates and configures layers, linetypes, and text styles. |
| [text.py](src/app/features/drawing_generation/formats/dxf/text.py) | Estimates text bounds and finds insertion positions clear of tracks and existing text. |
| [platform_io.py](src/app/features/drawing_generation/formats/dxf/platform_io.py) | Writes platform geometry, labels, and dimensions at drawing scale. |
| [siding.py](src/app/features/drawing_generation/formats/dxf/siding.py) | Draws the siding dead-end marker and clear standing length annotation. |
| [key_plan.py](src/app/features/drawing_generation/formats/dxf/key_plan.py) | Renders a schematic scene into a DXF document. |
| [final_plan.py](src/app/features/drawing_generation/formats/dxf/final_plan.py) | Rotates the completed plan using the main alignment’s best-fit direction and handles label orientation. |

#### formats/dxf/tracks/

DXF rendering specific to track lines, markers, and annotations.

| File | Responsibility |
| --- | --- |
| [__init__.py](src/app/features/drawing_generation/formats/dxf/tracks/__init__.py) | Exports the track-rendering functions used by drawing stages. |
| [tracks.py](src/app/features/drawing_generation/formats/dxf/tracks/tracks.py) | Coordinates drawing of main and loop tracks on their assigned layers. |
| [splines.py](src/app/features/drawing_generation/formats/dxf/tracks/splines.py) | Draws track splines and measures local clearance and anchor positions. |
| [markers.py](src/app/features/drawing_generation/formats/dxf/tracks/markers.py) | Draws switch-joint posts, direction arrows, dead ends, and overrun markers. |
| [annotations.py](src/app/features/drawing_generation/formats/dxf/tracks/annotations.py) | Places track names and track-centre spacing annotations. |

### Tests and fixtures

#### tests/

Pytest discovery root. The tests and their input files live under the feature they exercise.

#### tests/drawing_generation/

Tests that exercise the API, file conversions, caching, and interactions between drawing features.

| File | Responsibility |
| --- | --- |
| [__init__.py](tests/drawing_generation/__init__.py) | Empty package marker for this directory. |
| [conftest.py](tests/drawing_generation/conftest.py) | Automatically directs generated downloads to a temporary directory for each test. |
| [yard_fixture.py](tests/drawing_generation/yard_fixture.py) | Builds a representative yard and calculates a geometry digest for drawing comparisons. |
| [test_endpoints.py](tests/drawing_generation/test_endpoints.py) | Checks generation downloads, midpoint responses, rejected uploads, required fields, and output expiry. |
| [test_export_cache.py](tests/drawing_generation/test_export_cache.py) | Checks cache reuse, invalidation, distinct downloads for concurrent requests, and handling of failed exports. |
| [test_generation_performance.py](tests/drawing_generation/test_generation_performance.py) | Checks I/O counts, concurrency, cache limits, and geometry parity between disk and in-memory generation. |
| [test_key_plan.py](tests/drawing_generation/test_key_plan.py) | Checks snapshot reuse, expiry, layout, DXF round trips, and preservation of dimensions and directions. |
| [test_kml_direct.py](tests/drawing_generation/test_kml_direct.py) | Checks direct KML conversion through the converter and HTTP endpoints, including preservation of multiple lines. |
| [test_platform_overlap.py](tests/drawing_generation/test_platform_overlap.py) | Checks that platform outlines and stairs respect track and neighbouring platform geometry. |
| [test_track_detector.py](tests/drawing_generation/test_track_detector.py) | Checks candidate detection, connected segments, selected-track conversion, and survey-file regressions. |

#### tests/drawing_generation/fixtures/

Reusable input files. The larger KML samples are stored as gzip archives and unpacked by the tests.

| File | Responsibility |
| --- | --- |
| [ESP.kml](tests/drawing_generation/fixtures/ESP.kml) | Small alignment used in endpoint and platform tests. |
| [Ghaziabad.kml](tests/drawing_generation/fixtures/Ghaziabad.kml) | Single-path survey sample used for conversion and track-detection checks. |
| [Drawing5.kml.gz](tests/drawing_generation/fixtures/Drawing5.kml.gz) | Multi-line drawing sample used to verify that direct conversion preserves the source linework. |
| [doc.kml.gz](tests/drawing_generation/fixtures/doc.kml.gz) | Larger survey used to check candidate grouping, ordering, and measured lengths. |
| [inputconfig.json](tests/drawing_generation/fixtures/inputconfig.json) | Example generation settings uploaded alongside a KML file in endpoint tests. |

#### tests/drawing_generation/domain/

Feature-specific regression tests. Some exercise an individual calculation, while others generate a DXF and inspect its entities.

| File | Responsibility |
| --- | --- |
| [__init__.py](tests/drawing_generation/domain/__init__.py) | Empty package marker for this directory. |
| [gradient_fixture.py](tests/drawing_generation/domain/gradient_fixture.py) | Builds a sample gradient pipeline and extracts lines and text from its DXF. |
| [helpers_cal_labels.py](tests/drawing_generation/domain/helpers_cal_labels.py) | Builds track and mark fixtures and measures CAL text, leaders, and intersections. |
| [helpers_crossover.py](tests/drawing_generation/domain/helpers_crossover.py) | Builds straight, rotated, and curved tracks and supplies crossover requests for planner tests. |
| [test_boundary.py](tests/drawing_generation/domain/test_boundary.py) | Checks the land boundary’s extent, style, and behavior before and after finalization. |
| [test_cal_labels_calc.py](tests/drawing_generation/domain/test_cal_labels_calc.py) | Checks CAL values, label formatting, line numbering, and the span between fouling marks. |
| [test_cal_labels_layout.py](tests/drawing_generation/domain/test_cal_labels_layout.py) | Checks label stacking, leader placement, and clearances around tracks. |
| [test_chainage.py](tests/drawing_generation/domain/test_chainage.py) | Checks station datum projection, relative distance formatting, and the placement of chainage annotations. |
| [test_chainage_drawing.py](tests/drawing_generation/domain/test_chainage_drawing.py) | Checks interval ticks, station markers, leader limits, and placement on either side of the alignment. |
| [test_crossover_advanced.py](tests/drawing_generation/domain/test_crossover_advanced.py) | Checks planning and anchoring on rotated and curved tracks and interactions between multiple crossovers. |
| [test_crossover_validation.py](tests/drawing_generation/domain/test_crossover_validation.py) | Checks valid and invalid crossover combinations, spacing, and geometry constraints. |
| [test_dimensions.py](tests/drawing_generation/domain/test_dimensions.py) | Inspects DXF dimensions and captions for platforms, footbridge decks, and platform arms. |
| [test_dynamic_fob.py](tests/drawing_generation/domain/test_dynamic_fob.py) | Checks bridge positions calculated from station edges, offsets, directions, and conflicts. |
| [test_final_plan.py](tests/drawing_generation/domain/test_final_plan.py) | Checks that final rotation preserves relative geometry, blocks, and intended label orientations. |
| [test_fob_basic.py](tests/drawing_generation/domain/test_fob_basic.py) | Checks bridge configuration, span and clearance limits, and end-to-end deck generation. |
| [test_fob_deck.py](tests/drawing_generation/domain/test_fob_deck.py) | Checks deck intersections, spans, width, and extensions against platform boundaries. |
| [test_fob_side_arm_clearance.py](tests/drawing_generation/domain/test_fob_side_arm_clearance.py) | Checks landing-arm clearances, island-arm centring, and local widening of side platforms. |
| [test_fouling.py](tests/drawing_generation/domain/test_fouling.py) | Checks automatic fouling-mark detection, chainage calculation, and the resulting DXF marks. |
| [test_gradient.py](tests/drawing_generation/domain/test_gradient.py) | Checks gradient chainage parsing, unit conversion, offsets, and display formatting. |
| [test_gradient_drawing.py](tests/drawing_generation/domain/test_gradient_drawing.py) | Checks gradient symbols and text on straight and curved tracks and rejection of out-of-range positions. |
| [test_loop_auto_crossover.py](tests/drawing_generation/domain/test_loop_auto_crossover.py) | Checks automatic crossover anchoring at loop ends and adjustment when placements collide. |
| [test_loop_parallel.py](tests/drawing_generation/domain/test_loop_parallel.py) | Checks that loops remain parallel through bends, with extensions and chained references. |
| [test_main_line_trim.py](tests/drawing_generation/domain/test_main_line_trim.py) | Checks trimming beyond the outermost relevant switch joints and behavior when there are none. |
| [test_main_lines.py](tests/drawing_generation/domain/test_main_lines.py) | Checks independent parallel main lines, direction marks, and valid reference tracks. |
| [test_platform_arm.py](tests/drawing_generation/domain/test_platform_arm.py) | Checks configurable arm length, stair geometry, and footbridge label orientation. |
| [test_bridge.py](tests/drawing_generation/domain/test_bridge.py) | Checks bridge settings, geometry across multiple tracks, offsets, and station-relative placement. |
| [test_siding.py](tests/drawing_generation/domain/test_siding.py) | Checks siding geometry, clearances, validation, configuration loading, and dead-end drawing. |
| [test_station_chainage.py](tests/drawing_generation/domain/test_station_chainage.py) | Checks station-centre chainage inputs, accepted configuration aliases, and DXF label text. |
| [test_station_flag.py](tests/drawing_generation/domain/test_station_flag.py) | Checks the flag geometry directly and on a generated station drawing. |
| [test_station_platform_label.py](tests/drawing_generation/domain/test_station_platform_label.py) | Checks that platform labels remain legible around buildings and that direction marks are placed correctly. |
| [test_text_style.py](tests/drawing_generation/domain/test_text_style.py) | Checks fonts, numeric and letter styles, and collision avoidance when placing text. |
| [test_turnout_smoothness.py](tests/drawing_generation/domain/test_turnout_smoothness.py) | Checks tangent and curvature continuity at spline boundaries and preservation of crossover dimensions. |
| [test_turnouts.py](tests/drawing_generation/domain/test_turnouts.py) | Checks turnout parameter tables and the radii selected for supported turnout ratios. |
