import json
import unittest
from pathlib import Path

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.rendering.tikz_renderer import render_tikz
from dancenotation_mcp.mcp_server.server import handle


ROOT = Path(__file__).resolve().parents[1]


class TikZRendererTests(unittest.TestCase):
    def test_render_tikz_produces_valid_document(self):
        plan = parse_phrase("step forward, turn right")
        ir = phrase_plan_to_ir(plan, "tikz test")
        tikz = render_tikz(ir)
        self.assertIn(r"\documentclass", tikz)
        self.assertIn(r"\begin{tikzpicture}", tikz)
        self.assertIn(r"\end{tikzpicture}", tikz)
        self.assertIn(r"\end{document}", tikz)

    def test_render_tikz_contains_symbol_blocks(self):
        plan = parse_phrase("step forward high, gesture left arm backward low")
        ir = phrase_plan_to_ir(plan, "symbols test")
        tikz = render_tikz(ir)
        self.assertIn("support.step", tikz)
        self.assertIn("gesture.arm", tikz)
        self.assertIn("% support.step", tikz)
        self.assertIn("% gesture.arm", tikz)

    def test_render_tikz_encodes_level_fills(self):
        plan = parse_phrase("step forward high, step backward low, turn right middle")
        ir = phrase_plan_to_ir(plan, "levels test")
        tikz = render_tikz(ir)
        self.assertIn(r"\fill[white]", tikz)
        self.assertIn(r"\fill[fill=black]", tikz)
        self.assertIn("north east lines", tikz)

    def test_render_tikz_includes_lane_labels(self):
        plan = parse_phrase("step forward")
        ir = phrase_plan_to_ir(plan, "lanes test")
        tikz = render_tikz(ir)
        self.assertIn("Left Arm", tikz)
        self.assertIn("Right Leg", tikz)
        self.assertIn("Torso", tikz)
        self.assertIn("Support", tikz)
        self.assertIn("Repeat", tikz)

    def test_render_tikz_includes_measure_grid(self):
        plan = parse_phrase("step forward, step backward, step left, step right, jump high")
        ir = phrase_plan_to_ir(plan, "measures test")
        tikz = render_tikz(ir)
        self.assertIn("M1", tikz)
        self.assertIn("M2", tikz)
        self.assertIn("beat grid", tikz)

    def test_render_tikz_includes_tikz_styles(self):
        plan = parse_phrase("step forward")
        ir = phrase_plan_to_ir(plan, "styles test")
        tikz = render_tikz(ir)
        self.assertIn("laban staff/.style", tikz)
        self.assertIn("laban shape/.style", tikz)
        self.assertIn("attachment line/.style", tikz)
        self.assertIn(r"\usetikzlibrary{patterns", tikz)

    def test_render_tikz_with_golden_fixture(self):
        fixture_path = ROOT / "fixtures" / "golden_official_family_score.json"
        ir = json.loads(fixture_path.read_text(encoding="utf-8"))
        tikz = render_tikz(ir)
        self.assertIn(r"\begin{tikzpicture}", tikz)
        self.assertIn("Golden Official Families", tikz)
        self.assertGreater(len(tikz), 5000)

    def test_render_tikz_with_music_headers(self):
        plan = parse_phrase("3/4 time, tempo 120, step forward")
        ir = phrase_plan_to_ir(plan, "headers test")
        tikz = render_tikz(ir)
        self.assertIn("header card", tikz)
        self.assertIn("3/4", tikz)

    def test_render_tikz_with_attachments(self):
        ir = {
            "metadata": {"title": "Attach", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {"symbol_id": "support.step.forward", "body_part": "left_leg", "direction": "forward", "level": "middle", "timing": {"measure": 1, "beat": 1, "duration_beats": 1}, "modifiers": {}},
                {"symbol_id": "quality.strong", "body_part": "left_leg", "direction": "forward", "level": "middle", "timing": {"measure": 1, "beat": 1, "duration_beats": 1}, "modifiers": {"attach_to": "support.step.forward"}},
            ],
        }
        tikz = render_tikz(ir)
        self.assertIn("attachment line", tikz)

    def test_mcp_render_tikz_tool(self):
        plan = parse_phrase("step forward")
        ir = phrase_plan_to_ir(plan, "mcp test")
        resp = handle({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "render_tikz", "arguments": {"ir": ir}},
        })
        self.assertIn("result", resp)
        tikz = resp["result"]["content"][0]["json"]["tikz"]
        self.assertIn(r"\begin{tikzpicture}", tikz)

    def test_mcp_tools_list_has_schemas(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        for tool in tools:
            self.assertIn("inputSchema", tool)
            self.assertNotEqual(tool["inputSchema"], {"type": "object"}, f"{tool['name']} has empty schema")
            self.assertIn("properties", tool["inputSchema"], f"{tool['name']} missing properties")

    def test_mcp_initialize_has_capabilities(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertIn("capabilities", resp["result"])
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_mcp_notifications_initialized_does_not_error(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "notifications/initialized"})
        self.assertNotIn("error", resp)


    def test_render_tikz_direction_shapes_are_draw_paths(self):
        """Direction symbols use \\draw with cycle (closed paths), not \\node with glyphs."""
        plan = parse_phrase("step forward high, step backward low")
        ir = phrase_plan_to_ir(plan, "draw paths test")
        tikz = render_tikz(ir)
        self.assertIn("cycle", tikz)
        self.assertIn("laban shape", tikz)

    def test_render_tikz_no_unicode_direction_glyphs(self):
        """TikZ output must not contain Unicode geometric characters."""
        plan = parse_phrase("step forward, step backward, step left, step right, gesture left arm diagonal forward right")
        ir = phrase_plan_to_ir(plan, "no unicode test")
        tikz = render_tikz(ir)
        unicode_glyphs = "▲▼◀▶◢◣◥◤●◆◮◭"
        for glyph in unicode_glyphs:
            self.assertNotIn(glyph, tikz, f"Found Unicode glyph {glyph!r} in TikZ output")

    def test_render_tikz_all_directions_produce_distinct_paths(self):
        """Each direction produces a unique set of vertices."""
        from dancenotation_mcp.rendering.tikz_renderer import _tikz_direction_vertices
        directions = [
            "forward", "backward", "left", "right",
            "diagonal_forward_left", "diagonal_forward_right",
            "diagonal_backward_left", "diagonal_backward_right",
            "place",
        ]
        paths = set()
        for d in directions:
            verts = _tikz_direction_vertices(d, 0, 0, 40, 60)
            path = " -- ".join(verts)
            paths.add(path)
        self.assertEqual(len(paths), len(directions), "Some directions produce identical TikZ paths")


if __name__ == "__main__":
    unittest.main()
