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

Recent Milestone 2 semantic upgrades also enforce modifier-role behavior, including:
- attachment source/target role checks
- repeat-span source/target role and closing-variant checks
- measure-header family checks
- orphaned modifier dependency checks such as `attach_side` without `attach_to`
- measure-level timing checks such as overflow past beat 4 and duplicate measure-header stacks
- phrase parsing that rolls long prompts across measures instead of leaving every step in measure 1
- default limb alternation for unqualified step/glide/brush sequences so parser output is less likely to create avoidable same-limb conflicts
- attachment semantics that prefer primary targets on the same body_part during repair
- repeat-structure semantics that detect orphaned `repeat.start` / `repeat.end` signs and remove structurally unmatched repeat markers during repair
- repeat-span semantics that reject explicit targets which skip a nearer valid closing repeat sign, and retarget them to the closest closing marker during repair
- music-header semantics that detect redundant consecutive time signatures and remove repeated unchanged meter headers during repair
- tempo-header semantics that detect redundant consecutive unchanged tempi and remove repeated identical tempo headers during repair
- cadence-header semantics that detect redundant consecutive unchanged cadence labels and remove repeated identical cadence headers during repair
- within-measure header-family semantics that detect multiple time-signature/tempo/cadence headers of the same family in one measure and remove later duplicates during repair
- repeat-end slot semantics that detect multiple closing repeat signs on the same measure/beat slot and remove redundant duplicates during repair
- repeat-start slot semantics that detect multiple opening repeat signs on the same measure/beat slot and remove redundant duplicates during repair
- mixed repeat-boundary semantics that reject opening and closing repeat signs sharing the same slot and remove conflicting boundary markers during repair
- timing-overlap semantics now evaluate within each measure instead of leaking across measure boundaries, so legal rollover into the next measure is not misdiagnosed
- phrase parsing now covers music/repeat language such as `3/4`, `tempo 120`, `ritardando`, `begin repeat`, and `end repeat`, and preserves these as semantic modifiers in IR
- phrase parsing now also recognizes `120 bpm`, `accelerando`, and `accel.` as music-header language, so tempo/cadence phrases do not need explicit `tempo` or long-form cadence wording
- header semantics now allow stacked different header families within one measure while still rejecting duplicate families within the same header band
- structural music/repeat symbols no longer consume beat time in phrase parsing, and parsed `repeat.start` markers automatically link to the next closing repeat sign in IR construction
- phrase parsing now supports parallel `while` / `with` clauses so simultaneous actions share the same beat and only the longest branch advances time
- phrase parsing now also recognizes `together` / `simultaneously` as parallel-action language, keeping multi-limb actions aligned on the same beat
- phrase parsing also recognizes `alongside` as parallel-action language for short simultaneous phrases
- phrase parsing now understands `before` / `after` connectors, so simple temporal ordering language becomes explicit step order instead of relying on surface token order
- phrase parsing also recognizes `followed by` as a sequential connector for short action chains
- clause-level semantic words such as `sudden` and `accented` now emit companion `quality.*` / `timing.*` symbols directly from the parser
- duration language such as `hold`, `sustain`, and `linger` now emits a real `timing.hold` sign in addition to extending `duration_beats`
- IR construction now auto-attaches parsed `quality` / `timing` companions to the nearest same-measure primary motion, preferring the same `body_part`
- IR auto-attachment now prefers same-measure primary motions whose duration still covers the annotation beat, reducing semantically stale anchors
- annotation-family semantics now detect orphaned `pin` / `surface` / `quality` / `level` / `timing` symbols with no anchor and repair them by adding an `attach_to` target instead of leaving them semantically detached
- attachment semantics now reject cross-measure `attach_to` targets and repair them toward an earlier primary motion in the same measure whenever possible
- attachment semantics now also reject anchors whose motion has already ended before the annotation beat, and repair them toward a primary motion whose duration still covers that beat
- measure-header semantics now enforce a canonical in-measure order of time signature, then tempo, then cadence, and repair out-of-order header stacks by reordering them
- measure headers must also precede content symbols within the same measure, and repair will lift misplaced header stacks to the front of that measure
- measure headers are semantically normalized onto `body_part: torso`, and repair will correct misplaced limb assignments on music headers
- repeat-family symbols are likewise normalized onto `body_part: torso`, and repair will correct stray limb assignments on repeat boundaries
- timing semantics now honor active `music.time.*` headers, so overflow detection and duration repair use the current measure's actual beat capacity instead of assuming every measure is 4/4
- phrase planning now also honors active `music.time.*` headers, so measure rollover in parsed phrase plans follows 2/4 or 3/4 capacity instead of staying hard-coded to 4/4
- repeat-boundary timing semantics now align `repeat.start` to beat 1 and `repeat.end`/`repeat.double` to the last beat of the active measure during repair
- repeat-boundary ordering semantics now keep `repeat.start` before measure content and closing repeat signs after measure content, with repair reordering those boundary markers around the measure body
- executable repair hints that remove, retarget, or retime invalid relationships

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
- dogleg-shaped attachment routing for cross-beat clearance paths, so longer attachments approach their target lane with a cleaner final jog instead of a single blunt elbow
- more family-specific geometry for `turn.spin`, `pin.hold`, and stretched `jump` symbols, including spin echo arcs, hold crossbars, and secondary jump contours

## Assumptions
- This is an agent runtime, not a desktop notation editor.
- Parsing is deterministic and intentionally conservative in milestone 1.
- Networking/cloud deployment is out of scope.
- Full historical one-to-one LabanWriter parity is still a future milestone.
