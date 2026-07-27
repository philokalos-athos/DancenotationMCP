# ICKL reference materials

The International Council of Kinetography Laban is the standards body for the
notation this project renders. Its stated aim includes "acting as a deciding
body with regard to the orthography and principles of the system", and its
Research Panel is "the coordinating body of the Council in all Technical
Matters". Proceedings and Technical Reports are freely downloadable.

The PDFs are **not committed** — they are third-party publications totalling
~56 MB. Fetch them with:

```bash
python references/fetch_ickl.py
```

`ickl.org` returns 403 to requests without a browser User-Agent; the script
sets one. Files land in `references/ickl/` which is gitignored.

## What ICKL does and does not settle

This matters for deciding where an engraving argument gets resolved, so it was
measured rather than assumed. Full-text search across all seven documents
(~1500 pages) for engraving vocabulary:

| Term | Occurrences |
|---|---|
| `column width`, `staff width`, `line thickness`, `symbol size` | **0** |
| `engrav*` | **1** |
| `spacing` | 4 — all about dancers on stage or UI property sheets |
| `layout` | 19 — same, plus one about an EWMN property sheet |
| `support column` | 19 — semantics, not geometry |

**ICKL specifies orthography and semantics, not engraving geometry.** The 2017
Technical Report is research-panel business, workshop write-ups (Noëlle Simonet
on analysing transfer of weight) and archive matters — authoritative on what a
sign *means* and how movement is *analysed*, silent on how wide a column is or
whether a symbol fills it.

That report also records that the 1993 index of accumulated technical decisions
was never continued, so there is no current consolidated rulebook even for the
matters ICKL does cover — the decisions are distributed across conference
proceedings.

## Consequence for this project

Authority depends on the kind of question:

| Question | Authority |
|---|---|
| What does a sign mean; how is a movement analysed | ICKL Proceedings + Technical Reports |
| What does a sign look like | LabanWriter / KineScribe palettes (the digitised ICKL sign set) |
| Column widths, spacing, alignment, what fills what | **Published scores only** |

Nothing standardises layout, and no tool automates it — LabanWriter and its
touch-screen successor KineScribe are both manual drawing tools where the
notator positions symbols by hand against non-printing guides. Engraving
convention lives as craft knowledge in published scores.

This makes the Hutchinson Guest reference score (repo root, gitignored for
size) the primary layout authority, not a secondary one. See
`docs/labanwriter_parity_audit.md`.

## Contents

| File | Notes |
|---|---|
| `2017_Technical_Report_Addendum.pdf` | Research Panel technical report, revised. 26 pp. |
| `Proceedings_ICKL22_web.pdf` | 32nd conference, Budapest 2022 — most recent |
| `Proceedings_ICKL_2019_web.pdf` | 31st, Mexico City |
| `Proceedings_ICKL_2017_web.pdf` | 30th, Beijing Normal University |
| `Proceedings_ICKL_2015_web.pdf` | 29th, Tours |
| `Proceedings2013_web.pdf` | 28th, Toronto |
| `Proceedings_ICKL_2011_web.pdf` | 27th, Budapest |

Older proceedings (1959 onward) are listed at
<https://ickl.org/publications/>. Additional theoretical material is at
<http://kinetography.eu>, referenced by the 2017 report.
