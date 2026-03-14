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
- phrase parsing now also understands richer count language such as `for four beats`, `half beat`, `quarter beat`, `one and a half beats`, plus repeat-count prompts like `repeat twice` and `repeat three times`
- phrase planning now also supports explicit `rest`, `pause`, and `silence` language, mapping short gaps onto `music.rest.quarter`, `music.rest.eighth`, and `music.rest.sixteenth`
- phrase parsing now also understands cancellation and qualifier language such as `without turn`, `no repeat`, `release hold`, `slowly`, and `then immediately`, including modifier-only follow-up clauses like `suddenly then hold`
- phrase parsing now supports parenthetical grouped clauses in practical short-form prompts, richer plural body aliases such as `both hands` / `both feet`, and punctuation-tolerant music abbreviations like `accel .` and `rit .`
- phrase planning now preserves implied body, direction, and level across short continuation clauses when no new body/direction/level cue is given, instead of always resetting to default alternation or `forward/middle`
- grouped simultaneous branches now keep their own local clause timing inside `while (...)` style phrases, so parallel branches with different durations advance the main phrase by the longest branch instead of collapsing into a flat one-step parallel block
- header semantics now allow stacked different header families within one measure while still rejecting duplicate families within the same header band
- structural music/repeat symbols no longer consume beat time in phrase parsing, and parsed `repeat.start` markers automatically link to the next closing repeat sign in IR construction
- phrase-level repeat spans are now locked by tests across multiple clauses and measures, so parsed repeat structures remain connected after measure rollover
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
- mutually exclusive timing/quality companion semantics now reject contradictory companions on the same anchor and beat, and repair them by removing the later conflicting symbol
- explicit rest semantics now reject rests that overlap active movement or companion content in the same measure window, and repair those collisions by removing the conflicting rest sign
- semantic diagnostics now use a centralized severity split: structurally invalid IR remains `error`, while repairable overflow/order/conflict conditions stay `warning`
- cross-measure continuity diagnostics now report missing next-measure continuation when `timing.hold` or `quality.sustained` reaches a measure boundary and the same body resumes on beat 1 in the next measure
- repeat-boundary completeness diagnostics now reject empty, header-only, and rest-only measures wrapped by repeat boundaries
- key repeat/music entries now carry machine-readable behavior metadata such as `boundary_role`, `header_role`, `continuation_scope`, and `default_repair_target_family`, and semantic validation consumes that metadata for repeat/header role checks
- lane/family compatibility diagnostics now reject `music` and `repeat` symbols that incorrectly use movement-style `attach_to` anchors, and repair removes those incompatible attachments
- multi-symbol body coordination diagnostics now distinguish generic same-body overlap from stricter direction/level contradictions on overlapping primary motions, and repair can shift the later conflicting motion forward in time
- score-scoped `tempo` and `cadence` continuity is now modeled during repair, so later headers with missing content inherit the previous carried value or label instead of always falling back to generic defaults
- family-specific required modifier semantics are now modeled for selected official variants such as `pin.entry` and `separator.single/double`, and repair normalizes them to the variant-appropriate `pin_head` / `separator_mode`
- repair now carries richer executable actions, including `split_duration` for measure overflow and inserted continuation companions for missing cross-measure `hold` continuity, with deterministic priority ordering when multiple semantic families compete
  - behavior-bearing attachment families now carry explicit `preferred_anchor_side`, `valid_anchor_families`, and `coverage_expectation` metadata, and validator coverage checks consume that metadata before falling back to generic annotation-family assumptions
  - catalog audit tests now lock behavior completeness for repeat/music/attachment families so parser, validator, and renderer assumptions stay aligned as the symbol library grows
  - direction/level-transforming families now also carry machine-readable behavior metadata such as `direction_transform`, `rotation_rule`, `flip_variant`, and `level_fill_mode`, so future renderer work can shift more mirroring/fill behavior out of hard-coded family tables
  - `path` / `motif` entries now carry composition metadata like `composition_role`, `path_shape`, `repeatable_segment`, and `motif_variant`, while `surface` / `space` entries carry explicit `surface_role`, `anchor_mode`, `whitespace_role`, and `layout_effect` fields instead of relying only on generic staff-column assumptions
  - stretchable families now expose explicit `min_stretch`, `max_stretch`, `repeatable_segment`, and `cap_shape` metadata for path/pin/space/separator variants, giving Milestone 3 renderer work a machine-readable basis for cap/body/cap layout instead of pure scalar heuristics

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
- family-aware `multi-elbow` attachment routing for pin-driven cross-beat connections, exposed in SVG via `data-route` markers for regression testing
- symbol-bounding-box-aware collision avoidance for routed lines, so attachment, bridge, and span tracks avoid intersecting occupied symbol silhouettes rather than only family lanes
- measure-header-gutter-aware routing penalties, so routed tracks can step down or outward when the cleaner lane would clip the header band corridor in dense header measures
- geometry-width-aware track reuse, so very wide routed lines reserve a small guard band and do not reuse tracks that are only technically non-overlapping by a few pixels
- bundle/split routing for dense `pin` / `surface` / `music` attachment groups, so three or more external companions aimed at one target can share a corridor before splitting near the anchor
- deterministic target-approach side selection for dogleg, multi-elbow, and bundle routes, driven by explicit `attach_side` or family-level `preferred_anchor_side`
- route simplification for orthogonal attachment paths, so redundant elbows are collapsed after routing decisions and the visible SVG keeps only necessary turns
- complexity-driven per-measure width extension, so symbol-dense measures can widen their band/grid extent instead of forcing every measure to share one fixed horizontal envelope
- per-measure density balancing, so sparse measures reclaim right-side whitespace while dense measures expand farther before the shared outer frame is sized
- deep-stack-triggered staff-height adaptation, so unusually dense measures insert extra inter-measure vertical breathing room without perturbing normal beat-grid coordinates
- deep-stack vertical zoning, so structural `music` / `repeat` families ride higher while annotation-heavy timing layers sink lower in crowded measures instead of collapsing into one median band
- explicit continuation markers at crossed measure boundaries, so long-duration symbols spanning multiple measures remain visually legible after measure rollover
- multi-staff system wrapping for longer scores, so measure runs beyond the first four measures restart in a fresh staff frame with repeated lane guides instead of stretching one uninterrupted band indefinitely
- more family-specific geometry for `turn.spin`, `pin.hold`, and stretched `jump` symbols, including spin echo arcs, hold crossbars, and secondary jump contours
- more official family-native variants for `repeat`, `motif`, and `music`, including distinct opening/closing repeat bars, rise/fall motif markers, cadence signs, and differentiated quarter/eighth/sixteenth rest silhouettes
- stretchable `path` / `space` / `separator` families now render with cap/body/cap composition instead of only scaled outlines, and direction-aware families now emit mirrored SVG variants based on symbol direction semantics
- more official variants now have family-native silhouettes, including `pin.floorplan_exit` and `separator.final`, instead of falling back to generic specialized blocks
- remaining official extras like `bow`, `dynamic`, and `adlib` now render through dedicated family-native SVG geometry instead of generic glyph rectangles
- `path.spiral`, `turn.pivot`, and `jump.small` now expose subclass-specific SVG geometry and transition marks, and `tempo` / `cadence` music signs now use dedicated note/capsule and ribbon typography instead of plain text badges
- official parity work now includes an explicit audit against the OSU LabanWriter manual and updates in [`docs/labanwriter_parity_audit.md`](/C:/Users/moonw/DancenotationMCP/docs/labanwriter_parity_audit.md), and the renderer now consumes `header_role`, `boundary_role`, and `path_shape` metadata from the catalog instead of relying only on symbol-id suffixes
- parity coverage now also includes explicit `space.whitespace`, `jump.spring`, `bow.hook`, `separator.hook`, and `motif.rise_fall` variants with dedicated SVG geometry instead of generic fallbacks
- representative official-family layouts are now locked by a golden SVG fixture in `fixtures/golden_official_family_score.{json,svg}`, and engraving-heavy PDF export is covered by a smoke test against the same score

## Assumptions
- This is an agent runtime, not a desktop notation editor.
- Parsing is deterministic and intentionally conservative in milestone 1.
- Networking/cloud deployment is out of scope.
- Full historical one-to-one LabanWriter parity is still a future milestone.
