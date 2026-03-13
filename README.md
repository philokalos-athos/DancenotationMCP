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

## Implementation milestones
- **Milestone 1 (implemented):**
  - Canonical IR + schema + validation.
  - Prompt -> phrase plan -> IR.
  - SVG output using symbol geometry metadata.
  - MCP tools for plan/build/validate/repair/render.
- **Milestone 2 (next):** richer language parsing + stronger semantics + larger symbol behavior model.
- **Milestone 3 (in progress):** expanded engraving-quality rendering and larger coverage of notation signs.

## Symbol catalog coverage
The catalog is split into machine-editable JSON files in `resources/symbol_catalog/`:
- `support.json`
- `directions.json`
- `actions.json`
- `qualities.json`
- `timing.json`
- `official_extras.json`

Current total: **871 symbols** (expanded from 51). Every symbol includes:
- semantic constraints (`allowed_body_parts`, `requires_direction`, `allowed_directions`, `requires_level`, `allowed_levels`)
- geometry metadata (`geometry.glyph`, `width`, `height`, `anchor`, `staff_column`)

The `official_extras.json` layer adds LabanWriter manual-derived families that were previously missing from the machine catalog surface, including path, bow, pin, repeat, dynamics, ad lib, music/time, motif, separator, flexion/extension, foot hooks, and finger/toe marks.

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
- `generate_score`

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
  - `examples/svg/`
  - `examples/pdf/`

`generate_score` persists SVG to `examples/svg/{name}.svg`, attempts PDF export to `examples/pdf/{name}.pdf`, and returns `{svg_path, pdf_path, latex, preview_html}` for downstream automation.

Run tests:
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## GitHub automation
This repository now includes a minimal CI workflow at `.github/workflows/ci.yml` that runs the test suite on pushes to `main` and on pull requests. Set your branch protection required check to `test` after the workflow runs once.

For local GitHub automation with `gh`:
```powershell
# Push current branch, create/update PR, and enable auto-merge
.\scripts\pr_auto.ps1 -Base main -Title "Your PR title" -Body "Your PR body" -AutoMerge
```

For full Codex CLI automation:
```powershell
# Requires: git auth for push, gh auth login, codex installed
.\scripts\codex_full_auto.ps1 -Prompt "Implement X and update tests" -Base main
```

What the full automation script does:
- creates or resets a feature branch
- runs `codex exec` with your prompt
- commits all resulting changes
- pushes the branch
- creates or updates a PR
- enables GitHub auto-merge with squash strategy

## Symbol catalog strategy
`resources/symbol_catalog/` contains a seeded, extensible symbol inventory split by categories (support, direction, actions, qualities/levels). This is intended as a growth path toward broad Laban-style notation coverage while keeping milestone-1 implementation verifiable and incremental.

The renderer now supports an engraving-oriented modifier and layout layer for official notation behaviors documented in the LabanWriter manual:
- mixed high/middle/low fills within one symbol block
- degree badges for turns and rotations
- dotted/double line styles
- whitespace bands
- surface marks
- spring/jump takeoff and landing supports
- arrowheads for paths and travel motifs
- explicit attachment routing between dependent and primary symbols
- per-measure music header bands with dynamic gutter spacing based on header content
- repeat spans and repeat/separator bridge rules
- measure-boundary separators that span the full measure band
- measure-boundary slot offsets for repeat, separator, and music signs sharing the same beat
- measure-priority layering for repeat, quality, level, and timing annotation columns
- repeat-span clearance that routes outside competing quality/level/timing annotation families
- attachment-line clearance that reroutes around repeat and annotation layers when crossings would clutter the staff
- multi-track attachment routing so multiple clearance lines in one measure do not collapse onto the same path
- reusable attachment tracks so non-overlapping routed lines in the same measure can share the same clearance lane
- shared routing lane allocation across repeat-separator bridges and attachment lines so long-line elements negotiate the same staff space
- shared routing lane allocation for repeat spans as well, so vertical repeat extents shift outward when bridges or routed attachments already occupy the outer engraving corridor
- routing-priority lane scoring so bridges keep the outer corridor, repeat spans yield inward, and attachments fall back to deeper tracks only when higher-priority engraving lines already claim the cleaner lanes
- crossing-aware lane reuse so a repeat span can stay on the outer corridor when a bridge occupies the same track number but does not geometrically cross the span's x-position

## Assumptions
- This is an agent runtime, not a desktop notation editor.
- Parsing is deterministic and intentionally conservative in milestone 1.
- Networking/cloud deployment is out of scope.
- Full historical one-to-one LabanWriter parity is still a future milestone.
