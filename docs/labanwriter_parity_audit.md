# LabanWriter Parity Audit

## Measured baseline (2026-07-27)

Rendering every catalog symbol in isolation and fingerprinting the resulting
markup (position normalised away) gives the numbers below. Re-measure with the
same method rather than counting catalog entries — catalog size and rendering
capability have drifted apart badly, and only the second one is parity.

| Metric | Value |
|---|---|
| Catalog symbols | 1122 (now 906 — see cleanup below) |
| Distinct glyphs actually produced | 159 |
| Visual collapse ratio | 7.1 symbols per glyph |
| Symbols whose authored id was lost in the SVG | 8 (all of `quality.*`) |

Largest collision clusters: 157 `support`/`travel`/`gesture` entries share one
glyph; `jump.assemble.*` collapses to one glyph per level (direction is never
read by `_render_jump_annotation`); `turn.full.*` likewise, though for turns
that is arguably correct — a turn's direction is rotational, so the fault there
is combinatorial catalog entries that do not correspond to real signs.

Adding a catalog entry raises the first row and not the second. Treat the
second row as the parity number.

This document audits the current symbol and renderer coverage against official LabanWriter categories and update notes.

Sources used:
- OSU LabanWriter page: https://dance.osu.edu/research/dnb/laban-writer
- OSU LabanWriter 4.7 updates: https://dance.osu.edu/research/dnb/laban-writer/updates
- OSU LabanWriter manual PDF: https://dance.osu.edu/sites/dance.osu.edu/files/resources-dnb-laban-writer-manual.pdf

Key official category list from the manual:
- Directions
- Paths
- Turns
- Bows
- Pins
- Body Parts
- Flexion and Extension
- Retention, Cancellation, and Keys
- Carets, Staples, and Small Bows
- Foot Hooks
- Repeats
- Fingers and Toes
- Effort and Shape
- Dynamics
- Ad Lib
- Music and Time Signs
- Motif Symbols
- Laban Movement Analysis Symbols

Key manipulation and behavior features called out by the manual and updates:
- Flipping symbols
- Changing levels within a symbol
- Rotating symbols
- Changing lines
- Altering degrees
- Adding and deleting whitespace
- Oscillating ad libs
- Altering repeats
- Adding surface marks
- Specifying joint areas
- Adding arrowheads
- Creating limbs and surfaces of limbs
- Altering springs and jumps
- Circle and spiral tool behavior
- Counterclockwise curve arrowheads
- Floorplan flipping and floorplan exit pins
- Eighth and sixteenth rests
- Flipped staff separator
- Improved vertical ad libs

Current implementation status in this repo:
- Covered with specialized geometry or semantics:
  - paths, turns, jumps, pins, repeats, music/time, motif, surface, space, separator
  - bows, dynamics, ad lib
  - floorplan exit pin
  - eighth and sixteenth rests
  - flipped separators
  - circle, spiral, curved, and straight path subclasses
  - spin and pivot turns
  - cadence and tempo sign typography
  - whitespace band, spring jump, hook bow, hook separator, rise-fall motif combination
- Covered mainly by validator/catalog semantics, not yet renderer parity:
  - whitespace semantics
  - repeat boundary roles
  - attachment family anchor behavior
  - direction and level transform metadata
- Still partial or missing for stronger parity:
  - richer jump subclasses beyond current compact, stretched, and spring variants
  - carets, staples, and explicit retention/cancellation sign geometry
  - richer keys and LMA sign families
  - joint-area and limb-surface specific rendering
  - more official motif combinations and bow subclasses
  - line-style parity for more manual cases
  - more exact fill and contour parity for mixed-level and degree-altered symbols
  - screenshot or golden-SVG parity fixtures for representative official scores

## Reference score

`La vivandière Pas de six` (Saint-Léon, notated by Ann Hutchinson Guest) is in
the repo root, gitignored for size. Guest co-authored the ICKL standard that
LabanWriter implements, so its notation plates (from p.~73 on) are the
acceptance benchmark for engraving questions — settle conventions against them
rather than by argument.

Verified against the plates so far:
- Level shading: low solid / middle centre dot / high hatched — confirmed.
- Three-line staff with two equal support columns — confirmed.
- Beat ticks sit on the centre line — confirmed.
- Bar lines run staff-line to staff-line with *no* overhang; the marks further
  out are separate dashed segments. We currently draw a 4px overhang and no
  dashed segments. The dashed marks' meaning was not established — do not
  imitate them without reading the score properly first.
- Whether direction symbols fill the support column edge-to-edge could not be
  settled from the plates examined; unresolved.

Fixed since the baseline measurement:
- Middle level now renders as a centre dot rather than an unshaded outline, so
  all three levels are distinguishable (`MiddleLevelDotTest`).
- The staff is three vertical lines bounding the support columns, not a box
  around all ten columns; bar lines cross the staff instead of the full column
  extent (`ThreeLineStaffTest`).

- `quality.*` renders the correct shared effort-stroke glyph but now keeps the
  authored symbol id in the SVG instead of the alias target
  (`QualityAliasIdentityTest`).
- 216 combinatorial `turn.*`/`jump.*` entries removed: turn direction is
  rotational and jump direction lives in the support columns, so ids like
  `turn.full.diagonal_backward_left.high` named signs no LabanWriter palette
  contains. Nothing produced or referenced them
  (`NoCombinatorialTurnJumpEntriesTest`). Catalog 1122 -> 906.
- The `test_total_symbol_count_at_least_1100` threshold was replaced by a
  family-coverage assertion: a count floor rewards exactly the padding that
  produced those 216 entries.

Next parity priorities:
1. Settle the symbol-fills-column question against the reference plates.
2. Shift more renderer branching from symbol-id checks to catalog behavior roles.
4. Add explicit geometry for springs, carets, staples, and retention/cancellation families.
5. Expand official motif and LMA variants beyond current placeholders.
6. Add golden SVG fixtures for representative LabanWriter-style examples.
