from __future__ import annotations

import json
import sys
from pathlib import Path

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.rendering.pdf_renderer import svg_to_pdf
from dancenotation_mcp.rendering.svg_renderer import render_svg
from dancenotation_mcp.validation.validator import validate_ir


REPO_ROOT = Path(__file__).resolve().parents[3]
SVG_EXAMPLES_DIR = REPO_ROOT / "examples" / "svg"
PDF_EXAMPLES_DIR = REPO_ROOT / "examples" / "pdf"
HEADER_FAMILY_BY_SYMBOL = {
    "music.time.2_4": "time_signature",
    "music.time.3_4": "time_signature",
    "music.time.4_4": "time_signature",
    "music.tempo.mark": "tempo",
    "music.cadence.mark": "cadence",
}
HEADER_FAMILY_ORDER = {"time_signature": 0, "tempo": 1, "cadence": 2}


def _symbol_index_from_path(path: str) -> int | None:
    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "symbols":
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


def _modifier_key_from_path(path: str) -> str | None:
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[2] == "modifiers":
        return parts[3]
    return None


def repair_ir(ir: dict, diagnostics: dict) -> dict:
    patched = json.loads(json.dumps(ir))
    symbols_to_remove: set[int] = set()
    reorder_header_measures: set[int] = set()
    reorder_repeat_measures: set[int] = set()
    split_duration_hints: list[dict] = []
    continuation_insert_hints: list[dict] = []
    for hint in diagnostics.get("repair_hints", []):
        if hint["action"] == "remove_symbol":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None:
                symbols_to_remove.add(sym_idx)
        if hint["action"] == "reorder_measure_headers":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None and 0 <= sym_idx < len(patched.get("symbols", [])):
                measure = int(patched["symbols"][sym_idx].get("timing", {}).get("measure", 1))
                reorder_header_measures.add(measure)
        if hint["action"] == "reorder_repeat_boundaries":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None and 0 <= sym_idx < len(patched.get("symbols", [])):
                measure = int(patched["symbols"][sym_idx].get("timing", {}).get("measure", 1))
                reorder_repeat_measures.add(measure)
        if hint["action"] == "set_duration":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None:
                patched.get("symbols", [])[sym_idx].setdefault("timing", {})["duration_beats"] = float(hint.get("value", 1.0))
            else:
                for sym in patched.get("symbols", []):
                    if sym.get("timing", {}).get("duration_beats", 0) <= 0:
                        sym["timing"]["duration_beats"] = float(hint.get("value", 1.0))
        if hint["action"] == "split_duration":
            split_duration_hints.append(hint)
        if hint["action"] == "insert_continuation_symbol":
            continuation_insert_hints.append(hint)
        if hint["action"] == "replace_symbol":
            for sym in patched.get("symbols", []):
                if sym.get("symbol_id", "").startswith("unknown"):
                    sym["symbol_id"] = "support.step"
        if hint["action"] == "set_beat":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None:
                patched.get("symbols", [])[sym_idx].setdefault("timing", {})["beat"] = float(hint.get("value", 1.0))
        if hint["action"] == "set_body_part":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            if sym_idx is not None:
                patched.get("symbols", [])[sym_idx]["body_part"] = str(hint.get("value", "torso"))
        if hint["action"] == "remove_modifier":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            modifier_key = _modifier_key_from_path(hint.get("path", ""))
            if sym_idx is not None and modifier_key:
                modifiers = patched.get("symbols", [])[sym_idx].get("modifiers", {})
                if isinstance(modifiers, dict):
                    modifiers.pop(modifier_key, None)
        if hint["action"] == "set_modifier":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            modifier_key = str(hint.get("key", ""))
            if sym_idx is not None and modifier_key:
                patched.get("symbols", [])[sym_idx].setdefault("modifiers", {})[modifier_key] = hint.get("value")
        if hint["action"] == "retarget_attachment":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            modifier_key = _modifier_key_from_path(hint.get("path", ""))
            if sym_idx is not None and modifier_key == "attach_to":
                current = patched.get("symbols", [])[sym_idx]
                current_timing = current.get("timing", {})
                current_measure = int(current_timing.get("measure", 1))
                current_beat = float(current_timing.get("beat", 0))
                current_body = current.get("body_part")
                candidates = []
                for candidate in patched.get("symbols", []):
                    symbol_id = candidate.get("symbol_id")
                    if not symbol_id or symbol_id == current.get("symbol_id"):
                        continue
                    timing = candidate.get("timing", {})
                    measure = int(timing.get("measure", 1))
                    beat = float(timing.get("beat", 0))
                    duration = float(timing.get("duration_beats", 0))
                    ends_at = beat + max(duration, 0.0)
                    if measure < current_measure or (measure == current_measure and beat <= current_beat):
                        preferred_measure = 0 if measure == current_measure else 1
                        coverage_penalty = 0 if measure == current_measure and ends_at + 0.01 >= current_beat else 1
                        preferred_family = 0 if symbol_id.startswith(("support.", "direction.", "path.", "body.", "gesture.", "turn.", "jump.")) else 1
                        preferred_body = 0 if current_body and candidate.get("body_part") == current_body else 1
                        measure_distance = abs(current_measure - measure)
                        beat_distance = abs(current_beat - beat)
                        candidates.append((preferred_measure, coverage_penalty, preferred_body, preferred_family, measure_distance, beat_distance, measure, beat, symbol_id))
                if candidates:
                    _, _, _, _, _, _, _, _, symbol_id = min(candidates)
                    current.setdefault("modifiers", {})["attach_to"] = symbol_id
                else:
                    current.setdefault("modifiers", {}).pop("attach_to", None)
        if hint["action"] == "retarget_repeat_span":
            sym_idx = _symbol_index_from_path(hint.get("path", ""))
            modifier_key = _modifier_key_from_path(hint.get("path", ""))
            if sym_idx is not None and (modifier_key == "repeat_span_to" or modifier_key is None):
                current = patched.get("symbols", [])[sym_idx]
                current_timing = current.get("timing", {})
                current_measure = int(current_timing.get("measure", 1))
                current_beat = float(current_timing.get("beat", 0))
                candidates = []
                for candidate in patched.get("symbols", []):
                    symbol_id = candidate.get("symbol_id")
                    if not symbol_id or not symbol_id.startswith("repeat."):
                        continue
                    timing = candidate.get("timing", {})
                    measure = int(timing.get("measure", 1))
                    beat = float(timing.get("beat", 0))
                    if measure > current_measure or (measure == current_measure and beat > current_beat):
                        candidates.append((measure, beat, symbol_id))
                if candidates:
                    _, _, symbol_id = min(candidates)
                    current.setdefault("modifiers", {})["repeat_span_to"] = symbol_id
                else:
                    current.setdefault("modifiers", {}).pop("repeat_span_to", None)
    for sym_idx in sorted(symbols_to_remove, reverse=True):
        if 0 <= sym_idx < len(patched.get("symbols", [])):
            patched["symbols"].pop(sym_idx)
    for hint in split_duration_hints:
        sym_idx = _symbol_index_from_path(hint.get("path", ""))
        if sym_idx is None:
            continue
        removed_before = sum(1 for removed_idx in symbols_to_remove if removed_idx < sym_idx)
        adjusted_idx = sym_idx - removed_before
        if adjusted_idx in symbols_to_remove or not (0 <= adjusted_idx < len(patched.get("symbols", []))):
            continue
        current = patched["symbols"][adjusted_idx]
        current_timing = current.setdefault("timing", {})
        current_timing["duration_beats"] = float(hint.get("value", current_timing.get("duration_beats", 1.0)))
        carry_duration = float(hint.get("carry_duration", 0.0))
        next_measure = int(hint.get("next_measure") or (int(current_timing.get("measure", 1)) + 1))
        if carry_duration > 0.0:
            continuation = json.loads(json.dumps(current))
            continuation["timing"]["measure"] = next_measure
            continuation["timing"]["beat"] = 1.0
            continuation["timing"]["duration_beats"] = carry_duration
            patched["symbols"].insert(adjusted_idx + 1, continuation)
    for hint in continuation_insert_hints:
        sym_idx = _symbol_index_from_path(hint.get("path", ""))
        if sym_idx is None:
            continue
        removed_before = sum(1 for removed_idx in symbols_to_remove if removed_idx < sym_idx)
        adjusted_idx = sym_idx - removed_before
        if adjusted_idx in symbols_to_remove or not (0 <= adjusted_idx < len(patched.get("symbols", []))):
            continue
        current = patched["symbols"][adjusted_idx]
        attach_to = current.get("modifiers", {}).get("attach_to")
        if not isinstance(attach_to, str):
            continue
        target = next((sym for sym in patched.get("symbols", []) if sym.get("symbol_id") == attach_to), None)
        if not target:
            continue
        target_body = target.get("body_part")
        target_measure = int(target.get("timing", {}).get("measure", 1))
        next_target = next(
            (
                sym
                for sym in patched.get("symbols", [])
                if sym.get("body_part") == target_body
                and int(sym.get("timing", {}).get("measure", 1)) == target_measure + 1
                and abs(float(sym.get("timing", {}).get("beat", 0)) - 1.0) <= 0.01
                and str(sym.get("symbol_id", "")).startswith(("support.", "direction.", "path.", "body.", "gesture.", "turn.", "jump."))
            ),
            None,
        )
        if not next_target:
            continue
        already_present = any(
            sym.get("symbol_id") == current.get("symbol_id")
            and sym.get("modifiers", {}).get("attach_to") == next_target.get("symbol_id")
            and int(sym.get("timing", {}).get("measure", 1)) == target_measure + 1
            for sym in patched.get("symbols", [])
        )
        if already_present:
            continue
        continuation = json.loads(json.dumps(current))
        continuation["timing"]["measure"] = target_measure + 1
        continuation["timing"]["beat"] = 1.0
        continuation["timing"]["duration_beats"] = 1.0
        continuation.setdefault("modifiers", {})["attach_to"] = next_target.get("symbol_id")
        patched["symbols"].insert(adjusted_idx + 1, continuation)
    if reorder_header_measures:
        for measure in sorted(reorder_header_measures):
            measure_indices = [
                idx
                for idx, sym in enumerate(patched.get("symbols", []))
                if int(sym.get("timing", {}).get("measure", 1)) == measure
            ]
            if not measure_indices:
                continue
            measure_symbols = [patched["symbols"][idx] for idx in measure_indices]
            header_symbols = [sym for sym in measure_symbols if sym.get("modifiers", {}).get("measure_header")]
            content_symbols = [sym for sym in measure_symbols if not sym.get("modifiers", {}).get("measure_header")]
            ordered_headers = sorted(
                header_symbols,
                key=lambda sym: HEADER_FAMILY_ORDER.get(HEADER_FAMILY_BY_SYMBOL.get(sym.get("symbol_id", ""), ""), 99),
            )
            new_measure_symbols = ordered_headers + content_symbols
            for idx, sym in zip(measure_indices, new_measure_symbols):
                patched["symbols"][idx] = sym
    if reorder_repeat_measures:
        for measure in sorted(reorder_repeat_measures):
            measure_indices = [
                idx
                for idx, sym in enumerate(patched.get("symbols", []))
                if int(sym.get("timing", {}).get("measure", 1)) == measure
            ]
            if not measure_indices:
                continue
            measure_symbols = [patched["symbols"][idx] for idx in measure_indices]
            header_symbols = [sym for sym in measure_symbols if sym.get("modifiers", {}).get("measure_header")]
            repeat_start_symbols = [sym for sym in measure_symbols if sym.get("symbol_id") == "repeat.start"]
            repeat_end_symbols = [sym for sym in measure_symbols if sym.get("symbol_id") in {"repeat.end", "repeat.double"}]
            content_symbols = [
                sym
                for sym in measure_symbols
                if not sym.get("modifiers", {}).get("measure_header")
                and sym.get("symbol_id") != "repeat.start"
                and sym.get("symbol_id") not in {"repeat.end", "repeat.double"}
            ]
            new_measure_symbols = header_symbols + repeat_start_symbols + content_symbols + repeat_end_symbols
            for idx, sym in zip(measure_indices, new_measure_symbols):
                patched["symbols"][idx] = sym
    return patched


def _slugify_score_name(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    slug = "-".join(part for part in lowered.split("-") if part)
    return slug or "score"


def generate_score(args: dict) -> dict:
    ir = args["ir"]
    requested_name = args.get("name") or ir.get("metadata", {}).get("title") or "score"
    score_name = _slugify_score_name(requested_name)
    svg_path = SVG_EXAMPLES_DIR / f"{score_name}.svg"
    pdf_path = PDF_EXAMPLES_DIR / f"{score_name}.pdf"

    svg_content = render_svg(ir)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")

    pdf_created = svg_to_pdf(svg_content, pdf_path)
    relative_svg_path = svg_path.relative_to(REPO_ROOT).as_posix()
    relative_pdf_path = pdf_path.relative_to(REPO_ROOT).as_posix()
    preview_html = (
        '<div class="score-preview">'
        f'<object data="{relative_svg_path}" type="image/svg+xml" aria-label="{score_name}"></object>'
        "</div>"
    )
    result = {
        "svg_path": relative_svg_path,
        "pdf_path": relative_pdf_path if pdf_created else None,
        "latex": f"\\includegraphics{{{relative_pdf_path[:-4]}}}" if pdf_created else None,
        "preview_html": preview_html,
    }
    return result


TOOLS = {
    "plan_phrase": lambda args: parse_phrase(args["prompt"]),
    "build_ir": lambda args: phrase_plan_to_ir(args["phrase_plan"], args.get("source_prompt", "")),
    "validate_ir": lambda args: validate_ir(args["ir"]),
    "repair_ir": lambda args: repair_ir(args["ir"], args["diagnostics"]),
    "render_svg": lambda args: {"svg": render_svg(args["ir"])},
    "generate_score": generate_score,
}


def handle(req: dict) -> dict:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"serverInfo": {"name": "dancenotation-mcp", "version": "0.1.0"}}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": name, "description": f"{name} tool", "inputSchema": {"type": "object"}}
                    for name in TOOLS
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
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "json", "json": result}]}}
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


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        resp = handle(req)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
