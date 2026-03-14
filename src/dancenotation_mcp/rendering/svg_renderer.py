from __future__ import annotations

from xml.sax.saxutils import escape

from dancenotation_mcp.ir.catalog import load_symbol_catalog


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


def _symbol_time(symbol: dict) -> tuple[float, float]:
    timing = symbol.get("timing", {})
    measure = max(int(timing.get("measure", 1)), 1)
    beat = float(timing.get("beat", 1.0))
    duration = max(float(timing.get("duration_beats", 1.0)), 0.25)
    start = (measure - 1) * 4 + (beat - 1.0)
    end = start + duration
    return start, end


def _build_lane_positions(staff_left: float) -> dict[str, float]:
    order = BODY_LANES + COLUMN_LANES
    positions: dict[str, float] = {}
    x = staff_left + 26
    for lane in order:
        positions[lane] = x
        x += LANE_WIDTH + LANE_GAP
    return positions


def _measure_count(symbols: list[dict]) -> int:
    if not symbols:
        return 1
    last_end = max(_symbol_time(symbol)[1] for symbol in symbols)
    return max(1, int((last_end + 3.999) // 4))


def _measure_top(measure: int, staff_top: float) -> float:
    return staff_top + (measure - 1) * 4 * BEAT_HEIGHT


def _measure_stack_pressure(symbols: list[dict], catalog: dict[str, dict], measure_count: int) -> dict[int, float]:
    pressure_by_measure: dict[int, float] = {measure: 0.0 for measure in range(1, measure_count + 1)}
    for measure in range(1, measure_count + 1):
        slot_pressure: dict[float, float] = {}
        attachment_pressure = 0.0
        structural_pressure = 0.0
        for symbol in symbols:
            timing = symbol.get("timing", {})
            if max(int(timing.get("measure", 1)), 1) != measure:
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
        pressure_by_measure[measure] = max(slot_pressure.values(), default=0.0) + attachment_pressure + max(0.0, structural_pressure - 1.0)
    return pressure_by_measure


def _measure_vertical_layout(symbols: list[dict], catalog: dict[str, dict], staff_top: float, measure_count: int) -> tuple[dict[int, float], dict[int, float]]:
    extra_gap_after: dict[int, float] = {measure: 0.0 for measure in range(1, measure_count + 1)}
    pressure_by_measure = _measure_stack_pressure(symbols, catalog, measure_count)
    for measure in range(1, measure_count + 1):
        pressure = pressure_by_measure.get(measure, 0.0)
        if pressure >= 8.0:
            extra_gap_after[measure] = min(120.0, 16.0 * (pressure - 7.0))
        if measure < measure_count and measure % SYSTEM_MEASURE_CAPACITY == 0:
            extra_gap_after[measure] += SYSTEM_GAP_Y

    measure_tops: dict[int, float] = {}
    current_top = staff_top
    for measure in range(1, measure_count + 1):
        measure_tops[measure] = current_top
        current_top += (4 * BEAT_HEIGHT) + extra_gap_after.get(measure, 0.0)
    return measure_tops, extra_gap_after


def _measure_zone_y_offset(entry: dict, pressure: float) -> float:
    if pressure < 8.0:
        return 0.0
    family = _entry_family(entry)
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


def _system_layout(measure_count: int, measure_tops: dict[int, float], measure_right_padding: dict[int, float], staff_left: float, lane_right: float) -> list[dict]:
    systems: list[dict] = []
    for system_index, start_measure in enumerate(range(1, measure_count + 1, SYSTEM_MEASURE_CAPACITY), start=1):
        end_measure = min(measure_count, start_measure + SYSTEM_MEASURE_CAPACITY - 1)
        bottom_measure = measure_tops[end_measure] + (4 * BEAT_HEIGHT)
        right_edge = max(lane_right + measure_right_padding.get(measure, 52.0) for measure in range(start_measure, end_measure + 1))
        systems.append(
            {
                "index": system_index,
                "start_measure": start_measure,
                "end_measure": end_measure,
                "top": measure_tops[start_measure],
                "bottom": bottom_measure,
                "right": right_edge,
            }
        )
    return systems


def _entry_family(entry: dict) -> str:
    column = entry.get("column")
    if column:
        return column
    symbol_id = entry.get("symbol", {}).get("symbol_id", "")
    return symbol_id.split(".", 1)[0]


def _preferred_attachment_side(source: dict, target: dict) -> str:
    modifiers = source.get("symbol", {}).get("modifiers", {})
    explicit_side = modifiers.get("attach_side")
    if explicit_side in {"left", "right"}:
        return explicit_side
    preferred_side = source.get("spec", {}).get("behavior", {}).get("preferred_anchor_side")
    if preferred_side in {"left", "right"}:
        return preferred_side
    return "right" if source["x"] > target["x"] else "left"


def _measure_header_text(symbol: dict, spec: dict | None = None) -> str:
    behavior = (spec or {}).get("behavior", {})
    header_role = behavior.get("header_role")
    if header_role == "tempo" or symbol.get("symbol_id", "").endswith("tempo.mark"):
        return f'♩={symbol.get("modifiers", {}).get("tempo", 120)}'
    if header_role == "meter" or ".time." in symbol.get("symbol_id", ""):
        return symbol["symbol_id"].split(".time.", 1)[1].replace("_", "/")
    if header_role == "cadence" or symbol.get("symbol_id", "").endswith("cadence.mark"):
        return "cad"
    return symbol.get("symbol_id", "music").split(".")[-1].replace("_", "/")


def _measure_header_layout(symbols: list[dict], catalog: dict[str, dict]) -> dict[int, dict[str, float]]:
    layout: dict[int, dict[str, float]] = {}
    for symbol in symbols:
        spec = catalog.get(symbol.get("symbol_id", ""), {})
        if not _is_measure_header(symbol, spec):
            continue
        measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        text = _measure_header_text(symbol, spec)
        text_width = max(44.0, (len(text) * 6.6) + 16.0)
        entry = layout.setdefault(measure, {"count": 0.0, "max_text_width": 44.0})
        entry["count"] += 1
        entry["max_text_width"] = max(entry["max_text_width"], text_width)
    return layout


def _header_gutter_width(header_layout: dict[int, dict[str, float]]) -> float:
    if not header_layout:
        return 0.0
    max_band_width = max(entry["max_text_width"] + 12.0 for entry in header_layout.values())
    return max_band_width + 34.0


def _measure_header_corridors(
    header_layout: dict[int, dict[str, float]],
    measure_tops: dict[int, float] | float,
    staff_left: float,
) -> dict[int, dict[str, float]]:
    corridors: dict[int, dict[str, float]] = {}
    if isinstance(measure_tops, (int, float)):
        staff_top = float(measure_tops)
        measure_tops = {measure: _measure_top(measure, staff_top) for measure in header_layout}
    for measure, entry in header_layout.items():
        band_width = entry["max_text_width"] + 12.0
        band_x = staff_left - band_width - 4.0
        band_y = measure_tops[measure] + 4.0
        band_height = max(24.0, (float(entry["count"]) * 22.0) + 8.0)
        corridors[measure] = {
            "left": band_x - 6.0,
            "right": staff_left + 24.0,
            "top": band_y - 6.0,
            "bottom": band_y + band_height + 6.0,
        }
    return corridors


def _measure_right_padding(symbols: list[dict], catalog: dict[str, dict]) -> dict[int, float]:
    complexity: dict[int, float] = {}
    for symbol in symbols:
        measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
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
        complexity[measure] = complexity.get(measure, 0.0) + weight

    padding: dict[int, float] = {}
    for measure, score in complexity.items():
        # Sparse measures get a tighter right envelope; busy ones expand progressively.
        padding[measure] = min(280.0, max(24.0, 24.0 + ((score - 1.5) * 18.0)))
    return padding


def _resolve_lane(symbol: dict, spec: dict) -> str:
    column = spec.get("geometry", {}).get("staff_column")
    if column in COLUMN_LANES:
        return column
    body_part = symbol.get("body_part", "torso")
    if body_part in BODY_LANES:
        return body_part
    return "torso"


def _compute_collision_index(placed: list[dict], lane: str, top: float, bottom: float) -> int:
    overlapping = 0
    for item in placed:
        if item["lane"] != lane:
            continue
        if bottom <= item["top"] or top >= item["bottom"]:
            continue
        overlapping += 1
    return overlapping


def _render_duration_guides(height: float) -> str:
    guides: list[str] = []
    step = BEAT_HEIGHT / 2
    y = step
    while y < height:
        guides.append(
            f'<line x1="-10" y1="{y:.1f}" x2="10" y2="{y:.1f}" '
            'stroke="#dfe4ea" stroke-width="1" stroke-dasharray="3 3"/>'
        )
        y += step
    return "".join(guides)


def _modifier_line_attributes(modifiers: dict) -> tuple[str, str]:
    line_style = modifiers.get("line_style", "single")
    if line_style == "dotted":
        return "3 3", ""
    if line_style == "double_dotted":
        return "3 3", "double"
    if line_style == "double":
        return "", "double"
    return "", ""


def _styled_stroke_attributes(modifiers: dict, stroke_width: float) -> tuple[str, str]:
    dasharray, variant = _modifier_line_attributes(modifiers)
    attrs = f'stroke="#111827" stroke-width="{stroke_width:.1f}"'
    if dasharray:
        attrs += f' stroke-dasharray="{dasharray}"'
    return attrs, variant


def _styled_path_markup(path_d: str, modifiers: dict, stroke_width: float) -> str:
    attrs, variant = _styled_stroke_attributes(modifiers, stroke_width)
    underlay = ""
    if variant == "double":
        underlay = f'<path d="{path_d}" fill="none" stroke="#cbd5e1" stroke-width="{stroke_width + 1.6:.1f}"/>'
    return f'{underlay}<path d="{path_d}" fill="none" {attrs}/>'


def _styled_line_markup(x1: float, y1: float, x2: float, y2: float, modifiers: dict, stroke_width: float) -> str:
    attrs, variant = _styled_stroke_attributes(modifiers, stroke_width)
    underlay = ""
    if variant == "double":
        underlay = f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#cbd5e1" stroke-width="{stroke_width + 1.6:.1f}"/>'
    return f'{underlay}<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" {attrs}/>'


def _render_level_overlays(left: float, top: float, width: float, height: float, modifiers: dict) -> list[str]:
    overlays: list[str] = []
    top_fill = modifiers.get("level_fill_top")
    bottom_fill = modifiers.get("level_fill_bottom")
    if top_fill in LEVEL_STYLES:
        overlays.append(
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{width:.1f}" height="{height * 0.28:.1f}" '
            f'fill="{LEVEL_STYLES[top_fill]["fill"]}" opacity="0.95"/>'
        )
    if bottom_fill in LEVEL_STYLES:
        overlay_top = top + height * 0.72
        overlays.append(
            f'<rect x="{left:.1f}" y="{overlay_top:.1f}" width="{width:.1f}" height="{height * 0.28:.1f}" '
            f'fill="{LEVEL_STYLES[bottom_fill]["fill"]}" opacity="0.95"/>'
        )
    if modifiers.get("whitespace"):
        overlays.append(
            f'<rect x="{left + 2:.1f}" y="{top + height * 0.43:.1f}" width="{width - 4:.1f}" height="{height * 0.14:.1f}" '
            'fill="#ffffff" opacity="0.95"/>'
        )
    return overlays


def _render_surface_marks(left: float, top: float, width: float, height: float, modifiers: dict) -> list[str]:
    marks = modifiers.get("surface_marks", [])
    if not isinstance(marks, list):
        return []
    rendered: list[str] = []
    positions = {
        "left": (left - 6, top + height / 2),
        "right": (left + width + 6, top + height / 2),
        "forward": (left + width / 2, top - 6),
        "backward": (left + width / 2, top + height + 8),
    }
    for mark in marks:
        if mark not in positions:
            continue
        x, y = positions[mark]
        rendered.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#111827"/>')
    return rendered


def _render_degree_badge(left: float, top: float, modifiers: dict) -> str:
    degree = modifiers.get("degree")
    if degree is None:
        return ""
    label = escape(str(degree))
    return (
        f'<g class="degree-badge"><rect x="{left - 2:.1f}" y="{top - 16:.1f}" width="22" height="12" '
        'rx="3" ry="3" fill="#ffffff" stroke="#64748b" stroke-width="1"/>'
        f'<text x="{left + 9:.1f}" y="{top - 7:.1f}" text-anchor="middle" font-size="8" fill="#334155">{label}°</text></g>'
    )


def _render_arrowheads(left: float, top: float, width: float, height: float, modifiers: dict) -> list[str]:
    arrowheads = modifiers.get("arrowheads", {})
    if not isinstance(arrowheads, dict):
        return []
    rendered: list[str] = []
    center_y = top + height / 2
    if arrowheads.get("tail"):
        rendered.append(
            f'<polygon points="{left - 8:.1f},{center_y:.1f} {left - 1:.1f},{center_y - 4:.1f} {left - 1:.1f},{center_y + 4:.1f}" fill="#334155"/>'
        )
    if arrowheads.get("head"):
        right = left + width
        rendered.append(
            f'<polygon points="{right + 8:.1f},{center_y:.1f} {right + 1:.1f},{center_y - 4:.1f} {right + 1:.1f},{center_y + 4:.1f}" fill="#334155"/>'
        )
    return rendered


def _render_jump_supports(left: float, top: float, width: float, height: float, modifiers: dict) -> list[str]:
    support = modifiers.get("spring_jump", {})
    if not isinstance(support, dict):
        return []
    lines: list[str] = []
    takeoff = support.get("takeoff", [])
    landing = support.get("landing", [])
    if "left" in takeoff:
        lines.append(f'<line x1="{left:.1f}" y1="{top + height - 2:.1f}" x2="{left:.1f}" y2="{top + height + 9:.1f}" stroke="#111827" stroke-width="2"/>')
    if "right" in takeoff:
        lines.append(f'<line x1="{left + width:.1f}" y1="{top + height - 2:.1f}" x2="{left + width:.1f}" y2="{top + height + 9:.1f}" stroke="#111827" stroke-width="2"/>')
    if "left" in landing:
        lines.append(f'<line x1="{left:.1f}" y1="{top - 9:.1f}" x2="{left:.1f}" y2="{top + 2:.1f}" stroke="#111827" stroke-width="2"/>')
    if "right" in landing:
        lines.append(f'<line x1="{left + width:.1f}" y1="{top - 9:.1f}" x2="{left + width:.1f}" y2="{top + 2:.1f}" stroke="#111827" stroke-width="2"/>')
    return lines


def _direction_mirror_scale(direction: str | None) -> int:
    if direction in {"left", "diagonal_forward_left", "diagonal_backward_left", "counterclockwise"}:
        return -1
    return 1


def _direction_vertical_bias(direction: str | None) -> float:
    if direction in {"backward", "diagonal_backward_left", "diagonal_backward_right", "low"}:
        return 1.0
    if direction in {"forward", "diagonal_forward_left", "diagonal_forward_right", "high"}:
        return -1.0
    return 0.0


def _render_path_symbol(
    symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict, direction: str | None, spec: dict
) -> str:
    mid_x = left + width / 2
    bottom = top + height
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.5)
    path_width = width * stretch
    path_left = mid_x - path_width / 2
    path_right = mid_x + path_width / 2
    curve_mode = modifiers.get("path_curve", "standard")
    behavior = spec.get("behavior", {})
    path_shape = behavior.get("path_shape", "")
    cap_shape = behavior.get("cap_shape", "flat")
    mirror = _direction_mirror_scale(direction)
    vertical_bias = _direction_vertical_bias(direction) * 4.0
    if path_shape == "spiral" or symbol_id.endswith("spiral"):
        control_left = mid_x + mirror * (-(path_width / 2 + 10))
        control_mid = mid_x + mirror * (-(path_width / 2 + 6))
        control_right = mid_x + mirror * (path_width / 2 + 8)
        return (
            f'<g class="specialized-path" data-shape="spiral" data-subclass="spiral" data-cap-shape="{cap_shape}" data-transition-mark="loop-arrow" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
            f'{_styled_path_markup(f"M {mid_x:.1f} {bottom:.1f} C {control_left:.1f} {top + height * 0.78 + vertical_bias:.1f}, {control_mid:.1f} {top + height * 0.22 + vertical_bias:.1f}, {mid_x:.1f} {top + height * 0.22:.1f} S {control_right:.1f} {top + height * 0.72 + vertical_bias:.1f}, {mid_x:.1f} {top + height * 0.44:.1f}", modifiers, 1.8)}'
            f'<polygon points="{mid_x + mirror * 7:.1f},{top + height * 0.44:.1f} {mid_x + mirror * 1:.1f},{top + height * 0.40:.1f} {mid_x + mirror * 2:.1f},{top + height * 0.50:.1f}" fill="#111827"/>'
            "</g>"
        )
    if path_shape == "circle" or symbol_id.endswith("circle"):
        radius_x = max(path_width / 2 - 3, 6)
        radius_y = max(height / 2 - 4, 6)
        arrow_x = mid_x + mirror * radius_x
        arrow_y = top + height / 2 + vertical_bias
        return (
            f'<g class="specialized-path" data-shape="circle" data-subclass="circle" data-cap-shape="{cap_shape}" data-transition-mark="closed-loop" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
            f'<ellipse cx="{mid_x:.1f}" cy="{top + height / 2:.1f}" rx="{radius_x:.1f}" ry="{radius_y:.1f}" fill="none" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{arrow_x:.1f},{arrow_y:.1f} {arrow_x - mirror * 6:.1f},{arrow_y - 4:.1f} {arrow_x - mirror * 6:.1f},{arrow_y + 4:.1f}" fill="#111827"/>'
            "</g>"
        )
    if path_shape == "curved" or symbol_id.endswith("curved") or curve_mode == "curved":
        control_a = mid_x + mirror * (-(path_width / 2 + 10))
        control_b = mid_x + mirror * (path_width / 2 + 10)
        return (
            f'<g class="specialized-path" data-shape="curved" data-subclass="curved" data-cap-shape="{cap_shape}" data-transition-mark="sweep" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
            f'{_styled_path_markup(f"M {mid_x:.1f} {bottom:.1f} C {control_a:.1f} {top + height * 0.68 + vertical_bias:.1f}, {control_b:.1f} {top + height * 0.34 + vertical_bias:.1f}, {mid_x:.1f} {top:.1f}", modifiers, 1.8)}'
            f'<polygon points="{mid_x:.1f},{top + 1:.1f} {mid_x - mirror * 5:.1f},{top + 9:.1f} {mid_x + mirror * 3:.1f},{top + 10:.1f}" fill="#111827"/>'
            "</g>"
        )
    body_top = top + 8.0
    body_bottom = bottom - 8.0
    cap_shift = mirror * 3.0
    return (
        f'<g class="specialized-path" data-shape="straight" data-subclass="straight" data-cap-shape="{cap_shape}" data-stretch-mode="cap-body-cap" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
        f'{_styled_line_markup(mid_x, body_bottom, mid_x, body_top, modifiers, 1.4 * stretch)}'
        f'<line x1="{mid_x - 4 + cap_shift:.1f}" y1="{bottom:.1f}" x2="{mid_x + 4 + cap_shift:.1f}" y2="{bottom:.1f}" stroke="#111827" stroke-width="1.4"/>'
        f'<line x1="{mid_x - 4 - cap_shift:.1f}" y1="{top:.1f}" x2="{mid_x + 4 - cap_shift:.1f}" y2="{top:.1f}" stroke="#111827" stroke-width="1.4"/>'
        "</g>"
    )


def _render_turn_symbol(
    symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict, direction: str | None
) -> str:
    center_x = left + width / 2
    center_y = top + height / 2
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    radius_x = max((width / 2 - 4) * stretch, 6)
    radius_y = max(height / 2 - 4, 6)
    turn_direction = modifiers.get("turn_direction")
    if not turn_direction:
        turn_direction = "ccw" if direction == "counterclockwise" else "cw"
    sweep = 1 if turn_direction != "ccw" else 0
    rotation = float(modifiers.get("rotation", 0))
    degree = float(modifiers.get("degree", 0) or 0)
    spin_variant = symbol_id.endswith("spin") or degree >= 360
    echo_arc = ""
    pivot_axis = ""
    if spin_variant:
        echo_arc = (
            f'<path d="M {center_x - (radius_x - 5):.1f} {center_y + 6:.1f} '
            f'A {max(radius_x - 5, 4):.1f} {max(radius_y - 5, 4):.1f} 0 1 {sweep} {center_x + (radius_x - 5):.1f} {center_y + 6:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.2" stroke-dasharray="3 2"/>'
        )
    else:
        pivot_axis = (
            f'<line x1="{center_x:.1f}" y1="{center_y - radius_y + 2:.1f}" x2="{center_x:.1f}" y2="{center_y + radius_y - 2:.1f}" stroke="#64748b" stroke-width="1.1" stroke-dasharray="2 2"/>'
            f'<circle cx="{center_x:.1f}" cy="{center_y + radius_y - 1:.1f}" r="2.1" fill="#64748b"/>'
        )
    return (
        f'<g class="specialized-turn" data-variant="{"spin" if spin_variant else "pivot"}" data-subclass="{"spin" if spin_variant else "pivot"}" data-direction="{direction or "place"}" data-turn-direction="{turn_direction}" transform="rotate({rotation:.1f} {center_x:.1f} {center_y:.1f})">'
        f'{_styled_path_markup(f"M {center_x - radius_x:.1f} {center_y:.1f} A {radius_x:.1f} {radius_y:.1f} 0 1 {sweep} {center_x + radius_x:.1f} {center_y:.1f}", modifiers, 1.8)}'
        f'{pivot_axis}'
        f'{echo_arc}'
        f'<polygon points="{center_x + (radius_x + 7 if sweep else -(radius_x + 7)):.1f},{center_y:.1f} {center_x + (radius_x - 1 if sweep else -(radius_x - 1)):.1f},{center_y - 5:.1f} {center_x + (radius_x - 1 if sweep else -(radius_x - 1)):.1f},{center_y + 5:.1f}" fill="#111827"/>'
        "</g>"
    )


def _render_jump_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    bottom = top + height - 4
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    apex = top - 8 - (height * 0.15 * (stretch - 1))
    left_x = mid_x - (width * stretch / 2) + 2
    right_x = mid_x + (width * stretch / 2) - 2
    inner_arc = ""
    landing_mark = ""
    spring_coil = ""
    subclass = "spring" if symbol_id.endswith("spring") else "small" if symbol_id.endswith("small") else "stretched" if stretch >= 1.35 else "compact"
    takeoff_mark = ""
    if stretch >= 1.35 or symbol_id.endswith("small") or symbol_id.endswith("spring"):
        inner_arc = (
            f'<path d="M {left_x + 4:.1f} {bottom - 8:.1f} Q {mid_x:.1f} {apex + 10:.1f} {right_x - 4:.1f} {bottom - 8:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.1" stroke-dasharray="4 3"/>'
        )
        landing_mark = (
            f'<line x1="{right_x - 3:.1f}" y1="{bottom - 3:.1f}" x2="{right_x + 5:.1f}" y2="{bottom - 9:.1f}" stroke="#111827" stroke-width="1.2"/>'
        )
        takeoff_mark = (
            f'<line x1="{left_x - 5:.1f}" y1="{bottom - 2:.1f}" x2="{left_x + 2:.1f}" y2="{bottom - 8:.1f}" stroke="#111827" stroke-width="1.2"/>'
        )
    if symbol_id.endswith("spring"):
        spring_coil = (
            f'<path d="M {mid_x - 8:.1f} {bottom + 4:.1f} q 3 -6 6 0 q 3 6 6 0 q 3 -6 6 0" fill="none" stroke="#64748b" stroke-width="1.2"/>'
        )
    return (
        f'<g class="specialized-jump" data-variant="{"stretched" if stretch >= 1.35 else "compact"}" data-subclass="{subclass}">'
        f'{_styled_path_markup(f"M {left_x:.1f} {bottom:.1f} Q {mid_x:.1f} {apex:.1f} {right_x:.1f} {bottom:.1f}", modifiers, 1.8)}'
        f'{inner_arc}'
        f'{takeoff_mark}'
        f'{spring_coil}'
        f'<line x1="{mid_x:.1f}" y1="{top + 6:.1f}" x2="{mid_x:.1f}" y2="{bottom - 8:.1f}" stroke="#111827" stroke-width="1.2"/>'
        f'{landing_mark}'
        "</g>"
    )


def _render_pin_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    pin_scale = max(float(modifiers.get("pin_length", 1.0)), 0.6)
    pin_bottom = top + min(height * pin_scale, height + 8)
    head_style = modifiers.get("pin_head", "circle")
    hold_bar = ""
    variant = "entry" if symbol_id.endswith("entry") else "floorplan-exit" if symbol_id.endswith("floorplan_exit") else "hold" if symbol_id.endswith("hold") else "standard"
    if symbol_id.endswith("hold"):
        hold_y = top + max(height * 0.34, 12)
        hold_bar = (
            f'<line x1="{mid_x - 7:.1f}" y1="{hold_y:.1f}" x2="{mid_x + 7:.1f}" y2="{hold_y:.1f}" stroke="#64748b" stroke-width="1.6"/>'
        )
    if symbol_id.endswith("floorplan_exit"):
        head_style = "diamond"
        hold_bar = (
            f'<path d="M {mid_x - 6:.1f} {top + 10:.1f} L {mid_x + 3:.1f} {top + 16:.1f} L {mid_x - 6:.1f} {top + 22:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.3"/>'
        )
    head = (
        f'<circle cx="{mid_x:.1f}" cy="{top + 5:.1f}" r="3.2" fill="#111827"/>'
        if head_style != "diamond"
        else f'<polygon points="{mid_x:.1f},{top + 1:.1f} {mid_x - 4:.1f},{top + 5:.1f} {mid_x:.1f},{top + 9:.1f} {mid_x + 4:.1f},{top + 5:.1f}" fill="#111827"/>'
    )
    tip = (
        f'<polygon points="{mid_x + 6:.1f},{pin_bottom - 3:.1f} {mid_x - 1:.1f},{pin_bottom - 11:.1f} {mid_x + 3:.1f},{pin_bottom - 17:.1f}" fill="#111827"/>'
        if symbol_id.endswith("floorplan_exit")
        else f'<polygon points="{mid_x:.1f},{pin_bottom + 2:.1f} {mid_x - 5:.1f},{pin_bottom - 8:.1f} {mid_x + 5:.1f},{pin_bottom - 8:.1f}" fill="#111827"/>'
    )
    return (
        f'<g class="specialized-pin" data-variant="{variant}">'
        f'<line x1="{mid_x:.1f}" y1="{top + 2:.1f}" x2="{mid_x:.1f}" y2="{pin_bottom - 9:.1f}" stroke="#111827" stroke-width="1.8"/>'
        f'{hold_bar}'
        f'{head}'
        f'{tip}'
        "</g>"
    )


def _render_repeat_symbol(symbol_id: str, left: float, top: float, width: float, height: float, doubled: bool, modifiers: dict, spec: dict) -> str:
    x1 = left + width * 0.38
    x2 = left + width * 0.62
    bars = [x1, x2] if doubled else [left + width / 2]
    dots = []
    repeat_count = max(int(modifiers.get("repeat_count", 1)), 1)
    for x in bars:
        for idx in range(repeat_count):
            y = top + height * (0.28 + idx * min(0.16, 0.5 / repeat_count))
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="#111827"/>')
    opening_bar = ""
    closing_bar = ""
    behavior = spec.get("behavior", {})
    boundary_role = behavior.get("boundary_role")
    if boundary_role == "opening" or symbol_id.endswith("start"):
        opening_bar = (
            f'<line x1="{left + 2:.1f}" y1="{top + 2:.1f}" x2="{left + 2:.1f}" y2="{top + height - 2:.1f}" stroke="#111827" stroke-width="2.0"/>'
            f'<line x1="{left + 6:.1f}" y1="{top + 4:.1f}" x2="{left + 6:.1f}" y2="{top + height - 4:.1f}" stroke="#111827" stroke-width="1.2"/>'
        )
    if modifiers.get("repeat_end") or boundary_role == "closing" or symbol_id.endswith("end") or symbol_id.endswith("double"):
        closing_bar = (
            f'<line x1="{left + width - 2:.1f}" y1="{top + 2:.1f}" x2="{left + width - 2:.1f}" y2="{top + height - 2:.1f}" stroke="#111827" stroke-width="2.0"/>'
            f'<line x1="{left + width - 6:.1f}" y1="{top + 4:.1f}" x2="{left + width - 6:.1f}" y2="{top + height - 4:.1f}" stroke="#111827" stroke-width="1.2"/>'
        )
    variant = "double" if doubled else "start" if boundary_role == "opening" or symbol_id.endswith("start") else "end" if boundary_role == "closing" or symbol_id.endswith("end") else "single"
    return f'<g class="specialized-repeat" data-kind="{variant}" data-repeat-count="{repeat_count}">{opening_bar}{"".join(dots)}{closing_bar}</g>'


def _render_music_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    header_role = modifiers.get("_header_role")
    if header_role == "tempo" or symbol_id.endswith("tempo.mark"):
        tempo = escape(str(modifiers.get("tempo", 120)))
        capsule_width = max(26.0, len(tempo) * 6.5 + 18.0)
        capsule_x = mid_x - capsule_width / 2 + 6.0
        return (
            f'<g class="specialized-music" data-kind="tempo">'
            f'<ellipse cx="{left + 7:.1f}" cy="{top + height * 0.50:.1f}" rx="3.4" ry="4.8" fill="#111827"/>'
            f'<line x1="{left + 10:.1f}" y1="{top + height * 0.50:.1f}" x2="{left + 10:.1f}" y2="{top + 4:.1f}" stroke="#111827" stroke-width="1.4"/>'
            f'<path d="M {left + 10:.1f} {top + 4:.1f} Q {left + 17:.1f} {top + 7:.1f} {left + 12:.1f} {top + 12:.1f}" fill="none" stroke="#111827" stroke-width="1.2"/>'
            f'<rect x="{capsule_x:.1f}" y="{top + 5:.1f}" width="{capsule_width:.1f}" height="{height - 10:.1f}" rx="8" ry="8" fill="#f8fafc" stroke="#64748b" stroke-width="1.1"/>'
            f'<text x="{capsule_x + capsule_width / 2:.1f}" y="{top + height * 0.58:.1f}" text-anchor="middle" class="music-label" font-size="8.5" fill="#111827">{tempo}</text>'
            "</g>"
        )
    if header_role == "meter" or ".time." in symbol_id:
        parts = symbol_id.split(".time.", 1)[1].split("_")
        return (
            f'<g class="specialized-music" data-kind="time-signature">'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.38:.1f}" text-anchor="middle" font-size="9" fill="#111827">{parts[0]}</text>'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.72:.1f}" text-anchor="middle" font-size="9" fill="#111827">{parts[1]}</text>'
            "</g>"
        )
    if header_role == "cadence" or symbol_id.endswith("cadence.mark"):
        label = escape(str(modifiers.get("label", "cad.")))
        ribbon_width = max(width + 6.0, len(label) * 5.6 + 18.0)
        ribbon_left = mid_x - ribbon_width / 2
        return (
            f'<g class="specialized-music" data-kind="cadence">'
            f'<path d="M {ribbon_left:.1f} {top + 6:.1f} L {ribbon_left + ribbon_width:.1f} {top + 6:.1f} L {ribbon_left + ribbon_width - 8:.1f} {top + height - 8:.1f} L {mid_x:.1f} {top + height - 3:.1f} L {ribbon_left + 8:.1f} {top + height - 8:.1f} Z" '
            'fill="#eff6ff" stroke="#111827" stroke-width="1.2"/>'
            f'<path d="M {left + 4:.1f} {top + height * 0.72:.1f} Q {mid_x:.1f} {top + height * 0.40:.1f} {left + width - 4:.1f} {top + height * 0.72:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.1"/>'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.50:.1f}" text-anchor="middle" class="music-label" font-size="8" fill="#111827">{label}</text>'
            "</g>"
        )
    rest_height = max(float(modifiers.get("rest_height", 1.0)), 0.6)
    if symbol_id.endswith("rest.eighth"):
        return (
            f'<g class="specialized-music" data-kind="rest-eighth">'
            f'<path d="M {mid_x - 1:.1f} {top + 4:.1f} Q {mid_x + 5:.1f} {top + height * 0.28 * rest_height:.1f} {mid_x:.1f} {top + height * 0.52:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<line x1="{mid_x:.1f}" y1="{top + height * 0.52:.1f}" x2="{mid_x - 5:.1f}" y2="{top + height - 4:.1f}" stroke="#111827" stroke-width="1.6"/>'
            f'<circle cx="{mid_x - 5:.1f}" cy="{top + height - 4:.1f}" r="2.2" fill="#111827"/>'
            "</g>"
        )
    if symbol_id.endswith("rest.sixteenth"):
        return (
            f'<g class="specialized-music" data-kind="rest-sixteenth">'
            f'<path d="M {mid_x - 1:.1f} {top + 4:.1f} Q {mid_x + 5:.1f} {top + height * 0.24 * rest_height:.1f} {mid_x:.1f} {top + height * 0.46:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<line x1="{mid_x:.1f}" y1="{top + height * 0.46:.1f}" x2="{mid_x - 5:.1f}" y2="{top + height * 0.72:.1f}" stroke="#111827" stroke-width="1.4"/>'
            f'<line x1="{mid_x + 1:.0f}" y1="{top + height * 0.56:.1f}" x2="{mid_x - 4:.1f}" y2="{top + height - 4:.1f}" stroke="#111827" stroke-width="1.4"/>'
            f'<circle cx="{mid_x - 5:.1f}" cy="{top + height * 0.72:.1f}" r="2.0" fill="#111827"/>'
            f'<circle cx="{mid_x - 4:.1f}" cy="{top + height - 4:.1f}" r="2.0" fill="#111827"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-music" data-kind="rest-quarter">'
        f'<path d="M {mid_x - 2:.1f} {top + 4:.1f} Q {mid_x + 5:.1f} {top + height * 0.32 * rest_height:.1f} {mid_x - 1:.1f} {top + height * 0.58:.1f} '
        f'Q {mid_x - 7:.1f} {top + height * 0.82:.1f} {mid_x + 2:.1f} {top + height - 3:.1f}" '
        'fill="none" stroke="#111827" stroke-width="1.7"/>'
        f'<circle cx="{mid_x + 2:.1f}" cy="{top + height - 3:.1f}" r="2.4" fill="#111827"/>'
        "</g>"
    )


def _render_separator_symbol(left: float, top: float, width: float, height: float, flipped: bool, modifiers: dict) -> str:
    bar_x = left + width / 2
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    hook_offset = 8 * stretch
    hook_x = bar_x - hook_offset if flipped else bar_x + hook_offset
    if modifiers.get("separator_mode") == "single":
        return (
            f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}" data-mode="single">'
            f'<line x1="{bar_x:.1f}" y1="{top:.1f}" x2="{bar_x:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="2.2"/>'
            "</g>"
        )
    if modifiers.get("separator_mode") == "double":
        return (
            f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}" data-mode="double">'
            f'<line x1="{bar_x - 3:.1f}" y1="{top:.1f}" x2="{bar_x - 3:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<line x1="{bar_x + 3:.1f}" y1="{top:.1f}" x2="{bar_x + 3:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="1.8"/>'
            "</g>"
        )
    if modifiers.get("separator_mode") == "final":
        return (
            f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}" data-mode="final">'
            f'<line x1="{bar_x - 4:.1f}" y1="{top:.1f}" x2="{bar_x - 4:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="1.4"/>'
            f'<line x1="{bar_x + 2:.1f}" y1="{top:.1f}" x2="{bar_x + 2:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="3.0"/>'
            f'<line x1="{bar_x - 10:.1f}" y1="{top + 5:.1f}" x2="{bar_x + 8:.1f}" y2="{top + 5:.1f}" stroke="#64748b" stroke-width="1.0"/>'
            f'<line x1="{bar_x - 10:.1f}" y1="{top + height - 5:.1f}" x2="{bar_x + 8:.1f}" y2="{top + height - 5:.1f}" stroke="#64748b" stroke-width="1.0"/>'
            "</g>"
        )
    if modifiers.get("separator_mode") == "hook":
        hook_tip_x = bar_x + 9 if not flipped else bar_x - 9
        return (
            f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}" data-mode="hook">'
            f'<line x1="{bar_x:.1f}" y1="{top:.1f}" x2="{bar_x:.1f}" y2="{top + height - 8:.1f}" stroke="#111827" stroke-width="2.0"/>'
            f'<path d="M {bar_x:.1f} {top + height - 8:.1f} Q {bar_x:.1f} {top + height:.1f} {hook_tip_x:.1f} {top + height - 2:.1f}" fill="none" stroke="#111827" stroke-width="1.4"/>'
            "</g>"
        )
    body_top = top + 8.0
    body_bottom = top + height - 8.0
    return (
        f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}" data-stretch-mode="cap-body-cap">'
        f'<line x1="{bar_x:.1f}" y1="{body_top:.1f}" x2="{bar_x:.1f}" y2="{body_bottom:.1f}" stroke="#111827" stroke-width="2.2"/>'
        f'<line x1="{bar_x:.1f}" y1="{top:.1f}" x2="{hook_x:.1f}" y2="{top:.1f}" stroke="#111827" stroke-width="1.4"/>'
        f'<line x1="{bar_x:.1f}" y1="{top + height:.1f}" x2="{hook_x:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="1.4"/>'
        "</g>"
    )


def _is_measure_boundary_separator(symbol: dict, spec: dict) -> bool:
    if spec.get("geometry", {}).get("staff_column") != "separator":
        return False
    timing = symbol.get("timing", {})
    beat = float(timing.get("beat", 1.0))
    duration = float(timing.get("duration_beats", 1.0))
    return abs(beat - 1.0) < 0.01 and duration >= 1.0


def _render_motif_symbol(
    symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict, direction: str | None
) -> str:
    mid_x = left + width / 2
    rotation = float(modifiers.get("rotation", 0))
    mirror = _direction_mirror_scale(direction)
    if symbol_id.endswith("rise_fall"):
        kind = "rise-fall"
        content = (
            f'<path d="M {mid_x - 6:.1f} {top + height - 3:.1f} Q {mid_x - 2 + mirror * 2:.1f} {top + 4:.1f} {mid_x:.1f} {top + height / 2:.1f} '
            f'Q {mid_x + 2 + mirror * 2:.1f} {top + height - 6:.1f} {mid_x + 6:.1f} {top + 5:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.7"/>'
        )
    elif symbol_id.endswith("arc"):
        kind = "arc"
        content = (
            f'<path d="M {left + 3:.1f} {top + height * 0.72:.1f} Q {mid_x + mirror * 4:.1f} {top + 2:.1f} {left + width - 3:.1f} {top + height * 0.72:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.8"/>'
        )
    elif symbol_id.endswith("fall"):
        kind = "fall"
        content = (
            f'<line x1="{mid_x:.1f}" y1="{top + 4:.1f}" x2="{mid_x + mirror * 2:.1f}" y2="{top + height - 7:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{mid_x + mirror * 2:.1f},{top + height + 1:.1f} {mid_x - 5 + mirror * 2:.1f},{top + height - 8:.1f} {mid_x + 5 + mirror * 2:.1f},{top + height - 8:.1f}" fill="#111827"/>'
        )
    else:
        kind = "rise"
        content = (
            f'<line x1="{mid_x:.1f}" y1="{top + height - 4:.1f}" x2="{mid_x + mirror * 2:.1f}" y2="{top + 8:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{mid_x + mirror * 2:.1f},{top + 1:.1f} {mid_x - 5 + mirror * 2:.1f},{top + 10:.1f} {mid_x + 5 + mirror * 2:.1f},{top + 10:.1f}" fill="#111827"/>'
        )
    return (
        f'<g class="specialized-motif" data-kind="{kind}" data-direction="{direction or "place"}" '
        f'data-mirrored="{str(mirror < 0).lower()}" transform="rotate({rotation:.1f} {mid_x:.1f} {top + height / 2:.1f})">{content}</g>'
    )


def _render_surface_symbol(left: float, top: float, width: float, height: float, symbol_id: str, direction: str | None) -> str:
    mid_x = left + width / 2
    mid_y = top + height / 2
    mirror = _direction_mirror_scale(direction)
    vertical_bias = _direction_vertical_bias(direction) * 2.0
    if symbol_id.endswith("brush"):
        return (
            f'<g class="specialized-surface" data-kind="brush" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
            f'<path d="M {left + 2:.1f} {mid_y - 3 + vertical_bias:.1f} Q {mid_x + mirror * 4:.1f} {mid_y - 8 + vertical_bias:.1f} {left + width - 2:.1f} {mid_y - 3 + vertical_bias:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<path d="M {left + 2:.1f} {mid_y + 3 + vertical_bias:.1f} Q {mid_x + mirror * 4:.1f} {mid_y - 2 + vertical_bias:.1f} {left + width - 2:.1f} {mid_y + 3 + vertical_bias:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            "</g>"
        )
    if symbol_id.endswith("glide"):
        return (
            f'<g class="specialized-surface" data-kind="glide" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
            f'<path d="M {left + 2:.1f} {mid_y + 2 + vertical_bias:.1f} Q {mid_x + mirror * 5:.1f} {mid_y - 6 + vertical_bias:.1f} {left + width - 2:.1f} {mid_y + 2 + vertical_bias:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<line x1="{left + 4:.1f}" y1="{mid_y + 5 + vertical_bias:.1f}" x2="{left + width - 4:.1f}" y2="{mid_y + 5 + vertical_bias:.1f}" stroke="#111827" stroke-width="1.2"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-surface" data-kind="contact" data-direction="{direction or "place"}" data-mirrored="{str(mirror < 0).lower()}">'
        f'<circle cx="{mid_x:.1f}" cy="{mid_y:.1f}" r="5.5" fill="none" stroke="#111827" stroke-width="1.6"/>'
        f'<circle cx="{mid_x:.1f}" cy="{mid_y:.1f}" r="2.2" fill="#111827"/>'
        "</g>"
    )


def _render_space_symbol(left: float, top: float, width: float, height: float, symbol_id: str, modifiers: dict) -> str:
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    if symbol_id.endswith("whitespace"):
        line_y = top + height / 2
        body_left = left + 4.0
        body_right = left + max(width * stretch - 4, 12)
        return (
            f'<g class="specialized-space" data-kind="whitespace" data-stretch-mode="cap-body-cap">'
            f'<rect x="{body_left:.1f}" y="{top + 6:.1f}" width="{body_right - body_left:.1f}" height="{height - 12:.1f}" fill="#ffffff" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
            f'<line x1="{body_left:.1f}" y1="{line_y:.1f}" x2="{body_right:.1f}" y2="{line_y:.1f}" stroke="#cbd5e1" stroke-width="1.0" stroke-dasharray="4 3"/>'
            "</g>"
        )
    if symbol_id.endswith("transition"):
        line_y = top + height / 2
        body_left = left + 8.0
        body_right = left + max(width * stretch - 8, 10)
        return (
            f'<g class="specialized-space" data-kind="transition" data-stretch-mode="cap-body-cap">'
            f'<line x1="{left + 2:.1f}" y1="{line_y:.1f}" x2="{body_left:.1f}" y2="{line_y:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
            f'<line x1="{body_left:.1f}" y1="{line_y:.1f}" x2="{body_right:.1f}" y2="{line_y:.1f}" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="5 4"/>'
            f'<line x1="{body_right:.1f}" y1="{line_y:.1f}" x2="{left + width * stretch - 2:.1f}" y2="{line_y:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
            "</g>"
        )
    body_width = max(width * stretch - 12, 8)
    return (
        f'<g class="specialized-space" data-kind="hold" data-stretch-mode="cap-body-cap">'
        f'<line x1="{left + 2:.1f}" y1="{top + 3:.1f}" x2="{left + 6:.1f}" y2="{top + 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<line x1="{left + 2:.1f}" y1="{top + height - 3:.1f}" x2="{left + 6:.1f}" y2="{top + height - 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<line x1="{left + 2:.1f}" y1="{top + 3:.1f}" x2="{left + 2:.1f}" y2="{top + height - 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<rect x="{left + 6:.1f}" y="{top + 3:.1f}" width="{body_width:.1f}" height="{height - 6:.1f}" fill="none" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<line x1="{left + 6 + body_width:.1f}" y1="{top + 3:.1f}" x2="{left + 10 + body_width:.1f}" y2="{top + 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<line x1="{left + 6 + body_width:.1f}" y1="{top + height - 3:.1f}" x2="{left + 10 + body_width:.1f}" y2="{top + height - 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        f'<line x1="{left + 10 + body_width:.1f}" y1="{top + 3:.1f}" x2="{left + 10 + body_width:.1f}" y2="{top + height - 3:.1f}" stroke="#94a3b8" stroke-width="1.4"/>'
        "</g>"
    )


def _render_bow_symbol(symbol_id: str, left: float, top: float, width: float, height: float) -> str:
    mid_x = left + width / 2
    mid_y = top + height / 2
    if symbol_id.endswith("hook"):
        return (
            f'<g class="specialized-bow" data-kind="hook">'
            f'<path d="M {left + 3:.1f} {mid_y:.1f} Q {mid_x:.1f} {top + 3:.1f} {left + width - 5:.1f} {mid_y:.1f}" fill="none" stroke="#111827" stroke-width="1.7"/>'
            f'<path d="M {left + width - 5:.1f} {mid_y:.1f} Q {left + width + 1:.1f} {mid_y + 4:.1f} {left + width - 4:.1f} {top + height - 2:.1f}" fill="none" stroke="#111827" stroke-width="1.4"/>'
            "</g>"
        )
    if symbol_id.endswith("vertical"):
        return (
            f'<g class="specialized-bow" data-kind="vertical">'
            f'<path d="M {mid_x - 4:.1f} {top + 2:.1f} Q {mid_x + 6:.1f} {mid_y:.1f} {mid_x - 4:.1f} {top + height - 2:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.8"/>'
            "</g>"
        )
    if symbol_id.endswith("small"):
        return (
            f'<g class="specialized-bow" data-kind="small">'
            f'<path d="M {left + 3:.1f} {mid_y + 1:.1f} Q {mid_x:.1f} {top + 4:.1f} {left + width - 3:.1f} {mid_y + 1:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.4"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-bow" data-kind="horizontal">'
        f'<path d="M {left + 2:.1f} {mid_y + 2:.1f} Q {mid_x:.1f} {top + 2:.1f} {left + width - 2:.1f} {mid_y + 2:.1f}" '
        'fill="none" stroke="#111827" stroke-width="1.8"/>'
        "</g>"
    )


def _render_dynamic_symbol(symbol_id: str, left: float, top: float, width: float, height: float) -> str:
    mid_y = top + height / 2
    if symbol_id.endswith("diminuendo"):
        return (
            f'<g class="specialized-dynamic" data-kind="diminuendo">'
            f'<path d="M {left + width - 2:.1f} {mid_y - 5:.1f} L {left + 2:.1f} {mid_y:.1f} L {left + width - 2:.1f} {mid_y + 5:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-dynamic" data-kind="accent">'
        f'<path d="M {left + 2:.1f} {mid_y - 5:.1f} L {left + width - 2:.1f} {mid_y:.1f} L {left + 2:.1f} {mid_y + 5:.1f}" '
        'fill="none" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/>'
        "</g>"
    )


def _render_adlib_symbol(symbol_id: str, left: float, top: float, width: float, height: float) -> str:
    mid_x = left + width / 2
    if symbol_id.endswith("vertical"):
        return (
            f'<g class="specialized-adlib" data-kind="vertical">'
            f'<path d="M {mid_x:.1f} {top + 2:.1f} C {mid_x + 4:.1f} {top + 5:.1f}, {mid_x - 4:.1f} {top + 9:.1f}, {mid_x:.1f} {top + 12:.1f} '
            f'S {mid_x + 4:.1f} {top + 18:.1f}, {mid_x:.1f} {top + height - 2:.1f}" fill="none" stroke="#111827" stroke-width="1.5"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-adlib" data-kind="horizontal">'
        f'<path d="M {left + 2:.1f} {top + height / 2:.1f} C {left + 5:.1f} {top + 2:.1f}, {left + 9:.1f} {top + height - 2:.1f}, {mid_x:.1f} {top + height / 2:.1f} '
        f'S {left + width - 5:.1f} {top + 2:.1f}, {left + width - 2:.1f} {top + height / 2:.1f}" fill="none" stroke="#111827" stroke-width="1.5"/>'
        "</g>"
    )


def _render_specialized_symbol(symbol: dict, spec: dict, left: float, top: float, width: float, height: float) -> str:
    column = spec.get("geometry", {}).get("staff_column")
    symbol_id = symbol.get("symbol_id", "")
    modifiers = symbol.get("modifiers", {})
    direction = symbol.get("direction")
    if column == "path":
        return _render_path_symbol(symbol_id, left, top, width, height, modifiers, direction, spec)
    if column == "turn":
        return _render_turn_symbol(symbol_id, left, top, width, height, modifiers, direction)
    if column == "jump":
        return _render_jump_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "pin":
        if symbol_id.endswith("entry"):
            modifiers = {**modifiers, "pin_head": "diamond"}
        return _render_pin_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "repeat":
        if symbol_id.endswith("end"):
            modifiers = {**modifiers, "repeat_end": True}
        return _render_repeat_symbol(symbol_id, left, top, width, height, symbol_id.endswith("double"), modifiers, spec)
    if column == "music":
        header_role = spec.get("behavior", {}).get("header_role")
        if header_role:
            modifiers = {**modifiers, "_header_role": header_role}
        return _render_music_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "motif":
        return _render_motif_symbol(symbol_id, left, top, width, height, modifiers, direction)
    if column == "surface":
        return _render_surface_symbol(left, top, width, height, symbol_id, direction)
    if column == "space":
        return _render_space_symbol(left, top, width, height, symbol_id, modifiers)
    if column == "bow":
        return _render_bow_symbol(symbol_id, left, top, width, height)
    if column == "dynamic":
        return _render_dynamic_symbol(symbol_id, left, top, width, height)
    if column == "adlib":
        return _render_adlib_symbol(symbol_id, left, top, width, height)
    if column == "separator":
        if symbol_id.endswith("single"):
            modifiers = {**modifiers, "separator_mode": "single"}
        elif symbol_id.endswith("double"):
            modifiers = {**modifiers, "separator_mode": "double"}
        elif symbol_id.endswith("final"):
            modifiers = {**modifiers, "separator_mode": "final"}
        elif symbol_id.endswith("hook"):
            modifiers = {**modifiers, "separator_mode": "hook"}
        return _render_separator_symbol(left, top, width, height, symbol_id.endswith("flipped"), modifiers)
    return ""


def _render_symbol_block(symbol: dict, spec: dict, x: float, top: float, height: float) -> str:
    geom = spec.get("geometry", {})
    modifiers = symbol.get("modifiers", {})
    symbol_id = escape(symbol.get("symbol_id", "unknown"))
    glyph = escape(geom.get("glyph") or DIRECTION_GLYPH.get(symbol.get("direction", "place"), "◆"))
    level = symbol.get("level") or "middle"
    style = LEVEL_STYLES.get(level, LEVEL_STYLES["middle"])
    body_part = escape(symbol.get("body_part", "torso").replace("_", " "))
    direction = symbol.get("direction")
    direction_glyph = escape(DIRECTION_GLYPH.get(direction, "")) if direction else ""
    width = max(int(geom.get("width", 20)), 18)
    block_width = max(width + 16, 30)
    left = x - block_width / 2
    text_color = "#ffffff" if level == "low" else "#1f2933"
    stroke = "#1f2933"
    dasharray, border_mode = _modifier_line_attributes(modifiers)
    specialized = _render_specialized_symbol(symbol, spec, left, top, block_width, height)

    annotations: list[str] = []
    anchor = geom.get("anchor", "center")
    annotation_x = left + block_width + ANNOTATION_GAP
    if anchor == "adjacent":
        if direction_glyph:
            annotations.append(
                f'<text x="{annotation_x:.1f}" y="{top + 14:.1f}" class="adjacent-mark" '
                f'font-size="{ANNOTATION_WIDTH}" fill="#374151">{direction_glyph}</text>'
            )
        annotations.append(
            f'<text x="{annotation_x:.1f}" y="{top + height - 6:.1f}" class="adjacent-mark" '
            f'font-size="8" fill="#6b7280">{escape(style["label"])}</text>'
        )
    else:
        annotations.append(
            f'<text x="{x:.1f}" y="{top - 6:.1f}" text-anchor="middle" class="body-label" '
            f'font-size="8" fill="#6b7280">{body_part}</text>'
        )
        if direction_glyph:
            annotations.append(
                f'<text x="{x:.1f}" y="{top + 13:.1f}" text-anchor="middle" class="direction-mark" '
                f'font-size="10" fill="#6b7280">{direction_glyph}</text>'
            )

    return "\n".join(
        [
            f'<g class="symbol-block level-{escape(level)}" data-symbol-id="{symbol_id}">',
            f'<rect x="{left:.1f}" y="{top:.1f}" width="{block_width:.1f}" height="{height:.1f}" '
            f'rx="4" ry="4" fill="{style["fill"]}" stroke="{stroke}" stroke-width="1.4"'
            + (f' stroke-dasharray="{dasharray}"' if dasharray else "")
            + "/>",
            *(_render_level_overlays(left, top, block_width, height, modifiers)),
            (
                f'<rect x="{left + 4:.1f}" y="{top + 4:.1f}" width="{block_width - 8:.1f}" height="{height - 8:.1f}" '
                'rx="3" ry="3" fill="none" stroke="#94a3b8" stroke-width="0.9"/>'
                if border_mode == "double"
                else ""
            ),
            _render_duration_guides(height),
            specialized
            if specialized
            else f'<text x="{x:.1f}" y="{top + (height / 2) + 6:.1f}" text-anchor="middle" '
            f'font-size="{max(13, int(geom.get("height", 18)))}" fill="{text_color}">{glyph}</text>',
            _render_degree_badge(left, top, modifiers),
            f'<text x="{x:.1f}" y="{top + height + 12:.1f}" text-anchor="middle" '
            f'class="symbol-id" font-size="8" fill="#4b5563">{symbol_id}</text>',
            *(_render_surface_marks(left, top, block_width, height, modifiers)),
            *(_render_arrowheads(left, top, block_width, height, modifiers)),
            *(_render_jump_supports(left, top, block_width, height, modifiers)),
            *annotations,
            "</g>",
        ]
    )


def _is_measure_header(symbol: dict, spec: dict) -> bool:
    return spec.get("geometry", {}).get("staff_column") == "music" and bool(symbol.get("modifiers", {}).get("measure_header"))


def _render_measure_header_band(measure: int, header_count: int, band_width: float, measure_top: float, staff_left: float) -> str:
    band_x = staff_left - band_width - 4
    band_y = measure_top + 4
    band_height = max(24, (header_count * 22) + 8)
    return (
        f'<g class="measure-header-band" data-measure="{measure}">'
        f'<rect x="{band_x:.1f}" y="{band_y:.1f}" width="{band_width:.1f}" height="{band_height:.1f}" rx="8" ry="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1"/>'
        f'<line x1="{band_x + band_width:.1f}" y1="{measure_top + 14:.1f}" x2="{staff_left - 10:.1f}" y2="{measure_top + 14:.1f}" stroke="#93c5fd" stroke-width="1.2" stroke-dasharray="4 3"/>'
        "</g>"
    )


def _render_measure_header_symbol(symbol: dict, stack_index: int, card_width: float, measure_top: float, staff_left: float) -> str:
    measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
    x = staff_left - card_width - 10
    y = measure_top + 10 + (stack_index * 22)
    text = escape(_measure_header_text(symbol))
    return (
        f'<g class="measure-header" data-symbol-id="{escape(symbol.get("symbol_id", ""))}">'
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{card_width:.1f}" height="18" rx="4" ry="4" fill="#eef2ff" stroke="#c7d2fe" stroke-width="1"/>'
        f'<text x="{x + (card_width / 2):.1f}" y="{y + 13:.1f}" text-anchor="middle" font-size="9" fill="#312e81">{text}</text>'
        "</g>"
    )


def _find_anchor_entry(entries: list[dict], current: dict) -> dict | None:
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


def _anchor_point(entry: dict, role: str, peer: dict | None = None) -> tuple[float, float]:
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


def _attachment_clearance_y(source: dict, target: dict, entries: list[dict]) -> float | None:
    left = min(source["x"], target["x"])
    right = max(source["x"], target["x"])
    top = min(source["top"], target["top"])
    bottom = max(source["top"] + source["height"], target["top"] + target["height"])
    source_y = source["top"] + (source["height"] / 2)
    target_y = target["top"] + (target["height"] / 2)
    mid_y = (source_y + target_y) / 2
    blockers = []
    for entry in entries:
        if entry is source or entry is target:
            continue
        family = _entry_family(entry)
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
            if _routing_hits_symbol_box("horizontal", left, right, mid_y, mid_y, mid_y, entry):
                blockers.append(entry)
    if not blockers:
        return None
    route_above = min(entry["top"] for entry in blockers) - 12
    route_below = max(entry["top"] + entry["height"] for entry in blockers) + 12
    if mid_y <= route_above + 18:
        return route_above
    return route_below


def _entry_bounds(entry: dict, padding: float = 0.0) -> tuple[float, float, float, float]:
    half_width = entry["width"] / 2
    return (
        entry["x"] - half_width - padding,
        entry["x"] + half_width + padding,
        entry["top"] - padding,
        entry["top"] + entry["height"] + padding,
    )


def _routing_hits_symbol_box(
    axis: str,
    left: float,
    right: float,
    top: float,
    bottom: float,
    coordinate: float,
    entry: dict,
) -> bool:
    entry_left, entry_right, entry_top, entry_bottom = _entry_bounds(entry, padding=8.0)
    if axis == "horizontal":
        if coordinate < entry_top or coordinate > entry_bottom:
            return False
        return not (entry_right < left or entry_left > right)
    if coordinate < entry_left or coordinate > entry_right:
        return False
    return not (entry_bottom < top or entry_top > bottom)


def _simplify_polyline(points: list[tuple[float, float]], tolerance: float = 1.0) -> list[tuple[float, float]]:
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


def _render_attachment_polyline(route: str, points: list[tuple[float, float]]) -> str:
    simplified = _simplify_polyline(points)
    commands = [f"M {simplified[0][0]:.1f} {simplified[0][1]:.1f}"]
    commands.extend(f"L {x:.1f} {y:.1f}" for x, y in simplified[1:])
    return (
        f'<path class="attachment-line" data-route="{route}" d="{" ".join(commands)}" '
        'fill="none" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
    )


def _attachment_bundle_profiles(pending_attachments: list[tuple[dict, dict]]) -> dict[int, dict[str, float]]:
    grouped: dict[tuple[int, str, float], list[tuple[dict, dict]]] = {}
    for source, target in pending_attachments:
        if _entry_family(source) not in BUNDLE_ATTACHMENT_FAMILIES:
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
            preferred_side = _preferred_attachment_side(source, target)
            profiles[id(source)] = {
                "count": float(count),
                "rank": float(rank),
                "bundle_x": target["x"] - 28.0 if preferred_side == "left" else target["x"] + 28.0,
            }
    return profiles


def _routing_track_penalty(
    measure: int,
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
        if line["measure"] != measure:
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
            if _routing_hits_symbol_box(axis, left, right, top, bottom, coordinate, entry)
        )
        if symbol_collisions:
            penalty += 20 * symbol_collisions
    if header_corridors and measure in header_corridors:
        corridor = header_corridors[measure]
        overlaps_corridor = not (
            right < corridor["left"]
            or left > corridor["right"]
            or bottom < corridor["top"]
            or top > corridor["bottom"]
        )
        if overlaps_corridor:
            penalty += 24
    return penalty


def _reserve_routing_track(
    measure: int,
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
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == measure), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 5):
        routed_y = base_y + (track * 12.0)
        penalty = _routing_track_penalty(
            measure,
            left,
            right,
            routed_y,
            routed_y,
            "horizontal",
            track,
            kind,
            routed_lines,
            blockers,
            header_corridors,
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
            "measure": measure,
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


def _render_attachment_line(
    source: dict,
    target: dict,
    entries: list[dict],
    routed_lines: list[dict],
    header_corridors: dict[int, dict[str, float]] | None = None,
    bundle_profile: dict[str, float] | None = None,
) -> str:
    source_x, source_y = _anchor_point(source, "source", target)
    target_x, target_y = _anchor_point(target, "target", source)
    mid_x = (source_x + target_x) / 2
    blockers = [entry for entry in entries if entry is not source and entry is not target]
    preferred_side = _preferred_attachment_side(source, target)
    clearance_y = _attachment_clearance_y(source, target, entries)
    if clearance_y is not None:
        routed_y, _track = _reserve_routing_track(
            min(source["measure"], target["measure"]),
            min(source_x, target_x),
            max(source_x, target_x),
            min(source["top"], target["top"]),
            max(source["top"] + source["height"], target["top"] + target["height"]),
            clearance_y,
            routed_lines,
            "attachment",
            blockers,
            header_corridors,
        )
        if bundle_profile:
            bundle_x = bundle_profile["bundle_x"]
            split_y = target_y + ((bundle_profile["rank"] - ((bundle_profile["count"] - 1.0) / 2.0)) * 8.0)
            return _render_attachment_polyline(
                "bundle-clearance",
                [
                    (source_x, source_y),
                    (source_x, routed_y),
                    (bundle_x, routed_y),
                    (bundle_x, split_y),
                    (target_x, split_y),
                    (target_x, target_y),
                ],
            )
        if abs(source["start"] - target["start"]) >= 1.0 and {source["column"], target["column"]} & {"pin"}:
            jog_source_x = source_x - 18.0 if source_x > target_x else source_x + 18.0
            jog_target_x = target_x - 18.0 if preferred_side == "left" else target_x + 18.0
            return _render_attachment_polyline(
                "multi-elbow",
                [
                    (source_x, source_y),
                    (source_x, routed_y),
                    (jog_source_x, routed_y),
                    (jog_target_x, routed_y),
                    (target_x, routed_y),
                    (target_x, target_y),
                ],
            )
        if abs(source["start"] - target["start"]) >= 1.0:
            jog_x = target_x - 18.0 if preferred_side == "left" else target_x + 18.0
            jog_y = target_y + 12.0 if routed_y < target_y else target_y - 12.0
            return _render_attachment_polyline(
                "dogleg",
                [
                    (source_x, source_y),
                    (source_x, routed_y),
                    (jog_x, routed_y),
                    (jog_x, jog_y),
                    (target_x, jog_y),
                    (target_x, target_y),
                ],
            )
        return _render_attachment_polyline(
            "clearance",
            [
                (source_x, source_y),
                (source_x, routed_y),
                (target_x, routed_y),
                (target_x, target_y),
            ],
        )
    if abs(source["start"] - target["start"]) >= 1.0 and {source["column"], target["column"]} & {"pin"}:
        routed_y = min(source_y, target_y) - 24.0 if abs(source_y - target_y) < 48.0 else (source_y + target_y) / 2
        jog_source_x = source_x - 18.0 if source_x > target_x else source_x + 18.0
        jog_target_x = target_x - 18.0 if preferred_side == "left" else target_x + 18.0
        return _render_attachment_polyline(
            "multi-elbow",
            [
                (source_x, source_y),
                (source_x, routed_y),
                (jog_source_x, routed_y),
                (jog_target_x, routed_y),
                (target_x, routed_y),
                (target_x, target_y),
            ],
        )
    if abs(source_y - target_y) > abs(source_x - target_x):
        mid_x = source_x + ((target_x - source_x) * 0.25)
    return (
        f'<path class="attachment-line" data-route="curve" d="M {source_x:.1f} {source_y:.1f} C {mid_x:.1f} {source_y:.1f}, {mid_x:.1f} {target_y:.1f}, {target_x:.1f} {target_y:.1f}" '
        'fill="none" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
    )


def _render_repeat_separator_bridge(
    entries: list[dict],
    routed_lines: list[dict],
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> list[str]:
    bridges: list[str] = []
    repeats = [entry for entry in entries if entry["column"] == "repeat"]
    separators = [entry for entry in entries if entry["column"] == "separator"]
    for repeat in repeats:
        for separator in separators:
            if abs(repeat["start"] - separator["start"]) > 0.51:
                continue
            y, _track = _reserve_routing_track(
                repeat["measure"],
                min(repeat["x"], separator["x"]),
                max(repeat["x"], separator["x"]),
                min(repeat["top"], separator["top"]),
                max(repeat["top"] + repeat["height"], separator["top"] + separator["height"]),
                min(repeat["top"], separator["top"]) - 8,
                routed_lines,
                "bridge",
                [entry for entry in entries if entry is not repeat and entry is not separator],
                header_corridors,
            )
            bridges.append(
                f'<path class="repeat-separator-bridge" d="M {repeat["x"]:.1f} {y:.1f} L {separator["x"]:.1f} {y:.1f}" '
                'fill="none" stroke="#64748b" stroke-width="1.2"/>'
            )
            break
    return bridges


def _reserve_vertical_routing_track(
    measure: int,
    top: float,
    bottom: float,
    base_x: float,
    routed_lines: list[dict],
    kind: str,
    blockers: list[dict] | None = None,
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> tuple[float, int]:
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == measure), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 5):
        routed_x = base_x - (track * 12.0)
        penalty = _routing_track_penalty(
            measure,
            routed_x,
            routed_x,
            top,
            bottom,
            "vertical",
            track,
            kind,
            routed_lines,
            blockers,
            header_corridors,
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
            "measure": measure,
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


def _render_repeat_spans(
    entries: list[dict],
    routed_lines: list[dict],
    measure_tops: dict[int, float],
    header_corridors: dict[int, dict[str, float]] | None = None,
) -> list[str]:
    spans: list[str] = []
    starts = [entry for entry in entries if entry["symbol"].get("symbol_id") == "repeat.start"]
    ends = [entry for entry in entries if entry["column"] == "repeat" and entry["symbol"].get("symbol_id") in {"repeat.end", "repeat.double"}]
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
            and _entry_family(item) in {"quality", "level", "timing"}
        ]
        leftmost_annotation = min((item["x"] - (item["width"] / 2) for item in competing), default=start["x"] - 18)
        y1 = measure_tops[start["measure"]] + 4
        y2 = measure_tops[target["measure"]] + (4 * BEAT_HEIGHT) - 4
        x, _track = _reserve_vertical_routing_track(
            start["measure"],
            y1,
            y2,
            min(start["x"] - 18, leftmost_annotation - 14),
            routed_lines,
            "span",
            [entry for entry in entries if entry is not start and entry is not target],
            header_corridors,
        )
        spans.append(
            f'<path class="repeat-span" d="M {x:.1f} {y1:.1f} L {x:.1f} {y2:.1f} M {x:.1f} {y1:.1f} L {x + 9:.1f} {y1:.1f} M {x:.1f} {y2:.1f} L {x + 9:.1f} {y2:.1f}" '
            'fill="none" stroke="#475569" stroke-width="1.4"/>'
        )
    return spans


def _measure_special_x_offset(entry: dict, existing_entries: list[dict]) -> float:
    same_slot = [
        item
        for item in existing_entries
        if item["measure"] == entry["measure"] and abs(item["start"] - entry["start"]) < 0.01
    ]
    if not same_slot:
        return 0.0

    column = entry["column"]
    has_separator = any(item["column"] == "separator" for item in same_slot)
    has_repeat = any(item["column"] == "repeat" for item in same_slot)

    if column == "repeat" and has_separator:
        if entry["symbol"].get("symbol_id") == "repeat.start":
            return -14.0
        return -10.0
    if column == "separator" and has_repeat:
        return 8.0
    if column == "music" and not _is_measure_header(entry["symbol"], entry["spec"]) and (has_separator or has_repeat):
        return 14.0
    return 0.0


def _measure_priority_y_offset(entry: dict, existing_entries: list[dict]) -> float:
    same_slot = [
        item
        for item in existing_entries
        if item["measure"] == entry["measure"] and abs(item["start"] - entry["start"]) < 0.01
    ]
    if not same_slot:
        return 0.0

    column = _entry_family(entry)
    layer_offsets = {
        "repeat": -8.0,
        "quality": -4.0,
        "level": 6.0,
        "timing": 14.0,
    }
    competing_columns = {"repeat", "quality", "level", "timing"}
    if column not in competing_columns:
        return 0.0
    if not any(_entry_family(item) in competing_columns for item in same_slot):
        return 0.0
    return layer_offsets.get(column, 0.0)


def _render_continuation_markers(entry: dict, measure_tops: dict[int, float]) -> list[str]:
    markers: list[str] = []
    start_measure = entry["measure"]
    end_measure = max(start_measure, int(((entry["end"] - 0.001) // 4) + 1))
    if end_measure <= start_measure:
        return markers
    left = entry["x"] - (entry["width"] / 2) + 4.0
    right = entry["x"] + (entry["width"] / 2) - 4.0
    for boundary_measure in range(start_measure + 1, end_measure + 1):
        y = measure_tops.get(boundary_measure)
        if y is None:
            continue
        markers.append(
            f'<path class="continuation-marker" data-boundary-measure="{boundary_measure}" d="M {left:.1f} {y:.1f} L {right:.1f} {y:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.2" stroke-dasharray="5 4"/>'
        )
    return markers


def render_svg(ir: dict) -> str:
    catalog = load_symbol_catalog()
    symbols = ir.get("symbols", [])
    measure_count = _measure_count(symbols)
    header_layout = _measure_header_layout(symbols, catalog)
    measure_right_padding = _measure_right_padding(symbols, catalog)
    header_gutter = _header_gutter_width(header_layout)
    staff_left = MARGIN_X + header_gutter
    lane_positions = _build_lane_positions(staff_left)
    order = BODY_LANES + COLUMN_LANES
    lane_right = staff_left + len(order) * LANE_WIDTH + (len(order) - 1) * LANE_GAP
    staff_top = TOP_MARGIN + HEADER_HEIGHT
    measure_pressures = _measure_stack_pressure(symbols, catalog, measure_count)
    measure_tops, measure_gaps = _measure_vertical_layout(symbols, catalog, staff_top, measure_count)
    header_corridors = _measure_header_corridors(header_layout, measure_tops, staff_left)
    systems = _system_layout(measure_count, measure_tops, measure_right_padding, staff_left, lane_right)
    width = int(lane_right + max(measure_right_padding.values(), default=52.0) + MARGIN_X)
    timeline_height = (measure_count * 4 * BEAT_HEIGHT) + sum(measure_gaps.values())
    height = int(TOP_MARGIN + HEADER_HEIGHT + timeline_height + BOTTOM_MARGIN)

    elements: list[str] = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#f8fafc"/>',
        """
<defs>
  <pattern id="level-middle-fill" patternUnits="userSpaceOnUse" width="8" height="8">
    <rect width="8" height="8" fill="#ffffff"/>
    <rect width="8" height="4" fill="#8f9bb3"/>
  </pattern>
</defs>
""".strip(),
    ]

    title = escape(ir.get("metadata", {}).get("title", "Untitled"))
    elements.append(
        f'<text x="{MARGIN_X}" y="34" font-size="24" font-weight="700" fill="#111827">{title}</text>'
    )
    elements.append(
        f'<text x="{MARGIN_X}" y="56" font-size="11" fill="#6b7280">'
        "Laban staff engraving preview"
        "</text>"
    )

    staff_bottom = measure_tops[measure_count] + (4 * BEAT_HEIGHT)
    for system in systems:
        elements.append(f'<g class="staff-system" data-system="{system["index"]}" data-measures="{system["start_measure"]}-{system["end_measure"]}">')
        elements.append(
            f'<rect x="{staff_left - 10:.1f}" y="{int(system["top"] - 14)}" width="{system["right"] - staff_left + 20:.1f}" '
            f'height="{int(system["bottom"] - system["top"] + 28)}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>'
        )
        elements.append("</g>")

    for measure_index in range(measure_count):
        measure_number = measure_index + 1
        y = measure_tops[measure_number]
        measure_right = lane_right + measure_right_padding.get(measure_number, 52.0)
        measure_height = 4 * BEAT_HEIGHT
        if measure_index % 2 == 0:
            elements.append(
                f'<rect x="{staff_left - 10:.1f}" y="{y:.1f}" width="{measure_right - staff_left + 20:.1f}" '
                f'height="{measure_height:.1f}" fill="#fbfdff"/>'
            )
        elements.append(
            f'<line x1="{staff_left - 10:.1f}" y1="{y:.1f}" x2="{measure_right + 10:.1f}" y2="{y:.1f}" '
            'stroke="#94a3b8" stroke-width="1.4"/>'
        )
        elements.append(
            f'<text x="{staff_left - 6:.1f}" y="{y + 16:.1f}" text-anchor="end" font-size="10" fill="#64748b">'
            f'M{measure_index + 1}</text>'
        )
        for beat_index in range(1, 4):
            beat_y = y + (beat_index * (measure_height / 4.0))
            elements.append(
                f'<line x1="{staff_left - 10:.1f}" y1="{beat_y:.1f}" x2="{measure_right + 10:.1f}" y2="{beat_y:.1f}" '
                'stroke="#cbd5e1" stroke-width="1" stroke-dasharray="4 4"/>'
            )
            elements.append(
                f'<text x="{staff_left - 6:.1f}" y="{beat_y + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">'
                f'{beat_index + 1}</text>'
            )
    for system in systems:
        elements.append(
            f'<line x1="{staff_left - 10:.1f}" y1="{system["bottom"]:.1f}" x2="{system["right"] + 10:.1f}" y2="{system["bottom"]:.1f}" '
            'stroke="#94a3b8" stroke-width="1.4"/>'
        )

    for system in systems:
        for lane in order:
            x = lane_positions[lane]
            elements.append(
                f'<line x1="{x:.1f}" y1="{int(system["top"] - 14)}" x2="{x:.1f}" y2="{int(system["bottom"] + 14)}" '
                'stroke="#e5e7eb" stroke-width="1"/>'
            )
            label = lane.replace("_", " ").title()
            elements.append(
                f'<text x="{x:.1f}" y="{system["top"] - 22:.1f}" text-anchor="middle" font-size="9" fill="#475569">'
                f"{escape(label)}</text>"
            )

    placed: list[dict] = []
    rendered_entries: list[dict] = []
    deferred_elements: list[str] = []
    routed_attachment_lines: list[dict] = []
    pending_attachments: list[tuple[dict, dict]] = []
    measure_headers: dict[int, int] = {}
    header_stack: dict[int, int] = {}
    for symbol in sorted(symbols, key=lambda item: _symbol_time(item)[0]):
        symbol_id = symbol.get("symbol_id", "")
        spec = catalog.get(symbol_id, {})
        geom = spec.get("geometry", {})
        lane = _resolve_lane(symbol, spec)
        x = lane_positions[lane]
        start, end = _symbol_time(symbol)
        measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        measure_top = measure_tops[measure]
        within_measure_start = start - ((measure - 1) * 4)
        within_measure_end = end - ((measure - 1) * 4)
        top = measure_top + within_measure_start * BEAT_HEIGHT + 6
        height_span = max(MIN_SYMBOL_HEIGHT, (within_measure_end - within_measure_start) * BEAT_HEIGHT - 12)
        if _is_measure_boundary_separator(symbol, spec):
            top = measure_top + 2
            height_span = (4 * BEAT_HEIGHT) - 4
        bottom = top + height_span
        collision_index = _compute_collision_index(placed, lane, top, bottom)
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
            "measure": measure,
            "measure_top": measure_top,
            "measure_height": 4 * BEAT_HEIGHT,
        }
        x += _measure_special_x_offset(entry, rendered_entries)
        top += _measure_priority_y_offset(entry, rendered_entries)
        top += _measure_zone_y_offset(entry, measure_pressures.get(measure, 0.0))
        entry["x"] = x
        entry["top"] = top
        rendered_entries.append(entry)

        if _is_measure_header(symbol, spec):
            stack_index = header_stack.get(measure, 0)
            header_stack[measure] = stack_index + 1
            measure_headers[measure] = header_stack[measure]
            band_width = header_layout.get(measure, {}).get("max_text_width", 72.0) + 12.0
            deferred_elements.append(_render_measure_header_symbol(symbol, stack_index, band_width - 12.0, measure_top, staff_left))
        else:
            elements.append(_render_symbol_block(symbol, spec, x, top, height_span))
            elements.extend(_render_continuation_markers(entry, measure_tops))

        if geom.get("staff_column") in {"quality", "level", "timing"}:
            target_lane = symbol.get("body_part")
            if target_lane in lane_positions:
                elements.append(
                    f'<line x1="{lane_positions[target_lane]:.1f}" y1="{top + (height_span / 2):.1f}" '
                    f'x2="{x - 10:.1f}" y2="{top + (height_span / 2):.1f}" '
                    'stroke="#cbd5e1" stroke-width="1"/>'
                )

    for entry in rendered_entries:
        if entry["column"] not in ATTACHABLE_COLUMNS:
            continue
        if _is_measure_header(entry["symbol"], entry["spec"]):
            continue
        target = _find_anchor_entry(rendered_entries, entry)
        if target:
            pending_attachments.append((entry, target))
    attachment_bundle_profiles = _attachment_bundle_profiles(pending_attachments)

    for measure, header_count in sorted(measure_headers.items()):
        band_width = header_layout.get(measure, {}).get("max_text_width", 72.0) + 12.0
        deferred_elements.insert(0, _render_measure_header_band(measure, header_count, band_width, measure_tops[measure], staff_left))

    deferred_elements.extend(_render_repeat_separator_bridge(rendered_entries, routed_attachment_lines, header_corridors))
    deferred_elements.extend(_render_repeat_spans(rendered_entries, routed_attachment_lines, measure_tops, header_corridors))
    for entry, target in pending_attachments:
        deferred_elements.append(
            _render_attachment_line(
                entry,
                target,
                rendered_entries,
                routed_attachment_lines,
                header_corridors,
                attachment_bundle_profiles.get(id(entry)),
            )
        )
    elements.extend(deferred_elements)

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            *elements,
            "</svg>",
        ]
    )
