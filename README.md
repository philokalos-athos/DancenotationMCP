# DancenotationMCP

A local, single-user, headless-first dance notation MCP server inspired by LabanWriter/KineScribe workflows.

## 1) Repository current state (inspection summary)
This repository now contains a milestone-1 implementation focused on agent-native tooling:
- Canonical notation IR model.
- JSON schema.
- Validator (schema + semantic rules).
- Rule-based phrase planning pipeline.
- Minimal SVG renderer.
- Local MCP stdio server with composable tools.

## 2) Implementation plan and milestones
- **Milestone 1 (implemented):**
  - Canonical IR + schema + validation.
  - Prompt -> phrase plan -> IR.
  - Minimal SVG output.
  - MCP tools for plan/build/validate/repair/render.
- **Milestone 2 (next):** richer language parsing + stronger semantics + larger symbol behavior model.
- **Milestone 3 (next):** expanded engraving-quality rendering and larger coverage of notation signs.

## 3) Architecture
See `docs/architecture.md`.

## 4) Milestone 1 scope details
### Canonical notation IR
- Data classes in `src/dancenotation_mcp/ir/models.py`.
- Versioned metadata (`ir_version`, `schema_version`).

### JSON schema
- `schemas/notation-ir.schema.json`.

### Validator
- `src/dancenotation_mcp/validation/validator.py`.
- Outputs machine-readable diagnostics and repair hints.

### Phrase-plan pipeline
- `planning/phrase_parser.py`: prompt -> `phrase_plan`.
- `planning/phrase_to_ir.py`: `phrase_plan` -> canonical IR.

### SVG renderer
- `rendering/svg_renderer.py` for minimal subset rendering.

### Local MCP stdio server tools
- `src/dancenotation_mcp/mcp_server/server.py`.
- Tools:
  - `plan_phrase`
  - `build_ir`
  - `validate_ir`
  - `repair_ir`
  - `render_svg`

Run server:
```bash
PYTHONPATH=src python -m dancenotation_mcp.mcp_server.server
```

## 5) Tests, fixtures, example resources
- Tests: `tests/`.
- Fixtures: `fixtures/`.
- Sample prompts: `examples/sample_prompts.md`.
- Sample outputs:
  - `examples/sample_phrase_plan.json`
  - `examples/sample_score.ir.json`
  - `examples/sample_diagnostics.json`
  - `examples/sample_render.svg`

Run tests:
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Symbol catalog strategy
`resources/symbol_catalog/` contains a seeded, extensible symbol inventory split by categories (support, direction, actions, qualities/levels). This is intended as a growth path toward broad Laban-style notation coverage while keeping milestone-1 implementation verifiable and incremental.

## Assumptions
- This is an agent runtime, not a desktop notation editor.
- Parsing is intentionally deterministic and minimal in milestone 1.
- Networking/cloud deployment is out of scope.
