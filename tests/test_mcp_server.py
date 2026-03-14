import unittest

from dancenotation_mcp.mcp_server.server import handle, repair_ir
from dancenotation_mcp.validation.validator import validate_ir


class MCPServerTests(unittest.TestCase):
    def test_tools_list(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIn("result", resp)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("plan_phrase", names)
        self.assertIn("generate_score", names)

    def test_plan_call(self):
        resp = handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "plan_phrase", "arguments": {"prompt": "step forward"}},
            }
        )
        self.assertIn("result", resp)
        payload = resp["result"]["content"][0]["json"]
        self.assertGreaterEqual(len(payload["steps"]), 1)

    def test_repair_ir_applies_relationship_repairs(self):
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
                    "symbol_id": "support.step.early",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.late",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        surface_glide = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "surface.glide")
        repeat_start = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.start")
        surface_contact = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "surface.contact")
        self.assertEqual(surface_glide["modifiers"]["attach_to"], "support.step.early")
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], "repeat.end")
        self.assertNotIn("measure_header", surface_contact["modifiers"])

    def test_repair_ir_can_shift_beats_for_semantic_conflicts(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        jump = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "jump.small")
        tempo = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.tempo.mark")
        self.assertEqual(jump["timing"]["beat"], 3.0)
        self.assertEqual(tempo["timing"]["beat"], 1.0)

    def test_repair_ir_can_shift_beats_for_direction_level_conflicts(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        conflicting = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "support.step.backward")
        self.assertEqual(conflicting["timing"]["beat"], 3.0)

    def test_repair_ir_removes_conflicting_companion_symbols(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["support.step.forward", "timing.hold", "quality.bound"])

    def test_repair_ir_removes_rest_when_it_overlaps_active_content(self):
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
            ],
        }
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual([symbol["symbol_id"] for symbol in repaired["symbols"]], ["support.step.forward"])

    def test_repair_ir_removes_repeat_boundaries_from_header_only_and_rest_only_measures(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual([symbol["symbol_id"] for symbol in repaired["symbols"]], ["music.time.3_4", "music.rest.quarter"])

    def test_repair_ir_removes_repeat_boundaries_from_empty_measures(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"], [])

    def test_repair_ir_retargets_invalid_target_roles(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        surface_glide = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "surface.glide")
        repeat_start = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.start")
        self.assertEqual(surface_glide["modifiers"]["attach_to"], "support.step.forward")
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], "repeat.end")

    def test_repair_ir_fills_missing_annotation_attachment(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][1]["modifiers"]["attach_to"], "support.step.forward")

    def test_repair_ir_prefers_same_measure_attachment_targets(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][1]["modifiers"]["attach_to"], "support.step.backward")

    def test_repair_ir_removes_incompatible_music_and_repeat_attachments(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertNotIn("attach_to", repaired["symbols"][0]["modifiers"])
        self.assertNotIn("attach_to", repaired["symbols"][1]["modifiers"])

    def test_repair_ir_uses_attachment_behavior_metadata(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        pin_hold = repaired["symbols"][0]
        self.assertEqual(pin_hold["modifiers"]["attach_to"], "support.step.forward")
        self.assertEqual(pin_hold["modifiers"]["attach_side"], "top")

    def test_repair_ir_prefers_motion_that_still_covers_annotation_beat(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][2]["modifiers"]["attach_to"], "support.step.backward")

    def test_repair_ir_removes_invalid_modifier_source_roles(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertNotIn("attach_to", repaired["symbols"][0]["modifiers"])
        self.assertTrue(all(sym.get("symbol_id") != "repeat.end" for sym in repaired["symbols"]))

    def test_repair_ir_removes_or_retargets_variant_role_violations(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        pin_generic = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "pin.generic")
        music_rest = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.rest.quarter")
        repeat_start = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.start")
        self.assertNotIn("attach_side", pin_generic["modifiers"])
        self.assertNotIn("measure_header", music_rest["modifiers"])
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], "repeat.end")

    def test_repair_ir_trims_measure_overflow_and_duplicate_headers(self):
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
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 2},
                    "modifiers": {},
                },
            ],
        }
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        kept_headers = [sym for sym in repaired["symbols"] if sym.get("modifiers", {}).get("measure_header")]
        self.assertEqual(len(kept_headers), 2)
        self.assertEqual(repaired["symbols"][2]["timing"]["duration_beats"], 1.0)
        self.assertEqual(repaired["symbols"][3]["timing"]["measure"], 2)
        self.assertEqual(repaired["symbols"][3]["timing"]["beat"], 1.0)
        self.assertEqual(repaired["symbols"][3]["timing"]["duration_beats"], 1.0)

    def test_repair_ir_trims_measure_overflow_using_active_time_signature(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][1]["timing"]["duration_beats"], 1.0)
        self.assertEqual(repaired["symbols"][2]["timing"]["measure"], 2)
        self.assertEqual(repaired["symbols"][2]["timing"]["beat"], 1.0)
        self.assertEqual(repaired["symbols"][2]["timing"]["duration_beats"], 1.0)

    def test_repair_ir_prefers_same_body_part_attachment_targets(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][0]["modifiers"]["attach_to"], "gesture.arm")

    def test_repair_ir_removes_orphaned_repeat_signs(self):
        ir = {
            "metadata": {"ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"], [])

    def test_repair_ir_retargets_repeat_to_nearest_closing_sign(self):
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
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][0]["modifiers"]["repeat_span_to"], "repeat.end")

    def test_repair_ir_fills_missing_repeat_span_target(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        repeat_start = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.start")
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], "repeat.end")

    def test_repair_ir_removes_nested_repeat_start(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["repeat.start", "repeat.end"])

    def test_repair_ir_removes_duplicate_repeat_end_slots(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["repeat.start", "repeat.end"])

    def test_repair_ir_removes_duplicate_repeat_start_slots(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["repeat.start", "repeat.end"])

    def test_repair_ir_removes_mixed_repeat_boundary_conflict(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"], [])

    def test_repair_ir_removes_redundant_consecutive_time_signatures(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["music.time.4_4", "music.time.3_4"])

    def test_repair_ir_removes_redundant_consecutive_tempos(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_tempos = [sym.get("modifiers", {}).get("tempo") for sym in repaired["symbols"]]
        self.assertEqual(remaining_tempos, [120, 132])

    def test_repair_ir_fills_missing_music_header_content(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        tempo_header = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.tempo.mark")
        cadence_header = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.cadence.mark")
        self.assertEqual(tempo_header["modifiers"]["tempo"], 120)
        self.assertEqual(cadence_header["modifiers"]["label"], "rit.")

    def test_repair_ir_carries_score_scoped_tempo_and_cadence_content(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        tempo_headers = [sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.tempo.mark"]
        cadence_headers = [sym for sym in repaired["symbols"] if sym["symbol_id"] == "music.cadence.mark"]
        self.assertEqual(tempo_headers[1]["modifiers"]["tempo"], 108)
        self.assertEqual(cadence_headers[1]["modifiers"]["label"], "rit.")

    def test_repair_ir_inserts_missing_hold_continuation_symbol(self):
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
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        continuations = [
            sym for sym in repaired["symbols"]
            if sym["symbol_id"] == "timing.hold"
        ]
        self.assertGreaterEqual(len(continuations), 2)
        inserted = next(sym for sym in continuations if sym["timing"]["measure"] == 2)
        self.assertEqual(inserted["timing"]["beat"], 1.0)
        self.assertEqual(inserted["modifiers"]["attach_to"], "support.step.backward")

    def test_repair_ir_sets_required_variant_modifiers(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][0]["modifiers"]["pin_head"], "diamond")
        self.assertEqual(repaired["symbols"][1]["modifiers"]["separator_mode"], "double")

    def test_repair_ir_removes_redundant_consecutive_cadence_headers(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_labels = [sym.get("modifiers", {}).get("label") for sym in repaired["symbols"]]
        self.assertEqual(remaining_labels, ["rit.", "a tempo"])

    def test_repair_ir_removes_duplicate_header_families_within_measure(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["music.time.4_4", "music.tempo.mark"])

    def test_repair_ir_reorders_measure_headers_into_canonical_order(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["music.time.4_4", "music.tempo.mark", "music.cadence.mark"])

    def test_repair_ir_moves_measure_headers_before_content(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        remaining_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(remaining_ids, ["music.time.4_4", "music.tempo.mark", "support.step.forward"])

    def test_repair_ir_sets_measure_header_body_part_to_torso(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][0]["body_part"], "torso")

    def test_repair_ir_sets_repeat_body_part_to_torso(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        self.assertEqual(repaired["symbols"][0]["body_part"], "torso")
        self.assertEqual(repaired["symbols"][1]["body_part"], "torso")

    def test_repair_ir_aligns_repeat_boundaries_to_measure_edges(self):
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
                    "timing": {"measure": 2, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        start = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.start")
        end = next(sym for sym in repaired["symbols"] if sym["symbol_id"] == "repeat.end")
        self.assertEqual(start["timing"]["beat"], 1.0)
        self.assertEqual(end["timing"]["beat"], 3.0)

    def test_repair_ir_reorders_repeat_boundaries_around_measure_content(self):
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
        diagnostics = validate_ir(ir)
        repaired = repair_ir(ir, diagnostics)
        repaired_ids = [sym["symbol_id"] for sym in repaired["symbols"]]
        self.assertEqual(
            repaired_ids,
            ["repeat.start", "support.step.forward", "support.step.backward", "repeat.end"],
        )


if __name__ == "__main__":
    unittest.main()
