from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

LOGGER = logging.getLogger(__name__)

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.rendering.floor_plan_renderer import render_floor_plan_svg
from dancenotation_mcp.rendering.laban_renderer import render_laban_svg
from dancenotation_mcp.rendering.music_engraver import render_music_svg
from dancenotation_mcp.rendering.music_import import check_measure_alignment, import_music_source
from dancenotation_mcp.rendering.paired_score_renderer import render_paired_score_svg
from dancenotation_mcp.rendering.pdf_renderer import svg_to_pdf
from dancenotation_mcp.rendering.svg_renderer import render_svg
from dancenotation_mcp.rendering.tikz_renderer import render_tikz
from dancenotation_mcp.validation.repair import repair_ir
from dancenotation_mcp.validation.validator import RETENTION_TYPES
from dancenotation_mcp.validation.validator import validate_ir

from dancenotation_mcp.mcp_server.tools import (
    list_symbols,
    insert_symbol,
    remove_symbol,
    update_symbol,
    set_time_signature,
    add_floor_plan,
    add_effort_graph,
    create_empty_score,
    add_retention,
    get_score_summary,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SVG_EXAMPLES_DIR = REPO_ROOT / "examples" / "svg"
PDF_EXAMPLES_DIR = REPO_ROOT / "examples" / "pdf"
TEX_EXAMPLES_DIR = REPO_ROOT / "examples" / "tex"


# ── Tool schemas ───────────────────────────────────────────────────────

TOOL_SCHEMAS = {
    "plan_phrase": {
        "description": "Parse a natural-language dance phrase into a structured phrase plan with steps, timing, and body assignments",
        "inputSchema": {
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string", "description": "Natural language dance phrase, e.g. 'step forward, turn right, jump high'"},
            },
        },
    },
    "build_ir": {
        "description": "Build canonical notation IR from a phrase plan produced by plan_phrase",
        "inputSchema": {
            "type": "object",
            "required": ["phrase_plan"],
            "properties": {
                "phrase_plan": {"type": "object", "description": "Phrase plan object returned by plan_phrase"},
                "source_prompt": {"type": "string", "description": "Original prompt text for metadata"},
            },
        },
    },
    "validate_ir": {
        "description": "Validate notation IR against schema and semantic rules, returning diagnostics and repair hints",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to validate"},
            },
        },
    },
    "repair_ir": {
        "description": "Apply repair hints from validate_ir to fix invalid or stylistically problematic notation IR",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "diagnostics"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to repair"},
                "diagnostics": {"type": "object", "description": "Diagnostics object from validate_ir containing repair_hints"},
            },
        },
    },
    "render_svg": {
        "description": "Render notation IR as a debug/preview SVG with all 28 lanes visible",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to render"},
            },
        },
    },
    "render_laban": {
        "description": "Render notation IR as a standard Labanotation SVG score with narrow staff, direction-shape rectangles, and bottom-to-top time flow",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to render"},
            },
        },
    },
    "render_tikz": {
        "description": "Render notation IR as a LaTeX/TikZ document that can be imported and edited in LaTeX",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to render as TikZ"},
            },
        },
    },
    "render_floor_plan": {
        "description": "Render the IR's floor_plan extension data as a top-down stage diagram SVG (dancer positions, facing, and travel paths between measures)",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object with extensions.floor_plan entries (see add_floor_plan)"},
                "measure_start": {"type": "integer", "description": "Restrict the diagram to measures >= this value"},
                "measure_end": {"type": "integer", "description": "Restrict the diagram to measures <= this value"},
            },
        },
    },
    "render_music": {
        "description": "Import a MusicXML or MIDI file and engrave it to SVG via a local LilyPond install. Returns null svg (with a reason) if the file can't be parsed or LilyPond isn't installed — music engraving degrades gracefully rather than failing the whole score.",
        "inputSchema": {
            "type": "object",
            "required": ["music_source"],
            "properties": {
                "music_source": {"type": "string", "description": "Path to a MusicXML (.musicxml/.xml) or MIDI (.mid/.midi) file"},
                "ir": {"type": "object", "description": "Optional dance IR to check measure/time-signature alignment against"},
            },
        },
    },
    "render_paired_score": {
        "description": "Render the Labanotation staff with a music strip rotated and scaled to exactly match each dance measure's pixel height, per measure — the true side-by-side layout used by published Labanotation scores. Falls back to the plain dance-only render if the music source can't be engraved.",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "music_source"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to render"},
                "music_source": {"type": "string", "description": "Path to a MusicXML or MIDI file"},
            },
        },
    },
    "generate_score": {
        "description": "Generate a complete score with SVG, PDF, and TikZ output files, returning paths and a LaTeX snippet. Also emits a floor-plan diagram file when the IR has extensions.floor_plan data, and a music engraving file when music_source is given.",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to render"},
                "name": {"type": "string", "description": "Score name for output file paths (default: from IR title)"},
                "renderer": {"type": "string", "enum": ["laban", "debug"], "description": "Renderer to use: 'laban' (standard Labanotation, default) or 'debug' (28-lane preview)"},
                "music_source": {"type": "string", "description": "Optional path to a MusicXML/MIDI file to engrave alongside the score (requires a local LilyPond install; degrades gracefully if unavailable)"},
            },
        },
    },
    # ── Direct-manipulation tools ─────────────────────────────────────
    "list_symbols": {
        "description": "Browse and search the Labanotation symbol catalog (~1,140 symbols). Filter by category, name substring, or allowed body part.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filter by symbol category/family (e.g. 'gesture', 'support', 'turn')"},
                "search": {"type": "string", "description": "Substring to match against symbol name or id"},
                "body_part": {"type": "string", "description": "Filter to symbols that allow this body part"},
            },
        },
    },
    "insert_symbol": {
        "description": "Insert a catalog symbol into an IR score at a specific body part, measure, and beat",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "symbol_id", "body_part", "measure", "beat", "duration_beats"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "symbol_id": {"type": "string", "description": "Symbol ID from the catalog (use list_symbols to find)"},
                "body_part": {"type": "string", "description": "Target body part (e.g. 'left_arm', 'right_leg')"},
                "measure": {"type": "integer", "description": "Measure number (1-based)"},
                "beat": {"type": "number", "description": "Beat within the measure (1-based)"},
                "duration_beats": {"type": "number", "description": "Duration in beats"},
                "direction": {"type": "string", "description": "Direction (e.g. 'forward', 'left')"},
                "level": {"type": "string", "description": "Level (e.g. 'high', 'middle', 'low')"},
                "modifiers": {"type": "object", "description": "Additional modifier key-value pairs"},
            },
        },
    },
    "remove_symbol": {
        "description": "Remove a symbol from an IR score, addressed by its stable uid (preferred), its index, or its catalog symbol_id",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "uid": {"type": "string", "description": "Stable symbol id. Unaffected by insertions elsewhere in the score, unlike index. Assigned by the editing tools; scores written directly are stamped on first contact."},
                "index": {"type": "integer", "description": "Zero-based position. Any insertion before it shifts this, so prefer uid when making more than one edit."},
                "symbol_id": {"type": "string", "description": "Catalog id, e.g. support.step. Shared by every step in the score, so this removes the first match."},
            },
        },
    },
    "update_symbol": {
        "description": "Update properties of an existing symbol in the IR score, addressed by its stable uid (preferred) or its index",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "updates"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "uid": {"type": "string", "description": "Stable symbol id. Unaffected by insertions elsewhere in the score, unlike index. Assigned by the editing tools; scores written directly are stamped on first contact."},
                "index": {"type": "integer", "description": "Zero-based position. Any insertion before it shifts this, so prefer uid when making more than one edit."},
                "updates": {"type": "object", "description": "Partial dict of fields to change (e.g. {direction: 'left', timing: {beat: 2.0}})"},
            },
        },
    },
    "set_time_signature": {
        "description": "Set or update the time signature at a given measure",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "measure", "numerator", "denominator"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "measure": {"type": "integer", "description": "Measure number where the time signature takes effect"},
                "numerator": {"type": "integer", "description": "Time signature numerator (e.g. 3 for 3/4)"},
                "denominator": {"type": "integer", "description": "Time signature denominator (2, 4, 8, or 16)"},
            },
        },
    },
    "add_floor_plan": {
        "description": "Add a floor plan entry specifying performer position on stage",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "performer_id", "measure", "beat", "zone"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "performer_id": {"type": "string", "description": "Identifier for the performer (e.g. 'dancer_1')"},
                "measure": {"type": "integer", "description": "Measure number"},
                "beat": {"type": "number", "description": "Beat within the measure"},
                "zone": {"type": "string", "description": "Stage zone (e.g. 'center', 'downstage_left', 'upstage_right', or 'wing_left'/'wing_right' for offstage waiting positions)"},
                "x": {"type": "number", "description": "Normalized x position within zone (0.0-1.0)"},
                "y": {"type": "number", "description": "Normalized y position within zone (0.0-1.0)"},
                "facing": {"type": "string", "description": "Direction the performer faces (e.g. 'downstage', 'stage_left')"},
                "path_to_next": {"type": "string", "description": "Path type to next position: 'straight', 'curved', 'spiral', 'zigzag'"},
                "sex": {"type": "string", "description": "Pin head shape per LabanWriter convention: 'female' (white, default), 'male' (black), or 'neuter' (tack)"},
                "caption": {"type": "string", "description": "Optional caption text for this position (LabanWriter's 'Caption Squares')"},
            },
        },
    },
    "add_effort_graph": {
        "description": "Add a Laban Movement Analysis (LMA) effort-quality diamond (weight/time/space/flow) to ir.effort_graphs, positioned by measure/beat or attached to a specific symbol_index",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "measure", "beat"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "measure": {"type": "integer", "description": "Measure number"},
                "beat": {"type": "number", "description": "Beat within the measure"},
                "weight": {"type": "string", "description": "Weight effort: 'strong' or 'light'"},
                "time": {"type": "string", "description": "Time effort: 'sudden' or 'sustained'"},
                "space": {"type": "string", "description": "Space effort: 'direct' or 'indirect'"},
                "flow": {"type": "string", "description": "Flow effort: 'bound' or 'free'"},
                "symbol_index": {"type": "integer", "description": "Optional: attach this effort diamond to a specific existing symbol by its index instead of positioning by measure/beat alone"},
            },
        },
    },
    "create_empty_score": {
        "description": "Create a blank IR score with metadata and optional time signature/tempo",
        "inputSchema": {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string", "description": "Score title"},
                "time_sig_num": {"type": "integer", "description": "Time signature numerator (default: 4)"},
                "time_sig_den": {"type": "integer", "description": "Time signature denominator (default: 4)"},
                "tempo": {"type": "integer", "description": "Tempo in BPM"},
                "measures": {"type": "integer", "description": "Number of measures"},
            },
        },
    },
    "add_retention": {
        "description": "Add a retention symbol to sustain or end a movement: hold (round sign), space_hold (diamond), spot_hold (diamond with dot), or cancel/release (decrease sign)",
        "inputSchema": {
            "type": "object",
            "required": ["ir", "type", "body_part", "measure", "beat"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to modify"},
                "type": {"type": "string", "enum": list(RETENTION_TYPES), "description": "Retention type; release is a synonym of cancel"},
                "body_part": {"type": "string", "description": "Body part for the retention"},
                "measure": {"type": "integer", "description": "Measure number"},
                "beat": {"type": "number", "description": "Beat within the measure"},
                "duration_beats": {"type": "number", "description": "Duration in beats (default: 1.0)"},
            },
        },
    },
    "get_score_summary": {
        "description": "Analyze an IR score and return a summary with total symbols, measures, body parts used, and families used",
        "inputSchema": {
            "type": "object",
            "required": ["ir"],
            "properties": {
                "ir": {"type": "object", "description": "Notation IR object to analyze"},
            },
        },
    },
}


# ── Tool implementations ──────────────────────────────────────────────

def _slugify_score_name(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    slug = "-".join(part for part in lowered.split("-") if part)
    return slug or "score"


def generate_score(args: dict) -> dict:
    ir = args["ir"]
    renderer_choice = args.get("renderer", "laban")
    requested_name = args.get("name") or ir.get("metadata", {}).get("title") or "score"
    score_name = _slugify_score_name(requested_name)
    svg_path = SVG_EXAMPLES_DIR / f"{score_name}.svg"
    pdf_path = PDF_EXAMPLES_DIR / f"{score_name}.pdf"
    tex_path = TEX_EXAMPLES_DIR / f"{score_name}.tex"

    if renderer_choice == "debug":
        svg_content = render_svg(ir)
    else:
        svg_content = render_laban_svg(ir)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")

    pdf_created = svg_to_pdf(svg_content, pdf_path)

    tikz_content = render_tikz(ir)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    tex_path.write_text(tikz_content, encoding="utf-8")

    relative_svg_path = svg_path.relative_to(REPO_ROOT).as_posix()
    relative_pdf_path = pdf_path.relative_to(REPO_ROOT).as_posix()
    relative_tex_path = tex_path.relative_to(REPO_ROOT).as_posix()
    preview_html = (
        '<div class="score-preview">'
        f'<object data="{relative_svg_path}" type="image/svg+xml" aria-label="{score_name}"></object>'
        "</div>"
    )
    result = {
        "svg_path": relative_svg_path,
        "pdf_path": relative_pdf_path if pdf_created else None,
        "tikz_path": relative_tex_path,
        "latex": f"\\input{{{relative_tex_path}}}",
        "preview_html": preview_html,
    }

    if ir.get("extensions", {}).get("floor_plan"):
        floor_plan_svg_path = SVG_EXAMPLES_DIR / f"{score_name}-floorplan.svg"
        floor_plan_pdf_path = PDF_EXAMPLES_DIR / f"{score_name}-floorplan.pdf"
        floor_plan_content = render_floor_plan_svg(ir)
        floor_plan_svg_path.parent.mkdir(parents=True, exist_ok=True)
        floor_plan_svg_path.write_text(floor_plan_content, encoding="utf-8")
        floor_plan_pdf_created = svg_to_pdf(floor_plan_content, floor_plan_pdf_path)
        result["floor_plan_svg_path"] = floor_plan_svg_path.relative_to(REPO_ROOT).as_posix()
        result["floor_plan_pdf_path"] = (
            floor_plan_pdf_path.relative_to(REPO_ROOT).as_posix() if floor_plan_pdf_created else None
        )

    music_source = args.get("music_source")
    if music_source:
        music_result = _render_music_files(ir, music_source, score_name)
        result.update(music_result)

    return result


def _render_music_tool(args: dict) -> dict:
    score = import_music_source(args["music_source"])
    if score is None:
        return {"svg": None, "reason": "music source could not be parsed (see server logs)"}
    alignment = check_measure_alignment(score, args["ir"]) if args.get("ir") else None
    svg_content = render_music_svg(score)
    if svg_content is None:
        result = {"svg": None, "reason": "lilypond engraving unavailable or failed (see server logs)"}
    else:
        result = {"svg": svg_content}
    if alignment is not None:
        result["alignment"] = alignment
    return result


def _render_music_files(ir: dict, music_source: str, score_name: str) -> dict:
    """Import + engrave a music source and write its output files.

    Degrades gracefully (matching svg_to_pdf's pattern): a missing/unparsable
    source or missing LilyPond install never raises — it just omits the
    music output paths and reports why via music_alignment/music_engraved.
    """
    score = import_music_source(music_source)
    if score is None:
        return {"music_svg_path": None, "music_pdf_path": None, "music_engraved": False}

    alignment = check_measure_alignment(score, ir)
    music_svg_content = render_music_svg(score)
    if music_svg_content is None:
        return {
            "music_svg_path": None,
            "music_pdf_path": None,
            "music_engraved": False,
            "music_alignment": alignment,
        }

    music_svg_path = SVG_EXAMPLES_DIR / f"{score_name}-music.svg"
    music_pdf_path = PDF_EXAMPLES_DIR / f"{score_name}-music.pdf"
    music_svg_path.parent.mkdir(parents=True, exist_ok=True)
    music_svg_path.write_text(music_svg_content, encoding="utf-8")
    music_pdf_created = svg_to_pdf(music_svg_content, music_pdf_path)

    result = {
        "music_svg_path": music_svg_path.relative_to(REPO_ROOT).as_posix(),
        "music_pdf_path": music_pdf_path.relative_to(REPO_ROOT).as_posix() if music_pdf_created else None,
        "music_engraved": True,
        "music_alignment": alignment,
    }

    # Paired rendering: the music strip rotated and scaled to exactly match
    # each dance measure's pixel height, per-measure — this is the true
    # side-by-side layout the reference score uses, beyond the plain
    # separate music_svg_path above. Best-effort: falls back silently (no
    # paired_svg_path key) if per-measure engraving fails for any reason,
    # since the plain music/dance outputs above already succeeded.
    try:
        paired_content = render_paired_score_svg(ir, score)
    except Exception as exc:
        LOGGER.warning("Paired score composition failed: %s", exc)
        return result
    if paired_content and paired_content != render_laban_svg(ir):
        paired_svg_path = SVG_EXAMPLES_DIR / f"{score_name}-paired.svg"
        paired_pdf_path = PDF_EXAMPLES_DIR / f"{score_name}-paired.pdf"
        paired_svg_path.write_text(paired_content, encoding="utf-8")
        paired_pdf_created = svg_to_pdf(paired_content, paired_pdf_path)
        result["paired_svg_path"] = paired_svg_path.relative_to(REPO_ROOT).as_posix()
        result["paired_pdf_path"] = (
            paired_pdf_path.relative_to(REPO_ROOT).as_posix() if paired_pdf_created else None
        )

    return result


TOOLS = {
    "plan_phrase": lambda args: parse_phrase(args["prompt"]),
    "build_ir": lambda args: phrase_plan_to_ir(args["phrase_plan"], args.get("source_prompt", "")),
    "validate_ir": lambda args: validate_ir(args["ir"]),
    "repair_ir": lambda args: repair_ir(args["ir"], args["diagnostics"]),
    "render_svg": lambda args: {"svg": render_svg(args["ir"])},
    "render_laban": lambda args: {"svg": render_laban_svg(args["ir"])},
    "render_tikz": lambda args: {"tikz": render_tikz(args["ir"])},
    "render_floor_plan": lambda args: {
        "svg": render_floor_plan_svg(
            args["ir"],
            measure_range=(
                (args["measure_start"], args["measure_end"])
                if "measure_start" in args and "measure_end" in args
                else None
            ),
        )
    },
    "render_music": lambda args: _render_music_tool(args),
    "render_paired_score": lambda args: {
        "svg": render_paired_score_svg(args["ir"], import_music_source(args["music_source"]))
    },
    "generate_score": generate_score,
    # Direct-manipulation tools
    "list_symbols": list_symbols,
    "insert_symbol": insert_symbol,
    "remove_symbol": remove_symbol,
    "update_symbol": update_symbol,
    "set_time_signature": set_time_signature,
    "add_floor_plan": add_floor_plan,
    "add_effort_graph": add_effort_graph,
    "create_empty_score": create_empty_score,
    "add_retention": add_retention,
    "get_score_summary": get_score_summary,
}


# ── JSON-RPC handler ──────────────────────────────────────────────────

def handle(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "dancenotation-mcp", "version": "0.2.0"},
                "capabilities": {"tools": {"listChanged": False}},
            },
        }

    if method == "notifications/initialized":
        return {}  # Notifications don't get responses

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": schema["description"],
                        "inputSchema": schema["inputSchema"],
                    }
                    for name, schema in TOOL_SCHEMAS.items()
                ]
            },
        }

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOLS:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Unknown tool '{name}'"}}
        try:
            result = TOOLS[name](arguments)
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False), "json": result}]}}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32000,
                    "message": "Tool execution error",
                    "data": {"tool": name, "error": str(exc)},
                },
            }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}


def _read_mcp_message(stdin_bin) -> dict | None:
    """Read a single MCP message using Content-Length framing from binary stdin."""
    content_length = 0
    while True:
        line = stdin_bin.readline()
        if not line:
            return None  # EOF
        line = line.strip()
        if not line:
            break  # Empty line = end of headers
        if line.lower().startswith(b"content-length:"):
            content_length = int(line.split(b":", 1)[1].strip())
    if content_length == 0:
        return None
    body = stdin_bin.read(content_length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_mcp_message(resp: dict, stdout_bin) -> None:
    """Write a single MCP message with Content-Length framing to binary stdout."""
    body = json.dumps(resp, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    stdout_bin.write(header)
    stdout_bin.write(body)
    stdout_bin.flush()


def main() -> int:
    # Use binary mode for proper Content-Length framing on Windows
    stdin_bin = sys.stdin.buffer
    stdout_bin = sys.stdout.buffer
    while True:
        req = _read_mcp_message(stdin_bin)
        if req is None:
            break
        resp = handle(req)
        if resp.get("result") is None and resp.get("error") is None:
            continue
        _write_mcp_message(resp, stdout_bin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
