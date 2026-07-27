# LabanWriter Parity Audit

## Measured baseline (2026-07-27)

Rendering every catalog symbol in isolation and fingerprinting the resulting
markup (position normalised away) gives the numbers below. Re-measure with the
same method rather than counting catalog entries — catalog size and rendering
capability have drifted apart badly, and only the second one is parity.

| Metric | Baseline | Now |
|---|---|---|
| Catalog symbols | 1122 | 906 |
| Distinct glyphs actually produced | 159 | **207** |
| Visual collapse ratio | 7.1 : 1 | **4.4 : 1** |
| Symbols whose authored id was lost in the SVG | 8 | 0 |

Adding a catalog entry raises the first row and not the second. Treat the
second row as the parity number.

What closed the gap so far was not new geometry but reading information the
symbol ids already carried and no consumer looked at:

- **direction and level** — 564 ids name a direction, 408 a level, and every
  consumer read only `symbol["direction"]`. `support.step.backward` engraved as
  "step in place", silently. Largest cluster 157 → 56.
- **contact type and surface** — `contact_type` came from the *last* dotted
  segment, so `contact.grasp.front` resolved to "front" and lost the grasp
  staple. 38 symbols on one glyph → 38 distinct.
- **floor-plan sub-family** — `_render_stage_marker` read a `stage_position`
  field none of these entries carries, so 31 facings, zones, formations and
  paths all drew one dot and a literal "?".

### Reading the remaining clusters

The clusters left are not all defects, and the next round has to separate two
cases before touching anything:

- **Renderer drops information** — the three above. Fix these.
- **The notation genuinely shares a glyph** — `support.balance.backward`,
  `support.heel.backward` and `gesture.leg.backward` all draw the same
  direction symbol because in Labanotation the direction symbol encodes
  direction and level only; heel support, balance and the rest are carried by
  pre-signs and modifiers attached to it. Forcing these apart would be
  inventing signs, not reaching parity.

Current largest clusters, unclassified: 56 (`extension`/`flexion` degrees
sharing a direction glyph), 39 (`body.bend`/`contract`/`release`/`stretch`),
and a family of 21-symbol clusters, one per direction, of the pre-sign kind
described above.

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

## Where an engraving question gets settled

Authority depends on the kind of question, and the split is not the obvious one:

| Question | Authority |
|---|---|
| What a sign means; how a movement is analysed | ICKL Proceedings + Technical Reports |
| What a sign looks like | LabanWriter / KineScribe palettes |
| Column widths, spacing, alignment, what fills what | **Published scores only** |

ICKL is the standards body — its aim includes "acting as a deciding body with
regard to the orthography and principles of the system" — but it does not
standardise engraving. Full-text search across ~1500 pages of its proceedings
finds zero occurrences of `column width`, `staff width`, `line thickness` or
`symbol size`, and one of `engrav*`. See `references/ickl/README.md` for the
measurement and `references/fetch_ickl.py` to obtain the documents.

Nor does any tool automate layout. LabanWriter and its touch-screen successor
KineScribe are both manual drawing programs: the notator positions symbols by
hand against guides that, per the LabanWriter manual, do not print. There is no
reference implementation of automatic Labanotation layout to compare against —
this project has to encode as explicit rules what is currently craft knowledge.

That makes the published score the primary layout authority, not a fallback.

## Reference score

`La vivandière Pas de six` (Saint-Léon, notated by Ann Hutchinson Guest) is in
the repo root, gitignored for size. Guest chaired ICKL and sits on its Research
Panel as honorary member, so its notation plates (from p.~73 on) are the
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
- Direction symbols fill the support column and abut the centre line —
  **settled**, see below.

### Settled: symbols abut the centre line

Eyeballing the plates could not resolve this, so it was measured. Staff lines
were located by column-wise dark-pixel analysis (they are the only near-full
height vertical strokes), symbols were isolated as connected components, and
each component's horizontal extent compared to its column bounds. 57 plates,
397 direction-sized components:

| Measurement | Result |
|---|---|
| Symbol width as % of column | median **100%** |
| Components spanning >95% of the column | 72% |
| Components touching the **centre** line (<2% gap) | **88%** |
| Components touching the outer line (<2% gap) | 79% |
| Gap to centre line | median 0%, p90 **14.7%** |
| Gap to outer line | median 0%, p90 **41.2%** |

The asymmetry in the last two rows is the actual rule: when a symbol is
narrower than its column it keeps contact with the centre line and opens the
gap on the *outer* side. That follows from the semantics — a support symbol
touching the centre line is what marks it as a support, so the contact carries
meaning and is not a spacing choice.

The renderer had this backwards (3px off the centre, 1px off the outer) with a
4px `CENTER_GAP` holding symbols away from a line they must touch. Fixed:
`CENTER_GAP` is 0 and staff symbols carry no horizontal padding
(`SupportSymbolTouchesCentreLineTest`).

Note on method: a naive row-scan cannot settle this, because a bar line
crossing the staff produces the same edge-to-edge ink signature as a symbol
filling the column. Connected components are required. Plates where staff
detection returned unequal columns were discarded rather than averaged in.

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

### Settled: the starting-position area is drawn in solid lines

The plates of `La vivandière` all open mid-piece, so this could not be settled
there. The OPENING MARCH plate of `Soirée musicale` (p.58) shows it directly,
on four staves at once:

- The three staff lines **run straight down** past the opening double bar into
  the starting-position area — it is the staff continuing, not a separate box.
- A **solid** rule closes the area at the bottom.
- The starting direction symbols sit inside it, in their normal columns.
- Below that: the dancer identifier (`N`, `B2`, `B3`, `MN,MC,MT`) and a pin.
- **Nothing in the area is dashed.**

This renderer drew a dashed rectangle with a dashed centre line through it,
which reads as a UI affordance rather than notation. Replaced with the three
staff lines plus a solid closing rule (`StartingPositionAreaTest`).

Note that the second reference score answered in one plate what 188 pages of
the first could not, because it happens to open with a starting position. Where
a convention cannot be found, the gap may be in the sample rather than in the
notation.

Next parity priorities:
1. Bar lines: the plates show them running staff-line to staff-line with no
   overhang, plus separate dashed segments further out whose meaning was not
   established. We draw a 4px overhang and no dashed segments.
2. Shift more renderer branching from symbol-id checks to catalog behavior roles.
3. Add explicit geometry for springs, carets, staples, and retention/cancellation families.
4. Expand official motif and LMA variants beyond current placeholders.
5. Add golden SVG fixtures for representative LabanWriter-style examples.
