from __future__ import annotations

from xml.sax.saxutils import escape


BODY_X = {
    "left_arm": 90,
    "right_arm": 210,
    "left_leg": 120,
    "right_leg": 180,
    "torso": 150,
}

DIRECTION_GLYPH = {
    "forward": "▲",
    "backward": "▼",
    "left": "◀",
    "right": "▶",
    "diagonal_forward_left": "◢",
    "diagonal_forward_right": "◣",
}

LEVEL_Y_OFFSET = {"high": -25, "middle": 0, "low": 25}


def render_svg(ir: dict) -> str:
    width = 340
    height = 1200
    elements = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>']
    elements.append('<line x1="150" y1="20" x2="150" y2="1180" stroke="black" stroke-width="2"/>')

    for sym in ir.get("symbols", []):
        t = sym.get("timing", {})
        beat = float(t.get("beat", 1.0))
        y = 60 + beat * 60 + LEVEL_Y_OFFSET.get(sym.get("level", "middle"), 0)
        x = BODY_X.get(sym.get("body_part", "torso"), 150)
        direction = sym.get("direction", "forward")
        glyph = DIRECTION_GLYPH.get(direction, "◆")
        sid = escape(sym.get("symbol_id", "unknown"))
        elements.append(f'<text x="{x}" y="{y}" text-anchor="middle" font-size="22">{glyph}</text>')
        elements.append(f'<text x="{x}" y="{y+14}" text-anchor="middle" font-size="8" fill="#555">{sid}</text>')

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        *elements,
        "</svg>",
    ])
