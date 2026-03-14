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
- [x] Create a fresh development branch from latest `origin/main`
  - Do not continue development on a branch that has already been merged
  - Preserve current worktree state before branching
- [x] Advance Milestone 2 parsing and semantic behavior model
  - Parsing coverage and language mapping
    - [x] Support richer action, direction, level, body-part, and duration words
    - [x] Support basic music/repeat language (`2/4`, `3/4`, `4/4`, `tempo 120`, `120 bpm`, `ritardando`, `rit.`, `a tempo`, `accelerando`, `accel.`, `begin repeat`, `end repeat`)
    - [x] Support short parallel connectors (`while`, `with`, `together`, `simultaneously`, `alongside`)
    - [x] Support short sequential connectors (`before`, `after`, `followed by`)
    - [x] Support explicit count language beyond current fixed phrases (`for four beats`, `half beat`, `quarter beat`, `and a half`)
    - [x] Support repetition/count language in prompts (`repeat twice`, `repeat three times`, `again`)
    - [x] Support negation and cancellation language (`without turn`, `no repeat`, `release hold`)
    - [x] Support conditional/qualifying language (`then immediately`, `slowly`, `suddenly then hold`)
    - [x] Support grouped clause parsing with parentheses/paired phrases where practical
    - [x] Support richer body language aliases (`head`, `chest`, `hips`, `both arms`, `both legs`, `hands`, `feet`)
    - [x] Support richer directional nuance (`upstage`, `downstage`, `clockwise`, `counterclockwise`, `in place`)
    - [x] Support parser normalization for punctuation-fragmented music words so abbreviations survive tokenization
  - Phrase planning behavior
    - [x] Honor active time signatures for measure rollover
    - [x] Keep structural music/repeat symbols from consuming beat time
    - [x] Emit companion `quality.*` and `timing.*` symbols from semantic adjectives
    - [x] Alternate default limbs for under-specified simple sequences
    - [x] Add phrase-planning heuristics for implied body continuity vs deliberate body switches
    - [x] Add phrase-planning heuristics for implied continuation of direction/level across short coordinated phrases
    - [x] Add phrase-planning support for explicit rests/pauses and silence gaps
    - [x] Add phrase-planning support for phrase-level repeat spans across multiple clauses/measures
    - [x] Add phrase-planning support for grouped simultaneous branches with different durations and proper anchor advancement
  - Semantic validation and repair hints
    - [x] Validate attachment source/target roles, target ordering, same-measure preference, and body-part preference
    - [x] Validate repeat span source/target roles, target ordering, nearest-closing behavior, and missing explicit targets
    - [x] Validate music-header ordering, duplication, position-before-content, and torso normalization
    - [x] Validate repeat boundary duplication, mixed-slot conflicts, torso normalization, boundary timing, and boundary ordering
    - [x] Validate measure overflow against active time signatures
    - [x] Repair invalid structures through remove/retarget/retime/reorder/set-body/set-modifier actions
    - [x] Add severity stratification review so truly invalid IR vs repairable stylistic warnings are consistently separated
    - [x] Add semantic rules for explicit rests interacting with attachments, repeats, and timing companions
    - [x] Add semantic rules for mutually exclusive modifiers on the same symbol (`hold` vs `staccato`, contradictory qualities, incompatible line styles)
    - [x] Add semantic rules for cross-measure continuity (`hold` continuation, sustained qualities, carried cadence/tempo scope)
      - [x] Detect missing next-measure continuation for `timing.hold`
      - [x] Detect missing next-measure continuation for `quality.sustained`
      - [x] Add carried cadence/tempo scope diagnostics beyond current redundancy checks
    - [x] Add semantic rules for measure-level completeness (`repeat.start`/`repeat.end` around empty measures, header-only measures, rest-only measures)
      - [x] Detect repeat boundaries around header-only measures
      - [x] Detect repeat boundaries around rest-only measures
      - [x] Detect repeat boundaries around fully empty measures
    - [x] Add semantic rules for multi-symbol body coordination (same body in impossible simultaneous directions/levels across primary motions)
    - [x] Add semantic rules for lane/family compatibility between anchors and companions (e.g. music attachments vs movement attachments)
    - [x] Add semantic rules for symbol-family-specific required modifiers beyond current generic checks
    - [x] Expand repair hint vocabulary where current fixes are too blunt (symbol replacement, semantic downgrade, split duration, insert rest)
    - [x] Ensure repair ordering is deterministic when multiple semantic families compete (headers, repeats, attachments, timing)
  - Symbol behavior model
    - [x] Add machine-readable geometry and semantic constraints to the catalog
    - [x] Add official extras for repeat/music/path/pin/motif/surface/space families
    - [x] Audit catalog entries for one-to-one behavior completeness against current validator and renderer assumptions
    - [x] Add richer behavior metadata for stretchable families (minimum/maximum stretch, repeatable segments, cap shapes)
    - [x] Add richer behavior metadata for repeat/music families (boundary role, header role, continuation scope, default repair target family)
    - [x] Add richer behavior metadata for attachment families (preferred anchor side, valid anchor families, coverage expectations)
    - [x] Add richer behavior metadata for direction/level transformations (mirroring, flipping, rotation rules)
    - [x] Add richer behavior metadata for motif/path variants and composition rules
    - [x] Add explicit behavior metadata for whitespace/surface/contact signs rather than relying on generic column family rules
    - [x] Add catalog audit tests to ensure every behavior-bearing family has the metadata needed by parser, validator, and renderer
- [ ] Advance Milestone 3 engraving router and family-specific layout
  - Engraving router
    - [x] Add attachment clearance and dogleg routing beyond simple elbows
    - [x] Add shared lane allocation across attachment, bridge, and repeat-span families
    - [x] Add routing-priority scoring and limited lane reuse
    - [x] Add richer path shaping choices beyond current straight/dogleg fallback (multi-elbow, shallow arc, family-aware dogleg)
    - [x] Add collision avoidance against symbol bounding boxes instead of only family lanes
    - [x] Add explicit crossing minimization between long routed lines and measure-header gutters
    - [x] Add track reuse that considers geometry width and not only span overlap
    - [x] Add route bundling/splitting rules for many attachments in one measure
    - [x] Add deterministic left/right routing preferences by family and anchor side
    - [x] Add route simplification to reduce visual noise when no blockers remain after other repairs
  - Measure and staff layout
    - [x] Add measure header bands, dynamic header gutters, measure-priority layers, and boundary slot offsets
    - [x] Make measure width and spacing respond to actual symbol complexity, not only header width and fixed beat geometry
    - [x] Add per-measure density balancing so crowded measures expand while sparse measures compress
    - [x] Add staff-height adaptation when annotation families, repeat spans, and attachments stack deeply
    - [x] Add better vertical zoning for music, repeat, annotation, and movement layers across the full staff
    - [x] Add continuity-aware placement for symbols spanning multiple measures
    - [x] Add system-level layout for multi-staff/page output rather than one long canvas
  - Family-specific geometry
    - [x] Add specialized geometry for path, turn, jump, pin, repeat, music, separator, motif, surface, and space families
    - [x] Add variant detail for `turn.spin`, `pin.hold`, stretched `jump`, `path.circle`, `separator.single/double/final`, and selected music/repeat variants
    - [x] Expand family-specific geometry for more official variants (`pins`, `repeats`, `music signs`, `surface signs`, `motif` variants, whitespace variants)
    - [x] Implement truly stretchable geometry with cap/body/cap composition instead of scaled static outlines
    - [x] Implement direction-aware and mirror-aware geometry variants where glyph behavior should change with orientation
    - [x] Implement variant geometry for more jump/turn/path subclasses and official transition marks
    - [x] Replace remaining generic block rendering for specialized families with family-native silhouettes
    - [x] Add family-specific typography/label handling where music and cadence signs should not look like generic text badges
  - LabanWriter-style behavior parity
    - [x] Cross-audit current families against the LabanWriter manual categories and identify uncovered sign variants
    - [x] Add more explicit support for whitespace, springs, bows, hooks, separators, and motif combinations noted by the manual
    - [x] Make renderer behavior follow symbol-role semantics from the catalog rather than hard-coded family lists where possible
    - [x] Improve visual parity for official line styles, fills, contours, and attachment conventions
    - [x] Add screenshot/golden-SVG regression tests for representative official-family layouts
  - Renderer robustness
    - [x] Add snapshot-style regression tests for complex multi-measure scores, not only targeted string assertions
    - [x] Add renderer tests that combine headers, repeats, attachments, quality/timing marks, and stretched symbols in one score
    - [x] Add PDF-level smoke assertions for representative engraving-heavy examples
- [x] Open a new PR from the fresh branch with sample SVG + PDF attached

## Current Status
_Update this section at the end of each batch before stopping._

Last completed: Opened PR #6 from `codex/m2-m3-engraving-semantics` with the completed Milestone 2/3 work, golden SVG fixture coverage, and PDF smoke verification
Next: All tracked tasks in this file are complete

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
