# LabanWriter Parity Audit

## Measured baseline (2026-07-27)

Rendering every catalog symbol in isolation and fingerprinting the resulting
markup (position normalised away) gives the numbers below. Re-measure with the
same method rather than counting catalog entries — catalog size and rendering
capability have drifted apart badly, and only the second one is parity.

| Metric | Baseline | Now |
|---|---|---|
| Catalog symbols | 1122 | 906 |
| Distinct glyphs actually produced | 159 | **490** |
| Visual collapse ratio | 7.1 : 1 | **1.85 : 1** |
| Symbols with a wholly unique glyph | — | **436** |
| Symbols whose authored id was lost in the SVG | 8 | 0 |

Adding a catalog entry raises the first row and not the second. Treat the
second row as the parity number.

Almost none of this came from new geometry. It came from reading information
the symbol ids already carried that no consumer looked at — the same defect
found nine times over:

| Family | Symbols | What was discarded |
|---|---|---|
| direction/level | 564 / 408 | every consumer read only `symbol["direction"]`, so `support.step.backward` engraved as "step in place" |
| shape | 24 | the pole segment; spreading == enclosing, rising == sinking |
| contact | 38 | type taken from the *last* id segment, so `contact.grasp.front` resolved to "front" |
| floor-plan | 31 | read a `stage_position` field no entry carries; 31 facings/zones/formations/paths drew one dot and a "?" |
| flexion/extension | 54 | family in neither routing set, so all engraved as `place` direction symbols on the staff |
| sequential | 10 | the id was never read at all |
| body / floor actions | 140 / 84 | the action itself was invisible; only direction and level were drawn |
| effort actions | 14 | the eight basic actions all drew an empty diamond |
| pin / bow / turn / jump | 17 | subtype dropped; pin read a modifier nothing populates while `behavior.cap_shape` sat unread beside it |
| music | 12 | only `rest.*` was handled, so `music.time.3_4` engraved as a quarter rest |
| effort grading | 14 | the `.increasing`/`.decreasing` suffix was never read |
| separator | 6 | read a modifier nothing populates; the catalog stated each mode in `behavior` |
| surface | 3 | routed into the contact renderer, where their own names hit its defaults |

Two catalog-level fixes belong on the same list: 216 combinatorial turn/jump
entries naming signs that exist in no palette were removed, and plié, relevé,
rise and lower had free `allowed_levels` so they engraved at the default middle
— a support's level IS the state of the leg, so those are now pinned and the
rule "one allowed level means that is the level" is applied generally.

### What the remaining clusters are

Every family the audit found discarding information has been fixed;
`KNOWN_OPEN_COLLAPSES` in `tests/test_glyph_uniqueness.py` is empty.

What is left collapsing is `direction` / `support` / `gesture` / `travel`, and
that is the notation working rather than a defect. A direction symbol encodes
direction and level only; heel support, balance, kneel, stamp, slide and pivot
are carried by pre-signs attached beside it, which the catalog holds no
metadata for. Forcing those apart would be inventing signs.

Confirmed by two independent routes: reading the plates of both reference
scores, and Dance Notation Bureau Fundamentals — "the shapes of the symbols
indicate nine different directions in space", with part-of-foot carried by a
separate attached touch sign.

Distinguishing them properly means modelling the attached signs, not drawing
new direction glyphs. That is the next parity frontier, and it needs catalog
metadata that does not exist yet.

Two smaller cases share by design and are asserted to stay identical, so a
later pass cannot "fix" them by inventing signs:

- `flexion`/`extension` across joints — the mark for a 45-degree flexion is the
  same mark whatever joint it applies to; the joint is carried by which limb it
  attaches to.
- `sequential.wave.arm` / `.body` / `.leg` — one shared glyph in the catalog,
  the limb carried by placement.
- `jump.*` across directions — a jump sign takes no compass direction; travel
  direction lives in the support columns.

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
