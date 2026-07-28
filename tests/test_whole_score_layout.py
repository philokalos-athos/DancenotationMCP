"""Whole-score invariants that per-symbol tests structurally cannot see.

Twice a defect has been invisible to every per-symbol test and obvious on the
first full render, both times with 650+ tests green:

- systems stacked into one column, giving a 1 : 20.6 canvas that is not a page
- diagonals built by rotation, which at four beats came out 177 units wide in a
  26-unit column and crossed the whole staff

Neither could be caught by rendering one short symbol in isolation, which is
what every other test does. These assertions render a real multi-measure score
and check the things that only appear at that scale.
"""
import json
import re
import unittest
from pathlib import Path

from dancenotation_mcp.rendering.laban_layout import (
    COLUMN_WIDTHS,
    PAGE_ASPECT,
    compute_laban_layout,
)
from dancenotation_mcp.rendering.laban_renderer import render_laban_svg

ROOT = Path(__file__).resolve().parents[1]

# Widest column in the staff; no symbol's ink may exceed it.
_WIDEST_COLUMN = max(COLUMN_WIDTHS.values())


def _score_ir(measures=24):
    """A score long enough to wrap into several systems, with every direction
    and a range of durations — the conditions both regressions needed."""
    directions = ["forward", "backward", "left", "right", "place",
                  "diagonal_forward_left", "diagonal_forward_right",
                  "diagonal_backward_left", "diagonal_backward_right"]
    levels = ["high", "middle", "low"]
    symbols = []
    for m in range(1, measures + 1):
        for i, (part, beat, duration) in enumerate((
            ("left_leg", 1, 2), ("right_leg", 3, 2), ("left_arm", 1, 4),
        )):
            symbols.append({
                "symbol_id": "support.step" if "leg" in part else "gesture.arm",
                "body_part": part,
                "direction": directions[(m + i) % len(directions)],
                "level": levels[(m + i) % len(levels)],
                "timing": {"measure": m, "beat": beat,
                           "duration_beats": duration},
                "modifiers": {"label": f"m{m} {part}"} if i == 0 else {},
            })
    return {
        "metadata": {"title": "Layout probe", "ir_version": "0.1.0",
                     "schema_version": "0.1.0"},
        "symbols": symbols,
    }


def _symbol_boxes(svg):
    """(x_min, x_max) of the ink in each drawn direction symbol."""
    boxes = []
    for g in re.finditer(r'<g class="laban-symbol"[^>]*>(.*?)</g>', svg, re.S):
        xs = []
        for path in re.findall(r'<path d="([^"]+)"', g.group(1)):
            nums = [float(n) for n in re.findall(r'-?\d+\.?\d*', path)]
            xs += nums[0::2]
        for use in re.finditer(r'<use [^>]*x="([\d.]+)"[^>]*width="([\d.]+)"',
                               g.group(1)):
            xs += [float(use.group(1)),
                   float(use.group(1)) + float(use.group(2))]
        if xs:
            boxes.append((min(xs), max(xs)))
    return boxes


class WholeScoreLayoutTests(unittest.TestCase):
    """Rendered once for the class — it draws a full multi-system score."""

    @classmethod
    def setUpClass(cls):
        cls.ir = _score_ir()
        cls.svg = render_laban_svg(cls.ir)
        cls.layout = compute_laban_layout(cls.ir)

    def test_no_symbol_is_wider_than_a_staff_column(self):
        """Caught the rotated diagonals: they grew sideways with their height,
        so a long one spilled across neighbouring columns."""
        boxes = _symbol_boxes(self.svg)
        self.assertTrue(boxes, "no symbols rendered")
        for x_min, x_max in boxes:
            self.assertLessEqual(
                x_max - x_min, _WIDEST_COLUMN + 1,
                f"a symbol is {x_max - x_min:.0f} units wide; the widest "
                f"column is {_WIDEST_COLUMN}")

    def test_no_symbol_crosses_into_another_system(self):
        systems = sorted(s["staff_left"] for s in self.layout["systems"])
        if len(systems) < 2:
            self.skipTest("score did not wrap into multiple systems")
        # A symbol may sit in any column of its own system, but must not reach
        # the next system's staff.
        for x_min, x_max in _symbol_boxes(self.svg):
            for staff_left in systems:
                self.assertFalse(
                    x_min < staff_left < x_max,
                    f"a symbol spans {x_min:.0f}-{x_max:.0f}, crossing the "
                    f"staff at {staff_left:.0f}")

    def test_a_long_score_wraps_rather_than_running_off(self):
        """Caught the stacked systems: a 33-measure score came out 1 : 20.6,
        which is not a page. The plates are 1 : 1.37."""
        self.assertGreater(len(self.layout["systems"]), 1,
                           "score long enough to wrap did not wrap")
        aspect = self.layout["height"] / self.layout["width"]
        self.assertLess(
            aspect, PAGE_ASPECT * 3,
            f"canvas is {self.layout['width']}x{self.layout['height']}, "
            f"aspect 1:{aspect:.1f} against the plates' 1:{PAGE_ASPECT}")

    def test_no_caption_is_written_across_a_staff(self):
        centres = sorted({
            round(float(m.group(1)), 1)
            for m in re.finditer(
                r'<line x1="([\d.]+)" y1="[\d.]+" x2="\1" y2="[\d.]+"'
                r'[^>]*stroke-width="2\.5"', self.svg)
        })
        self.assertTrue(centres, "no staff centre lines found")
        half = COLUMN_WIDTHS["left_support"]
        for m in re.finditer(r'<text([^>]*class="laban-caption"[^>]*)>',
                             self.svg):
            x = float(re.search(r'\sx="(-?[\d.]+)"', m.group(1)).group(1))
            for centre in centres:
                self.assertFalse(
                    centre - half <= x <= centre + half,
                    f"a caption sits at x={x:.0f}, across the staff at "
                    f"{centre:.0f}")

    def test_the_golden_example_score_still_renders(self):
        """The largest score the pipeline is exercised against."""
        path = ROOT / "examples" / "collapse_of_symmetry_full.ir.json"
        if not path.exists():
            self.skipTest("example score not built")
        svg = render_laban_svg(json.loads(path.read_text(encoding="utf-8")))
        for x_min, x_max in _symbol_boxes(svg):
            self.assertLessEqual(x_max - x_min, _WIDEST_COLUMN + 1)


if __name__ == "__main__":
    unittest.main()
