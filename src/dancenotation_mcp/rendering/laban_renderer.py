"""Standard Labanotation SVG renderer.

Produces publication-quality Labanotation scores with:
- Narrow 6-column staff with center line
- Direction-shape rectangles (shape encodes direction)
- Level-encoded fills (hollow/hatched/solid)
- Bottom-to-top time flow
- Annotation areas for turn, jump, quality, timing marks
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from dancenotation_mcp.rendering.laban_layout import (
    ANNOTATION_GAP,
    ANNOTATION_WIDTH,
    BEAT_HEIGHT,
    CENTER_GAP,
    COL_WIDTH,
    HEADER_HEIGHT,
    LABAN_SYSTEM_CAPACITY,
    MARGIN_X,
    MARGIN_Y_BOTTOM,
    MARGIN_Y_TOP,
    STAFF_COLUMNS,
    compute_laban_layout,
    is_measure_header,
)
from dancenotation_mcp.ir.time_signatures import beats_for_measure


# ── Level fill styles ─────────────────────────────────────────────────

# Per the LabanWriter 4.4 manual ("High level stripe space can be changed...
# Make a high level symbol, then separate stripes"): High is the striped
# level, not Middle. Low = solid black is unambiguous and unchanged. Middle
# is blank/unshaded (outline only) by elimination — the manual documents no
# separate shading for it, and LabanWriter's "Blank" level command clears
# fill entirely, matching an unshaded middle.
LEVEL_FILLS = {
    "high":   {"fill": "url(#laban-hatch)", "stroke": "#111827"},  # striped
    "middle": {"fill": "#ffffff", "stroke": "#111827"},    # blank/unshaded
    "low":    {"fill": "#111827", "stroke": "#111827"},    # solid
}

LEVEL_TEXT_COLOR = {
    "high": "#111827",
    "middle": "#111827",
    "low": "#ffffff",
}


# ── Direction shape paths ─────────────────────────────────────────────

def _direction_path(direction: str | None, x_left: float, y_top: float,
                    x_right: float, y_bottom: float) -> str:
    """Return SVG path 'd' attribute for an ICKL-standard Labanotation direction shape.

    ICKL shapes:
    - forward:  rectangle with isosceles triangle point at top (~27% of height)
    - backward: rectangle with isosceles triangle point at bottom
    - left:     pentagon (rect body + triangle point at left)
    - right:    pentagon (rect body + triangle point at right)
    - diagonals: forward/backward shape rotated ±45°
    - place:    full-width rectangle (no triangle point)
    """
    w = x_right - x_left
    h = y_bottom - y_top
    cx = (x_left + x_right) / 2
    cy = (y_top + y_bottom) / 2

    if direction == "forward":
        # Rectangle body with isosceles triangle point at top.
        # Triangle occupies ~27% of total height.
        tri_h = h * 0.27
        rect_top = y_top + tri_h  # where rectangle starts below triangle
        return (
            f"M {cx:.1f} {y_top:.1f} "               # triangle apex
            f"L {x_right:.1f} {rect_top:.1f} "        # triangle right base
            f"L {x_right:.1f} {y_bottom:.1f} "        # rectangle bottom-right
            f"L {x_left:.1f} {y_bottom:.1f} "         # rectangle bottom-left
            f"L {x_left:.1f} {rect_top:.1f} Z"        # triangle left base
        )

    if direction == "backward":
        # Rectangle body with isosceles triangle point at bottom.
        tri_h = h * 0.27
        rect_bottom = y_bottom - tri_h
        return (
            f"M {x_left:.1f} {y_top:.1f} "            # rectangle top-left
            f"L {x_right:.1f} {y_top:.1f} "           # rectangle top-right
            f"L {x_right:.1f} {rect_bottom:.1f} "     # triangle right base
            f"L {cx:.1f} {y_bottom:.1f} "              # triangle apex
            f"L {x_left:.1f} {rect_bottom:.1f} Z"     # triangle left base
        )

    if direction == "right":
        # Pentagon: rectangular body (~73% width) with triangle point at right.
        body_w = w * 0.73
        body_right = x_left + body_w
        return (
            f"M {x_left:.1f} {y_top:.1f} "
            f"L {body_right:.1f} {y_top:.1f} "
            f"L {x_right:.1f} {cy:.1f} "
            f"L {body_right:.1f} {y_bottom:.1f} "
            f"L {x_left:.1f} {y_bottom:.1f} Z"
        )

    if direction == "left":
        # Pentagon: rectangular body (~73% width) with triangle point at left.
        body_w = w * 0.73
        body_left = x_right - body_w
        return (
            f"M {x_right:.1f} {y_top:.1f} "
            f"L {x_right:.1f} {y_bottom:.1f} "
            f"L {body_left:.1f} {y_bottom:.1f} "
            f"L {x_left:.1f} {cy:.1f} "
            f"L {body_left:.1f} {y_top:.1f} Z"
        )

    # Diagonals: rotate the forward/backward shape by ±45°.
    import math
    _DIAG_ANGLES = {
        "diagonal_forward_right": -math.pi / 4,    # 45° CW (upper-right)
        "diagonal_forward_left": math.pi / 4,       # 45° CCW (upper-left)
        "diagonal_backward_right": math.pi / 4,     # 45° CCW from backward (lower-right)
        "diagonal_backward_left": -math.pi / 4,     # 45° CW from backward (lower-left)
    }
    if direction in _DIAG_ANGLES:
        angle = _DIAG_ANGLES[direction]
        # Build base shape (forward for forward_*, backward for backward_*)
        tri_h = h * 0.27
        if direction.startswith("diagonal_forward"):
            # Forward shape: triangle at top
            rect_top = y_top + tri_h
            pts = [
                (cx, y_top),                # apex
                (x_right, rect_top),        # triangle right base
                (x_right, y_bottom),        # bottom-right
                (x_left, y_bottom),         # bottom-left
                (x_left, rect_top),         # triangle left base
            ]
        else:
            # Backward shape: triangle at bottom
            rect_bottom = y_bottom - tri_h
            pts = [
                (x_left, y_top),            # top-left
                (x_right, y_top),           # top-right
                (x_right, rect_bottom),     # triangle right base
                (cx, y_bottom),             # apex
                (x_left, rect_bottom),      # triangle left base
            ]
        # Rotate all points around center
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        rotated = []
        for px, py in pts:
            dx, dy = px - cx, py - cy
            rotated.append((cx + dx * cos_a - dy * sin_a,
                            cy + dx * sin_a + dy * cos_a))
        parts = [f"M {rotated[0][0]:.1f} {rotated[0][1]:.1f}"]
        for rx, ry in rotated[1:]:
            parts.append(f"L {rx:.1f} {ry:.1f}")
        parts.append("Z")
        return " ".join(parts)

    # place / unknown → full-width rectangle (no triangle point)
    return (
        f"M {x_left:.1f} {y_top:.1f} "
        f"L {x_right:.1f} {y_top:.1f} "
        f"L {x_right:.1f} {y_bottom:.1f} "
        f"L {x_left:.1f} {y_bottom:.1f} Z"
    )


# ── Facing indicator ──────────────────────────────────────────────────

_FACING_ARROW_DX = {
    "forward": (0, -1), "backward": (0, 1),
    "left": (-1, 0), "right": (1, 0),
    "diagonal_forward_right": (0.7, -0.7), "diagonal_forward_left": (-0.7, -0.7),
    "diagonal_backward_right": (0.7, 0.7), "diagonal_backward_left": (-0.7, 0.7),
}


def _render_facing_indicator(facing: str, x_right: float, y_top: float,
                             y_bottom: float) -> str:
    """Small arrow showing facing direction, placed just outside the symbol's right edge."""
    dx, dy = _FACING_ARROW_DX.get(facing, (0, -1))
    cx = x_right + 6
    cy = (y_top + y_bottom) / 2
    length = 5
    ex, ey = cx + dx * length, cy + dy * length
    return (
        f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
        f'stroke="#6b7280" stroke-width="0.8" marker-end="url(#arrow)"/>'
    )


# ── Symbol rendering ─────────────────────────────────────────────────


class _RenderContext:
    """Mutable state passed through rendering functions to avoid global variables."""
    __slots__ = ("split_clip_counter",)

    def __init__(self) -> None:
        self.split_clip_counter = 0


def _render_separator(entry: dict) -> str:
    """Render separator lines across the staff."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    modifiers = symbol.get("modifiers", {})
    mode = modifiers.get("separator_mode", "single")

    x_left = entry["x_left"]
    x_right = entry["x_right"]
    cy = (entry["y_top"] + entry["y_bottom"]) / 2

    svg = f'<g class="laban-symbol separator" data-symbol-id="{escape(symbol_id)}">'

    if mode == "double":
        svg += (
            f'<line x1="{x_left:.1f}" y1="{cy - 1.5:.1f}" x2="{x_right:.1f}" y2="{cy - 1.5:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
            f'<line x1="{x_left:.1f}" y1="{cy + 1.5:.1f}" x2="{x_right:.1f}" y2="{cy + 1.5:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
        )
    elif mode == "hooked":
        hook = 4
        svg += (
            f'<line x1="{x_left:.1f}" y1="{cy:.1f}" x2="{x_right:.1f}" y2="{cy:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
            f'<line x1="{x_left:.1f}" y1="{cy:.1f}" x2="{x_left:.1f}" y2="{cy + hook:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
            f'<line x1="{x_right:.1f}" y1="{cy:.1f}" x2="{x_right:.1f}" y2="{cy + hook:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
        )
    else:
        # single
        svg += (
            f'<line x1="{x_left:.1f}" y1="{cy:.1f}" x2="{x_right:.1f}" y2="{cy:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
        )

    svg += '</g>'
    return svg


def _render_modifier_overlays(svg: str, modifiers: dict,
                              x_left: float, x_right: float,
                              y_top: float, y_bottom: float) -> str:
    """Append modifier visual overlays to an in-progress SVG group string.

    Called after the main shape path has been added but before the closing </g>.
    """
    cx = (x_left + x_right) / 2

    # ── Oscillation marks ────────────────────────────────────────────
    osc = modifiers.get("oscillations", 0)
    if osc > 0:
        mid_y = (y_top + y_bottom) / 2
        amp = 3
        step = (x_right - x_left) / (osc * 2)
        points = []
        for i in range(osc * 2 + 1):
            px = x_left + i * step
            py = mid_y + (amp if i % 2 == 1 else -amp if i % 2 == 0 and i > 0 else 0)
            points.append(f"{px:.1f},{py:.1f}")
        svg += f'<polyline points="{" ".join(points)}" fill="none" stroke="#111827" stroke-width="1"/>'

    # ── Surface marks ────────────────────────────────────────────────
    surface_marks = modifiers.get("surface_marks")
    if surface_marks:
        tick = 4
        mid_y = (y_top + y_bottom) / 2
        for mark in surface_marks:
            if mark in ("forward", "front"):
                svg += (
                    f'<line x1="{cx:.1f}" y1="{y_top:.1f}" x2="{cx:.1f}" y2="{y_top - tick:.1f}" '
                    f'stroke="#111827" stroke-width="1"/>'
                )
            elif mark in ("backward", "back"):
                svg += (
                    f'<line x1="{cx:.1f}" y1="{y_bottom:.1f}" x2="{cx:.1f}" y2="{y_bottom + tick:.1f}" '
                    f'stroke="#111827" stroke-width="1"/>'
                )
            elif mark in ("left", "inner"):
                svg += (
                    f'<line x1="{x_left:.1f}" y1="{mid_y:.1f}" x2="{x_left - tick:.1f}" y2="{mid_y:.1f}" '
                    f'stroke="#111827" stroke-width="1"/>'
                )
            elif mark in ("right", "outer"):
                svg += (
                    f'<line x1="{x_right:.1f}" y1="{mid_y:.1f}" x2="{x_right + tick:.1f}" y2="{mid_y:.1f}" '
                    f'stroke="#111827" stroke-width="1"/>'
                )

    # ── Joint area label ─────────────────────────────────────────────
    joint = modifiers.get("joint_area")
    if joint:
        svg += (
            f'<text x="{cx:.1f}" y="{y_top - 3:.1f}" text-anchor="middle" '
            f'font-size="6" font-style="italic" fill="#666">{escape(joint)}</text>'
        )

    # ── Degree marks ─────────────────────────────────────────────────
    degree = modifiers.get("degree", 0)
    if degree and degree > 0:
        dot_y = (y_top + y_bottom) / 2
        dot_r = 1.5
        degree = min(degree, 3)
        total_w = (degree - 1) * 5
        start_x = cx - total_w / 2
        for i in range(degree):
            dx = start_x + i * 5
            svg += f'<circle cx="{dx:.1f}" cy="{dot_y:.1f}" r="{dot_r}" fill="#111827"/>'

    # ── Label ────────────────────────────────────────────────────────
    label = modifiers.get("label")
    if label:
        svg += (
            f'<text x="{cx:.1f}" y="{y_bottom + 10:.1f}" text-anchor="middle" '
            f'font-size="7" fill="#475569">{escape(label)}</text>'
        )

    # ── Source text ──────────────────────────────────────────────────
    source_text = modifiers.get("source_text")
    if source_text:
        svg += (
            f'<text x="{cx:.1f}" y="{y_bottom + 18:.1f}" text-anchor="middle" '
            f'font-size="6" font-style="italic" fill="#999">{escape(source_text)}</text>'
        )

    return svg


def _render_staff_symbol(entry: dict, ctx: _RenderContext,
                         use_defs: dict[tuple[str, str], str] | None = None) -> str:
    """Render a primary symbol as a direction-shape rectangle with modifier overlays.

    When *use_defs* is provided and the symbol's (direction, level) pair has a
    matching ``<symbol>`` definition, the renderer emits a ``<use>`` reference
    instead of an inline ``<path>``.  Symbols with special modifiers
    (split-level, whitespace, separators) always fall back to inline rendering.
    """
    symbol = entry["symbol"]
    direction = symbol.get("direction")
    level = symbol.get("level") or "middle"
    symbol_id = symbol.get("symbol_id", "")
    facing = symbol.get("facing")

    x_left = entry["x_left"] + 1   # small padding
    x_right = entry["x_right"] - 1
    y_top = entry["y_top"] + 1
    y_bottom = entry["y_bottom"] - 1

    modifiers = symbol.get("modifiers", {})

    # Dispatch separators to dedicated renderer
    if symbol_id.startswith("separator"):
        return _render_separator(entry)

    # Whitespace band: blank gap instead of normal shape. Triggered either by
    # an explicit modifier on any symbol, or by the dedicated space.* family
    # (space.hold/transition/whitespace — see official_extras.json), which
    # otherwise fell through to a plain place/middle rectangle.
    if modifiers.get("whitespace") or symbol_id.startswith("space."):
        return (
            f'<g class="laban-symbol whitespace" data-symbol-id="{escape(symbol_id)}">'
            f'<rect x="{x_left}" y="{y_top}" width="{x_right - x_left}" height="{y_bottom - y_top}" '
            f'fill="white" stroke="#ccc" stroke-width="0.8" stroke-dasharray="4,3"/>'
            f'</g>'
        )

    has_top = "level_fill_top" in modifiers
    has_bottom = "level_fill_bottom" in modifiers

    if has_top or has_bottom:
        # Split-level rendering: two halves with different fills (always inline)
        path_d = _direction_path(direction, x_left, y_top, x_right, y_bottom)
        top_level = modifiers.get("level_fill_top", level)
        bottom_level = modifiers.get("level_fill_bottom", level)
        top_style = LEVEL_FILLS.get(top_level, LEVEL_FILLS["middle"])
        bottom_style = LEVEL_FILLS.get(bottom_level, LEVEL_FILLS["middle"])

        w = x_right - x_left
        h = y_bottom - y_top
        y_mid = y_top + h / 2

        uid = ctx.split_clip_counter
        ctx.split_clip_counter += 1

        svg = (
            f'<g class="laban-symbol" data-symbol-id="{escape(symbol_id)}" '
            f'data-direction="{escape(direction or "place")}" data-level="{escape(level)}">'
            f'<defs>'
            f'<clipPath id="upper-clip-{uid}">'
            f'<rect x="{x_left:.1f}" y="{y_top:.1f}" width="{w:.1f}" height="{h / 2:.1f}"/>'
            f'</clipPath>'
            f'<clipPath id="lower-clip-{uid}">'
            f'<rect x="{x_left:.1f}" y="{y_mid:.1f}" width="{w:.1f}" height="{h / 2:.1f}"/>'
            f'</clipPath>'
            f'</defs>'
            f'<path d="{path_d}" clip-path="url(#upper-clip-{uid})" '
            f'fill="{top_style["fill"]}" stroke="{top_style["stroke"]}" stroke-width="1.5"/>'
            f'<path d="{path_d}" clip-path="url(#lower-clip-{uid})" '
            f'fill="{bottom_style["fill"]}" stroke="{bottom_style["stroke"]}" stroke-width="1.5"/>'
            f'<line x1="{x_left:.1f}" y1="{y_mid:.1f}" x2="{x_right:.1f}" y2="{y_mid:.1f}" '
            f'stroke="#111827" stroke-width="0.8"/>'
            f'<path d="{path_d}" fill="none" stroke="{top_style["stroke"]}" stroke-width="1.5"/>'
        )
        svg = _render_modifier_overlays(svg, modifiers, x_left, x_right, y_top, y_bottom)
        if facing and facing != direction:
            svg += _render_facing_indicator(facing, x_right, y_top, y_bottom)
        svg += '</g>'
        return svg

    # ── Standard symbol: try <use> from defs ──────────────────────────
    line_style = modifiers.get("line_style", "single")
    dash_attr = ' stroke-dasharray="3,3"' if line_style in ("dotted", "double_dotted") else ""
    has_special_line = line_style not in ("single",)
    has_modifiers = bool(modifiers) and not (len(modifiers) == 1 and "line_style" in modifiers and line_style == "single")

    def_key = (direction or "place", level)
    use_href = use_defs.get(def_key) if use_defs and not has_special_line else None

    w = x_right - x_left
    h = y_bottom - y_top

    svg = (
        f'<g class="laban-symbol" data-symbol-id="{escape(symbol_id)}" '
        f'data-direction="{escape(direction or "place")}" data-level="{escape(level)}">'
    )
    if use_href and not dash_attr:
        svg += (
            f'<use href="#{use_href}" x="{x_left:.1f}" y="{y_top:.1f}" '
            f'width="{w:.1f}" height="{h:.1f}"/>'
        )
    else:
        path_d = _direction_path(direction, x_left, y_top, x_right, y_bottom)
        style = LEVEL_FILLS.get(level, LEVEL_FILLS["middle"])
        svg += f'<path d="{path_d}" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="1.5"{dash_attr}/>'
        if line_style in ("double", "double_dotted"):
            svg += (
                f'<path d="{path_d}" fill="none" stroke="{style["stroke"]}" '
                f'stroke-width="3.5" opacity="0.3"{dash_attr}/>'
            )
    svg = _render_modifier_overlays(svg, modifiers, x_left, x_right, y_top, y_bottom)
    if facing and facing != direction:
        svg += _render_facing_indicator(facing, x_right, y_top, y_bottom)
    svg += '</g>'
    return svg


def _render_turn_annotation(entry: dict) -> str:
    """Render a turn sign in the annotation area."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    direction = symbol.get("direction")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2
    r = min(w / 2 - 2, (y_bottom - y_top) / 2 - 2, 8)

    # Arc direction
    sweep = 1 if direction not in ("left", "counterclockwise") else 0

    rotation_degrees = symbol.get("rotation_degrees") or symbol.get("modifiers", {}).get("rotation_degrees")
    rotate_attr = f' transform="rotate({rotation_degrees}, {cx:.1f}, {cy:.1f})"' if rotation_degrees else ""

    return (
        f'<g class="laban-annotation turn" data-symbol-id="{escape(symbol_id)}"{rotate_attr}>'
        f'<path d="M {cx - r:.1f} {cy:.1f} A {r:.1f} {r:.1f} 0 1 {sweep} {cx + r:.1f} {cy:.1f}" '
        f'fill="none" stroke="#111827" stroke-width="1.5"/>'
        f'<polygon points="{cx + r + 4:.1f},{cy:.1f} {cx + r - 2:.1f},{cy - 3:.1f} {cx + r - 2:.1f},{cy + 3:.1f}" '
        f'fill="#111827"/>'
        f'</g>'
    )


def _render_jump_annotation(entry: dict) -> str:
    """Render jump bow variants in the annotation area.

    Variants based on modifiers:
    - Normal: smooth cubic-bezier bow arc
    - Spring jump: zigzag/coil line between endpoints
    - Stretched jump: wider bow with extended horizontal endpoints
    - Compact jump (duration < 1 beat): tighter, smaller bow
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    bow_top = y_top + 4
    bow_bottom = y_bottom - 4

    modifiers = symbol.get("modifiers", {})
    is_spring = modifiers.get("spring_jump", False)
    stretch = modifiers.get("stretch", 0)
    duration = symbol.get("timing", {}).get("duration_beats", 1.0) if isinstance(symbol.get("timing"), dict) else 1.0

    svg = f'<g class="laban-annotation jump" data-symbol-id="{escape(symbol_id)}">'

    if is_spring:
        # Zigzag/coil line: 4 zigzag segments between endpoints
        seg_h = (bow_bottom - bow_top) / 8
        zag_w = 4
        svg += f'<path d="M {cx:.1f} {bow_bottom:.1f} '
        for i in range(8):
            zy = bow_bottom - (i + 1) * seg_h
            zx = cx + (zag_w if i % 2 == 0 else -zag_w)
            svg += f'L {zx:.1f} {zy:.1f} '
        svg += f'L {cx:.1f} {bow_top:.1f}" fill="none" stroke="#111827" stroke-width="1.5"/>'
    elif stretch > 0:
        # Stretched jump: wider bow with extended horizontal endpoints
        ext = min(stretch * 3, 8)
        svg += (
            f'<line x1="{cx - 6 - ext:.1f}" y1="{bow_bottom:.1f}" '
            f'x2="{cx - 6:.1f}" y2="{bow_bottom:.1f}" stroke="#111827" stroke-width="1.5"/>'
            f'<path d="M {cx - 6:.1f} {bow_bottom:.1f} '
            f'C {cx - 6:.1f} {bow_top - 4:.1f} {cx + 6:.1f} {bow_top - 4:.1f} '
            f'{cx + 6:.1f} {bow_bottom:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
            f'<line x1="{cx + 6:.1f}" y1="{bow_bottom:.1f}" '
            f'x2="{cx + 6 + ext:.1f}" y2="{bow_bottom:.1f}" stroke="#111827" stroke-width="1.5"/>'
        )
    elif duration < 1.0:
        # Compact jump: smaller, tighter bow
        svg += (
            f'<path d="M {cx - 4:.1f} {bow_bottom:.1f} '
            f'C {cx - 4:.1f} {bow_top + 2:.1f} {cx + 4:.1f} {bow_top + 2:.1f} '
            f'{cx + 4:.1f} {bow_bottom:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
        )
    else:
        # Normal jump: smooth cubic bezier bow
        svg += (
            f'<path d="M {cx - 6:.1f} {bow_bottom:.1f} '
            f'C {cx - 6:.1f} {bow_top - 6:.1f} {cx + 6:.1f} {bow_top - 6:.1f} '
            f'{cx + 6:.1f} {bow_bottom:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
        )

    # Center vertical stem
    svg += (
        f'<line x1="{cx:.1f}" y1="{bow_top:.1f}" x2="{cx:.1f}" y2="{bow_bottom - 4:.1f}" '
        f'stroke="#111827" stroke-width="1.2"/>'
    )

    svg += '</g>'
    return svg


def _render_quality_annotation(entry: dict) -> str:
    """Render a quality/effort mark."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    # Quality symbols: small geometric marks
    label = symbol_id.split(".")[-1][:3]
    return (
        f'<g class="laban-annotation quality" data-symbol-id="{escape(symbol_id)}">'
        f'<rect x="{x + 2:.1f}" y="{y_top + 2:.1f}" width="{w - 4:.1f}" height="{y_bottom - y_top - 4:.1f}" '
        f'rx="2" fill="none" stroke="#475569" stroke-width="1"/>'
        f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="7" fill="#475569">'
        f'{escape(label)}</text>'
        f'</g>'
    )


def _render_timing_annotation(entry: dict) -> str:
    """Render a timing mark (accent, hold, etc)."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    kind = symbol_id.split(".")[-1]
    if kind == "accent":
        return (
            f'<g class="laban-annotation timing" data-symbol-id="{escape(symbol_id)}">'
            f'<path d="M {cx - 5:.1f} {cy - 5:.1f} L {cx + 5:.1f} {cy:.1f} L {cx - 5:.1f} {cy + 5:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
            f'</g>'
        )
    if kind == "hold":
        return (
            f'<g class="laban-annotation timing" data-symbol-id="{escape(symbol_id)}">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#111827"/>'
            f'<path d="M {cx - 6:.1f} {cy:.1f} Q {cx:.1f} {cy - 8:.1f} {cx + 6:.1f} {cy:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
            f'</g>'
        )
    # Generic mark
    label = kind[:3]
    return (
        f'<g class="laban-annotation timing" data-symbol-id="{escape(symbol_id)}">'
        f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="7" fill="#475569">'
        f'{escape(label)}</text>'
        f'</g>'
    )


def _render_repeat_annotation(entry: dict) -> str:
    """Render repeat signs in annotation area."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2

    # Vertical bar with dots
    dots = ""
    if "double" in symbol_id or "end" in symbol_id:
        dots = (
            f'<circle cx="{cx:.1f}" cy="{(y_top + y_bottom) / 2 - 5:.1f}" r="2" fill="#111827"/>'
            f'<circle cx="{cx:.1f}" cy="{(y_top + y_bottom) / 2 + 5:.1f}" r="2" fill="#111827"/>'
        )
    bar_style = 'stroke-width="2.5"' if "start" in symbol_id else 'stroke-width="1.5"'
    return (
        f'<g class="laban-annotation repeat" data-symbol-id="{escape(symbol_id)}">'
        f'<line x1="{cx:.1f}" y1="{y_top + 2:.1f}" x2="{cx:.1f}" y2="{y_bottom - 2:.1f}" '
        f'stroke="#111827" {bar_style}/>'
        f'{dots}'
        f'</g>'
    )


def _render_retention_annotation(entry: dict) -> str:
    """Render hold/release/cancel marks."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    # Catalog IDs are "retention.{type}.{body_category}" (e.g.
    # "retention.hold.arm") — the type is the *second* segment, not the
    # last (that's the body category). Using [-1] here previously matched
    # nothing for any real catalog retention symbol, silently rendering
    # every hold/release/cancel as the same generic dot.
    symbol_id_parts = symbol_id.split(".")
    retention = symbol.get("retention") or (symbol_id_parts[1] if len(symbol_id_parts) > 1 else symbol_id_parts[-1])

    if retention == "hold":
        # Filled circle with tie arc above
        return (
            f'<g class="laban-annotation retention" data-symbol-id="{escape(symbol_id)}">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#111827"/>'
            f'<path d="M {cx - 6:.1f} {cy:.1f} Q {cx:.1f} {cy - 8:.1f} {cx + 6:.1f} {cy:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
            f'</g>'
        )
    if retention == "release":
        # X mark
        return (
            f'<g class="laban-annotation retention" data-symbol-id="{escape(symbol_id)}">'
            f'<line x1="{cx - 4:.1f}" y1="{cy - 4:.1f}" x2="{cx + 4:.1f}" y2="{cy + 4:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
            f'<line x1="{cx + 4:.1f}" y1="{cy - 4:.1f}" x2="{cx - 4:.1f}" y2="{cy + 4:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
            f'</g>'
        )
    if retention == "cancel":
        # Diagonal slash
        return (
            f'<g class="laban-annotation retention" data-symbol-id="{escape(symbol_id)}">'
            f'<line x1="{cx - 5:.1f}" y1="{cy + 5:.1f}" x2="{cx + 5:.1f}" y2="{cy - 5:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
            f'</g>'
        )
    # Fallback
    return (
        f'<g class="laban-annotation retention" data-symbol-id="{escape(symbol_id)}">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#111827"/>'
        f'</g>'
    )


def _render_contact_annotation(entry: dict) -> str:
    """Render ICKL-standard contact symbols (touch, slide, strike, grasp)."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    modifiers = symbol.get("modifiers", {})
    contact_type = modifiers.get("contact_type") or symbol_id.split(".")[-1]
    surface_marks = modifiers.get("surface_marks", [])

    parts = ""

    if contact_type == "grasp":
        # Standard staple shape: two verticals connected at bottom (~10x10px)
        parts = (
            f'<path d="M {cx - 5:.1f} {cy - 5:.1f} '
            f'L {cx - 5:.1f} {cy + 5:.1f} '
            f'L {cx + 5:.1f} {cy + 5:.1f} '
            f'L {cx + 5:.1f} {cy - 5:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5" stroke-linejoin="miter"/>'
        )
    elif contact_type == "slide":
        # Clean upward caret with small horizontal arrow above
        parts = (
            f'<path d="M {cx - 6:.1f} {cy + 4:.1f} L {cx:.1f} {cy - 4:.1f} L {cx + 6:.1f} {cy + 4:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5" stroke-linejoin="miter"/>'
            f'<line x1="{cx - 5:.1f}" y1="{cy - 7:.1f}" x2="{cx + 4:.1f}" y2="{cy - 7:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
            f'<polygon points="{cx + 6:.1f},{cy - 7:.1f} {cx + 3:.1f},{cy - 9:.1f} {cx + 3:.1f},{cy - 5:.1f}" '
            f'fill="#111827"/>'
        )
    elif contact_type == "strike":
        # Clean upward caret with vertical line through center
        parts = (
            f'<path d="M {cx - 6:.1f} {cy + 4:.1f} L {cx:.1f} {cy - 4:.1f} L {cx + 6:.1f} {cy + 4:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5" stroke-linejoin="miter"/>'
            f'<line x1="{cx:.1f}" y1="{cy - 7:.1f}" x2="{cx:.1f}" y2="{cy + 7:.1f}" '
            f'stroke="#111827" stroke-width="1.2"/>'
        )
    else:
        # Touch: clean upward caret (~12px wide, ~8px tall)
        parts = (
            f'<path d="M {cx - 6:.1f} {cy + 4:.1f} L {cx:.1f} {cy - 4:.1f} L {cx + 6:.1f} {cy + 4:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5" stroke-linejoin="miter"/>'
        )

    # Surface marks as small lines
    surface_svg = ""
    mark_offsets = {"front": (0, -9), "back": (0, 9), "inner": (-9, 0), "outer": (9, 0)}
    for mark in surface_marks:
        dx, dy = mark_offsets.get(mark, (0, 0))
        surface_svg += (
            f'<line x1="{cx + dx - 2:.1f}" y1="{cy + dy:.1f}" '
            f'x2="{cx + dx + 2:.1f}" y2="{cy + dy:.1f}" stroke="#111827" stroke-width="1"/>'
        )

    return (
        f'<g class="laban-annotation contact" data-symbol-id="{escape(symbol_id)}">'
        f'{parts}{surface_svg}'
        f'</g>'
    )


def _render_flexion_symbol(entry: dict) -> str:
    """Render ICKL-standard flexion/extension marks with hooked X arms.

    Flexion: narrow X where each arm tip has small perpendicular hooks
    curving inward.  Extension: hooks curve outward.
    Degree 1/2/3 → 1/2/3 concentric hook sets at each tip.
    """
    import math

    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    modifiers = symbol.get("modifiers", {})
    degree = max(1, min(int(modifiers.get("degree", 1)), 3))
    is_extension = "extension" in symbol_id

    arm_len = 6
    hook_len = 2.5
    stroke_w = "1.2"

    svg = f'<g class="laban-annotation flexion" data-symbol-id="{escape(symbol_id)}">'

    # Four arm directions: top-right, bottom-right, bottom-left, top-left
    arm_angles = [math.pi / 4, -math.pi / 4, -3 * math.pi / 4, 3 * math.pi / 4]

    for angle in arm_angles:
        dx = math.cos(angle)
        dy = -math.sin(angle)  # SVG y-axis inverted
        tip_x = cx + arm_len * dx
        tip_y = cy + arm_len * dy

        svg += (
            f'<line x1="{cx:.1f}" y1="{cy:.1f}" '
            f'x2="{tip_x:.1f}" y2="{tip_y:.1f}" '
            f'stroke="#111827" stroke-width="{stroke_w}"/>'
        )

        # Perpendicular hook direction (CCW rotation in SVG coords)
        perp_dx = -dy
        perp_dy = dx
        sign = -1 if is_extension else 1

        for d in range(degree):
            offset = (d + 1) * 1.8
            base_x = tip_x - offset * dx
            base_y = tip_y - offset * dy
            end_x = base_x + sign * hook_len * perp_dx
            end_y = base_y + sign * hook_len * perp_dy
            svg += (
                f'<line x1="{base_x:.1f}" y1="{base_y:.1f}" '
                f'x2="{end_x:.1f}" y2="{end_y:.1f}" '
                f'stroke="#111827" stroke-width="{stroke_w}"/>'
            )

    svg += '</g>'
    return svg


def _render_effort_diamond(entry: dict) -> str:
    """Render LMA effort graph as a diamond shape (~16x16px)."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2
    s = 8  # half-size of diamond

    modifiers = symbol.get("modifiers", {})
    active = set(modifiers.get("active_efforts", []))

    # Diamond outline
    svg = (
        f'<g class="laban-annotation effort" data-symbol-id="{escape(symbol_id)}">'
        f'<path d="M {cx:.1f} {cy - s:.1f} L {cx + s:.1f} {cy:.1f} '
        f'L {cx:.1f} {cy + s:.1f} L {cx - s:.1f} {cy:.1f} Z" '
        f'fill="none" stroke="#111827" stroke-width="1.2"/>'
    )

    # Dividing lines
    svg += (
        f'<line x1="{cx:.1f}" y1="{cy - s:.1f}" x2="{cx:.1f}" y2="{cy + s:.1f}" '
        f'stroke="#111827" stroke-width="0.8"/>'
        f'<line x1="{cx - s:.1f}" y1="{cy:.1f}" x2="{cx + s:.1f}" y2="{cy:.1f}" '
        f'stroke="#111827" stroke-width="0.8"/>'
    )

    # Quadrants: Weight(top-left), Time(top-right), Space(bottom-left), Flow(bottom-right)
    quadrant_paths = {
        "weight": f"M {cx:.1f} {cy - s:.1f} L {cx - s:.1f} {cy:.1f} L {cx:.1f} {cy:.1f} Z",
        "time": f"M {cx:.1f} {cy - s:.1f} L {cx + s:.1f} {cy:.1f} L {cx:.1f} {cy:.1f} Z",
        "space": f"M {cx:.1f} {cy:.1f} L {cx - s:.1f} {cy:.1f} L {cx:.1f} {cy + s:.1f} Z",
        "flow": f"M {cx:.1f} {cy:.1f} L {cx + s:.1f} {cy:.1f} L {cx:.1f} {cy + s:.1f} Z",
    }

    for quality, path_d in quadrant_paths.items():
        if quality in active:
            svg += f'<path d="{path_d}" fill="#111827" opacity="0.6"/>'

    svg += '</g>'
    return svg


def _render_shape_symbol(entry: dict) -> str:
    """Render LMA shape symbols (pin, wall, ball, screw)."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    modifiers = symbol.get("modifiers", {})
    shape_type = modifiers.get("shape_type") or symbol_id.split(".")[-1]

    if shape_type == "pin":
        # Vertical line with arrowhead
        return (
            f'<g class="laban-annotation shape" data-symbol-id="{escape(symbol_id)}">'
            f'<line x1="{cx:.1f}" y1="{cy + 6:.1f}" x2="{cx:.1f}" y2="{cy - 6:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
            f'<polygon points="{cx:.1f},{cy - 8:.1f} {cx - 3:.1f},{cy - 4:.1f} {cx + 3:.1f},{cy - 4:.1f}" '
            f'fill="#111827"/>'
            f'</g>'
        )
    if shape_type == "wall":
        # Horizontal line with arrows
        return (
            f'<g class="laban-annotation shape" data-symbol-id="{escape(symbol_id)}">'
            f'<line x1="{cx - 7:.1f}" y1="{cy:.1f}" x2="{cx + 7:.1f}" y2="{cy:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
            f'<polygon points="{cx - 9:.1f},{cy:.1f} {cx - 5:.1f},{cy - 3:.1f} {cx - 5:.1f},{cy + 3:.1f}" '
            f'fill="#111827"/>'
            f'<polygon points="{cx + 9:.1f},{cy:.1f} {cx + 5:.1f},{cy - 3:.1f} {cx + 5:.1f},{cy + 3:.1f}" '
            f'fill="#111827"/>'
            f'</g>'
        )
    if shape_type == "ball":
        # Circle
        return (
            f'<g class="laban-annotation shape" data-symbol-id="{escape(symbol_id)}">'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="none" stroke="#111827" stroke-width="1.5"/>'
            f'</g>'
        )
    if shape_type == "screw":
        # Spiral line
        return (
            f'<g class="laban-annotation shape" data-symbol-id="{escape(symbol_id)}">'
            f'<path d="M {cx:.1f} {cy + 6:.1f} '
            f'Q {cx + 5:.1f} {cy + 3:.1f} {cx:.1f} {cy:.1f} '
            f'Q {cx - 4:.1f} {cy - 2:.1f} {cx:.1f} {cy - 4:.1f} '
            f'Q {cx + 3:.1f} {cy - 5:.1f} {cx + 2:.1f} {cy - 7:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
            f'</g>'
        )
    # Generic fallback
    label = shape_type[:3] if shape_type else "shp"
    return (
        f'<g class="laban-annotation shape" data-symbol-id="{escape(symbol_id)}">'
        f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="7" fill="#475569">'
        f'{escape(label)}</text>'
        f'</g>'
    )


def _render_stage_marker(entry: dict) -> str:
    """Render stage position marker."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    stage_position = symbol.get("stage_position", {})
    zone = ""
    if isinstance(stage_position, dict):
        zone = stage_position.get("zone", "")
    # Abbreviate zone name
    zone_abbr = "".join(word[0].upper() for word in zone.split("_")) if zone else "?"

    return (
        f'<g class="laban-annotation floor_plan" data-symbol-id="{escape(symbol_id)}">'
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="#111827"/>'
        f'<text x="{cx:.1f}" y="{cy - 6:.1f}" text-anchor="middle" font-size="6" fill="#475569">'
        f'{escape(zone_abbr)}</text>'
        f'<line x1="{cx:.1f}" y1="{cy + 3:.1f}" x2="{cx:.1f}" y2="{y_bottom:.1f}" '
        f'stroke="#999" stroke-width="0.5" stroke-dasharray="2,2"/>'
        f'</g>'
    )


def _render_rotation_degree(entry: dict) -> str:
    """Render rotation degree annotation."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    degrees = symbol.get("rotation_degrees")
    if degrees is None:
        degrees = symbol.get("modifiers", {}).get("rotation_degrees", 0)
    label = f"{int(degrees)}\u00b0"

    return (
        f'<g class="laban-annotation rotation" data-symbol-id="{escape(symbol_id)}">'
        f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="7" '
        f'font-weight="600" fill="#475569">{escape(label)}</text>'
        f'</g>'
    )


def _render_sequential_annotation(entry: dict) -> str:
    """Render sequential/successive movement marks."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2

    modifiers = symbol.get("modifiers", {})
    wave_dir = modifiers.get("wave_direction", "upward")

    # Undulating wavy line
    wave_h = y_bottom - y_top
    amp = 3
    svg = (
        f'<g class="laban-annotation sequential" data-symbol-id="{escape(symbol_id)}">'
        f'<path d="M {cx:.1f} {y_bottom - 2:.1f} '
        f'Q {cx + amp:.1f} {y_bottom - wave_h * 0.25:.1f} {cx:.1f} {y_bottom - wave_h * 0.33:.1f} '
        f'Q {cx - amp:.1f} {y_bottom - wave_h * 0.5:.1f} {cx:.1f} {y_bottom - wave_h * 0.67:.1f} '
        f'Q {cx + amp:.1f} {y_bottom - wave_h * 0.75:.1f} {cx:.1f} {y_top + 2:.1f}" '
        f'fill="none" stroke="#111827" stroke-width="1.2"/>'
    )

    # Arrow indicating direction
    if wave_dir == "downward":
        svg += (
            f'<polygon points="{cx:.1f},{y_bottom:.1f} {cx - 3:.1f},{y_bottom - 5:.1f} '
            f'{cx + 3:.1f},{y_bottom - 5:.1f}" fill="#111827"/>'
        )
    else:
        svg += (
            f'<polygon points="{cx:.1f},{y_top:.1f} {cx - 3:.1f},{y_top + 5:.1f} '
            f'{cx + 3:.1f},{y_top + 5:.1f}" fill="#111827"/>'
        )

    svg += '</g>'
    return svg


def _render_path_annotation(entry: dict) -> str:
    """Render path-sign trajectory marks (straight/curved/spiral/circle).

    Shape logic adapted from the equivalent path-shape dispatch already
    written in svg_renderer.py's _render_path_symbol, fitted to the
    annotation-area geometry (a narrow column beside the staff) instead of
    a diagram box.
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    direction = symbol.get("direction")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2
    mirror = -1 if direction in ("left", "diagonal_forward_left", "diagonal_backward_left") else 1

    spec = entry.get("spec", {})
    path_shape = spec.get("behavior", {}).get("path_shape", "straight")

    if path_shape == "spiral":
        content = (
            f'<path d="M {cx:.1f} {y_bottom - 2:.1f} C {cx - 6:.1f} {y_bottom - 8:.1f}, '
            f'{cx + 6:.1f} {cy + 3:.1f}, {cx:.1f} {cy:.1f} '
            f'S {cx - 6:.1f} {y_top + 8:.1f}, {cx:.1f} {y_top + 2:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.4"/>'
        )
    elif path_shape == "circle":
        radius = max(min(w, y_bottom - y_top) / 2 - 2, 3)
        content = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="none" stroke="#111827" stroke-width="1.4"/>'
    elif path_shape == "curved":
        content = (
            f'<path d="M {cx + mirror * 5:.1f} {y_bottom - 2:.1f} '
            f'Q {cx - mirror * 6:.1f} {cy:.1f} {cx + mirror * 5:.1f} {y_top + 2:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.6"/>'
        )
    else:  # straight (default)
        content = (
            f'<line x1="{cx:.1f}" y1="{y_bottom - 2:.1f}" x2="{cx:.1f}" y2="{y_top + 2:.1f}" '
            f'stroke="#111827" stroke-width="1.6"/>'
        )

    return f'<g class="laban-annotation path" data-symbol-id="{escape(symbol_id)}">{content}</g>'


def _render_music_rest_annotation(entry: dict) -> str:
    """Render music rest glyphs (quarter/eighth/sixteenth) for music.rest.*
    symbols not used as measure headers. Adapted from the equivalent glyphs
    already written in svg_renderer.py's _render_music_symbol.
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2

    if symbol_id.endswith("rest.sixteenth"):
        content = (
            f'<path d="M {cx - 1:.1f} {y_top + 2:.1f} Q {cx + 4:.1f} {y_top + 5:.1f} {cx:.1f} {y_top + 9:.1f} '
            f'L {cx - 4:.1f} {y_bottom - 4:.1f}" fill="none" stroke="#111827" stroke-width="1.3"/>'
            f'<circle cx="{cx - 4:.1f}" cy="{y_bottom - 4:.1f}" r="1.6" fill="#111827"/>'
            f'<circle cx="{cx - 2:.1f}" cy="{(y_top + y_bottom) / 2:.1f}" r="1.6" fill="#111827"/>'
        )
    elif symbol_id.endswith("rest.eighth"):
        content = (
            f'<path d="M {cx - 1:.1f} {y_top + 2:.1f} Q {cx + 4:.1f} {y_top + 6:.1f} {cx:.1f} {y_top + 11:.1f} '
            f'L {cx - 4:.1f} {y_bottom - 3:.1f}" fill="none" stroke="#111827" stroke-width="1.4"/>'
            f'<circle cx="{cx - 4:.1f}" cy="{y_bottom - 3:.1f}" r="1.8" fill="#111827"/>'
        )
    else:  # quarter rest (default)
        content = (
            f'<path d="M {cx - 2:.1f} {y_top + 3:.1f} Q {cx + 4:.1f} {(y_top + y_bottom) / 2 - 4:.1f} {cx - 1:.1f} {(y_top + y_bottom) / 2:.1f} '
            f'Q {cx - 6:.1f} {(y_top + y_bottom) / 2 + 6:.1f} {cx + 2:.1f} {y_bottom - 3:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
        )

    return f'<g class="laban-annotation music" data-symbol-id="{escape(symbol_id)}">{content}</g>'


def _render_dynamic_annotation(entry: dict) -> str:
    """Render dynamic accent (>) or diminuendo (<) marks."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    if symbol_id.endswith("diminuendo"):
        path_d = f"M {cx + 5:.1f} {cy - 5:.1f} L {cx - 5:.1f} {cy:.1f} L {cx + 5:.1f} {cy + 5:.1f}"
    else:
        path_d = f"M {cx - 5:.1f} {cy - 5:.1f} L {cx + 5:.1f} {cy:.1f} L {cx - 5:.1f} {cy + 5:.1f}"

    return (
        f'<g class="laban-annotation dynamic" data-symbol-id="{escape(symbol_id)}">'
        f'<path d="{path_d}" fill="none" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/>'
        f'</g>'
    )


def _render_adlib_annotation(entry: dict) -> str:
    """Render wavy ad-lib (improvisation) marks."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    if symbol_id.endswith("vertical"):
        path_d = (
            f"M {cx:.1f} {y_top + 2:.1f} C {cx + 4:.1f} {y_top + 5:.1f}, {cx - 4:.1f} {y_top + 9:.1f}, "
            f"{cx:.1f} {y_top + 12:.1f} S {cx + 4:.1f} {y_top + 18:.1f}, {cx:.1f} {y_bottom - 2:.1f}"
        )
    else:
        path_d = (
            f"M {x + 2:.1f} {cy:.1f} C {x + 5:.1f} {cy - 3:.1f}, {x + 9:.1f} {cy + 3:.1f}, {cx:.1f} {cy:.1f} "
            f"S {x + w - 5:.1f} {cy - 3:.1f}, {x + w - 2:.1f} {cy:.1f}"
        )

    return (
        f'<g class="laban-annotation adlib" data-symbol-id="{escape(symbol_id)}">'
        f'<path d="{path_d}" fill="none" stroke="#111827" stroke-width="1.5"/>'
        f'</g>'
    )


def _render_motif_annotation(entry: dict) -> str:
    """Render motif-writing rise/fall/arc marks (direction-mirrored)."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    direction = symbol.get("direction")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    mirror = -1 if direction in ("left", "diagonal_forward_left", "diagonal_backward_left") else 1

    if symbol_id.endswith("rise_fall"):
        cy = (y_top + y_bottom) / 2
        content = (
            f'<path d="M {cx - 6:.1f} {y_bottom - 3:.1f} Q {cx - 2 + mirror * 2:.1f} {y_top + 4:.1f} {cx:.1f} {cy:.1f} '
            f'Q {cx + 2 + mirror * 2:.1f} {y_bottom - 6:.1f} {cx + 6:.1f} {y_top + 5:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.7"/>'
        )
    elif symbol_id.endswith("arc"):
        arc_y = y_bottom - (y_bottom - y_top) * 0.28
        content = (
            f'<path d="M {x + 3:.1f} {arc_y:.1f} Q {cx + mirror * 4:.1f} {y_top + 2:.1f} {x + w - 3:.1f} {arc_y:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.8"/>'
        )
    elif symbol_id.endswith("fall"):
        content = (
            f'<line x1="{cx:.1f}" y1="{y_top + 4:.1f}" x2="{cx + mirror * 2:.1f}" y2="{y_bottom - 7:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{cx + mirror * 2:.1f},{y_bottom + 1:.1f} {cx - 5 + mirror * 2:.1f},{y_bottom - 8:.1f} {cx + 5 + mirror * 2:.1f},{y_bottom - 8:.1f}" fill="#111827"/>'
        )
    else:
        content = (
            f'<line x1="{cx:.1f}" y1="{y_bottom - 4:.1f}" x2="{cx + mirror * 2:.1f}" y2="{y_top + 8:.1f}" stroke="#111827" stroke-width="1.8"/>'
            f'<polygon points="{cx + mirror * 2:.1f},{y_top + 1:.1f} {cx - 5 + mirror * 2:.1f},{y_top + 10:.1f} {cx + 5 + mirror * 2:.1f},{y_top + 10:.1f}" fill="#111827"/>'
        )

    return f'<g class="laban-annotation motif" data-symbol-id="{escape(symbol_id)}">{content}</g>'


def _render_pin_annotation(entry: dict) -> str:
    """Render dedicated pin symbols with head variants.

    Pin heads based on modifiers.pin_head:
    - "circle": vertical line with open circle at top
    - "diamond": vertical line with small rotated square at top
    - default: vertical line with filled triangle arrowhead at top
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    modifiers = symbol.get("modifiers", {})
    pin_head = modifiers.get("pin_head", "triangle")
    pin_length = modifiers.get("pin_length", 10)
    half_len = pin_length / 2

    svg = f'<g class="laban-annotation pin" data-symbol-id="{escape(symbol_id)}">'

    # Vertical line (stem)
    svg += (
        f'<line x1="{cx:.1f}" y1="{cy + half_len:.1f}" '
        f'x2="{cx:.1f}" y2="{cy - half_len:.1f}" '
        f'stroke="#111827" stroke-width="1.5"/>'
    )

    # Pin head
    head_y = cy - half_len
    if pin_head == "circle":
        svg += (
            f'<circle cx="{cx:.1f}" cy="{head_y - 3:.1f}" r="3" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
        )
    elif pin_head == "diamond":
        s = 2.5
        svg += (
            f'<path d="M {cx:.1f} {head_y - s * 2:.1f} '
            f'L {cx + s:.1f} {head_y - s:.1f} '
            f'L {cx:.1f} {head_y:.1f} '
            f'L {cx - s:.1f} {head_y - s:.1f} Z" '
            f'fill="#111827" stroke="#111827" stroke-width="0.8"/>'
        )
    else:
        # Default: filled triangle arrowhead
        svg += (
            f'<polygon points="{cx:.1f},{head_y - 6:.1f} '
            f'{cx - 3:.1f},{head_y:.1f} {cx + 3:.1f},{head_y:.1f}" '
            f'fill="#111827"/>'
        )

    svg += '</g>'
    return svg


def _render_bow_annotation(entry: dict) -> str:
    """Render bow variants: hook bow and tie bow.

    - Hook bow: standard bow arc with small hooks (curls) at endpoints
    - Tie bow: symmetric shallow arc connecting two beat positions (hold/legato)
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2

    modifiers = symbol.get("modifiers", {})
    bow_type = modifiers.get("bow_type", "hook")

    svg = f'<g class="laban-annotation bow" data-symbol-id="{escape(symbol_id)}">'

    left_x = cx - 6
    right_x = cx + 6
    base_y = y_bottom - 4
    peak_y = y_top + 4

    if bow_type == "tie":
        # Symmetric shallow arc for hold/legato
        svg += (
            f'<path d="M {left_x:.1f} {base_y:.1f} '
            f'C {left_x:.1f} {(base_y + peak_y) / 2:.1f} '
            f'{right_x:.1f} {(base_y + peak_y) / 2:.1f} '
            f'{right_x:.1f} {base_y:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
        )
    else:
        # Hook bow: standard arc with small hooks at endpoints
        hook_r = 2
        svg += (
            f'<path d="M {left_x:.1f} {base_y:.1f} '
            f'C {left_x:.1f} {peak_y - 4:.1f} {right_x:.1f} {peak_y - 4:.1f} '
            f'{right_x:.1f} {base_y:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
            # Left hook (small curl downward)
            f'<path d="M {left_x:.1f} {base_y:.1f} '
            f'Q {left_x - hook_r:.1f} {base_y:.1f} '
            f'{left_x - hook_r:.1f} {base_y + hook_r:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
            # Right hook (small curl downward)
            f'<path d="M {right_x:.1f} {base_y:.1f} '
            f'Q {right_x + hook_r:.1f} {base_y:.1f} '
            f'{right_x + hook_r:.1f} {base_y + hook_r:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
        )

    svg += '</g>'
    return svg


def _render_generic_annotation(entry: dict) -> str:
    """Fallback annotation renderer."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2
    label = symbol_id.split(".")[-1][:4]

    return (
        f'<g class="laban-annotation" data-symbol-id="{escape(symbol_id)}">'
        f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="7" fill="#64748b">'
        f'{escape(label)}</text>'
        f'</g>'
    )


def _render_foot_detail_annotation(entry: dict) -> str:
    """Render foot-surface/hook/position/digit modifier marks.

    These catalog entries (staff_column "foothook"/"digit") are small
    non-directional modifiers (requires_direction=False, anchor="adjacent")
    covering ~30 distinct concepts (foot surface, edge, hook, position,
    digit pointer). Rather than inventing bespoke geometry for each, this
    reuses the catalog author's own designated glyph as a small marker —
    consistent with the symbol's "adjacent" anchor intent, and avoids the
    misrendering-as-a-direction-pentagon bug this family had before routing
    was fixed (see ANNOTATION_FAMILIES in laban_layout.py).
    """
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    spec = entry.get("spec", {})
    glyph = spec.get("geometry", {}).get("glyph") or "?"
    x = entry["x"]
    y_top = entry["y_top"]
    y_bottom = entry["y_bottom"]
    w = entry["width"]
    cx = x + w / 2
    cy = (y_top + y_bottom) / 2

    return (
        f'<g class="laban-annotation foot-detail" data-symbol-id="{escape(symbol_id)}">'
        f'<text x="{cx:.1f}" y="{cy + 4:.1f}" text-anchor="middle" font-size="10" fill="#111827">'
        f'{escape(glyph)}</text>'
        f'</g>'
    )


def _render_annotation(entry: dict) -> str:
    """Dispatch annotation rendering by family."""
    family = entry["family"]
    staff_column = entry.get("spec", {}).get("geometry", {}).get("staff_column")
    if staff_column in ("foothook", "digit"):
        return _render_foot_detail_annotation(entry)
    if family == "turn":
        return _render_turn_annotation(entry)
    if family == "jump":
        return _render_jump_annotation(entry)
    if family == "quality":
        return _render_quality_annotation(entry)
    if family in ("timing", "level"):
        return _render_timing_annotation(entry)
    if family == "repeat":
        return _render_repeat_annotation(entry)
    if family == "retention":
        return _render_retention_annotation(entry)
    if family in ("contact", "surface"):
        return _render_contact_annotation(entry)
    if family == "path":
        return _render_path_annotation(entry)
    if family == "music":
        return _render_music_rest_annotation(entry)
    if family == "effort":
        return _render_effort_diamond(entry)
    if family == "pin":
        return _render_pin_annotation(entry)
    if family == "bow":
        return _render_bow_annotation(entry)
    if family == "dynamic":
        return _render_dynamic_annotation(entry)
    if family == "adlib":
        return _render_adlib_annotation(entry)
    if family == "motif":
        return _render_motif_annotation(entry)
    if family == "flexion":
        return _render_flexion_symbol(entry)
    if family == "shape":
        return _render_shape_symbol(entry)
    if family == "floor_plan" or staff_column == "floor_plan":
        # floor_plan.json's zone symbols (e.g. "floor.zone.downstage_left")
        # collide with the unrelated "floor.roll" body-action family on
        # symbol_id prefix ("floor" for both) — staff_column ("floor_plan"
        # vs "floor") is the only reliable signal distinguishing them.
        return _render_stage_marker(entry)
    if family == "sequential":
        return _render_sequential_annotation(entry)
    return _render_generic_annotation(entry)


def _render_measure_header(entry: dict, staff_left: float, staff_right: float,
                           measure_positions: dict) -> str:
    """Render time signature or tempo mark at the start of a measure."""
    symbol = entry["symbol"]
    symbol_id = symbol.get("symbol_id", "")
    m = entry["measure"]

    if m not in measure_positions:
        return ""

    m_bottom, m_top = measure_positions[m]

    if ".time." in symbol_id:
        parts = symbol_id.split(".time.", 1)[1].split("_")
        x = staff_left - 30
        cy = m_bottom - 10
        return (
            f'<g class="laban-header time-sig">'
            f'<text x="{x:.1f}" y="{cy - 4:.1f}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#111827">{parts[0]}</text>'
            f'<text x="{x:.1f}" y="{cy + 10:.1f}" text-anchor="middle" '
            f'font-size="12" font-weight="700" fill="#111827">{parts[1]}</text>'
            f'</g>'
        )

    if symbol_id.endswith("tempo.mark"):
        tempo = symbol.get("modifiers", {}).get("tempo", 120)
        x = staff_right + 10
        cy = m_bottom - 10
        return (
            f'<g class="laban-header tempo">'
            f'<text x="{x:.1f}" y="{cy + 4:.1f}" text-anchor="start" '
            f'font-size="9" fill="#475569">&#x2669;={tempo}</text>'
            f'</g>'
        )

    if symbol_id.endswith("cadence.mark"):
        label = symbol.get("modifiers", {}).get("label", "cad.")
        x = staff_right + 10
        cy = m_bottom - 10
        return (
            f'<g class="laban-header cadence">'
            f'<text x="{x:.1f}" y="{cy + 4:.1f}" text-anchor="start" '
            f'font-size="8" font-style="italic" fill="#475569">{escape(label)}</text>'
            f'</g>'
        )

    return ""


# ── Main renderer ─────────────────────────────────────────────────────

def _render_relationship_bow(bow: dict, placed_symbols: list[dict]) -> str:
    """Render a curved line connecting two symbols showing body-part relationship.

    bow_type visuals:
    - "touch": thin solid line
    - "near": thin dashed line
    - "grasp": thick solid line with small hooks at each end
    - "support_on": double line
    """
    src_idx = bow.get("source_symbol_index", 0)
    tgt_idx = bow.get("target_symbol_index", 0)
    bow_type = bow.get("bow_type", "touch")
    side = bow.get("side", "right")

    if src_idx >= len(placed_symbols) or tgt_idx >= len(placed_symbols):
        return ""

    src = placed_symbols[src_idx]
    tgt = placed_symbols[tgt_idx]

    # Source/target midpoints
    sx = (src["x_left"] + src["x_right"]) / 2
    sy = (src["y_top"] + src["y_bottom"]) / 2
    tx = (tgt["x_left"] + tgt["x_right"]) / 2
    ty = (tgt["y_top"] + tgt["y_bottom"]) / 2

    # Control point offset for bezier curve — ensure visible arc even when
    # source and target are at similar y-coordinates
    dy = abs(ty - sy)
    min_bulge = 40  # minimum horizontal bulge for visibility
    offset = max(min_bulge, dy * 0.4) * (1 if side == "right" else -1)
    # When src and tgt are horizontally close, add vertical spread to control points
    mid_y = (sy + ty) / 2
    vert_spread = max(20, dy * 0.3)
    c1x = sx + offset
    c1y = mid_y - vert_spread
    c2x = tx + offset
    c2y = mid_y + vert_spread

    svg = '<g class="relationship-bow">'

    if bow_type == "touch":
        svg += (
            f'<path d="M {sx:.1f} {sy:.1f} C {c1x:.1f} {c1y:.1f} '
            f'{c2x:.1f} {c2y:.1f} {tx:.1f} {ty:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1"/>'
        )
    elif bow_type == "near":
        svg += (
            f'<path d="M {sx:.1f} {sy:.1f} C {c1x:.1f} {c1y:.1f} '
            f'{c2x:.1f} {c2y:.1f} {tx:.1f} {ty:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1" stroke-dasharray="4,3"/>'
        )
    elif bow_type == "grasp":
        hook_r = 3
        svg += (
            f'<path d="M {sx:.1f} {sy:.1f} C {c1x:.1f} {c1y:.1f} '
            f'{c2x:.1f} {c2y:.1f} {tx:.1f} {ty:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="2.5"/>'
            # Hook at source
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{hook_r}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
            # Hook at target
            f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{hook_r}" '
            f'fill="none" stroke="#111827" stroke-width="1.5"/>'
        )
    elif bow_type == "support_on":
        # Double line: two parallel curves offset by 2px
        off2 = 2
        svg += (
            f'<path d="M {sx:.1f} {sy - off2:.1f} C {c1x:.1f} {c1y - off2:.1f} '
            f'{c2x:.1f} {c2y - off2:.1f} {tx:.1f} {ty - off2:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
            f'<path d="M {sx:.1f} {sy + off2:.1f} C {c1x:.1f} {c1y + off2:.1f} '
            f'{c2x:.1f} {c2y + off2:.1f} {tx:.1f} {ty + off2:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.2"/>'
        )
    else:
        # Fallback: thin solid
        svg += (
            f'<path d="M {sx:.1f} {sy:.1f} C {c1x:.1f} {c1y:.1f} '
            f'{c2x:.1f} {c2y:.1f} {tx:.1f} {ty:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1"/>'
        )

    svg += '</g>'
    return svg


def _render_effort_graph_overlay(eg: dict, placed_symbols: list[dict],
                                 layout: dict) -> str:
    """Render an effort graph diamond in the right annotation area.

    The effort graph is positioned at the time position of its associated symbol
    (if symbol_index is given) or at its measure/beat position.
    """
    weight = eg.get("weight")   # "strong" or "light"
    time = eg.get("time")       # "sudden" or "sustained"
    space = eg.get("space")     # "direct" or "indirect"
    flow = eg.get("flow")       # "bound" or "free"

    # Determine vertical position from symbol_index or measure/beat
    symbol_idx = eg.get("symbol_index")
    measure = eg.get("measure", 1)
    beat = eg.get("beat", 1)

    cy = None
    if symbol_idx is not None and symbol_idx < len(placed_symbols):
        entry = placed_symbols[symbol_idx]
        cy = (entry["y_top"] + entry["y_bottom"]) / 2

    if cy is None:
        # Fall back to measure position
        mp = layout.get("measure_positions", {})
        if measure in mp:
            m_bottom, m_top = mp[measure]
            beats = beats_for_measure(measure, layout.get("beats_map", {}))
            beat_h = (m_bottom - m_top) / beats
            cy = m_bottom - (beat - 1) * beat_h - beat_h / 2
        else:
            return ""

    # Place in right annotation area
    systems = layout.get("systems", [])
    if not systems:
        return ""
    sys0 = systems[0]
    cx = sys0["staff_right"] + ANNOTATION_GAP + ANNOTATION_WIDTH / 2 + 20

    s = 8  # half-size of diamond

    svg = '<g class="effort-graph">'

    # Diamond outline
    svg += (
        f'<path d="M {cx:.1f} {cy - s:.1f} L {cx + s:.1f} {cy:.1f} '
        f'L {cx:.1f} {cy + s:.1f} L {cx - s:.1f} {cy:.1f} Z" '
        f'fill="none" stroke="#111827" stroke-width="1.2"/>'
    )

    # Dividing cross
    svg += (
        f'<line x1="{cx:.1f}" y1="{cy - s:.1f}" x2="{cx:.1f}" y2="{cy + s:.1f}" '
        f'stroke="#111827" stroke-width="0.8"/>'
        f'<line x1="{cx - s:.1f}" y1="{cy:.1f}" x2="{cx + s:.1f}" y2="{cy:.1f}" '
        f'stroke="#111827" stroke-width="0.8"/>'
    )

    # Active efforts shown as filled quadrants with slash lines
    # Weight (top-right): strong = filled
    if weight == "strong":
        svg += (
            f'<path d="M {cx:.1f} {cy - s:.1f} L {cx + s:.1f} {cy:.1f} L {cx:.1f} {cy:.1f} Z" '
            f'fill="#111827" opacity="0.6"/>'
        )
    # Time (top-left): sudden = filled
    if time == "sudden":
        svg += (
            f'<path d="M {cx:.1f} {cy - s:.1f} L {cx - s:.1f} {cy:.1f} L {cx:.1f} {cy:.1f} Z" '
            f'fill="#111827" opacity="0.6"/>'
        )
    # Space (bottom-left): direct = filled
    if space == "direct":
        svg += (
            f'<path d="M {cx:.1f} {cy:.1f} L {cx - s:.1f} {cy:.1f} L {cx:.1f} {cy + s:.1f} Z" '
            f'fill="#111827" opacity="0.6"/>'
        )
    # Flow (bottom-right): bound = filled
    if flow == "bound":
        svg += (
            f'<path d="M {cx:.1f} {cy:.1f} L {cx + s:.1f} {cy:.1f} L {cx:.1f} {cy + s:.1f} Z" '
            f'fill="#111827" opacity="0.6"/>'
        )

    svg += '</g>'
    return svg


def render_laban_svg(ir: dict) -> str:
    """Render IR as a standard Labanotation SVG score.

    Scores with more than ``LABAN_SYSTEM_CAPACITY`` measures are
    automatically wrapped into multiple side-by-side staff systems.
    """
    layout = compute_laban_layout(ir)

    width = layout["width"]
    height = layout["height"]
    systems = layout["systems"]
    measure_positions = layout["measure_positions"]
    placed_symbols = layout["placed_symbols"]
    annotation_entries = layout["annotation_entries"]
    header_entries = layout["header_entries"]
    mc = layout["measure_count"]
    beats_map = layout.get("beats_map", {})
    title = escape(layout["title"])

    # Use centre of the canvas (or first system) for title placement
    title_x = width / 2

    elements: list[str] = []

    # Background
    elements.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fefefe"/>')

    # ── Build all <defs> in a single block at the top ────────────────
    # This includes: hatch pattern, arrow marker, AND direction symbol templates.
    ctx = _RenderContext()
    use_defs: dict[tuple[str, str], str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for entry in placed_symbols:
        sym = entry["symbol"]
        d = sym.get("direction") or "place"
        lv = sym.get("level") or "middle"
        seen_pairs.add((d, lv))

    import re as _re
    REF_W, REF_H = 20, 40
    symbol_defs = []
    for d, lv in sorted(seen_pairs):
        def_id = f"laban-dir-{d}-{lv}"
        use_defs[(d, lv)] = def_id
        path_d = _direction_path(d, 0, 0, REF_W, REF_H)
        style = LEVEL_FILLS.get(lv, LEVEL_FILLS["middle"])
        coords = _re.findall(r'[-+]?\d*\.?\d+', path_d)
        xs = [float(coords[i]) for i in range(0, len(coords), 2)]
        ys = [float(coords[i]) for i in range(1, len(coords), 2)]
        pad = 2
        vb_x, vb_y = min(xs) - pad, min(ys) - pad
        vb_w = max(xs) - min(xs) + 2 * pad
        vb_h = max(ys) - min(ys) + 2 * pad
        symbol_defs.append(
            f'<symbol id="{def_id}" viewBox="{vb_x:.1f} {vb_y:.1f} {vb_w:.1f} {vb_h:.1f}">'
            f'<path d="{path_d}" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="1.5"/>'
            f'</symbol>'
        )

    elements.append(
        '<defs>'
        '  <pattern id="laban-hatch" patternUnits="userSpaceOnUse" width="4" height="4" '
        '   patternTransform="rotate(45)">'
        '    <line x1="0" y1="0" x2="0" y2="4" stroke="#555" stroke-width="1.5"/>'
        '  </pattern>'
        '  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        '   markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '    <path d="M 0 0 L 10 5 L 0 10 Z" fill="#111827"/>'
        '  </marker>'
        + ''.join(symbol_defs) +
        '</defs>'
    )

    # Title
    elements.append(
        f'<text x="{title_x:.1f}" y="28" text-anchor="middle" '
        f'font-size="16" font-weight="700" font-family="serif" fill="#111827">{title}</text>'
    )
    elements.append(
        f'<text x="{title_x:.1f}" y="44" text-anchor="middle" '
        f'font-size="9" font-family="serif" fill="#6b7280">Labanotation Score</text>'
    )

    # ── Draw each system ─────────────────────────────────────────────

    for sys in systems:
        si = sys["system_index"]
        s_staff_left = sys["staff_left"]
        s_staff_right = sys["staff_right"]
        s_staff_center_x = sys["staff_center_x"]
        s_col_positions = sys["col_positions"]
        s_measure_positions = sys["measure_positions"]
        start_m = sys["start_measure"]
        end_m = sys["end_measure"]

        if not s_measure_positions:
            continue

        staff_visual_bottom = s_measure_positions[start_m][0] + 4
        staff_visual_top = s_measure_positions[end_m][1] - 4

        # System group wrapper
        elements.append(
            f'<g class="laban-system" data-system="{si + 1}" '
            f'data-measures="{start_m}-{end_m}">'
        )

        # Staff outer boundary
        elements.append(
            f'<rect x="{s_staff_left:.1f}" y="{staff_visual_top:.1f}" '
            f'width="{s_staff_right - s_staff_left:.1f}" '
            f'height="{staff_visual_bottom - staff_visual_top:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="2"/>'
        )

        # Center line (bold)
        elements.append(
            f'<line x1="{s_staff_center_x:.1f}" y1="{staff_visual_top:.1f}" '
            f'x2="{s_staff_center_x:.1f}" y2="{staff_visual_bottom:.1f}" '
            f'stroke="#111827" stroke-width="2.5"/>'
        )

        # No column divider lines: per the LabanWriter manual, column guides
        # are on-screen placement aids only ("these dots are guidelines to
        # show columns. They do not print"). The staff prints only its outer
        # box, center line, and measure lines.

        # Measure bar lines
        for m in range(start_m, end_m + 1):
            m_bottom, m_top = s_measure_positions[m]
            elements.append(
                f'<line x1="{s_staff_left:.1f}" y1="{m_bottom:.1f}" '
                f'x2="{s_staff_right:.1f}" y2="{m_bottom:.1f}" '
                f'stroke="#111827" stroke-width="1.2"/>'
            )
            if m == end_m:
                elements.append(
                    f'<line x1="{s_staff_left:.1f}" y1="{m_top:.1f}" '
                    f'x2="{s_staff_right:.1f}" y2="{m_top:.1f}" '
                    f'stroke="#111827" stroke-width="1.2"/>'
                )

            # Beat tick marks
            measure_h = m_bottom - m_top
            m_bpm = beats_for_measure(m, beats_map)
            for b in range(1, int(m_bpm)):
                tick_y = m_bottom - b * (measure_h / m_bpm)
                elements.append(
                    f'<line x1="{s_staff_center_x - 3:.1f}" y1="{tick_y:.1f}" '
                    f'x2="{s_staff_center_x + 3:.1f}" y2="{tick_y:.1f}" '
                    f'stroke="#666" stroke-width="0.8"/>'
                )

        # Starting double bar: thick (outer) + thin (inner) at bottom of system
        bottom_y = s_measure_positions[start_m][0]
        elements.append(
            f'<line x1="{s_staff_left:.1f}" y1="{bottom_y + 4:.1f}" '
            f'x2="{s_staff_right:.1f}" y2="{bottom_y + 4:.1f}" '
            f'stroke="#111827" stroke-width="3"/>'
        )
        elements.append(
            f'<line x1="{s_staff_left:.1f}" y1="{bottom_y + 1:.1f}" '
            f'x2="{s_staff_right:.1f}" y2="{bottom_y + 1:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
        )

        # Ending double bar: thin + thick at top of last measure
        top_y = s_measure_positions[end_m][1]
        elements.append(
            f'<line x1="{s_staff_left:.1f}" y1="{top_y - 1:.1f}" '
            f'x2="{s_staff_right:.1f}" y2="{top_y - 1:.1f}" '
            f'stroke="#111827" stroke-width="1"/>'
        )
        elements.append(
            f'<line x1="{s_staff_left:.1f}" y1="{top_y - 4:.1f}" '
            f'x2="{s_staff_right:.1f}" y2="{top_y - 4:.1f}" '
            f'stroke="#111827" stroke-width="3"/>'
        )

        # Starting position area (below measure 1, only in first system)
        sp_top = sys.get("starting_pos_top")
        sp_bottom = sys.get("starting_pos_bottom")
        if sp_top is not None and sp_bottom is not None:
            # Dashed boundary for starting position box
            elements.append(
                f'<rect x="{s_staff_left:.1f}" y="{sp_top:.1f}" '
                f'width="{s_staff_right - s_staff_left:.1f}" '
                f'height="{sp_bottom - sp_top:.1f}" '
                f'fill="none" stroke="#111827" stroke-width="1" '
                f'stroke-dasharray="4,3"/>'
            )
            # Center line extends into starting position
            elements.append(
                f'<line x1="{s_staff_center_x:.1f}" y1="{sp_top:.1f}" '
                f'x2="{s_staff_center_x:.1f}" y2="{sp_bottom:.1f}" '
                f'stroke="#111827" stroke-width="1.5" stroke-dasharray="4,3"/>'
            )

        # Measure numbers
        for m in range(start_m, end_m + 1):
            m_bottom, m_top = s_measure_positions[m]
            elements.append(
                f'<text x="{s_staff_left - 36:.1f}" y="{m_bottom - 4:.1f}" '
                f'text-anchor="end" font-size="9" fill="#999">{m}</text>'
            )

        # System number label (shown when more than one system)
        if len(systems) > 1:
            elements.append(
                f'<text x="{s_staff_center_x:.1f}" y="{staff_visual_bottom + 18:.1f}" '
                f'text-anchor="middle" font-size="9" font-style="italic" '
                f'fill="#999">System {si + 1}</text>'
            )

        elements.append('</g>')  # close laban-system group

        # System continuation connector (between this system and next)
        if si < len(systems) - 1:
            next_sys = systems[si + 1]
            next_top = min(pos[1] for pos in next_sys["measure_positions"].values())
            connector_y1 = staff_visual_bottom + 8
            connector_y2 = next_top - 8
            connector_mid = (connector_y1 + connector_y2) / 2
            # Vertical bracket with arrows on center line
            elements.append(
                f'<line x1="{s_staff_center_x:.1f}" y1="{connector_y1:.1f}" '
                f'x2="{s_staff_center_x:.1f}" y2="{connector_y2:.1f}" '
                f'stroke="#999" stroke-width="1" stroke-dasharray="3,3"/>'
            )
            # Small continuation arrow
            elements.append(
                f'<polygon points="{s_staff_center_x - 4:.1f},{connector_mid - 4:.1f} '
                f'{s_staff_center_x + 4:.1f},{connector_mid - 4:.1f} '
                f'{s_staff_center_x:.1f},{connector_mid + 4:.1f}" '
                f'fill="#999"/>'
            )

    # ── Render symbols ────────────────────────────────────────────────

    for entry in placed_symbols:
        elements.append(_render_staff_symbol(entry, ctx, use_defs))

    # ── Render annotations ────────────────────────────────────────────

    for entry in annotation_entries:
        elements.append(_render_annotation(entry))

    # ── Render measure headers ────────────────────────────────────────

    for entry in header_entries:
        si = entry.get("system_index", 0)
        if si < len(systems):
            sys = systems[si]
            elements.append(_render_measure_header(
                entry, sys["staff_left"], sys["staff_right"],
                sys["measure_positions"],
            ))

    # ── Render bridge routes ─────────────────────────────────────────

    for route in layout.get("bridge_routes", []):
        pts = route["points"]
        elements.append(
            f'<line x1="{pts[0][0]:.1f}" y1="{pts[0][1]:.1f}" '
            f'x2="{pts[1][0]:.1f}" y2="{pts[1][1]:.1f}" '
            f'stroke="#111827" stroke-width="1.5"/>'
        )

    # ── Render span routes ───────────────────────────────────────────

    for route in layout.get("span_routes", []):
        x = route["x"]
        y1 = route["y1"]
        y2 = route["y2"]
        cap = 9  # horizontal cap length
        elements.append(
            f'<path class="repeat-span" '
            f'd="M {x:.1f} {y1:.1f} L {x:.1f} {y2:.1f} '
            f'M {x:.1f} {y1:.1f} L {x + cap:.1f} {y1:.1f} '
            f'M {x:.1f} {y2:.1f} L {x + cap:.1f} {y2:.1f}" '
            f'fill="none" stroke="#111827" stroke-width="1.4"/>'
        )

    # ── Render attachment routes ─────────────────────────────────────

    for route in layout.get("attachment_routes", []):
        pts = route["points"]
        dash = ' stroke-dasharray="3,3"' if route.get("style") == "dashed" else ""
        elements.append(
            f'<line x1="{pts[0][0]:.1f}" y1="{pts[0][1]:.1f}" '
            f'x2="{pts[1][0]:.1f}" y2="{pts[1][1]:.1f}" '
            f'stroke="#94a3b8" stroke-width="1.2"{dash}/>'
        )

    # ── Render relationship bows ────────────────────────────────────

    for bow in ir.get("relationship_bows", []):
        elements.append(_render_relationship_bow(bow, placed_symbols))

    # ── Render effort graphs ─────────────────────────────────────────

    for eg in ir.get("effort_graphs", []):
        elements.append(_render_effort_graph_overlay(eg, placed_symbols, layout))

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        *elements,
        "</svg>",
    ])
