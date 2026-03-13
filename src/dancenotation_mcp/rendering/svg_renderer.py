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


def _entry_family(entry: dict) -> str:
    column = entry.get("column")
    if column:
        return column
    symbol_id = entry.get("symbol", {}).get("symbol_id", "")
    return symbol_id.split(".", 1)[0]


def _measure_header_text(symbol: dict) -> str:
    if symbol.get("symbol_id", "").endswith("tempo.mark"):
        return f'♩={symbol.get("modifiers", {}).get("tempo", 120)}'
    if ".time." in symbol.get("symbol_id", ""):
        return symbol["symbol_id"].split(".time.", 1)[1].replace("_", "/")
    if symbol.get("symbol_id", "").endswith("cadence.mark"):
        return "cad"
    return symbol.get("symbol_id", "music").split(".")[-1].replace("_", "/")


def _measure_header_layout(symbols: list[dict], catalog: dict[str, dict]) -> dict[int, dict[str, float]]:
    layout: dict[int, dict[str, float]] = {}
    for symbol in symbols:
        spec = catalog.get(symbol.get("symbol_id", ""), {})
        if not _is_measure_header(symbol, spec):
            continue
        measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
        text = _measure_header_text(symbol)
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


def _render_path_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    bottom = top + height
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.5)
    path_width = width * stretch
    path_left = mid_x - path_width / 2
    path_right = mid_x + path_width / 2
    direction = modifiers.get("path_curve", "standard")
    if symbol_id.endswith("spiral"):
        return (
            f'<g class="specialized-path" data-shape="spiral">'
            f'<path d="M {mid_x:.1f} {bottom:.1f} C {path_left - 10:.1f} {top + height * 0.78:.1f}, {path_left - 6:.1f} {top + height * 0.22:.1f}, {mid_x:.1f} {top + height * 0.22:.1f} '
            f'S {path_right + 8:.1f} {top + height * 0.72:.1f}, {mid_x:.1f} {top + height * 0.44:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.8"/>'
            "</g>"
        )
    if symbol_id.endswith("circle"):
        radius_x = max(path_width / 2 - 3, 6)
        radius_y = max(height / 2 - 4, 6)
        return (
            f'<g class="specialized-path" data-shape="circle">'
            f'<ellipse cx="{mid_x:.1f}" cy="{top + height / 2:.1f}" rx="{radius_x:.1f}" ry="{radius_y:.1f}" fill="none" stroke="#111827" stroke-width="1.8"/>'
            "</g>"
        )
    if symbol_id.endswith("curved") or direction == "curved":
        return (
            f'<g class="specialized-path" data-shape="curved">'
            f'<path d="M {mid_x:.1f} {bottom:.1f} C {path_left - 10:.1f} {top + height * 0.68:.1f}, {path_right + 10:.1f} {top + height * 0.34:.1f}, {mid_x:.1f} {top:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.8"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-path" data-shape="straight">'
        f'<line x1="{mid_x:.1f}" y1="{bottom:.1f}" x2="{mid_x:.1f}" y2="{top:.1f}" stroke="#111827" stroke-width="{1.4 * stretch:.1f}"/>'
        "</g>"
    )


def _render_turn_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    center_x = left + width / 2
    center_y = top + height / 2
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    radius_x = max((width / 2 - 4) * stretch, 6)
    radius_y = max(height / 2 - 4, 6)
    sweep = 1 if modifiers.get("turn_direction", "cw") != "ccw" else 0
    rotation = float(modifiers.get("rotation", 0))
    degree = float(modifiers.get("degree", 0) or 0)
    spin_variant = symbol_id.endswith("spin") or degree >= 360
    echo_arc = ""
    if spin_variant:
        echo_arc = (
            f'<path d="M {center_x - (radius_x - 5):.1f} {center_y + 6:.1f} '
            f'A {max(radius_x - 5, 4):.1f} {max(radius_y - 5, 4):.1f} 0 1 {sweep} {center_x + (radius_x - 5):.1f} {center_y + 6:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.2" stroke-dasharray="3 2"/>'
        )
    return (
        f'<g class="specialized-turn" data-variant="{"spin" if spin_variant else "pivot"}" transform="rotate({rotation:.1f} {center_x:.1f} {center_y:.1f})">'
        f'<path d="M {center_x - radius_x:.1f} {center_y:.1f} A {radius_x:.1f} {radius_y:.1f} 0 1 {sweep} {center_x + radius_x:.1f} {center_y:.1f}" '
        'fill="none" stroke="#111827" stroke-width="1.8"/>'
        f'{echo_arc}'
        f'<polygon points="{center_x + radius_x + 7:.1f},{center_y:.1f} {center_x + radius_x - 1:.1f},{center_y - 5:.1f} {center_x + radius_x - 1:.1f},{center_y + 5:.1f}" fill="#111827"/>'
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
    if stretch >= 1.35 or symbol_id.endswith("small"):
        inner_arc = (
            f'<path d="M {left_x + 4:.1f} {bottom - 8:.1f} Q {mid_x:.1f} {apex + 10:.1f} {right_x - 4:.1f} {bottom - 8:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.1" stroke-dasharray="4 3"/>'
        )
        landing_mark = (
            f'<line x1="{right_x - 3:.1f}" y1="{bottom - 3:.1f}" x2="{right_x + 5:.1f}" y2="{bottom - 9:.1f}" stroke="#111827" stroke-width="1.2"/>'
        )
    return (
        f'<g class="specialized-jump" data-variant="{"stretched" if stretch >= 1.35 else "compact"}">'
        f'<path d="M {left_x:.1f} {bottom:.1f} Q {mid_x:.1f} {apex:.1f} {right_x:.1f} {bottom:.1f}" '
        'fill="none" stroke="#111827" stroke-width="1.8"/>'
        f'{inner_arc}'
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
    if symbol_id.endswith("hold"):
        hold_y = top + max(height * 0.34, 12)
        hold_bar = (
            f'<line x1="{mid_x - 7:.1f}" y1="{hold_y:.1f}" x2="{mid_x + 7:.1f}" y2="{hold_y:.1f}" stroke="#64748b" stroke-width="1.6"/>'
        )
    head = (
        f'<circle cx="{mid_x:.1f}" cy="{top + 5:.1f}" r="3.2" fill="#111827"/>'
        if head_style != "diamond"
        else f'<polygon points="{mid_x:.1f},{top + 1:.1f} {mid_x - 4:.1f},{top + 5:.1f} {mid_x:.1f},{top + 9:.1f} {mid_x + 4:.1f},{top + 5:.1f}" fill="#111827"/>'
    )
    return (
        f'<g class="specialized-pin" data-variant="{"hold" if symbol_id.endswith("hold") else "standard"}">'
        f'<line x1="{mid_x:.1f}" y1="{top + 2:.1f}" x2="{mid_x:.1f}" y2="{pin_bottom - 9:.1f}" stroke="#111827" stroke-width="1.8"/>'
        f'{hold_bar}'
        f'{head}'
        f'<polygon points="{mid_x:.1f},{pin_bottom + 2:.1f} {mid_x - 5:.1f},{pin_bottom - 8:.1f} {mid_x + 5:.1f},{pin_bottom - 8:.1f}" fill="#111827"/>'
        "</g>"
    )


def _render_repeat_symbol(left: float, top: float, width: float, height: float, doubled: bool, modifiers: dict) -> str:
    x1 = left + width * 0.38
    x2 = left + width * 0.62
    bars = [x1, x2] if doubled else [left + width / 2]
    dots = []
    repeat_count = max(int(modifiers.get("repeat_count", 1)), 1)
    for x in bars:
        for idx in range(repeat_count):
            y = top + height * (0.28 + idx * min(0.16, 0.5 / repeat_count))
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="#111827"/>')
    end_bar = ""
    if modifiers.get("repeat_end"):
        end_bar = f'<line x1="{left + width - 2:.1f}" y1="{top + 2:.1f}" x2="{left + width - 2:.1f}" y2="{top + height - 2:.1f}" stroke="#111827" stroke-width="2.0"/>'
    return f'<g class="specialized-repeat" data-repeat-count="{repeat_count}">{"".join(dots)}{end_bar}</g>'


def _render_music_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    if symbol_id.endswith("tempo.mark"):
        tempo = escape(str(modifiers.get("tempo", 120)))
        return (
            f'<g class="specialized-music" data-kind="tempo">'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.48:.1f}" text-anchor="middle" font-size="9" fill="#111827">♩={tempo}</text>'
            "</g>"
        )
    if ".time." in symbol_id:
        parts = symbol_id.split(".time.", 1)[1].split("_")
        return (
            f'<g class="specialized-music" data-kind="time-signature">'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.38:.1f}" text-anchor="middle" font-size="9" fill="#111827">{parts[0]}</text>'
            f'<text x="{mid_x:.1f}" y="{top + height * 0.72:.1f}" text-anchor="middle" font-size="9" fill="#111827">{parts[1]}</text>'
            "</g>"
        )
    rest_height = max(float(modifiers.get("rest_height", 1.0)), 0.6)
    return (
        f'<g class="specialized-music" data-kind="rest">'
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
    return (
        f'<g class="specialized-separator" data-flipped="{str(flipped).lower()}">'
        f'<line x1="{bar_x:.1f}" y1="{top:.1f}" x2="{bar_x:.1f}" y2="{top + height:.1f}" stroke="#111827" stroke-width="2.2"/>'
        f'<line x1="{bar_x:.1f}" y1="{top + height * 0.33:.1f}" x2="{hook_x:.1f}" y2="{top + height * 0.33:.1f}" stroke="#111827" stroke-width="1.4"/>'
        f'<line x1="{bar_x:.1f}" y1="{top + height * 0.66:.1f}" x2="{hook_x:.1f}" y2="{top + height * 0.66:.1f}" stroke="#111827" stroke-width="1.4"/>'
        "</g>"
    )


def _is_measure_boundary_separator(symbol: dict, spec: dict) -> bool:
    if spec.get("geometry", {}).get("staff_column") != "separator":
        return False
    timing = symbol.get("timing", {})
    beat = float(timing.get("beat", 1.0))
    duration = float(timing.get("duration_beats", 1.0))
    return abs(beat - 1.0) < 0.01 and duration >= 1.0


def _render_motif_symbol(symbol_id: str, left: float, top: float, width: float, height: float, modifiers: dict) -> str:
    mid_x = left + width / 2
    rotation = float(modifiers.get("rotation", 0))
    if symbol_id.endswith("arc"):
        content = (
            f'<path d="M {left + 3:.1f} {top + height * 0.72:.1f} Q {mid_x:.1f} {top + 2:.1f} {left + width - 3:.1f} {top + height * 0.72:.1f}" '
            'fill="none" stroke="#111827" stroke-width="1.8"/>'
        )
    elif symbol_id.endswith("fall"):
        content = (
            f'<line x1="{mid_x:.1f}" y1="{top + 4:.1f}" x2="{mid_x:.1f}" y2="{top + height - 7:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{mid_x:.1f},{top + height + 1:.1f} {mid_x - 5:.1f},{top + height - 8:.1f} {mid_x + 5:.1f},{top + height - 8:.1f}" fill="#111827"/>'
        )
    else:
        content = (
            f'<line x1="{mid_x:.1f}" y1="{top + height - 4:.1f}" x2="{mid_x:.1f}" y2="{top + 8:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{mid_x:.1f},{top + 1:.1f} {mid_x - 5:.1f},{top + 10:.1f} {mid_x + 5:.1f},{top + 10:.1f}" fill="#111827"/>'
        )
    return f'<g class="specialized-motif" transform="rotate({rotation:.1f} {mid_x:.1f} {top + height / 2:.1f})">{content}</g>'


def _render_surface_symbol(left: float, top: float, width: float, height: float, symbol_id: str) -> str:
    mid_x = left + width / 2
    mid_y = top + height / 2
    if symbol_id.endswith("brush"):
        return (
            f'<g class="specialized-surface" data-kind="brush">'
            f'<path d="M {left + 2:.1f} {mid_y - 3:.1f} Q {mid_x:.1f} {mid_y - 8:.1f} {left + width - 2:.1f} {mid_y - 3:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<path d="M {left + 2:.1f} {mid_y + 3:.1f} Q {mid_x:.1f} {mid_y - 2:.1f} {left + width - 2:.1f} {mid_y + 3:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            "</g>"
        )
    if symbol_id.endswith("glide"):
        return (
            f'<g class="specialized-surface" data-kind="glide">'
            f'<path d="M {left + 2:.1f} {mid_y + 2:.1f} Q {mid_x:.1f} {mid_y - 6:.1f} {left + width - 2:.1f} {mid_y + 2:.1f}" fill="none" stroke="#111827" stroke-width="1.6"/>'
            f'<line x1="{left + 4:.1f}" y1="{mid_y + 5:.1f}" x2="{left + width - 4:.1f}" y2="{mid_y + 5:.1f}" stroke="#111827" stroke-width="1.2"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-surface" data-kind="contact">'
        f'<circle cx="{mid_x:.1f}" cy="{mid_y:.1f}" r="5.5" fill="none" stroke="#111827" stroke-width="1.6"/>'
        f'<circle cx="{mid_x:.1f}" cy="{mid_y:.1f}" r="2.2" fill="#111827"/>'
        "</g>"
    )


def _render_space_symbol(left: float, top: float, width: float, height: float, symbol_id: str, modifiers: dict) -> str:
    stretch = max(float(modifiers.get("stretch", 1.0)), 0.6)
    if symbol_id.endswith("transition"):
        line_y = top + height / 2
        return (
            f'<g class="specialized-space" data-kind="transition">'
            f'<line x1="{left + 2:.1f}" y1="{line_y:.1f}" x2="{left + width * stretch - 2:.1f}" y2="{line_y:.1f}" stroke="#94a3b8" stroke-width="1.4" stroke-dasharray="5 4"/>'
            "</g>"
        )
    return (
        f'<g class="specialized-space" data-kind="hold">'
        f'<rect x="{left + 2:.1f}" y="{top + 3:.1f}" width="{max(width * stretch - 4, 8):.1f}" height="{height - 6:.1f}" fill="none" stroke="#94a3b8" stroke-width="1.4"/>'
        "</g>"
    )


def _render_specialized_symbol(symbol: dict, spec: dict, left: float, top: float, width: float, height: float) -> str:
    column = spec.get("geometry", {}).get("staff_column")
    symbol_id = symbol.get("symbol_id", "")
    modifiers = symbol.get("modifiers", {})
    if column == "path":
        return _render_path_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "turn":
        return _render_turn_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "jump":
        return _render_jump_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "pin":
        if symbol_id.endswith("entry"):
            modifiers = {**modifiers, "pin_head": "diamond"}
        return _render_pin_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "repeat":
        if symbol_id.endswith("end"):
            modifiers = {**modifiers, "repeat_end": True}
        return _render_repeat_symbol(left, top, width, height, symbol_id.endswith("double"), modifiers)
    if column == "music":
        return _render_music_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "motif":
        return _render_motif_symbol(symbol_id, left, top, width, height, modifiers)
    if column == "surface":
        return _render_surface_symbol(left, top, width, height, symbol_id)
    if column == "space":
        return _render_space_symbol(left, top, width, height, symbol_id, modifiers)
    if column == "separator":
        if symbol_id.endswith("single"):
            modifiers = {**modifiers, "separator_mode": "single"}
        elif symbol_id.endswith("double"):
            modifiers = {**modifiers, "separator_mode": "double"}
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


def _render_measure_header_band(measure: int, header_count: int, band_width: float, staff_top: float, staff_left: float) -> str:
    measure_top = _measure_top(measure, staff_top)
    band_x = staff_left - band_width - 4
    band_y = measure_top + 4
    band_height = max(24, (header_count * 22) + 8)
    return (
        f'<g class="measure-header-band" data-measure="{measure}">'
        f'<rect x="{band_x:.1f}" y="{band_y:.1f}" width="{band_width:.1f}" height="{band_height:.1f}" rx="8" ry="8" fill="#eff6ff" stroke="#bfdbfe" stroke-width="1"/>'
        f'<line x1="{band_x + band_width:.1f}" y1="{measure_top + 14:.1f}" x2="{staff_left - 10:.1f}" y2="{measure_top + 14:.1f}" stroke="#93c5fd" stroke-width="1.2" stroke-dasharray="4 3"/>'
        "</g>"
    )


def _render_measure_header_symbol(symbol: dict, stack_index: int, card_width: float, staff_top: float, staff_left: float) -> str:
    measure = max(int(symbol.get("timing", {}).get("measure", 1)), 1)
    measure_top = _measure_top(measure, staff_top)
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
        return None
    route_above = min(entry["top"] for entry in blockers) - 12
    route_below = max(entry["top"] + entry["height"] for entry in blockers) + 12
    source_y = source["top"] + (source["height"] / 2)
    target_y = target["top"] + (target["height"] / 2)
    mid_y = (source_y + target_y) / 2
    if mid_y <= route_above + 18:
        return route_above
    return route_below


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
) -> int | None:
    penalty = 0
    for line in routed_lines:
        if line["measure"] != measure:
            continue
        if int(line["track"]) != track:
            continue
        if line["bottom"] < top or line["top"] > bottom:
            continue
        line_axis = line.get("axis")
        if line_axis == "vertical":
            overlaps = left <= line["x"] <= right
        else:
            overlaps = not (line["right"] < left or line["left"] > right)
        if not overlaps:
            continue
        if line_axis == axis:
            return None
        existing_priority = ROUTING_KIND_PRIORITY.get(line.get("kind", "attachment"), 2)
        current_priority = ROUTING_KIND_PRIORITY.get(kind, 2)
        penalty += 8 if existing_priority <= current_priority else 2
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
) -> tuple[float, int]:
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == measure), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 3):
        penalty = _routing_track_penalty(measure, left, right, top, bottom, "horizontal", track, kind, routed_lines)
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
        }
    )
    return routed_y, track


def _render_attachment_line(source: dict, target: dict, entries: list[dict], routed_lines: list[dict]) -> str:
    source_x, source_y = _anchor_point(source, "source", target)
    target_x, target_y = _anchor_point(target, "target", source)
    mid_x = (source_x + target_x) / 2
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
        )
        if abs(source["start"] - target["start"]) >= 1.0:
            jog_x = target_x + 18.0 if target_x < source_x else target_x - 18.0
            jog_y = target_y + 12.0 if routed_y < target_y else target_y - 12.0
            return (
                f'<path class="attachment-line" d="M {source_x:.1f} {source_y:.1f} '
                f'L {source_x:.1f} {routed_y:.1f} L {jog_x:.1f} {routed_y:.1f} '
                f'L {jog_x:.1f} {jog_y:.1f} L {target_x:.1f} {jog_y:.1f} L {target_x:.1f} {target_y:.1f}" '
                'fill="none" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
            )
        return (
            f'<path class="attachment-line" d="M {source_x:.1f} {source_y:.1f} '
            f'L {source_x:.1f} {routed_y:.1f} L {target_x:.1f} {routed_y:.1f} L {target_x:.1f} {target_y:.1f}" '
            'fill="none" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
        )
    if abs(source_y - target_y) > abs(source_x - target_x):
        mid_x = source_x + ((target_x - source_x) * 0.25)
    return (
        f'<path class="attachment-line" d="M {source_x:.1f} {source_y:.1f} C {mid_x:.1f} {source_y:.1f}, {mid_x:.1f} {target_y:.1f}, {target_x:.1f} {target_y:.1f}" '
        'fill="none" stroke="#94a3b8" stroke-width="1.2" stroke-dasharray="3 3"/>'
    )


def _render_repeat_separator_bridge(entries: list[dict], routed_lines: list[dict]) -> list[str]:
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
) -> tuple[float, int]:
    max_existing_track = max((int(line["track"]) for line in routed_lines if line["measure"] == measure), default=-1)
    best_track = 0
    best_penalty: int | None = None
    for track in range(max_existing_track + 3):
        penalty = _routing_track_penalty(measure, base_x, base_x, top, bottom, "vertical", track, kind, routed_lines)
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
        }
    )
    return routed_x, track


def _render_repeat_spans(entries: list[dict], routed_lines: list[dict]) -> list[str]:
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
        y1 = start["measure_top"] + 4
        y2 = target["measure_top"] + (4 * BEAT_HEIGHT) - 4
        x, _track = _reserve_vertical_routing_track(
            start["measure"],
            y1,
            y2,
            min(start["x"] - 18, leftmost_annotation - 14),
            routed_lines,
            "span",
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


def render_svg(ir: dict) -> str:
    catalog = load_symbol_catalog()
    symbols = ir.get("symbols", [])
    measure_count = _measure_count(symbols)
    header_layout = _measure_header_layout(symbols, catalog)
    header_gutter = _header_gutter_width(header_layout)
    staff_left = MARGIN_X + header_gutter
    lane_positions = _build_lane_positions(staff_left)
    order = BODY_LANES + COLUMN_LANES
    width = int(staff_left + MARGIN_X + len(order) * LANE_WIDTH + (len(order) - 1) * LANE_GAP + 80)
    timeline_height = measure_count * 4 * BEAT_HEIGHT
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

    staff_top = TOP_MARGIN + HEADER_HEIGHT
    staff_bottom = staff_top + timeline_height
    elements.append(
        f'<rect x="{staff_left - 10:.1f}" y="{staff_top - 14}" width="{width - staff_left - MARGIN_X + 20:.1f}" '
        f'height="{timeline_height + 28}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>'
    )

    for measure_index in range(measure_count):
        y = staff_top + measure_index * 4 * BEAT_HEIGHT
        if measure_index % 2 == 0:
            elements.append(
                f'<rect x="{staff_left - 10:.1f}" y="{y:.1f}" width="{width - staff_left - MARGIN_X + 20:.1f}" '
                f'height="{4 * BEAT_HEIGHT:.1f}" fill="#fbfdff"/>'
            )
        elements.append(
            f'<line x1="{staff_left - 10:.1f}" y1="{y:.1f}" x2="{width - MARGIN_X + 10}" y2="{y:.1f}" '
            'stroke="#94a3b8" stroke-width="1.4"/>'
        )
        elements.append(
            f'<text x="{staff_left - 6:.1f}" y="{y + 16:.1f}" text-anchor="end" font-size="10" fill="#64748b">'
            f'M{measure_index + 1}</text>'
        )
        for beat_index in range(1, 4):
            beat_y = y + beat_index * BEAT_HEIGHT
            elements.append(
                f'<line x1="{staff_left - 10:.1f}" y1="{beat_y:.1f}" x2="{width - MARGIN_X + 10}" y2="{beat_y:.1f}" '
                'stroke="#cbd5e1" stroke-width="1" stroke-dasharray="4 4"/>'
            )
            elements.append(
                f'<text x="{staff_left - 6:.1f}" y="{beat_y + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">'
                f'{beat_index + 1}</text>'
            )
    elements.append(
        f'<line x1="{staff_left - 10:.1f}" y1="{staff_bottom:.1f}" x2="{width - MARGIN_X + 10}" y2="{staff_bottom:.1f}" '
        'stroke="#94a3b8" stroke-width="1.4"/>'
    )

    for lane in order:
        x = lane_positions[lane]
        elements.append(
            f'<line x1="{x:.1f}" y1="{staff_top - 14}" x2="{x:.1f}" y2="{staff_bottom + 14:.1f}" '
            'stroke="#e5e7eb" stroke-width="1"/>'
        )
        label = lane.replace("_", " ").title()
        elements.append(
            f'<text x="{x:.1f}" y="{staff_top - 22:.1f}" text-anchor="middle" font-size="9" fill="#475569">'
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
        measure_top = _measure_top(measure, staff_top)
        top = staff_top + start * BEAT_HEIGHT + 6
        height_span = max(MIN_SYMBOL_HEIGHT, (end - start) * BEAT_HEIGHT - 12)
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
        }
        x += _measure_special_x_offset(entry, rendered_entries)
        top += _measure_priority_y_offset(entry, rendered_entries)
        entry["x"] = x
        entry["top"] = top
        rendered_entries.append(entry)

        if _is_measure_header(symbol, spec):
            stack_index = header_stack.get(measure, 0)
            header_stack[measure] = stack_index + 1
            measure_headers[measure] = header_stack[measure]
            band_width = header_layout.get(measure, {}).get("max_text_width", 72.0) + 12.0
            deferred_elements.append(_render_measure_header_symbol(symbol, stack_index, band_width - 12.0, staff_top, staff_left))
        else:
            elements.append(_render_symbol_block(symbol, spec, x, top, height_span))

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

    for measure, header_count in sorted(measure_headers.items()):
        band_width = header_layout.get(measure, {}).get("max_text_width", 72.0) + 12.0
        deferred_elements.insert(0, _render_measure_header_band(measure, header_count, band_width, staff_top, staff_left))

    deferred_elements.extend(_render_repeat_separator_bridge(rendered_entries, routed_attachment_lines))
    deferred_elements.extend(_render_repeat_spans(rendered_entries, routed_attachment_lines))
    for entry, target in pending_attachments:
        deferred_elements.append(_render_attachment_line(entry, target, rendered_entries, routed_attachment_lines))
    elements.extend(deferred_elements)

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">',
            *elements,
            "</svg>",
        ]
    )
