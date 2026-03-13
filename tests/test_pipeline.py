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
                    "symbol_id": "music.tempo.mark",
                    "body_part": "torso",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 4, "duration_beats": 1},
                    "modifiers": {"tempo": 96},
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
                    "symbol_id": "surface.glide",
                    "body_part": "left_arm",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 2, "beat": 2, "duration_beats": 1},
                    "modifiers": {},
                },
            ],
        }
        svg = render_svg(ir)
        self.assertIn('data-shape="circle"', svg)
        self.assertIn('data-repeat-count="2"', svg)
        self.assertIn('data-kind="tempo"', svg)
        self.assertIn('data-mode="double"', svg)
        self.assertIn('data-kind="glide"', svg)

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
        self.assertIn('M 505.0 162.0 C 418.5 162.0, 418.5 162.0, 332.0 162.0', svg)
        self.assertIn('M 1285.0 162.0 C 808.5 162.0, 808.5 162.0, 332.0 162.0', svg)

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
        self.assertIn('<rect x="88.0" y="218.0" width="36.0" height="60.0"', svg)

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
        self.assertIn('d="M 74.0 130.0 L 74.0 410.0', svg)

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
        self.assertIn('d="M 1181.0 234.0 L 1181.0 288.0 L 332.0 288.0 L 332.0 234.0"', svg)

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
        self.assertIn('d="M 1285.0 234.0 L 1285.0 288.0 L 332.0 288.0 L 332.0 234.0"', svg)

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


if __name__ == "__main__":
    unittest.main()
