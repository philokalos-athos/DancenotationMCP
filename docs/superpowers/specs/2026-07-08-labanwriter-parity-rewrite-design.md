# LabanWriter-Parity Rendering Rewrite

Status: approved by user (verbal, iterative Q&A); user has directed continuous
autonomous execution without further approval checkpoints.

## Problem

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
