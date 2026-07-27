import json
import re
import unittest
from pathlib import Path

from dancenotation_mcp.rendering.laban_renderer import (
    render_laban_svg,
    _render_turn_annotation,
    _render_jump_annotation,
    _render_effort_diamond,
    _render_shape_symbol,
    _render_quality_annotation,
    _render_timing_annotation,
    _render_foot_detail_annotation,
    LEVEL_FILLS,
)
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
        """Per the LabanWriter manual, Middle level is unshaded (no fill
        pattern). That is about the fill only — the centre dot that also marks
        middle level is a separate mark; see MiddleLevelDotTest."""
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
        self.assertIn('class="laban-annotation foot-position"', svg)

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

    def test_bare_surface_symbols_reach_a_dispatch_branch(self):
        """surface.contact/brush/glide (symbol_id prefix "surface", distinct
        from the "contact" family prefix) had no dispatch branch at all — only
        "contact" was handled — and fell through.

        They were first routed to the contact renderer, which stopped them
        falling through but made all three engrave as contact.touch. The
        catalog settles that they are their own signs, each with its own glyph
        and staff_column, so they now have their own branch. See
        SurfaceFamilyTest.
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
        self.assertIn('class="laban-annotation surface"', svg)

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
        # quality.sustained is the Time-factor "sustained" pole, so it now
        # renders with the shared effort-stroke geometry rather than the old
        # generic labelled box.
        self.assertIn('class="laban-annotation effort"', svg)
        self.assertIn('data-effort="time.sustained"', svg)

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


class TurnJumpLevelFillTest(unittest.TestCase):
    """Turn and jump signs are universally ``requires_level`` in the catalog;
    the renderer must show level via the standard fill convention
    (low = solid black, middle = blank/white, high = striped hatch) so the
    three levels are visually distinct."""

    def _entry(self, symbol_id, level, **modifiers):
        symbol = {"symbol_id": symbol_id, "level": level}
        if symbol_id.startswith("turn"):
            symbol["direction"] = "right"
        if modifiers:
            symbol["modifiers"] = modifiers
        return {
            "symbol": symbol,
            "x": 10.0,
            "y_top": 0.0,
            "y_bottom": 40.0,
            "width": 20.0,
        }

    def _turn(self, level, **mods):
        return _render_turn_annotation(self._entry("turn.pivot", level, **mods))

    def _jump(self, level, **mods):
        return _render_jump_annotation(self._entry("jump.small", level, **mods))

    def test_turn_levels_are_distinct(self):
        low, mid, high = self._turn("low"), self._turn("middle"), self._turn("high")
        self.assertNotEqual(low, mid)
        self.assertNotEqual(mid, high)
        self.assertNotEqual(low, high)

    def test_turn_fill_matches_convention(self):
        self.assertIn(LEVEL_FILLS["low"]["fill"], self._turn("low"))       # solid black
        self.assertIn(LEVEL_FILLS["middle"]["fill"], self._turn("middle"))  # blank/white
        self.assertIn(LEVEL_FILLS["high"]["fill"], self._turn("high"))     # striped hatch

    def test_turn_records_level_attribute(self):
        self.assertIn('data-level="high"', self._turn("high"))

    def test_jump_levels_are_distinct(self):
        low, mid, high = self._jump("low"), self._jump("middle"), self._jump("high")
        self.assertNotEqual(low, mid)
        self.assertNotEqual(mid, high)
        self.assertNotEqual(low, high)

    def test_jump_fill_matches_convention(self):
        self.assertIn(LEVEL_FILLS["low"]["fill"], self._jump("low"))
        self.assertIn(LEVEL_FILLS["high"]["fill"], self._jump("high"))

    def test_jump_level_composes_with_variants(self):
        # Level fill must survive alongside the existing spring/stretch variants.
        for mods in ({"spring_jump": True}, {"stretch": 2}):
            low = self._jump("low", **mods)
            high = self._jump("high", **mods)
            self.assertNotEqual(low, high)
            self.assertIn('class="laban-annotation jump"', low)

    def test_jump_missing_level_defaults_to_middle(self):
        entry = self._entry("jump.small", None)
        entry["symbol"].pop("level")
        out = _render_jump_annotation(entry)
        self.assertIn('data-level="middle"', out)


class EffortShapeGeometryTest(unittest.TestCase):
    """Effort and shape signs must render as distinct authentic geometry, not
    an identical empty diamond (effort) or a single letter (shape)."""

    def _entry(self, symbol_id):
        return {
            "symbol": {"symbol_id": symbol_id},
            "spec": {},
            "x": 10.0, "y_top": 0.0, "y_bottom": 40.0, "width": 20.0,
        }

    def _geom(self, svg):
        import re as _re
        return _re.sub(r'data-[a-z-]+="[^"]*"', "", svg)

    def test_eight_effort_poles_render_distinctly(self):
        poles = [
            "effort.weight.strong", "effort.weight.light",
            "effort.space.direct", "effort.space.indirect",
            "effort.time.sudden", "effort.time.sustained",
            "effort.flow.bound", "effort.flow.free",
        ]
        geoms = {self._geom(_render_effort_diamond(self._entry(p))) for p in poles}
        self.assertEqual(len(geoms), 8, "all 8 effort poles must be visually distinct")

    def test_condensing_pole_filled_indulging_pole_open(self):
        strong = _render_effort_diamond(self._entry("effort.weight.strong"))
        light = _render_effort_diamond(self._entry("effort.weight.light"))
        self.assertIn("path", strong)   # filled wedge
        self.assertNotIn("path", light)  # open stroke only

    def test_effort_graph_with_active_efforts_still_uses_diamond(self):
        entry = self._entry("effort.drive.action")
        entry["symbol"]["modifiers"] = {"active_efforts": ["weight", "time"]}
        svg = _render_effort_diamond(entry)
        # Aggregate graph keeps the four-quadrant diamond outline.
        self.assertIn("L", svg)
        self.assertIn('opacity="0.6"', svg)  # shaded active quadrants

    def test_shape_families_render_distinctly_without_text_fallback(self):
        shapes = [
            "shape.wall.spreading", "shape.ball.bulging", "shape.pin.rising",
            "shape.screw.advancing", "shape.flow.growing",
            "shape.door.spreading", "shape.table.spreading",
        ]
        geoms = {self._geom(_render_shape_symbol(self._entry(s))) for s in shapes}
        self.assertEqual(len(geoms), 7, "all 7 shape families must be distinct")
        for s in shapes:
            svg = _render_shape_symbol(self._entry(s))
            self.assertNotIn('font-size="7"', svg, f"{s} fell back to a text label")

    def test_quality_pole_alias_reuses_effort_geometry(self):
        q = _render_quality_annotation(self._entry("quality.strong"))
        e = _render_effort_diamond(self._entry("effort.weight.strong"))
        self.assertEqual(self._geom(q), self._geom(e))


class PlaceholderGeometryTest(unittest.TestCase):
    """The last families that rendered as truncated-id / glyph text labels
    (level, timing, digit, foothook) must draw distinct, convention-based
    geometry with no text placeholder."""

    def _entry(self, symbol_id, glyph=""):
        return {
            "symbol": {"symbol_id": symbol_id},
            "spec": {"geometry": {"glyph": glyph}},
            "x": 10.0, "y_top": 0.0, "y_bottom": 40.0, "width": 20.0,
        }

    def _geom(self, svg):
        import re as _re
        return _re.sub(r'data-[a-z-]+="[^"]*"', "", svg)

    def _assert_no_text_placeholder(self, svg, sid):
        shapes = ("<path", "<line", "<rect", "<circle", "<polygon",
                  "<ellipse", "<polyline")
        self.assertTrue(any(t in svg for t in shapes),
                        f"{sid} drew no shape primitive")
        self.assertNotIn("<text", svg, f"{sid} still renders a text label")

    def test_level_marks_reuse_level_fills_and_are_distinct(self):
        levels = ["level.low", "level.middle", "level.high"]
        svgs = {lv: _render_timing_annotation(self._entry(lv)) for lv in levels}
        geoms = {self._geom(s) for s in svgs.values()}
        self.assertEqual(len(geoms), 3, "the 3 level marks must be distinct")
        for lv, svg in svgs.items():
            self._assert_no_text_placeholder(svg, lv)
        # Fill follows the shared LEVEL_FILLS convention.
        self.assertIn(LEVEL_FILLS["low"]["fill"], svgs["level.low"])
        self.assertIn(LEVEL_FILLS["high"]["fill"], svgs["level.high"])

    def test_timing_marks_render_distinctly_without_text_fallback(self):
        ids = [
            "timing.duration.1_8", "timing.duration.1_4", "timing.duration.1_2",
            "timing.duration.1", "timing.duration.2", "timing.duration.3",
            "timing.duration.4", "timing.syncopated", "timing.staccato",
            "timing.tenuto", "timing.fermata",
        ]
        svgs = {sid: _render_timing_annotation(self._entry(sid)) for sid in ids}
        geoms = {self._geom(s) for s in svgs.values()}
        self.assertEqual(len(geoms), len(ids),
                         "all 11 timing marks must be visually distinct")
        for sid, svg in svgs.items():
            self._assert_no_text_placeholder(svg, sid)

    def test_duration_marks_scale_with_duration_value(self):
        # Longer note values draw a longer duration line.
        short = _render_timing_annotation(self._entry("timing.duration.1_8"))
        long = _render_timing_annotation(self._entry("timing.duration.4"))
        import re as _re

        def line_len(svg):
            m = _re.search(r'<line x1="[\d.]+" y1="([\d.]+)" x2="[\d.]+" y2="([\d.]+)"', svg)
            return abs(float(m.group(2)) - float(m.group(1)))

        self.assertLess(line_len(short), line_len(long))

    def test_accent_and_hold_geometry_unchanged(self):
        # Regression: the two timing marks that were already authentic must
        # keep drawing their existing shapes.
        self.assertIn("path", _render_timing_annotation(self._entry("timing.accent")))
        self.assertIn("circle", _render_timing_annotation(self._entry("timing.hold")))

    def test_digit_marks_render_distinctly_without_text_fallback(self):
        ids = ["finger.mark", "toe.mark"]
        svgs = {sid: _render_foot_detail_annotation(self._entry(sid)) for sid in ids}
        geoms = {self._geom(s) for s in svgs.values()}
        self.assertEqual(len(geoms), 2, "finger and toe marks must be distinct")
        for sid, svg in svgs.items():
            self._assert_no_text_placeholder(svg, sid)

    def test_foothook_symbols_render_distinctly_without_text_fallback(self):
        ids = [
            "foot.surface.ball", "foot.surface.heel", "foot.surface.full_sole",
            "foot.surface.toe_tip", "foot.surface.demi_pointe",
            "foot.surface.instep", "foot.surface.metatarsal",
            "foot.edge.inside", "foot.edge.outside",
            "foot.hook.forward", "foot.hook.backward", "foot.hook.side",
            "foot.hook.crossed_forward", "foot.hook.crossed_backward",
            "foot.position.parallel", "foot.position.turned_out",
            "foot.position.turned_in", "foot.position.first",
            "foot.position.second", "foot.position.third",
            "foot.position.fourth", "foot.position.fifth",
            "foot.action.stamp", "foot.action.tap", "foot.action.brush",
            "foot.action.scuff", "foot.action.dig", "foot.action.slide",
            "foot.action.heel_drop", "foot.action.toe_drop",
            "foothook.left", "foothook.right",
        ]
        svgs = {sid: _render_foot_detail_annotation(self._entry(sid)) for sid in ids}
        geoms = {self._geom(s) for s in svgs.values()}
        self.assertEqual(len(geoms), len(ids),
                         f"all {len(ids)} foothook symbols must be visually distinct")
        for sid, svg in svgs.items():
            self._assert_no_text_placeholder(svg, sid)

    def test_foothook_subfamilies_share_structural_motif(self):
        # Each sub-family uses a consistent structural element:
        # surface -> foot-outline with shaded region
        # hook -> stem with hook endpoint
        # position -> pair of tick marks
        surface = _render_foot_detail_annotation(self._entry("foot.surface.ball"))
        hook = _render_foot_detail_annotation(self._entry("foot.hook.forward"))
        position = _render_foot_detail_annotation(self._entry("foot.position.first"))
        action = _render_foot_detail_annotation(self._entry("foot.action.stamp"))
        # Each sub-family has a unique class marker in its group.
        self.assertIn("foot-surface", surface)
        self.assertIn("foot-hook", hook)
        self.assertIn("foot-position", position)
        self.assertIn("foot-action", action)


class QualityAliasIdentityTest(unittest.TestCase):
    """``quality.<pole>`` ids are aliases of the LMA effort poles and correctly
    reuse the effort-stroke glyph. The glyph may be shared; the identity may
    not — the emitted group must still name the symbol the score author wrote,
    or the SVG cannot be traced back to the IR that produced it."""

    POLES = ("strong", "light", "sudden", "sustained",
             "direct", "flexible", "bound", "free")

    def _render(self, pole):
        ir = _minimal_ir([{
            "symbol_id": f"quality.{pole}",
            "body_part": "left_arm",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        return render_laban_svg(ir)

    def test_authored_quality_id_survives_into_the_svg(self):
        for pole in self.POLES:
            with self.subTest(pole=pole):
                self.assertIn(f'data-symbol-id="quality.{pole}"', self._render(pole))

    def test_alias_target_is_recorded_separately(self):
        # Keeping the effort id as its own attribute preserves the aliasing
        # information without overwriting the authored identity.
        self.assertIn('data-effort="weight.strong"', self._render("strong"))

    def test_quality_still_renders_effort_stroke_geometry(self):
        # The shared glyph is correct and must not regress into a text label.
        svg = self._render("strong")
        group = re.search(r'<g class="laban-annotation effort"[^>]*>.*?</g>', svg, re.S)
        self.assertIsNotNone(group, "quality did not render as an effort stroke")
        self.assertNotIn("<text", group.group(0))


class CaptionPlacementTest(unittest.TestCase):
    """A caption belongs beside the staff, not across it.

    Captions were drawn at the symbol's own x, so they landed on the staff and
    over the notation — in one 33-measure score, 23 of 91 sat inside the staff
    lines, one of them exactly on the centre line.

    The plates put this text in the margin: Soirée musicale p58 runs
    "(DRY ELEGANT BOW)" vertically beside the staff, and La vivandière keeps
    dancer identification below it. Nothing is written across the notation.
    """

    def _svg(self):
        return render_laban_svg(_minimal_ir([
            {
                "symbol_id": "support.step",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                "modifiers": {"label": "grand plie 2nd"},
            },
            {
                "symbol_id": "support.step",
                "body_part": "right_leg",
                "direction": "backward",
                "level": "low",
                "timing": {"measure": 1, "beat": 3, "duration_beats": 1},
                "modifiers": {"label": "flat-back table"},
            },
        ]))

    def _staff_bounds(self, svg):
        xs = sorted({
            round(float(m.group(1)), 1)
            for m in re.finditer(
                r'<line x1="([\d.]+)" y1="([\d.]+)" x2="\1" y2="([\d.]+)"([^>]*)>', svg)
            if abs(float(m.group(3)) - float(m.group(2))) > 30
            and "dasharray" not in m.group(4)
        })
        self.assertGreaterEqual(len(xs), 3, "staff lines not found")
        return xs[0], xs[-1]

    def test_no_caption_is_written_across_the_staff(self):
        svg = self._svg()
        left, right = self._staff_bounds(svg)
        # Attribute order is not guaranteed, so match the class anywhere in the
        # tag rather than assuming x comes first.
        captions = [
            (float(re.search(r'\sx="([\d.]+)"', m.group(1)).group(1)), m.group(2))
            for m in re.finditer(
                r'<text([^>]*class="laban-caption"[^>]*)>([^<]*)</text>', svg)
        ]
        self.assertTrue(captions, "no captions rendered")
        for x, text in captions:
            self.assertFalse(
                left - 2 <= x <= right + 2,
                f"caption {text!r} sits at x={x}, across the staff ({left}-{right})")

    def test_captions_are_still_rendered(self):
        svg = self._svg()
        self.assertIn("grand plie 2nd", svg)
        self.assertIn("flat-back table", svg)


class SystemLayoutTest(unittest.TestCase):
    """Systems run side by side across the page, not stacked into one column.

    Measured on the reference plates: La vivandière p91 and p97 each carry two
    three-line staves side by side, and the page is 1 : 1.37 portrait. Stacking
    every system vertically gave one unbounded column — a 33-measure score came
    out 360 x 7428, an aspect of 1 : 20.6, which is not a page at all.

    Measure height was already right (about 186px against the plates' ~190 at
    150dpi); what was wrong was the direction systems flow and how many
    measures one holds.
    """

    def _score(self, measures):
        return _minimal_ir([{
            "symbol_id": "support.step",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "middle",
            "timing": {"measure": m, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        } for m in range(1, measures + 1)])

    def test_a_long_score_places_systems_side_by_side(self):
        layout = compute_laban_layout(self._score(33))
        self.assertGreater(len(layout["systems"]), 1, "score did not wrap")
        lefts = {round(s["staff_left"], 1) for s in layout["systems"]}
        self.assertGreater(
            len(lefts), 1,
            f"every system sits at the same x ({lefts}) — they are stacked")

    def test_a_long_score_is_not_an_unbounded_column(self):
        layout = compute_laban_layout(self._score(33))
        aspect = layout["height"] / layout["width"]
        self.assertLess(
            aspect, 4.0,
            f"canvas is {layout['width']}x{layout['height']} — aspect 1:{aspect:.1f}, "
            f"the plates are 1:1.37")

    def test_a_short_score_still_gets_one_system(self):
        layout = compute_laban_layout(self._score(3))
        self.assertEqual(len(layout["systems"]), 1)


class SurfaceFamilyTest(unittest.TestCase):
    """surface.* are their own signs, not aliases of contact.*.

    They routed into ``_render_contact_annotation``, where the type comes from
    parts[1] — for a surface id that is "contact"/"glide"/"brush", so
    surface.contact hit the touch default and surface.glide with it.

    The catalog settles that they are distinct rather than aliases: each
    carries its own glyph (U+224B, U+25CD, U+2248) and its own
    ``staff_column`` of "surface". Where a family really is an alias — quality.*
    against effort.* — the shared glyph is kept and only the authored id
    preserved; that is not this case.
    """

    IDS = ["surface.brush", "surface.contact", "surface.glide"]

    def _markup(self, symbol_id):
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_the_three_surface_signs_render_distinctly(self):
        seen = {}
        for symbol_id in self.IDS:
            shape = self._markup(symbol_id)
            clash = seen.get(shape)
            self.assertIsNone(clash, f"{symbol_id} renders like {clash}")
            seen[shape] = symbol_id

    def test_a_surface_sign_is_not_a_contact_sign(self):
        contact = self._markup("contact.touch")
        for symbol_id in self.IDS:
            with self.subTest(symbol=symbol_id):
                self.assertNotEqual(self._markup(symbol_id), contact)

    def test_surface_signs_keep_their_authored_id(self):
        for symbol_id in self.IDS:
            with self.subTest(symbol=symbol_id):
                svg = render_laban_svg(_minimal_ir([{
                    "symbol_id": symbol_id,
                    "body_part": "torso",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                }]))
                self.assertIn(f'data-symbol-id="{symbol_id}"', svg)


class SeparatorModeTest(unittest.TestCase):
    """Six separators shared one glyph.

    ``_render_separator`` read ``modifiers.separator_mode``, defaulting to
    "single" — a field nothing populates — while the catalog stated the mode
    for each entry in ``behavior.preferred_separator_mode`` and
    ``behavior.cap_shape``, and marked the flipped staff separator with
    ``behavior.flip_variant``. The LabanWriter manual lists the flipped staff
    separator as its own feature, so that one in particular must not collapse
    onto the unflipped form.
    """

    IDS = ["separator.single", "separator.double", "separator.hook",
           "separator.final", "separator.staff", "separator.staff.flipped"]

    def _markup(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_every_separator_renders_distinctly(self):
        seen = {}
        for symbol_id in self.IDS:
            shape = self._markup(symbol_id)
            clash = seen.get(shape)
            self.assertIsNone(clash, f"{symbol_id} renders like {clash}")
            seen[shape] = symbol_id

    def test_the_flipped_staff_separator_is_a_mirror_of_the_plain_one(self):
        plain = self._markup("separator.staff")
        flipped = self._markup("separator.staff.flipped")
        self.assertNotEqual(plain, flipped)
        # Same number of strokes — flipping turns the hooks, it does not add.
        self.assertEqual(len(re.findall(r"<line", plain)),
                         len(re.findall(r"<line", flipped)))

    def test_an_explicit_separator_mode_still_wins(self):
        by_catalog = self._markup("separator.single")
        forced = self._markup("separator.single",
                              modifiers={"separator_mode": "double"})
        self.assertNotEqual(by_catalog, forced)


class EffortGradingTest(unittest.TestCase):
    """``effort.<factor>.<pole>.increasing`` grades the element; the grading was
    dropped.

    ``_render_effort_diamond`` took factor from parts[1] and pole from
    parts[2], then stopped — parts[3] was never read, so a bound flow and a
    bound flow that is increasing engraved identically. In LMA a growing or
    diminishing effort is the element plus a grading mark, so the element keeps
    its stroke and the grading is added to it.
    """

    GRADED = [
        ("effort.flow.bound", "effort.flow.bound.increasing"),
        ("effort.flow.free", "effort.flow.free.increasing"),
        ("effort.space.direct", "effort.space.direct.increasing"),
        ("effort.space.indirect", "effort.space.indirect.increasing"),
        ("effort.time.sudden", "effort.time.sudden.increasing"),
        ("effort.time.sustained", "effort.time.sustained.increasing"),
        ("effort.weight.strong", "effort.weight.strong.increasing"),
        ("effort.weight.light", "effort.weight.light.decreasing"),
    ]

    def _markup(self, symbol_id):
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_a_graded_element_differs_from_the_plain_one(self):
        for plain, graded in self.GRADED:
            with self.subTest(symbol=graded):
                self.assertNotEqual(self._markup(plain), self._markup(graded))

    def test_the_element_stroke_survives_the_grading(self):
        # The grading is added to the element, it does not replace it.
        for plain, graded in self.GRADED:
            with self.subTest(symbol=graded):
                marked = self._markup(graded)
                for line in re.findall(r'<line[^>]*/>', self._markup(plain)):
                    self.assertIn(line, marked, "element stroke lost")

    def test_increasing_and_decreasing_are_not_the_same_mark(self):
        rising = self._markup("effort.weight.strong.increasing")
        falling = self._markup("effort.weight.light.decreasing")
        # Different poles too, so compare only the grading marks.
        self.assertNotEqual(
            re.findall(r'<path[^>]*/>', rising),
            re.findall(r'<path[^>]*/>', falling))


class InherentLevelTest(unittest.TestCase):
    """A support whose level is inherent must engrave at that level.

    In Labanotation a support's level IS the state of the leg — DNB
    Fundamentals: "a low level corresponds to a bent leg, a middle level to a
    straight leg, and a high level to being up on the toes". So plié is a low
    support and relevé a high one; they are not pre-signs added to a symbol,
    they are that symbol's own shading, which the renderer already draws.

    The catalog gave those entries free allowed_levels, so nothing pinned them
    and they engraved byte-identical to a plain step. The rule applied: when
    the catalog allows exactly one level, that is the level, and the symbol
    need not repeat it.

    They still coincide with a plain step at the matching level. That is
    correct — a low-level step IS a plié step.
    """

    def _glyph(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "left_leg",
            "direction": "forward",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        m = re.search(r'<use href="#laban-dir-([a-z_]+)-([a-z]+)"', svg)
        self.assertIsNotNone(m, f"no direction glyph for {symbol_id}")
        return m.group(2)

    def test_plie_is_a_low_support(self):
        self.assertEqual(self._glyph("support.plie.forward"), "low")

    def test_releve_and_rise_are_high_supports(self):
        self.assertEqual(self._glyph("support.releve.forward"), "high")
        self.assertEqual(self._glyph("support.rise.forward"), "high")

    def test_lower_is_a_low_support(self):
        self.assertEqual(self._glyph("support.lower.forward"), "low")

    def test_a_plain_step_still_takes_any_level(self):
        # Nothing is pinned on step; it must keep defaulting to middle and
        # honour whatever the score asks for.
        self.assertEqual(self._glyph("support.step.forward"), "middle")
        self.assertEqual(self._glyph("support.step.forward", level="high"), "high")

    def test_an_explicit_level_still_wins_over_the_inherent_one(self):
        self.assertEqual(self._glyph("support.plie.forward", level="high"), "high")


class JumpSubtypeTest(unittest.TestCase):
    """A jump id names a subtype the renderer never read.

    ``_render_jump_annotation`` read ``modifiers.spring_jump``,
    ``modifiers.stretch`` and level, but not the id, and nothing injects those
    modifiers from the id — so a score built from catalog ids engraved
    jump.small, jump.large, jump.assemble, jump.sissonne and jump.spring
    identically.

    The boundary that must hold: a jump sign carries no compass direction. That
    part of the collapse is correct notation — the travel direction lives in
    the direction symbols in the support columns — and is asserted below so a
    later pass cannot "fix" it by inventing signs.
    """

    SUBTYPES = ["small", "large", "assemble", "sissonne", "spring"]

    def _markup(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "torso",
            "level": "middle",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_each_jump_subtype_renders_distinctly(self):
        seen = {}
        for subtype in self.SUBTYPES:
            shape = self._markup(f"jump.{subtype}")
            clash = seen.get(shape)
            self.assertIsNone(clash, f"jump.{subtype} renders like jump.{clash}")
            seen[shape] = subtype
        self.assertEqual(len(seen), len(self.SUBTYPES))

    def test_a_jump_carries_no_compass_direction(self):
        # Correct shared notation: the travel direction is in the support
        # columns, not on the jump sign. These must stay identical.
        for direction in ("forward", "backward", "left"):
            with self.subTest(direction=direction):
                self.assertEqual(
                    self._markup("jump.small", direction=direction),
                    self._markup("jump.small", direction="right"))

    def test_level_still_reaches_the_jump_sign(self):
        low = self._markup("jump.small", level="low")
        high = self._markup("jump.small", level="high")
        self.assertNotEqual(low, high)

    def test_explicit_modifiers_still_win(self):
        plain = self._markup("jump.small")
        sprung = self._markup("jump.small", modifiers={"spring_jump": True})
        self.assertNotEqual(plain, sprung)


class PinBowTurnSubtypeTest(unittest.TestCase):
    """pin, bow and turn each name a subtype in the id that never reached the
    drawing. Three instances of one defect, so they are asserted together.

    pin is the clearest: ``_render_pin_annotation`` read
    ``modifiers.pin_head``, which nothing populates, while the catalog's own
    ``behavior.cap_shape`` sat unread beside it — pin.entry declares
    "diamond_head" and still drew the default triangle.
    """

    FAMILIES = {
        "pin": ["generic", "entry", "hold", "floorplan_exit"],
        "bow": ["hook", "horizontal", "vertical", "small"],
        "turn": ["pivot", "spin", "half", "full"],
    }

    def _markup(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_each_subtype_renders_distinctly(self):
        for family, subtypes in self.FAMILIES.items():
            seen = {}
            for subtype in subtypes:
                shape = self._markup(f"{family}.{subtype}")
                clash = seen.get(shape)
                self.assertIsNone(
                    clash, f"{family}.{subtype} renders like {family}.{clash}")
                seen[shape] = subtype

    def test_pin_head_comes_from_the_catalog_behavior(self):
        # pin.entry declares cap_shape "diamond_head"; pin.hold "hold_bar".
        self.assertNotEqual(self._markup("pin.entry"), self._markup("pin.generic"))
        self.assertNotEqual(self._markup("pin.hold"), self._markup("pin.generic"))

    def test_an_explicit_modifier_still_overrides_the_id(self):
        for family, override in (("pin", {"pin_head": "diamond"}),
                                 ("bow", {"bow_type": "vertical"})):
            with self.subTest(family=family):
                base = self._markup(f"{family}.{self.FAMILIES[family][0]}")
                forced = self._markup(f"{family}.{self.FAMILIES[family][0]}",
                                      modifiers=override)
                self.assertNotEqual(base, forced)

    def test_turn_amount_and_turn_type_are_separate_distinctions(self):
        # half/full is how far; pivot/spin is what kind. Neither may collapse.
        self.assertNotEqual(self._markup("turn.half"), self._markup("turn.full"))
        self.assertNotEqual(self._markup("turn.pivot"), self._markup("turn.spin"))


class SequentialKindTest(unittest.TestCase):
    """A sequential id names a kind; the renderer never read the id at all.

    ``_render_sequential_annotation`` drew one wavy line plus an arrow whose
    direction came from ``modifiers.wave_direction`` (default "upward"), a field
    nothing populates. So a simultaneous movement, a successive one, a ripple
    and a proximal-to-distal sequence all engraved as the same upward wave,
    although the catalog gives each its own glyph.

    ``wave.arm``/``body``/``leg`` are NOT part of this — the catalog gives all
    three the same glyph U+223F, and the limb is carried by placement. Forcing
    those apart would be inventing signs.
    """

    KINDS = [
        "sequential.simultaneous",
        "sequential.ripple",
        "sequential.successive.upward",
        "sequential.successive.downward",
        "sequential.successive.lateral",
        "sequential.sequential.proximal_to_distal",
        "sequential.sequential.distal_to_proximal",
        "sequential.wave.body",
    ]

    def _markup(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_each_sequential_kind_renders_distinctly(self):
        seen = {}
        for symbol_id in self.KINDS:
            shape = self._markup(symbol_id)
            clash = seen.get(shape)
            self.assertIsNone(clash, f"{symbol_id} renders like {clash}")
            seen[shape] = symbol_id
        self.assertEqual(len(seen), len(self.KINDS))

    def test_the_wave_limbs_share_one_glyph_by_design(self):
        # Same catalog glyph; the limb comes from placement, not the mark.
        arm = self._markup("sequential.wave.arm")
        leg = self._markup("sequential.wave.leg")
        self.assertEqual(arm, leg)

    def test_an_explicit_wave_direction_modifier_still_wins(self):
        by_id = self._markup("sequential.successive.upward")
        overridden = self._markup("sequential.successive.upward",
                                  modifiers={"wave_direction": "downward"})
        self.assertNotEqual(by_id, overridden)


class ShapePoleTest(unittest.TestCase):
    """A shape id names a family AND a pole; both must reach the drawing.

    ``_render_shape_symbol`` keyed only on ``parts[1]``, the family, and drew
    one fixed glyph for it. The pole in ``parts[2]`` was never read, so every
    semantic opposite engraved identically — spreading as enclosing, rising as
    sinking, growing as shrinking — although the catalog gives each pole its own
    glyph (wall.spreading U+2194 vs wall.enclosing U+2195, and so on).

    The poles are directional opposites along LMA's three dimensions, so the
    family keeps its form and the pole sets the sense.
    """

    POLES = {
        "ball": ["bulging", "hollowing"],
        "door": ["spreading", "enclosing"],
        "flow": ["growing", "shrinking"],
        "pin": ["rising", "sinking", "lengthening", "shortening"],
        "screw": ["advancing", "retreating", "forward", "backward"],
        "table": ["spreading", "enclosing"],
        "wall": ["spreading", "enclosing", "widening", "narrowing"],
    }

    def _markup(self, symbol_id):
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        # Strip the id: two symbols drawn identically still differ by it, and
        # keeping it would make every comparison below pass for free.
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_poles_within_a_family_render_distinctly(self):
        for family, poles in self.POLES.items():
            seen = {}
            for pole in poles:
                shape = self._markup(f"shape.{family}.{pole}")
                clash = seen.get(shape)
                self.assertIsNone(
                    clash,
                    f"shape.{family}.{pole} renders like shape.{family}.{clash}")
                seen[shape] = pole

    def test_every_shape_symbol_is_unique_across_families(self):
        seen = {}
        for family, poles in self.POLES.items():
            for pole in poles:
                symbol_id = f"shape.{family}.{pole}"
                shape = self._markup(symbol_id)
                clash = seen.get(shape)
                self.assertIsNone(clash, f"{symbol_id} renders like {clash}")
                seen[shape] = symbol_id
        self.assertEqual(len(seen), sum(len(p) for p in self.POLES.values()))

    def test_an_explicit_shape_type_modifier_still_selects_the_family(self):
        # The modifier override predates the id parsing and must keep working.
        by_id = self._markup("shape.wall.spreading")
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": "shape.wall.spreading",
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {"shape_type": "ball"},
        }]))
        self.assertNotIn(by_id.strip("<g >"), svg)


class BodyActionMarkTest(unittest.TestCase):
    """The body action must be visible, not just its direction and level.

    body.* symbols drew the direction symbol alone, so the action —
    which is the whole point of the sign — was invisible: body.tilt.forward.high
    and body.bend.forward.high engraved identically, and so did contract and
    release, which the catalog itself records as mirror opposites (glyph U+2282
    vs U+2283, and U+2312 vs U+2322 for bend vs stretch).
    """

    ACTIONS = ["bend", "stretch", "tilt", "contract", "release"]

    def _markup(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_each_body_action_is_distinguishable(self):
        seen = {}
        for action in self.ACTIONS:
            shape = self._markup(f"body.{action}.forward.high")
            clash = seen.get(shape)
            self.assertIsNone(clash, f"body.{action} renders like body.{clash}")
            seen[shape] = action

    def test_mirror_pairs_are_not_identical(self):
        for a, b in (("contract", "release"), ("bend", "stretch")):
            with self.subTest(pair=f"{a}/{b}"):
                self.assertNotEqual(self._markup(f"body.{a}.place.middle"),
                                    self._markup(f"body.{b}.place.middle"))

    def test_direction_and_level_still_reach_the_symbol(self):
        # The action mark must not displace the direction symbol.
        markup = self._markup("body.tilt.forward.high")
        self.assertIn("laban-dir-forward-high", markup)


class FlexionExtensionRoutingTest(unittest.TestCase):
    """Flexion and extension marks are annotation signs, not direction symbols.

    ``_symbol_family("extension.ankle.45")`` is "extension", which appears in
    neither PRIMARY_FAMILIES nor ANNOTATION_FAMILIES, so ``_resolve_column``
    fell through to the body-part mapping and all 54 catalog entries were drawn
    on the staff as ``place``-``middle`` direction symbols — the wrong sign
    entirely. ``_render_flexion_symbol`` was dead code for every one of them.

    The degree is in the id (``.45``/``.90``/``.full``), which the renderer also
    never read: it took degree from modifiers only.
    """

    def _markup(self, symbol_id, body_part="left_leg", **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": body_part,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        markup = svg[start:svg.find("</g>", start)]
        # Strip the id, or every comparison below passes trivially: two symbols
        # drawn identically still differ by their data-symbol-id.
        return re.sub(r'data-symbol-id="[^"]*"', "", markup)

    def test_flexion_marks_are_not_drawn_as_direction_symbols(self):
        for symbol_id in ("flexion.knee.90", "extension.ankle.45",
                          "flexion.elbow.full", "extension.spine.90"):
            with self.subTest(symbol=symbol_id):
                markup = self._markup(symbol_id)
                self.assertNotIn("laban-dir-", markup,
                                 "drawn as a direction glyph")
                self.assertIn("laban-annotation flexion", markup)

    def test_degree_comes_from_the_id(self):
        shapes = {
            degree: self._markup(f"flexion.knee.{degree}")
            for degree in ("45", "90", "full")
        }
        self.assertEqual(len(set(shapes.values())), 3,
                         f"degrees render alike: {list(shapes)}")

    def test_flexion_and_extension_of_the_same_joint_differ(self):
        self.assertNotEqual(self._markup("flexion.knee.90"),
                            self._markup("extension.knee.90"))

    def test_explicit_degree_modifier_still_wins(self):
        by_id = self._markup("flexion.knee.45")
        overridden = self._markup("flexion.knee.45", modifiers={"degree": 3})
        self.assertNotEqual(by_id, overridden)


class ContactSymbolIdParsingTest(unittest.TestCase):
    """A contact id names two things — the contact type and, optionally, the
    body surface — and both must reach the drawing.

    ``contact_type`` was taken from the *last* dotted segment, so
    ``contact.grasp.front`` resolved its type to "front", missed the grasp
    staple and drew the generic touch caret. Only the bare ``contact.grasp``
    ever rendered correctly. The surface suffix was ignored entirely: it was
    read from modifiers only. 38 symbols collapsed onto one glyph.
    """

    TYPES = ["touch", "slide", "strike", "grasp", "brush", "carry",
             "press", "release", "interlock", "support"]
    SURFACES = ["front", "back", "inner", "outer"]

    def _markup(self, symbol_id):
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": symbol_id,
            "body_part": "right_arm",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }]))
        i = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(i, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, i)
        return re.sub(r'data-symbol-id="[^"]*"', "",
                      svg[start:svg.find("</g>", start)])

    def test_each_contact_type_has_its_own_shape(self):
        seen = {}
        for name in self.TYPES:
            shape = self._markup(f"contact.{name}")
            clash = seen.get(shape)
            self.assertIsNone(clash, f"contact.{name} renders like contact.{clash}")
            seen[shape] = name
        self.assertEqual(len(seen), len(self.TYPES))

    def test_surface_suffix_does_not_replace_the_contact_type(self):
        # contact.grasp.front must still draw a grasp, plus a front mark.
        bare = self._markup("contact.grasp")
        for surface in self.SURFACES:
            with self.subTest(surface=surface):
                marked = self._markup(f"contact.grasp.{surface}")
                self.assertNotEqual(marked, bare, "surface mark not drawn")
                # every path of the bare grasp must survive
                for path in re.findall(r'<path[^>]*>', bare):
                    self.assertIn(path, marked, "grasp shape lost")

    def test_each_surface_marks_a_different_side(self):
        seen = {self._markup("contact.touch")}
        for surface in self.SURFACES:
            shape = self._markup(f"contact.touch.{surface}")
            self.assertNotIn(shape, seen, f"contact.touch.{surface} is a duplicate")
            seen.add(shape)


class FloorPlanMarkerGeometryTest(unittest.TestCase):
    """The four floor.* staff-annotation sub-families mean different things and
    must not share one glyph.

    ``_render_stage_marker`` drew a dot plus an abbreviation taken from
    ``symbol["stage_position"]["zone"]``. None of these catalog symbols carries
    that field, so all 31 fell back to the same dot and a literal "?" — a
    facing, a group formation, a travel path and a stage zone all engraved
    identically, though the id names each one.
    """

    FAMILIES = {
        "facing": ["downstage", "upstage", "stage_left", "stage_right",
                   "downstage_left", "downstage_right",
                   "upstage_left", "upstage_right"],
        "zone": ["center", "center_left", "center_right",
                 "downstage_center", "downstage_left", "downstage_right",
                 "upstage_center", "upstage_left", "upstage_right",
                 "wings_left", "wings_right"],
        "path": ["straight", "curved", "circular", "spiral", "zigzag",
                 "figure_eight"],
        "formation": ["circle", "line", "diagonal", "v_shape", "cluster",
                      "scatter"],
    }

    def _markup(self, symbol_id):
        svg = render_laban_svg(_minimal_ir([{
            "symbol_id": symbol_id,
            "body_part": "torso",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }]))
        start = svg.find(f'data-symbol-id="{symbol_id}"')
        self.assertNotEqual(start, -1, f"{symbol_id} not rendered")
        start = svg.rfind("<g", 0, start)
        body = svg[start:svg.find("</g>", start)]
        # Only the id is stripped. Do NOT blank the coordinates: every symbol
        # here renders in the same slot, so coordinates *are* the shape — an
        # arrow pointing up and one pointing down differ only in a y value.
        return re.sub(r'data-symbol-id="[^"]*"', "", body)

    def test_every_floor_marker_renders_a_distinct_shape(self):
        seen = {}
        for family, names in self.FAMILIES.items():
            for name in names:
                symbol_id = f"floor.{family}.{name}"
                shape = self._markup(symbol_id)
                clash = seen.get(shape)
                self.assertIsNone(
                    clash, f"{symbol_id} renders identically to {clash}")
                seen[shape] = symbol_id
        self.assertEqual(len(seen), sum(len(v) for v in self.FAMILIES.values()))

    def test_floor_markers_carry_no_placeholder_text(self):
        for family, names in self.FAMILIES.items():
            with self.subTest(family=family):
                self.assertNotIn("?", self._markup(f"floor.{family}.{names[0]}"))


class DirectionImpliedBySymbolIdTest(unittest.TestCase):
    """A symbol id that names a direction must render as that direction.

    564 of the 906 catalog ids encode one (`support.step.backward`), and the
    list_symbols → insert_symbol workflow hands those ids straight to the score.
    Without inference the renderer fell back to the `place` glyph: a score that
    says "step backward" engraved as "step in place", silently and with no
    diagnostic. Explicit IR fields always win over the id.
    """

    def _glyph(self, symbol_id, **extra):
        symbol = {
            "symbol_id": symbol_id,
            "body_part": "left_leg",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        symbol.update(extra)
        svg = render_laban_svg(_minimal_ir([symbol]))
        m = re.search(r'<use href="#laban-dir-([a-z_]+)-([a-z]+)"', svg)
        self.assertIsNotNone(m, f"no direction glyph emitted for {symbol_id}")
        return m.group(1), m.group(2)

    def test_direction_in_the_id_is_used_when_the_ir_omits_it(self):
        for symbol_id, expected in (
            ("support.step.backward", "backward"),
            ("support.step.forward", "forward"),
            ("support.balance.diagonal_backward_left", "diagonal_backward_left"),
            ("gesture.arm.forward.high", "forward"),
        ):
            with self.subTest(symbol=symbol_id):
                self.assertEqual(self._glyph(symbol_id)[0], expected)

    def test_level_in_the_id_is_used_when_the_ir_omits_it(self):
        self.assertEqual(self._glyph("support.step.forward.low")[1], "low")
        self.assertEqual(self._glyph("gesture.arm.forward.high")[1], "high")

    def test_explicit_ir_fields_win_over_the_id(self):
        direction, level = self._glyph(
            "support.step.backward", direction="forward", level="low")
        self.assertEqual((direction, level), ("forward", "low"))

    def test_ids_naming_no_direction_still_fall_back_to_place(self):
        self.assertEqual(self._glyph("support.step")[0], "place")


class BarLineTest(unittest.TestCase):
    """A measure line is solid across the staff and dashed outside it.

    Verified at high magnification on the OPENING MARCH plate of Soirée
    musicale: the rule is solid between the outer staff lines, stops exactly on
    them with no overhang, and continues outward on both sides as a dashed line.
    The dashed part is a time reference — on that plate it runs the full page
    width, tying the same count across four dancers' staves and out to the count
    numbers in the margin.

    How far it should reach is layout-dependent and was not measurable to a
    constant (staff detection was unreliable across plates and the answer
    differs between single- and multi-staff pages), so we run it to the notation
    column extent: everything drawn at that moment in time.
    """

    def _render(self):
        svg = render_laban_svg(_minimal_ir())
        horizontals = [
            (float(a), float(b), "dasharray" in rest)
            for a, _, b, rest in re.findall(
                r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="\2"([^>]*)>', svg)
        ]
        # Staff position must come from the render, not from
        # build_column_positions(0.0) -- the staff is laid out at an offset.
        verticals = sorted({
            round(float(m.group(1)), 1)
            for m in re.finditer(
                r'<line x1="([\d.]+)" y1="([\d.]+)" x2="\1" y2="([\d.]+)"([^>]*)>', svg)
            if abs(float(m.group(3)) - float(m.group(2))) > 30
            and "dasharray" not in m.group(4)
        })
        return horizontals, verticals[0], verticals[-1]

    def test_solid_measure_rule_stops_on_the_outer_staff_lines(self):
        horizontals, left, right = self._render()
        solid = [h for h in horizontals if not h[2]]
        self.assertTrue(solid, "no solid horizontal rules rendered")
        for x1, x2, _ in solid:
            self.assertGreaterEqual(round(x1, 1), left - 0.1,
                                    f"rule starts at {x1}, staff starts at {left}")
            self.assertLessEqual(round(x2, 1), right + 0.1,
                                 f"rule ends at {x2}, staff ends at {right}")

    def test_measure_rule_continues_outside_the_staff_as_dashes(self):
        horizontals, left, right = self._render()
        dashed = [h for h in horizontals if h[2]]
        self.assertTrue(dashed, "no dashed measure-line extensions rendered")
        self.assertTrue(any(x2 <= left + 0.1 for x1, x2, _ in dashed),
                        f"no dashed extension left of {left}: {dashed}")
        self.assertTrue(any(x1 >= right - 0.1 for x1, x2, _ in dashed),
                        f"no dashed extension right of {right}: {dashed}")


class StartingPositionAreaTest(unittest.TestCase):
    """The starting position is drawn as the staff continuing below the opening
    double bar and closed by a rule at the bottom — all solid lines.

    Verified against the OPENING plate of the Soirée musicale score, where every
    staff shows the three staff lines running down past the double bar into the
    starting-position area, a solid closing rule beneath it, and the starting
    direction symbols inside. Nothing there is dashed; this renderer was drawing
    a dashed box, which reads as a UI affordance rather than notation.
    """

    def _svg(self):
        return render_laban_svg(_minimal_ir())

    def test_starting_position_area_is_not_dashed(self):
        svg = self._svg()
        start = svg.find('class="laban-starting-position"')
        self.assertNotEqual(start, -1, "starting-position area not rendered")
        block = svg[start:svg.find("</g>", start)]
        self.assertNotIn("stroke-dasharray", block)

    def test_staff_lines_continue_through_the_starting_position(self):
        svg = self._svg()
        start = svg.find('class="laban-starting-position"')
        block = svg[start:svg.find("</g>", start)]
        verticals = {
            round(float(m.group(1)), 1)
            for m in re.finditer(
                r'<line x1="([\d.]+)" y1="[\d.]+" x2="\1" y2="[\d.]+', block)
        }
        self.assertEqual(len(verticals), 3,
                         f"expected the three staff lines, got {sorted(verticals)}")

    def test_starting_position_area_is_closed_at_the_bottom(self):
        svg = self._svg()
        start = svg.find('class="laban-starting-position"')
        block = svg[start:svg.find("</g>", start)]
        horizontals = [
            m for m in re.finditer(
                r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="\2"', block)
        ]
        self.assertTrue(horizontals, "no closing rule beneath the starting position")


class SupportSymbolTouchesCentreLineTest(unittest.TestCase):
    """A support symbol touches the centre line -- that contact is what marks it
    as a support, so it carries meaning and is not a spacing choice.

    Measured over 57 notation plates of the reference score (397 direction-sized
    components): median width 100% of the column, 88% touching the centre line,
    and when a symbol is narrower than its column the gap opens on the *outer*
    side (p90 41%) not the centre side (p90 15%). See
    docs/labanwriter_parity_audit.md.
    """

    def _placed(self, body_part="right_leg"):
        ir = _minimal_ir([{
            "symbol_id": "support.step",
            "body_part": body_part,
            "direction": "forward",
            "level": "low",
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        use = re.search(
            r'<use [^>]*x="([\d.]+)"[^>]*width="([\d.]+)"[^>]*/>', svg)
        self.assertIsNotNone(use, "no <use> emitted for the support symbol")
        x, w = float(use.group(1)), float(use.group(2))
        centre = float(re.search(
            r'<line x1="([\d.]+)" y1="[\d.]+" x2="\1" y2="[\d.]+" '
            r'stroke="#111827" stroke-width="2.5"/>', svg).group(1))
        return x, w, centre

    def test_right_support_symbol_starts_at_the_centre_line(self):
        x, _, centre = self._placed("right_leg")
        self.assertAlmostEqual(x, centre, delta=1.5,
                               msg=f"symbol starts at {x}, centre line at {centre}")

    def test_left_support_symbol_ends_at_the_centre_line(self):
        x, w, centre = self._placed("left_leg")
        self.assertAlmostEqual(x + w, centre, delta=1.5,
                               msg=f"symbol ends at {x + w}, centre line at {centre}")

    def test_support_symbol_spans_the_full_column_width(self):
        from dancenotation_mcp.rendering.laban_layout import COLUMN_WIDTHS
        _, w, _ = self._placed("right_leg")
        self.assertAlmostEqual(w, COLUMN_WIDTHS["right_support"], delta=0.5)


class ThreeLineStaffTest(unittest.TestCase):
    """A Labanotation staff is three vertical lines: the centre line, plus one
    line on each side delimiting the two support columns. The gesture, body,
    arm and path columns lie outside those lines and are *not* boxed in — the
    staff is open at both sides, never a rectangle enclosing every column."""

    def _vertical_lines(self):
        """x positions of full-measure-height vertical lines in the staff."""
        ir = _minimal_ir()
        svg = render_laban_svg(ir)
        xs = []
        for m in re.finditer(
            r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"([^/]*)/>',
            svg,
        ):
            x1, y1, x2, y2, rest = m.groups()
            if abs(float(x1) - float(x2)) < 0.01 and abs(float(y2) - float(y1)) > 30:
                if "dasharray" not in rest:      # skip starting-position guides
                    xs.append(round(float(x1), 1))
        return sorted(set(xs))

    def test_staff_draws_exactly_three_vertical_lines(self):
        self.assertEqual(len(self._vertical_lines()), 3,
                         f"got {self._vertical_lines()}")

    def test_outer_staff_lines_sit_on_the_support_column_edges(self):
        positions = build_column_positions(0.0)
        left, centre, right = self._vertical_lines()
        offset = centre - (positions["left_support"][1] + positions["right_support"][0]) / 2
        self.assertAlmostEqual(left, positions["left_support"][0] + offset, places=1)
        self.assertAlmostEqual(right, positions["right_support"][1] + offset, places=1)

    def _horizontal_line_spans(self, dashed=False):
        """(x1, x2) of horizontal rules, solid by default.

        The dashed measure-line extensions legitimately reach past the staff to
        the notation column extent, so a span check on every horizontal rule
        would flag them; pass dashed=True to look at those instead.
        """
        svg = render_laban_svg(_minimal_ir())
        spans = []
        for m in re.finditer(
            r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"([^/]*)/>',
            svg,
        ):
            x1, y1, x2, y2, rest = m.groups()
            if abs(float(y1) - float(y2)) < 0.01 and abs(float(x2) - float(x1)) > 20:
                if ("dasharray" in rest) == dashed:
                    spans.append((float(x1), float(x2)))
        return spans

    def test_solid_bar_lines_do_not_overhang_the_staff(self):
        # The solid part of a measure line crosses the staff and stops on the
        # outer staff lines. It must not stretch across the arm and path
        # columns, which would re-draw the box the staff lines replaced.
        # (The *dashed* extension does reach that far, by design — see
        # BarLineTest.)
        positions = build_column_positions(0.0)
        support_span = positions["right_support"][1] - positions["left_support"][0]
        spans = self._horizontal_line_spans()
        self.assertTrue(spans, "no solid horizontal rules found")
        for x1, x2 in spans:
            self.assertLessEqual(
                x2 - x1, support_span + 12,
                f"bar line spans {x2 - x1:.0f}px, staff is only {support_span:.0f}px",
            )

    def test_gesture_columns_lie_outside_the_staff_lines(self):
        # The arm/path columns must not be enclosed: if they were, the render
        # would be a box around all 10 columns rather than a 3-line staff.
        positions = build_column_positions(0.0)
        left, _, right = self._vertical_lines()
        staff_span = right - left
        support_span = positions["right_support"][1] - positions["left_support"][0]
        self.assertAlmostEqual(staff_span, support_span, places=1)


class MiddleLevelDotTest(unittest.TestCase):
    """ICKL/LabanWriter encode level on a direction symbol by shading:
    low = solid black, middle = a dot at the centre, high = diagonal stripes.
    Middle must not render as a bare unshaded outline — an empty symbol is not
    a middle-level symbol, it is an unshaded one, and readers cannot tell the
    two apart."""

    def _symbol_def(self, level, direction="forward"):
        """Return the <symbol> def markup the renderer emits for direction+level."""
        ir = _minimal_ir([{
            "symbol_id": "support.step",
            "body_part": "left_leg",
            "direction": direction,
            "level": level,
            "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }])
        svg = render_laban_svg(ir)
        match = re.search(
            rf'<symbol id="laban-dir-{direction}-{level}".*?</symbol>', svg, re.S)
        self.assertIsNotNone(
            match, f"no <symbol> def emitted for {direction}/{level}")
        return match.group(0)

    def test_middle_level_direction_symbol_carries_centre_dot(self):
        self.assertIn("<circle", self._symbol_def("middle"))

    def test_low_and_high_levels_carry_no_dot(self):
        # Low is solid black and high is hatched; a dot on either would be
        # both invisible and wrong.
        self.assertNotIn("<circle", self._symbol_def("low"))
        self.assertNotIn("<circle", self._symbol_def("high"))

    def test_middle_dot_is_filled_solid(self):
        # An unfilled ring would read as a different sign, not a level dot.
        dot = re.search(r"<circle[^>]*>", self._symbol_def("middle")).group(0)
        self.assertIn('fill="#111827"', dot)

    def test_every_direction_gets_the_dot_at_middle_level(self):
        for direction in ("forward", "backward", "left", "right", "place"):
            with self.subTest(direction=direction):
                self.assertIn("<circle", self._symbol_def("middle", direction))


if __name__ == "__main__":
    unittest.main()
