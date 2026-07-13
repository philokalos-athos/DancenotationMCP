import json
import unittest
from pathlib import Path

from dancenotation_mcp.rendering.floor_plan_renderer import render_floor_plan_svg

ROOT = Path(__file__).resolve().parents[1]


class MultiDancerFloorPlanTests(unittest.TestCase):
    """Stress-tests multiple simultaneous performers, inspired by the group
    formations (e.g. the "First Pas de Cinq" facing-page diagrams) in the
    La Vivandiere reference score — the single-dancer tests elsewhere don't
    exercise per-performer color assignment or converging paths.
    """

    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "floor_plan_multi_dancer.json").read_text(encoding="utf-8")
        )
        cls.golden_svg = (ROOT / "fixtures" / "floor_plan_multi_dancer.svg").read_text(encoding="utf-8")
        cls.rendered = render_floor_plan_svg(cls.fixture)

    def test_golden_svg_matches(self):
        self.assertEqual(self.rendered, self.golden_svg)

    def test_all_three_performers_present(self):
        for performer in ("G1", "G2", "G3"):
            self.assertIn(performer, json.dumps(self.fixture))

    def test_three_distinct_performer_colors_used(self):
        # colors palette in floor_plan_renderer.py; first three should all appear
        for color in ("#111827", "#2563eb", "#dc2626"):
            self.assertIn(f'fill="{color}"', self.rendered)

    def test_curved_and_straight_paths_both_rendered(self):
        self.assertIn("stroke-dasharray=\"4,3\"", self.rendered)
        self.assertIn("<path d=\"M", self.rendered)  # curved path
        self.assertIn("<line x1=", self.rendered)     # straight path

    def test_facing_arrows_rendered_for_each_position(self):
        # 6 positions total, each with a facing -> 6 arrowhead polygons
        self.assertEqual(self.rendered.count("<polygon"), 6)


class PinSexShapeTests(unittest.TestCase):
    """Per the LabanWriter manual: "female pin (white) is the default.
    Select male pin (black) if most of the dancers are men or neuter pin
    (tack) if the dancers can be either." Color still distinguishes
    performers on top of the shape encoding.
    """

    def _render_single_pin(self, sex):
        ir = {
            "metadata": {"title": "pin sex test"},
            "symbols": [],
            "extensions": {
                "floor_plan": [
                    {
                        "performer_id": "dancer_1",
                        "measure": 1,
                        "beat": 1,
                        "position": {"zone": "center"},
                        "facing": None,
                        "path_to_next": None,
                        "sex": sex,
                    }
                ]
            },
        }
        return render_floor_plan_svg(ir)

    def test_unset_sex_defaults_to_female_hollow_pin(self):
        svg = self._render_single_pin(None)
        self.assertIn('fill="white" stroke="#111827" stroke-width="1.5"', svg)

    def test_female_sex_renders_hollow_pin(self):
        svg = self._render_single_pin("female")
        self.assertIn('fill="white" stroke="#111827" stroke-width="1.5"', svg)

    def test_male_sex_renders_filled_circle(self):
        svg = self._render_single_pin("male")
        self.assertIn('<circle cx="186.0" cy="100.0" r="5" fill="#111827"/>', svg)

    def test_neuter_sex_renders_tack_polygon(self):
        svg = self._render_single_pin("neuter")
        self.assertIn('<polygon points="186.0,95.0 182.0,103.0 190.0,103.0" fill="#111827"/>', svg)


class WingColumnAndCaptionTests(unittest.TestCase):
    """Per the LabanWriter manual: "Wing columns can also be added to the
    floorplan to allow you to place pins outside the floorplan(s)" and
    "Squares at the bottom of the floor plan can be added for typing in
    captions."
    """

    def test_wing_columns_rendered_on_both_sides(self):
        ir = {"metadata": {"title": "wing test"}, "symbols": [], "extensions": {"floor_plan": []}}
        svg = render_floor_plan_svg(ir)
        self.assertEqual(svg.count(">WING<"), 2)

    def test_performer_can_be_placed_in_left_wing(self):
        ir = {
            "metadata": {"title": "wing placement test"},
            "symbols": [],
            "extensions": {
                "floor_plan": [
                    {
                        "performer_id": "waiting_dancer",
                        "measure": 1,
                        "beat": 1,
                        "position": {"zone": "wing_left"},
                        "facing": None,
                        "path_to_next": None,
                    }
                ]
            },
        }
        svg = render_floor_plan_svg(ir)
        # wing_left center is at x = WING_WIDTH / 2 = 18.0, well inside the
        # left wing strip (0-36), left of the main grid (which starts at 36).
        self.assertIn('cx="18.0"', svg)

    def test_performer_can_be_placed_in_right_wing(self):
        ir = {
            "metadata": {"title": "wing placement test"},
            "symbols": [],
            "extensions": {
                "floor_plan": [
                    {
                        "performer_id": "waiting_dancer",
                        "measure": 1,
                        "beat": 1,
                        "position": {"zone": "wing_right"},
                        "facing": None,
                        "path_to_next": None,
                    }
                ]
            },
        }
        svg = render_floor_plan_svg(ir)
        # wing_right center is at STAGE_X_OFFSET + PLAN_WIDTH + WING_WIDTH/2
        # = 36 + 300 + 18 = 354.0, inside the right wing strip.
        self.assertIn('cx="354.0"', svg)

    def test_caption_text_rendered_for_position(self):
        ir = {
            "metadata": {"title": "caption test"},
            "symbols": [],
            "extensions": {
                "floor_plan": [
                    {
                        "performer_id": "dancer_1",
                        "measure": 1,
                        "beat": 1,
                        "position": {"zone": "center"},
                        "facing": None,
                        "path_to_next": None,
                        "caption": "58-59",
                    }
                ]
            },
        }
        svg = render_floor_plan_svg(ir)
        self.assertIn(">58-59<", svg)

    def test_no_caption_element_when_caption_unset(self):
        ir = {
            "metadata": {"title": "no caption test"},
            "symbols": [],
            "extensions": {
                "floor_plan": [
                    {
                        "performer_id": "dancer_1",
                        "measure": 1,
                        "beat": 1,
                        "position": {"zone": "center"},
                        "facing": None,
                        "path_to_next": None,
                    }
                ]
            },
        }
        svg = render_floor_plan_svg(ir)
        # Only the zone-label texts (DSL, DSC, ...) and AUDIENCE should appear
        self.assertNotIn("font-size=\"6.5\"", svg)


if __name__ == "__main__":
    unittest.main()
