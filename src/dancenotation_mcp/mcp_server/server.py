from __future__ import annotations

import json
import sys

from dancenotation_mcp.planning.phrase_parser import parse_phrase
from dancenotation_mcp.planning.phrase_to_ir import phrase_plan_to_ir
from dancenotation_mcp.rendering.svg_renderer import render_svg
from dancenotation_mcp.validation.validator import validate_ir


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


TOOLS = {
    "plan_phrase": lambda args: parse_phrase(args["prompt"]),
    "build_ir": lambda args: phrase_plan_to_ir(args["phrase_plan"], args.get("source_prompt", "")),
    "validate_ir": lambda args: validate_ir(args["ir"]),
    "repair_ir": lambda args: repair_ir(args["ir"], args["diagnostics"]),
    "render_svg": lambda args: {"svg": render_svg(args["ir"])} ,
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
