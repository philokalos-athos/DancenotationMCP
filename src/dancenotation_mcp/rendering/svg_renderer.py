from __future__ import annotations

from xml.sax.saxutils import escape

from dancenotation_mcp.ir.catalog import load_symbol_catalog


BODY_X = {
    "left_arm": 90,
    "right_arm": 210,
    "left_leg": 120,
    "right_leg": 180,
    "torso": 150,
    "head": 150,
}

CATEGORY_X = {
    "support": 150,
    "direction": 245,
    "quality": 265,
    "level": 285,
    "timing": 305,
}

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

LEVEL_Y_OFFSET = {"high": -25, "middle": 0, "low": 25}


def render_svg(ir: dict) -> str:
    catalog = load_symbol_catalog()
    width = 360
    height = 1200
    elements = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>']
    elements.append('<line x1="150" y1="20" x2="150" y2="1180" stroke="black" stroke-width="2"/>')

    for sym in ir.get("symbols", []):
        t = sym.get("timing", {})
        beat = float(t.get("beat", 1.0))
        y = 60 + beat * 60 + LEVEL_Y_OFFSET.get(sym.get("level", "middle"), 0)
        sid = sym.get("symbol_id", "unknown")
        catalog_entry = catalog.get(sid, {})
        category = catalog_entry.get("category", "")
        geom = catalog_entry.get("geometry", {})

        x = BODY_X.get(sym.get("body_part", "torso"), 150)
        if geom.get("staff_column") in CATEGORY_X:
            x = CATEGORY_X[geom["staff_column"]]

        direction = sym.get("direction", "forward")
        glyph = geom.get("glyph") or DIRECTION_GLYPH.get(direction, "◆")
        text_size = max(12, int(geom.get("height", 18)))
        sid_txt = escape(sid)
        elements.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-size="{text_size}">{escape(glyph)}</text>')
        elements.append(f'<text x="{x}" y="{y+14}" text-anchor="middle" font-size="8" fill="#555">{sid_txt}</text>')
        if category:
            elements.append(f'<text x="{x+20}" y="{y-4}" text-anchor="start" font-size="7" fill="#888">{escape(category)}</text>')

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        *elements,
        "</svg>",
    ])
