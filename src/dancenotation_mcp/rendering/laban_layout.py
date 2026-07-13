"""Standard Labanotation staff layout engine.

Produces an 11-column staff with center line, bottom-to-top time flow,
and annotation regions — matching ICKL publication conventions.

Scores longer than ``LABAN_SYSTEM_CAPACITY`` measures are wrapped into
multiple side-by-side *systems* (columns), each containing at most that
many measures.
"""

from __future__ import annotations

from math import ceil

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.time_signatures import (
    DEFAULT_BEATS_PER_MEASURE,
    beats_for_measure,
    build_measure_beats_map,
)

# ── Constants ─────────────────────────────────────────────────────────

MARGIN_X = 60
MARGIN_Y_TOP = 70
MARGIN_Y_BOTTOM = 40
HEADER_HEIGHT = 40

COL_WIDTH = 20  # default fallback; per-column widths below override this
CENTER_GAP = 4

# ICKL-standard column widths: support widest, body medium, arm/gesture/path narrow
COLUMN_WIDTHS = {
    "left_path":         14,
    "left_arm_gesture":  16,
    "left_arm":          18,
    "left_body":         18,
    "left_support":      26,
    "right_support":     26,
    "right_body":        18,
    "right_arm":         18,
    "right_arm_gesture": 16,
    "right_path":        14,
}
BEAT_HEIGHT = 60
ANNOTATION_WIDTH = 22
ANNOTATION_GAP = 6

LABAN_SYSTEM_CAPACITY = 8   # measures per system before wrapping
LABAN_SYSTEM_GAP_X = 40     # horizontal gap (kept for backward compat)
LABAN_SYSTEM_GAP_Y = 30     # vertical gap between stacked systems

STARTING_POSITION_HEIGHT = 60  # vertical space for starting position area
STARTING_POSITION_GAP = 8     # gap between starting position and measure 1

# Staff columns from left to right (11-column ICKL standard).
# The center line sits between left_support and right_support.
STAFF_COLUMNS = [
    "left_path",
    "left_arm_gesture",
    "left_arm",
    "left_body",
    "left_support",
    # ── center line ──
    "right_support",
    "right_body",
    "right_arm",
    "right_arm_gesture",
    "right_path",
]

LEFT_COLUMNS = {"left_path", "left_arm_gesture", "left_arm", "left_body", "left_support"}
RIGHT_COLUMNS = {"right_support", "right_body", "right_arm", "right_arm_gesture", "right_path"}

BODY_TO_COLUMN = {
    # Legs → support columns
    "left_leg": "left_support", "right_leg": "right_support",
    "left_upper_leg": "left_support", "right_upper_leg": "right_support",
    "left_lower_leg": "left_support", "right_lower_leg": "right_support",
    "left_foot": "left_support", "right_foot": "right_support",
    "left_toes": "left_support", "right_toes": "right_support",
    "left_hip": "left_support", "right_hip": "right_support",
    "left_knee": "left_support", "right_knee": "right_support",
    "left_ankle": "left_support", "right_ankle": "right_support",
    # Arms (main limb) → arm columns
    "left_arm": "left_arm", "right_arm": "right_arm",
    "left_upper_arm": "left_arm", "right_upper_arm": "right_arm",
    "left_lower_arm": "left_arm", "right_lower_arm": "right_arm",
    # Arms (extremities) → gesture columns
    "left_hand": "left_arm_gesture", "right_hand": "right_arm_gesture",
    "left_fingers": "left_arm_gesture", "right_fingers": "right_arm_gesture",
    "left_elbow": "left_arm_gesture", "right_elbow": "right_arm_gesture",
    "left_wrist": "left_arm_gesture", "right_wrist": "right_arm_gesture",
    # Shoulders → body columns
    "left_shoulder": "left_body", "right_shoulder": "right_body",
    # Body → center
    "torso": "center", "head": "head",
    "upper_spine": "center", "lower_spine": "center",
    "neck": "head",
    "pelvis": "center", "whole_body": "center",
}

# Symbol families placed inside the main staff columns.
PRIMARY_FAMILIES = {"support", "direction", "gesture", "body", "flexion"}

# Symbol families placed in annotation areas beside the staff.
ANNOTATION_FAMILIES = {"turn", "jump", "path", "quality", "timing",
                       "level", "surface", "pin", "repeat", "music",
                       "retention", "contact", "effort", "shape",
                       "floor_plan", "sequential", "bow", "dynamic",
                       "adlib", "motif", "foothook", "digit"}

# Annotation side preference (left or right of staff).
ANNOTATION_SIDE = {
    "turn": "left",
    "path": "left",
    "jump": "right",
    "quality": "right",
    "timing": "right",
    "level": "right",
    "surface": "right",
    "pin": "left",
    "repeat": "left",
    "music": "left",
    "retention": "right",
    "contact": "right",
    "effort": "right",
    "shape": "right",
    "floor_plan": "left",
    "sequential": "left",
    "bow": "right",
    "dynamic": "right",
    "adlib": "right",
    "motif": "right",
    "foothook": "right",
    "digit": "right",
}


# ── Helpers ───────────────────────────────────────────────────────────

def _symbol_family(symbol_id: str) -> str:
    return symbol_id.split(".", 1)[0]


def _symbol_time(symbol: dict, beats_map: dict[int, float] | None = None) -> tuple[float, float]:
    timing = symbol.get("timing", {})
    measure = max(int(timing.get("measure", 1)), 1)
    beat = float(timing.get("beat", 1.0))
    duration = max(float(timing.get("duration_beats", 1.0)), 0.25)
    bpm = beats_for_measure(measure, beats_map or {})
    start = sum(beats_for_measure(m, beats_map or {}) for m in range(1, measure)) + (beat - 1.0)
    end = start + duration
    return start, end


def measure_count(symbols: list[dict], beats_map: dict[int, float] | None = None) -> int:
    if not symbols:
        return 1
    max_m = 1
    for s in symbols:
        timing = s.get("timing", {})
        m = max(int(timing.get("measure", 1)), 1)
        beat = float(timing.get("beat", 1.0))
        dur = max(float(timing.get("duration_beats", 1.0)), 0.25)
        bpm = beats_for_measure(m, beats_map or {})
        end_beat = beat + dur - 1.0  # relative to measure start
        extra = 0
        while end_beat > bpm:
            extra += 1
            end_beat -= beats_for_measure(m + extra, beats_map or {})
        max_m = max(max_m, m + extra)
    return max_m


def is_measure_header(symbol: dict, spec: dict) -> bool:
    col = spec.get("geometry", {}).get("staff_column", "")
    return col == "music" and bool(symbol.get("modifiers", {}).get("measure_header"))


# ── Column geometry ───────────────────────────────────────────────────

def build_column_positions(staff_left: float) -> dict[str, tuple[float, float]]:
    """Return {column_name: (left_x, right_x)} for the 11 staff columns.

    Uses per-column widths from COLUMN_WIDTHS for ICKL-standard proportions:
    support columns are widest, gesture/path columns are narrowest.
    """
    positions: dict[str, tuple[float, float]] = {}
    x = staff_left
    for col in STAFF_COLUMNS:
        if col == "right_support":
            x += CENTER_GAP   # skip over center line
        col_w = COLUMN_WIDTHS.get(col, COL_WIDTH)
        left_x = x
        right_x = x + col_w
        positions[col] = (left_x, right_x)
        x = right_x
    # Center spans left_support + right_support
    ls = positions["left_support"]
    rs = positions["right_support"]
    positions["center"] = (ls[0], rs[1])
    return positions


def staff_total_width() -> float:
    return sum(COLUMN_WIDTHS.get(c, COL_WIDTH) for c in STAFF_COLUMNS) + CENTER_GAP


# ── Measure geometry (bottom-to-top) ─────────────────────────────────

def build_measure_positions(
    mc: int, canvas_bottom: float, beats_map: dict[int, float] | None = None,
    *, first_measure: int = 1,
) -> dict[int, tuple[float, float]]:
    """Return {measure_number: (bottom_y, top_y)}.

    Beat 1 is at the *bottom* of the measure; higher beats go up.
    The lowest measure (nearest *canvas_bottom*) is ``first_measure``.

    *mc* is the **count** of measures in this system (not the last
    measure number).
    """
    positions: dict[int, tuple[float, float]] = {}
    y_bottom = canvas_bottom
    for i in range(mc):
        m = first_measure + i
        bpm = beats_for_measure(m, beats_map or {})
        measure_height = bpm * BEAT_HEIGHT
        y_top = y_bottom - measure_height
        positions[m] = (y_bottom, y_top)
        y_bottom = y_top  # next measure stacks on top
    return positions


# ── Symbol placement ─────────────────────────────────────────────────

def _resolve_column(symbol: dict, spec: dict) -> str:
    """Decide which staff column a symbol belongs to."""
    body_part = symbol.get("body_part", "torso")
    family = _symbol_family(symbol.get("symbol_id", ""))
    staff_col = spec.get("geometry", {}).get("staff_column", "")

    # Annotation families go outside the staff
    if staff_col in ANNOTATION_FAMILIES or family in ANNOTATION_FAMILIES:
        return "annotation"

    # Map body part to column
    col = BODY_TO_COLUMN.get(body_part, "center")
    return col


def _beat_to_y(measure_pos: tuple[float, float], beat: float,
               duration: float, beats_per_measure: float | None = None) -> tuple[float, float]:
    """Convert beat position within a measure to y-coordinates.

    Returns (y_bottom, y_top) — bottom of symbol, top of symbol.
    In bottom-to-top layout: beat 1 at bottom_y, beat N at top_y.
    """
    m_bottom, m_top = measure_pos
    measure_height = m_bottom - m_top
    bpm = beats_per_measure if beats_per_measure is not None else DEFAULT_BEATS_PER_MEASURE
    beat_h = measure_height / bpm

    # beat 1 starts at bottom
    y_bottom = m_bottom - (beat - 1.0) * beat_h
    y_top = y_bottom - duration * beat_h
    return y_bottom, y_top


def _system_for_measure(m: int) -> int:
    """Return 0-based system index for a given 1-based measure number."""
    return (m - 1) // LABAN_SYSTEM_CAPACITY


def compute_laban_layout(ir: dict) -> dict:
    """Compute full standard Labanotation layout from IR.

    When the score has more than ``LABAN_SYSTEM_CAPACITY`` measures the
    layout wraps into multiple vertically stacked *systems*.  Each system
    shares the same x-position; earlier measures appear at the top of the
    page.
    """
    catalog = load_symbol_catalog()
    symbols = ir.get("symbols", [])
    beats_map = build_measure_beats_map(ir)
    mc = measure_count(symbols, beats_map)

    num_systems = max(1, ceil(mc / LABAN_SYSTEM_CAPACITY))

    # ── Per-system geometry ───────────────────────────────────────────
    annotation_left_width = ANNOTATION_WIDTH + ANNOTATION_GAP
    annotation_right_width = ANNOTATION_WIDTH + ANNOTATION_GAP
    staff_w = staff_total_width()
    single_system_width = MARGIN_X + annotation_left_width + staff_w + annotation_right_width + MARGIN_X

    systems: list[dict] = []
    y_cursor = MARGIN_Y_TOP + HEADER_HEIGHT  # top of first system's content
    for si in range(num_systems):
        # All systems share the same x position (vertical stacking)
        s_staff_left = MARGIN_X + annotation_left_width
        s_staff_right = s_staff_left + staff_w
        s_col_positions = build_column_positions(s_staff_left)
        # Center line sits between left_support and right_support
        ls_right = s_col_positions["left_support"][1]
        rs_left = s_col_positions["right_support"][0]
        s_staff_center_x = (ls_right + rs_left) / 2

        start_m = si * LABAN_SYSTEM_CAPACITY + 1
        end_m = min(mc, (si + 1) * LABAN_SYSTEM_CAPACITY)

        # Vertical extent for this system's measures
        total_beat_height = sum(
            beats_for_measure(m, beats_map) * BEAT_HEIGHT
            for m in range(start_m, end_m + 1)
        )
        # First system includes starting position area below measure 1
        start_pos_space = (STARTING_POSITION_HEIGHT + STARTING_POSITION_GAP) if si == 0 else 0

        # canvas_bottom for this system: measures go bottom-to-top within system
        canvas_bottom = y_cursor + total_beat_height + start_pos_space + MARGIN_Y_BOTTOM
        s_measure_positions = build_measure_positions(
            end_m - start_m + 1,
            canvas_bottom - MARGIN_Y_BOTTOM - start_pos_space,
            beats_map,
            first_measure=start_m,
        )

        # Starting position area sits below measure 1
        starting_pos_top = canvas_bottom - MARGIN_Y_BOTTOM - start_pos_space
        starting_pos_bottom = starting_pos_top + STARTING_POSITION_HEIGHT

        systems.append({
            "system_index": si,
            "start_measure": start_m,
            "end_measure": end_m,
            "staff_left": s_staff_left,
            "staff_right": s_staff_right,
            "staff_center_x": s_staff_center_x,
            "col_positions": s_col_positions,
            "measure_positions": s_measure_positions,
            "starting_pos_top": starting_pos_top if si == 0 else None,
            "starting_pos_bottom": starting_pos_bottom if si == 0 else None,
            "canvas_bottom": canvas_bottom,
        })

        # Advance y_cursor for next system
        y_cursor = canvas_bottom + LABAN_SYSTEM_GAP_Y

    # Global canvas size — single column width, total stacked height
    canvas_width = single_system_width
    canvas_height = max(s["canvas_bottom"] for s in systems)

    # Build a merged measure_positions dict for backward-compat (single system)
    merged_measure_positions: dict[int, tuple[float, float]] = {}
    for s in systems:
        merged_measure_positions.update(s["measure_positions"])

    # Use first system's staff geometry as the "default" (backward compat)
    first = systems[0]

    # ── Place symbols ─────────────────────────────────────────────────
    placed_symbols: list[dict] = []
    annotation_entries: list[dict] = []
    header_entries: list[dict] = []
    annot_stack: dict[tuple[int, str, float], int] = {}

    for symbol in sorted(symbols, key=lambda s: _symbol_time(s, beats_map)[0]):
        symbol_id = symbol.get("symbol_id", "")
        spec = catalog.get(symbol_id, {})
        timing = symbol.get("timing", {})
        m = max(int(timing.get("measure", 1)), 1)
        beat = float(timing.get("beat", 1.0))
        duration = max(float(timing.get("duration_beats", 1.0)), 0.25)
        family = _symbol_family(symbol_id)

        si = _system_for_measure(m)
        if si >= len(systems):
            continue
        sys = systems[si]
        s_staff_left = sys["staff_left"]
        s_staff_right = sys["staff_right"]
        s_staff_center_x = sys["staff_center_x"]
        s_col_positions = sys["col_positions"]
        s_measure_positions = sys["measure_positions"]

        if m not in s_measure_positions:
            continue

        m_pos = s_measure_positions[m]

        # Measure headers
        if is_measure_header(symbol, spec):
            header_entries.append({
                "symbol": symbol,
                "spec": spec,
                "measure": m,
                "family": family,
                "system_index": si,
            })
            continue

        col = _resolve_column(symbol, spec)
        m_bpm = beats_for_measure(m, beats_map)
        y_bottom, y_top = _beat_to_y(m_pos, beat, duration, m_bpm)

        if col == "annotation":
            side = ANNOTATION_SIDE.get(family, "right")
            stack_key = (m, side, round(beat, 2))
            stack_idx = annot_stack.get(stack_key, 0)
            annot_stack[stack_key] = stack_idx + 1

            if side == "left":
                ax = s_staff_left - ANNOTATION_GAP - ANNOTATION_WIDTH - stack_idx * (ANNOTATION_WIDTH + 2)
            else:
                ax = s_staff_right + ANNOTATION_GAP + stack_idx * (ANNOTATION_WIDTH + 2)

            annotation_entries.append({
                "symbol": symbol,
                "spec": spec,
                "measure": m,
                "family": family,
                "x": ax,
                "y_top": y_top,
                "y_bottom": y_bottom,
                "width": ANNOTATION_WIDTH,
                "side": side,
                "system_index": si,
            })
            continue

        if col == "head":
            _, m_top_y = m_pos
            cx = s_staff_center_x
            placed_symbols.append({
                "symbol": symbol,
                "spec": spec,
                "measure": m,
                "family": family,
                "column": col,
                "x_left": cx - COL_WIDTH / 2,
                "x_right": cx + COL_WIDTH / 2,
                "y_top": m_top_y - 18,
                "y_bottom": m_top_y - 4,
                "system_index": si,
            })
            continue

        # Normal staff column placement
        if col == "center":
            # Body/torso symbols: center on the center line with body-column width.
            # In ICKL standard, body symbols sit between the two support columns,
            # straddling the center line — NOT spanning the full center distance.
            body_w = COLUMN_WIDTHS.get("left_body", COL_WIDTH)
            cx_left = s_staff_center_x - body_w / 2
            cx_right = s_staff_center_x + body_w / 2
        elif col in s_col_positions:
            cx_left, cx_right = s_col_positions[col]
        else:
            cx_left, cx_right = s_col_positions["right_support"]

        placed_symbols.append({
            "symbol": symbol,
            "spec": spec,
            "measure": m,
            "family": family,
            "column": col,
            "x_left": cx_left,
            "x_right": cx_right,
            "y_top": y_top,
            "y_bottom": y_bottom,
            "system_index": si,
        })

    # ── Route computation ────────────────────────────────────────────
    bridge_routes = _compute_laban_bridge_routes(annotation_entries)
    span_routes = _compute_laban_span_routes(annotation_entries, merged_measure_positions)
    attachment_routes = _compute_laban_attachment_routes(
        annotation_entries, placed_symbols, systems,
    )

    return {
        "catalog": catalog,
        "symbols": symbols,
        "measure_count": mc,
        "beats_map": beats_map,
        "staff_left": first["staff_left"],
        "staff_right": first["staff_right"],
        "staff_center_x": first["staff_center_x"],
        "staff_width": staff_w,
        "column_positions": first["col_positions"],
        "measure_positions": merged_measure_positions,
        "systems": systems,
        "placed_symbols": placed_symbols,
        "annotation_entries": annotation_entries,
        "header_entries": header_entries,
        "bridge_routes": bridge_routes,
        "span_routes": span_routes,
        "attachment_routes": attachment_routes,
        "width": int(canvas_width),
        "height": int(canvas_height),
        "title": ir.get("metadata", {}).get("title", "Untitled"),
    }


# ── Route computation helpers ─────────────────────────────────────────


def _compute_laban_bridge_routes(
    annotation_entries: list[dict],
) -> list[dict]:
    """Connect repeat.start / repeat.end pairs with horizontal bridge lines."""
    bridges: list[dict] = []
    starts = [e for e in annotation_entries if e["family"] == "repeat"
              and e["symbol"].get("symbol_id", "").endswith(".start")]
    ends = [e for e in annotation_entries if e["family"] == "repeat"
            and e["symbol"].get("symbol_id", "") in {"repeat.end", "repeat.double"}]
    for start in starts:
        for end in ends:
            if end.get("system_index") != start.get("system_index"):
                continue
            if end["measure"] < start["measure"]:
                continue
            # Connect at a y midpoint between the two symbols
            y = (start["y_top"] + start["y_bottom"] + end["y_top"] + end["y_bottom"]) / 4
            bridges.append({
                "points": [(start["x"] + start["width"] / 2, y),
                           (end["x"] + end["width"] / 2, y)],
                "symbol_ids": [start["symbol"].get("symbol_id"),
                               end["symbol"].get("symbol_id")],
            })
            break  # match first end per start
    return bridges


def _compute_laban_span_routes(
    annotation_entries: list[dict],
    measure_positions: dict[int, tuple[float, float]],
) -> list[dict]:
    """Vertical repeat-section brackets on the left side of the staff."""
    spans: list[dict] = []
    starts = [e for e in annotation_entries if e["symbol"].get("symbol_id") == "repeat.start"]
    ends = [e for e in annotation_entries if e["family"] == "repeat"
            and e["symbol"].get("symbol_id") in {"repeat.end", "repeat.double"}]
    for start in starts:
        target = None
        for candidate in ends:
            if candidate.get("system_index") != start.get("system_index"):
                continue
            if candidate["measure"] >= start["measure"]:
                target = candidate
                break
        if not target:
            continue
        # Vertical bracket just to the left of the annotation column
        x = min(start["x"], target["x"]) - 6
        # Span from bottom of start measure to top of end measure
        if start["measure"] in measure_positions and target["measure"] in measure_positions:
            y1 = measure_positions[start["measure"]][0]  # bottom_y of start measure
            y2 = measure_positions[target["measure"]][1]  # top_y of end measure
        else:
            y1 = start["y_bottom"]
            y2 = target["y_top"]
        spans.append({"x": x, "y1": y1, "y2": y2})
    return spans


def _compute_laban_attachment_routes(
    annotation_entries: list[dict],
    placed_symbols: list[dict],
    systems: list[dict],
) -> list[dict]:
    """Dashed lines from annotations with ``attach_to`` to their target staff column."""
    routes: list[dict] = []
    for entry in annotation_entries:
        attach_to = entry["symbol"].get("modifiers", {}).get("attach_to")
        if not attach_to:
            continue
        si = entry.get("system_index", 0)
        if si >= len(systems):
            continue
        sys = systems[si]
        # Find target: a placed symbol with matching symbol_id in the same system
        target = None
        for ps in placed_symbols:
            if ps.get("system_index") != si:
                continue
            if ps["symbol"].get("symbol_id") == attach_to:
                target = ps
                break
        if target:
            # Connect annotation center to target center
            src_x = entry["x"] + entry["width"] / 2
            src_y = (entry["y_top"] + entry["y_bottom"]) / 2
            tgt_x = (target["x_left"] + target["x_right"]) / 2
            tgt_y = (target["y_top"] + target["y_bottom"]) / 2
        else:
            # Fallback: connect to nearest staff edge
            src_x = entry["x"] + entry["width"] / 2
            src_y = (entry["y_top"] + entry["y_bottom"]) / 2
            if entry.get("side") == "left":
                tgt_x = sys["staff_left"]
            else:
                tgt_x = sys["staff_right"]
            tgt_y = src_y
        routes.append({
            "points": [(src_x, src_y), (tgt_x, tgt_y)],
            "style": "dashed",
        })
    return routes
