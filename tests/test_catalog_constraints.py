import json
import unittest
from pathlib import Path

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.models import DIRECTIONS
from dancenotation_mcp.validation.validator import REPAIR_ACTION_PRIORITY, validate_ir

ROOT = Path(__file__).resolve().parents[1]


class CatalogConstraintTests(unittest.TestCase):
    def test_catalog_is_large(self):
        catalog = load_symbol_catalog()
        self.assertGreaterEqual(len(catalog), 850)

    def test_direction_naming_is_consistent_across_catalog_schema_and_models(self):
        """Guards against a real inconsistency found during the LabanWriter-
        parity audit: the catalog's allowed_directions used
        "diagonal_forward_left" etc. (1360 declarations) while the schema's
        direction enum and models.DIRECTIONS both used the short
        "forward_left" form instead — silently unenforced (validate_schema()
        is a hand-rolled check, not real jsonschema validation) but wrong
        documentation that would break the moment someone wired up real
        schema enforcement. All three must agree on one spelling.
        """
        catalog = load_symbol_catalog()
        catalog_directions: set[str] = set()
        for spec in catalog.values():
            catalog_directions.update(spec.get("allowed_directions", []))

        schema = json.loads((ROOT / "schemas" / "notation-ir.schema.json").read_text(encoding="utf-8"))
        schema_directions = set(
            schema["properties"]["symbols"]["items"]["properties"]["direction"]["enum"]
        ) - {None}

        self.assertEqual(
            catalog_directions, schema_directions,
            "Catalog allowed_directions and the schema's direction enum have "
            "diverged — pick one spelling (diagonal_forward_left, not "
            "forward_left) and update whichever side is behind.",
        )
        self.assertEqual(
            catalog_directions, set(DIRECTIONS),
            "Catalog allowed_directions and ir.models.DIRECTIONS have "
            "diverged the same way.",
        )

    def test_every_symbol_has_geometry_and_constraints(self):
        catalog = load_symbol_catalog()
        for sid, spec in catalog.items():
            self.assertIn("allowed_body_parts", spec, sid)
            self.assertIn("allowed_directions", spec, sid)
            self.assertIn("allowed_levels", spec, sid)
            self.assertIn("geometry", spec, sid)
            self.assertIn("glyph", spec["geometry"], sid)

    def test_every_symbol_geometry_is_complete_and_valid(self):
        """Guard produced by the LabanWriter-parity geometry audit.

        The prior test only checked that ``geometry`` and ``glyph`` exist. The
        audit swept all catalog entries and confirmed every one carries the
        full geometry contract the layout/renderer consume — ``glyph``,
        ``width``, ``height``, ``anchor``, ``staff_column`` — with valid
        values (positive dimensions, an anchor from the known set, a routed
        staff_column). This locks that invariant so a future catalog addition
        can't silently ship an entry missing a field or holding a degenerate
        value (which previously fell through to a generic misrender).

        ``VALID_ANCHORS`` / ``ROUTED_STAFF_COLUMNS`` are the exact value sets
        observed across the catalog at audit time; extend them deliberately
        (and wire the renderer to match) when a genuinely new class is added.
        """
        VALID_ANCHORS = {"center", "adjacent", "foot"}
        ROUTED_STAFF_COLUMNS = {
            "support", "body", "jump", "gesture", "turn", "travel", "floor",
            "quality", "surface", "timing", "foothook", "floor_plan", "music",
            "direction", "separator", "path", "bow", "pin", "repeat", "motif",
            "space", "level", "dynamic", "adlib", "flexion", "digit",
            # "retention" replaced "timing" on all 21 retention entries. A
            # retention sign is read from the column it sits in -- Knust vol 1
            # Rule III, p67 -- so it is placed by body part like a primary
            # symbol, not parked in the timing lane where every one of them
            # landed at the same x.
            "retention",
        }
        catalog = load_symbol_catalog()
        for sid, spec in catalog.items():
            geom = spec.get("geometry")
            self.assertIsInstance(geom, dict, sid)
            for field in ("glyph", "width", "height", "anchor", "staff_column"):
                self.assertIn(field, geom, f"{sid} missing geometry.{field}")
                self.assertNotIn(geom[field], (None, ""), f"{sid} empty geometry.{field}")
            for dim in ("width", "height"):
                self.assertIsInstance(geom[dim], (int, float), f"{sid} geometry.{dim} not numeric")
                self.assertGreater(geom[dim], 0, f"{sid} geometry.{dim} must be positive")
            self.assertIn(
                geom["anchor"], VALID_ANCHORS,
                f"{sid} geometry.anchor {geom['anchor']!r} not in {sorted(VALID_ANCHORS)}",
            )
            self.assertIn(
                geom["staff_column"], ROUTED_STAFF_COLUMNS,
                f"{sid} geometry.staff_column {geom['staff_column']!r} is not a routed "
                "column — add a renderer/layout route and list it here, or fix the value.",
            )

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

    def test_modifier_semantic_relationships_are_applied(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.late"},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.start"},
                },
                {
                    "symbol_id": "surface.contact",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "support.step.late",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TARGET_FUTURE", codes)
        self.assertIn("MODIFIER_REPEAT_SPAN_TARGET_ORDER", codes)
        self.assertIn("MODIFIER_MEASURE_HEADER_UNSUPPORTED", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)
        self.assertIn("retarget_repeat_span", hint_actions)
        self.assertIn("remove_modifier", hint_actions)

    def test_body_part_conflict_and_measure_header_timing_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1.5, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("BODY_PART_SIMULTANEITY_CONFLICT", codes)
        self.assertIn("MODIFIER_MEASURE_HEADER_TIMING", codes)

    def test_body_part_direction_and_level_conflicts_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "high",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "left_leg",
                    "direction": "backward",
                    "level": "low",
                    "timing": {"measure": 1, "beat": 1.5, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("BODY_PART_DIRECTION_LEVEL_CONFLICT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_beat", hint_actions)

    def test_conflicting_quality_and_timing_companions_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "timing.staccato",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "quality.bound",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "quality.free",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("TIMING_COMPANION_CONFLICT", codes)
        self.assertIn("QUALITY_COMPANION_CONFLICT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)
        self.assertNotIn("set_beat", hint_actions)

    def test_rests_should_not_overlap_active_content(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REST_CONTENT_CONFLICT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_semantic_severity_stratification_distinguishes_invalid_and_repairable_issues(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "quality.sudden"},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 5},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        severity_by_code = {issue["code"]: issue["severity"] for issue in result["issues"]}
        self.assertEqual(severity_by_code["MODIFIER_ATTACH_TARGET_ROLE"], "error")
        self.assertEqual(severity_by_code["TIMING_MEASURE_OVERFLOW"], "warning")
        self.assertEqual(severity_by_code["REPEAT_START_TIMING"], "warning")
        self.assertEqual(severity_by_code["REST_CONTENT_CONFLICT"], "warning")

    def test_repair_hints_are_returned_in_deterministic_priority_order(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "missing.motion"},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        actions = [hint["action"] for hint in result["repair_hints"]]
        self.assertEqual(actions, sorted(actions, key=lambda action: REPAIR_ACTION_PRIORITY.get(action, 99)))

    def test_repeat_boundaries_on_header_only_and_rest_only_measures_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_BOUNDARY_HEADER_ONLY_MEASURE", codes)
        self.assertIn("REPEAT_BOUNDARY_REST_ONLY_MEASURE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_repeat_boundaries_on_empty_measures_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_BOUNDARY_EMPTY_MEASURE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_cross_measure_hold_and_sustained_quality_continuity_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 3},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 3},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "quality.sustained",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 3},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("HOLD_CONTINUATION_MISSING", codes)
        self.assertIn("SUSTAINED_QUALITY_CONTINUATION_MISSING", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("insert_continuation_symbol", hint_actions)

    def test_repeat_and_music_behavior_metadata_is_present_for_key_official_families(self):
        catalog = load_symbol_catalog()
        self.assertEqual(catalog["repeat.start"]["behavior"]["boundary_role"], "opening")
        self.assertEqual(catalog["repeat.end"]["behavior"]["boundary_role"], "closing")
        self.assertEqual(catalog["music.time.3_4"]["behavior"]["header_role"], "time_signature")
        self.assertEqual(catalog["music.tempo.mark"]["behavior"]["continuation_scope"], "score")
        self.assertEqual(catalog["music.rest.quarter"]["behavior"]["continuation_scope"], "measure")
        self.assertEqual(catalog["pin.entry"]["behavior"]["preferred_pin_head"], "diamond")
        self.assertEqual(catalog["separator.double"]["behavior"]["preferred_separator_mode"], "double")
        self.assertIn("support", catalog["surface.glide"]["behavior"]["valid_anchor_families"])
        self.assertEqual(catalog["pin.hold"]["behavior"]["preferred_anchor_side"], "top")

    def test_behavior_bearing_families_have_complete_audit_metadata(self):
        catalog = load_symbol_catalog()
        repeat_symbols = {"repeat.start", "repeat.end", "repeat.double"}
        music_header_symbols = {
            "music.time.2_4",
            "music.time.3_4",
            "music.time.4_4",
            "music.tempo.mark",
            "music.cadence.mark",
            "music.rest.quarter",
        }
        attachment_symbols = {
            "pin.generic",
            "pin.entry",
            "pin.hold",
            "surface.contact",
            "surface.brush",
            "surface.glide",
        }
        for symbol_id in repeat_symbols:
            behavior = catalog[symbol_id]["behavior"]
            self.assertIn("boundary_role", behavior, symbol_id)
            self.assertIn("continuation_scope", behavior, symbol_id)
            self.assertIn("default_repair_target_family", behavior, symbol_id)
        for symbol_id in music_header_symbols:
            behavior = catalog[symbol_id]["behavior"]
            self.assertIn("header_role", behavior, symbol_id)
            self.assertIn("continuation_scope", behavior, symbol_id)
            self.assertIn("default_repair_target_family", behavior, symbol_id)
        for symbol_id in attachment_symbols:
            behavior = catalog[symbol_id]["behavior"]
            self.assertIn("preferred_anchor_side", behavior, symbol_id)
            self.assertIn("valid_anchor_families", behavior, symbol_id)
            self.assertIn("coverage_expectation", behavior, symbol_id)
            self.assertIsInstance(behavior["valid_anchor_families"], list, symbol_id)
            self.assertTrue(behavior["valid_anchor_families"], symbol_id)

    def test_direction_and_level_transformation_metadata_is_present_for_transforming_families(self):
        catalog = load_symbol_catalog()
        transforming_symbols = {
            "path.straight",
            "path.curved",
            "path.spiral",
            "path.circle",
            "motif.rise",
            "motif.fall",
            "motif.arc",
        }
        for symbol_id in transforming_symbols:
            behavior = catalog[symbol_id]["behavior"]
            self.assertIn("direction_transform", behavior, symbol_id)
            self.assertIn("rotation_rule", behavior, symbol_id)
        self.assertEqual(catalog["separator.staff.flipped"]["behavior"]["flip_variant"], "horizontal")
        self.assertEqual(catalog["level.high"]["behavior"]["level_fill_mode"], "outline")
        self.assertEqual(catalog["level.middle"]["behavior"]["level_fill_mode"], "half_fill")
        self.assertEqual(catalog["level.low"]["behavior"]["level_fill_mode"], "solid")

    def test_path_motif_and_surface_space_behavior_metadata_is_present(self):
        catalog = load_symbol_catalog()
        for symbol_id in {"path.straight", "path.curved", "path.spiral", "path.circle"}:
            behavior = catalog[symbol_id]["behavior"]
            self.assertEqual(behavior["composition_role"], "trajectory", symbol_id)
            self.assertIn("path_shape", behavior, symbol_id)
            self.assertIn("repeatable_segment", behavior, symbol_id)
            self.assertIn("supports_arrowheads", behavior, symbol_id)
        for symbol_id in {"motif.rise", "motif.fall", "motif.arc"}:
            behavior = catalog[symbol_id]["behavior"]
            self.assertEqual(behavior["composition_role"], "motif", symbol_id)
            self.assertIn("motif_variant", behavior, symbol_id)
        self.assertEqual(catalog["surface.contact"]["behavior"]["surface_role"], "contact")
        self.assertEqual(catalog["surface.brush"]["behavior"]["surface_role"], "brush")
        self.assertEqual(catalog["surface.glide"]["behavior"]["surface_role"], "glide")
        self.assertEqual(catalog["space.hold"]["behavior"]["whitespace_role"], "hold")
        self.assertEqual(catalog["space.transition"]["behavior"]["whitespace_role"], "transition")

    def test_manual_parity_variants_have_behavior_metadata(self):
        catalog = load_symbol_catalog()
        for symbol_id in {"jump.spring", "motif.rise_fall", "space.whitespace", "separator.hook"}:
            self.assertIn("behavior", catalog[symbol_id], symbol_id)

    def test_stretchable_families_expose_stretch_caps_and_segments(self):
        catalog = load_symbol_catalog()
        stretchable_symbols = {
            "path.straight",
            "path.curved",
            "path.spiral",
            "path.circle",
            "pin.generic",
            "pin.entry",
            "pin.hold",
            "space.hold",
            "space.transition",
            "separator.staff",
            "separator.staff.flipped",
            "separator.single",
            "separator.double",
        }
        for symbol_id in stretchable_symbols:
            behavior = catalog[symbol_id]["behavior"]
            self.assertIn("min_stretch", behavior, symbol_id)
            self.assertIn("max_stretch", behavior, symbol_id)
            self.assertIn("cap_shape", behavior, symbol_id)
            self.assertLessEqual(float(behavior["min_stretch"]), float(behavior["max_stretch"]), symbol_id)
        self.assertEqual(catalog["path.straight"]["behavior"]["repeatable_segment"], "shaft")
        self.assertEqual(catalog["path.curved"]["behavior"]["repeatable_segment"], "curve_body")
        self.assertEqual(catalog["path.circle"]["behavior"]["cap_shape"], "closed")

    def test_modifier_target_roles_are_enforced(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "quality.sudden"},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "support.step.forward"},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "right_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TARGET_ROLE", codes)
        self.assertIn("MODIFIER_REPEAT_SPAN_TARGET_ROLE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)
        self.assertIn("retarget_repeat_span", hint_actions)

    def test_annotation_symbols_require_attachment_targets(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_MISSING_FOR_ANNOTATION", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)

    def test_annotation_attachments_should_not_cross_measure_boundaries(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "left_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TARGET_MEASURE_MISMATCH", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)

    def test_music_and_repeat_families_do_not_use_movement_attachments(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_FAMILY_INCOMPATIBLE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_modifier", hint_actions)

    def test_attachment_families_consume_behavior_metadata_for_anchor_rules(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.hold",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "flexion.knee", "attach_side": "left"},
                },
                {
                    "symbol_id": "flexion.knee",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TARGET_FAMILY_INCOMPATIBLE", codes)
        self.assertIn("MODIFIER_ATTACH_SIDE_PREFERRED_MISMATCH", codes)
        hinted = {(hint["action"], hint.get("key"), hint.get("value")) for hint in result["repair_hints"]}
        self.assertIn(("set_modifier", "attach_side", "top"), hinted)

    def test_annotation_attachments_should_not_target_finished_motion(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "left_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_TARGET_OUTSIDE_COVERAGE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)

    def test_modifier_source_roles_are_enforced(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.backward"},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_SOURCE_ROLE", codes)
        self.assertIn("MODIFIER_REPEAT_SPAN_SOURCE_ROLE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_modifier", hint_actions)

    def test_modifier_variant_roles_and_dependencies_are_enforced(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.generic",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_side": "left"},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.start"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_SIDE_ORPHANED", codes)
        self.assertIn("MODIFIER_MEASURE_HEADER_SYMBOL_ROLE", codes)
        self.assertIn("MODIFIER_REPEAT_SPAN_TARGET_VARIANT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_modifier", hint_actions)
        self.assertIn("retarget_repeat_span", hint_actions)

    def test_measure_overflow_and_duplicate_headers_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 108},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 2},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("TIMING_MEASURE_OVERFLOW", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_duration", hint_actions)
        self.assertIn("split_duration", hint_actions)

    def test_measure_overflow_uses_active_time_signature(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 2},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        overflow_issue = next(issue for issue in result["issues"] if issue["code"] == "TIMING_MEASURE_OVERFLOW")
        self.assertEqual(overflow_issue["details"]["measure_beats"], 3.0)
        self.assertEqual(overflow_issue["details"]["max_duration"], 1.0)
        self.assertEqual(overflow_issue["details"]["carry_duration"], 1.0)

    def test_stacked_header_families_in_same_measure_are_allowed(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "rit."},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertNotIn("MEASURE_HEADER_FAMILY_DUPLICATE", codes)

    def test_overlap_is_measured_within_each_measure_only(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertNotIn("TIMING_OVERLAP", codes)

    def test_attachment_body_part_consistency_is_enforced(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "right_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "gesture.arm",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_ATTACH_BODY_PART_MISMATCH", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_attachment", hint_actions)

    def test_orphaned_repeat_structures_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 3, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = [issue["code"] for issue in result["issues"]]
        self.assertIn("REPEAT_END_ORPHANED", codes)
        self.assertIn("REPEAT_START_UNCLOSED", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_repeat_start_cannot_skip_closer_closing_sign(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.double"},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_SPAN_TARGET_SKIPS_CLOSER_END", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_repeat_span", hint_actions)

    def test_repeat_start_without_explicit_span_target_is_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_START_MISSING_SPAN_TARGET", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("retarget_repeat_span", hint_actions)

    def test_nested_repeat_starts_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_START_NESTED_UNSUPPORTED", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_duplicate_repeat_end_slots_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_END_SLOT_DUPLICATE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_duplicate_repeat_start_slots_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_START_SLOT_DUPLICATE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_mixed_repeat_boundaries_on_same_slot_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_SLOT_MIXED_BOUNDARY_CONFLICT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_redundant_consecutive_time_signatures_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 3, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
            ],
        }
        result = validate_ir(ir)
        codes = [issue["code"] for issue in result["issues"]]
        self.assertIn("MUSIC_TIME_SIGNATURE_REDUNDANT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_redundant_consecutive_tempos_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 3, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 132},
                },
            ],
        }
        result = validate_ir(ir)
        codes = [issue["code"] for issue in result["issues"]]
        self.assertIn("MUSIC_TEMPO_REDUNDANT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_music_headers_require_tempo_and_cadence_content(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MUSIC_TEMPO_VALUE_MISSING", codes)
        self.assertIn("MUSIC_CADENCE_LABEL_MISSING", codes)

    def test_music_headers_can_carry_score_scoped_tempo_and_cadence_values(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 108},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "rit."},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MUSIC_TEMPO_CONTINUATION_VALUE_MISSING", codes)
        self.assertIn("MUSIC_CADENCE_CONTINUATION_LABEL_MISSING", codes)
        hinted = {(hint["action"], hint.get("key"), hint.get("value")) for hint in result["repair_hints"]}
        self.assertIn(("set_modifier", "tempo", 108), hinted)
        self.assertIn(("set_modifier", "label", "rit."), hinted)

    def test_pin_and_separator_variants_require_matching_modifiers(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.entry",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"pin_head": "circle"},
                },
                {
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"separator_mode": "single"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("PIN_VARIANT_HEAD_REQUIRED", codes)
        self.assertIn("SEPARATOR_VARIANT_MODE_REQUIRED", codes)
        hinted = {(hint["action"], hint.get("key"), hint.get("value")) for hint in result["repair_hints"]}
        self.assertIn(("set_modifier", "pin_head", "diamond"), hinted)
        self.assertIn(("set_modifier", "separator_mode", "double"), hinted)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_modifier", hint_actions)

    def test_redundant_consecutive_cadence_headers_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "rit."},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "rit."},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 3, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "a tempo"},
                },
            ],
        }
        result = validate_ir(ir)
        codes = [issue["code"] for issue in result["issues"]]
        self.assertIn("MUSIC_CADENCE_REDUNDANT", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_duplicate_header_families_within_measure_are_reported(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 132},
                },
            ],
        }
        result = validate_ir(ir)
        codes = [issue["code"] for issue in result["issues"]]
        self.assertIn("MEASURE_HEADER_FAMILY_DUPLICATE", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("remove_symbol", hint_actions)

    def test_measure_header_order_is_enforced_within_measure(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "label": "rit."},
                },
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 120},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MEASURE_HEADER_ORDER_INVALID", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("reorder_measure_headers", hint_actions)

    def test_measure_headers_must_precede_content_within_measure(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MEASURE_HEADER_POSITION_INVALID", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("reorder_measure_headers", hint_actions)

    def test_measure_headers_should_use_torso_body_part(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.4_4",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("MODIFIER_MEASURE_HEADER_BODY_PART", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_body_part", hint_actions)

    def test_repeat_symbols_should_use_torso_body_part(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_BODY_PART_INVALID", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_body_part", hint_actions)

    def test_repeat_boundaries_should_align_to_measure_edges(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_START_TIMING", codes)
        self.assertIn("REPEAT_END_TIMING", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_beat", hint_actions)

    def test_repeat_boundaries_should_wrap_measure_content_in_symbol_order(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertIn("REPEAT_START_POSITION_INVALID", codes)
        self.assertIn("REPEAT_END_POSITION_INVALID", codes)
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("reorder_repeat_boundaries", hint_actions)


class NoCombinatorialTurnJumpEntriesTest(unittest.TestCase):
    """Turn and jump signs take no compass direction in LabanWriter.

    A turn's direction is rotational (right/left), carried by the sign's own
    arc, and a jump's travel direction is carried by the direction symbols in
    the support columns — never by the jump sign itself. Entries like
    ``turn.full.diagonal_backward_left.high`` therefore name signs that do not
    exist in any LabanWriter palette. They rendered identically to their base
    sign, inflated the catalog count without adding a single glyph, and no
    parser path or fixture ever produced one.
    """

    DIRECTIONS = {
        "forward", "backward", "left", "right", "place",
        "diagonal_forward_left", "diagonal_forward_right",
        "diagonal_backward_left", "diagonal_backward_right",
    }
    LEVELS = {"high", "middle", "low"}

    def test_turn_and_jump_ids_carry_no_direction_or_level_suffix(self):
        offenders = sorted(
            sid for sid in load_symbol_catalog()
            if sid.split(".")[0] in ("turn", "jump")
            and set(sid.split(".")) & (self.DIRECTIONS | self.LEVELS)
        )
        self.assertEqual(
            offenders, [],
            f"{len(offenders)} combinatorial turn/jump entries remain, "
            f"e.g. {offenders[:3]}",
        )

    def test_the_base_turn_and_jump_signs_are_still_present(self):
        # The real signs must survive the cleanup — this is the guard that
        # stops the rule above from being satisfied by deleting the family.
        catalog = load_symbol_catalog()
        for sid in ("turn.full", "turn.half", "turn.pivot", "turn.spin",
                    "jump.assemble", "jump.large", "jump.sissonne",
                    "jump.small", "jump.spring"):
            with self.subTest(symbol=sid):
                self.assertIn(sid, catalog)


if __name__ == "__main__":
    unittest.main()
