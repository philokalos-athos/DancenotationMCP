import json
from pathlib import Path
import re
import unittest

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.validation.validator import validate_ir
from dancenotation_mcp.rendering.svg_renderer import _header_gutter_width, _measure_header_corridors, _render_attachment_polyline, _reserve_routing_track, render_svg


ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def test_phrase_to_ir_roundtrip(self):
        plan = parse_phrase("step forward, turn right")
        self.assertGreaterEqual(len(plan["steps"]), 2)
        ir = phrase_plan_to_ir(plan, "step forward, turn right")
        res = validate_ir(ir)
        self.assertTrue(res["ok"])

    def test_phrase_parser_supports_richer_action_direction_and_duration_words(self):
        plan = parse_phrase("left hand glide forward right for two beats, then leap backward low")
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0]["symbol_id"], "surface.glide")
        self.assertEqual(plan["steps"][0]["body_part"], "left_arm")
        self.assertEqual(plan["steps"][0]["direction"], "diagonal_forward_right")
        self.assertEqual(plan["steps"][0]["timing"]["duration_beats"], 2.0)
        self.assertEqual(plan["steps"][1]["symbol_id"], "jump.small")
        self.assertEqual(plan["steps"][1]["direction"], "backward")
        self.assertEqual(plan["steps"][1]["level"], "low")

    def test_phrase_parser_supports_richer_count_durations(self):
        plan = parse_phrase("step forward for four beats, gesture high half beat, brush left quarter beat, jump right one and a half beats")
        primary_steps = [step for step in plan["steps"] if step["symbol_id"] in {"support.step", "gesture.arm", "surface.brush", "jump.small"}]
        self.assertEqual([step["timing"]["duration_beats"] for step in primary_steps], [4.0, 0.5, 0.25, 1.5])

    def test_phrase_parser_emits_quality_and_timing_companions(self):
        plan = parse_phrase("left hand glide forward right sudden accented")
        symbol_ids = [step["symbol_id"] for step in plan["steps"]]
        self.assertEqual(symbol_ids, ["surface.glide", "quality.sudden", "timing.accent"])
        self.assertTrue(all(step["timing"]["beat"] == 1.0 for step in plan["steps"]))

    def test_phrase_parser_emits_hold_timing_symbol_for_duration_language(self):
        plan = parse_phrase("hold step forward")
        symbol_ids = [step["symbol_id"] for step in plan["steps"]]
        self.assertEqual(symbol_ids, ["support.step", "timing.hold"])
        self.assertTrue(all(step["timing"]["duration_beats"] == 2.0 for step in plan["steps"]))

    def test_phrase_parser_supports_music_and_repeat_language(self):
        plan = parse_phrase("3/4 time, tempo 120, ritardando, begin repeat, step forward, end repeat")
        self.assertEqual([step["symbol_id"] for step in plan["steps"][:4]], ["music.time.3_4", "music.tempo.mark", "music.cadence.mark", "repeat.start"])
        self.assertTrue(plan["steps"][0]["modifiers"]["measure_header"])
        self.assertEqual(plan["steps"][1]["modifiers"]["tempo"], 120)
        self.assertEqual(plan["steps"][2]["modifiers"]["label"], "ritardando")
        self.assertEqual(plan["steps"][3]["body_part"], "torso")
        self.assertEqual(plan["steps"][0]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][1]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][2]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][3]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][4]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][5]["timing"]["beat"], 2.0)

    def test_phrase_parser_supports_repeat_count_language(self):
        plan = parse_phrase("repeat twice, repeat three times")
        self.assertEqual([step["symbol_id"] for step in plan["steps"]], ["repeat.double", "repeat.end"])
        self.assertEqual(plan["steps"][0]["modifiers"]["repeat_count"], 2)
        self.assertEqual(plan["steps"][1]["modifiers"]["repeat_count"], 3)

    def test_phrase_parser_supports_rest_and_pause_language(self):
        plan = parse_phrase("rest, pause half beat, silence quarter beat")
        self.assertEqual(
            [step["symbol_id"] for step in plan["steps"]],
            ["music.rest.quarter", "music.rest.eighth", "music.rest.sixteenth"],
        )
        self.assertTrue(all(step["body_part"] == "torso" for step in plan["steps"]))
        self.assertEqual([step["timing"]["duration_beats"] for step in plan["steps"]], [1.0, 0.5, 0.25])

    def test_phrase_parser_supports_richer_body_and_direction_aliases(self):
        plan = parse_phrase("head turn counterclockwise, chest gesture upstage, hips step in place")
        self.assertEqual(plan["steps"][0]["body_part"], "head")
        self.assertEqual(plan["steps"][0]["direction"], "left")
        self.assertEqual(plan["steps"][1]["body_part"], "torso")
        self.assertEqual(plan["steps"][1]["direction"], "backward")
        self.assertEqual(plan["steps"][2]["body_part"], "torso")
        self.assertEqual(plan["steps"][2]["direction"], "place")

    def test_phrase_parser_supports_plural_body_aliases(self):
        plan = parse_phrase("both hands gesture slowly, both feet step in place")
        primary = [step for step in plan["steps"] if step["symbol_id"] in {"gesture.arm", "support.step"}]
        companions = [step for step in plan["steps"] if step["symbol_id"] == "quality.sustained"]
        self.assertEqual([step["body_part"] for step in primary[:2]], ["left_arm", "right_arm"])
        self.assertEqual([step["body_part"] for step in primary[2:]], ["left_leg", "right_leg"])
        self.assertEqual([step["direction"] for step in primary[2:]], ["place", "place"])
        self.assertEqual([step["body_part"] for step in companions], ["left_arm", "right_arm"])

    def test_phrase_parser_supports_basic_negation_and_cancellation_language(self):
        plan = parse_phrase("step forward without turn, no repeat, glide left without jump, release hold step right")
        self.assertEqual([step["symbol_id"] for step in plan["steps"]], ["support.step", "surface.glide", "support.step"])
        self.assertEqual(plan["steps"][-1]["timing"]["duration_beats"], 1.0)
        self.assertNotIn("timing.hold", [step["symbol_id"] for step in plan["steps"]])

    def test_phrase_parser_supports_bpm_only_and_accelerando_language(self):
        plan = parse_phrase("3/4 time, 120 bpm, accel.")
        self.assertEqual([step["symbol_id"] for step in plan["steps"]], ["music.time.3_4", "music.tempo.mark", "music.cadence.mark"])
        self.assertTrue(plan["steps"][1]["modifiers"]["measure_header"])
        self.assertEqual(plan["steps"][1]["modifiers"]["tempo"], 120)
        self.assertEqual(plan["steps"][2]["modifiers"]["label"], "accel.")

    def test_phrase_parser_normalizes_fragmented_music_abbreviations(self):
        plan = parse_phrase("3/4 time; 120 bpm; accel . ; rit .")
        self.assertEqual(
            [step["symbol_id"] for step in plan["steps"]],
            ["music.time.3_4", "music.tempo.mark", "music.cadence.mark", "music.cadence.mark"],
        )
        self.assertEqual(plan["steps"][2]["modifiers"]["label"], "accel.")
        self.assertEqual(plan["steps"][3]["modifiers"]["label"], "rit.")

    def test_phrase_parser_supports_parenthetical_grouping_and_immediate_qualifier(self):
        plan = parse_phrase("step forward (suddenly then hold), turn left")
        self.assertEqual(
            [step["symbol_id"] for step in plan["steps"][:3]],
            ["support.step", "quality.sudden", "timing.hold"],
        )
        turn = next(step for step in plan["steps"] if step["symbol_id"] == "turn.pivot")
        self.assertEqual(turn["timing"]["beat"], 3.0)

    def test_phrase_parser_supports_grouped_parallel_branches_with_different_durations(self):
        plan = parse_phrase("left hand gesture high for two beats while (right foot step forward, turn left), jump right")
        primary = [step for step in plan["steps"] if step["symbol_id"] in {"gesture.arm", "support.step", "turn.pivot", "jump.small"}]
        self.assertEqual(primary[0]["symbol_id"], "gesture.arm")
        self.assertEqual(primary[0]["timing"]["beat"], 1.0)
        self.assertEqual(primary[0]["timing"]["duration_beats"], 2.0)
        self.assertEqual(primary[1]["symbol_id"], "support.step")
        self.assertEqual(primary[1]["timing"]["beat"], 1.0)
        self.assertEqual(primary[2]["symbol_id"], "turn.pivot")
        self.assertEqual(primary[2]["timing"]["beat"], 2.0)
        self.assertEqual(primary[3]["symbol_id"], "jump.small")
        self.assertEqual(primary[3]["timing"]["beat"], 3.0)

    def test_phrase_to_ir_preserves_music_modifiers(self):
        plan = parse_phrase("4/4 time, tempo 108, a tempo")
        ir = phrase_plan_to_ir(plan, "4/4 time, tempo 108, a tempo")
        headers = [sym for sym in ir["symbols"] if sym.get("modifiers", {}).get("measure_header")]
        self.assertEqual(len(headers), 3)
        self.assertEqual(headers[0]["symbol_id"], "music.time.4_4")
        self.assertEqual(headers[1]["modifiers"]["tempo"], 108)
        self.assertEqual(headers[2]["modifiers"]["label"], "a tempo")

    def test_phrase_to_ir_links_repeat_start_to_next_closing_repeat(self):
        plan = parse_phrase("begin repeat, step forward, end repeat")
        ir = phrase_plan_to_ir(plan, "begin repeat, step forward, end repeat")
        repeat_start = ir["symbols"][0]
        repeat_end = ir["symbols"][2]
        self.assertEqual(repeat_start["symbol_id"], "repeat.start")
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], repeat_end["symbol_id"])
        self.assertEqual(repeat_end["timing"]["beat"], 2.0)

    def test_phrase_to_ir_links_repeat_spans_across_multiple_clauses_and_measures(self):
        plan = parse_phrase("begin repeat, hold step forward, hold step right, end repeat")
        ir = phrase_plan_to_ir(plan, "begin repeat, hold step forward, hold step right, end repeat")
        repeat_start = next(sym for sym in ir["symbols"] if sym["symbol_id"] == "repeat.start")
        repeat_end = next(sym for sym in ir["symbols"] if sym["symbol_id"] == "repeat.end")
        self.assertEqual(repeat_start["modifiers"]["repeat_span_to"], "repeat.end")
        self.assertEqual(repeat_end["timing"]["measure"], 2)
        self.assertEqual(repeat_end["timing"]["beat"], 1.0)

    def test_phrase_to_ir_auto_attaches_quality_and_timing_symbols(self):
        plan = parse_phrase("step forward sudden accented")
        ir = phrase_plan_to_ir(plan, "step forward sudden accented")
        self.assertEqual(ir["symbols"][1]["modifiers"]["attach_to"], "support.step")
        self.assertEqual(ir["symbols"][2]["modifiers"]["attach_to"], "support.step")

    def test_phrase_parser_supports_parallel_while_clauses(self):
        plan = parse_phrase("left hand gesture high while right foot step forward, turn left")
        self.assertEqual(len(plan["steps"]), 3)
        self.assertEqual(plan["steps"][0]["symbol_id"], "gesture.arm")
        self.assertEqual(plan["steps"][1]["symbol_id"], "support.step")
        self.assertEqual(plan["steps"][0]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][1]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][2]["symbol_id"], "turn.pivot")
        self.assertEqual(plan["steps"][2]["timing"]["beat"], 2.0)

    def test_phrase_parser_supports_parallel_together_language(self):
        plan = parse_phrase("left hand gesture high together right foot step forward, turn left")
        primary_steps = [step for step in plan["steps"] if step["symbol_id"] in {"gesture.arm", "support.step", "turn.pivot"}]
        self.assertEqual(len(primary_steps), 3)
        self.assertEqual(primary_steps[0]["timing"]["beat"], 1.0)
        self.assertEqual(primary_steps[1]["timing"]["beat"], 1.0)
        self.assertEqual(primary_steps[2]["timing"]["beat"], 2.0)

    def test_phrase_parser_supports_parallel_alongside_language(self):
        plan = parse_phrase("left hand gesture high alongside right foot step forward, turn left")
        primary_steps = [step for step in plan["steps"] if step["symbol_id"] in {"gesture.arm", "support.step", "turn.pivot"}]
        self.assertEqual(len(primary_steps), 3)
        self.assertEqual(primary_steps[0]["timing"]["beat"], 1.0)
        self.assertEqual(primary_steps[1]["timing"]["beat"], 1.0)
        self.assertEqual(primary_steps[2]["timing"]["beat"], 2.0)

    def test_phrase_parser_supports_before_and_after_connectors(self):
        after_plan = parse_phrase("turn left after step forward")
        after_primary = [step["symbol_id"] for step in after_plan["steps"] if step["symbol_id"] in {"support.step", "turn.pivot"}]
        self.assertEqual(after_primary, ["support.step", "turn.pivot"])
        before_plan = parse_phrase("step forward before turn left")
        before_primary = [step["symbol_id"] for step in before_plan["steps"] if step["symbol_id"] in {"support.step", "turn.pivot"}]
        self.assertEqual(before_primary, ["support.step", "turn.pivot"])
        self.assertEqual(before_plan["steps"][0]["timing"]["beat"], 1.0)
        self.assertEqual(before_plan["steps"][1]["timing"]["beat"], 2.0)

    def test_phrase_parser_supports_followed_by_connector(self):
        plan = parse_phrase("step forward followed by turn left")
        primary = [step["symbol_id"] for step in plan["steps"] if step["symbol_id"] in {"support.step", "turn.pivot"}]
        self.assertEqual(primary, ["support.step", "turn.pivot"])
        self.assertEqual(plan["steps"][0]["timing"]["beat"], 1.0)
        self.assertEqual(plan["steps"][1]["timing"]["beat"], 2.0)

    def test_phrase_to_ir_auto_attaches_parallel_companions_to_same_body_motion(self):
        plan = parse_phrase("left hand gesture sudden while right foot step forward")
        ir = phrase_plan_to_ir(plan, "left hand gesture sudden while right foot step forward")
        gesture = ir["symbols"][0]
        quality = ir["symbols"][1]
        step = ir["symbols"][2]
        self.assertEqual(gesture["symbol_id"], "gesture.arm")
        self.assertEqual(quality["symbol_id"], "quality.sudden")
        self.assertEqual(step["symbol_id"], "support.step")
        self.assertEqual(quality["modifiers"]["attach_to"], "gesture.arm")

    def test_phrase_to_ir_prefers_covering_motion_for_auto_attachment(self):
        plan = {
            "version": "0.1.0",
            "steps": [
                {
                    "action": "step",
                    "symbol_id": "support.step",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1.0, "duration_beats": 1.0},
                    "modifiers": {},
                    "source_text": "step forward",
                },
                {
                    "action": "jump",
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3.0, "duration_beats": 2.0},
                    "modifiers": {},
                    "source_text": "jump backward hold",
                },
                {
                    "action": "quality",
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3.0, "duration_beats": 1.0},
                    "modifiers": {},
                    "source_text": "sudden",
                },
            ],
        }
        ir = phrase_plan_to_ir(plan, "step forward, hold jump backward sudden")
        self.assertEqual(ir["symbols"][2]["modifiers"]["attach_to"], "jump.small")

    def test_phrase_parser_rolls_over_into_next_measure(self):
        plan = parse_phrase("hold step forward, hold step right, turn left")
        primary_steps = [step for step in plan["steps"] if step["symbol_id"].startswith(("support.", "turn."))]
        self.assertEqual(len(primary_steps), 3)
        self.assertEqual(primary_steps[0]["timing"]["measure"], 1)
        self.assertEqual(primary_steps[1]["timing"]["measure"], 1)
        self.assertEqual(primary_steps[1]["timing"]["beat"], 3.0)
        self.assertEqual(primary_steps[2]["timing"]["measure"], 2)
        self.assertEqual(primary_steps[2]["timing"]["beat"], 1.0)

    def test_phrase_parser_rolls_over_using_active_time_signature(self):
        plan = parse_phrase("3/4 time, hold step forward, step right, turn left")
        primary_steps = [step for step in plan["steps"] if step["symbol_id"].startswith("support.")]
        self.assertEqual(primary_steps[0]["timing"]["measure"], 1)
        self.assertEqual(primary_steps[0]["timing"]["beat"], 1.0)
        self.assertEqual(primary_steps[1]["timing"]["measure"], 1)
        self.assertEqual(primary_steps[1]["timing"]["beat"], 3.0)
        turn = next(step for step in plan["steps"] if step["symbol_id"] == "turn.pivot")
        self.assertEqual(turn["timing"]["measure"], 2)
        self.assertEqual(turn["timing"]["beat"], 1.0)

    def test_phrase_rollover_does_not_trigger_cross_measure_overlap(self):
        plan = parse_phrase("hold step forward, hold step right, turn left")
        ir = phrase_plan_to_ir(plan, "hold step forward, hold step right, turn left")
        result = validate_ir(ir)
        codes = {issue["code"] for issue in result["issues"]}
        self.assertNotIn("TIMING_OVERLAP", codes)

    def test_phrase_parser_alternates_default_limbs_for_unqualified_sequences(self):
        plan = parse_phrase("step forward, step backward, glide left, brush right")
        self.assertEqual(plan["steps"][0]["body_part"], "right_leg")
        self.assertEqual(plan["steps"][1]["body_part"], "left_leg")
        self.assertEqual(plan["steps"][2]["body_part"], "right_arm")
        self.assertEqual(plan["steps"][3]["body_part"], "left_arm")

    def test_phrase_parser_preserves_body_direction_and_level_for_short_continuations(self):
        plan = parse_phrase("left hand gesture high backward, gesture, step low right, step")
        primary = [step for step in plan["steps"] if step["symbol_id"] in {"gesture.arm", "support.step"}]
        self.assertEqual(primary[0]["body_part"], "left_arm")
        self.assertEqual(primary[1]["body_part"], "left_arm")
        self.assertEqual(primary[1]["direction"], "backward")
        self.assertEqual(primary[1]["level"], "high")
        self.assertEqual(primary[2]["body_part"], "right_leg")
        self.assertEqual(primary[3]["body_part"], "right_leg")
        self.assertEqual(primary[3]["direction"], "right")
        self.assertEqual(primary[3]["level"], "low")

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
        self.assertIn('class="symbol-block', svg)
        self.assertIn("Laban staff engraving preview", svg)

    def test_renderer_draws_duration_aware_layout(self):
        ir = {
            "metadata": {"title": "Duration Layout", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 0.5},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn("level-middle-fill", svg)
        self.assertIn('data-symbol-id="support.step.forward"', svg)
        self.assertIn('class="adjacent-mark"', svg)

    def test_renderer_marks_cross_measure_continuations(self):
        ir = {
            "metadata": {"title": "Continuation Layout", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 3},
                    "modifiers": {},
                }
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="continuation-marker" data-boundary-measure="2"', svg)
        self.assertIn(' 414.0"', svg)

    def test_renderer_wraps_long_scores_into_multiple_staff_systems(self):
        symbols = []
        for measure in range(1, 7):
            symbols.append(
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg" if measure % 2 else "right_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": measure, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                }
            )
        ir = {
            "metadata": {"title": "System Layout", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": symbols,
        }
        svg = render_svg(ir)
        self.assertIn('class="staff-system" data-system="1" data-measures="1-4"', svg)
        self.assertIn('class="staff-system" data-system="2" data-measures="5-6"', svg)
        self.assertGreaterEqual(svg.count(">Support</text>"), 2)
        self.assertIn(">M5</text>", svg)

    def test_renderer_supports_manual_modifier_features(self):
        ir = {
            "metadata": {"title": "Manual Features", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "turn.spin",
                    "body_part": "torso",
                    "direction": "right",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {"degree": 180, "level_fill_top": "high", "level_fill_bottom": "low", "line_style": "double"},
                },
                {
                    "symbol_id": "path.curved",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"arrowheads": {"head": "single", "tail": "open"}, "whitespace": True},
                },
                {
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "high",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1.5},
                    "modifiers": {"spring_jump": {"takeoff": ["left"], "landing": ["right"]}},
                },
                {
                    "symbol_id": "body.torso",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"surface_marks": ["left", "right"]},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="degree-badge"', svg)
        self.assertIn('data-symbol-id="path.curved"', svg)
        self.assertIn("polygon", svg)
        self.assertIn('stroke-width="2"', svg)

    def test_renderer_uses_specialized_geometry_for_official_families(self):
        ir = {
            "metadata": {"title": "Specialized Families", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.generic",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.time.3_4",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "separator.staff.flipped",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-pin"', svg)
        self.assertIn('class="specialized-repeat"', svg)
        self.assertIn('class="specialized-music"', svg)
        self.assertIn('class="specialized-separator"', svg)

    def test_renderer_supports_stretch_rotation_and_new_specialized_families(self):
        ir = {
            "metadata": {"title": "Advanced Families", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "turn.spin",
                    "body_part": "torso",
                    "direction": "right",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1.5},
                    "modifiers": {"stretch": 1.5, "rotation": 45},
                },
                {
                    "symbol_id": "motif.arc",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "high",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"rotation": -30},
                },
                {
                    "symbol_id": "surface.brush",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "space.transition",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"stretch": 1.8},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-turn"', svg)
        self.assertIn('class="specialized-motif"', svg)
        self.assertIn('class="specialized-surface"', svg)
        self.assertIn('class="specialized-space"', svg)
        self.assertIn('rotate(45.0', svg)
        self.assertIn('class="specialized-turn"', svg)
        self.assertIn('data-variant="spin"', svg)
        self.assertIn('data-stretch-mode="cap-body-cap"', svg)

    def test_renderer_uses_variant_geometry_for_hold_pin_and_stretched_jump(self):
        ir = {
            "metadata": {"title": "Variant Geometry", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"pin_length": 1.2},
                },
                {
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1.5},
                    "modifiers": {"stretch": 1.6},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-pin" data-variant="hold"', svg)
        self.assertIn('class="specialized-jump" data-variant="stretched"', svg)
        self.assertIn('stroke-dasharray="4 3"', svg)

    def test_renderer_uses_cap_body_cap_for_stretchable_space_path_and_separator(self):
        ir = {
            "metadata": {"title": "Stretch Composition", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "path.straight",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"stretch": 1.8},
                },
                {
                    "symbol_id": "space.transition",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"stretch": 1.8},
                },
                {
                    "symbol_id": "space.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"stretch": 1.6},
                },
                {
                    "symbol_id": "separator.staff",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"stretch": 1.5},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-path"', svg)
        self.assertIn('data-shape="straight"', svg)
        self.assertIn('data-stretch-mode="cap-body-cap"', svg)
        self.assertIn('class="specialized-space" data-kind="transition" data-stretch-mode="cap-body-cap"', svg)
        self.assertIn('class="specialized-space" data-kind="hold" data-stretch-mode="cap-body-cap"', svg)
        self.assertIn('class="specialized-separator" data-flipped="false" data-stretch-mode="cap-body-cap"', svg)

    def test_renderer_applies_directional_mirroring_to_specialized_families(self):
        ir = {
            "metadata": {"title": "Directional Variants", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "path.curved",
                    "body_part": "torso",
                    "direction": "left",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "motif.rise",
                    "body_part": "left_arm",
                    "direction": "right",
                    "level": "high",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.brush",
                    "body_part": "right_arm",
                    "direction": "diagonal_backward_left",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "turn.spin",
                    "body_part": "torso",
                    "direction": "counterclockwise",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-path"', svg)
        self.assertIn('data-shape="curved"', svg)
        self.assertIn('data-direction="left"', svg)
        self.assertIn('data-mirrored="true"', svg)
        self.assertIn('class="specialized-motif" data-kind="rise" data-direction="right" data-mirrored="false"', svg)
        self.assertIn('class="specialized-surface" data-kind="brush" data-direction="diagonal_backward_left" data-mirrored="true"', svg)
        self.assertIn('class="specialized-turn"', svg)
        self.assertIn('data-variant="spin"', svg)
        self.assertIn('data-direction="counterclockwise"', svg)
        self.assertIn('data-turn-direction="ccw"', svg)

    def test_renderer_supports_variant_specific_official_families(self):
        ir = {
            "metadata": {"title": "Variant Families", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "path.circle",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"stretch": 1.4},
                },
                {
                    "symbol_id": "pin.entry",
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
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"repeat_count": 2},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"label": "rit."},
                },
                {
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.rest.sixteenth",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-shape="circle"', svg)
        self.assertIn('data-repeat-count="2"', svg)
        self.assertIn('data-kind="cadence"', svg)
        self.assertIn('data-mode="double"', svg)
        self.assertIn('data-kind="rest-sixteenth"', svg)
        self.assertIn('data-kind="glide"', svg)

    def test_renderer_refines_jump_turn_path_subclasses_and_music_typography(self):
        ir = {
            "metadata": {"title": "Subclass Geometry", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "path.spiral",
                    "body_part": "torso",
                    "direction": "left",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "turn.pivot",
                    "body_part": "torso",
                    "direction": "clockwise",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "jump.small",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"tempo": 132},
                },
                {
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"label": "a tempo"},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-path"', svg)
        self.assertIn('data-shape="spiral"', svg)
        self.assertIn('data-subclass="spiral"', svg)
        self.assertIn('data-transition-mark="loop-arrow"', svg)
        self.assertIn('class="specialized-turn" data-variant="pivot" data-subclass="pivot"', svg)
        self.assertIn('class="specialized-jump" data-variant="compact" data-subclass="small"', svg)
        self.assertIn('class="specialized-music" data-kind="tempo"', svg)
        self.assertIn('class="music-label"', svg)
        self.assertIn('class="specialized-music" data-kind="cadence"', svg)
        self.assertIn('data-cap-shape="spiral"', svg)

    def test_renderer_supports_whitespace_spring_hook_and_motif_combo_variants(self):
        ir = {
            "metadata": {"title": "Manual Parity Variants", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "space.whitespace",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"stretch": 1.6},
                },
                {
                    "symbol_id": "jump.spring",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "bow.hook",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "separator.hook",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "motif.rise_fall",
                    "body_part": "right_arm",
                    "direction": "left",
                    "level": "high",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-space" data-kind="whitespace"', svg)
        self.assertIn('class="specialized-jump" data-variant="compact" data-subclass="spring"', svg)
        self.assertIn('class="specialized-bow" data-kind="hook"', svg)
        self.assertIn('class="specialized-separator" data-flipped="false" data-mode="hook"', svg)
        self.assertIn('class="specialized-motif" data-kind="rise-fall"', svg)

    def test_renderer_uses_more_official_pin_and_separator_variants(self):
        ir = {
            "metadata": {"title": "Official Variants", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "pin.floorplan_exit",
                    "body_part": "torso",
                    "direction": "right",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "separator.final",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-pin" data-variant="floorplan-exit"', svg)
        self.assertIn('class="specialized-separator" data-flipped="false" data-mode="final"', svg)

    def test_renderer_replaces_more_generic_official_blocks_with_family_native_shapes(self):
        ir = {
            "metadata": {"title": "Native Families", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "bow.horizontal",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "dynamic.accent",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "adlib.vertical",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-bow" data-kind="horizontal"', svg)
        self.assertIn('class="specialized-dynamic" data-kind="accent"', svg)
        self.assertIn('class="specialized-adlib" data-kind="vertical"', svg)

    def test_renderer_distinguishes_repeat_and_motif_variant_kinds(self):
        ir = {
            "metadata": {"title": "Variant Kinds", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"repeat_count": 2},
                },
                {
                    "symbol_id": "motif.rise",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "motif.fall",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="specialized-repeat" data-kind="start"', svg)
        self.assertIn('class="specialized-repeat" data-kind="end"', svg)
        self.assertIn('class="specialized-motif" data-kind="rise"', svg)
        self.assertIn('class="specialized-motif" data-kind="fall"', svg)

    def test_renderer_supports_attachment_and_measure_header_rules(self):
        ir = {
            "metadata": {"title": "Combo Rules", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
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
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
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
                    "symbol_id": "music.cadence.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True},
                },
                {
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"repeat_count": 2, "attach_side": "left"},
                },
                {
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('class="measure-header"', svg)
        self.assertIn('class="measure-header-band"', svg)
        self.assertIn('class="repeat-separator-bridge"', svg)
        self.assertIn('class="repeat-span"', svg)

    def test_measure_headers_are_placed_per_measure_band(self):
        ir = {
            "metadata": {"title": "Measure Headers", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 108},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-symbol-id="music.time.4_4"', svg)
        self.assertIn('data-symbol-id="music.tempo.mark"', svg)
        self.assertIn('class="measure-header-band" data-measure="1"', svg)
        self.assertIn('class="measure-header-band" data-measure="2"', svg)
        self.assertIn('y="136.0"', svg)
        self.assertIn('y="424.0"', svg)
        self.assertIn('height="30.0"', svg)

    def test_measure_boundary_separator_spans_full_measure(self):
        ir = {
            "metadata": {"title": "Measure Boundary", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "separator.final",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                }
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-symbol-id="separator.final"', svg)
        self.assertIn('y="416.0"', svg)
        self.assertIn('height="284.0"', svg)

    def test_header_gutter_shifts_staff_layout(self):
        ir = {
            "metadata": {"title": "Header Gutter", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('<rect x="108.0" y="112"', svg)
        self.assertIn('<line x1="144.0" y1="112"', svg)

    def test_measure_header_spacing_expands_for_longer_text(self):
        ir = {
            "metadata": {"title": "Header Widths", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 144},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="measure-header-band" data-measure="1"><rect x="63.0" y="130.0" width="56.0"', svg)
        self.assertIn('class="measure-header-band" data-measure="2"><rect x="58.0" y="418.0" width="61.0"', svg)
        self.assertIn('data-symbol-id="music.tempo.mark"><rect x="64.0" y="424.0" width="49.0"', svg)

    def test_measure_width_expands_for_symbol_complexity(self):
        ir = {
            "metadata": {"title": "Measure Width", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        svg = render_svg(ir)
        measure_tops = re.findall(r'<line x1="18\.0" y1="(126\.0|414\.0)" x2="([0-9.]+)" y2="\1" stroke="#94a3b8"', svg)
        self.assertEqual(len(measure_tops), 2)
        top_widths = {float(y): float(x2) for y, x2 in measure_tops}
        self.assertGreater(top_widths[414.0], top_widths[126.0])
        self.assertLess(top_widths[126.0], 1660.0)

    def test_deep_attachment_and_annotation_stacks_expand_measure_gaps(self):
        ir = {
            "metadata": {"title": "Vertical Gap", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "level.high",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "high",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 2},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "right_leg",
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
        svg = render_svg(ir)
        svg_height = int(re.search(r'height="(\d+)" viewBox=', svg).group(1))
        measure_2_y = float(re.search(r'<text x="[0-9.\\-]+" y="([0-9.]+)" text-anchor="end" font-size="10" fill="#64748b">M2</text>', svg).group(1))
        self.assertGreater(svg_height, 742)
        self.assertGreater(measure_2_y, 430.0)

    def test_deep_stack_vertical_zoning_separates_repeat_quality_and_timing_layers(self):
        ir = {
            "metadata": {"title": "Vertical Zoning", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 2},
                    "modifiers": {},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 2},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "separator.double",
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
                    "timing": {"measure": 2, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        repeat_y = float(re.search(r'data-symbol-id="repeat\.start">.*?<text x="[^"]+" y="([0-9.]+)" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">repeat\.start</text>', svg, re.S).group(1))
        quality_y = float(re.search(r'data-symbol-id="quality\.sudden">.*?<text x="[^"]+" y="([0-9.]+)" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">quality\.sudden</text>', svg, re.S).group(1))
        timing_y = float(re.search(r'data-symbol-id="timing\.hold">.*?<text x="[^"]+" y="([0-9.]+)" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">timing\.hold</text>', svg, re.S).group(1))
        self.assertLess(repeat_y, quality_y)
        self.assertLess(quality_y, timing_y)

    def test_attachment_anchors_follow_relative_layout(self):
        ir = {
            "metadata": {"title": "Anchor Routing", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('M 505.0 162.0', svg)
        self.assertIn('M 1285.0 162.0', svg)
        self.assertIn('332.0 162.0', svg)

    def test_measure_boundary_special_columns_get_slot_offsets(self):
        ir = {
            "metadata": {"title": "Boundary Offsets", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-symbol-id="repeat.start"', svg)
        self.assertIn('data-symbol-id="separator.double"', svg)
        self.assertIn('data-symbol-id="music.rest.quarter"', svg)
        self.assertIn('<text x="1042.0" y="204.0" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">repeat.start</text>', svg)
        self.assertIn('<g class="specialized-separator" data-flipped="false" data-mode="double">', svg)
        self.assertIn('<text x="1414.0" y="424.0" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">separator.double</text>', svg)
        self.assertIn('<text x="1212.0" y="204.0" text-anchor="middle" class="symbol-id" font-size="8" fill="#4b5563">music.rest.quarter</text>', svg)

    def test_measure_priority_layers_stack_annotation_columns(self):
        ir = {
            "metadata": {"title": "Priority Layers", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
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
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-symbol-id="repeat.start"', svg)
        self.assertIn('data-symbol-id="quality.sudden"', svg)
        self.assertIn('data-symbol-id="timing.hold"', svg)
        self.assertIn('<rect x="1025.0" y="204.0" width="34.0" height="60.0"', svg)
        self.assertIn('<rect x="1441.0" y="200.0" width="34.0" height="60.0"', svg)
        self.assertIn('<rect x="1545.0" y="218.0" width="34.0" height="60.0"', svg)

    def test_repeat_span_moves_left_of_annotation_columns(self):
        ir = {
            "metadata": {"title": "Repeat Span Clearance", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "quality.sudden",
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
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="repeat-span"', svg)
        self.assertIn('d="M 1024.0 130.0 L 1024.0 410.0', svg)

    def test_attachment_lines_route_around_annotation_families(self):
        ir = {
            "metadata": {"title": "Attachment Clearance", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
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
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('d="M 1285.0 234.0 L 1285.0 276.0 L 332.0 276.0 L 332.0 234.0"', svg)

    def test_multiple_attachment_lines_use_distinct_routing_tracks(self):
        ir = {
            "metadata": {"title": "Attachment Tracks", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
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
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('d="M 1285.0 234.0 L 1285.0 276.0 L 332.0 276.0 L 332.0 234.0"', svg)
        self.assertIn('L 332.0 276.0 L 332.0 234.0"', svg)
        self.assertIn('L 332.0 288.0 L 332.0 234.0"', svg)

    def test_attachment_tracks_are_reused_when_ranges_do_not_overlap(self):
        ir = {
            "metadata": {"title": "Attachment Track Reuse", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
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
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.brush",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.backward"},
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
                    "symbol_id": "quality.smooth",
                    "body_part": "right_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('d="M 1285.0 234.0 L 1285.0 276.0 L 332.0 276.0 L 332.0 234.0"', svg)
        self.assertIn('d="M 1285.0 378.0 L 1285.0 420.0 L 332.0 420.0 L 332.0 378.0"', svg)

    def test_repeat_bridge_and_attachment_share_routing_lane_pool(self):
        ir = {
            "metadata": {"title": "Shared Lane Pool", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "separator.double",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
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
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="repeat-separator-bridge"', svg)
        self.assertIn('d="M 1042.0 196.0 L 1414.0 196.0"', svg)
        self.assertIn('d="M 1285.0 234.0 L 1285.0 276.0 L 332.0 276.0 L 332.0 234.0"', svg)

    def test_repeat_span_reuses_outer_track_when_bridge_does_not_cross_it(self):
        ir = {
            "metadata": {"title": "Span Lane Pool", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "separator.double",
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
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="repeat-separator-bridge"', svg)
        self.assertIn('class="repeat-span"', svg)
        self.assertIn('d="M 1010.0 130.0 L 1010.0 410.0', svg)

    def test_attachment_yields_when_bridge_and_span_share_outer_track(self):
        ir = {
            "metadata": {"title": "Routing Priority", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "separator.double",
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
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
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
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="repeat-separator-bridge"', svg)
        self.assertIn('class="repeat-span"', svg)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('d="M 1285.0 234.0 L 1285.0 288.0 L 332.0 288.0 L 332.0 234.0"', svg)

    def test_cross_beat_attachment_uses_dogleg_routing_shape(self):
        ir = {
            "metadata": {"title": "Dogleg Attachment", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
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
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('d="M 1285.0 306.0 L 1285.0 276.0 L 350.0 276.0 L 350.0 150.0 L 332.0 150.0 L 332.0 162.0"', svg)

    def test_attach_side_left_changes_dogleg_target_approach_side(self):
        ir = {
            "metadata": {"title": "Left Side Dogleg", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward", "attach_side": "left"},
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
                    "symbol_id": "quality.sudden",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-route="dogleg"', svg)
        self.assertIn('L 314.0 150.0 L 332.0 150.0', svg)

    def test_pin_cross_beat_attachment_uses_multi_elbow_route(self):
        ir = {
            "metadata": {"title": "Pin Multi Elbow", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "pin.hold",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
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
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('data-route="multi-elbow"', svg)

    def test_attachment_clearance_avoids_non_annotation_symbol_bounding_boxes(self):
        ir = {
            "metadata": {"title": "BBox Clearance", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('data-route="clearance"', svg)
        self.assertNotIn('data-route="curve"', svg)

    def test_routing_tracks_avoid_measure_header_gutter_corridors(self):
        header_layout = {1: {"count": 3.0, "max_text_width": 52.0}}
        staff_left = 28.0 + _header_gutter_width(header_layout)
        corridors = _measure_header_corridors(header_layout, 126.0, staff_left)
        routed_lines: list[dict] = []
        routed_y, track = _reserve_routing_track(
            1,
            staff_left - 10.0,
            staff_left + 48.0,
            180.0,
            180.0,
            180.0,
            routed_lines,
            "attachment",
            header_corridors=corridors,
        )
        self.assertGreater(track, 0)
        self.assertGreater(routed_y, corridors[1]["bottom"])

    def test_routing_track_reuse_considers_line_geometry_width(self):
        routed_lines = [
            {
                "measure": 1,
                "left": 240.0,
                "right": 780.0,
                "y": 276.0,
                "track": 0,
                "axis": "horizontal",
                "kind": "attachment",
                "top": 276.0,
                "bottom": 276.0,
                "geometry_width": 540.0,
            }
        ]
        routed_y, track = _reserve_routing_track(
            1,
            784.0,
            930.0,
            276.0,
            276.0,
            276.0,
            routed_lines,
            "attachment",
        )
        self.assertGreater(track, 0)
        self.assertGreater(routed_y, 276.0)

    def test_many_external_attachments_bundle_before_splitting_to_target(self):
        ir = {
            "metadata": {"title": "Attachment Bundle", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "music.rest.quarter",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "pin.hold",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "support.step.forward"},
                },
                {
                    "symbol_id": "support.step.backward",
                    "body_part": "right_leg",
                    "direction": "backward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertEqual(svg.count('data-route="bundle-clearance"'), 3)

    def test_attachment_polyline_simplification_removes_redundant_elbows(self):
        path = _render_attachment_polyline(
            "clearance",
            [
                (100.0, 200.0),
                (100.0, 200.0),
                (100.0, 240.0),
                (140.0, 240.0),
                (180.0, 240.0),
                (180.0, 200.0),
            ],
        )
        self.assertIn('data-route="clearance"', path)
        self.assertNotIn('L 100.0 200.0 L 100.0 200.0', path)
        self.assertIn('d="M 100.0 200.0 L 100.0 240.0 L 180.0 240.0 L 180.0 200.0"', path)

    def test_renderer_matches_golden_official_family_snapshot(self):
        ir = json.loads((ROOT / "fixtures" / "golden_official_family_score.json").read_text(encoding="utf-8"))
        expected = (ROOT / "fixtures" / "golden_official_family_score.svg").read_text(encoding="utf-8").strip()
        self.assertEqual(render_svg(ir).strip(), expected)

    def test_renderer_combines_headers_repeats_attachments_quality_timing_and_stretchables(self):
        ir = {
            "metadata": {"title": "Combined Engraving Fixture", "ir_version": "0.1.0", "schema_version": "0.1.0"},
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
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"measure_header": True, "tempo": 108},
                },
                {
                    "symbol_id": "repeat.start",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"repeat_span_to": "repeat.end"},
                },
                {
                    "symbol_id": "path.spiral",
                    "body_part": "torso",
                    "direction": "right",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {"line_style": "double"},
                },
                {
                    "symbol_id": "surface.glide",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "path.spiral"},
                },
                {
                    "symbol_id": "quality.sustained",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                    "modifiers": {"attach_to": "surface.glide"},
                },
                {
                    "symbol_id": "timing.hold",
                    "body_part": "right_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 2, "duration_beats": 2},
                    "modifiers": {"attach_to": "surface.glide"},
                },
                {
                    "symbol_id": "space.whitespace",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                    "modifiers": {"stretch": 1.8},
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
                    "symbol_id": "repeat.end",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 3, "duration_beats": 1},
                    "modifiers": {"repeat_count": 2},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('class="measure-header"', svg)
        self.assertIn('class="repeat-span"', svg)
        self.assertIn('class="attachment-line"', svg)
        self.assertIn('data-symbol-id="quality.sustained"', svg)
        self.assertIn('data-symbol-id="timing.hold"', svg)
        self.assertIn('data-kind="whitespace"', svg)
        self.assertIn('data-stretch-mode="cap-body-cap"', svg)


if __name__ == "__main__":
    unittest.main()
