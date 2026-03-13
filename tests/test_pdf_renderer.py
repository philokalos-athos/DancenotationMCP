from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from dancenotation_mcp.mcp_server import server
from dancenotation_mcp.rendering import pdf_renderer


class PDFRendererTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_root = Path(__file__).resolve().parents[1] / "tests" / ".tmp"
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def test_generate_score_creates_pdf_alongside_svg(self):
        ir = {
            "metadata": {"title": "PDF Fixture", "ir_version": "0.1.0", "schema_version": "0.1.0"},
            "symbols": [
                {
                    "symbol_id": "support.step.forward",
                    "body_part": "left_leg",
                    "direction": "forward",
                    "level": "middle",
                    "timing": {"measure": 1, "beat": 1, "duration_beats": 1},
                    "modifiers": {},
                }
            ],
        }

        def fake_svg_to_pdf(svg_content: str, path: Path) -> bool:
            Path(path).write_bytes(b"%PDF-1.4\n%mock\n")
            return True

        score_name = f"pdf-fixture-{uuid4().hex[:8]}"
        svg_target = server.SVG_EXAMPLES_DIR / f"{score_name}.svg"
        pdf_target = server.PDF_EXAMPLES_DIR / f"{score_name}.pdf"
        self.addCleanup(lambda: svg_target.unlink(missing_ok=True))
        self.addCleanup(lambda: pdf_target.unlink(missing_ok=True))

        with patch.object(server, "svg_to_pdf", side_effect=fake_svg_to_pdf):
            result = server.generate_score({"ir": ir, "name": score_name})

        svg_path = server.REPO_ROOT / result["svg_path"]
        self.assertTrue(svg_path.exists())
        self.assertEqual(result["pdf_path"], f"examples/pdf/{score_name}.pdf")
        self.assertEqual(result["latex"], rf"\includegraphics{{examples/pdf/{score_name}}}")
        if result["pdf_path"] is not None:
            self.assertTrue((server.REPO_ROOT / result["pdf_path"]).exists())

    def test_svg_to_pdf_returns_false_when_cairosvg_is_unavailable(self):
        target = self.temp_root / f"{uuid4().hex[:8]}.pdf"
        self.addCleanup(lambda: target.unlink(missing_ok=True))
        real_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "cairosvg":
                raise ImportError("mocked missing cairosvg")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            created = pdf_renderer.svg_to_pdf("<svg xmlns='http://www.w3.org/2000/svg'></svg>", target)
        self.assertFalse(created)
        self.assertFalse(target.exists())

    def test_svg_to_pdf_returns_false_when_cairo_runtime_is_unavailable(self):
        target = self.temp_root / f"{uuid4().hex[:8]}.pdf"
        self.addCleanup(lambda: target.unlink(missing_ok=True))

        class FakeCairoSVG:
            @staticmethod
            def svg2pdf(*args, **kwargs):
                raise OSError("missing cairo runtime")

        with patch.dict("sys.modules", {"cairosvg": FakeCairoSVG()}):
            created = pdf_renderer.svg_to_pdf("<svg xmlns='http://www.w3.org/2000/svg'></svg>", target)
        self.assertFalse(created)
        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
