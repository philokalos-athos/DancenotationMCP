# LabanWriter-Parity Rendering Rewrite

Status: approved by user (verbal, iterative Q&A); user has directed continuous
autonomous execution without further approval checkpoints.

## STATUS: M1-M4 core work complete (511 tests passing)

- **M1** — confirmed `laban_renderer.py`/`laban_layout.py` (not the debug
  `svg_renderer.py` tool) is the real target; fixed 2 real bugs against the
  manual (level-fill high/middle was backwards; column guides were
  incorrectly printing).
- **M2** — swept every catalog `staff_column` value against the renderer's
  routing tables and fixed 7 orphaned families (`bow`, `dynamic`, `adlib`,
  `motif`, `foothook`, `digit`, `space`) that were silently misrendering as
  generic direction pentagons. Added a permanent guard test
  (`test_every_staff_column_is_routed_or_explicitly_allowlisted`) so a future
  catalog addition can't repeat this bug class undetected.
- **M3** — discovered `floor_plan_renderer.py` already existed as a working
  implementation but was completely unwired (no tool, no `generate_score`
  integration, no tests). Wired it up, added a center mark, added tests.
- **M4** — built MusicXML/MIDI import (`music_import.py`) and a real
  music21 → LilyPond → SVG engraving pipeline (`music_engraver.py`) from
  scratch (genuine greenfield — no prior partial implementation existed).
  Found and fixed a real LilyPond multi-page-output bug along the way
  (music21's auto-generated title header causes numbered page splitting).
  Wired into `generate_score` via an optional `music_source` input, plus a
  standalone `render_music` tool. Composed as a paired `{name}-music.svg`
  file rather than a pixel-merged, per-measure-aligned single staff — true
  measure-for-measure visual merge with the dance staff is flagged as a
  follow-up, not attempted here.

**All 14 tracked tasks now complete (517 tests passing).** Additional work
beyond the original four milestones:

- **M2.1** — found and fixed a real direction-naming inconsistency: the
  catalog's `allowed_directions` used `diagonal_forward_left` etc. (1360
  declarations) while `schemas/notation-ir.schema.json`'s enum and
  `ir/models.py`'s `DIRECTIONS` both used the short `forward_left` form.
  Confirmed `validate_schema()` is a hand-rolled check (not real jsonschema
  enforcement) so this wasn't actively breaking anything today, but was
  wrong documentation that would break the instant someone wired up real
  schema validation. Fixed both to match the catalog (the actually-enforced
  source of truth) + added a guard test.
- **M3.2** — added a 3-performer floor-plan golden fixture (converging
  formation, mixed path styles, diagonal facings) since prior coverage only
  exercised a single dancer.

**Post-completion addition:** implemented floor-plan pin-sex shapes per the
manual's explicit convention ("female pin (white) is the default... male
pin (black)... neuter pin (tack)"). Added an optional `sex` field to
`extensions.floor_plan` entries (schema + `add_floor_plan` tool +
`ir/models.py`'s new `PIN_SEXES`), rendered as a hollow white circle
(female/default), solid filled circle (male), or triangular tack shape
(neuter) — per-performer color is retained on top of the shape as a modern
multi-dancer disambiguation aid the monochrome original didn't need.
Visually verified all three shapes render distinctly; golden fixture
regenerated (diffed to confirm the change was isolated).

**Post-completion addition 2:** forced LilyPond's engraved music onto a
single continuous horizontal line instead of its default multi-system page
wrapping, matching the reference score's melody-line style (a continuous
strip alongside the dance staff, not paginated sheet music). Implemented by
appending a `\paper { ragged-right }` + `\layout { \override
NonMusicalPaperColumn.line-break-permission = ##f }` override to the
generated `.ly` source before invoking `lilypond`. Verified: a 6-measure
piece renders as one unbroken `<svg>` (152mm × 12.92mm — height stays
constant regardless of length). Added a regression test.

**Post-completion addition 3:** implemented floor-plan wing columns and
caption squares, per the manual ("Wing columns can also be added to the
floorplan to allow you to place pins outside the floorplan(s)"; "Squares at
the bottom of the floor plan can be added for typing in captions"). Added
`wing_left`/`wing_right` zones (schema + `ir/models.py`'s `STAGE_ZONES`) and
an optional `caption` string field on floor-plan entries. The stage canvas
grew from 300px to 372px wide (two 36px wing strips, dashed border,
rotated "WING" label) with all main-grid coordinates shifting by the wing
offset; captions render as small colored text below each pin. Updated the
golden fixture (diffed — change was exactly the coordinate shift + new wing
elements, nothing else) and added 5 new tests. Visually verified via a
rendered PNG showing a dancer starting in the wing, traveling onstage with
a captioned path, alongside a second captioned dancer.

**Post-completion addition 4 (the big one): true per-measure staff
merging.** Built `paired_score_renderer.py`. The reference score runs its
melody line *vertically*, rotated 90 degrees, so it lines up bottom-to-top
exactly like the dance staff, measure for measure. LilyPond has no native
vertical-staff mode, so instead of rotating one continuous strip (which
can't line up per-measure since dance measure heights vary with time
signature/stacking pressure while LilyPond's own measure widths don't match
that), this renders **each measure independently**, then applies a derived
affine `matrix()` transform that simultaneously rotates 90 degrees and
scales/positions each one to exactly span its corresponding dance measure's
pixel height (from `compute_laban_layout`'s `measure_positions`).
Implemented, tested, and **visually verified via a rendered PNG**: a
4-measure test score shows each measure's engraved notes precisely spanning
its own measure box, bottom (measure 1) to top (measure 4), correctly
aligned to the beat. Wired into `generate_score` (adds `paired_svg_path`/
`paired_pdf_path` alongside the existing separate `music_svg_path`, best-
effort — falls back silently if per-measure engraving fails) and a new
`render_paired_score` tool. 5 new tests including a partial-coverage case
(music shorter than the dance score). Known trade-off: one `lilypond`
subprocess call per measure (~0.3-1s each) — documented in the module
docstring as slower than the single-invocation path for long pieces, by
design given the per-measure alignment requirement.

**Post-completion addition 5: dispatch-completeness sweep (M2.1
continuation).** M2's earlier sweep checked *routing* (does a family reach
the annotation area at all) but not *dispatch* (does `_render_annotation`
actually know how to draw it once there) — found the same bug class in 4
more places, all now fixed with regression tests (536 tests passing):
- `path.*` (4 symbols) — routed correctly, no dispatch branch, fell to
  generic text. Added `_render_path_annotation` (straight/curved/spiral/
  circle shapes, adapted from svg_renderer.py's existing correct logic).
- bare `surface.*` (3 symbols: contact/brush/glide) — a second, un-dispatched
  symbol_id prefix distinct from the already-handled `contact` family.
  Now shares `_render_contact_annotation`.
- non-header `music.rest.*` (rest symbols without `modifiers.measure_header`)
  — no dispatch branch. Added `_render_music_rest_annotation`.
- `floor.zone.*` (31 symbols, `floor_plan.json`) — a genuine catalog naming
  collision: these share the `floor` symbol_id prefix with the unrelated
  `floor.roll` body-action family (84 symbols), so the dispatch check
  `family == "floor_plan"` never matched (family is "floor" for both).
  Fixed by dispatching on `staff_column == "floor_plan"` instead, the only
  reliable distinguishing signal.

Also noted (not fixed — lower confidence without stronger source
grounding): `jump` (113 symbols, `requires_direction`/`requires_level`
nearly universal) and `turn` (112 symbols, `requires_level` universal) both
declare inputs their renderers don't fully use — `_render_jump_annotation`
draws one bow shape regardless of level, `_render_turn_annotation` ignores
level entirely. Real Labanotation likely does vary these by level/direction,
but fixing it well needs firmer textual grounding than inference; flagged
as a follow-up rather than guessed.

**Post-completion addition 6: broken symbol_id construction across the
codebase (found by grepping every hardcoded dot-notation string against
the real catalog).** More severe than the dispatch gaps above — these
produced symbols that fail validation outright with "Unknown symbol id",
not just a cosmetic misrender:
- `add_retention` MCP tool built `symbol_id="timing.retention.{type}"`,
  which doesn't exist anywhere in the catalog (real family is
  `retention.{type}.{body_category}`, e.g. `retention.hold.arm`). Every
  score built with this tool failed validation. Fixed with a body-part →
  category mapping (arm/leg/torso/head/hand/shoulder/full_body).
- The retention *renderer* had a second, independent bug: it read
  `symbol_id.split(".")[-1]` (the body category, e.g. "arm") instead of
  the type (index 1) — so even correctly-authored `retention.hold.arm`
  symbols rendered as the same generic dot regardless of hold/release/
  cancel. Fixed; the three types are now visually distinct (tie-arc,
  X-mark, diagonal slash).
- `add_effort_graph` built a fake `"quality.effort"` symbol with
  `modifiers.weight/time/space/flow` — but `laban_renderer.py`'s effort
  overlay reads a completely separate top-level `ir["effort_graphs"]` list
  with those same field names *un-nested*. `effort_graphs` wasn't even in
  the schema despite being read by the renderer. Fixed: the tool now
  appends to `ir["effort_graphs"]` correctly, and the schema documents it.
- `create_empty_score`'s optional `tempo` argument built a fake
  `"timing.tempo"` symbol with `modifiers.bpm` — real family is
  `music.tempo.mark` (body_part `"torso"`, not `"whole_body"`), read via
  `modifiers.tempo` (not `bpm`), and needs `modifiers.measure_header=True`
  to route to the header renderer instead of the plain music-rest one.
  Fixed.
- **The most significant one**: `phrase_parser.py`'s `ACTION_PATTERNS`
  table — the core natural-language-prompt pipeline — maps ordinary ballet
  vocabulary ("plie", "releve", "stamp", "on toes", "on heels") to bare
  hints like `"support.plie"`. Those families are 100%
  `requires_direction: true` with **no** standalone entry (unlike
  `support.step`/`support.lower`, which do have one) — so parsing any of
  these five everyday words produced an IR that failed validation with
  "Unknown symbol id". Fixed generally in `phrase_to_ir.py`
  (`_resolve_symbol_id`): if the bare hint isn't in the catalog but
  `f"{hint}.{direction}"` is, expand to that — covering this and any future
  family with the same shape, not just these five words. 25 new tests
  across this batch (updating several that had encoded the old broken
  behavior as if it were correct), 547 tests passing.

**Post-completion addition 7: found the same "Unknown symbol id" bug class
already present in a real example file.** `examples/collapse_of_symmetry_full.ir.json`
had 24 symbol instances using exactly this pattern (`timing.tempo` — the
identical bug already fixed in `create_empty_score`, confirming this file
predates that fix — plus `turn.right`, `jump.basic`, `sequential.successive`,
none of which exist in the catalog either). Also uncovered a second, coupled
issue: the correct replacements (`turn.pivot`, `jump.small`) don't allow
`body_part: "whole_body"` either, so fixing the symbol_id alone wasn't
enough — `body_part` needed correcting too (`torso` / `left_leg`). Fixed
all 24 instances; the file now has zero "Unknown symbol id" issues (547
tests still passing — this file isn't part of the test suite, so this was
a pure sanity check, not a required fix, but a real one to leave broken).
Left as a separate, lower-priority, pre-existing finding: ~18 unrelated
`body_part` mismatches in the same file (e.g. `effort.weight.strong` with
`body_part: "whole_body"`) that predate and are unrelated to this specific
bug pattern — not touched, to stay scoped to the one bug class this pass
was hunting.

**Deferred (documented, not silently dropped, no remaining open tasks):**
deeper per-symbol geometry audit for the ~800 remaining catalog symbols
beyond the family-routing/dispatch sweep; pixel-exact transcription of the
actual La Vivandière scan pages (scan resolution makes reliable readback
risky — an honest representative fixture beats mis-transcribed "ground
truth").

## CORRECTION (found during M1 implementation)

`src/dancenotation_mcp/rendering/svg_renderer.py` + `layout.py` (`render_svg`)
is **not** the LabanWriter-parity target — it is an explicitly-documented
debug/diagnostic tool ("render notation IR as a debug/preview SVG with all 28
lanes visible", per `server.py`'s `TOOL_SCHEMAS["render_svg"]`). The actual
publication-quality renderer, already wired as `generate_score`'s default and
the `render_laban` MCP tool, is `laban_renderer.py` + `laban_layout.py`
(`render_laban_svg` / `compute_laban_layout`). It already implements an
authentic 11-column ICKL staff with center line, mirrored support/body/arm/
arm_gesture/path columns, bottom-to-top time flow, ICKL-standard direction
pentagon/hexagon shapes, and per-family annotation placement — with a
54-test passing suite (`tests/test_laban_renderer.py`) and its own golden
fixture (`fixtures/golden_laban_parity_score.svg/.json`).

An initial pass mistakenly rewrote the debug tool's mirrored-column model
instead of touching `laban_renderer.py`; that work was reverted in full
(diffed against original to confirm a clean revert, all 489 tests green)
since it provided no value toward the actual goal and degraded the debug
tool's purpose (showing every lane independently).

**All milestones below now target `laban_renderer.py`/`laban_layout.py`.**
Given how much of the "build the staff" work already exists, M1 collapsed
into an audit that found and fixed one real bug: the manual states "High
level stripe space can be changed... Make a high level symbol, then separate
stripes" (p.70) — High is the striped level, not Middle, which the code had
backwards. Fixed in `laban_renderer.py`'s `LEVEL_FILLS` and
`tikz_renderer.py`'s `_LEVEL_TIKZ`; tests and the golden fixture were
regenerated (diffed to confirm the change was isolated to fill patterns).

## Problem (original framing — see correction above for the actual target file)

The current renderer (`src/dancenotation_mcp/rendering/svg_renderer.py`,
`layout.py`) does not produce real Labanotation. It renders a flowchart-style
diagram: independent per-body-part "lanes" with rounded boxes, unicode arrow
glyphs (▲▼◀▶) and text labels for direction/level, CSS-colored fills instead
of real shading patterns, and auto-routed elbow/curve connector lines between
symbols like a graph-diagram tool. Several "specialized" symbol renderers
(spiral paths, spring coils) are invented decoration, not real Laban glyphs.

Goal: rebuild the rendering + geometry stack so output is visually and
structurally consistent with **LabanWriter** (the canonical software,
authoritative per user direction) and matches the proportions/conventions of
an academically published score (reference: Ann Hutchinson Guest,
*La Vivandière Pas de Six*, Saint-Léon, 1993 facsimile-quality edition).

## Ground truth sources

1. **LabanWriter 4.4 manual** (OSU Dance Notation Bureau) — authoritative for
   software conventions: base units, column model, level-fill mechanics,
   symbol stretch/width rules, floor plan defaults. Extracted facts below.
2. **La Vivandière Pas de Six** reference PDF (188-page scanned facsimile) —
   authoritative for whole-page academic layout: dual music+dance staff,
   measure numbers in margin, floor-plan diagrams on facing pages, front
   matter conventions. Used as golden-fixture source (pages 62 "First Pas de
   Cinq", 82-83 "Adagio" identified as good candidates — dense multi-dancer
   staff + floor plan pair).
3. Where neither source gives an exact shape/rule (e.g. some family-specific
   glyph geometry), fall back to standard Labanotation theory (Hutchinson
   Guest textbook conventions, which are effectively universal across the
   field) and cross-check visually against the reference scan.

### Extracted facts (LabanWriter manual)

- **Base unit**: 7 pixels per "square"; squares-per-beat is configurable
  (quick-start example uses 4 squares/beat). All our proportions should be
  expressed as multiples of a `SQUARE_PX` constant, not ad hoc pixel values.
- **Staff/column model**: "Columns per staff must be an even number... if you
  use six columns per staff, you will get a staff with three columns on each
  side of the center line." The staff is symmetric around a **center line**;
  columns are invisible placement guides ("dots representing columns... do
  not print") — never drawn as boxes/lanes. Default "Exterior Columns" = 9 on
  each side (extra guide columns beyond the core body-part columns, mainly
  used for gesture/relationship extensions).
- **Core column order** (standard Labanotation theory, confirmed by the
  reference score's visual layout): outward from the center line on each
  side — support, leg gesture, body, arm gesture, head. Whole-body/traveling
  and turn signs sit in their own column set beyond that.
- **Direction symbol shape/width**: forward/backward directions render as a
  *narrow* elongated-hexagon pointer; side (left/right) directions render
  *wide*; diagonals render at an intermediate width. Symbols default to one
  column wide but are stretchable to half a column or multiple columns.
  Extension is quantized "a square at a time" unless Option/pixel-fine mode
  is used.
- **Level shading** (direction & turn symbols): Low = solid black fill;
  Middle = unshaded/blank (outline only); High = striped fill with
  adjustable stripe spacing. A symbol can be split into two or three level
  bands (fill from top / fill from bottom / remaining band) — i.e. a single
  symbol can show a level transition across its own duration.
- **Duration → height**: symbol vertical length is literally the number of
  squares/beats it spans on the staff timeline; there is no separate
  "collision lane offset" concept — simultaneous symbols in the same column
  simply share that column's timeline.
- **Floor plans**: default depth 16 squares × width 24 squares grid,
  optional horizontal/vertical divisions, caption squares (bottom, for
  typed captions), wing columns (outside the grid, for offstage pins),
  center mark, and dancer pins (female = white/open pin head, male = black
  pin head, neuter = tack shape) with rotation for facing direction.
- **Page**: US Letter default (8.5×11in), half-inch margins; symbols/staff
  must stay inside margins for reliable printing.

## Architecture overview

Replace the "lane diagram" layout model with a genuine **mirrored staff**
model:

```
                    center line
                        │
  [head] [arm] [body] [leg] [support] │ [support] [leg] [body] [arm] [head]
   (left side, mirrored)              │  (right side)
```

- `layout.py` computes column x-positions as offsets from a single
  `center_x`, not as a flat list of independent "lanes". Column width and
  order come from the extracted core-column-order fact above, mirrored
  left/right per dancer's laterality (a `body_part` of `left_leg` places in
  the left leg-gesture column, `right_leg` in the right).
- Duration → height uses `SQUARE_PX * squares_per_beat * beats`, replacing
  the current ad hoc `BEAT_HEIGHT` pixel constant with a value derived from
  the base unit so proportions match LabanWriter's default scaling.
- Symbol geometry in the catalog gains authentic shape parameters (pointer
  width class: narrow/medium/wide; level-fill capability) instead of
  `glyph` unicode characters and `width`/`height` box dimensions tuned for
  a diagram box.
- The staff itself draws exactly: two outer bounding lines, one center
  line, horizontal measure lines, and (optional) beat tick marks — no
  visible column guides, no rounded symbol-container boxes, no auto-routed
  connector lines. Attachments (pins, surface marks, etc.) attach directly
  to their host symbol's edge per LabanWriter's own attachment conventions,
  not via a flowchart routing engine.
- Text is eliminated from the notation staff itself (body-part labels,
  level labels, unicode direction glyphs) — Labanotation is non-verbal by
  design. Any human-readable labels (measure numbers, tempo text) appear
  only in the margin/header, matching the reference score.

## Milestones

Executed in dependency order; each ships a working end-to-end
`generate_score` output, later milestones increase fidelity.

### M1 — Staff model + direction-symbol rebuild (foundation)

- Rewrite `layout.py`'s column model: center-line-relative column
  positions, core column order, mirrored left/right placement.
- Introduce `SQUARE_PX` base unit and derive all spacing/duration scaling
  from it and a configurable squares-per-beat.
- Rewrite direction-symbol rendering: real elongated-hexagon pointer
  shapes with narrow/medium/wide classes per direction, plus solid /
  blank / striped level-fill rendering (including split-level fills).
- Redraw the staff itself: outer lines, center line, measure lines, tick
  marks — remove lane boxes, text labels, and connector-line routing for
  the symbols this milestone covers.
- Golden fixture: re-encode a slice of *La Vivandière* p.62 (First Pas de
  Cinq) covering plain support/gesture direction symbols across several
  measures; compare rendered SVG proportions against the scan.

### M2 — Full symbol catalog re-audit (871 symbols, 6 JSON files)

- Re-audit every entry's `geometry`/`behavior` metadata against LabanWriter
  conventions (pointer width class, level-fill applicability, attachment
  anchoring). The user asked for a full taxonomy re-audit, not just a
  geometry swap: `symbol_id` values and semantic constraint fields
  (`allowed_body_parts`, etc.) may be renamed/restructured where the audit
  finds the existing taxonomy itself wrong, not only where the drawing is
  wrong. Renames are tracked in a migration note so the parser/validator/
  planner call sites can be updated in the same pass.
- Replace all "specialized renderer" invented glyphs (spiral, circle,
  spring-coil, etc.) with authentic path/turn/pin/repeat/retention shapes
  per Labanotation convention, cross-checked against the reference scan.
- Catalog audit tests (`tests/test_catalog_constraints.py`) extended to
  assert every entry has the new required geometry fields.

### M3 — Floor-plan diagrams

- New floor-plan renderer: bird's-eye rectangle, default 16×24 squares,
  optional grid/divisions/captions/wing columns/center mark, numbered
  dancer pins (male/female/neuter head shapes) with path arrows between
  positions — replacing the current abstract "zone glyph" entries in
  `floor_plan.json`.
- Golden fixture: reference p.63/83 floor-plan diagrams paired with their
  facing staff pages.

### M4 — MusicXML/MIDI import + local music engraving

- New import path: MusicXML or MIDI file → `music21` parses pitches/
  durations/ties/dynamics → converted to a LilyPond (`.ly`) source aligned
  to the same measure/beat timeline as the dance IR → local `lilypond`
  binary (already installed, confirmed v2.24.4) renders engraved SVG.
- Compose the engraved music SVG alongside the Labanotation staff,
  matching the reference's side-by-side placement and vertical alignment
  per measure.
- `generate_score` gains an optional `music_source` input (MusicXML/MIDI
  path); when absent, output is dance-staff-only (no placeholder gutter).

## Non-goals (explicitly out of scope for this rewrite)

- Reproducing front-matter/photo pages, foreword, or any prose content
  from the reference book — only its notation-page and floor-plan-page
  conventions are being matched.
- Transcribing the *La Vivandière* ballet in full — only small excerpts
  are encoded as golden fixtures for visual-parity testing.

## Risks / open items

- `music21` → LilyPond conversion fidelity for complex meters/ties will
  need spot-checking; start with the reference's melody-line style
  (single voice, simple meter) which is the actual target, not full
  orchestral engraving.
- Exact glyph geometry for less common symbol families (effort/shape,
  LMA symbols, retention signs) isn't in the manual's prose; these will be
  derived from standard Labanotation theory and validated visually against
  the reference scan page-by-page during M2's audit rather than guessed.
- This is a large rewrite touching almost every file in `rendering/` and
  every catalog JSON file; existing golden fixtures
  (`fixtures/golden_official_family_score.svg`,
  `fixtures/golden_laban_parity_score.svg`) will need regenerating once M1
  lands, and tests referencing current lane/box/glyph output will need
  updating to assert against the new shape model instead.
