# Key Plan

Generate the ESP, then click **Finalize Plan**. In the **Key Plan** section,
adjust the container dimensions/captions and click **Generate Key Plan**.
Switch between **Final ESP** and **Key Plan** above the drawing. The viewer's
DXF and PNG download actions export the selected view.

The default standalone schematic is 420 × 150 mm and is marked **NOT TO SCALE**.
The original ESP remains a separate drawing in metres. Increasing width changes
chainage-to-X mapping; increasing height changes track levels, platform thickness,
gaps, symbols and text. Actual lengths and platform widths remain in labels.
Overrun lines appear separately from the running tracks, with an SRJ anchor
and dead-end stop. Overrun captions and crossover IDs (C1, C2, etc.) are omitted
from the drawing; turnout ratios such as 1:12 remain visible. Actual overrun
lengths and crossover IDs remain in the snapshot. Configured overruns and
overruns created or moved by crossover/SRJ placement use the finalized ESP
anchors, including clipped extensions at alignment ends. Zero-length/disabled
overruns are omitted. Their tips are included when fitting the complete frame.

Main lines show **UP MAIN LINE** / **DN MAIN LINE** captions and direction arrows
in the left and right margins, outside the yard. The key-plan reference convention
is **DN →** and **UP ←**. A single unspecified main line shows DN above and UP
below the centreline at both ends. Set individual directions in the main-track inputs,
then finalize again to refresh them in the key plan.

The displayed boundary is explicitly schematic. North is a survey orientation
reference, with an optional angle override measured counterclockwise from right.

## Data flow

`ESPGenerator` captures plain resolved geometry before final rotation and context
cleanup: displayed track extents, CAL lengths, actual crossover endpoint chainages,
platform/building results, bridges, overrun anchors/lengths and resolved main-line
directions. Overrun CAL labels carry their host track and anchors as DXF XDATA,
so redraws, SRJ cuts and disk checkpoints retain the final engineering data.
The snapshot uses the original MAIN datum,
so trimming does not reset chainages. Bridge positions come from generated geometry,
so bounded-loop reference chainages are not misinterpreted as local MAIN distances.
Generation caches store the snapshot with the successful DXF bytes, including
on cache hits.

Successful final exports expose `X-ESP-Generation-ID` through CORS.
`POST /key-plan` accepts:

```json
{
  "generation_id": "<32-character identifier from finalization>",
  "options": {
    "width": 420,
    "height": 150,
    "left_destination": "",
    "right_destination": "",
    "station_caption": "",
    "north_angle": null
  }
}
```

It returns a separate DXF built by `backend/key_plan/`. It never reruns the ESP
pipeline or AUTO crossover resolution. The frontend previews those returned DXF
bytes through its existing renderer, fitting the entire frame initially.

Snapshots are process-local, bounded to 32 entries/4 MB and expire after 10 minutes.
An unavailable snapshot returns HTTP 410 with a re-finalization instruction.
Invalid dimensions, unreadable captions or unsupported crowded arrangements return
HTTP 422 rather than clipping or silently modifying engineering positions.
Container width is 210–1680 mm and height is 100–1200 mm.

Design edits invalidate the finalized ID/key-plan view. Presentation-only edits
invalidate just the key-plan result; neither sends an automatic backend request.
In-flight results are discarded when their design/options have been superseded.

## Validation

`backend/tests/test_key_plan.py` covers proportional X/Y resizing, measurement
preservation, track ordering, island platforms, label placement, DXF round trips,
snapshot expiry, cached finalization and complete-yard integration.
`frontend/src/lib/keyPlan.test.js` checks the API contract and expiry handling.
