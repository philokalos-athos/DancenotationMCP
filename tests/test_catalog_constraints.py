import unittest

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.validation.validator import validate_ir


class CatalogConstraintTests(unittest.TestCase):
    def test_catalog_is_large(self):
        catalog = load_symbol_catalog()
        self.assertGreaterEqual(len(catalog), 850)

    def test_every_symbol_has_geometry_and_constraints(self):
        catalog = load_symbol_catalog()
        for sid, spec in catalog.items():
            self.assertIn("allowed_body_parts", spec, sid)
            self.assertIn("allowed_directions", spec, sid)
            self.assertIn("allowed_levels", spec, sid)
            self.assertIn("geometry", spec, sid)
            self.assertIn("glyph", spec["geometry"], sid)

    def test_semantic_constraints_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                }
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("SYMBOL_BODY_PART", codes)

    def test_modifier_constraints_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "path.curved",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"line_style": "triple", "surface_marks": ["up"]},
                }
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_LINE_STYLE_INVALID", codes)
        self.assertIn("MODIFIER_SURFACE_MARK_INVALID", codes)

    def test_numeric_modifier_constraints_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.generic",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"stretch": "wide", "repeat_count": 0},
                }
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_NUMERIC_INVALID", codes)
        self.assertIn("MODIFIER_REPEAT_COUNT_INVALID", codes)

    def test_discrete_modifier_constraints_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "separator.staff",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"pin_head": "triangle", "separator_mode": "triple"},
                }
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_PIN_HEAD_INVALID", codes)
        self.assertIn("MODIFIER_SEPARATOR_MODE_INVALID", codes)

    def test_attachment_modifier_constraints_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.generic",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": 42, "measure_header": "yes", "attach_side": "center", "repeat_span_to": 9},
                }
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TO_INVALID", codes)
        self.assertIn("MODIFIER_MEASURE_HEADER_INVALID", codes)
        self.assertIn("MODIFIER_ATTACH_SIDE_INVALID", codes)
        self.assertIn("MODIFIER_REPEAT_SPAN_TO_INVALID", codes)


if __name__ == "__main__":
    unittest.main()
