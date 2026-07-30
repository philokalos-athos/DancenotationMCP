"""Direct-manipulation MCP tools for composing Labanotation scores.

These 10 tools let AI agents bypass the NLP parser and directly compose
Labanotation scores using any of the catalog symbols.
"""

from __future__ import annotations

import copy

from dancenotation_mcp.validation.validator import RETENTION_TYPES
from typing import Any

from dancenotation_mcp.ir.models import BODY_PARTS, PIN_SEXES, STAGE_ZONES, STAGE_FACINGS
from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.time_signatures import build_measure_beats_map, beats_for_measure


# ── Helpers ───────────────────────────────────────────────────────────

def _get_catalog() -> dict[str, dict]:
    return load_symbol_catalog()


def _validate_body_part(body_part: str) -> None:
    if body_part not in BODY_PARTS:
        raise ValueError(
            f"Invalid body_part '{body_part}'. Must be one of: {', '.join(BODY_PARTS)}"
        )


def _validate_symbol_id(symbol_id: str, catalog: dict[str, dict]) -> dict:
    entry = catalog.get(symbol_id)
    if entry is None:
        raise ValueError(
            f"Unknown symbol_id '{symbol_id}'. "
            f"Use list_symbols to browse available symbols."
        )
    return entry


def _ensure_extensions(ir: dict) -> dict:
    if "extensions" not in ir:
        ir["extensions"] = {}
    return ir["extensions"]


# ── Tool 1: list_symbols ─────────────────────────────────────────────

def list_symbols(args: dict) -> dict:
    """Browse/search the symbol catalog.

    Args (all optional):
        category: filter by symbol category (e.g. 'gesture', 'support')
        search: substring match against symbol name or id
        body_part: filter to symbols that allow this body part
    """
    catalog = _get_catalog()
    category = args.get("category")
    search = args.get("search", "").lower()
    body_part = args.get("body_part")

    if body_part and body_part not in BODY_PARTS:
        raise ValueError(
            f"Invalid body_part '{body_part}'. Must be one of: {', '.join(BODY_PARTS)}"
        )

    results = []
    for sym_id, sym in catalog.items():
        if category and sym.get("category") != category:
            continue
        if search and search not in sym.get("name", "").lower() and search not in sym_id.lower():
            continue
        if body_part and body_part not in sym.get("allowed_body_parts", []):
            continue
        results.append({
            "symbol_id": sym_id,
            "display_name": sym.get("name", sym_id),
            "family": sym.get("category", ""),
            "description": (
                f"Allowed body parts: {', '.join(sym.get('allowed_body_parts', []))}. "
                f"Direction required: {sym.get('requires_direction', False)}. "
                f"Level required: {sym.get('requires_level', False)}."
            ),
        })

    return {"count": len(results), "symbols": results}


# ── Tool 2: insert_symbol ────────────────────────────────────────────

def insert_symbol(args: dict) -> dict:
    """Insert a symbol into an IR score.

    Required args: ir, symbol_id, body_part, measure, beat, duration_beats
    Optional args: direction, level, modifiers
    """
    ir = copy.deepcopy(args["ir"])
    symbol_id = args["symbol_id"]
    body_part = args["body_part"]
    measure = int(args["measure"])
    beat = float(args["beat"])
    duration_beats = float(args["duration_beats"])

    catalog = _get_catalog()
    entry = _validate_symbol_id(symbol_id, catalog)
    _validate_body_part(body_part)

    if body_part not in entry.get("allowed_body_parts", []):
        raise ValueError(
            f"Body part '{body_part}' is not allowed for symbol '{symbol_id}'. "
            f"Allowed: {', '.join(entry.get('allowed_body_parts', []))}"
        )

    if measure < 1:
        raise ValueError("measure must be >= 1")
    if beat < 1.0:
        raise ValueError("beat must be >= 1.0")
    if duration_beats <= 0:
        raise ValueError("duration_beats must be > 0")

    new_symbol: dict[str, Any] = {
        "symbol_id": symbol_id,
        "body_part": body_part,
        "direction": args.get("direction"),
        "level": args.get("level"),
        "timing": {
            "measure": measure,
            "beat": beat,
            "duration_beats": duration_beats,
        },
        "modifiers": args.get("modifiers", {}),
        "rotation_degrees": None,
        "flexion_degrees": None,
        "stage_position": None,
        "facing": None,
        "retention": None,
    }

    if "symbols" not in ir:
        ir["symbols"] = []
    ir["symbols"].append(new_symbol)

    return ir


# ── Tool 3: remove_symbol ────────────────────────────────────────────

def remove_symbol(args: dict) -> dict:
    """Remove a symbol from an IR score by index or symbol_id.

    Required args: ir
    Plus one of: index (int) or symbol_id (str)
    """
    ir = copy.deepcopy(args["ir"])
    symbols = ir.get("symbols", [])

    if "index" in args:
        idx = int(args["index"])
        if idx < 0 or idx >= len(symbols):
            raise ValueError(
                f"Index {idx} out of range. Score has {len(symbols)} symbols (0-{len(symbols) - 1})."
            )
        removed = symbols.pop(idx)
        return ir

    if "symbol_id" in args:
        target = args["symbol_id"]
        for i, sym in enumerate(symbols):
            if sym.get("symbol_id") == target:
                symbols.pop(i)
                return ir
        raise ValueError(f"No symbol with symbol_id '{target}' found in the score.")

    raise ValueError("Must provide either 'index' or 'symbol_id' to identify the symbol to remove.")


# ── Tool 4: update_symbol ────────────────────────────────────────────

def update_symbol(args: dict) -> dict:
    """Update an existing symbol in the IR score.

    Required args: ir, index, updates (partial dict of fields to change)
    """
    ir = copy.deepcopy(args["ir"])
    idx = int(args["index"])
    updates = args["updates"]
    symbols = ir.get("symbols", [])

    if idx < 0 or idx >= len(symbols):
        raise ValueError(
            f"Index {idx} out of range. Score has {len(symbols)} symbols (0-{len(symbols) - 1})."
        )

    sym = symbols[idx]

    # Validate updated fields if provided
    if "symbol_id" in updates:
        catalog = _get_catalog()
        _validate_symbol_id(updates["symbol_id"], catalog)

    if "body_part" in updates:
        _validate_body_part(updates["body_part"])

    # Apply timing updates as nested merge
    if "timing" in updates:
        if "timing" not in sym or sym["timing"] is None:
            sym["timing"] = {}
        for k, v in updates["timing"].items():
            sym["timing"][k] = v
        del updates["timing"]

    # Apply modifier updates as nested merge
    if "modifiers" in updates:
        if "modifiers" not in sym or sym["modifiers"] is None:
            sym["modifiers"] = {}
        for k, v in updates["modifiers"].items():
            sym["modifiers"][k] = v
        del updates["modifiers"]

    # Apply remaining top-level updates
    for k, v in updates.items():
        sym[k] = v

    return ir


# ── Tool 5: set_time_signature ────────────────────────────────────────

def set_time_signature(args: dict) -> dict:
    """Set or update a time signature at a given measure.

    Required args: ir, measure, numerator, denominator
    """
    ir = copy.deepcopy(args["ir"])
    measure = int(args["measure"])
    numerator = int(args["numerator"])
    denominator = int(args["denominator"])

    if measure < 1:
        raise ValueError("measure must be >= 1")
    if numerator < 1:
        raise ValueError("numerator must be >= 1")
    if denominator not in (2, 4, 8, 16):
        raise ValueError("denominator must be one of: 2, 4, 8, 16")

    ext = _ensure_extensions(ir)
    if "time_signatures" not in ext:
        ext["time_signatures"] = []

    # Update existing entry for this measure or add new one
    for ts in ext["time_signatures"]:
        if ts.get("measure") == measure:
            ts["numerator"] = numerator
            ts["denominator"] = denominator
            return ir

    ext["time_signatures"].append({
        "measure": measure,
        "numerator": numerator,
        "denominator": denominator,
    })
    ext["time_signatures"].sort(key=lambda ts: ts["measure"])

    return ir


# ── Tool 6: add_floor_plan ───────────────────────────────────────────

def add_floor_plan(args: dict) -> dict:
    """Add a floor plan entry for a performer.

    Required args: ir, performer_id, measure, beat, zone
    Optional args: x, y, facing, path_to_next, sex, caption
    """
    ir = copy.deepcopy(args["ir"])
    zone = args["zone"]
    if zone not in STAGE_ZONES:
        raise ValueError(
            f"Invalid zone '{zone}'. Must be one of: {', '.join(STAGE_ZONES)}"
        )

    facing = args.get("facing")
    if facing is not None and facing not in STAGE_FACINGS:
        raise ValueError(
            f"Invalid facing '{facing}'. Must be one of: {', '.join(STAGE_FACINGS)}"
        )

    path_to_next = args.get("path_to_next")
    valid_paths = ("straight", "curved", "spiral", "zigzag")
    if path_to_next is not None and path_to_next not in valid_paths:
        raise ValueError(
            f"Invalid path_to_next '{path_to_next}'. Must be one of: {', '.join(valid_paths)}"
        )

    sex = args.get("sex")
    if sex is not None and sex not in PIN_SEXES:
        raise ValueError(
            f"Invalid sex '{sex}'. Must be one of: {', '.join(PIN_SEXES)}"
        )

    ext = _ensure_extensions(ir)
    if "floor_plan" not in ext:
        ext["floor_plan"] = []

    entry: dict[str, Any] = {
        "performer_id": args["performer_id"],
        "measure": int(args["measure"]),
        "beat": float(args["beat"]),
        "position": {
            "zone": zone,
        },
        "facing": facing,
        "path_to_next": path_to_next,
        "sex": sex,
        "caption": args.get("caption"),
    }

    if "x" in args and args["x"] is not None:
        entry["position"]["x"] = float(args["x"])
    if "y" in args and args["y"] is not None:
        entry["position"]["y"] = float(args["y"])

    ext["floor_plan"].append(entry)

    return ir


# ── Tool 7: add_effort_graph ─────────────────────────────────────────

def add_effort_graph(args: dict) -> dict:
    """Add an LMA effort-quality diamond.

    Required args: ir, measure, beat
    Optional args: weight ('strong'/'light'), time ('sudden'/'sustained'),
                   space ('direct'/'indirect'), flow ('bound'/'free'),
                   symbol_index (attach the diamond to a specific symbol
                   instead of positioning it by measure/beat alone)

    Note: this appends to ir["effort_graphs"] (a top-level list rendered by
    laban_renderer.py's _render_effort_graph_overlay), not ir["symbols"] —
    "quality.effort" isn't a real catalog symbol_id, so an earlier version
    of this tool produced symbols that always failed validation with
    "Unknown symbol id".
    """
    ir = copy.deepcopy(args["ir"])

    measure = int(args["measure"])
    beat = float(args["beat"])

    if measure < 1:
        raise ValueError("measure must be >= 1")
    if beat < 1.0:
        raise ValueError("beat must be >= 1.0")

    valid_efforts = {
        "weight": ("strong", "light"),
        "time": ("sudden", "sustained"),
        "space": ("direct", "indirect"),
        "flow": ("bound", "free"),
    }
    effort_graph: dict[str, Any] = {"measure": measure, "beat": beat}
    for effort_key, allowed in valid_efforts.items():
        value = args.get(effort_key)
        if value is not None:
            if value not in allowed:
                raise ValueError(
                    f"Invalid {effort_key} '{value}'. Must be one of: {', '.join(allowed)}"
                )
            effort_graph[effort_key] = value

    if args.get("symbol_index") is not None:
        effort_graph["symbol_index"] = int(args["symbol_index"])

    if "effort_graphs" not in ir:
        ir["effort_graphs"] = []
    ir["effort_graphs"].append(effort_graph)

    return ir


# ── Tool 8: create_empty_score ────────────────────────────────────────

def create_empty_score(args: dict) -> dict:
    """Create a blank IR score.

    Required args: title
    Optional args: time_sig_num (default 4), time_sig_den (default 4),
                   tempo (bpm), measures (count)
    """
    title = args.get("title", "Untitled")
    time_sig_num = int(args.get("time_sig_num", 4))
    time_sig_den = int(args.get("time_sig_den", 4))
    tempo = args.get("tempo")
    measures = args.get("measures")

    ir: dict[str, Any] = {
        "metadata": {
            "title": title,
            "source_prompt": "",
            "ir_version": "0.2.0",
            "schema_version": "0.2.0",
        },
        "symbols": [],
        "extensions": {},
    }

    # Add initial time signature if not default 4/4
    if time_sig_num != 4 or time_sig_den != 4:
        ir["extensions"]["time_signatures"] = [{
            "measure": 1,
            "numerator": time_sig_num,
            "denominator": time_sig_den,
        }]

    # Add tempo as a measure-header symbol if provided. "timing.tempo" isn't
    # a real catalog symbol_id (same bug class as add_retention/
    # add_effort_graph elsewhere in this file) — the real tempo-mark family
    # is "music.tempo.mark" (body_part "torso"), read via modifiers.tempo
    # (not "bpm") by laban_renderer.py's _render_measure_header, and needs
    # modifiers.measure_header=True to route there instead of the plain
    # annotation-area music-rest renderer.
    if tempo is not None:
        ir["symbols"].append({
            "symbol_id": "music.tempo.mark",
            "body_part": "torso",
            "direction": None,
            "level": None,
            "timing": {
                "measure": 1,
                "beat": 1.0,
                "duration_beats": 1.0,
            },
            "modifiers": {"tempo": int(tempo), "measure_header": True},
            "rotation_degrees": None,
            "flexion_degrees": None,
            "stage_position": None,
            "facing": None,
            "retention": None,
        })

    return ir


# ── Tool 9: add_retention ────────────────────────────────────────────


def add_retention(args: dict) -> dict:
    """Add a retention symbol.

    Required args: ir, type, body_part, measure, beat
    Optional args: duration_beats (default 1.0)

    The types are Knust's, vol 2 Fig. 78-79:

      hold        the round retention sign (78a) -- retention in the body, or
                  retaining the weight when it sits in a support column
      space_hold  the diamond (78b) -- retention in space, maintaining the
                  same spatial direction while the body turns under it
      spot_hold   the diamond with a dot (78c) -- retention at a spot
      cancel      the decrease sign (79a), Kinetography's general
                  cancellation sign
      release     a synonym of cancel; it engraves the same sign, because
                  "Release X Position" and "Cancel X Retention" name one
                  operation and the notation has one sign for it. Kept
                  because it is already in this tool's public enum.
    """
    ir = copy.deepcopy(args["ir"])
    ret_type = args["type"]
    body_part = args["body_part"]
    measure = int(args["measure"])
    beat = float(args["beat"])
    duration_beats = float(args.get("duration_beats", 1.0))

    # One list, in the validator, so the tool cannot accept what the
    # validator will then reject.
    valid_types = RETENTION_TYPES
    if ret_type not in valid_types:
        raise ValueError(
            f"Invalid retention type '{ret_type}'. Must be one of: {', '.join(valid_types)}"
        )

    _validate_body_part(body_part)

    if measure < 1:
        raise ValueError("measure must be >= 1")
    if beat < 1.0:
        raise ValueError("beat must be >= 1.0")

    # The catalog only has retention.{type}.{category} entries (arm/leg/
    # torso/head/hand/shoulder/full_body) — "timing.retention.{type}" doesn't
    # exist at all, which previously made every add_retention symbol fail
    # validation with "Unknown symbol id".
    # One id per sign. The body part is carried by the symbol's own
    # body_part field, which is what places it -- BODY_TO_COLUMN reads that,
    # never an id suffix. The family used to cross five types with seven body
    # categories for 35 entries, duplicating the field in the id the way
    # turn.right duplicated the direction field before that prune.
    symbol_id = f"retention.{ret_type}"

    retention_symbol: dict[str, Any] = {
        "symbol_id": symbol_id,
        "body_part": body_part,
        "direction": None,
        "level": None,
        "timing": {
            "measure": measure,
            "beat": beat,
            "duration_beats": duration_beats,
        },
        "modifiers": {},
        "rotation_degrees": None,
        "flexion_degrees": None,
        "stage_position": None,
        "facing": None,
        "retention": ret_type,
    }

    if "symbols" not in ir:
        ir["symbols"] = []
    ir["symbols"].append(retention_symbol)

    return ir


# ── Tool 10: get_score_summary ────────────────────────────────────────

def get_score_summary(args: dict) -> dict:
    """Analyze an IR score and return a summary.

    Required args: ir
    """
    ir = args["ir"]
    symbols = ir.get("symbols", [])

    body_parts_used: set[str] = set()
    families_used: set[str] = set()
    max_measure = 0

    catalog = _get_catalog()

    for sym in symbols:
        bp = sym.get("body_part", "")
        if bp:
            body_parts_used.add(bp)
        sid = sym.get("symbol_id", "")
        cat_entry = catalog.get(sid)
        if cat_entry:
            families_used.add(cat_entry.get("category", ""))
        elif "." in sid:
            families_used.add(sid.split(".")[0])

        timing = sym.get("timing", {})
        m = int(timing.get("measure", 1))
        if m > max_measure:
            max_measure = m

    # Collect time signatures from extensions
    time_sigs = ir.get("extensions", {}).get("time_signatures", [])

    return {
        "total_symbols": len(symbols),
        "measures": max_measure,
        "body_parts_used": sorted(body_parts_used),
        "families_used": sorted(families_used),
        "time_signatures": time_sigs,
    }
