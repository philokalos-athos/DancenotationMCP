import unittest

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.validation.validator import validate_ir


class CatalogConstraintTests(unittest.TestCase):
    def test_catalog_is_large(self):
        catalog = load_symbol_catalog()
        self.assertGreaterEqual(len(catalog), 800)

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


if __name__ == "__main__":
    unittest.main()
