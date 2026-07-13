from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import music21  # noqa: F401
    HAS_MUSIC21 = True
except ImportError:
    HAS_MUSIC21 = False

from dancenotation_mcp.rendering.laban_renderer import render_laban_svg
from dancenotation_mcp.rendering.music_engraver import find_lilypond_binary
from dancenotation_mcp.rendering.music_import import import_music_source
from dancenotation_mcp.rendering.paired_score_renderer import render_paired_score_svg

HAS_LILYPOND = find_lilypond_binary() is not None


def _write_test_musicxml(path: Path, measures: int) -> None:
    from music21 import meter, note, stream

    part = stream.Part()
    part.append(meter.TimeSignature("4/4"))
    pitches = ["C4", "D4", "E4", "F4"]
    for i in range(measures * 4):
        part.append(note.Note(pitches[i % len(pitches)], quarterLength=1))
    score = stream.Score()
    score.append(part)
    score.write("musicxml", fp=str(path))


def _dance_ir(measures: int):
    return {
        "metadata": {"title": "Paired Score Test"},
        "symbols": [
            {
                "symbol_id": "support.step.forward",
                "body_part": "left_leg",
                "direction": "forward",
                "level": "middle",
                "timing": {"measure": m, "beat": 1, "duration_beats": 1},
                "modifiers": {},
            }
            for m in range(1, measures + 1)
        ],
    }


class PairedScoreFallbackTests(unittest.TestCase):
    """These must pass regardless of whether music21/lilypond are installed
    — graceful degradation to the plain dance-only render is the contract.
    """

    def test_none_music_score_falls_back_to_dance_only(self):
        ir = _dance_ir(2)
        paired = render_paired_score_svg(ir, None)
        plain = render_laban_svg(ir)
        self.assertEqual(paired, plain)


@unittest.skipUnless(HAS_MUSIC21 and HAS_LILYPOND, "music21 and a local lilypond install are both required")
class PairedScoreCompositionTests(unittest.TestCase):

    def test_paired_svg_is_wider_than_plain_dance_svg(self):
        """The composed output must reserve extra width for the rotated
        music strip beyond the plain dance-only staff.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=4)
            score = import_music_source(path)
            ir = _dance_ir(4)
            paired = render_paired_score_svg(ir, score)
            plain = render_laban_svg(ir)

            def _width(svg):
                import re
                return float(re.search(r'width="([\d.]+)"', svg).group(1))

            self.assertGreater(_width(paired), _width(plain))

    def test_paired_svg_has_one_rotated_group_per_measure(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=4)
            score = import_music_source(path)
            ir = _dance_ir(4)
            paired = render_paired_score_svg(ir, score)
            # Each measure gets one <g transform="matrix(...)"> wrapper.
            self.assertEqual(paired.count('transform="matrix('), 4)

    def test_paired_svg_height_matches_plain_dance_svg(self):
        """Composition must not change the dance staff's own vertical
        extent — only add width for the music gutter.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=3)
            score = import_music_source(path)
            ir = _dance_ir(3)
            paired = render_paired_score_svg(ir, score)
            plain = render_laban_svg(ir)

            def _height(svg):
                import re
                return float(re.search(r'height="([\d.]+)"', svg).group(1))

            self.assertAlmostEqual(_height(paired), _height(plain), places=1)

    def test_fewer_music_measures_than_dance_measures_degrades_partially(self):
        """If the music is shorter than the dance score, only the covered
        measures get a rotated strip — no crash, no fabricated notes.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=2)
            score = import_music_source(path)
            ir = _dance_ir(4)  # dance score has 4 measures, music only has 2
            paired = render_paired_score_svg(ir, score)
            self.assertEqual(paired.count('transform="matrix('), 2)


if __name__ == "__main__":
    unittest.main()
