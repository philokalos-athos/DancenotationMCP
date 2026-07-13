"""Local music engraving via music21 -> LilyPond -> SVG.

LilyPond is an optional local toolchain dependency, matching pdf_renderer.py's
graceful-degradation pattern for cairosvg/cairo: if the `lilypond` binary
isn't on PATH, or engraving fails for any reason, render_music_svg() returns
None (and logs a warning) instead of raising. This repo is local-only by
design (see CLAUDE.md) — we invoke the binary via subprocess with no network
access, we never touch music21's persistent global UserSettings (that would
be a side effect outside this repo affecting the user's other projects), and
we resolve the binary via PATH (shutil.which) at call time instead.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

LOGGER = logging.getLogger(__name__)

# Forces the whole piece onto a single continuous horizontal line instead of
# LilyPond's automatic multi-system page wrapping — matching the reference
# score's melody-line style (a continuous strip running alongside the dance
# staff, not paginated sheet music).
_SINGLE_LINE_OVERRIDE = """
\\paper {
  indent = 0
  ragged-right = ##t
}
\\layout {
  \\context {
    \\Score
    \\override NonMusicalPaperColumn.line-break-permission = ##f
  }
}
"""


def find_lilypond_binary() -> str | None:
    return shutil.which("lilypond")


def render_music_svg(score, timeout_seconds: float = 60.0) -> str | None:
    """Engrave a music21 score/stream to SVG via a local LilyPond install.

    Returns None (and logs a warning) if `score` is None, LilyPond isn't
    installed, or engraving fails for any reason — music engraving is a
    supplementary output, not a hard requirement for dance-notation scores.
    """
    if score is None:
        return None

    lilypond_bin = find_lilypond_binary()
    if not lilypond_bin:
        LOGGER.warning("lilypond binary not found on PATH; skipping music engraving")
        return None

    with tempfile.TemporaryDirectory(prefix="dancenotation-music-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        ly_path = tmp_path / "score.ly"
        try:
            # Clearing metadata suppresses music21's auto-generated \header
            # title block. With a title, LilyPond splits output into a
            # numbered title page (score-1.svg) plus the music (score-2.svg)
            # instead of a single score.svg — we want just the music, sized
            # to sit beside the dance staff, not a title page of its own.
            score.metadata = None
            score.write("lily", fp=str(ly_path))
            with ly_path.open("a", encoding="utf-8") as ly_file:
                ly_file.write(_SINGLE_LINE_OVERRIDE)
        except Exception as exc:
            LOGGER.warning("music21 failed to write LilyPond source: %s", exc)
            return None

        try:
            result = subprocess.run(
                [lilypond_bin, "--svg", "-o", str(tmp_path / "score"), str(ly_path)],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            LOGGER.warning("lilypond invocation failed: %s", exc)
            return None

        if result.returncode != 0:
            LOGGER.warning("lilypond engraving failed (exit %s): %s", result.returncode, result.stderr[-2000:])
            return None

        svg_path = tmp_path / "score.svg"
        if not svg_path.exists():
            # Defensive fallback: some inputs still produce numbered pages
            # (e.g. multi-movement scores forcing a page break). Take the
            # last page — title/front matter sorts first, music last.
            numbered = sorted(tmp_path.glob("score-*.svg"))
            if numbered:
                svg_path = numbered[-1]
        if not svg_path.exists():
            LOGGER.warning("lilypond did not produce an SVG output in %s", tmp_path)
            return None
        return svg_path.read_text(encoding="utf-8")
