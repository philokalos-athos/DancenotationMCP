import json
from pathlib import Path
import unittest

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.validation.validator import validate_ir
from dancenotation_mcp.rendering.svg_renderer import render_svg


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_phrase_to_ir_roundtrip(self):
        plan = parse_phrase("step forward, turn right")
        self.assertGreaterEqual(len(plan["steps"]), 2)
        ir = phrase_plan_to_ir(plan, "step forward, turn right")
        res = validate_ir(ir)
        self.assertTrue(res["ok"])

    def test_invalid_fixture_detected(self):
        data = json.loads((ROOT / "fixtures" / "invalid_overlap_timing.json").read_text())
        res = validate_ir(data)
        codes = {issue["code"] for issue in res["issues"]}
        self.assertIn("UNKNOWN_SYMBOL", codes)
        self.assertIn("TIMING_DURATION", codes)

    def test_renderer_outputs_svg(self):
        valid = json.loads((ROOT / "fixtures" / "valid_minimal_score.json").read_text())
        svg = render_svg(valid)
        self.assertIn("<svg", svg)
        self.assertIn("support.step", svg)


if __name__ == "__main__":
    unittest.main()
