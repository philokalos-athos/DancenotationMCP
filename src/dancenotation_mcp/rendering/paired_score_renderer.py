"""Compose the Labanotation staff with a per-measure-aligned music strip.

The reference score (Ann Hutchinson Guest's *La Vivandiere*) runs its melody
line *vertically*, rotated 90 degrees, so it lines up bottom-to-top exactly
like the dance staff's own time flow, measure for measure. LilyPond has no
native vertical-staff mode (all music engraving software is horizontal), so
this renders each measure as its own small horizontal snippet, then rotates
and scales each one individually to fit its corresponding dance measure's
exact pixel height — rather than rotating one long continuous strip, which
wouldn't line up per measure since dance measures vary in height (different
time signatures / stacking pressure) while LilyPond's own measure widths
don't naturally match.

Graceful degradation matches every other optional-toolchain path in this
codebase: if the music can't be engraved (see music_engraver.py), this falls
back to the plain dance-only render_laban_svg output rather than raising.

Performance note: this invokes the `lilypond` subprocess once per measure
(~0.3-1s each observed locally), since each measure needs independent
rotation/scaling to its own dance-measure height. A long ballet (hundreds of
measures) will take proportionally longer than the single-invocation
render_music_svg() path — acceptable for the paired/enhanced output, but
callers wanting a fast preview should use the plain music_svg_path output
from generate_score instead.
"""

from __future__ import annotations

import logging
import re

from dancenotation_mcp.rendering.laban_layout import compute_laban_layout
from dancenotation_mcp.rendering.laban_renderer import render_laban_svg
from dancenotation_mcp.rendering.music_engraver import find_lilypond_binary, render_music_svg

LOGGER = logging.getLogger(__name__)

MUSIC_GUTTER_GAP = 16.0
MUSIC_STRIP_THICKNESS = 40.0

_SVG_OPEN_RE = re.compile(r'<svg\b[^>]*viewBox="([\d.\-]+) ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)"[^>]*>', re.IGNORECASE)
_SVG_TAG_RE = re.compile(r'^\s*<svg\b[^>]*>|</svg>\s*$', re.IGNORECASE)


def _extract_svg_inner(svg_text: str) -> tuple[str, tuple[float, float, float, float]] | None:
    """Return (inner_markup, (vb_x, vb_y, vb_w, vb_h)) for a standalone SVG document."""
    match = _SVG_OPEN_RE.search(svg_text)
    if not match:
        return None
    vb = tuple(float(g) for g in match.groups())
    inner = svg_text[match.end():]
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.IGNORECASE)
    return inner, vb  # type: ignore[return-value]


def _measure_snippet(measure, is_first: bool):
    """Render one music21 Measure as its own standalone SVG snippet."""
    from music21 import stream

    part = stream.Part()
    if is_first:
        # First measure keeps its clef/time signature (already attached by
        # music21 when the measure came from a parsed part); later measures
        # render as bare notes, matching how the continuous strip would
        # naturally look mid-piece.
        part.append(measure)
    else:
        stripped = measure.template()
        for element in measure.notesAndRests:
            stripped.insert(element.offset, element)
        part.append(stripped)
    score = stream.Score()
    score.append(part)
    return render_music_svg(score)


def _rotated_measure_group(inner: str, vb: tuple[float, float, float, float],
                            y_bottom: float, y_top: float, gutter_center_x: float,
                            thickness: float) -> str:
    """Wrap a measure snippet's inner markup in a matrix transform that
    rotates it 90 degrees and scales/positions it to exactly span
    [y_top, y_bottom] vertically at gutter_center_x horizontally.

    Derivation: we want original x (time within the measure) to map to a
    new_y that decreases from y_bottom (start) to y_top (end) — matching the
    dance staff's bottom-to-top time flow — and original y (position within
    the 5-line staff) to map to a new_x centered on gutter_center_x. That
    gives an affine matrix(a, b, c, d, e, f) with a=0, d=0 (no direct-axis
    scaling, purely cross-axis):
        new_x = c*y + e
        new_y = b*x + f
    """
    vb_x, vb_y, vb_w, vb_h = vb
    if vb_w <= 0 or vb_h <= 0:
        return ""
    height_m = y_bottom - y_top
    b = -height_m / vb_w
    c = thickness / vb_h
    e = gutter_center_x - thickness / 2 - vb_y * c
    f = y_bottom - vb_x * b
    return f'<g transform="matrix(0 {b:.6f} {c:.6f} 0 {e:.3f} {f:.3f})" color="#111827">{inner}</g>'


def render_paired_score_svg(ir: dict, music_score) -> str:
    """Render the dance staff with a per-measure-aligned, rotated music
    strip to the left of each system. Falls back to the plain dance-only
    render if music_score is None or engraving isn't available.
    """
    dance_svg = render_laban_svg(ir)
    if music_score is None or find_lilypond_binary() is None:
        return dance_svg

    try:
        part = music_score.parts[0] if music_score.parts else music_score
        measures = list(part.getElementsByClass("Measure"))
    except Exception as exc:
        LOGGER.warning("Could not enumerate measures for paired rendering: %s", exc)
        return dance_svg
    if not measures:
        return dance_svg

    dance_layout = compute_laban_layout(ir)
    measure_positions = dance_layout["measure_positions"]
    systems = dance_layout["systems"]

    dance_extracted = _extract_svg_inner(dance_svg)
    if dance_extracted is None:
        return dance_svg
    dance_inner, dance_vb = dance_extracted
    _, _, dance_w, dance_h = dance_vb

    gutter_width = MUSIC_STRIP_THICKNESS + MUSIC_GUTTER_GAP
    total_width = dance_w + gutter_width

    music_groups: list[str] = []
    for index, measure in enumerate(measures):
        measure_number = measure.number or (index + 1)
        if measure_number not in measure_positions:
            continue
        system = next(
            (s for s in systems if s["start_measure"] <= measure_number <= s["end_measure"]),
            None,
        )
        if system is None:
            continue
        snippet_svg = _measure_snippet(measure, is_first=(index == 0))
        if snippet_svg is None:
            continue
        extracted = _extract_svg_inner(snippet_svg)
        if extracted is None:
            continue
        inner, vb = extracted
        y_bottom, y_top = measure_positions[measure_number]
        gutter_center_x = system["staff_left"] - MUSIC_GUTTER_GAP - MUSIC_STRIP_THICKNESS / 2
        music_groups.append(_rotated_measure_group(inner, vb, y_bottom, y_top, gutter_center_x, MUSIC_STRIP_THICKNESS))

    if not music_groups:
        return dance_svg

    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_width:.1f}" height="{dance_h:.1f}" '
        f'viewBox="0 0 {total_width:.1f} {dance_h:.1f}">',
        f'<g transform="translate({gutter_width:.1f} 0)">{dance_inner}</g>',
        *music_groups,
        "</svg>",
    ])
