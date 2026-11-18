"""Resolved overrun anchors carried by their existing DXF CAL labels."""

APPID = "ESP_OVERRUN"


def attach_overrun(label, track, srj, tip, length_m, at_start):
    if APPID not in label.doc.appids:
        label.doc.appids.new(APPID)
    label.set_xdata(APPID, [
        (1000, str(track)), (1070, int(at_start)),
        (1011, (float(srj[0]), float(srj[1]), 0)),
        (1011, (float(tip[0]), float(tip[1]), 0)),
        (1040, float(length_m)),
    ])


def resolved_overruns(doc):
    for entity in doc.modelspace().query('TEXT[layer=="OVER_RUN"]'):
        if not entity.has_xdata(APPID):
            continue
        tags = entity.get_xdata(APPID)
        points = [tag.value for tag in tags if tag.code == 1011]
        yield dict(track=next(tag.value for tag in tags if tag.code == 1000),
                   at_start=bool(next(tag.value for tag in tags if tag.code == 1070)),
                   srj=points[0], tip=points[1],
                   length_m=float(next(tag.value for tag in tags if tag.code == 1040)))
