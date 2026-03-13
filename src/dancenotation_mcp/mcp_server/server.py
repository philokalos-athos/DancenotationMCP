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


def repair_ir(ir: dict, diagnostics: dict) -> dict:
    patched = json.loads(json.dumps(ir))
    for hint in diagnostics.get("repair_hints", []):
        if hint["action"] == "set_duration":
            for sym in patched.get("symbols", []):
                if sym.get("timing", {}).get("duration_beats", 0) <= 0:
                    sym["timing"]["duration_beats"] = hint.get("value", 1.0)
        if hint["action"] == "replace_symbol":
            for sym in patched.get("symbols", []):
                if sym.get("symbol_id", "").startswith("unknown"):
                    sym["symbol_id"] = "support.step"
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
