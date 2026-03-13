# Repository Guidelines

## Project Structure & Module Organization
Core package code lives in `src/dancenotation_mcp/` and is split by responsibility: `planning/` parses phrases, `ir/` defines the canonical score model, `validation/` enforces schema and semantic rules, `rendering/` produces SVG and PDF, and `mcp_server/` exposes stdio MCP tools. Tests are in `tests/`, JSON fixtures in `fixtures/`, sample outputs in `examples/` (with `examples/svg/` and `examples/pdf/` subdirectories), schemas in `schemas/`, and symbol metadata in `resources/symbol_catalog/`. Architecture notes live in `docs/architecture.md`.

## Build, Test, and Development Commands
Use Python 3.10+.

- `python -m pip install -e .` installs the package in editable mode.
- `python -m pip install cairosvg` installs the SVG-to-PDF renderer (required for PDF output).
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` runs the full test suite locally.
- `$env:PYTHONPATH='src'; python -m dancenotation_mcp.mcp_server.server` starts the local stdio MCP server.
- `.\scripts\pr_auto.ps1 -Base main -Title "..." -Body "..."` pushes a branch and opens or updates a PR.

CI in `.github/workflows/ci.yml` installs the package and runs the same `unittest` command on pushes to `main` and on pull requests.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints where useful, and small focused modules. Use `snake_case` for functions, variables, and module names; `PascalCase` for test classes; and descriptive JSON IDs such as `support.step.forward`. Keep imports explicit and grouped by standard library first, then local modules. No formatter or linter is configured yet, so match surrounding code closely and keep diffs minimal.

## PDF Output Specification
Every `generate_score` call must produce both SVG and PDF in a single operation.

- SVG is saved to `examples/svg/{name}.svg` and returned as the primary render.
- PDF is generated from SVG via `cairosvg.svg2pdf()` and saved to `examples/pdf/{name}.pdf`.
- Both paths and a ready-to-paste LaTeX snippet are returned in the tool response:
```
  \includegraphics{examples/pdf/{name}}
```
- If `cairosvg` is unavailable, log a warning and return SVG only — do not raise.
- PDF generation must not increase total tool response time by more than 500 ms on typical scores.

## Task List
Work through this list in order. Mark each item `[x]` immediately upon completion. Do not wait for user confirmation between tasks — proceed autonomously unless a decision point requires input.

- [x] Project structure initialization
- [x] SVG generation core logic (`rendering/svg_renderer.py`)
- [x] MCP tool scaffolding (`mcp_server/server.py`)
- [x] Integrate `cairosvg` PDF output into `generate_score`
  - Add `cairosvg` to `pyproject.toml` dependencies
  - Create `rendering/pdf_renderer.py` with `svg_to_pdf(svg_content, path)` helper
  - Update `generate_score` tool to call PDF renderer after SVG is written
  - Return `{svg_path, pdf_path, latex, preview_html}` dict from tool
- [x] Update `examples/` directory structure (`svg/` and `pdf/` subdirs)
- [x] Add tests for PDF output (`tests/test_pdf_renderer.py`)
  - Verify PDF file is created alongside SVG
  - Verify `cairosvg` unavailable path returns SVG-only without crash
- [x] Update `docs/architecture.md` to document dual-output rendering pipeline
- [x] Install system Cairo runtime and verify real PDF export
  - Ensure `generate_score` returns a non-null `pdf_path` on this machine
  - Generate a real sample PDF in `examples/pdf/`
  - Keep SVG-only fallback behavior covered by tests
- [ ] Create a fresh development branch from latest `origin/main`
  - Do not continue development on a branch that has already been merged
  - Preserve current worktree state before branching
- [ ] Advance Milestone 3 engraving router and family-specific layout
  - Improve routed attachment path shaping beyond simple elbows
  - Refine multi-line crossing priority across bridge/span/attachment families
  - Add more realistic stretchable and family-specific geometry rules
  - Move closer to LabanWriter-style variant-specific engraving behavior
- [ ] Advance Milestone 2 parsing and semantic behavior model
  - Expand phrase parsing coverage and richer language mapping
  - Strengthen multi-symbol semantic validation and repair hints
  - Increase symbol behavior modeling beyond current catalog constraints
- [ ] Open a new PR from the fresh branch with sample SVG + PDF attached

## Current Status
_Update this section at the end of each batch before stopping._

Last completed: Installed GTK/Cairo runtime, restored real PDF export, and generated `examples/pdf/sample-render.pdf`
Next: Create a fresh development branch from latest `origin/main`, then continue Milestone 3 engraving and Milestone 2 parsing/semantics work

## Autonomous Work Rules
- On startup: read this file, find the first unchecked `[ ]` task, begin immediately.
- On task completion: mark `[x]`, update **Current Status**, proceed to next task.
- Pause and ask only when: a dependency conflict arises, a design decision has multiple valid approaches, or a test fails in an unexpected way.
- Do not pause to say "I've finished X, shall I continue?" — just continue.

## Testing Guidelines
Tests use `unittest` and live in `tests/test_*.py`. Add targeted fixture-based tests when changing validation rules, renderer behavior, or MCP tool responses. Prefer assertions against visible contract data such as issue codes, SVG markers, IR fields, and PDF file existence. Run the full suite before opening a PR.

## Commit & Pull Request Guidelines
Recent history uses short imperative commit subjects such as `Add CI workflow...`, `Remove...`, and `Resolve merge conflicts...`. Keep commit titles concise, capitalized, and action-oriented. PRs should include a clear summary, note any schema or catalog changes, link related issues when applicable, and attach sample SVG **and PDF** output when behavior changes are user-visible.

## Security & Configuration Tips
This project is local and headless by design. Do not add network-dependent runtime behavior without discussion. Keep large catalog or fixture edits machine-readable JSON, and preserve `PYTHONPATH=src` in local commands so imports and CI stay aligned.
