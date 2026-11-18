"""Map real chainages to X and ordered track levels to schematic Y."""


class Normalizer:
    def __init__(self, snapshot, options):
        self.options = options
        self.start, self.end = snapshot["start"], snapshot["end"]
        if self.end <= self.start:
            raise ValueError("The finalized yard has no usable chainage extent.")
        ordered = sorted(snapshot["tracks"], key=lambda t: (t["offset"], t["name"]))
        if not ordered:
            raise ValueError("The finalized ESP contains no tracks.")
        self.step = options.track_height / (len(ordered) + 1)
        if min(options.font, self.step*.24) < 1.2:
            raise ValueError("Too many tracks for a legible key plan. Increase container height or split the yard into separate key plans.")
        self.levels = {t["name"]: options.track_bottom + (i + 1) * self.step
                       for i, t in enumerate(ordered)}
        self.thickness = self.step * (7 / 15)
        self.gap = self.step * (2 / 15)

    def x(self, chainage):
        return self.options.padding_x + (chainage - self.start) / (self.end - self.start) * (
            self.options.width - 2 * self.options.padding_x)

