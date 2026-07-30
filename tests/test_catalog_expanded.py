import json
import unittest
from collections import Counter
from pathlib import Path

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.models import BODY_PARTS


CATALOG_DIR = Path(__file__).resolve().parents[1] / "resources" / "symbol_catalog"

NEW_FILES = [
    "retention.json",
    "contact.json",
    "flexion_extension.json",
    "effort.json",
    "shape.json",
    "floor_plan.json",
    "foot_detail.json",
    "sequential.json",
]

NEW_TIME_SIGNATURES = [
    "music.time.5_4",
    "music.time.5_8",
    "music.time.6_8",
    "music.time.7_8",
    "music.time.9_8",
    "music.time.12_8",
]

VALID_STAFF_COLUMNS = {
    "adlib", "body", "bow", "digit", "direction", "dynamic",
    "flexion", "floor", "floor_plan", "foothook", "gesture",
    "jump", "level", "motif", "music", "path", "pin", "quality",
    "repeat", "retention", "separator", "space", "support", "surface",
    "timing", "travel", "turn",
}

REQUIRED_FIELDS = {"id", "category", "name", "geometry", "allowed_body_parts"}

EXPECTED_CATEGORIES = {
    "retention.json": "retention",
    "contact.json": "contact",
    "flexion_extension.json": "flexion",
    "effort.json": "effort",
    "shape.json": "shape",
    "floor_plan.json": "floor_plan",
    "foot_detail.json": "foothook",
    "sequential.json": "sequential",
}


class CatalogExpandedTests(unittest.TestCase):
    """Tests for the expanded symbol catalog (new files + new time sigs)."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_symbol_catalog(CATALOG_DIR)

    # ---- 1. Total symbol count ----

    def test_every_official_labanwriter_family_is_represented(self):
        """Coverage is measured by families of real signs, not by raw entry
        count. A count threshold rewards padding the catalog with mechanically
        combined ids that render identically to their base sign — which is how
        216 fictional turn/jump entries accumulated — while a missing family is
        a genuine parity gap. See docs/labanwriter_parity_audit.md.
        """
        families = {sid.split(".")[0] for sid in self.catalog}
        required = {
            "support", "gesture", "body", "direction", "turn", "jump",
            "travel", "path", "floor", "contact", "surface", "flexion",
            "extension", "retention", "effort", "shape", "quality",
            "timing", "music", "repeat", "pin", "bow", "motif", "dynamic",
            "adlib", "sequential", "separator", "space", "level",
            "foot", "foothook", "finger", "toe",
        }
        self.assertEqual(
            required - families, set(),
            "official LabanWriter families missing from the catalog",
        )

    # ---- 2. No duplicate symbol ids ----

    def test_no_duplicate_symbol_ids_across_files(self):
        all_ids = []
        for p in sorted(CATALOG_DIR.glob("*.json")):
            items = json.loads(p.read_text())
            all_ids.extend(item["id"] for item in items)
        id_counts = Counter(all_ids)
        duplicates = {k: v for k, v in id_counts.items() if v > 1}
        self.assertEqual(duplicates, {}, f"Duplicate symbol ids found: {duplicates}")

    # ---- 3. Each new file loads correctly ----

    def test_retention_json_loads(self):
        self._assert_file_loads("retention.json")

    def test_contact_json_loads(self):
        self._assert_file_loads("contact.json")

    def test_flexion_extension_json_loads(self):
        self._assert_file_loads("flexion_extension.json")

    def test_effort_json_loads(self):
        self._assert_file_loads("effort.json")

    def test_shape_json_loads(self):
        self._assert_file_loads("shape.json")

    def test_floor_plan_json_loads(self):
        self._assert_file_loads("floor_plan.json")

    def test_foot_detail_json_loads(self):
        self._assert_file_loads("foot_detail.json")

    def test_sequential_json_loads(self):
        self._assert_file_loads("sequential.json")

    def _assert_file_loads(self, filename):
        path = CATALOG_DIR / filename
        self.assertTrue(path.exists(), f"{filename} does not exist")
        items = json.loads(path.read_text())
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 0, f"{filename} is empty")
        for item in items:
            self.assertIn(item["id"], self.catalog,
                          f"{item['id']} from {filename} not in loaded catalog")

    # ---- 4. Required fields on every new symbol ----

    def test_new_symbols_have_required_fields(self):
        for filename in NEW_FILES:
            path = CATALOG_DIR / filename
            items = json.loads(path.read_text())
            for item in items:
                for field in REQUIRED_FIELDS:
                    self.assertIn(field, item,
                                  f"{item.get('id', '?')} in {filename} missing '{field}'")
                geom = item["geometry"]
                self.assertIn("staff_column", geom,
                              f"{item['id']} missing geometry.staff_column")
                self.assertIn("glyph", geom,
                              f"{item['id']} missing geometry.glyph")

    # ---- 5. New time signatures exist ----

    def test_new_time_signatures_exist(self):
        for ts_id in NEW_TIME_SIGNATURES:
            self.assertIn(ts_id, self.catalog,
                          f"Time signature {ts_id} not found in catalog")

    def test_new_time_signatures_have_correct_category(self):
        for ts_id in NEW_TIME_SIGNATURES:
            spec = self.catalog[ts_id]
            self.assertEqual(spec["category"], "music",
                             f"{ts_id} has category '{spec['category']}', expected 'music'")

    # ---- 6. Family/category matches symbol_id prefix ----

    def test_category_matches_symbol_id_prefix(self):
        for filename, expected_category in EXPECTED_CATEGORIES.items():
            path = CATALOG_DIR / filename
            items = json.loads(path.read_text())
            for item in items:
                self.assertEqual(
                    item["category"], expected_category,
                    f"{item['id']} in {filename}: category '{item['category']}' "
                    f"!= expected '{expected_category}'",
                )

    # ---- 7. All allowed_body_parts values are valid ----

    def test_allowed_body_parts_are_valid(self):
        valid = set(BODY_PARTS)
        for filename in NEW_FILES:
            path = CATALOG_DIR / filename
            items = json.loads(path.read_text())
            for item in items:
                for bp in item["allowed_body_parts"]:
                    self.assertIn(
                        bp, valid,
                        f"{item['id']} in {filename}: "
                        f"invalid body part '{bp}'",
                    )

    # ---- 8. Staff column values are valid ----

    def test_staff_column_values_are_valid(self):
        for filename in NEW_FILES:
            path = CATALOG_DIR / filename
            items = json.loads(path.read_text())
            for item in items:
                col = item["geometry"]["staff_column"]
                self.assertIn(
                    col, VALID_STAFF_COLUMNS,
                    f"{item['id']} in {filename}: "
                    f"invalid staff_column '{col}'",
                )

    # ---- Bonus: minimum symbol counts per new file ----

    def test_retention_has_every_sign_knust_names(self):
        """Not a count. The family was 35 entries and is now 5, because the
        old ones crossed each sign with seven body categories that duplicated
        the symbol's own body_part field. A minimum-count assertion would
        have called that a regression; what matters is whether each sign
        Knust names is present (vol 2, Fig. 78-79)."""
        items = json.loads((CATALOG_DIR / "retention.json").read_text())
        ids = {e["id"] for e in items}
        for sign in ("retention.hold",        # 78a round
                     "retention.space_hold",  # 78b diamond
                     "retention.spot_hold",   # 78c diamond with a dot
                     "retention.cancel"):     # 79a decrease sign
            with self.subTest(sign=sign):
                self.assertIn(sign, ids)

    def test_contact_has_minimum_symbols(self):
        self._assert_min_symbols("contact.json", 30)

    def test_flexion_extension_has_minimum_symbols(self):
        self._assert_min_symbols("flexion_extension.json", 40)

    def test_effort_has_minimum_symbols(self):
        self._assert_min_symbols("effort.json", 25)

    def test_shape_has_minimum_symbols(self):
        self._assert_min_symbols("shape.json", 20)

    def test_floor_plan_has_minimum_symbols(self):
        self._assert_min_symbols("floor_plan.json", 25)

    def test_foot_detail_has_minimum_symbols(self):
        self._assert_min_symbols("foot_detail.json", 25)

    def test_sequential_has_minimum_symbols(self):
        self._assert_min_symbols("sequential.json", 8)

    def _assert_min_symbols(self, filename, minimum):
        path = CATALOG_DIR / filename
        items = json.loads(path.read_text())
        self.assertGreaterEqual(
            len(items), minimum,
            f"{filename} has {len(items)} symbols, expected >= {minimum}",
        )


if __name__ == "__main__":
    unittest.main()
