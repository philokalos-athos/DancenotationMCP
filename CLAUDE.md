# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A local, single-user, headless-first dance notation MCP server for AI agents. It parses natural-language movement prompts into Labanotation IR, validates/repairs scores, and renders SVG+PDF output. Not a GUI editor, not a cloud service.

## Build & Run

Requires Python 3.10+. Source lives under `src/` with `PYTHONPATH=src` required for all commands.

```bash
# Install (editable mode)
python -m pip install -e .

# Install PDF support (optional but expected)
python -m pip install cairosvg

# Run MCP server (stdio JSON-RPC)
PYTHONPATH=src python -m dancenotation_mcp.mcp_server.stdio_main

# Run full test suite
PYTHONPATH=src python -m unittest discover -s tests -v

# Run a single test file
PYTHONPATH=src python -m unittest tests.test_pipeline -v

# Run a single test method
PYTHONPATH=src python -m unittest tests.test_pipeline.TestPipeline.test_method_name -v
```

On Windows PowerShell, use `$env:PYTHONPATH='src'` instead of the Unix prefix.

**Entry points**: `mcp_server/stdio_main.py` is the only working MCP entry point — it
uses the official `mcp` SDK, whose stdio transport is newline-delimited JSON.
`mcp_server/server.py` holds the tool registry (`TOOLS`, `TOOL_SCHEMAS`) that
`stdio_main` imports, but its own `main()` implements LSP-style `Content-Length`
framing and will exit 0 without a word if a real MCP client connects to it.
Point launchers and client configs at `stdio_main`.

CI (`.github/workflows/ci.yml`) runs `unittest discover` on Python 3.11 for pushes to `main` and PRs. The required check name is `test`.

## Architecture

Five-layer pipeline, each layer in its own subpackage under `src/dancenotation_mcp/`:

```
prompt text
    │
    ▼
planning/          phrase_parser.py → phrase_to_ir.py
    │              Parses NL prompts into phrase_plan steps,
    │              then builds canonical IR from those steps.
    ▼
ir/                models.py (Score, SymbolInstance dataclasses)
    │              catalog.py (loads symbol_catalog JSON files)
    ▼
validation/        validator.py
    │              Schema checks → semantic checks → catalog-constrained checks.
    │              Produces {ok, issues[], repair_hints[]} diagnostics.
    ▼
rendering/         svg_renderer.py → pdf_renderer.py
    │              Metadata-driven SVG layout + optional CairoSVG PDF.
    ▼
mcp_server/        server.py
                   Exposes 6 stdio MCP tools: plan_phrase, build_ir,
                   validate_ir, repair_ir, render_svg, generate_score.
```

Key data contracts flowing between layers:
- **phrase_plan**: intermediate action steps (JSON)
- **notation IR**: canonical `Score` object with metadata and `SymbolInstance` list
- **diagnostics**: `{ok, issues[], repair_hints[]}` with severity split (error vs warning)
- **generate_score output**: `{svg_path, pdf_path, latex, preview_html}`

## Symbol Catalog

`resources/symbol_catalog/` contains 1,122 symbols across 14 JSON files (actions, contact,
directions, effort, flexion_extension, floor_plan, foot_detail, official_extras, qualities,
retention, sequential, shape, support, timing). Every `*.json` in that directory is loaded,
so adding a file needs no code change. Each entry carries:
- Semantic constraints: `allowed_body_parts`, `requires_direction`, `allowed_levels`, etc.
- Geometry metadata: `glyph`, `width`, `height`, `anchor`, `staff_column`
- Behavior metadata (varies by family): `boundary_role`, `header_role`, `preferred_anchor_side`, `path_shape`, `composition_role`, stretch parameters, etc.

The catalog is the single source of truth for parser, validator, and renderer behavior. When adding symbols or changing families, ensure the catalog entry has the metadata fields expected by all three consumers. Catalog audit tests in `tests/test_catalog_constraints.py` enforce this.

## Schema

`schemas/notation-ir.schema.json` defines the canonical IR JSON structure. The validator checks against this schema first, then applies semantic rules.

## Fixtures and Golden Tests

- `fixtures/valid_minimal_score.json` — minimal valid IR for smoke tests
- `fixtures/invalid_overlap_timing.json` — known-bad IR for validation tests
- `fixtures/golden_official_family_score.{json,svg}` — golden regression fixture for engraving layout; tests compare rendered SVG against the golden file

## Key Conventions

- **Style**: 4-space indent, type hints where useful, `snake_case` for functions/vars, `PascalCase` for test classes. No formatter/linter configured — match surrounding code.
- **Symbol IDs**: dotted hierarchical names like `support.step.forward`, `music.time.3_4`, `repeat.start`.
- **PDF output**: `generate_score` always attempts dual SVG+PDF. If `cairosvg` is missing, degrade to SVG-only (warn, don't raise). PDF must not add >500ms to response time.
- **Output paths**: SVG → `examples/svg/{name}.svg`, PDF → `examples/pdf/{name}.pdf`.
- **Imports**: `PYTHONPATH=src` is required. Imports use `from dancenotation_mcp.ir.models import ...` style.
- **Commits**: short imperative subjects (`Add ...`, `Fix ...`, `Remove ...`). PRs should attach sample SVG+PDF when behavior changes are visible.
- **No network**: this is local-only by design. Don't add network-dependent runtime behavior.
