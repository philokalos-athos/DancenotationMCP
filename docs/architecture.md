# DanceNotation MCP Architecture (Milestone 1)

## Goals
- Headless-first runtime for AI agents.
- Separate planning, IR, validation, rendering.
- Machine-readable outputs and diagnostics.
- Incremental path toward broader LabanWriter-like symbol coverage.

## Layered Design
1. **Planning layer** (`planning/`)
   - Parses natural language prompts into a deterministic `phrase_plan`.
2. **Canonical IR layer** (`ir/`)
   - Versioned `Score` model with `SymbolInstance` and timing.
3. **Validation layer** (`validation/`)
   - Schema checks + semantic checks + repair hints.
4. **Rendering layer** (`rendering/`)
   - Converts IR subset into SVG staff and symbol marks.
5. **MCP layer** (`mcp_server/`)
   - stdio JSON-RPC handlers exposing composable tools.

## Data Contracts
- `phrase_plan`: intermediate machine-readable action steps.
- `notation IR`: canonical score object with metadata and symbol instances.
- `diagnostics`: `{ok, issues[], repair_hints[]}`.

## Tool API (Milestone 1)
- `plan_phrase(prompt)`
- `build_ir(phrase_plan, source_prompt?)`
- `validate_ir(ir)`
- `repair_ir(ir, diagnostics)`
- `render_svg(ir)`

## Assumptions and Constraints
- Current parser is rule-based and intentionally conservative.
- Renderer currently draws a minimal symbol subset.
- Symbol catalog is seeded and expandable via JSON files.
- Not a GUI editor and not a cloud deployment target.

## Incremental Milestones
- **M1 (implemented):** Canonical IR + schema + validator + simple pipeline + minimal SVG + MCP tools.
- **M2:** richer lexicon, phrase grammar, stronger semantic constraints.
- **M3:** larger symbol geometry coverage and engraving-quality layout.
