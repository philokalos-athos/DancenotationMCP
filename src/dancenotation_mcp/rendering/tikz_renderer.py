from __future__ import annotations

from dancenotation_mcp.ir.time_signatures import beats_for_measure
from dancenotation_mcp.rendering.layout import (
    BEAT_HEIGHT,
    BODY_LANES,
    COLUMN_LANES,
    MARGIN_X,
    compute_layout,
    entry_family,
    is_measure_header,
    measure_header_text,
    simplify_polyline,
)


def _pt(px: float) -> str:
    """Convert SVG px to TeX pt (approximate 1:1 for tikz)."""
    return f"{px:.1f}pt"


def _tikz_coord(x: float, y: float) -> str:
    """TikZ coordinate. SVG y goes down; TikZ y goes up, so we negate y."""
    return f"({x:.1f}pt, {-y:.1f}pt)"


def _escape_tex(text: str) -> str:
    for ch in ("\\", "{", "}", "&", "%", "$", "#", "_", "^", "~"):
        text = text.replace(ch, f"\\{ch}")
    return text


# Per the LabanWriter manual: High = striped, Middle = blank/unshaded,
# Low = solid black. See laban_renderer.py's LEVEL_FILLS for the citation.
_LEVEL_TIKZ = {
    "high": ("pattern=north east lines, pattern color=gray", "draw=black"),
    "middle": ("white", "draw=black"),
    "low": ("fill=black", "draw=black, text=white"),
}

_TIKZ_PREAMBLE = r"""\documentclass[border=10pt]{standalone}
\usepackage{tikz}
\usetikzlibrary{patterns, arrows.meta}

\tikzset{
  laban staff/.style={draw=gray!40, thin},
  beat grid/.style={draw=gray!30, dashed, thin},
  measure line/.style={draw=gray!60, semithick},
  laban shape/.style={thick, line join=miter},
  symbol label/.style={font=\tiny\sffamily, text=gray!70},
  header card/.style={draw=blue!30, fill=blue!5, rounded corners=3pt, font=\tiny\sffamily},
  attachment line/.style={draw=gray!50, dashed, thin, -{Stealth[length=3pt]}},
  bridge line/.style={draw=gray!60, semithick},
  span line/.style={draw=gray!70, semithick},
  body label/.style={font=\tiny\sffamily, text=gray!60},
}

\begin{document}
\begin{tikzpicture}
"""

_TIKZ_POSTAMBLE = r"""\end{tikzpicture}
\end{document}
"""


def _tikz_direction_vertices(direction: str | None,
                              left: float, top: float,
                              right: float, bottom: float) -> list[str]:
    """Return TikZ coordinate list for an ICKL-standard Labanotation direction shape.

    Mirrors the geometry from laban_renderer.py:_direction_path().
    Coordinates are in SVG space (y-down); _tikz_coord() handles the y-flip.
    """
    w = right - left
    h = bottom - top
    cx = (left + right) / 2
    cy = (top + bottom) / 2

    if direction == "forward":
        tri_h = h * 0.27
        rect_top = top + tri_h
        return [
            _tikz_coord(cx, top),           # triangle apex
            _tikz_coord(right, rect_top),    # triangle right base
            _tikz_coord(right, bottom),      # rectangle bottom-right
            _tikz_coord(left, bottom),       # rectangle bottom-left
            _tikz_coord(left, rect_top),     # triangle left base
        ]

    if direction == "backward":
        tri_h = h * 0.27
        rect_bottom = bottom - tri_h
        return [
            _tikz_coord(left, top),          # rectangle top-left
            _tikz_coord(right, top),         # rectangle top-right
            _tikz_coord(right, rect_bottom), # triangle right base
            _tikz_coord(cx, bottom),         # triangle apex
            _tikz_coord(left, rect_bottom),  # triangle left base
        ]

    if direction == "right":
        return [
            _tikz_coord(left, top),
            _tikz_coord(right, cy),
            _tikz_coord(left, bottom),
        ]

    if direction == "left":
        return [
            _tikz_coord(right, top),
            _tikz_coord(left, cy),
            _tikz_coord(right, bottom),
        ]

    if direction == "diagonal_forward_right":
        skew = min(h * 0.32, w * 0.45)
        return [
            _tikz_coord(left, bottom),
            _tikz_coord(left + skew, top),
            _tikz_coord(right, top),
            _tikz_coord(right - skew, bottom),
        ]

    if direction == "diagonal_forward_left":
        skew = min(h * 0.32, w * 0.45)
        return [
            _tikz_coord(right, bottom),
            _tikz_coord(right - skew, top),
            _tikz_coord(left, top),
            _tikz_coord(left + skew, bottom),
        ]

    if direction == "diagonal_backward_right":
        skew = min(h * 0.32, w * 0.45)
        return [
            _tikz_coord(left + skew, top),
            _tikz_coord(right, top),
            _tikz_coord(right - skew, bottom),
            _tikz_coord(left, bottom),
        ]

    if direction == "diagonal_backward_left":
        skew = min(h * 0.32, w * 0.45)
        return [
            _tikz_coord(left, top),
            _tikz_coord(right - skew, top),
            _tikz_coord(right, bottom),
            _tikz_coord(left + skew, bottom),
        ]

    if direction == "place":
        inset = w * 0.20
        return [
            _tikz_coord(left + inset, top),
            _tikz_coord(right - inset, top),
            _tikz_coord(right - inset, bottom),
            _tikz_coord(left + inset, bottom),
        ]

    # Default: full rectangle
    return [
        _tikz_coord(left, top),
        _tikz_coord(right, top),
        _tikz_coord(right, bottom),
        _tikz_coord(left, bottom),
    ]


def render_tikz(ir: dict) -> str:
    layout = compute_layout(ir)
    lines: list[str] = [_TIKZ_PREAMBLE]

    width = layout["width"]
    height = layout["height"]
    staff_left = layout["staff_left"]
    lane_positions = layout["lane_positions"]
    measure_tops = layout["measure_tops"]
    systems = layout["systems"]
    mc = layout["measure_count"]
    m_right_padding = layout["measure_right_padding"]
    lane_right = layout["lane_right"]
    header_layout = layout["header_layout"]
    rendered_entries = layout["rendered_entries"]
    measure_headers_count = layout["measure_headers"]
    bridge_routes = layout["bridge_routes"]
    span_routes = layout["span_routes"]
    attachment_routes = layout["attachment_routes"]
    title = _escape_tex(layout["title"])
    order = BODY_LANES + COLUMN_LANES

    # Background
    lines.append(f"\\fill[white] {_tikz_coord(0, 0)} rectangle {_tikz_coord(width, height)};")

    # Title
    lines.append(f"\\node[anchor=west, font=\\Large\\bfseries] at {_tikz_coord(MARGIN_X, 34)} {{{title}}};")
    lines.append(f"\\node[anchor=west, font=\\small, text=gray] at {_tikz_coord(MARGIN_X, 56)} {{Laban staff — TikZ export}};")

    # Staff system frames
    for system in systems:
        x1 = staff_left - 10
        y1 = system["top"] - 14
        x2 = system["right"] + 10
        y2 = system["bottom"] + 14
        lines.append(f"\\draw[gray!30] {_tikz_coord(x1, y1)} rectangle {_tikz_coord(x2, y2)};")

    # Measure lines and beat grid
    beats_map = layout.get("beats_map", {})
    for mi in range(mc):
        mn = mi + 1
        y = measure_tops[mn]
        mr = lane_right + m_right_padding.get(mn, 52.0)
        m_bpm = beats_for_measure(mn, beats_map)
        mh = m_bpm * BEAT_HEIGHT

        # Alternating fill
        if mi % 2 == 0:
            lines.append(f"\\fill[blue!2] {_tikz_coord(staff_left - 10, y)} rectangle {_tikz_coord(mr + 10, y + mh)};")

        # Measure top line
        lines.append(f"\\draw[measure line] {_tikz_coord(staff_left - 10, y)} -- {_tikz_coord(mr + 10, y)};")
        lines.append(f"\\node[anchor=east, font=\\tiny, text=gray!60] at {_tikz_coord(staff_left - 6, y + 16)} {{M{mn}}};")

        # Beat grid
        for bi in range(1, int(m_bpm)):
            by = y + bi * (mh / m_bpm)
            lines.append(f"\\draw[beat grid] {_tikz_coord(staff_left - 10, by)} -- {_tikz_coord(mr + 10, by)};")
            lines.append(f"\\node[anchor=east, font=\\tiny, text=gray!40] at {_tikz_coord(staff_left - 6, by + 4)} {{{bi + 1}}};")

    # System bottom lines
    for system in systems:
        lines.append(f"\\draw[measure line] {_tikz_coord(staff_left - 10, system['bottom'])} -- {_tikz_coord(system['right'] + 10, system['bottom'])};")

    # Lane columns
    for system in systems:
        for lane in order:
            x = lane_positions[lane]
            lines.append(f"\\draw[laban staff] {_tikz_coord(x, system['top'] - 14)} -- {_tikz_coord(x, system['bottom'] + 14)};")
            label = _escape_tex(lane.replace("_", " ").title())
            lines.append(f"\\node[symbol label, anchor=south] at {_tikz_coord(x, system['top'] - 22)} {{{label}}};")

    # Symbols
    header_stack: dict[int, int] = {}
    for entry in rendered_entries:
        symbol = entry["symbol"]
        spec = entry["spec"]
        x = entry["x"]
        top = entry["top"]
        h = entry["height"]
        m = entry["measure"]
        geom = spec.get("geometry", {})
        symbol_id = symbol.get("symbol_id", "unknown")
        level = symbol.get("level") or "middle"
        direction = symbol.get("direction")
        body_part = symbol.get("body_part", "torso")
        block_width = max(int(geom.get("width", 20)), 18) + 16
        left = x - block_width / 2
        right = x + block_width / 2

        if is_measure_header(symbol, spec):
            si = header_stack.get(m, 0)
            header_stack[m] = si + 1
            band_width = header_layout.get(m, {}).get("max_text_width", 72.0) + 12.0
            card_width = band_width - 12.0
            hx = staff_left - card_width - 10
            hy = measure_tops[m] + 10 + (si * 22)
            text = _escape_tex(measure_header_text(symbol, spec))
            lines.append(f"\\node[header card, minimum width={_pt(card_width)}, minimum height=18pt] at {_tikz_coord(hx + card_width / 2, hy + 9)} {{{text}}};")
            continue

        # Level fill style
        fill_style, draw_style = _LEVEL_TIKZ.get(level, _LEVEL_TIKZ["middle"])

        # Direction shape path (ICKL geometry via \draw, no Unicode glyphs)
        vertices = _tikz_direction_vertices(direction, left, top, right, top + h)
        path_str = " -- ".join(vertices) + " -- cycle"
        lines.append(f"% {symbol_id} ({body_part}, {direction}, {level})")
        lines.append(f"\\fill[{fill_style}] {path_str};")
        lines.append(f"\\draw[laban shape] {path_str};")

        # Body label
        lines.append(f"\\node[body label, anchor=south] at {_tikz_coord(x, top - 6)} {{{_escape_tex(body_part.replace('_', ' '))}}};")

        # Symbol ID label
        lines.append(f"\\node[symbol label, anchor=north] at {_tikz_coord(x, top + h + 12)} {{{_escape_tex(symbol_id)}}};")

        # Annotation → body lane connector
        column = geom.get("staff_column", "")
        if column in {"quality", "level", "timing"}:
            target_lane = body_part
            if target_lane in lane_positions:
                lines.append(f"\\draw[gray!30, thin] {_tikz_coord(lane_positions[target_lane], top + h / 2)} -- {_tikz_coord(x - 10, top + h / 2)};")

    # Measure header bands
    for m, count in sorted(measure_headers_count.items()):
        band_width = header_layout.get(m, {}).get("max_text_width", 72.0) + 12.0
        bx = staff_left - band_width - 4
        by = measure_tops[m] + 4
        bh = max(24, count * 22 + 8)
        lines.append(f"\\fill[blue!3, rounded corners=4pt] {_tikz_coord(bx, by)} rectangle {_tikz_coord(bx + band_width, by + bh)};")
        lines.append(f"\\draw[blue!20, rounded corners=4pt] {_tikz_coord(bx, by)} rectangle {_tikz_coord(bx + band_width, by + bh)};")

    # Bridge routes
    for route in bridge_routes:
        pts = route["points"]
        lines.append(f"\\draw[bridge line] {_tikz_coord(pts[0][0], pts[0][1])} -- {_tikz_coord(pts[1][0], pts[1][1])};")

    # Span routes
    for route in span_routes:
        rx = route["x"]
        ry1 = route["y1"]
        ry2 = route["y2"]
        lines.append(f"\\draw[span line] {_tikz_coord(rx, ry1)} -- {_tikz_coord(rx, ry2)};")
        lines.append(f"\\draw[span line] {_tikz_coord(rx, ry1)} -- {_tikz_coord(rx + 9, ry1)};")
        lines.append(f"\\draw[span line] {_tikz_coord(rx, ry2)} -- {_tikz_coord(rx + 9, ry2)};")

    # Attachment routes
    for route in attachment_routes:
        points = route["points"]
        if route["route_type"] == "curve" and len(points) == 4:
            sx, sy = points[0]
            mx, _ = points[1]
            _, _ = points[2]
            tx, ty = points[3]
            lines.append(f"\\draw[attachment line] {_tikz_coord(sx, sy)} .. controls {_tikz_coord(mx, sy)} and {_tikz_coord(mx, ty)} .. {_tikz_coord(tx, ty)};")
        else:
            simplified = simplify_polyline(points)
            if len(simplified) >= 2:
                path_parts = [_tikz_coord(simplified[0][0], simplified[0][1])]
                for px, py in simplified[1:]:
                    path_parts.append(f"-- {_tikz_coord(px, py)}")
                lines.append(f"\\draw[attachment line] {' '.join(path_parts)};")

    lines.append(_TIKZ_POSTAMBLE)
    return "\n".join(lines)
