"""Tests for the 10 direct-manipulation MCP tools."""

import re
import unittest

from dancenotation_mcp.mcp_server.server import handle


def _call(tool_name: str, arguments: dict) -> dict:
    """Helper: invoke a tool via the MCP JSON-RPC handler and return the response."""
    return handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    })


def _ok(resp: dict) -> dict:
    """Extract the successful JSON payload from a tool response."""
    return resp["result"]["content"][0]["json"]


def _err(resp: dict) -> str:
    """Extract the error message from a failed tool response."""
    return resp["error"]["data"]["error"]


def _make_ir(symbols=None, extensions=None, title="Test"):
    """Build a minimal valid IR dict."""
    return {
        "metadata": {
            "title": title,
            "source_prompt": "",
            "ir_version": "0.2.0",
            "schema_version": "0.2.0",
        },
        "symbols": symbols or [],
        "extensions": extensions or {},
    }


def _sample_symbol(symbol_id="support.step", body_part="right_leg",
                    measure=1, beat=1.0, duration_beats=1.0,
                    direction="forward", level="middle"):
    return {
        "symbol_id": symbol_id,
        "body_part": body_part,
        "direction": direction,
        "level": level,
        "timing": {"measure": measure, "beat": beat, "duration_beats": duration_beats},
        "modifiers": {},
        "rotation_degrees": None,
        "flexion_degrees": None,
        "stage_position": None,
        "facing": None,
        "retention": None,
    }


# ── 1. list_symbols ─────────────────────────────────────────────────

class TestListSymbols(unittest.TestCase):

    def test_filter_by_category(self):
        data = _ok(_call("list_symbols", {"category": "support"}))
        self.assertGreater(data["count"], 0)
        for sym in data["symbols"]:
            self.assertEqual(sym["family"], "support")

    def test_filter_by_search_substring(self):
        data = _ok(_call("list_symbols", {"search": "step"}))
        self.assertGreater(data["count"], 0)
        for sym in data["symbols"]:
            self.assertTrue(
                "step" in sym["symbol_id"].lower() or "step" in sym["display_name"].lower()
            )

    def test_filter_by_body_part(self):
        data = _ok(_call("list_symbols", {"body_part": "left_arm"}))
        self.assertGreater(data["count"], 0)

    def test_empty_results_for_nonexistent_category(self):
        data = _ok(_call("list_symbols", {"category": "nonexistent_category_xyz"}))
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["symbols"], [])

    def test_combined_filters(self):
        data = _ok(_call("list_symbols", {"category": "support", "search": "step"}))
        self.assertGreater(data["count"], 0)
        for sym in data["symbols"]:
            self.assertEqual(sym["family"], "support")

    def test_invalid_body_part_raises_error(self):
        resp = _call("list_symbols", {"body_part": "INVALID_PART"})
        self.assertIn("error", resp)
        self.assertIn("Invalid body_part", _err(resp))

    def test_no_filters_returns_all(self):
        data = _ok(_call("list_symbols", {}))
        self.assertGreater(data["count"], 100)


# ── 2. insert_symbol ────────────────────────────────────────────────

class TestInsertSymbol(unittest.TestCase):

    def test_valid_insert(self):
        ir = _make_ir()
        result = _ok(_call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "right_leg",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 2.0,
            "direction": "forward",
            "level": "middle",
        }))
        self.assertEqual(len(result["symbols"]), 1)
        sym = result["symbols"][0]
        self.assertEqual(sym["symbol_id"], "support.step")
        self.assertEqual(sym["body_part"], "right_leg")
        self.assertEqual(sym["timing"]["duration_beats"], 2.0)
        self.assertEqual(sym["direction"], "forward")

    def test_insert_appends_to_existing_symbols(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        result = _ok(_call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "left_leg",
            "measure": 1,
            "beat": 2.0,
            "duration_beats": 1.0,
        }))
        self.assertEqual(len(result["symbols"]), 2)

    def test_invalid_symbol_id(self):
        ir = _make_ir()
        resp = _call("insert_symbol", {
            "ir": ir,
            "symbol_id": "totally.fake.symbol",
            "body_part": "right_leg",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("Unknown symbol_id", _err(resp))

    def test_invalid_body_part(self):
        ir = _make_ir()
        resp = _call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "FAKE_BODY_PART",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid body_part", _err(resp))

    def test_body_part_not_in_allowed_list(self):
        ir = _make_ir()
        # gesture.arm only allows left_arm, right_arm — not left_leg
        resp = _call("insert_symbol", {
            "ir": ir,
            "symbol_id": "gesture.arm",
            "body_part": "left_leg",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("not allowed", _err(resp))

    def test_invalid_measure(self):
        ir = _make_ir()
        resp = _call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "right_leg",
            "measure": 0,
            "beat": 1.0,
            "duration_beats": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("measure must be >= 1", _err(resp))

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir()
        original_len = len(ir["symbols"])
        _ok(_call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "right_leg",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 1.0,
        }))
        self.assertEqual(len(ir["symbols"]), original_len)

    def test_insert_with_modifiers(self):
        ir = _make_ir()
        result = _ok(_call("insert_symbol", {
            "ir": ir,
            "symbol_id": "support.step",
            "body_part": "right_leg",
            "measure": 1,
            "beat": 1.0,
            "duration_beats": 1.0,
            "modifiers": {"source_text": "plie"},
        }))
        self.assertEqual(result["symbols"][0]["modifiers"]["source_text"], "plie")


# ── 3. remove_symbol ────────────────────────────────────────────────

class TestRemoveSymbol(unittest.TestCase):

    def test_remove_by_index(self):
        ir = _make_ir(symbols=[
            _sample_symbol(body_part="right_leg"),
            _sample_symbol(body_part="left_leg"),
        ])
        result = _ok(_call("remove_symbol", {"ir": ir, "index": 0}))
        self.assertEqual(len(result["symbols"]), 1)
        self.assertEqual(result["symbols"][0]["body_part"], "left_leg")

    def test_remove_by_symbol_id(self):
        ir = _make_ir(symbols=[
            _sample_symbol(symbol_id="support.step"),
            _sample_symbol(symbol_id="gesture.arm", body_part="left_arm"),
        ])
        result = _ok(_call("remove_symbol", {"ir": ir, "symbol_id": "gesture.arm"}))
        self.assertEqual(len(result["symbols"]), 1)
        self.assertEqual(result["symbols"][0]["symbol_id"], "support.step")

    def test_remove_invalid_index(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("remove_symbol", {"ir": ir, "index": 5})
        self.assertIn("error", resp)
        self.assertIn("out of range", _err(resp))

    def test_remove_negative_index(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("remove_symbol", {"ir": ir, "index": -1})
        self.assertIn("error", resp)
        self.assertIn("out of range", _err(resp))

    def test_remove_nonexistent_symbol_id(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("remove_symbol", {"ir": ir, "symbol_id": "does.not.exist"})
        self.assertIn("error", resp)
        self.assertIn("No symbol", _err(resp))

    def test_remove_without_index_or_symbol_id(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("remove_symbol", {"ir": ir})
        self.assertIn("error", resp)
        self.assertIn("Must provide", _err(resp))

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        _ok(_call("remove_symbol", {"ir": ir, "index": 0}))
        self.assertEqual(len(ir["symbols"]), 1)


# ── 4. update_symbol ────────────────────────────────────────────────

class TestUpdateSymbol(unittest.TestCase):

    def test_partial_update_direction(self):
        ir = _make_ir(symbols=[_sample_symbol(direction="forward")])
        result = _ok(_call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"direction": "backward"},
        }))
        self.assertEqual(result["symbols"][0]["direction"], "backward")
        # Other fields unchanged
        self.assertEqual(result["symbols"][0]["body_part"], "right_leg")

    def test_nested_timing_update(self):
        ir = _make_ir(symbols=[_sample_symbol(beat=1.0)])
        result = _ok(_call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"timing": {"beat": 3.0}},
        }))
        self.assertEqual(result["symbols"][0]["timing"]["beat"], 3.0)
        # measure and duration_beats should still be preserved
        self.assertEqual(result["symbols"][0]["timing"]["measure"], 1)
        self.assertEqual(result["symbols"][0]["timing"]["duration_beats"], 1.0)

    def test_nested_modifier_update(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        ir["symbols"][0]["modifiers"] = {"key1": "val1"}
        result = _ok(_call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"modifiers": {"key2": "val2"}},
        }))
        mods = result["symbols"][0]["modifiers"]
        self.assertEqual(mods["key1"], "val1")
        self.assertEqual(mods["key2"], "val2")

    def test_invalid_index(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("update_symbol", {
            "ir": ir, "index": 99, "updates": {"direction": "left"},
        })
        self.assertIn("error", resp)
        self.assertIn("out of range", _err(resp))

    def test_update_body_part_validates(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"body_part": "INVALID"},
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid body_part", _err(resp))

    def test_update_symbol_id_validates(self):
        ir = _make_ir(symbols=[_sample_symbol()])
        resp = _call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"symbol_id": "fake.nonexistent"},
        })
        self.assertIn("error", resp)
        self.assertIn("Unknown symbol_id", _err(resp))

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir(symbols=[_sample_symbol(direction="forward")])
        _ok(_call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"direction": "backward"},
        }))
        self.assertEqual(ir["symbols"][0]["direction"], "forward")


# ── 5. set_time_signature ────────────────────────────────────────────

class TestSetTimeSignature(unittest.TestCase):

    def test_set_4_4(self):
        ir = _make_ir()
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 4, "denominator": 4,
        }))
        ts = result["extensions"]["time_signatures"]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0], {"measure": 1, "numerator": 4, "denominator": 4})

    def test_set_7_8(self):
        ir = _make_ir()
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 7, "denominator": 8,
        }))
        self.assertEqual(result["extensions"]["time_signatures"][0]["numerator"], 7)
        self.assertEqual(result["extensions"]["time_signatures"][0]["denominator"], 8)

    def test_set_5_4(self):
        ir = _make_ir()
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 5, "denominator": 4,
        }))
        self.assertEqual(result["extensions"]["time_signatures"][0]["numerator"], 5)

    def test_invalid_denominator(self):
        ir = _make_ir()
        resp = _call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 4, "denominator": 3,
        })
        self.assertIn("error", resp)
        self.assertIn("denominator must be one of", _err(resp))

    def test_update_existing_time_signature(self):
        ir = _make_ir(extensions={
            "time_signatures": [{"measure": 1, "numerator": 4, "denominator": 4}],
        })
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 3, "denominator": 4,
        }))
        ts = result["extensions"]["time_signatures"]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0]["numerator"], 3)

    def test_add_second_time_signature(self):
        ir = _make_ir(extensions={
            "time_signatures": [{"measure": 1, "numerator": 4, "denominator": 4}],
        })
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 5, "numerator": 6, "denominator": 8,
        }))
        ts = result["extensions"]["time_signatures"]
        self.assertEqual(len(ts), 2)
        self.assertEqual(ts[0]["measure"], 1)
        self.assertEqual(ts[1]["measure"], 5)

    def test_time_signatures_sorted_by_measure(self):
        ir = _make_ir()
        ir = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 5, "numerator": 3, "denominator": 4,
        }))
        result = _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 4, "denominator": 4,
        }))
        ts = result["extensions"]["time_signatures"]
        self.assertEqual(ts[0]["measure"], 1)
        self.assertEqual(ts[1]["measure"], 5)

    def test_invalid_measure(self):
        ir = _make_ir()
        resp = _call("set_time_signature", {
            "ir": ir, "measure": 0, "numerator": 4, "denominator": 4,
        })
        self.assertIn("error", resp)
        self.assertIn("measure must be >= 1", _err(resp))

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir()
        _ok(_call("set_time_signature", {
            "ir": ir, "measure": 1, "numerator": 3, "denominator": 4,
        }))
        self.assertEqual(ir.get("extensions", {}), {})


# ── 6. add_floor_plan ───────────────────────────────────────────────

class TestAddFloorPlan(unittest.TestCase):

    def test_valid_entry(self):
        ir = _make_ir()
        result = _ok(_call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "center",
            "facing": "downstage",
        }))
        fp = result["extensions"]["floor_plan"]
        self.assertEqual(len(fp), 1)
        self.assertEqual(fp[0]["performer_id"], "dancer_1")
        self.assertEqual(fp[0]["position"]["zone"], "center")
        self.assertEqual(fp[0]["facing"], "downstage")

    def test_with_xy_coordinates(self):
        ir = _make_ir()
        result = _ok(_call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "downstage_left",
            "x": 0.5,
            "y": 0.3,
        }))
        pos = result["extensions"]["floor_plan"][0]["position"]
        self.assertEqual(pos["x"], 0.5)
        self.assertEqual(pos["y"], 0.3)

    def test_with_path_to_next(self):
        ir = _make_ir()
        result = _ok(_call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "center",
            "path_to_next": "curved",
        }))
        self.assertEqual(result["extensions"]["floor_plan"][0]["path_to_next"], "curved")

    def test_invalid_zone(self):
        ir = _make_ir()
        resp = _call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "INVALID_ZONE",
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid zone", _err(resp))

    def test_invalid_facing(self):
        ir = _make_ir()
        resp = _call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "center",
            "facing": "INVALID_FACING",
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid facing", _err(resp))

    def test_invalid_path_to_next(self):
        ir = _make_ir()
        resp = _call("add_floor_plan", {
            "ir": ir,
            "performer_id": "dancer_1",
            "measure": 1,
            "beat": 1.0,
            "zone": "center",
            "path_to_next": "teleport",
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid path_to_next", _err(resp))

    def test_multiple_entries(self):
        ir = _make_ir()
        ir = _ok(_call("add_floor_plan", {
            "ir": ir, "performer_id": "d1", "measure": 1, "beat": 1.0, "zone": "center",
        }))
        result = _ok(_call("add_floor_plan", {
            "ir": ir, "performer_id": "d2", "measure": 1, "beat": 1.0, "zone": "upstage_left",
        }))
        self.assertEqual(len(result["extensions"]["floor_plan"]), 2)

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir()
        _ok(_call("add_floor_plan", {
            "ir": ir, "performer_id": "d1", "measure": 1, "beat": 1.0, "zone": "center",
        }))
        self.assertNotIn("floor_plan", ir.get("extensions", {}))


# ── 7. add_effort_graph ─────────────────────────────────────────────

class TestAddEffortGraph(unittest.TestCase):
    """Regression coverage: add_effort_graph used to build a fake
    "quality.effort" symbol (not a real catalog symbol_id — always failed
    validation with "Unknown symbol id") with modifiers.weight/time/space/
    flow, but laban_renderer.py's effort-graph overlay reads a completely
    separate top-level ir["effort_graphs"] list with those same field names
    at the top level, not nested under "modifiers". Fixed to append there.
    """

    def test_all_four_qualities(self):
        ir = _make_ir()
        result = _ok(_call("add_effort_graph", {
            "ir": ir,
            "measure": 1,
            "beat": 1.0,
            "weight": "strong",
            "time": "sudden",
            "space": "direct",
            "flow": "bound",
        }))
        eg = result["effort_graphs"][0]
        self.assertEqual(eg["weight"], "strong")
        self.assertEqual(eg["time"], "sudden")
        self.assertEqual(eg["space"], "direct")
        self.assertEqual(eg["flow"], "bound")
        self.assertEqual(eg["measure"], 1)

    def test_partial_qualities(self):
        ir = _make_ir()
        result = _ok(_call("add_effort_graph", {
            "ir": ir,
            "measure": 2,
            "beat": 1.0,
            "weight": "light",
        }))
        eg = result["effort_graphs"][0]
        self.assertEqual(eg["weight"], "light")
        self.assertNotIn("time", eg)
        self.assertNotIn("space", eg)
        self.assertNotIn("flow", eg)

    def test_empty_qualities(self):
        ir = _make_ir()
        result = _ok(_call("add_effort_graph", {
            "ir": ir,
            "measure": 1,
            "beat": 1.0,
        }))
        eg = result["effort_graphs"][0]
        for key in ("weight", "time", "space", "flow"):
            self.assertNotIn(key, eg)

    def test_symbol_index_attaches_to_existing_symbol(self):
        ir = _make_ir()
        result = _ok(_call("add_effort_graph", {
            "ir": ir,
            "measure": 1,
            "beat": 1.0,
            "weight": "strong",
            "symbol_index": 0,
        }))
        self.assertEqual(result["effort_graphs"][0]["symbol_index"], 0)

    def test_invalid_weight(self):
        ir = _make_ir()
        resp = _call("add_effort_graph", {
            "ir": ir,
            "measure": 1,
            "beat": 1.0,
            "weight": "INVALID",
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid weight", _err(resp))

    def test_symbol_id_is_never_used_for_effort_graphs(self):
        """effort_graphs entries have no symbol_id at all — they're not
        catalog symbols, so there's nothing that could fail "Unknown
        symbol id" validation.
        """
        from dancenotation_mcp.validation.validator import validate_ir
        ir = _make_ir()
        result = _ok(_call("add_effort_graph", {"ir": ir, "measure": 1, "beat": 1.0, "weight": "strong"}))
        validation = validate_ir(result)
        messages = [i["message"] for i in validation.get("issues", [])]
        self.assertFalse(any("Unknown symbol id" in m for m in messages))

    def test_invalid_measure(self):
        ir = _make_ir()
        resp = _call("add_effort_graph", {
            "ir": ir,
            "body_part": "torso",
            "measure": 0,
            "beat": 1.0,
            "duration_beats": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("measure must be >= 1", _err(resp))

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir()
        _ok(_call("add_effort_graph", {
            "ir": ir, "body_part": "torso", "measure": 1, "beat": 1.0, "duration_beats": 1.0,
        }))
        self.assertEqual(len(ir["symbols"]), 0)


# ── 8. create_empty_score ────────────────────────────────────────────

class TestCreateEmptyScore(unittest.TestCase):

    def test_default_score(self):
        result = _ok(_call("create_empty_score", {"title": "My Score"}))
        self.assertEqual(result["metadata"]["title"], "My Score")
        self.assertEqual(result["metadata"]["ir_version"], "0.2.0")
        self.assertEqual(result["symbols"], [])
        # No time_signatures for default 4/4
        self.assertNotIn("time_signatures", result.get("extensions", {}))

    def test_with_custom_time_signature(self):
        result = _ok(_call("create_empty_score", {
            "title": "Waltz", "time_sig_num": 3, "time_sig_den": 4,
        }))
        ts = result["extensions"]["time_signatures"]
        self.assertEqual(len(ts), 1)
        self.assertEqual(ts[0]["numerator"], 3)
        self.assertEqual(ts[0]["denominator"], 4)

    def test_with_tempo(self):
        """Regression: "timing.tempo" isn't a real catalog symbol_id (same
        bug class as add_retention/add_effort_graph) — the real tempo-mark
        family is "music.tempo.mark", read via modifiers.tempo (not "bpm").
        """
        result = _ok(_call("create_empty_score", {
            "title": "Fast", "tempo": 140,
        }))
        tempo_symbols = [s for s in result["symbols"] if s["symbol_id"] == "music.tempo.mark"]
        self.assertEqual(len(tempo_symbols), 1)
        self.assertEqual(tempo_symbols[0]["modifiers"]["tempo"], 140)
        self.assertTrue(tempo_symbols[0]["modifiers"]["measure_header"])

    def test_tempo_symbol_id_exists_in_catalog(self):
        from dancenotation_mcp.ir.catalog import load_symbol_catalog
        result = _ok(_call("create_empty_score", {"title": "Fast", "tempo": 140}))
        catalog = load_symbol_catalog()
        tempo_symbol = next(s for s in result["symbols"] if "tempo" in s["symbol_id"])
        self.assertIn(tempo_symbol["symbol_id"], catalog)

    def test_default_4_4_no_time_sig_extension(self):
        result = _ok(_call("create_empty_score", {
            "title": "Default", "time_sig_num": 4, "time_sig_den": 4,
        }))
        self.assertNotIn("time_signatures", result.get("extensions", {}))

    def test_6_8_time_signature(self):
        result = _ok(_call("create_empty_score", {
            "title": "Compound", "time_sig_num": 6, "time_sig_den": 8,
        }))
        ts = result["extensions"]["time_signatures"][0]
        self.assertEqual(ts["numerator"], 6)
        self.assertEqual(ts["denominator"], 8)

    def test_score_has_valid_structure(self):
        result = _ok(_call("create_empty_score", {"title": "Structural"}))
        self.assertIn("metadata", result)
        self.assertIn("symbols", result)
        self.assertIn("extensions", result)
        self.assertIsInstance(result["symbols"], list)
        self.assertIsInstance(result["extensions"], dict)


# ── 9. add_retention ────────────────────────────────────────────────

class TestAddRetention(unittest.TestCase):

    def test_hold(self):
        ir = _make_ir()
        result = _ok(_call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "left_arm",
            "measure": 1, "beat": 2.0, "duration_beats": 2.0,
        }))
        sym = result["symbols"][0]
        # Regression: "timing.retention.hold" doesn't exist anywhere in the
        # catalog, so every add_retention symbol used to fail validation
        # with "Unknown symbol id". The real catalog family is
        # "retention.{type}.{body_category}".
        self.assertEqual(sym["symbol_id"], "retention.hold.arm")
        self.assertEqual(sym["retention"], "hold")
        self.assertEqual(sym["body_part"], "left_arm")
        self.assertEqual(sym["timing"]["duration_beats"], 2.0)

    def test_hold_symbol_id_exists_in_catalog(self):
        from dancenotation_mcp.ir.catalog import load_symbol_catalog
        ir = _make_ir()
        result = _ok(_call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "left_arm",
            "measure": 1, "beat": 1.0,
        }))
        catalog = load_symbol_catalog()
        self.assertIn(result["symbols"][0]["symbol_id"], catalog)

    def test_release(self):
        ir = _make_ir()
        result = _ok(_call("add_retention", {
            "ir": ir, "type": "release", "body_part": "right_leg",
            "measure": 2, "beat": 1.0,
        }))
        sym = result["symbols"][0]
        self.assertEqual(sym["symbol_id"], "retention.release.leg")
        self.assertEqual(sym["retention"], "release")

    def test_cancel(self):
        ir = _make_ir()
        result = _ok(_call("add_retention", {
            "ir": ir, "type": "cancel", "body_part": "torso",
            "measure": 3, "beat": 1.0,
        }))
        self.assertEqual(result["symbols"][0]["retention"], "cancel")

    def test_every_accepted_type_produces_a_score_that_validates(self):
        """Whatever the tool accepts, the validator must accept.

        The retention type is whitelisted in three places — the tool, the MCP
        schema enum, and the validator — and adding space_hold and spot_hold
        to the first two left the third behind, so the tool cheerfully built
        a score that failed validation with INVALID_RETENTION. Enumerating the
        tool's own list here means the next type added cannot repeat it.
        """
        from dancenotation_mcp.validation.validator import (
            RETENTION_TYPES, validate_ir)
        self.assertGreaterEqual(len(RETENTION_TYPES), 3, "type list looks wrong")

        for retention_type in RETENTION_TYPES:
            with self.subTest(type=retention_type):
                result = _ok(_call("add_retention", {
                    "ir": _make_ir(), "type": retention_type,
                    "body_part": "left_arm", "measure": 1, "beat": 2.0,
                }))
                errors = [i for i in validate_ir(result)["issues"]
                          if i["severity"] == "error"]
                self.assertEqual(
                    errors, [],
                    f"add_retention accepts '{retention_type}' but the score "
                    f"it builds does not validate: "
                    + "; ".join(i["message"] for i in errors))

    def test_invalid_type(self):
        ir = _make_ir()
        resp = _call("add_retention", {
            "ir": ir, "type": "INVALID", "body_part": "left_arm",
            "measure": 1, "beat": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid retention type", _err(resp))

    def test_invalid_body_part(self):
        ir = _make_ir()
        resp = _call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "INVALID",
            "measure": 1, "beat": 1.0,
        })
        self.assertIn("error", resp)
        self.assertIn("Invalid body_part", _err(resp))

    def test_default_duration(self):
        ir = _make_ir()
        result = _ok(_call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "left_arm",
            "measure": 1, "beat": 1.0,
        }))
        self.assertEqual(result["symbols"][0]["timing"]["duration_beats"], 1.0)

    def test_does_not_mutate_original_ir(self):
        ir = _make_ir()
        _ok(_call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "left_arm",
            "measure": 1, "beat": 1.0,
        }))
        self.assertEqual(len(ir["symbols"]), 0)


# ── 10. get_score_summary ───────────────────────────────────────────

class TestGetScoreSummary(unittest.TestCase):

    def test_empty_score(self):
        ir = _make_ir()
        result = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertEqual(result["total_symbols"], 0)
        self.assertEqual(result["measures"], 0)
        self.assertEqual(result["body_parts_used"], [])
        self.assertEqual(result["families_used"], [])
        self.assertEqual(result["time_signatures"], [])

    def test_populated_score(self):
        ir = _make_ir(symbols=[
            _sample_symbol(symbol_id="support.step", body_part="right_leg", measure=1),
            _sample_symbol(symbol_id="support.step", body_part="left_leg", measure=2),
            _sample_symbol(symbol_id="gesture.arm", body_part="left_arm", measure=3),
        ])
        result = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertEqual(result["total_symbols"], 3)
        self.assertEqual(result["measures"], 3)
        self.assertIn("right_leg", result["body_parts_used"])
        self.assertIn("left_leg", result["body_parts_used"])
        self.assertIn("left_arm", result["body_parts_used"])
        self.assertIn("support", result["families_used"])
        self.assertIn("gesture", result["families_used"])

    def test_with_time_signatures(self):
        ir = _make_ir(extensions={
            "time_signatures": [
                {"measure": 1, "numerator": 4, "denominator": 4},
                {"measure": 5, "numerator": 3, "denominator": 4},
            ],
        })
        result = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertEqual(len(result["time_signatures"]), 2)

    def test_families_derived_from_symbol_id_prefix(self):
        ir = _make_ir(symbols=[{
            "symbol_id": "custom.unknown.symbol",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {"measure": 1, "beat": 1.0, "duration_beats": 1.0},
            "modifiers": {},
            "rotation_degrees": None,
            "flexion_degrees": None,
            "stage_position": None,
            "facing": None,
            "retention": None,
        }])
        result = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertIn("custom", result["families_used"])

    def test_body_parts_sorted(self):
        ir = _make_ir(symbols=[
            _sample_symbol(body_part="torso", symbol_id="direction.forward"),
            _sample_symbol(body_part="left_arm", symbol_id="gesture.arm"),
            _sample_symbol(body_part="right_leg"),
        ])
        result = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertEqual(result["body_parts_used"], sorted(result["body_parts_used"]))


# ── Integration: tools visible in tools/list ─────────────────────────

class TestToolsRegistered(unittest.TestCase):

    def test_all_10_new_tools_in_tools_list(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [t["name"] for t in resp["result"]["tools"]]
        expected = [
            "list_symbols", "insert_symbol", "remove_symbol", "update_symbol",
            "set_time_signature", "add_floor_plan", "add_effort_graph",
            "create_empty_score", "add_retention", "get_score_summary",
        ]
        for tool in expected:
            self.assertIn(tool, names, f"Tool '{tool}' not found in tools/list")

    def test_total_tool_count(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        # 8 original + 10 new + render_floor_plan + render_music + render_paired_score = 21
        self.assertEqual(len(tools), 21)

    def test_each_new_tool_has_input_schema(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        new_tools = [
            "list_symbols", "insert_symbol", "remove_symbol", "update_symbol",
            "set_time_signature", "add_floor_plan", "add_effort_graph",
            "create_empty_score", "add_retention", "get_score_summary",
        ]
        tools_by_name = {t["name"]: t for t in resp["result"]["tools"]}
        for name in new_tools:
            tool = tools_by_name[name]
            self.assertIn("inputSchema", tool, f"Tool '{name}' missing inputSchema")
            self.assertEqual(tool["inputSchema"]["type"], "object")


# ── Workflow: end-to-end composition ─────────────────────────────────

class TestEndToEndWorkflow(unittest.TestCase):

    def test_compose_score_from_scratch(self):
        """Create a score, set time sig, insert symbols, get summary."""
        # Step 1: Create empty score
        ir = _ok(_call("create_empty_score", {
            "title": "Test Waltz", "time_sig_num": 3, "time_sig_den": 4, "tempo": 120,
        }))

        # Step 2: Insert a step
        ir = _ok(_call("insert_symbol", {
            "ir": ir, "symbol_id": "support.step", "body_part": "right_leg",
            "measure": 1, "beat": 1.0, "duration_beats": 1.0,
            "direction": "forward", "level": "middle",
        }))

        # Step 3: Insert an arm gesture
        ir = _ok(_call("insert_symbol", {
            "ir": ir, "symbol_id": "gesture.arm", "body_part": "left_arm",
            "measure": 1, "beat": 1.0, "duration_beats": 2.0,
            "direction": "forward", "level": "high",
        }))

        # Step 4: Add retention
        ir = _ok(_call("add_retention", {
            "ir": ir, "type": "hold", "body_part": "left_arm",
            "measure": 1, "beat": 3.0, "duration_beats": 1.0,
        }))

        # Step 5: Add floor plan
        ir = _ok(_call("add_floor_plan", {
            "ir": ir, "performer_id": "dancer_1",
            "measure": 1, "beat": 1.0, "zone": "center",
            "facing": "downstage",
        }))

        # Step 6: Get summary
        summary = _ok(_call("get_score_summary", {"ir": ir}))
        self.assertEqual(summary["total_symbols"], 4)  # tempo + step + gesture + retention
        self.assertIn("right_leg", summary["body_parts_used"])
        self.assertIn("left_arm", summary["body_parts_used"])
        self.assertIn("support", summary["families_used"])
        self.assertIn("gesture", summary["families_used"])

    def test_insert_then_update_then_remove(self):
        """Insert a symbol, update it, then remove it."""
        ir = _ok(_call("create_empty_score", {"title": "Edit Test"}))

        # Insert
        ir = _ok(_call("insert_symbol", {
            "ir": ir, "symbol_id": "support.step", "body_part": "right_leg",
            "measure": 1, "beat": 1.0, "duration_beats": 1.0,
            "direction": "forward", "level": "low",
        }))
        self.assertEqual(len(ir["symbols"]), 1)

        # Update direction
        ir = _ok(_call("update_symbol", {
            "ir": ir, "index": 0, "updates": {"direction": "backward"},
        }))
        self.assertEqual(ir["symbols"][0]["direction"], "backward")

        # Remove
        ir = _ok(_call("remove_symbol", {"ir": ir, "index": 0}))
        self.assertEqual(len(ir["symbols"]), 0)


if __name__ == "__main__":
    unittest.main()
