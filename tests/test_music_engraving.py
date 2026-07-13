from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    import music21  # noqa: F401
    HAS_MUSIC21 = True
except ImportError:
    HAS_MUSIC21 = False

from dancenotation_mcp.rendering.music_engraver import find_lilypond_binary, render_music_svg
from dancenotation_mcp.rendering.music_import import check_measure_alignment, import_music_source

ROOT = Path(__file__).resolve().parents[1]
HAS_LILYPOND = find_lilypond_binary() is not None


def _write_test_musicxml(path: Path, measures: int = 2) -> None:
    from music21 import meter, note, stream

    part = stream.Part()
    part.append(meter.TimeSignature("4/4"))
    pitches = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
    for i in range(measures * 4):
        part.append(note.Note(pitches[i % len(pitches)], quarterLength=1))
    score = stream.Score()
    score.append(part)
    score.write("musicxml", fp=str(path))


def _minimal_dance_ir(measures: int = 2):
    symbols = [
        {
            "symbol_id": "support.step.forward",
            "body_part": "left_leg",
            "direction": "forward",
            "level": "middle",
            "timing": {"measure": m, "beat": 1, "duration_beats": 1},
            "modifiers": {},
        }
        for m in range(1, measures + 1)
    ]
    return {"metadata": {"title": "Music Alignment Test"}, "symbols": symbols}


@unittest.skipUnless(HAS_MUSIC21, "music21 not installed")
class MusicImportTests(unittest.TestCase):

    def test_import_valid_musicxml_returns_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=2)
            score = import_music_source(path)
            self.assertIsNotNone(score)

    def test_import_missing_file_returns_none(self):
        score = import_music_source(Path("/nonexistent/does-not-exist.musicxml"))
        self.assertIsNone(score)

    def test_alignment_matches_when_measure_counts_agree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=2)
            score = import_music_source(path)
            report = check_measure_alignment(score, _minimal_dance_ir(measures=2))
            self.assertTrue(report["aligned"])
            self.assertEqual(report["music_measure_count"], 2)
            self.assertEqual(report["dance_measure_count"], 2)

    def test_alignment_flags_measure_count_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=3)
            score = import_music_source(path)
            report = check_measure_alignment(score, _minimal_dance_ir(measures=2))
            self.assertFalse(report["aligned"])
            self.assertEqual(report["music_measure_count"], 3)
            self.assertEqual(report["dance_measure_count"], 2)

    def test_alignment_with_no_score_reports_unaligned(self):
        report = check_measure_alignment(None, _minimal_dance_ir())
        self.assertFalse(report["aligned"])


@unittest.skipUnless(HAS_MUSIC21 and HAS_LILYPOND, "music21 and a local lilypond install are both required")
class MusicEngravingTests(unittest.TestCase):

    def test_render_music_svg_produces_valid_svg(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=1)
            score = import_music_source(path)
            svg = render_music_svg(score)
            self.assertIsNotNone(svg)
            self.assertIn("<svg", svg)

    def test_render_music_svg_with_none_score_returns_none(self):
        self.assertIsNone(render_music_svg(None))

    def test_render_music_svg_forces_single_continuous_line(self):
        """A multi-measure piece must render as one unbroken horizontal
        strip (matching the reference score's melody-line style), not
        LilyPond's default multi-system page wrapping.
        """
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=6)
            score = import_music_source(path)
            svg = render_music_svg(score)
            self.assertIsNotNone(svg)
            self.assertEqual(svg.count("<svg"), 1)


class ServerMusicIntegrationTests(unittest.TestCase):

    def test_generate_score_without_music_source_omits_music_paths(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_dance_ir()
        result = TOOLS["generate_score"]({"ir": ir, "name": "no-music-integration-test"})
        self.assertNotIn("music_svg_path", result)
        (ROOT / result["svg_path"]).unlink(missing_ok=True)
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)

    def test_generate_score_with_unparsable_music_source_degrades_gracefully(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        ir = _minimal_dance_ir()
        result = TOOLS["generate_score"]({
            "ir": ir,
            "name": "bad-music-integration-test",
            "music_source": "/nonexistent/does-not-exist.musicxml",
        })
        self.assertIsNone(result.get("music_svg_path"))
        self.assertFalse(result.get("music_engraved"))
        (ROOT / result["svg_path"]).unlink(missing_ok=True)
        if result.get("pdf_path"):
            (ROOT / result["pdf_path"]).unlink(missing_ok=True)
        if result.get("tikz_path"):
            (ROOT / result["tikz_path"]).unlink(missing_ok=True)

    @unittest.skipUnless(HAS_MUSIC21 and HAS_LILYPOND, "music21 and a local lilypond install are both required")
    def test_generate_score_with_music_source_emits_music_files(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=2)
            ir = _minimal_dance_ir(measures=2)
            result = TOOLS["generate_score"]({
                "ir": ir,
                "name": "music-integration-test",
                "music_source": str(path),
            })
            self.assertTrue(result.get("music_engraved"))
            self.assertIsNotNone(result.get("music_svg_path"))
            self.assertTrue(result["music_alignment"]["aligned"])
            music_svg = ROOT / result["music_svg_path"]
            self.assertTrue(music_svg.exists())
            music_svg.unlink(missing_ok=True)
            if result.get("music_pdf_path"):
                (ROOT / result["music_pdf_path"]).unlink(missing_ok=True)
            (ROOT / result["svg_path"]).unlink(missing_ok=True)
            if result.get("pdf_path"):
                (ROOT / result["pdf_path"]).unlink(missing_ok=True)
            if result.get("tikz_path"):
                (ROOT / result["tikz_path"]).unlink(missing_ok=True)

    @unittest.skipUnless(HAS_MUSIC21 and HAS_LILYPOND, "music21 and a local lilypond install are both required")
    def test_render_music_tool(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.musicxml"
            _write_test_musicxml(path, measures=1)
            result = TOOLS["render_music"]({"music_source": str(path)})
            self.assertIsNotNone(result["svg"])
            self.assertIn("<svg", result["svg"])

    def test_render_music_tool_with_bad_source_returns_reason(self):
        from dancenotation_mcp.mcp_server.server import TOOLS
        result = TOOLS["render_music"]({"music_source": "/nonexistent/does-not-exist.musicxml"})
        self.assertIsNone(result["svg"])
        self.assertIn("reason", result)


if __name__ == "__main__":
    unittest.main()
