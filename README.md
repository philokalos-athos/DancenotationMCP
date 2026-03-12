# DancenotationMCP

A local, single-user, headless-first dance notation MCP server inspired by LabanWriter/KineScribe workflows.

## Current status
This repository contains a milestone-1 runtime focused on agent-native tooling:
- Canonical notation IR model.
- JSON schema.
- Validator (schema + semantic rules + per-symbol constraints).
- Rule-based phrase planning pipeline.
- SVG renderer using symbol geometry metadata.
- Local MCP stdio server with composable tools.

## Symbol catalog coverage
The catalog is now heavily expanded and split into machine-editable JSON files in `resources/symbol_catalog/`:
- `support.json`
- `directions.json`
- `actions.json`
- `qualities.json`
- `timing.json`

Current total: **828 symbols** (expanded from 51). Every symbol includes:
- semantic constraints (`allowed_body_parts`, `requires_direction`, `allowed_directions`, `requires_level`, `allowed_levels`)
- geometry metadata (`geometry.glyph`, `width`, `height`, `anchor`, `staff_column`)

> Note: full one-to-one parity with every historic LabanWriter sign variant is still an ongoing target, but catalog structure is designed for that expansion.

## Architecture
See `docs/architecture.md`.

## MCP tools (stdio)
Implemented in `src/dancenotation_mcp/mcp_server/server.py`:
- `plan_phrase`
- `build_ir`
- `validate_ir`
- `repair_ir`
- `render_svg`

## Install / run as MCP server
From repo root:
```bash
PYTHONPATH=src python -m dancenotation_mcp.mcp_server.server
```

In a generic MCP client config (stdio mode), set:
- `command`: `python`
- `args`: `[-m, dancenotation_mcp.mcp_server.server]`
- `cwd`: `/workspace/DancenotationMCP`
- `env.PYTHONPATH`: `src`

## Tests, fixtures, examples
- Tests: `tests/`
- Fixtures: `fixtures/`
- Sample prompts: `examples/sample_prompts.md`
- Sample outputs:
  - `examples/sample_phrase_plan.json`
  - `examples/sample_score.ir.json`
  - `examples/sample_diagnostics.json`
  - `examples/sample_render.svg`

Run tests:
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Assumptions
- This is an agent runtime, not a desktop notation editor.
- Parsing is deterministic and still intentionally conservative in milestone 1.
- High-quality engraving layout is a future milestone.
