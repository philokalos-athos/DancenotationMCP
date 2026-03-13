from __future__ import annotations

import logging
from pathlib import Path


LOGGER = logging.getLogger(__name__)


def svg_to_pdf(svg_content: str, path: str | Path) -> bool:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg
    except ImportError:
        LOGGER.warning("cairosvg is unavailable; skipping PDF generation for %s", target)
        return False
    except OSError as exc:
        LOGGER.warning("cairo runtime is unavailable; skipping PDF generation for %s (%s)", target, exc)
        return False

    try:
        cairosvg.svg2pdf(bytestring=svg_content.encode("utf-8"), write_to=str(target))
    except OSError as exc:
        LOGGER.warning("cairo runtime is unavailable; skipping PDF generation for %s (%s)", target, exc)
        return False
    return True
