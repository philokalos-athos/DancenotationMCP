# LabanWriter Parity Audit

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

Next parity priorities:
1. Shift more renderer branching from symbol-id checks to catalog behavior roles.
2. Add explicit geometry for springs, carets, staples, and retention/cancellation families.
3. Expand official motif and LMA variants beyond current placeholders.
4. Add golden SVG fixtures for representative LabanWriter-style examples.
