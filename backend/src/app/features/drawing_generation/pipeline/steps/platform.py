"""Platform generation: polygons, overlap checks, writing."""

from __future__ import annotations

from ...domain.geometry.operations import (
    nearest_point_on_alignment,
    point_at_chainage,
    polygon_contains,
    polygons_overlap,
    polyline_length,
)
from ...domain.platform.config import PlatformType as _PlatformType
from ...domain.platform.generator import PlatformGenerator
from ...domain.platform.track import Track, _extract_points
from ...domain.station.builder import _polygon_area
from ...formats.dxf.platform_io import write_platform as _write_platform
from ...formats.dxf.tracks import _add_track_label
from .base import PipelineStep

__all__ = [
    "PlatformStep",
    "_orient2d",
    "_segments_properly_cross",
    "_point_strictly_inside",
    "_ring_edges",
    "_footprints_strict_overlap",
]


def _orient2d(a, b, c) -> float:
    """Cross product (b - a) x (c - a); sign = turn direction."""
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_properly_cross(a, b, c, d, eps: float = 1e-9) -> bool:
    """True only for a genuine crossing (touching/collinear never counts)."""
    o1, o2 = _orient2d(a, b, c), _orient2d(a, b, d)
    o3, o4 = _orient2d(c, d, a), _orient2d(c, d, b)
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and (
        (o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps)
    )


def _point_strictly_inside(outline, pt, eps: float = 1e-6) -> bool:
    """True when pt lies inside outline with clearance from its boundary."""
    try:
        if nearest_point_on_alignment(outline, pt).distance <= eps:
            return False
    except Exception:
        pass
    try:
        return bool(polygon_contains(outline, pt))
    except Exception:
        return False


def _ring_edges(ring):
    """De-duplicated closed edges of a (possibly closed) polygon ring."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return []
    return list(zip(pts, pts[1:] + pts[:1]))


def _footprints_strict_overlap(first, second) -> bool:
    """True when two polygons genuinely overlap (touching is allowed)."""
    edges_first = _ring_edges(first)
    edges_second = _ring_edges(second)
    if not edges_first or not edges_second:
        return False
    pts_first = [a for a, _b in edges_first]
    pts_second = [a for a, _b in edges_second]
    if any(_point_strictly_inside(first, p) for p in pts_second):
        return True
    if any(_point_strictly_inside(second, p) for p in pts_first):
        return True
    return any(
        _segments_properly_cross(a, b, c, d)
        for a, b in edges_first
        for c, d in edges_second
    )


class PlatformStep(PipelineStep):
    """Pipeline step: Platform generation: polygons, overlap checks, writing."""

    def _platform_polygons(self, doc, layer: str):
        """Extract platform polygons from a DXF layer."""
        def extract():
            polygons = []
            for entity in doc.modelspace():
                if entity.dxf.layer != layer or entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                    continue
                points = _extract_points(entity)
                if len(points) >= 3:
                    polygons.append(points)
            return sorted(polygons, key=_polygon_area, reverse=True)
        return self._cached_polygons(doc, layer, extract)

    def _check_platform_overlap(self, doc, outline, platform_layer: str) -> None:
        """Verify that a new platform doesn't overlap existing platforms."""
        for entity in doc.modelspace():
            if entity.dxf.layer == platform_layer or not entity.dxf.layer.startswith("PLATFORM_"):
                continue
            if entity.dxftype() not in ("LWPOLYLINE", "POLYLINE"):
                continue
            if polygons_overlap(outline, _extract_points(entity)):
                raise ValueError(f"Platform {platform_layer!r} overlaps an existing platform")

    def _check_platform_covers_track(self, outline, platform_layer: str, tracks) -> None:
        """Reject a platform drawn across any track centreline."""
        for name, pts in (tracks or {}).items():
            line = [(float(p[0]), float(p[1])) for p in pts]
            if len(line) < 2 or len(outline) < 3:
                continue
            edges = _ring_edges(outline)
            hit = any(_point_strictly_inside(outline, p) for p in line)
            if not hit:
                segments = list(zip(line, line[1:]))
                hit = any(
                    _segments_properly_cross(a, b, c, d)
                    for a, b in segments
                    for c, d in edges
                )
            if hit:
                raise ValueError(
                    f"Platform {platform_layer!r} covers track {name!r} - "
                    f"move it (side/clearance/width) so no track "
                    f"centreline passes through the platform."
                )

    def _check_platform_stair_overlap(self, outline, stair_outlines, platform_layer: str) -> None:
        """Reject stair footprints colliding with other platforms."""
        for layer, prev_outline, prev_stairs in (
            getattr(self, "_platform_footprints", None) or []
        ):
            if polygons_overlap(outline, prev_outline):
                raise ValueError(
                    f"Platform {platform_layer!r} overlaps {layer!r} - "
                    f"move it so the outlines do not intersect."
                )
            for rect in list(prev_stairs or []):
                if _footprints_strict_overlap(outline, rect):
                    raise ValueError(
                        f"Platform {platform_layer!r} overlaps the stairs "
                        f"of {layer!r} - move it so it clears them."
                    )
            for mine in list(stair_outlines or []):
                if _footprints_strict_overlap(mine, prev_outline):
                    raise ValueError(
                        f"Platform {platform_layer!r} stairs overlap "
                        f"{layer!r} - move it so they clear it."
                    )
                for rect in list(prev_stairs or []):
                    if _footprints_strict_overlap(mine, rect):
                        raise ValueError(
                            f"Platform {platform_layer!r} stairs overlap "
                            f"the stairs of {layer!r}."
                        )

    def _resolve_platform_center(
        self, platform_cfg, tracks: dict | None = None
    ) -> None:
        """Resolve center_chainage along the platform's track from the referenced station marker."""
        station_markers = getattr(self.config, "station_markers", None) or []
        if not station_markers:
            return

        stn_idx = getattr(platform_cfg, "station_index", None)
        if stn_idx is None:
            if len(station_markers) == 1:
                stn_idx = 0
            else:
                return

        if not (0 <= stn_idx < len(station_markers)):
            return

        # Obtain main track points
        main_pts = (tracks or {}).get("MAIN_LINE")
        if not main_pts and hasattr(self, "config") and getattr(self.config, "output_dxf", None):
            try:
                doc = self._load_document()
                main_pts = Track.from_dxf(doc, layer_name="MAIN_LINE").points
            except Exception:
                main_pts = None

        if not main_pts:
            return

        cleaned_main = [(float(p[0]), float(p[1])) for p in main_pts]
        total_len = polyline_length(cleaned_main)
        if total_len <= 0:
            return

        start_ch_m = getattr(self, "_get_start_chainage_meters", None)
        if callable(start_ch_m):
            start_m = start_ch_m()
        else:
            start_m = 0.0
            sk = getattr(self.config, "start_km", None)
            sm = getattr(self.config, "start_m", None)
            if sk is not None and str(sk).strip() != "":
                try:
                    sk_f = float(sk)
                    sm_f = float(sm) if sm is not None and str(sm).strip() != "" else 0.0
                    sign = -1.0 if (sk_f < 0 or str(sk).strip().startswith("-")) else 1.0
                    start_m = sign * (abs(sk_f) * 1000.0 + abs(sm_f))
                except (ValueError, TypeError):
                    start_m = 0.0

        parse_fn = getattr(self, "_parse_alignment_station_markers", None)
        if callable(parse_fn):
            parsed = parse_fn(cleaned_main, start_m, total_len)
        else:
            parsed = []

        if not parsed or stn_idx >= len(parsed):
            stn = station_markers[stn_idx]
            km_val = stn.get("km") if isinstance(stn, dict) else getattr(stn, "km", None)
            m_val = stn.get("m") if isinstance(stn, dict) else getattr(stn, "m", None)
            km_has = km_val is not None and str(km_val).strip() != ""
            m_has = m_val is not None and str(m_val).strip() != ""
            try:
                km_f = float(km_val) if km_has else 0.0
                m_f = float(m_val) if m_has else 0.0
                sign = -1.0 if (km_f < 0 or (km_has and str(km_val).strip().startswith("-"))) else 1.0
                stn_ch = sign * (abs(km_f) * 1000.0 + abs(m_f))
            except Exception:
                stn_ch = 0.0
            d = stn_ch - start_m if (stn_ch >= start_m) else stn_ch
            stn_d = max(0.0, min(d, total_len))
        else:
            stn_d = parsed[stn_idx]["d"]

        stn_pt = point_at_chainage(cleaned_main, stn_d).point

        # Target track for this platform
        track_layer = platform_cfg.track_layer or "MAIN_LINE"
        target_pts = (tracks or {}).get(track_layer)
        if not target_pts and hasattr(self, "config") and getattr(self.config, "output_dxf", None):
            try:
                doc = self._load_document()
                target_pts = Track.from_dxf(doc, layer_name=track_layer).points
            except Exception:
                target_pts = None

        if not target_pts:
            target_pts = cleaned_main

        cleaned_target = [(float(p[0]), float(p[1])) for p in target_pts]
        proj = nearest_point_on_alignment(cleaned_target, stn_pt)
        platform_cfg.center_chainage = proj.chainage

    def _calculate_fob_widenings(self, platform_cfg, tracks) -> list[dict]:
        """Compute localized extra-width rectangular zones for side platforms where an FOB arm is placed."""
        plat_type = getattr(platform_cfg, "platform_type", "SIDE")
        plat_type_str = getattr(plat_type, "value", str(plat_type)).upper()
        if plat_type_str not in ("SIDE", "PLATFORMTYPE.SIDE"):
            return []

        plat_layer = getattr(platform_cfg, "output_layer", "")
        fobs = getattr(self.config, "fobs", None) or []
        if not fobs or not tracks:
            return []

        clr = float(getattr(platform_cfg, "clearance", 1.68) or 1.68)
        std_w = float(getattr(platform_cfg, "platform_width", 7.0) or 7.0)
        std_far_offset = clr + std_w

        plat_track_name = platform_cfg.track_layer or "MAIN_LINE"
        plat_track_pts = tracks.get(plat_track_name)
        if not plat_track_pts:
            return []
        cleaned_plat_track = [(float(p[0]), float(p[1])) for p in plat_track_pts]
        plat_track_len = polyline_length(cleaned_plat_track)

        widenings = []
        for fob in fobs:
            connected = getattr(fob, "platforms", None) or []
            norm_conn = [str(p).strip().upper().replace(" ", "_") for p in connected]
            norm_layer = plat_layer.strip().upper().replace(" ", "_")
            if norm_conn and norm_layer not in norm_conn:
                continue

            arms = getattr(fob, "arms", None) or {}
            arm_spec = None
            if isinstance(arms, dict):
                arm_spec = arms.get(plat_layer)
                if arm_spec is None:
                    arm_spec = arms.get(plat_layer.replace("_", " "))
                if arm_spec is None:
                    for k, v in arms.items():
                        if str(k).strip().upper().replace(" ", "_") == norm_layer:
                            arm_spec = v
                            break

            if arms and arm_spec is None:
                continue

            fob_w = max(3.0, float(getattr(fob, "width", 3.0) or 3.0))
            arm_w = max(3.0, fob_w)
            if isinstance(arm_spec, dict) and arm_spec.get("width"):
                try:
                    arm_w = max(3.0, float(arm_spec["width"]))
                except (ValueError, TypeError):
                    pass

            # Distance from track centerline to outer edge of FOB arm:
            # IRS SOD clearance for side platform is 5.33m from track centerline.
            # Arm width is arm_w (>= 3.0m).
            # FOB arm outer edge is at 5.33 + arm_w from track centerline.
            fob_arm_outer_dist = 5.33 + arm_w

            # Only widen if the FOB arm actually extends beyond the standard platform width
            if std_far_offset < fob_arm_outer_dist:
                widened_offset = round(fob_arm_outer_dist + 1.0, 2)
                extra_width = round(widened_offset - std_far_offset, 2)

                # Determine FOB reference chainage
                from ...domain.bridges.fob.deck import resolve_fob_chainage

                fob_ch = resolve_fob_chainage(
                    fob,
                    tracks,
                    station_requests=getattr(self.config, "stations", None),
                    station_markers=getattr(self.config, "station_markers", None),
                )

                ref_track_name = getattr(fob, "reference_track", "MAIN_LINE") or "MAIN_LINE"
                ref_track_pts = tracks.get(ref_track_name) or tracks.get("MAIN_LINE")
                if not ref_track_pts:
                    continue
                cleaned_ref_track = [(float(p[0]), float(p[1])) for p in ref_track_pts]
                fob_pt = point_at_chainage(cleaned_ref_track, fob_ch).point

                # Project FOB 2D point onto the platform's target track
                proj = nearest_point_on_alignment(cleaned_plat_track, fob_pt)
                plat_fob_ch = proj.chainage

                half_fob_w = fob_w / 2.0

                if arm_spec and isinstance(arm_spec, dict):
                    arm_len = float(arm_spec.get("length", 15.0) or 15.0)
                    arm_side = str(arm_spec.get("side", "LEFT") or "LEFT").upper()
                    if arm_side == "LEFT":
                        fob_min_ch = plat_fob_ch - half_fob_w - arm_len
                        fob_max_ch = plat_fob_ch + half_fob_w
                    else:
                        fob_min_ch = plat_fob_ch - half_fob_w
                        fob_max_ch = plat_fob_ch + half_fob_w + arm_len
                else:
                    fob_min_ch = plat_fob_ch - half_fob_w
                    fob_max_ch = plat_fob_ch + half_fob_w

                # User requirement:
                # "from 1m before the FOB arm and make a line above or down depending on the side where we are making FOB,
                #  then we will push that line required width + 1m so that to have little gap on the width
                #  and the extended platform will have length till the end of the FOB on that side + 1m
                #  and then we will connect it with the old platform"
                s1 = fob_min_ch - 1.0
                s2 = fob_max_ch + 1.0

                p_start = platform_cfg.resolved_start_chainage(plat_track_len)
                p_end = platform_cfg.resolved_end_chainage(plat_track_len)
                s1 = max(p_start, s1)
                s2 = min(p_end, s2)

                if s2 > s1 + 0.5:
                    widenings.append({
                        "start_chainage": s1,
                        "end_chainage": s2,
                        "widened_offset": widened_offset,
                        "extra_width": extra_width,
                    })

        return widenings

    def _generate_platforms(self, tracks=None) -> None:
        """Generate all platforms (outlines, stairs and tracks validated)."""
        self._platform_footprints = []
        for request in self.config.platforms:
            platform_cfg = request.config
            platform_cfg.source_dxf = self.config.output_dxf
            platform_cfg.output_dxf = self.config.output_dxf

            if platform_cfg.center_on_track and platform_cfg.center_chainage is None:
                self._resolve_platform_center(platform_cfg, tracks)

            if getattr(platform_cfg, "fob_widenings", None) is None:
                widenings = self._calculate_fob_widenings(platform_cfg, tracks)
                if widenings:
                    platform_cfg.fob_widenings = widenings

            result, doc = PlatformGenerator(platform_cfg, track_points=tracks).build(document=self._load_document() if self._active_document() is not None else None)
            _write_platform(doc, result, platform_cfg)
            outline = [(p[0], p[1]) for p in result.outline]
            stair_outlines = [
                [(p[0], p[1]) for p in stair.outline]
                for stair in (getattr(result, "stairs", None) or [])
            ]
            self._check_platform_overlap(doc, outline, platform_cfg.output_layer)
            self._check_platform_stair_overlap(
                outline, stair_outlines, platform_cfg.output_layer
            )
            self._check_platform_covers_track(
                outline, platform_cfg.output_layer, tracks
            )
            self._platform_footprints.append(
                (platform_cfg.output_layer, outline, stair_outlines)
            )
            if hasattr(self, "_key_plan_platform_results"):
                self._key_plan_platform_results.append((request, result))
            if (
                platform_cfg.platform_type == _PlatformType.SIDE
                and getattr(result, "far_edge", None)
            ):
                self._fencing_jobs.append(
                    (platform_cfg.output_layer, result.far_edge, outline, 0.0)
                )
            self._save_document(doc)
            self.platform_layers.append(platform_cfg.output_layer)

        try:
            doc = self._load_document()
            for entity in list(doc.modelspace()):
                try:
                    if entity.dxf.layer == "TRACK_LABELS":
                        doc.modelspace().delete_entity(entity)
                except Exception:
                    pass
            for name, points in tracks.items():
                display = name.replace("_", " ").title()
                if name.upper() == "MAIN_LINE":
                    display = "MAIN LINE"
                _add_track_label(doc, display, points, "TRACK_LABELS", color=1, height=1.0)
            self._save_document(doc)
        except Exception:
            pass
