# DanceNotation MCP Architecture (Milestone 1 + Catalog Expansion)

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
3. **Catalog layer** (`resources/symbol_catalog/*.json`)
   - Large symbol inventory with per-symbol semantics and geometry.
4. **Validation layer** (`validation/`)
   - Schema checks + semantic checks + catalog-constrained checks + repair hints.
5. **Rendering layer** (`rendering/`)
   - Uses symbol geometry metadata to render SVG in a staff-like layout.
   - Converts SVG to PDF via `rendering/pdf_renderer.py` when `generate_score` is used.
6. **MCP layer** (`mcp_server/`)
   - stdio JSON-RPC handlers exposing composable tools.

## Data Contracts
- `phrase_plan`: intermediate machine-readable action steps.
- `notation IR`: canonical score object with metadata and symbol instances.
- `diagnostics`: `{ok, issues[], repair_hints[]}`.
- `generate_score` output: `{svg_path, pdf_path, latex, preview_html}` with SVG as the primary render artifact and PDF as a best-effort companion.
- `symbol catalog entry`:
  - `id`, `category`, `name`
  - `allowed_body_parts`, `requires_direction`, `allowed_directions`
  - `requires_level`, `allowed_levels`
  - `geometry` (`glyph`, `width`, `height`, `anchor`, `staff_column`)

## Tool API
- `plan_phrase(prompt)`
- `build_ir(phrase_plan, source_prompt?)`
- `validate_ir(ir)`
- `repair_ir(ir, diagnostics)`
- `render_svg(ir)`
- `generate_score(ir, name?)`

## Assumptions and Constraints
- Parser is rule-based and intentionally conservative.
- Renderer is metadata-driven and now emits dual SVG/PDF score artifacts.
- Catalog is intentionally broad and machine-augmentable.
- Not a GUI editor and not a cloud deployment target.
- PDF generation is best-effort and degrades to SVG-only if `cairosvg` is unavailable.

## Incremental Milestones
- **M1 (implemented):** Canonical IR + schema + validator + simple pipeline + minimal SVG + MCP tools.
- **M1.1 (implemented):** large expanded catalog + per-symbol semantic constraints + geometry metadata validation/render usage.
- **M2:** richer lexicon, phrase grammar, stricter multi-limb simultaneity rules.
- **M3:** high-quality engraving layout and additional notational families.
- **M3.1 (implemented):** dual-output score generation with SVG persistence, optional PDF export, and MCP delivery metadata for downstream LaTeX/doc workflows.
