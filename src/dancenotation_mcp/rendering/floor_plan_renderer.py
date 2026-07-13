"""Floor plan SVG renderer.

Renders a top-down stage floor plan as an independent SVG showing:
- 300x200 px grid divided into 9 zones (3x3)
- Zone labels (DSL, DSC, DSR, CL, C, CR, USL, USC, USR)
- Wing columns left/right of the main grid, per the LabanWriter manual
  ("Wing columns can also be added to the floorplan to allow you to place
  pins outside the floorplan(s)") — for dancers waiting offstage.
- Dancer positions as filled circles
- Facing shown as arrows from circles
- Paths between positions as lines/curves
- Optional per-position captions, per the manual's "Caption Squares"
- Audience at bottom
"""

from __future__ import annotations

import math

from xml.sax.saxutils import escape

from dancenotation_mcp.ir.models import STAGE_FACINGS, STAGE_ZONES


# ── Zone layout ──────────────────────────────────────────────────────

ZONE_GRID = {
    "downstage_left":   (0, 2),
    "downstage_center": (1, 2),
    "downstage_right":  (2, 2),
    "center_left":      (0, 1),
    "center":           (1, 1),
    "center_right":     (2, 1),
    "upstage_left":     (0, 0),
    "upstage_center":   (1, 0),
    "upstage_right":    (2, 0),
}

ZONE_LABELS = {
    "downstage_left": "DSL", "downstage_center": "DSC", "downstage_right": "DSR",
    "center_left": "CL", "center": "C", "center_right": "CR",
    "upstage_left": "USL", "upstage_center": "USC", "upstage_right": "USR",
}

# Facing → angle in radians (0 = right, π/2 = up on SVG = upstage)
FACING_ANGLES = {
    "downstage": math.pi / 2 * 3,       # pointing down
    "upstage": math.pi / 2,             # pointing up
    "stage_left": math.pi,              # pointing left
    "stage_right": 0,                   # pointing right
    "diagonal_downstage_left": math.pi + math.pi / 4,
    "diagonal_downstage_right": math.pi / 4 * 7,
    "diagonal_upstage_left": math.pi * 3 / 4,
    "diagonal_upstage_right": math.pi / 4,
}

PLAN_WIDTH = 300
PLAN_HEIGHT = 200
GRID_COLS = 3
GRID_ROWS = 3
CELL_W = PLAN_WIDTH / GRID_COLS
CELL_H = PLAN_HEIGHT / GRID_ROWS

AUDIENCE_HEIGHT = 20
WING_WIDTH = 36
STAGE_X_OFFSET = WING_WIDTH  # main 3x3 grid sits to the right of the left wing
TOTAL_WIDTH = WING_WIDTH + PLAN_WIDTH + WING_WIDTH

CAPTION_ROW_HEIGHT = 14


def _zone_center(zone: str, sub_x: float | None = None, sub_y: float | None = None) -> tuple[float, float]:
    if zone == "wing_left":
        cx = WING_WIDTH / 2
        cy = PLAN_HEIGHT / 2 if sub_y is None else sub_y * PLAN_HEIGHT
        return cx, cy
    if zone == "wing_right":
        cx = STAGE_X_OFFSET + PLAN_WIDTH + WING_WIDTH / 2
        cy = PLAN_HEIGHT / 2 if sub_y is None else sub_y * PLAN_HEIGHT
        return cx, cy
    col, row = ZONE_GRID.get(zone, (1, 1))
    cx = STAGE_X_OFFSET + (col + 0.5) * CELL_W
    cy = (row + 0.5) * CELL_H
    if sub_x is not None:
        cx = STAGE_X_OFFSET + col * CELL_W + sub_x * CELL_W
    if sub_y is not None:
        cy = row * CELL_H + sub_y * CELL_H
    return cx, cy


def _render_pin_head(px: float, py: float, sex: str | None, color: str) -> str:
    """Render a dancer pin head per the LabanWriter floor-plan convention:
    female (white/open, the documented default) / male (black/filled) /
    neuter (tack shape). `color` still distinguishes performers from each
    other — a modern addition layered on top of the authentic shape
    encoding, since the manual's monochrome convention doesn't need to
    disambiguate more than one or two dancers by eye the way a multi-
    performer computational score does.
    """
    if sex == "male":
        return f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="{color}"/>'
    if sex == "neuter":
        return (
            f'<polygon points="{px:.1f},{py - 5:.1f} {px - 4:.1f},{py + 3:.1f} {px + 4:.1f},{py + 3:.1f}" '
            f'fill="{color}"/>'
        )
    # Female is the documented default (also used when sex is unset).
    return f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" fill="white" stroke="{color}" stroke-width="1.5"/>'


def render_floor_plan_svg(ir: dict, measure_range: tuple[int, int] | None = None) -> str:
    """Render stage floor plan as independent SVG.

    Reads floor_plan entries from IR extensions, or falls back to
    stage_position data on individual symbols.
    """
    total_h = PLAN_HEIGHT + AUDIENCE_HEIGHT
    elements: list[str] = []

    # Background
    elements.append(f'<rect x="0" y="0" width="{TOTAL_WIDTH}" height="{total_h}" fill="#fefefe"/>')

    # Wing columns, left and right of the main grid
    for wing_x, label in ((0.0, "WING"), (STAGE_X_OFFSET + PLAN_WIDTH, "WING")):
        elements.append(
            f'<rect x="{wing_x:.1f}" y="0" width="{WING_WIDTH:.1f}" height="{PLAN_HEIGHT:.1f}" '
            f'fill="#f9fafb" stroke="#d1d5db" stroke-width="0.5" stroke-dasharray="3,2"/>'
        )
        elements.append(
            f'<text x="{wing_x + WING_WIDTH / 2:.1f}" y="{PLAN_HEIGHT / 2:.1f}" text-anchor="middle" '
            f'font-size="7" fill="#d1d5db" font-family="sans-serif" '
            f'transform="rotate(-90 {wing_x + WING_WIDTH / 2:.1f} {PLAN_HEIGHT / 2:.1f})">{label}</text>'
        )

    # Grid lines and zone labels
    for zone, (col, row) in ZONE_GRID.items():
        x = STAGE_X_OFFSET + col * CELL_W
        y = row * CELL_H
        elements.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL_W:.1f}" height="{CELL_H:.1f}" '
            f'fill="none" stroke="#d1d5db" stroke-width="0.5"/>'
        )
        label = ZONE_LABELS.get(zone, "")
        lx = x + CELL_W / 2
        ly = y + CELL_H / 2
        elements.append(
            f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" '
            f'font-size="8" fill="#d1d5db" font-family="sans-serif">{label}</text>'
        )

    # Center mark, per the LabanWriter manual's "Show center mark" option
    center_x, center_y = STAGE_X_OFFSET + PLAN_WIDTH / 2, PLAN_HEIGHT / 2
    mark = 5
    elements.append(
        f'<line x1="{center_x - mark:.1f}" y1="{center_y:.1f}" x2="{center_x + mark:.1f}" y2="{center_y:.1f}" '
        f'stroke="#9ca3af" stroke-width="0.8"/>'
        f'<line x1="{center_x:.1f}" y1="{center_y - mark:.1f}" x2="{center_x:.1f}" y2="{center_y + mark:.1f}" '
        f'stroke="#9ca3af" stroke-width="0.8"/>'
    )

    # Audience label at bottom (spans the main grid only, not the wings)
    elements.append(
        f'<rect x="{STAGE_X_OFFSET:.1f}" y="{PLAN_HEIGHT:.1f}" width="{PLAN_WIDTH}" height="{AUDIENCE_HEIGHT}" '
        f'fill="#f3f4f6" stroke="#d1d5db" stroke-width="0.5"/>'
    )
    elements.append(
        f'<text x="{STAGE_X_OFFSET + PLAN_WIDTH / 2:.1f}" y="{PLAN_HEIGHT + AUDIENCE_HEIGHT / 2 + 4:.1f}" '
        f'text-anchor="middle" font-size="9" fill="#6b7280" font-family="sans-serif">AUDIENCE</text>'
    )

    # Collect floor plan entries
    floor_plan_entries = ir.get("extensions", {}).get("floor_plan", [])
    if not floor_plan_entries:
        # Fallback: extract from symbols with stage_position
        symbols = ir.get("symbols", [])
        for sym in symbols:
            sp = sym.get("stage_position")
            if not isinstance(sp, dict) or not sp.get("zone"):
                continue
            timing = sym.get("timing", {})
            m = int(timing.get("measure", 1))
            if measure_range and not (measure_range[0] <= m <= measure_range[1]):
                continue
            floor_plan_entries.append({
                "performer_id": sym.get("body_part", "dancer"),
                "measure": m,
                "beat": float(timing.get("beat", 1.0)),
                "position": sp,
                "facing": sym.get("facing"),
                "path_to_next": None,
            })

    if measure_range:
        floor_plan_entries = [
            e for e in floor_plan_entries
            if measure_range[0] <= int(e.get("measure", 1)) <= measure_range[1]
        ]

    # Group by performer
    by_performer: dict[str, list[dict]] = {}
    for entry in floor_plan_entries:
        pid = entry.get("performer_id", "dancer")
        by_performer.setdefault(pid, []).append(entry)

    colors = ["#111827", "#2563eb", "#dc2626", "#059669", "#7c3aed"]

    for pidx, (performer_id, entries) in enumerate(by_performer.items()):
        color = colors[pidx % len(colors)]
        entries.sort(key=lambda e: (int(e.get("measure", 1)), float(e.get("beat", 1.0))))

        positions: list[tuple[float, float]] = []
        for entry in entries:
            pos = entry.get("position", {})
            zone = pos.get("zone", "center")
            px, py = _zone_center(zone, pos.get("x"), pos.get("y"))
            positions.append((px, py))

        # Draw paths between positions
        for i in range(len(positions) - 1):
            x1, y1 = positions[i]
            x2, y2 = positions[i + 1]
            path_type = entries[i].get("path_to_next", "straight")
            if path_type == "curved":
                mx = (x1 + x2) / 2 + 20
                my = (y1 + y2) / 2 - 20
                elements.append(
                    f'<path d="M {x1:.1f} {y1:.1f} Q {mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" '
                    f'fill="none" stroke="{color}" stroke-width="1" stroke-dasharray="4,3"/>'
                )
            else:
                elements.append(
                    f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                    f'stroke="{color}" stroke-width="1" stroke-dasharray="4,3"/>'
                )

        # Draw dancer positions
        for i, (px, py) in enumerate(positions):
            elements.append(_render_pin_head(px, py, entries[i].get("sex"), color))

            # Facing arrow
            facing = entries[i].get("facing")
            if facing and facing in FACING_ANGLES:
                angle = FACING_ANGLES[facing]
                ax = px + 10 * math.cos(angle)
                ay = py - 10 * math.sin(angle)
                elements.append(
                    f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" '
                    f'stroke="{color}" stroke-width="1.5"/>'
                )
                # Arrowhead
                arr_angle1 = angle + math.pi * 0.8
                arr_angle2 = angle - math.pi * 0.8
                ax1 = ax + 4 * math.cos(arr_angle1)
                ay1 = ay - 4 * math.sin(arr_angle1)
                ax2 = ax + 4 * math.cos(arr_angle2)
                ay2 = ay - 4 * math.sin(arr_angle2)
                elements.append(
                    f'<polygon points="{ax:.1f},{ay:.1f} {ax1:.1f},{ay1:.1f} {ax2:.1f},{ay2:.1f}" '
                    f'fill="{color}"/>'
                )

            # Caption, per the LabanWriter manual's "Caption Squares"
            caption = entries[i].get("caption")
            if caption:
                elements.append(
                    f'<text x="{px:.1f}" y="{py + 13:.1f}" text-anchor="middle" '
                    f'font-size="6.5" fill="{color}" font-family="sans-serif">{escape(str(caption))}</text>'
                )

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{TOTAL_WIDTH}" height="{total_h}" '
        f'viewBox="0 0 {TOTAL_WIDTH} {total_h}">',
        *elements,
        "</svg>",
    ])
