"""MAIN-line direction defaults shared with the ESP drawing convention."""


def resolved_main_directions(config, tracks):
    mains = [name for name in tracks if name == "MAIN_LINE" or name.startswith("MAIN_LINE_")]
    explicit = {spec.name: str(getattr(spec, "direction", "")).upper()
                for spec in getattr(config, "additional_lines", []) or []}
    explicit.update({name: str(value).upper() for name, value in
                     (getattr(config, "main_directions", None) or {}).items()})
    result = {}
    for index, name in enumerate(mains):
        default = "UP/DN" if len(mains) == 1 else "UP" if index == 0 else "DN"
        value = explicit.get(name) or default
        result[name] = "UP/DN" if value in ("BOTH", "UP/DN") else value if value in ("UP", "DN") else default
    return result
