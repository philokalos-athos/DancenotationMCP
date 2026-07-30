# LabanWriter Parity Audit

## Measured baseline (2026-07-27)

Rendering every catalog symbol in isolation and fingerprinting the resulting
markup (position normalised away) gives the numbers below. Re-measure with the
same method rather than counting catalog entries — catalog size and rendering
capability have drifted apart badly, and only the second one is parity.

| Metric | Baseline | Now |
|---|---|---|
| Catalog symbols | 1122 | 906 |
| Distinct glyphs actually produced | 159 | **526** |
| Visual collapse ratio | 7.1 : 1 | **1.72 : 1** |
| Symbols with a wholly unique glyph | — | **472** |
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

### Whole-score parity, measured separately

Per-symbol work cannot see how a finished score reads. Rendering the largest
example beside the plates found two defects the glyph probe is blind to:

| | Plates | Was | Now |
|---|---|---|---|
| Page proportion | 1 : 1.37 | 1 : 20.6 | 1 : 1.08 |
| System flow | side by side | stacked into one column | side by side |
| Captions across the staff | none | 23 of 91 | 0 |

Page proportion measured on La vivandière (2698x3668 and 2727x3775); p91 and
p97 each carry two three-line staves side by side. Soirée musicale has three
and four across, but those are four dancers on their own staves — a different
thing from one dance wrapping, and not what settles this.

What was NOT wrong: measure height, about 186px against the plates' ~190 at
150dpi. The whole error was in the direction systems flow.

Caption orientation is settled and was re-checked, because it looks wrong at
first sight. On La vivandière every piece of text is horizontal — measure
numbers, the dancer letters F, A, G1,2 under each staff, the floor-plan
number under each bracket. That made our 90°-rotated captions look like a
defect. They are not: the rule is length, not text as such. Soirée musicale
p58 runs a full sentence up the left margin, rotated —
"(LET HER BALANCE HERSELF AS MUCH AS POSSIBLE - SUPPORT WHERE NEEDED)" —
while its measure numbers and its C and MC dancer labels stay horizontal on
the same page. Short identifiers horizontal, prose vertical.

We already do both, which was checked rather than assumed: of the 128 text
elements in the example score, the 89 carrying `class="laban-caption"` are
prose from `modifiers.label` and all rotate, and the 39 structural ones —
measure numbers, title, system labels — are all horizontal. There is no gap
here. Those 39 carry no class, so
`test_no_caption_is_written_across_a_staff` does not see them — but most are
glyph text drawn at a symbol's own centre, where they belong, and the measure
numbers are placed at a fixed margin x by the layout rather than tracking a
symbol. Nothing shows them landing on a staff; the gap is in what the test
can observe, not in what is drawn.

The plates offer no example of a *short prose* annotation, so there is
nothing to check our "jeté" and "hold" against. Whether a four-letter caption
should rotate like a sentence or sit horizontal like an identifier is
unsettled, and unimportant until a plate shows one.

Since settled: captions are assigned lanes in the margin and no longer stack
on each other. Still open: the trailing system of a score can come out nearly
empty.

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

Distinguishing them means modelling the attached signs, not drawing new
direction glyphs. Partly done: `behavior.pre_sign` now names the sign a support
carries and the renderer attaches it, for the four whose sign is settled —
heel, toe, stamp and slide.

Kneel, pivot, balance, hop and lunge are deliberately left declaring nothing.
They are not foot pre-signs: kneeling puts the knee down as the weight-bearing
part, a pivot is a turn sign, and the rest are compound positions with no
dedicated glyph. A test asserts they stay unsigned, so a later pass cannot give
them a guessed one. Settling those needs a source for the forms that neither
the plates nor the ICKL documents provide — Knust's *Handbook of Kinetography
Laban* is the likely one.

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

### A movement that outruns its system

Open. A symbol's length is its duration, so one anchored near the top of a
system can extend past the end of it. The renderer drew it anyway, off the
page — a four-beat step on the last beat of an eight-measure system started at
y -69 against a canvas beginning at 0.

The plates do not settle what such a sign should look like, because a notator
does not write one. On La vivandière p84 the staff closes with a horizontal
cap and the last measure's signs finish inside it; the movement is broken at
the bar instead. The score-level condition is already reported — the validator
raises `TIMING_MEASURE_OVERFLOW` carrying the `carry_duration` that would have
to resume in the following measure.

What is unsettled is whether that remainder should be re-engraved at the foot
of the next system, and if so with what mark joining the two halves. Until
that is answered from a source, the sign is clamped to the top of its system:
shorter than its duration, which the Third Principle would forbid, but the
score is already flagged as malformed at that point, and drawing off the page
is wrong under every answer to the question.

The measurement to settle it: find a plate where a held support crosses a
system break. None of La vivandière pp. 63-150 has been searched for one yet.

### Retention

Settled against Knust vol 2 Fig. 78-79 (the plate is PDF page 12, printed
page 5). The vocabulary is:

| sign | shape | meaning |
|------|-------|---------|
| 78a | empty circle | retention in the body; in a support column, retaining the weight |
| 78b | empty diamond | retention in space — the same spatial direction is kept while the body turns under it |
| 78c | diamond with a dot | retention at a spot |
| 78d | 78c over an × on a bow | retention of a relationship |
| 79a | a narrow Λ | the decrease sign, Kinetography's general cancellation sign, derived from the decrescendo |
| 79c, 79c′ | wave, or small curl | the broken retention sign, cancelling a relationship |

Three things follow, and all three are now done: the column carries half the
meaning so the sign is placed by body part rather than in the margin; the
round sign is drawn open, not as a filled disc under an invented tie arc; and
78b and 78c existed nowhere in the catalog and now do.

`release` and `cancel` name one operation — "Release X Position" and
"Cancel X Retention" — and the notation has one sign for it, so both engrave
the decrease sign. They stay as separate ids only because `add_retention`
already exposes both in its public type enum. Note that Knust's usual way of
ending a retention is not a sign at all: vol 1 p67, "A movement symbol in one
support column cancels previous retention signs in both support columns."
Writing the next movement is the cancellation.

A retention sign written *inside* a direction symbol is a separate
construction, and it is implemented. Vol 1 p45: "For undeviating movements
retention signs are written within a direction sign ... A retention in space
within a direction sign (122a) indicates an undeviating curve or an
undeviating step. A 'retention at a spot' sign written within a direction
sign (122b) indicates an undeviating movement towards an aim."

One detail there had to be settled by looking at the plate. Fig. 122b is
drawn **filled**, where the standalone spot hold (78c) is an outlined diamond
with a separate dot in it. That matters beyond fidelity: the mark sits at the
symbol's centre and so does the middle-level dot, so an outlined diamond with
a dot inside and an outlined diamond over the level dot render as the same
picture. The first implementation did exactly that, and a string comparison
of the two passed — the markup differed by one `<circle>` — while the two
pictures were identical. Filling 122b restores the distinction the plate
prints and lets the level dot show through 122a. Whether the plate means
"solid" or "a dot grown large enough to fill" cannot be told from the scan.

Still open:

- 78d, retention of a relationship, and the broken retention signs 79c/79c′.

Since settled: **slide**. p45, immediately after the undeviating passage,
"The round retention sign is only written within a support sign in order to
indicate a slide." The nine `support.slide_support.*` entries carried
`behavior.pre_sign: foot.action.slide`, putting a mark beside the support
sign instead of the round sign inside it. That came in when the foot
pre-signs were modelled — slide was grouped with heel and toe, and it is a
different kind of statement: those say which part of the foot takes the
weight, a slide says the weight stays on the foot while it travels.

### Staff proportions

Settled, after getting it wrong once. **The earlier figure in this section —
"the staff is 2.3 times too wide for its beat" — was measured against the
wrong object and is withdrawn.**

The error: the pixel detector finds a *three-line staff box*, the support
columns and their outer rules. On our side the number compared against it was
`staff_left..staff_right` = 184, which is the span of all ten columns
including path, arm-gesture, arm and body. Our three-line box is 154..206 =
52. Box against ten-column span is not a comparison.

Measured properly, on Hutchinson Guest's *Labanotation* — the standard modern
textbook, and a vector figure that survives a 7x zoom, unlike the scanned
plates. Fig. 162a: staff box x 308..507 = 199, ruled into four columns, so
49.8 a column; the arm-gesture blocks beside it are 203, 194, 194 and 196
tall, one movement each, median 195.

| source                      | column width | beat height | column / beat |
|-----------------------------|--------------|-------------|---------------|
| Hutchinson Guest, fig. 162a | 49.8         | 195         | 0.255         |
| ours, before                | 26           | 60          | 0.433         |
| ours, after                 | 26           | 102         | 0.255         |

**1.70 times, not 2.3.** Column width over beat height is the invariant worth
comparing: a column is a well-defined object on both sides, where "the staff"
is not — it may or may not include the arm columns, and the plate detectors
cannot tell.

Closed by raising `BEAT_HEIGHT` 60 -> 102 rather than narrowing the columns to
15.3, which is the other way to the same ratio. A 15-unit column cannot hold
the ten graded foot marks, whose reach is already capped at 4px, nor the
interior area a level fill needs.

One consequence, recorded rather than fixed: the example score's canvas goes
from 1 : 1.08 to 1 : 2.16, against the plates' 1 : 1.37. A taller beat makes
each system taller, and we tile four systems across one canvas where the
plates give each system its own page. Whether to reduce
`LABAN_SYSTEM_CAPACITY` from 8, or to emit multiple pages, is the page
composition question and is still open. The plates use 8 measures to a system,
so the capacity is not obviously the thing to change.

The scanned-plate measurements are left below for the record. They are
consistent with each other and with Hutchinson once read as box-to-box, but
their column counts were never established, so they cannot produce a
column-to-beat figure:

| plate                | box width | beat height | box / beat |
|----------------------|-----------|-------------|------------|
| La vivandiere p72    | 112       | 89.3        | 1.25       |
| La vivandiere p84    | 105       | 78.7        | 1.33       |
| La vivandiere p90    | 142       | 103.0       | 1.38       |
| Soiree musicale p58  | 129       | 97.0        | 1.33       |

Method note worth keeping: beats per measure came from counting the beat ticks
the notation draws on its own centre line -- sample a narrow band at the
staff's centre x, take dark runs, and the median gap is the beat height. No
music and no eye. It was reading beats off the piano reduction, and assuming
three where p90 has two, that made those four plates look scattered at first.

Next parity priorities:
1. Shift more renderer branching from symbol-id checks to catalog behavior
   roles. `behavior.cap_shape`, `behavior.preferred_separator_mode` and
   `behavior.pre_sign` are read now; several families still key off id
   prefixes, and every defect of the "id says X, renderer ignores it" class
   came from that pattern.
2. Add explicit geometry for springs, carets, staples, and the
   retention/cancellation families.
3. Expand official motif and LMA variants beyond current placeholders.
4. Add golden SVG fixtures for representative LabanWriter-style examples.

Bar lines were on this list and are settled: solid across the staff, stopping
on the outer staff lines, continuing outward as a dashed time reference. The
meaning of the dashed segments is now known — they tie the same count across
every staff on the page.
