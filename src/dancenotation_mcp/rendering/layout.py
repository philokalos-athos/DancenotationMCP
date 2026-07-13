from __future__ import annotations

from xml.sax.saxutils import escape

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.time_signatures import (
    DEFAULT_BEATS_PER_MEASURE,
    beats_for_measure,
    build_measure_beats_map,
)


# ── Constants ──────────────────────────────────────────────────────────

MARGIN_X = 28
TOP_MARGIN = 72
BOTTOM_MARGIN = 40
HEADER_HEIGHT = 54
BEAT_HEIGHT = 72
MIN_SYMBOL_HEIGHT = 26
LANE_GAP = 18
LANE_WIDTH = 34
ANNOTATION_WIDTH = 14
ANNOTATION_GAP = 5
COLLISION_OFFSET = 12
SYSTEM_MEASURE_CAPACITY = 4
SYSTEM_GAP_Y = 110

BODY_LANES = [
    "left_arm",
    "left_leg",
    "torso",
    "right_leg",
    "right_arm",
]

COLUMN_LANES = [
    "support",
    "direction",
    "path",
    "bow",
    "pin",
    "gesture",
    "body",
    "flexion",
    "foothook",
    "digit",
    "turn",
    "travel",
    "jump",
    "floor",
    "repeat",
    "dynamic",
    "adlib",
    "music",
    "motif",
    "surface",
    "space",
    "separator",
    "quality",
    "level",
    "timing",
]

DIRECTION_GLYPH = {
    "forward": "▲",
    "backward": "▼",
    "left": "◀",
    "right": "▶",
    "diagonal_forward_left": "◢",
    "diagonal_forward_right": "◣",
    "diagonal_backward_left": "◥",
    "diagonal_backward_right": "◤",
    "place": "●",
}

LEVEL_STYLES = {
    "high": {"fill": "#ffffff", "label": "High"},
    "middle": {"fill": "url(#level-middle-fill)", "label": "Middle"},
    "low": {"fill": "#2f3542", "label": "Low"},
}

SPECIALIZED_COLUMNS = {"path", "pin", "repeat", "music", "separator", "turn", "jump", "motif", "surface", "space"}
ATTACHABLE_COLUMNS = {"pin", "surface", "music", "repeat", "quality", "level", "timing"}
ROUTING_KIND_PRIORITY = {"bridge": 0, "span": 1, "attachment": 2}
BUNDLE_ATTACHMENT_FAMILIES = {"pin", "surface", "music"}


# ── Geometry helpers ───────────────────────────────────────────────────

def symbol_time(symbol: dict, beats_map: dict[int, float] | None = None) -> tuple[float, float]:
    timing = symbol.get("timing", {})
    measure = max(int(timing.get("measure", 1)), 1)
    beat = float(timing.get("beat", 1.0))
    duration = max(float(timing.get("duration_beats", 1.0)), 0.25)
    bm = beats_map or {}
    start = sum(beats_for_measure(m, bm) for m in range(1, measure)) + (beat - 1.0)
    end = start + duration
    return start, end


def build_lane_positions(staff_left: float) -> dict[str, float]:
    order = BODY_LANES + COLUMN_LANES
    positions: dict[str, float] = {}
    x = staff_left + 26
    for lane in order:
        positions[lane] = x
        x += LANE_WIDTH + LANE_GAP
    return positions


def measure_count(symbols: list[dict], beats_map: dict[int, float] | None = None) -> int:
    if not symbols:
        return 1
    max_m = 1
    for s in symbols:
        timing = s.get("timing", {})
        m = max(int(timing.get("measure", 1)), 1)
        beat = float(timing.get("beat", 1.0))
        dur = max(float(timing.get("duration_beats", 1.0)), 0.25)
        bm = beats_map or {}
        bpm = beats_for_measure(m, bm)
        end_beat = beat + dur - 1.0
        extra = 0
        while end_beat > bpm:
            extra += 1
            end_beat -= beats_for_measure(m + extra, bm)
        max_m = max(max_m, m + extra)
    return max_m


def measure_top(measure: int, staff_top: float, beats_map: dict[int, float] | None = None) -> float:
    bm = beats_map or {}
    offset = sum(beats_for_measure(m, bm) * BEAT_HEIGHT for m in range(1, measure))
    return staff_top + offset


def measure_stack_pressure(symbols: list[dict], catalog: dict[str, dict], mc: int) -> dict[int, float]:
    pressure_by_measure: dict[int, float] = {m: 0.0 for m in range(1, mc + 1)}
    for m in range(1, mc + 1):
        slot_pressure: dict[float, float] = {}
        attachment_pressure = 0.0
        structural_pressure = 0.0
        for symbol in symbols:
            timing = symbol.get("timing", {})
            if max(int(timing.get("measure", 1)), 1) != m:
                continue
            spec = catalog.get(symbol.get("symbol_id", ""), {})
            column = spec.get("geometry", {}).get("staff_column", "")
            if column == "music" and bool(symbol.get("modifiers", {}).get("measure_header")):
                continue
            beat = round(float(timing.get("beat", 1.0)), 2)
            if column in {"quality", "level", "timing", "pin", "surface", "music"}:
                slot_pressure[beat] = slot_pressure.get(beat, 0.0) + 1.0
            if column in {"pin", "surface", "music"} and symbol.get("modifiers", {}).get("attach_to"):
                attachment_pressure += 1.0
            if column in {"repeat", "separator"}:
                slot_pressure[beat] = slot_pressure.get(beat, 0.0) + 0.5
                structural_pressure += 1.0
        pressure_by_measure[m] = max(slot_pressure.values(), default=0.0) + attachment_pressure + max(0.0, structural_pressure - 1.0)
    return pressure_by_measure


def measure_vertical_layout(symbols: list[dict], catalog: dict[str, dict], staff_top: float, mc: int) -> tuple[dict[int, float], dict[int, float]]:
    extra_gap_after: dict[int, float] = {m: 0.0 for m in range(1, mc + 1)}
    pressure_by_measure = measure_stack_pressure(symbols, catalog, mc)
    for m in range(1, mc + 1):
        pressure = pressure_by_measure.get(m, 0.0)
        if pressure >= 8.0:
            extra_gap_after[m] = min(120.0, 16.0 * (pressure - 7.0))
        if m < mc and m % SYSTEM_MEASURE_CAPACITY == 0:
            extra_gap_after[m] += SYSTEM_GAP_Y

    measure_tops: dict[int, float] = {}
    current_top = staff_top
    for m in range(1, mc + 1):
        measure_tops[m] = current_top
        current_top += (4 * BEAT_HEIGHT) + extra_gap_after.get(m, 0.0)
    return measure_tops, extra_gap_after


def measure_zone_y_offset(entry: dict, pressure: float) -> float:
    if pressure < 8.0:
        return 0.0
    family = entry_family(entry)
    zone_offsets = {
        "music": -14.0,
        "repeat": -18.0,
        "separator": -14.0,
        "pin": -4.0,
        "quality": -6.0,
        "level": 2.0,
        "surface": 6.0,
        "timing": 14.0,
    }
    return zone_offsets.get(family, 0.0)


def system_layout(mc: int, m_tops: dict[int, float], m_right_padding: dict[int, float], staff_left: float, lane_right: float) -> list[dict]:
    systems: list[dict] = []
    for system_index, start_m in enumerate(range(1, mc + 1, SYSTEM_MEASURE_CAPACITY), start=1):
        end_m = min(mc, start_m + SYSTEM_MEASURE_CAPACITY - 1)
        bottom = m_tops[end_m] + (4 * BEAT_HEIGHT)
        right_edge = max(lane_right + m_right_padding.get(m, 52.0) for m in range(start_m, end_m + 1))
        systems.append(
            {
                "index": system_index,
                "start_measure": start_m,
                "end_measure": end_m,
                "top": m_tops[start_m],
                "bottom": bottom,
                "right": right_edge,
            }
        )
    return systems


def entry_family(entry: dict) -> str:
    column = entry.get("column")
    if column:
        return column
    symbol_id = entry.get("symbol", {}).get("symbol_id", "")
    return symbol_id.split(".", 1)[0]


def preferred_attachment_side(source: dict, target: dict) -> str:
    modifiers = source.get("symbol", {}).get("modifiers", {})
    explicit_side = modifiers.get("attach_side")
    if explicit_side in {"left", "right"}:
        return explicit_side
    preferred_side = source.get("spec", {}).get("behavior", {}).get("preferred_anchor_side")
    if preferred_side in {"left", "right"}:
        return preferred_side
    return "right" if source["x"] > target["x"] else "left"


def measure_header_text(symbol: dict, spec: dict | None = None) -> str:
    behavior = (spec or {}).get("behavior", {})
    header_role = behavior.get("header_role")
    if header_role == "tempo" or symbol.get("symbol_id", "").endswith("tempo.mark"):
        return f'♩={symbol.get("modifiers", {}).get("tempo", 120)}'
    if header_role == "meter" or ".time." in symbol.get("symbol_id", ""):
        return symbol["symbol_id"].split(".time.", 1)[1].replace("_", "/")
    if header_role == "cadence" or symbol.get("symbol_id", "").endswith("cadence.mark"):
        return "cad"
    return symbol.get("symbol_id", "music").split(".")[-1].replace("_", "/")


def measure_header_layout(symbols: list[dict], catalog: dict[str, dict]) -> dict[int, dict[str, float]]:
    layout: dict[int, dict[str, float]] = {}
    for symbol in symbols:
        spec = catalog.get(symbol.get("symbol_id", ""), {})
        if not is_measure_header(symbol, spec):
            continue
        m = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        text = measure_header_text(symbol, spec)
        text_width = max(44.0, (len(text) * 6.6) + 16.0)
        entry = layout.setdefault(m, {"count": 0.0, "max_text_width": 44.0})
        entry["count"] += 1
        entry["max_text_width"] = max(entry["max_text_width"], text_width)
    return layout


def header_gutter_width(h_layout: dict[int, dict[str, float]]) -> float:
    if not h_layout:
        return 0.0
    max_band_width = max(entry["max_text_width"] + 12.0 for entry in h_layout.values())
    return max_band_width + 34.0


def measure_header_corridors(
    h_layout: dict[int, dict[str, float]],
    m_tops: dict[int, float] | float,
    staff_left: float,
) -> dict[int, dict[str, float]]:
    corridors: dict[int, dict[str, float]] = {}
    if isinstance(m_tops, (int, float)):
        st = float(m_tops)
        m_tops = {m: measure_top(m, st) for m in h_layout}
    for m, entry in h_layout.items():
        band_width = entry["max_text_width"] + 12.0
        band_x = staff_left - band_width - 4.0
        band_y = m_tops[m] + 4.0
        band_height = max(24.0, (float(entry["count"]) * 22.0) + 8.0)
        corridors[m] = {
            "left": band_x - 6.0,
            "right": staff_left + 24.0,
            "top": band_y - 6.0,
            "bottom": band_y + band_height + 6.0,
        }
    return corridors


def measure_right_padding(symbols: list[dict], catalog: dict[str, dict]) -> dict[int, float]:
    complexity: dict[int, float] = {}
    for symbol in symbols:
        m = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        spec = catalog.get(symbol.get("symbol_id", ""), {})
        column = spec.get("geometry", {}).get("staff_column", "")
        weight = 1.0
        if column in {"pin", "surface", "music", "repeat", "separator", "quality", "level", "timing"}:
            weight += 0.6
        if symbol.get("modifiers", {}).get("attach_to"):
            weight += 0.8
        if symbol.get("modifiers", {}).get("measure_header"):
            weight += 0.4
        if float(symbol.get("timing", {}).get("duration_beats", 1.0)) > 1.0:
            weight += 0.3
        complexity[m] = complexity.get(m, 0.0) + weight

    padding: dict[int, float] = {}
    for m, score in complexity.items():
        padding[m] = min(280.0, max(24.0, 24.0 + ((score - 1.5) * 18.0)))
    return padding


def resolve_lane(symbol: dict, spec: dict) -> str:
    column = spec.get("geometry", {}).get("staff_column")
    if column in COLUMN_LANES:
        return column
    body_part = symbol.get("body_part", "torso")
    if body_part in BODY_LANES:
        return body_part
    return "torso"


def compute_collision_index(placed: list[dict], lane: str, top: float, bottom: float) -> int:
    overlapping = 0
    for item in placed:
        if item["lane"] != lane:
            continue
        if bottom <= item["top"] or top >= item["bottom"]:
            continue
        overlapping += 1
    return overlapping


def direction_mirror_scale(direction: str | None) -> int:
    if direction in {"left", "diagonal_forward_left", "diagonal_backward_left", "counterclockwise"}:
        return -1
    return 1


def direction_vertical_bias(direction: str | None) -> float:
    if direction in {"backward", "diagonal_backward_left", "diagonal_backward_right", "low"}:
        return 1.0
    if direction in {"forward", "diagonal_forward_left", "diagonal_forward_right", "high"}:
        return -1.0
    return 0.0


def is_measure_header(symbol: dict, spec: dict) -> bool:
    return spec.get("geometry", {}).get("staff_column") == "music" and bool(symbol.get("modifiers", {}).get("measure_header"))


def is_measure_boundary_separator(symbol: dict, spec: dict) -> bool:
    column = spec.get("geometry", {}).get("staff_column")
    if column != "separator":
        return False
    symbol_id = symbol.get("symbol_id", "")
    if symbol_id.endswith("staff") or symbol_id.endswith("final"):
        return True
    behavior = spec.get("behavior", {})
    return behavior.get("layout_effect") == "full_measure_span"


def find_anchor_entry(entries: list[dict], current: dict) -> dict | None:
    attach_to = current["symbol"].get("modifiers", {}).get("attach_to")
    if attach_to:
        for entry in reversed(entries):
            if entry["symbol"].get("symbol_id") == attach_to and entry is not current:
                return entry
        return None
    current_start, current_end = current["start"], current["end"]
    best: dict | None = None
    for entry in reversed(entries):
        if entry is current:
            continue
        if entry["column"] in ATTACHABLE_COLUMNS:
            continue
        if current_end <= entry["start"] or current_start >= entry["end"]:
            continue
        best = entry
        break
    return best


def anchor_point(entry: dict, role: str, peer: dict | None = None) -> tuple[float, float]:
    modifiers = entry["symbol"].get("modifiers", {})
    side = modifiers.get("attach_side", "auto")
    geom_anchor = entry["spec"].get("geometry", {}).get("anchor", "center")
    left = entry["x"] - entry["width"] / 2
    right = entry["x"] + entry["width"] / 2
    top = entry["top"]
    bottom = entry["top"] + entry["height"]
    mid_x = entry["x"]
    mid_y = top + entry["height"] / 2
    if side == "auto" and peer is not None:
        horizontal_gap = peer["x"] - entry["x"]
        vertical_gap = (peer["top"] + peer["height"] / 2) - mid_y
        if abs(horizontal_gap) >= abs(vertical_gap):
            side = "right" if horizontal_gap >= 0 else "left"
        else:
            side = "bottom" if vertical_gap >= 0 else "top"
    if side == "left":
        return left, mid_y
    if side == "right":
        return right, mid_y
    if side == "top":
        return mid_x, top
    if side == "bottom":
        return mid_x, bottom
    if geom_anchor == "adjacent":
        if role == "source":
            if peer is not None and peer["x"] < entry["x"]:
                return left, mid_y
            return right, mid_y
        if peer is not None and peer["x"] < entry["x"]:
            return left, mid_y
        return right, mid_y
    if entry["column"] == "pin":
        return mid_x, bottom if role == "source" else top + 6
    if entry["column"] == "surface":
        return mid_x, mid_y
    if entry["column"] == "repeat":
        if role == "source":
            return left, top + 10
        return right, bottom - 10
    if entry["column"] == "music":
        return mid_x, bottom if role == "source" else mid_x, top + 4
    if entry["column"] in {"turn", "jump"}:
        return right, mid_y
    if entry["column"] in {"support", "body", "travel", "path"}:
        return right, mid_y
    return mid_x, mid_y


def attachment_clearance_y(source: dict, target: dict, entries: list[dict]) -> float | None:
    left = min(source["x"], target["x"])
    right = max(source["x"], target["x"])
    top = min(source["top"], target["top"])
    bottom = max(source["top"] + source["height"], target["top"] + target["height"])
    source_y = source["top"] + (source["height"] / 2)
    target_y = target["top"] + (target["height"] / 2)
    blockers = []
    for entry in entries:
        if entry is source or entry is target:
            continue
        family = entry_family(entry)
        if family not in {"repeat", "quality", "level", "timing"}:
            continue
        entry_left = entry["x"] - (entry["width"] / 2)
        entry_right = entry["x"] + (entry["width"] / 2)
        entry_top = entry["top"]
        entry_bottom = entry["top"] + entry["height"]
        if entry_right < left or entry_left > right:
            continue
        if entry_bottom < top or entry_top > bottom:
            continue
        blockers.append(entry)
    if not blockers:
        for entry in entries:
            if entry is source or entry is target:
                continue
            entry_left = entry["x"] - (entry["width"] / 2)
            entry_right = entry["x"] + (entry["width"] / 2)
            entry_top = entry["top"]
            entry_bottom = entry["top"] + entry["height"]
            if entry_right < left or entry_left > right:
                continue
            if entry_bottom < top or entry_top > bottom:
                continue
            blockers.append(entry)
    if not blockers:
        return None
    lowest_blocker_top = min(entry["top"] for entry in blockers)
    return lowest_blocker_top - 16


def entry_bounds(entry: dict, padding: float = 0.0) -> tuple[float, float, float, float]:
    half_width = entry["width"] / 2
    return (
        entry["x"] - half_width - padding,
        entry["x"] + half_width + padding,
        entry["top"] - padding,
        entry["top"] + entry["height"] + padding,
    )


def routing_hits_symbol_box(
    axis: str,
    left: float,
    right: float,
    top: float,
    bottom: float,
    coordinate: float,
    entry: dict,
) -> bool:
    entry_left, entry_right, entry_top, entry_bottom = entry_bounds(entry, padding=8.0)
    if axis == "horizontal":
        if coordinate < entry_top or coordinate > entry_bottom:
            return False
        return not (entry_right < left or entry_left > right)
    if coordinate < entry_left or coordinate > entry_right:
        return False
    return not (entry_bottom < top or entry_top > bottom)


def simplify_polyline(points: list[tuple[float, float]], tolerance: float = 1.0) -> list[tuple[float, float]]:
    simplified: list[tuple[float, float]] = []
    for x, y in points:
        point = (round(x, 1), round(y, 1))
        if simplified and abs(simplified[-1][0] - point[0]) <= tolerance and abs(simplified[-1][1] - point[1]) <= tolerance:
            continue
        simplified.append(point)

    changed = True
    while changed and len(simplified) >= 3:
        changed = False
        collapsed: list[tuple[float, float]] = [simplified[0]]
        for index in range(1, len(simplified) - 1):
            prev_x, prev_y = collapsed[-1]
            x, y = simplified[index]
            next_x, next_y = simplified[index + 1]
            same_x = abs(prev_x - x) <= tolerance and abs(x - next_x) <= tolerance
            same_y = abs(prev_y - y) <= tolerance and abs(y - next_y) <= tolerance
            if same_x or same_y:
                changed = True
                continue
            collapsed.append((x, y))
        collapsed.append(simplified[-1])
        simplified = collapsed
    return simplified


def attachment_bundle_profiles(pending_attachments: list[tuple[dict, dict]]) -> dict[int, dict[str, float]]:
    grouped: dict[tuple[int, str, float], list[tuple[dict, dict]]] = {}
    for source, target in pending_attachments:
        if entry_family(source) not in BUNDLE_ATTACHMENT_FAMILIES:
            continue
        key = (target["measure"], target["symbol"].get("symbol_id", ""), target["start"])
        grouped.setdefault(key, []).append((source, target))

    profiles: dict[int, dict[str, float]] = {}
    for attachments in grouped.values():
        if len(attachments) < 3:
            continue
        attachments.sort(key=lambda pair: pair[0]["x"])
        count = len(attachments)
        for rank, (source, target) in enumerate(attachments):
            ps = preferred_attachment_side(source, target)
            profiles[id(source)] = {
                "count": float(count),
                "rank": float(rank),
                "bundle_x": target["x"] - 28.0 if ps == "left" else target["x"] + 28.0,
            }
    return profiles


def routing_track_penalty(
    m: int,
    left: float,
    right: float,
    top: float,
    bottom: float,
    axis: str,
    track: int,
    kind: str,
    routed_lines: list[dict],
    blockers: list[dict] | None = None,
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> int | None:
    penalty = 0
    current_span = (right - left) if axis == "horizontal" else (bottom - top)
    for line in routed_lines:
        if line["measure"] != m:
            continue
        if int(line["track"]) != track:
            continue
        if line["bottom"] < top or line["top"] > bottom:
            continue
        line_axis = line.get("axis")
        line_span = (line["right"] - line["left"]) if line_axis == "horizontal" else (line["bottom"] - line["top"])
        geometry_buffer = min(24.0, max(6.0, max(line_span, current_span) * 0.04))
        if line_axis == "vertical":
            overlaps = (left - geometry_buffer) <= line["x"] <= (right + geometry_buffer)
        else:
            overlaps = not ((line["right"] + geometry_buffer) < left or (line["left"] - geometry_buffer) > right)
        if not overlaps:
            continue
        if line_axis == axis:
            return None
        existing_priority = ROUTING_KIND_PRIORITY.get(line.get("kind", "attachment"), 2)
        current_priority = ROUTING_KIND_PRIORITY.get(kind, 2)
        penalty += 8 if existing_priority <= current_priority else 2
    if blockers:
        coordinate = top if axis == "horizontal" else left
        symbol_collisions = sum(
            1
            for entry in blockers
            if routing_hits_symbol_box(axis, left, right, top, bottom, coordinate, entry)
        )
        if symbol_collisions:
            penalty += 20 * symbol_collisions
    if header_corridors and m in header_corridors:
        corridor = header_corridors[m]
        overlaps_corridor = not (
            right < corridor["left"]
            or left > corridor["right"]
            or bottom < corridor["top"]
            or top > corridor["bottom"]
        )
        if overlaps_corridor:
            penalty += 24
    return penalty


def reserve_routing_track(
    m: int,
    left: float,
    right: float,
    top: float,
    bottom: float,
    base_y: float,
    routed_lines: list[dict],
    kind: str,
    blockers: list[dict] | None = None,
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> tuple[float, int]:
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == m), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 5):
        routed_y = base_y + (track * 12.0)
        penalty = routing_track_penalty(
            m, left, right, routed_y, routed_y, "horizontal", track, kind,
            routed_lines, blockers, header_corridors,
        )
        if penalty is None:
            continue
        if best_penalty is None or penalty < best_penalty:
            best_track = track
            best_penalty = penalty
            if penalty == 0:
                break
    track = best_track
    routed_y = base_y + (track * 12.0)
    routed_lines.append(
        {
            "measure": m,
            "left": left,
            "right": right,
            "y": routed_y,
            "track": track,
            "axis": "horizontal",
            "kind": kind,
            "top": top,
            "bottom": bottom,
            "geometry_width": right - left,
        }
    )
    return routed_y, track


def reserve_vertical_routing_track(
    m: int,
    top: float,
    bottom: float,
    base_x: float,
    routed_lines: list[dict],
    kind: str,
    blockers: list[dict] | None = None,
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> tuple[float, int]:
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == m), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 5):
        routed_x = base_x - (track * 12.0)
        penalty = routing_track_penalty(
            m, routed_x, routed_x, top, bottom, "vertical", track, kind,
            routed_lines, blockers, header_corridors,
        )
        if penalty is None:
            continue
        if best_penalty is None or penalty < best_penalty:
            best_track = track
            best_penalty = penalty
            if penalty == 0:
                break
    track = best_track
    routed_x = base_x - (track * 12.0)
    routed_lines.append(
        {
            "measure": m,
            "left": routed_x,
            "right": routed_x,
            "x": routed_x,
            "track": track,
            "axis": "vertical",
            "kind": kind,
            "top": top,
            "bottom": bottom,
            "geometry_height": bottom - top,
        }
    )
    return routed_x, track


def measure_special_x_offset(entry: dict, existing_entries: list[dict]) -> float:
    same_slot = [
        item for item in existing_entries
        if item["measure"] == entry["measure"]
        and abs(item["start"] - entry["start"]) < 0.01
        and item is not entry
    ]
    family = entry_family(entry)
    if family in {"repeat", "separator", "music"}:
        same_family = [item for item in same_slot if entry_family(item) == family]
        return len(same_family) * 8.0
    return 0.0


def measure_priority_y_offset(entry: dict, existing_entries: list[dict]) -> float:
    column = entry.get("column")
    if column not in {"quality", "level", "timing", "repeat", "separator"}:
        return 0.0
    same_slot = [
        item for item in existing_entries
        if item["measure"] == entry["measure"]
        and abs(item["start"] - entry["start"]) < 0.51
        and item is not entry
    ]
    competing_columns = {"quality", "level", "timing", "repeat", "separator"}
    layer_offsets = {
        "repeat": -14.0,
        "quality": -4.0,
        "level": 4.0,
        "timing": 10.0,
        "separator": -8.0,
    }
    if not any(entry_family(item) in competing_columns for item in same_slot):
        return 0.0
    return layer_offsets.get(column, 0.0)


# ── Attachment route computation ───────────────────────────────────────

def compute_attachment_route(
    source: dict,
    target: dict,
    entries: list[dict],
    routed_lines: list[dict],
    header_corridors: dict[int, dict[str, float]] | None = None,
    bundle_profile: dict[str, float] | None = None,
) -> dict:
    """Returns {route_type, points} for an attachment line."""
    source_x, source_y = anchor_point(source, "source", target)
    target_x, target_y = anchor_point(target, "target", source)
    blockers = [e for e in entries if e is not source and e is not target]
    ps = preferred_attachment_side(source, target)
    clearance = attachment_clearance_y(source, target, entries)
    if clearance is not None:
        routed_y, _track = reserve_routing_track(
            min(source["measure"], target["measure"]),
            min(source_x, target_x),
            max(source_x, target_x),
            min(source["top"], target["top"]),
            max(source["top"] + source["height"], target["top"] + target["height"]),
            clearance,
            routed_lines,
            "attachment",
            blockers,
            header_corridors,
        )
        if bundle_profile:
            bundle_x = bundle_profile["bundle_x"]
            split_y = target_y + ((bundle_profile["rank"] - ((bundle_profile["count"] - 1.0) / 2.0)) * 8.0)
            return {"route_type": "bundle-clearance", "points": [
                (source_x, source_y), (source_x, routed_y), (bundle_x, routed_y),
                (bundle_x, split_y), (target_x, split_y), (target_x, target_y),
            ]}
        if abs(source["start"] - target["start"]) >= 1.0 and {source["column"], target["column"]} & {"pin"}:
            jog_source_x = source_x - 18.0 if source_x > target_x else source_x + 18.0
            jog_target_x = target_x - 18.0 if ps == "left" else target_x + 18.0
            return {"route_type": "multi-elbow", "points": [
                (source_x, source_y), (source_x, routed_y), (jog_source_x, routed_y),
                (jog_target_x, routed_y), (target_x, routed_y), (target_x, target_y),
            ]}
        if abs(source["start"] - target["start"]) >= 1.0:
            jog_x = target_x - 18.0 if ps == "left" else target_x + 18.0
            jog_y = target_y + 12.0 if routed_y < target_y else target_y - 12.0
            return {"route_type": "dogleg", "points": [
                (source_x, source_y), (source_x, routed_y), (jog_x, routed_y),
                (jog_x, jog_y), (target_x, jog_y), (target_x, target_y),
            ]}
        return {"route_type": "clearance", "points": [
            (source_x, source_y), (source_x, routed_y),
            (target_x, routed_y), (target_x, target_y),
        ]}
    if abs(source["start"] - target["start"]) >= 1.0 and {source["column"], target["column"]} & {"pin"}:
        routed_y = min(source_y, target_y) - 24.0 if abs(source_y - target_y) < 48.0 else (source_y + target_y) / 2
        jog_source_x = source_x - 18.0 if source_x > target_x else source_x + 18.0
        jog_target_x = target_x - 18.0 if ps == "left" else target_x + 18.0
        return {"route_type": "multi-elbow", "points": [
            (source_x, source_y), (source_x, routed_y), (jog_source_x, routed_y),
            (jog_target_x, routed_y), (target_x, routed_y), (target_x, target_y),
        ]}
    mid_x = (source_x + target_x) / 2
    if abs(source_y - target_y) > abs(source_x - target_x):
        mid_x = source_x + ((target_x - source_x) * 0.25)
    return {"route_type": "curve", "points": [
        (source_x, source_y), (mid_x, source_y), (mid_x, target_y), (target_x, target_y),
    ]}


def compute_bridge_routes(
    entries: list[dict],
    routed_lines: list[dict],
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> list[dict]:
    """Returns [{route_type, points, ...}, ...] for repeat-separator bridges."""
    bridges: list[dict] = []
    repeats = [e for e in entries if e["column"] == "repeat"]
    separators = [e for e in entries if e["column"] == "separator"]
    for repeat in repeats:
        for separator in separators:
            if abs(repeat["start"] - separator["start"]) > 0.51:
                continue
            y, _track = reserve_routing_track(
                repeat["measure"],
                min(repeat["x"], separator["x"]),
                max(repeat["x"], separator["x"]),
                min(repeat["top"], separator["top"]),
                max(repeat["top"] + repeat["height"], separator["top"] + separator["height"]),
                min(repeat["top"], separator["top"]) - 8,
                routed_lines,
                "bridge",
                [e for e in entries if e is not repeat and e is not separator],
                header_corridors,
            )
            bridges.append({"route_type": "bridge", "points": [(repeat["x"], y), (separator["x"], y)]})
            break
    return bridges


def compute_span_routes(
    entries: list[dict],
    routed_lines: list[dict],
    m_tops: dict[int, float],
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> list[dict]:
    """Returns [{route_type, x, y1, y2}, ...] for repeat spans."""
    spans: list[dict] = []
    starts = [e for e in entries if e["symbol"].get("symbol_id") == "repeat.start"]
    ends = [e for e in entries if e["column"] == "repeat" and e["symbol"].get("symbol_id") in {"repeat.end", "repeat.double"}]
    for start in starts:
        target_id = start["symbol"].get("modifiers", {}).get("repeat_span_to")
        target = None
        if target_id:
            for candidate in entries:
                if candidate["symbol"].get("symbol_id") == target_id:
                    target = candidate
                    break
        else:
            for candidate in ends:
                if candidate["start"] > start["start"]:
                    target = candidate
                    break
        if not target:
            continue
        competing = [
            item for item in entries
            if item["measure"] in {start["measure"], target["measure"]}
            and entry_family(item) in {"quality", "level", "timing"}
        ]
        leftmost_annotation = min((item["x"] - (item["width"] / 2) for item in competing), default=start["x"] - 18)
        y1 = m_tops[start["measure"]] + 4
        y2 = m_tops[target["measure"]] + (4 * BEAT_HEIGHT) - 4
        x, _track = reserve_vertical_routing_track(
            start["measure"],
            y1, y2,
            min(start["x"] - 18, leftmost_annotation - 14),
            routed_lines,
            "span",
            [e for e in entries if e is not start and e is not target],
            header_corridors,
        )
        spans.append({"route_type": "span", "x": x, "y1": y1, "y2": y2})
    return spans


# ── Top-level layout computation ──────────────────────────────────────

def compute_layout(ir: dict) -> dict:
    """Compute the full score layout from IR, returning all coordinates needed for rendering."""
    catalog = load_symbol_catalog()
    symbols = ir.get("symbols", [])
    beats_map = build_measure_beats_map(ir)
    mc = measure_count(symbols, beats_map)
    h_layout = measure_header_layout(symbols, catalog)
    m_right_padding = measure_right_padding(symbols, catalog)
    header_gutter = header_gutter_width(h_layout)
    staff_left = MARGIN_X + header_gutter
    lane_positions = build_lane_positions(staff_left)
    order = BODY_LANES + COLUMN_LANES
    lane_right = staff_left + len(order) * LANE_WIDTH + (len(order) - 1) * LANE_GAP
    staff_top = TOP_MARGIN + HEADER_HEIGHT
    m_pressures = measure_stack_pressure(symbols, catalog, mc)
    m_tops, m_gaps = measure_vertical_layout(symbols, catalog, staff_top, mc)
    h_corridors = measure_header_corridors(h_layout, m_tops, staff_left)
    systems = system_layout(mc, m_tops, m_right_padding, staff_left, lane_right)
    width = int(lane_right + max(m_right_padding.values(), default=52.0) + MARGIN_X)
    total_beats = sum(beats_for_measure(m, beats_map) for m in range(1, mc + 1))
    timeline_height = (total_beats * BEAT_HEIGHT) + sum(m_gaps.values())
    height = int(TOP_MARGIN + HEADER_HEIGHT + timeline_height + BOTTOM_MARGIN)

    # Place symbols
    placed: list[dict] = []
    rendered_entries: list[dict] = []
    header_stack: dict[int, int] = {}
    measure_headers: dict[int, int] = {}
    for symbol in sorted(symbols, key=lambda item: symbol_time(item, beats_map)[0]):
        symbol_id = symbol.get("symbol_id", "")
        spec = catalog.get(symbol_id, {})
        geom = spec.get("geometry", {})
        lane = resolve_lane(symbol, spec)
        x = lane_positions[lane]
        start, end = symbol_time(symbol, beats_map)
        m = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        m_top = m_tops[m]
        measure_abs_start = sum(beats_for_measure(mi, beats_map) for mi in range(1, m))
        within_measure_start = start - measure_abs_start
        within_measure_end = end - measure_abs_start
        top = m_top + within_measure_start * BEAT_HEIGHT + 6
        height_span = max(MIN_SYMBOL_HEIGHT, (within_measure_end - within_measure_start) * BEAT_HEIGHT - 12)
        m_bpm = beats_for_measure(m, beats_map)
        if is_measure_boundary_separator(symbol, spec):
            top = m_top + 2
            height_span = (m_bpm * BEAT_HEIGHT) - 4
        bottom = top + height_span
        collision_index = compute_collision_index(placed, lane, top, bottom)
        x += collision_index * COLLISION_OFFSET
        placed.append({"lane": lane, "top": top, "bottom": bottom})
        entry = {
            "symbol": symbol,
            "spec": spec,
            "column": geom.get("staff_column"),
            "x": x,
            "top": top,
            "height": height_span,
            "width": max(int(geom.get("width", 20)), 18) + 16,
            "start": start,
            "end": end,
            "measure": m,
            "measure_top": m_top,
            "measure_height": 4 * BEAT_HEIGHT,
        }
        x += measure_special_x_offset(entry, rendered_entries)
        top += measure_priority_y_offset(entry, rendered_entries)
        top += measure_zone_y_offset(entry, m_pressures.get(m, 0.0))
        entry["x"] = x
        entry["top"] = top
        rendered_entries.append(entry)
        if is_measure_header(symbol, spec):
            si = header_stack.get(m, 0)
            header_stack[m] = si + 1
            measure_headers[m] = header_stack[m]

    # Build attachment pairs
    pending_attachments: list[tuple[dict, dict]] = []
    for entry in rendered_entries:
        if entry["column"] not in ATTACHABLE_COLUMNS:
            continue
        if is_measure_header(entry["symbol"], entry["spec"]):
            continue
        target = find_anchor_entry(rendered_entries, entry)
        if target:
            pending_attachments.append((entry, target))
    bundle_profiles = attachment_bundle_profiles(pending_attachments)

    # Compute routes
    routed_lines: list[dict] = []
    bridge_routes = compute_bridge_routes(rendered_entries, routed_lines, h_corridors)
    span_routes = compute_span_routes(rendered_entries, routed_lines, m_tops, h_corridors)
    attachment_routes: list[dict] = []
    for source, target in pending_attachments:
        route = compute_attachment_route(
            source, target, rendered_entries, routed_lines,
            h_corridors, bundle_profiles.get(id(source)),
        )
        attachment_routes.append(route)

    return {
        "catalog": catalog,
        "symbols": symbols,
        "measure_count": mc,
        "beats_map": beats_map,
        "header_layout": h_layout,
        "measure_right_padding": m_right_padding,
        "header_gutter": header_gutter,
        "staff_left": staff_left,
        "lane_positions": lane_positions,
        "lane_right": lane_right,
        "staff_top": staff_top,
        "measure_pressures": m_pressures,
        "measure_tops": m_tops,
        "measure_gaps": m_gaps,
        "header_corridors": h_corridors,
        "systems": systems,
        "width": width,
        "height": height,
        "rendered_entries": rendered_entries,
        "pending_attachments": pending_attachments,
        "measure_headers": measure_headers,
        "header_stack": header_stack,
        "bridge_routes": bridge_routes,
        "span_routes": span_routes,
        "attachment_routes": attachment_routes,
        "routed_lines": routed_lines,
        "title": ir.get("metadata", {}).get("title", "Untitled"),
    }
