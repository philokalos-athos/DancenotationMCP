from __future__ import annotations

import logging
import os
from pathlib import Path


LOGGER = logging.getLogger(__name__)
_DLL_HANDLES: list[object] = []


def _candidate_cairo_dirs() -> list[Path]:
    candidates: list[Path] = []
    env_roots = [
        os.environ.get("GTK_RUNTIME_ROOT"),
        os.environ.get("GTK3_RUNTIME_ROOT"),
        os.environ.get("GTK_BASEPATH"),
    ]
    for value in env_roots:
        if value:
            candidates.append(Path(value) / "bin")
            candidates.append(Path(value))
    candidates.extend(
        [
            Path(r"C:\Program Files\GTK3-Runtime Win64\bin"),
            Path(r"C:\Program Files\GTK3-Runtime Win64"),
        ]
    )
    return [path for path in candidates if path.exists()]


def _configure_windows_cairo_runtime() -> None:
    if os.name != "nt":
        return
    current_path = os.environ.get("PATH", "")
    for dll_dir in _candidate_cairo_dirs():
        dll_dir_str = str(dll_dir)
        if hasattr(os, "add_dll_directory"):
            try:
                _DLL_HANDLES.append(os.add_dll_directory(dll_dir_str))
            except OSError:
                pass
        if dll_dir_str not in current_path:
            current_path = f"{dll_dir_str};{current_path}" if current_path else dll_dir_str
    os.environ["PATH"] = current_path


def svg_to_pdf(svg_content: str, path: str | Path) -> bool:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _configure_windows_cairo_runtime()
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
