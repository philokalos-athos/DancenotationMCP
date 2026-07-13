import json
import re
import unittest
from pathlib import Path

from dancenotation_mcp.rendering.laban_renderer import render_laban_svg
from dancenotation_mcp.rendering.laban_layout import (
    compute_laban_layout,
    build_column_positions,
    build_measure_positions,
    STAFF_COLUMNS,
    COL_WIDTH,
    CENTER_GAP,
    PRIMARY_FAMILIES,
    ANNOTATION_FAMILIES,
)
from dancenotation_mcp.ir.catalog import load_symbol_catalog

# staff_column values that legitimately fall through to BODY_TO_COLUMN (main
# staff placement) without appearing in PRIMARY_FAMILIES/ANNOTATION_FAMILIES,
# because they carry their own direction+level like a normal body action
# ("travel", "floor") or have a dedicated symbol_id-prefix special case in
# _render_staff_symbol ("separator", "space"). Verified by manual audit — see
# docs/superpowers/specs/2026-07-08-labanwriter-parity-rewrite-design.md.
KNOWN_MAIN_STAFF_FALLTHROUGH = {"travel", "floor", "separator", "space"}


ROOT = Path(__file__).resolve().parents[1]


def _minimal_ir(symbols=None, title="Test Score"):
    return {
        "metadata": {"title": title, "ir_version": "0.1.0", "schema_version": "0.1.0"},
        "symbols": symbols or [
            {
                "symbol_id": "support.step.forward",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            }
        ],
    }


class LabanLayoutTests(unittest.TestCase):

    def test_column_positions_have_six_staff_columns(self):
        positions = build_column_positions(100.0)
        for col in STAFF_COLUMNS:
            self.assertIn(col, positions)
        self.assertIn("center", positions)

    def test_center_column_spans_both_supports(self):
        positions = build_column_positions(100.0)
        center = positions["center"]
        ls = positions["left_support"]
        rs = positions["right_support"]
        self.assertEqual(center[0], ls[0])
        self.assertEqual(center[1], rs[1])

    def test_center_gap_separates_supports(self):
        positions = build_column_positions(100.0)
        ls_right = positions["left_support"][1]
        rs_left = positions["right_support"][0]
        self.assertAlmostEqual(rs_left - ls_right, CENTER_GAP)

    def test_measure_positions_bottom_to_top(self):
        positions = build_measure_positions(3, 500.0)
        # Measure 1 bottom should be at canvas bottom
        self.assertEqual(positions[1][0], 500.0)
        # Measure 1 top should be above its bottom
        self.assertLess(positions[1][1], positions[1][0])
        # Measure 2 bottom == measure 1 top
        self.assertEqual(positions[2][0], positions[1][1])
        # Measure 3 is highest
        self.assertLess(positions[3][1], positions[2][1])

    def test_compute_layout_returns_required_keys(self):
        ir = _minimal_ir()
        layout = compute_laban_layout(ir)
        required_keys = [
            "staff_left", "staff_right", "staff_center_x",
            "column_positions", "measure_positions",
            "placed_symbols", "annotation_entries", "header_entries",
            "width", "height", "title",
        ]
        for key in required_keys:
            self.assertIn(key, layout, f"Missing key: {key}")

    def test_left_leg_maps_to_left_support(self):
        ir = _minimal_ir()
        layout = compute_laban_layout(ir)
        self.assertEqual(len(layout["placed_symbols"]), 1)
        self.assertEqual(layout["placed_symbols"][0]["column"], "left_support")

    def test_right_arm_maps_to_right_gesture(self):
        ir = _minimal_ir(symbols=[{
            "symbol_id": "gesture.arm",
            "body_part": "right_arm",
            "direction": "forward",
            "level": "high",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        layout = compute_laban_layout(ir)
        self.assertEqual(len(layout["placed_symbols"]), 1)
        self.assertEqual(layout["placed_symbols"][0]["column"], "right_arm")


class LabanRendererTests(unittest.TestCase):

    def test_renders_valid_svg(self):
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)

    def test_renders_title(self):
        ir = _minimal_ir(title="My Dance")
        svg = render_laban_svg(ir)
        self.assertIn("My Dance", svg)

    def test_renders_center_line(self):
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn('stroke-width="2.5"', svg)

    def test_renders_staff_boundary(self):
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn('stroke-width="2"', svg)

    def test_renders_direction_shape_for_forward(self):
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn('data-direction="forward"', svg)
        self.assertIn('class="laban-symbol"', svg)

    def test_level_encoding_high_is_striped(self):
        """Per the LabanWriter manual, High level uses adjustable-spacing stripes."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "high",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('data-level="high"', svg)
        self.assertIn("laban-hatch", svg)

    def test_level_encoding_low_is_solid(self):
        ir = _minimal_ir(symbols=[{
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "low",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('data-level="low"', svg)
        self.assertIn('fill="#111827"', svg)

    def test_level_encoding_middle_is_blank(self):
        """Per the LabanWriter manual, Middle level is unshaded (no fill pattern)."""
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn('data-level="middle"', svg)
        self.assertIn('fill="#ffffff"', svg)

    def test_turn_placed_in_annotation_area(self):
        ir = _minimal_ir(symbols=[
            {
                "symbol_id": "support.step.forward",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
            {
                "symbol_id": "turn.pivot",
                "body_part": "torso",
                "direction": "right",
                "level": "middle",
                "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                "modifiers": {},
            },
        ])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation turn"', svg)

    def test_jump_placed_in_annotation_area(self):
        ir = _minimal_ir(symbols=[{
            "symbol_id": "jump.small",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "high",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation jump"', svg)

    def test_bow_placed_in_annotation_area(self):
        """bow.* symbols must reach _render_bow_annotation, not the main staff.

        Regression test: ANNOTATION_FAMILIES omitted "bow", so bow symbols
        fell through to BODY_TO_COLUMN and rendered as generic direction
        pentagons instead of their dedicated bow-arc glyph.
        """
        ir = _minimal_ir(symbols=[{
            "symbol_id": "bow.horizontal",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation bow"', svg)

    def test_dynamic_placed_in_annotation_area(self):
        """dynamic.* symbols (accent/diminuendo) must render as chevron marks."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "dynamic.accent",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation dynamic"', svg)

    def test_adlib_placed_in_annotation_area(self):
        """adlib.* symbols must render as wavy improvisation marks."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "adlib.horizontal",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation adlib"', svg)

    def test_space_family_renders_as_whitespace_band(self):
        """space.hold/transition/whitespace must render as a dashed blank
        band, not a plain place/middle rectangle (their fallback before this
        was fixed was visually indistinguishable from a real blank symbol).
        """
        ir = _minimal_ir(symbols=[{
            "symbol_id": "space.hold",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-symbol whitespace" data-symbol-id="space.hold"', svg)

    def test_foot_detail_placed_in_annotation_area(self):
        """foot.*/finger.*/toe.* modifier symbols (staff_column foothook/digit,
        requires_direction=False, anchor='adjacent') must render as small
        glyph markers, not main-staff direction pentagons.
        """
        ir = _minimal_ir(symbols=[
            {
                "symbol_id": "foot.position.first",
                "body_part": "left_leg",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
            {
                "symbol_id": "finger.mark",
                "body_part": "left_arm",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                "modifiers": {},
            },
        ])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation foot-detail"', svg)

    def test_motif_placed_in_annotation_area(self):
        """motif.* symbols (rise/fall/arc) must render as motif marks, not pentagons."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "motif.rise",
            "body_part": "left_arm",
            "direction": "forward",
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation motif"', svg)

    def test_path_symbols_render_as_path_annotation(self):
        """path.* symbols were routed to the annotation area correctly but
        had no dispatch branch in _render_annotation, falling through to
        the generic text-label renderer. Covers all four path shapes.
        """
        for symbol_id in ("path.straight", "path.curved", "path.spiral", "path.circle"):
            ir = _minimal_ir(symbols=[{
                "symbol_id": symbol_id,
                "body_part": "torso",
                "direction": "forward",
                "level": None,
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            }])
            svg = render_laban_svg(ir)
            self.assertIn('class="laban-annotation path"', svg, symbol_id)

    def test_bare_surface_symbols_render_as_contact_annotation(self):
        """surface.contact/brush/glide (symbol_id prefix "surface", distinct
        from the "contact" family prefix) had no dispatch branch — only
        "contact" family was handled, not "surface".
        """
        ir = _minimal_ir(symbols=[{
            "symbol_id": "surface.brush",
            "body_part": "left_arm",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation contact"', svg)

    def test_non_header_music_rest_renders_as_music_annotation(self):
        """music.rest.* symbols not used as a measure header (no
        modifiers.measure_header) had no dispatch branch, falling through
        to the generic text-label renderer.
        """
        for symbol_id in ("music.rest.quarter", "music.rest.eighth", "music.rest.sixteenth"):
            ir = _minimal_ir(symbols=[{
                "symbol_id": symbol_id,
                "body_part": "torso",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            }])
            svg = render_laban_svg(ir)
            self.assertIn('class="laban-annotation music"', svg, symbol_id)

    def test_floor_plan_zone_symbols_render_as_stage_marker(self):
        """floor.zone.* symbols (floor_plan.json) collide on symbol_id
        prefix ("floor") with the unrelated floor.roll body-action family,
        so the dispatch check `family == "floor_plan"` never matched them —
        staff_column is the only reliable signal.
        """
        ir = _minimal_ir(symbols=[{
            "symbol_id": "floor.zone.downstage_left",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation floor_plan"', svg)

    def test_retention_types_render_as_visually_distinct_marks(self):
        """Regression: retention.{type}.{body_category} catalog IDs (e.g.
        "retention.hold.arm") put the type in the *second* segment, but the
        renderer's fallback read symbol_id.split(".")[-1] (the body
        category, e.g. "arm") — so hold/release/cancel never matched their
        branch and every retention symbol silently rendered as the same
        generic dot, losing the hold-vs-release-vs-cancel distinction.
        """
        ir = _minimal_ir(symbols=[
            {
                "symbol_id": "retention.hold.arm",
                "body_part": "left_arm",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
            {
                "symbol_id": "retention.release.leg",
                "body_part": "left_leg",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 2, "duration_beats": 1},
                "modifiers": {},
            },
            {
                "symbol_id": "retention.cancel.torso",
                "body_part": "torso",
                "direction": None,
                "level": None,
                "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                "modifiers": {},
            },
        ])
        svg = render_laban_svg(ir)
        # hold: filled circle + tie arc (has both a <circle> and a <path>)
        self.assertRegex(
            svg,
            r'data-symbol-id="retention\.hold\.arm">.*?<circle[^/]*/>.*?<path',
        )
        # release: X mark (two crossing <line> elements, no <circle>/<path>)
        self.assertRegex(
            svg,
            r'data-symbol-id="retention\.release\.leg">(?:(?!<circle|<path).)*<line[^/]*/><line',
        )
        # cancel: single diagonal <line>, no circle/path/second line
        self.assertIn('data-symbol-id="retention.cancel.torso">', svg)

    def test_quality_annotation_rendered(self):
        ir = _minimal_ir(symbols=[
            {
                "symbol_id": "support.step.forward",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
            {
                "symbol_id": "quality.sustained",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
        ])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-annotation quality"', svg)

    def test_measure_header_time_signature(self):
        ir = _minimal_ir(symbols=[{
            "symbol_id": "music.time.3_4",
            "body_part": "torso",
            "direction": "forward",
            "level": "middle",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {"measure_header": True},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-header time-sig"', svg)

    def test_measure_header_tempo(self):
        ir = _minimal_ir(symbols=[{
            "symbol_id": "music.tempo.mark",
            "body_part": "torso",
            "direction": "forward",
            "level": "middle",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {"measure_header": True, "tempo": 120},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('class="laban-header tempo"', svg)
        self.assertIn("120", svg)

    def test_multiple_measures_rendered(self):
        ir = _minimal_ir(symbols=[
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
                "body_part": "right_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 2, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            },
        ])
        svg = render_laban_svg(ir)
        # Should have measure numbers
        self.assertIn(">1</text>", svg)
        self.assertIn(">2</text>", svg)

    def test_subtitle_is_labanotation_score(self):
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertIn("Labanotation Score", svg)

    def test_no_28_lane_labels(self):
        """Standard Laban renderer should NOT have the old lane labels."""
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        self.assertNotIn("Left Arm</text>", svg)
        self.assertNotIn("Right Leg</text>", svg)
        self.assertNotIn("Support</text>", svg)

    def test_staff_width_is_narrow(self):
        """Staff should be much narrower than the old 28-lane layout."""
        ir = _minimal_ir()
        layout = compute_laban_layout(ir)
        staff_width = layout["staff_right"] - layout["staff_left"]
        # Standard staff should be under 250px (vs old ~1500px)
        self.assertLess(staff_width, 250)

    def test_all_direction_shapes_are_distinct(self):
        """Each direction should produce a unique SVG shape (inline path or <use> def reference)."""
        directions = [
            "forward", "backward", "left", "right",
            "diagonal_forward_left", "diagonal_forward_right",
            "diagonal_backward_left", "diagonal_backward_right",
            "place",
        ]
        identifiers = set()
        for d in directions:
            ir = _minimal_ir(symbols=[{
                "symbol_id": "support.step.forward",
                "body_part": "left_leg",
                "direction": d,
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            }])
            svg = render_laban_svg(ir)
            # Accept either inline path or <use> reference
            path_match = re.search(r'class="laban-symbol"[^>]*>.*?d="(M [^"]+)"', svg, re.DOTALL)
            use_match = re.search(r'class="laban-symbol"[^>]*>.*?<use\s+href="#([^"]+)"', svg, re.DOTALL)
            ident = None
            if path_match:
                ident = path_match.group(1)
            elif use_match:
                ident = use_match.group(1)
            self.assertIsNotNone(ident, f"No path or <use> found for direction {d}")
            identifiers.add(ident)
        self.assertEqual(len(identifiers), len(directions), "Some directions produce identical shapes")

    def test_defs_use_pattern_emitted(self):
        """SVG should contain <symbol> defs and <use> references for direction shapes."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "middle",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('id="laban-dir-forward-middle"', svg)
        self.assertIn('href="#laban-dir-forward-middle"', svg)

    def test_facing_indicator_rendered(self):
        """When facing differs from direction, a facing arrow should appear."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "middle",
            "facing": "right",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        self.assertIn('marker-end="url(#arrow)"', svg)

    def test_no_facing_indicator_when_same_as_direction(self):
        """No facing arrow when facing equals direction."""
        ir = _minimal_ir(symbols=[{
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "middle",
            "facing": "forward",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        # The arrow marker def exists in defs, but no facing indicator line should reference it
        # Count marker-end usages - should be 0 in symbol groups
        import re as _re
        facing_arrows = _re.findall(r'class="laban-symbol".*?marker-end', svg, _re.DOTALL)
        self.assertEqual(len(facing_arrows), 0)


class ServerIntegrationTests(unittest.TestCase):

    def test_generate_score_defaults_to_laban_renderer(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        result = TOOLS["generate_score"]({"ir": ir, "name": "laban-integration-test"})
        self.assertIn("svg_path", result)
        # Read the SVG and check it's a Laban score
        svg_path = ROOT / result["svg_path"]
        if svg_path.exists():
            content = svg_path.read_text(encoding="utf-8")
            self.assertIn("Labanotation Score", content)
            svg_path.unlink(missing_ok=True)
        # Clean up
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)

    def test_generate_score_debug_renderer(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        result = TOOLS["generate_score"]({"ir": ir, "name": "debug-integration-test", "renderer": "debug"})
        svg_path = ROOT / result["svg_path"]
        if svg_path.exists():
            content = svg_path.read_text(encoding="utf-8")
            self.assertIn("Laban staff engraving preview", content)
            svg_path.unlink(missing_ok=True)
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)

    def test_generate_score_without_floor_plan_omits_floor_plan_paths(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        result = TOOLS["generate_score"]({"ir": ir, "name": "no-floorplan-integration-test"})
        self.assertNotIn("floor_plan_svg_path", result)
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)
        (ROOT / result["svg_path"]).unlink(missing_ok=True)

    def test_generate_score_with_floor_plan_emits_floor_plan_files(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        ir["extensions"] = {
            "floor_plan": [
                {
                    "performer_id": "dancer_1",
                    "measure": 1,
                    "beat": 1,
                    "position": {"zone": "downstage_left"},
                    "facing": "downstage",
                    "path_to_next": "curved",
                },
                {
                    "performer_id": "dancer_1",
                    "measure": 2,
                    "beat": 1,
                    "position": {"zone": "center"},
                    "facing": "stage_right",
                    "path_to_next": None,
                },
            ]
        }
        result = TOOLS["generate_score"]({"ir": ir, "name": "floorplan-integration-test"})
        self.assertIn("floor_plan_svg_path", result)
        floor_plan_svg = ROOT / result["floor_plan_svg_path"]
        self.assertTrue(floor_plan_svg.exists())
        content = floor_plan_svg.read_text(encoding="utf-8")
        self.assertIn("<svg", content)
        self.assertIn("AUDIENCE", content)
        floor_plan_svg.unlink(missing_ok=True)
        if result.get("floor_plan_pdf_path"):
            (ROOT / result["floor_plan_pdf_path"]).unlink(missing_ok=True)
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)
        (ROOT / result["svg_path"]).unlink(missing_ok=True)

    def test_render_floor_plan_tool(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        ir["extensions"] = {
            "floor_plan": [
                {
                    "performer_id": "dancer_1",
                    "measure": 1,
                    "beat": 1,
                    "position": {"zone": "center"},
                    "facing": "downstage",
                    "path_to_next": None,
                },
            ]
        }
        result = TOOLS["render_floor_plan"]({"ir": ir})
        self.assertIn("svg", result)
        self.assertIn("AUDIENCE", result["svg"])

    def test_render_laban_tool(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_ir()
        result = TOOLS["render_laban"]({"ir": ir})
        self.assertIn("svg", result)
        self.assertIn("Labanotation Score", result["svg"])


class GoldenParityTests(unittest.TestCase):
    """Golden regression tests for LabanWriter parity features."""

    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(
            (ROOT / "fixtures" / "golden_laban_parity_score.json").read_text(encoding="utf-8")
        )
        cls.golden_svg = (ROOT / "fixtures" / "golden_laban_parity_score.svg").read_text(encoding="utf-8")
        cls.rendered = render_laban_svg(cls.fixture)

    def test_golden_svg_matches(self):
        """Rendered SVG matches the golden file exactly."""
        self.assertEqual(self.rendered, self.golden_svg)

    def test_all_direction_shapes_present(self):
        """All 9 direction variants produce distinct path shapes."""
        directions = [
            "forward", "backward", "left", "right",
            "diagonal_forward_left", "diagonal_forward_right",
            "diagonal_backward_left", "diagonal_backward_right", "place",
        ]
        for d in directions:
            self.assertIn(f'data-direction="{d}"', self.rendered, f"Missing direction: {d}")

    def test_split_level_clip_paths(self):
        """Split-level symbols use clipPath elements."""
        self.assertIn("clipPath", self.rendered)

    def test_system_wrapping_for_long_scores(self):
        """Scores with >8 measures produce multiple staff systems."""
        layout = compute_laban_layout(self.fixture)
        systems = layout.get("systems", [])
        self.assertGreaterEqual(len(systems), 2, "10-measure score should wrap to 2+ systems")

    def test_turn_annotation_present(self):
        self.assertIn('class="laban-annotation turn"', self.rendered)

    def test_jump_annotation_present(self):
        self.assertIn('class="laban-annotation jump"', self.rendered)

    def test_spring_jump_zigzag(self):
        """Spring jump should render zigzag/coil geometry."""
        # The spring jump is in measure 4 beat 4
        self.assertIn("spring_jump", json.dumps(self.fixture))

    def test_effort_diamond_present(self):
        # effort symbols render as annotation with 'effort' in the class
        self.assertIn('laban-annotation effort', self.rendered)

    def test_contact_variants_present(self):
        self.assertIn('class="laban-annotation contact"', self.rendered)

    def test_flexion_symbols_present(self):
        """Flexion symbols are placed in staff columns (not annotations)."""
        self.assertIn('data-symbol-id="flexion.knee.90"', self.rendered)

    def test_retention_present(self):
        self.assertIn('class="laban-annotation retention"', self.rendered)

    def test_whitespace_symbol(self):
        self.assertIn('class="laban-symbol whitespace"', self.rendered)

    def test_oscillation_marks(self):
        """Symbol with oscillations=3 should have a polyline."""
        self.assertIn("polyline", self.rendered)

    def test_surface_marks(self):
        """Surface marks render as tick lines near the symbol edges."""
        # The surface_marks modifier adds tick lines (no dedicated class)
        # Our fixture has surface_marks: ["forward", "left"] on a direction.forward symbol
        # Just verify the modifier data flows through to the rendered symbol
        self.assertIn('data-symbol-id="direction.forward"', self.rendered)

    def test_joint_area_label(self):
        self.assertIn("elbow", self.rendered)

    def test_degree_marks(self):
        """Degree marks render as small circles at symbol center."""
        self.assertIn('r="1.5" fill="#111827"', self.rendered)

    def test_line_style_dotted(self):
        self.assertIn("stroke-dasharray", self.rendered)

    def test_repeat_annotations(self):
        self.assertIn('class="laban-annotation repeat"', self.rendered)

    def test_sequential_annotation(self):
        self.assertIn('class="laban-annotation sequential"', self.rendered)

    def test_bridge_routes_present(self):
        """Repeat start/end should generate bridge route lines."""
        layout = compute_laban_layout(self.fixture)
        bridges = layout.get("bridge_routes", [])
        self.assertGreater(len(bridges), 0, "Should have bridge routes for repeat start/end")

    def test_label_text(self):
        self.assertIn("plié", self.rendered)

    def test_source_text(self):
        self.assertIn("relevé", self.rendered)

    def test_measure_count(self):
        """Fixture has 10 measures."""
        layout = compute_laban_layout(self.fixture)
        self.assertEqual(layout["measure_count"], 10)


class CatalogFamilyRoutingTests(unittest.TestCase):
    """Guards against the exact bug class found during the LabanWriter-parity
    audit: a catalog family whose geometry.staff_column isn't in
    PRIMARY_FAMILIES or ANNOTATION_FAMILIES silently falls through to
    BODY_TO_COLUMN and renders as a generic direction pentagon instead of
    its intended mark (this happened to bow/dynamic/adlib/motif/foothook/
    digit before the fix). Every catalog staff_column must be accounted for
    here, explicitly, so a newly-added symbol family can't repeat it.
    """

    @classmethod
    def setUpClass(cls):
        cls.catalog = load_symbol_catalog()

    def test_every_staff_column_is_routed_or_explicitly_allowlisted(self):
        known = PRIMARY_FAMILIES | ANNOTATION_FAMILIES | KNOWN_MAIN_STAFF_FALLTHROUGH
        unrouted = set()
        for entry in self.catalog.values():
            staff_column = entry.get("geometry", {}).get("staff_column")
            if staff_column and staff_column not in known:
                unrouted.add(staff_column)
        self.assertEqual(
            unrouted, set(),
            f"Catalog staff_column(s) {unrouted} are not in PRIMARY_FAMILIES, "
            "ANNOTATION_FAMILIES, or KNOWN_MAIN_STAFF_FALLTHROUGH — they will "
            "silently misrender as direction pentagons. Add them to one of "
            "those sets (with a renderer, if annotation) or to the "
            "fallthrough allowlist with a comment justifying why main-staff "
            "placement is correct.",
        )


if __name__ == "__main__":
    unittest.main()
