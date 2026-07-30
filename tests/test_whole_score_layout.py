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
from dancenotation_mcp.validation.validator import validate_ir

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


def _symbol_spans_y(svg):
    """(y_min, y_max, symbol_id) of the ink in each drawn symbol.

    Reads only geometry attributes and path data, never colours or ids — a
    naive sweep of every number in the group picks up the digits inside
    ``#111827`` and ``stroke-width="1"`` and drowns the coordinates.
    """
    num = r"-?\d*\.?\d+"
    spans = []
    for g in re.finditer(
            r'<g class="laban-symbol"[^>]*data-symbol-id="([^"]+)"[^>]*>'
            r'(.*?)</g>', svg, re.S):
        symbol_id, body = g.group(1), g.group(2)
        ys = [float(v) for v in
              re.findall(r'\b(?:y|cy|y1|y2)="(' + num + r')"', body)]
        for d in re.findall(r'\bd="([^"]*)"', body):
            ys += [float(n) for n in re.findall(num, d)][1::2]
        for use in re.finditer(
                r'<use [^>]*y="(' + num + r')"[^>]*height="(' + num + r')"',
                body):
            ys += [float(use.group(1)),
                   float(use.group(1)) + float(use.group(2))]
        if ys:
            spans.append((min(ys), max(ys), symbol_id))
    return spans


class SymbolFitsThePageTests(unittest.TestCase):
    """A symbol long enough to outrun its system was drawn off the page.

    Per-symbol tests cannot see this: the symbol is the right shape and the
    right length, and only the last measure of a system puts it anywhere it
    does not fit. The whole-score guard next door checked width and system
    crossing but never vertical bounds, so this was green across 678 tests.
    """

    def _score_with_a_long_symbol_at_the_top_of_a_system(self, duration):
        """Fill a system, then put a long symbol on its final beat.

        Time runs bottom to top, so the last measure of a system is at the
        top of the page and a symbol there grows towards the margin.
        """
        symbols = [{
            "symbol_id": "support.step", "body_part": "left_leg",
            "direction": "forward", "level": "middle",
            "timing": {"measure": m, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        } for m in range(1, 9)]
        symbols.append({
            "symbol_id": "support.step", "body_part": "right_leg",
            "direction": "forward", "level": "middle",
            "timing": {"measure": 8, "beat": 4, "duration_beats": duration},
            "modifiers": {},
        })
        return {"metadata": {"title": "overflow probe", "ir_version": "0.1.0",
                             "schema_version": "0.1.0"},
                "symbols": symbols}

    def test_no_symbol_is_drawn_outside_the_canvas(self):
        """Measured: a four-beat step on the last beat of a system drew
        y -69 .. 169 against a canvas starting at 0."""
        for duration in (1, 2, 4):
            with self.subTest(duration_beats=duration):
                ir = self._score_with_a_long_symbol_at_the_top_of_a_system(
                    duration)
                layout = compute_laban_layout(ir)
                height = layout["height"]
                for y_min, y_max, symbol_id in _symbol_spans_y(
                        render_laban_svg(ir)):
                    self.assertGreaterEqual(
                        y_min, 0,
                        f"{symbol_id} starts at y={y_min:.0f}, above the top "
                        f"of the canvas")
                    self.assertLessEqual(
                        y_max, height,
                        f"{symbol_id} ends at y={y_max:.0f}, below the "
                        f"canvas bottom of {height}")


class NothingCrossesTheCentreLineTests(unittest.TestCase):
    """The centre line carries beat ticks and bar lines. Not symbols.

    torso, pelvis, upper_spine, lower_spine and whole_body mapped to a
    "center" column spanning both support columns, and head to a "head"
    column that is not in the staff at all; all five came out straddling the
    centre line, drawn over whatever the legs were doing. Measured on measure
    1 of the example score: left_leg 154..180, right_leg 180..206, torso
    171..189, all three at y 212..518.

    Knust vol 1 p170: "trunk, chest, and shoulder section are, as a rule,
    written in one of the upper body columns as long as these columns are
    free, otherwise they are written in any empty gesture column." A column
    beside the supports, never across them. Confirmed on Soirée musicale p58,
    where a magnified band across a bar line shows the centre line carrying
    beat ticks and nothing else.

    Neither existing guard sees this. The glyph probe fixes one body part for
    every symbol, so no two ever share a slot; COLUMN_CONFLICT buckets by
    column name, and "center" is a different bucket from "left_support", so
    two symbols on the same pixels were never compared.
    """

    BODY_PARTS = ("torso", "pelvis", "upper_spine", "lower_spine",
                  "whole_body", "head")

    def _layout(self, body_part):
        return compute_laban_layout({
            "schema_version": "1.0",
            "metadata": {"title": "centre line probe"},
            "symbols": [
                {"symbol_id": "support.step", "body_part": "left_leg",
                 "direction": "place", "level": "low",
                 "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                 "modifiers": {}},
                {"symbol_id": "support.step", "body_part": "right_leg",
                 "direction": "place", "level": "low",
                 "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                 "modifiers": {}},
                {"symbol_id": "direction.forward", "body_part": body_part,
                 "direction": "forward", "level": "middle",
                 "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                 "modifiers": {}},
            ],
        })

    def test_no_body_symbol_straddles_the_centre_line(self):
        for body_part in self.BODY_PARTS:
            with self.subTest(body_part=body_part):
                layout = self._layout(body_part)
                centre = layout["systems"][0]["staff_center_x"]
                entry = next(e for e in layout["placed_symbols"]
                             if e["symbol"]["body_part"] == body_part)
                self.assertFalse(
                    entry["x_left"] < centre < entry["x_right"],
                    f"a {body_part} symbol spans {entry['x_left']}.."
                    f"{entry['x_right']}, across the centre line at {centre}")

    def test_no_body_symbol_overlaps_a_support(self):
        """The consequence that showed in the render."""
        for body_part in self.BODY_PARTS:
            with self.subTest(body_part=body_part):
                placed = self._layout(body_part)["placed_symbols"]
                body = next(e for e in placed
                            if e["symbol"]["body_part"] == body_part)
                for support in (e for e in placed
                                if e["symbol"]["body_part"].endswith("_leg")):
                    overlap = (min(body["x_right"], support["x_right"])
                               - max(body["x_left"], support["x_left"]))
                    self.assertLessEqual(
                        overlap, 0,
                        f"{body_part} overlaps {support['symbol']['body_part']}"
                        f" by {overlap} units at the same beat")


class LegGestureColumnTests(unittest.TestCase):
    """A leg that is not carrying weight has its own column.

    Knust vol 1 p31, defining the staff: "On both sides the columns are
    numbered outwards from the middle line. The first columns, immediately
    right and left of the middle line, are for the notation of the movements
    of the body as a whole, i.e. progression of the body as a whole with steps
    and jumps, and turns of the body as a whole. The second columns are called
    the leg gesture columns. In these columns are written the movements of the
    legs when they are not carrying the body weight."

    BODY_TO_COLUMN sent every leg part to a support column whatever the
    symbol, so a gesture and a support on the same leg shared one column and
    could be drawn on top of each other.
    """

    def _columns(self, symbols):
        layout = compute_laban_layout({
            "schema_version": "1.0",
            "metadata": {"title": "leg gesture probe"},
            "symbols": symbols,
        })
        return {e["symbol"]["symbol_id"]: e["column"]
                for e in layout["placed_symbols"]}

    @staticmethod
    def _sym(symbol_id, body_part, beat=1):
        return {"symbol_id": symbol_id, "body_part": body_part,
                "direction": "forward", "level": "middle",
                "timing": {"measure": 1, "beat": beat, "duration_beats": 1},
                "modifiers": {}}

    def test_a_weight_bearing_leg_stays_in_the_support_column(self):
        columns = self._columns([self._sym("support.step", "left_leg")])
        self.assertEqual(columns["support.step"], "left_support")

    def test_a_leg_gesture_goes_to_the_leg_gesture_column(self):
        columns = self._columns([self._sym("gesture.leg", "right_leg")])
        self.assertEqual(columns["gesture.leg"], "right_leg_gesture")

    def test_a_support_and_a_gesture_on_one_leg_do_not_share_a_column(self):
        """The collision this removes: measure 25 of the example score had two
        symbols stacked in right_support because both went there."""
        columns = self._columns([
            self._sym("support.step", "left_leg"),
            self._sym("gesture.leg", "left_leg"),
        ])
        self.assertNotEqual(columns["support.step"], columns["gesture.leg"])

    def test_the_drawn_staff_encloses_support_and_leg_gesture(self):
        """Knust p31: Laban's staff is a five-line staff with only the first,
        third and fifth lines drawn, the second and fourth imaginary. The
        drawn lines therefore sit outside the second column, enclosing
        support and leg gesture on each side — four columns, which is what
        Hutchinson Guest fig. 162a rules its staff box into."""
        layout = compute_laban_layout({
            "schema_version": "1.0", "metadata": {"title": "staff probe"},
            "symbols": [self._sym("support.step", "left_leg")],
        })
        system = layout["systems"][0]
        columns = system["col_positions"]
        left, right = layout["staff_left"], layout["staff_right"]
        # staff_left/right span every column; the drawn box is narrower.
        inside = ("left_leg_gesture", "left_support",
                  "right_support", "right_leg_gesture")
        outside = ("left_body", "right_body", "left_arm", "right_arm")
        box_left = min(columns[c][0] for c in inside)
        box_right = max(columns[c][1] for c in inside)
        for column in outside:
            with self.subTest(column=column):
                start, end = columns[column]
                self.assertTrue(
                    end <= box_left or start >= box_right,
                    f"{column} at {start}..{end} is inside the drawn staff "
                    f"box {box_left}..{box_right}")


class WhatTheLayoutStacksTheValidatorReportsTest(unittest.TestCase):
    """If two symbols are drawn on the same pixels, something must say so.

    The two halves are maintained separately and keep drifting: the layout
    decides a column from PRIMARY_FAMILIES and BODY_TO_COLUMN, the validator
    from PRIMARY_MOTION_COLUMNS, and a family added to one is not added to the
    other. Moving retention onto the staff updated the layout's set and not
    the validator's, so eight retention signs drawn over the movements they
    retain went unreported.

    Rather than assert the membership of two sets — which is the thing that
    drifts — this compares the outcome: every pair the layout overlaps in both
    x and y must produce a diagnostic.
    """

    def _overlapping_pairs(self, layout):
        placed = layout["placed_symbols"]
        pairs = []
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                if a["system_index"] != b["system_index"]:
                    continue
                dx = (min(a["x_right"], b["x_right"])
                      - max(a["x_left"], b["x_left"]))
                dy = (min(a["y_bottom"], b["y_bottom"])
                      - max(a["y_top"], b["y_top"]))
                if dx > 0.5 and dy > 0.5:
                    pairs.append((a, b))
        return pairs

    def test_every_stacked_pair_is_reported(self):
        path = ROOT / "examples" / "collapse_of_symmetry_full.ir.json"
        if not path.exists():
            self.skipTest("example score not built")
        ir = json.loads(path.read_text(encoding="utf-8"))

        stacked = self._overlapping_pairs(compute_laban_layout(ir))
        reported = {int(i["path"].split("/")[2])
                    for i in validate_ir(ir)["issues"]
                    if i["code"] in ("COLUMN_CONFLICT", "TIMING_OVERLAP")
                    and i.get("path", "").startswith("/symbols/")}

        symbols = ir["symbols"]
        unreported = []
        for a, b in stacked:
            indices = {symbols.index(a["symbol"]), symbols.index(b["symbol"])}
            if not (indices & reported):
                unreported.append(
                    f"{a['symbol']['symbol_id']} over "
                    f"{b['symbol']['symbol_id']} in {a['column']}")
        self.assertEqual(
            unreported, [],
            f"{len(unreported)} of {len(stacked)} stacked pairs are drawn on "
            f"top of each other with no diagnostic: " + "; ".join(unreported[:4]))


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

    def test_the_golden_example_score_validates(self):
        """Rendering it was never proof that it is a legal score.

        The builder emitted timing.tempo, which is not in the catalog. The
        renderer drew it anyway -- an unknown id falls through to a generic
        annotation -- so this file could be regenerated into an invalid score
        and every test stayed green. The validator does catch the id; nothing
        was asking it.
        """
        path = ROOT / "examples" / "collapse_of_symmetry_full.ir.json"
        if not path.exists():
            self.skipTest("example score not built")
        report = validate_ir(json.loads(path.read_text(encoding="utf-8")))
        errors = [i for i in report.get("issues", [])
                  if i.get("severity") == "error"]
        self.assertEqual(
            errors, [],
            "the example score does not validate: "
            + "; ".join(i.get("message", "") for i in errors))


if __name__ == "__main__":
    unittest.main()
