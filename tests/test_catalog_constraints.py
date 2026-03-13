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
        hint_actions = {hint["action"] for hint in result["repair_hints"]}
        self.assertIn("set_beat", hint_actions)

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


if __name__ == "__main__":
    unittest.main()
