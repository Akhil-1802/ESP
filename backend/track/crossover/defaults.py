"""Crossover spec conversion, DEFAULT preset chainages and target inference."""

from __future__ import annotations

from typing import Sequence

from common.constants import CHAINAGE_TOL_M
from track.crossover.footprints import main_track_anchors  # re-export for legacy imports
from track.crossover.geometry import (
    compute_crossover_params,
    get_required_separation,
    normalize_direction,
)
from track.crossover.models import CrossoverRequest, CrossoverResult

RESTRICT_TOL_M = 1e-9


def requests_from_specs(specs) -> list[CrossoverRequest]:
    """Convert legacy CrossoverSpec list into generic CrossoverRequests."""
    out: list[CrossoverRequest] = []
    for i, spec in enumerate(specs, 1):
        cid = getattr(spec, "id", None) or f"C{i}"
        raw_dir = getattr(spec, "direction", None) or "FORWARD"
        raw_place = getattr(spec, "placement", None)
        raw_mode = getattr(spec, "position_mode", None)
        ch = getattr(spec, "from_chainage_m", None)
        if isinstance(ch, str) and ch.strip().upper() == "AUTO":
            ch = None
            raw_mode = "AUTO"
        out.append(
            CrossoverRequest(
                id=str(cid),
                from_track=spec.from_track,
                to_track=spec.to_track,
                chainage=ch,
                direction=raw_dir,
                turnout=getattr(spec, "turnout", None),
                placement=raw_place,
                position_mode=raw_mode or ("AUTO" if ch is None else "FIXED"),
                metadata={
                    "spec_index": i,
                    "auto_anchor_id": getattr(spec, "auto_anchor_id", None),
                },
            )
        )
    return out


def _fmt_num(value, spec: str) -> str:
    """Format a possibly-None debug number (None -> '?')."""
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return "?"


def format_debug_block(result: CrossoverResult) -> str:
    """One-crossover debug block (integrates with --verbose style output)."""
    d = result.debug_dict()
    n_ratio = d["N"] if d["N"] is not None else "?"
    return (
        f"Crossover {d['id']}: {d['from_track']} -> {d['to_track']} "
        f"ch={_fmt_num(d['chainage'], '.3f')}m dir={d['direction']} "
        f"turnout={d['turnout'] or '?'} TC={_fmt_num(d['TC_m'], '.3f')}m N={n_ratio} "
        f"F={_fmt_num(d['F_deg'], '.4f')}deg A={_fmt_num(d['A_mm'], '.0f')}mm "
        f"OL={_fmt_num(d['OL_mm'], '.0f')}mm [{_fmt_num(d['start'], '.2f')}, {_fmt_num(d['end'], '.2f')}] "
        f"{d['status']}"
    )


def infer_target_track(
    from_track: str,
    track_metas: Sequence[tuple],
) -> str:
    """Propose the default target track for interactive input."""
    names = [m[0] for m in track_metas]
    is_main = from_track == "MAIN_LINE" or from_track.startswith("MAIN_LINE")
    if not is_main:
        if "MAIN_LINE" in names:
            return "MAIN_LINE"
        mains = [
            n for n in names if n == "MAIN_LINE" or n.startswith("MAIN_LINE")
        ]
        if mains:
            return mains[0]
        raise ValueError(
            f"Cannot infer a target track for {from_track!r}: "
            f"no MAIN line is configured."
        )
    cands = [
        m
        for m in track_metas
        if m[0] != from_track
        and not (m[0] == "MAIN_LINE" or m[0].startswith("MAIN_LINE"))
    ]
    if not cands:
        raise ValueError(
            f"Cannot infer a target track for {from_track!r}: configure "
            f"at least one LOOP or PROPOSED line first."
        )

    def _spacing(meta) -> float:
        try:
            return float(meta[1]) if meta[1] is not None else 1e9
        except (TypeError, ValueError, IndexError):
            return 1e9

    return min(cands, key=_spacing)[0]


def auto_candidates_for_main(
    new_direction: str,
    anchors: list[dict],
) -> list[dict]:
    """Ordered AUTO START candidates on the starting track."""
    new_dir = normalize_direction(new_direction)
    out: list[dict] = []
    for anc in anchors or []:
        try:
            required = float(get_required_separation(new_dir, anc["direction"]))
        except (ValueError, KeyError, TypeError):
            continue
        try:
            base = float(anc["pos"])
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "candidate": base + required,
                "anchor_pos": base,
                "required": required,
                "anchor_id": anc.get("id"),
                "anchor_kind": anc.get("kind"),
                "anchor_direction": anc.get("direction"),
                "side": "AHEAD",
            }
        )
        out.append(
            {
                "candidate": base - required,
                "anchor_pos": base,
                "required": required,
                "anchor_id": anc.get("id"),
                "anchor_kind": anc.get("kind"),
                "anchor_direction": anc.get("direction"),
                "side": "BEHIND",
            }
        )
    return out


auto_candidates_for_track = auto_candidates_for_main


def compute_default_chainages(
    loop1_c1: float,
    loop1_c2: float,
    turnout,
    tracks: dict,
    loop1: str = "LOOP_1",
    loop2: str = "LOOP_2",
    main: str = "MAIN_LINE",
    extents: dict | None = None,
    main_length: float | None = None,
) -> dict:
    """Compute the DEFAULT 4-crossover chainages (centre-ward, 54 m)."""
    extents = dict(extents or {})
    c1, c2 = float(loop1_c1), float(loop1_c2)
    if not c2 > c1:
        raise ValueError(
            f"DEFAULT preset needs LOOP_1 C1 < C2, got [{c1:.2f}, {c2:.2f}]."
        )

    probe1 = CrossoverRequest(
        id="C1",
        from_track=loop1,
        to_track=main,
        chainage=c1,
        direction="REVERSE",
        turnout=turnout,
        placement=None,
        position_mode="FIXED",
    )
    try:
        p1 = compute_crossover_params(probe1, c1, tracks, extents)
    except Exception as exc:
        raise ValueError(
            f"DEFAULT C1 (LOOP_1 {c1:.2f} REVERSE) does not fit: {exc}"
        ) from exc
    ol1, e1 = float(p1["ol_m"]), float(p1["to_main"])

    probe2 = CrossoverRequest(
        id="C2",
        from_track=loop1,
        to_track=main,
        chainage=c2,
        direction="FORWARD",
        turnout=turnout,
        placement=None,
        position_mode="FIXED",
    )
    try:
        p2 = compute_crossover_params(probe2, c2, tracks, extents)
    except Exception as exc:
        raise ValueError(
            f"DEFAULT C2 (LOOP_1 {c2:.2f} FORWARD) does not fit: {exc}"
        ) from exc
    ol2, e2 = float(p2["ol_m"]), float(p2["to_main"])

    required = float(get_required_separation("FORWARD", "REVERSE"))

    def _second_fits(track: str, second: float) -> bool:
        ext = extents.get(track)
        if ext is None:
            if main_length is not None and not (
                -CHAINAGE_TOL_M <= second <= main_length + CHAINAGE_TOL_M
            ):
                return False
            return True
        return ext[0] - CHAINAGE_TOL_M <= second <= ext[1] + CHAINAGE_TOL_M

    s3 = None
    ol3_m: float | None = None
    for cand in (e1 + required, e1 - required):
        probe = CrossoverRequest(
            id="C3",
            from_track=main,
            to_track=loop2,
            chainage=cand,
            direction="FORWARD",
            turnout=turnout,
            placement=None,
            position_mode="FIXED",
        )
        try:
            pp = compute_crossover_params(probe, float(cand), tracks, extents)
        except Exception:
            continue
        if _second_fits(loop2, float(pp["to_main"])):
            s3, ol3_m = float(cand), float(pp["ol_m"])
            break
    if s3 is None:
        raise ValueError(
            f"DEFAULT C3 (MAIN -> {loop2} FORWARD, 54 m from LOOP_1 start "
            f"ending {e1:.2f} m) does not fit: neither {e1 + required:.2f} m "
            f"nor {e1 - required:.2f} m keeps the second SRJ inside {loop2}."
        )

    s4 = None
    ol4_m: float | None = None
    for cand in (e2 - required, e2 + required):
        probe = CrossoverRequest(
            id="C4",
            from_track=main,
            to_track=loop2,
            chainage=cand,
            direction="REVERSE",
            turnout=turnout,
            placement=None,
            position_mode="FIXED",
        )
        try:
            pp = compute_crossover_params(probe, float(cand), tracks, extents)
        except Exception:
            continue
        if _second_fits(loop2, float(pp["to_main"])):
            s4, ol4_m = float(cand), float(pp["ol_m"])
            break
    if s4 is None:
        raise ValueError(
            f"DEFAULT C4 (MAIN -> {loop2} REVERSE, 54 m from LOOP_1 end "
            f"ending {e2:.2f} m) does not fit: neither {e2 - required:.2f} m "
            f"nor {e2 + required:.2f} m keeps the second SRJ inside {loop2}."
        )
    return {
        "c1": c1,
        "c2": c2,
        "c3": float(s3),
        "c4": float(s4),
        "e1": float(e1),
        "e2": float(e2),
        "ol1_m": float(ol1),
        "ol2_m": float(ol2),
        "ol3_m": float(ol3_m or 0.0),
        "ol4_m": float(ol4_m or 0.0),
        "required_m": float(required),
    }


__all__ = [
    "RESTRICT_TOL_M",
    "auto_candidates_for_main",
    "auto_candidates_for_track",
    "compute_default_chainages",
    "format_debug_block",
    "infer_target_track",
    "main_track_anchors",
    "requests_from_specs",
]
