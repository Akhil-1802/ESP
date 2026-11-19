"""One bounded schematic scene shared by DXF export and its browser preview."""

import math
import textwrap

from .models import Scene
from .normalize import Normalizer


def build_scene(snapshot, options):
    n = Normalizer(snapshot, options)
    w, h, font = options.width, options.height, min(options.font, n.step*.24)
    scene = Scene(w, h)
    boxes = []
    obstacles = []

    def line(points, layer="KEY_PLAN_TRACK"):
        scene.lines.append(dict(points=points, layer=layer))

    def polygon(points, layer):
        scene.polygons.append(dict(points=points, layer=layer))

    def rectangle(x0, y0, x1, y1, layer):
        polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer)

    def label(text, x, y, width, size=font, move=True, layer="KEY_PLAN_TEXT", alternate_y=None, avoid_obstacles=False):
        text = " ".join(str(text).split())
        if not text:
            return
        size = min(size, width / max(1, len(text) * 0.75))
        if size < font * 0.65:
            raise ValueError(f"Key-plan label is too long to fit legibly: {text[:70]}. Shorten the caption or widen the container.")
        tw = len(text) * size * 0.75
        # Reserve a generous text box; shift labels only, never engineering endpoints.
        for cy in [y] + ([] if alternate_y is None else [alternate_y]):
            for shift in ([0, -0.06*w, 0.06*w, -0.12*w, 0.12*w] if move else [0]):
                cx = min(max(x + shift, tw / 2 + w*.015), w*.985 - tw/2)
                box = (cx-tw/2, cy-size*.65, cx+tw/2, cy+size*.65)
                occupied = boxes + (obstacles if avoid_obstacles else [])
                if any(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in occupied):
                    continue
                if box[1] < h*.02 or box[3] > h*.98:
                    continue
                boxes.append(box)
                scene.texts.append(dict(text=text, x=cx, y=cy, height=size, layer=layer))
                return cx, cy
        raise ValueError(f"Key-plan labels overlap near {text[:60]}. Increase width or shorten captions.")

    def arrow(x0, y0, x1, y1, size, layer="KEY_PLAN_SYMBOL", both=False):
        line([(x0, y0), (x1, y1)], layer)
        a = math.atan2(y1-y0, x1-x0)
        polygon([(x1, y1), (x1-size*math.cos(a-.35), y1-size*math.sin(a-.35)),
                 (x1-size*math.cos(a+.35), y1-size*math.sin(a+.35))], "KEY_PLAN_ARROW")
        if both:
            polygon([(x0, y0), (x0+size*math.cos(a-.35), y0+size*math.sin(a-.35)),
                     (x0+size*math.cos(a+.35), y0+size*math.sin(a+.35))], "KEY_PLAN_ARROW")

    rectangle(w*.005, h*.015, w*.995, h*.985, "KEY_PLAN_FRAME")
    rectangle(w*.009, h*.025, w*.991, h*.975, "KEY_PLAN_FRAME")
    label("KEY PLAN (NOT TO SCALE)", w/2, h*.09, w*.8, font*1.7, move=False)
    label("BOUNDARY (SCHEMATIC)", w/2, h*.165, w*.65, font*.75, move=False)
    # Stepped drafting outline. It is explicitly schematic, not a cadastral ROW claim.
    for y_outer, y_inner in ((h*.80, h*.73), (h*.20, h*.27)):
        line([(w*.02, y_inner), (w*.10, y_inner), (w*.10, (y_inner+y_outer)/2),
              (w*.19, (y_inner+y_outer)/2), (w*.19, y_outer), (w*.81, y_outer),
              (w*.81, (y_inner+y_outer)/2), (w*.90, (y_inner+y_outer)/2),
              (w*.90, y_inner), (w*.98, y_inner)], "KEY_PLAN_ROW")
    for track in sorted(snapshot["tracks"], key=lambda t: t["offset"]):
        y = n.levels[track["name"]]
        x0, x1 = sorted((n.x(track["start"]), n.x(track["end"])))
        line([(x0, y), (x1, y)])
        scene.tracks.append(dict(**track, x0=x0, x1=x1, y=y))

    platform_boxes = []
    for platform in snapshot["platforms"]:
        y = n.levels[platform["track"]]
        if platform["type"] == "ISLAND":
            other = n.levels.get(platform["second_track"])
            if other is None:
                raise ValueError(f"Missing second track for island platform {platform['name']}.")
            y0, y1 = (y+other)/2-n.thickness/2, (y+other)/2+n.thickness/2
        elif platform["side"] == "LEFT":
            y0, y1 = y+n.gap, y+n.gap+n.thickness
        else:
            y0, y1 = y-n.gap-n.thickness, y-n.gap
        x0, x1 = sorted((n.x(platform["start"]), n.x(platform["end"])))
        box = (x0, y0, x1, y1)
        if any(x0 < b[2] and x1 > b[0] and y0 < b[3] and y1 > b[1] for b in platform_boxes):
            raise ValueError("Schematic platforms overlap. Use separate key plans for this yard arrangement.")
        if any(y0 < other < y1 for other in n.levels.values()):
            raise ValueError("A schematic platform crosses a track. Increase track separation in the key-plan template.")
        platform_boxes.append(box)
        rectangle(*box, "KEY_PLAN_PLATFORM")
        text = f"{platform['name'].replace('_', ' ')} {platform['length_m']:.2f} x {platform['width_m']:.2f}M"
        label(text, (x0+x1)/2, (y0+y1)/2, (x1-x0)*.95, min(font, n.thickness*.38), move=False)
        scene.platforms.append(dict(**platform, x0=x0, x1=x1, y0=y0, y1=y1))

    obstacles.extend(platform_boxes)
    for track in scene.tracks:
        label(track["label"], (track["x0"]+track["x1"])/2, track["y"]-font*1.2,
              track["x1"]-track["x0"], font*.90, alternate_y=track["y"]+font*1.2,
              avoid_obstacles=True)

    for crossover in snapshot["crossovers"]:
        x0, x1 = n.x(crossover["start"]), n.x(crossover["end"])
        y0, y1 = n.levels[crossover["from_track"]], n.levels[crossover["to_track"]]
        if abs(x1-x0) < font*.5:
            raise ValueError(f"Crossover {crossover['id']} is too compressed to read. Widen the key-plan container.")
        # Smooth-looking S transition with exact finalized endpoint anchors.
        points = []
        for i in range(17):
            t = i/16
            blend = t*t*(3-2*t)
            points.append((x0+(x1-x0)*t, y0+(y1-y0)*blend))
        line(points, "KEY_PLAN_CONNECTION")
        for x, y in ((x0, y0), (x1, y1)):
            r = font*.22
            polygon([(x-r, y), (x, y+r), (x+r, y), (x, y-r)], "KEY_PLAN_SRJ")
        position = label(crossover['turnout'], (x0+x1)/2,
              (y0+y1)/2+font, w*.17, font*.72, alternate_y=(y0+y1)/2-font,
              avoid_obstacles=True)
        if position and abs(position[0]-(x0+x1)/2) > font:
            line([((x0+x1)/2, (y0+y1)/2), (position[0], position[1]-font*.6)], "KEY_PLAN_CALLOUT")
        scene.crossovers.append(dict(**crossover, x0=x0, x1=x1, y0=y0, y1=y1))

    for overrun in snapshot.get("overruns", []):
        track = next((t for t in scene.tracks if t["name"] == overrun["track"]), None)
        if track is None:
            raise ValueError(f"Missing track for overrun {overrun['track']}.")
        sx, tx, y = n.x(overrun["srj_chainage"]), n.x(overrun["tip_chainage"]), track["y"]
        if abs(tx-sx) < 1e-8:
            raise ValueError(f"Overrun on {overrun['track']} has no visible chainage extent.")
        line([(sx, y), (tx, y)], "KEY_PLAN_OVERRUN")
        exterior = 1 if tx > sx else -1
        bar, cap, r = font*.65, font*.5, font*.22
        line([(tx+exterior*cap, y+bar), (tx, y+bar), (tx, y-bar),
              (tx+exterior*cap, y-bar)], "KEY_PLAN_DEAD_END")
        polygon([(sx-r, y), (sx, y+r), (sx+r, y), (sx, y-r)], "KEY_PLAN_SRJ")
        scene.overruns.append(dict(**overrun, x_srj=sx, x_tip=tx, y=y))

    # Key-plan drafting convention from the reference: DN points right and UP
    # left, repeated outside the yard at both ends of each main line.
    for track in scene.tracks:
        direction = track.get("direction", "").upper()
        if direction not in ("UP", "DN", "UP/DN", "BOTH"):
            continue
        two_way = direction in ("UP/DN", "BOTH")
        markers = [("DN", track["y"]+font*1.7), ("UP", track["y"]-font*1.7)] if two_way else [(direction, track["y"])]
        for side, ax, bx in (("left", w*.025, w*.10), ("right", w*.90, w*.975)):
            for designation, y in markers:
                tail, head = (bx, ax) if designation == "UP" else (ax, bx)
                arrow(tail, y, head, y, min(font*.8, (bx-ax)*.15), layer="KEY_PLAN_DIRECTION")
                caption = f"{designation} MAIN LINE"
                rows = [caption] if len(caption)*font*.72*.75 <= w*.10 else [designation, "MAIN LINE"]
                for index, row in enumerate(rows):
                    label(row, (ax+bx)/2, y+font*(.85+(len(rows)-1-index)*1.1),
                          w*.10, font*.72, move=False, layer="KEY_PLAN_DIRECTION_TEXT")
                scene.directions.append(dict(track=track["name"], direction=designation, side=side,
                                             x_tail=tail, x_head=head, y=y))

    for building in snapshot["buildings"]:
        platform = next((p for p in scene.platforms if p["name"] == building["platform"]), None)
        if platform is None:
            continue
        x = n.x(building["chainage"])
        bw = max(w*.014, (building["length_m"] / (snapshot["end"]-snapshot["start"])) * (w-2*options.padding_x))
        bh = n.step*.35
        above = building["offset"] >= platform["offset"]
        y0 = platform["y1"] if above else platform["y0"]-bh
        rectangle(x-bw/2, y0, x+bw/2, y0+bh, "KEY_PLAN_STATION")
        # Building captions occupy the header; footprints stay beside their platform.

    for bridge in snapshot["bridges"]:
        x = n.x(bridge["chainage"])
        connected = [p for p in scene.platforms if p["name"] in bridge["platforms"]]
        lo = min((p["y0"] for p in connected), default=min(n.levels.values())-n.gap)
        hi = max((p["y1"] for p in connected), default=max(n.levels.values())+n.gap)
        rectangle(x-font*.35, lo, x+font*.35, hi, "KEY_PLAN_BRIDGE")
        label(bridge.get("label", bridge["kind"]), x, hi+font*1.2, w*.12, font*.75)

    stations = snapshot["stations"] or [dict(name=b["name"], chainage=b["chainage"],
        chainage_m=snapshot["start_chainage_m"]+b["chainage"]) for b in snapshot["buildings"]]
    for station in stations:
        x = n.x(station["chainage"])
        line([(x, h*.29), (x, h*.82)], "KEY_PLAN_STATION_REFERENCE")
        line([(x, h*.82), (x, h*.875), (x+w*.018, h*.85), (x, h*.84)], "KEY_PLAN_SYMBOL")
    heading = options.station_caption or " / ".join(s["name"] for s in stations)
    if not heading:
        heading = "FINALIZED STATION YARD"
    if stations:
        heading += " | " + ", ".join(f"CH:{s['chainage_m']:.2f}m" for s in stations)
    # A bounded two-line header leaves a dedicated region for the north indicator.
    capacity = max(24, int(w*.72/(font*.75)))
    rows = textwrap.wrap(heading, width=capacity)
    if len(rows) > 2:
        raise ValueError("Station caption is too long for the key-plan header. Shorten the caption or widen the container.")
    for i, row in enumerate(rows):
        label(row, w*.44, h*.92-i*font*1.8, w*.72, font, move=False)
    for text, x, direction in ((options.left_destination, w*.07, -1),
                               (options.right_destination, w*.93, 1)):
        if text:
            rows = textwrap.wrap(f"TO {text}", width=max(10, int(w*.12/(font*.75))))
            if len(rows) > 3:
                raise ValueError("Destination caption is too long. Shorten it or widen the container.")
            direction_top = max((t["y"]+t["height"]*.65 for t in scene.texts
                                 if t["layer"] == "KEY_PLAN_DIRECTION_TEXT"), default=h*.48)
            arrow_y = max(h*.53, direction_top+font*2)
            for i, row in enumerate(rows):
                label(row, x, arrow_y+font*(2+(len(rows)-1-i)*1.5), w*.12, font*.8, move=False)
            arrow(x-direction*w*.04, arrow_y, x+direction*w*.04, arrow_y, font*1.3)
    angle = options.north_angle if options.north_angle is not None else snapshot.get("north_angle")
    if angle is not None:
        a = math.radians(angle)
        cx, cy, radius = w*.92, h*.89, h*.045
        arrow(cx-radius*math.cos(a), cy-radius*math.sin(a),
              cx+radius*math.cos(a), cy+radius*math.sin(a), font*1.5)
        label("N (REF)", cx, cy-radius-font, w*.12, font*.8, move=False)
    # Reject overflow rather than clipping or silently changing engineering data.
    for item in scene.lines + scene.polygons:
        if any(not (0 <= x <= w and 0 <= y <= h) for x, y in item["points"]):
            raise ValueError("Key-plan geometry exceeds its container. Use a larger layout or split the yard.")
    return scene
