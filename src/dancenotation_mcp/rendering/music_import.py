"""MusicXML/MIDI import for pairing a music score with a dance IR.

music21 is treated as an optional dependency, matching pdf_renderer.py's
graceful-degradation pattern for cairosvg: if it's unavailable or the source
file can't be parsed, functions return None (and log a warning) rather than
raising, so a missing/broken music source never breaks dance-notation-only
output.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dancenotation_mcp.ir.time_signatures import (
    beats_for_measure,
    build_measure_beats_map,
    measure_count_from_ir,
)

LOGGER = logging.getLogger(__name__)


def import_music_source(path: str | Path):
    """Parse a MusicXML or MIDI file into a music21 Score.

    Returns None (and logs a warning) if music21 is unavailable or the file
    can't be parsed.
    """
    try:
        import music21
    except ImportError:
        LOGGER.warning("music21 is unavailable; skipping music import for %s", path)
        return None

    try:
        return music21.converter.parse(str(path))
    except Exception as exc:  # music21 raises many distinct exception types
        LOGGER.warning("Failed to parse music source %s: %s", path, exc)
        return None


def check_measure_alignment(score, ir: dict) -> dict:
    """Compare the music score's measure/meter structure against the dance IR's.

    Returns {"aligned": bool, "music_measure_count": int,
    "dance_measure_count": int, "mismatched_time_signatures": [...]}.
    This is a lightweight validation, not a full re-modeling of the music as
    IR — music21's own Score is the canonical representation of the notes;
    this just confirms the two timelines actually correspond measure-for-
    measure before they're composed side by side.
    """
    if score is None:
        return {"aligned": False, "reason": "no music score provided"}

    try:
        part = score.parts[0] if score.parts else score
        measures = list(part.getElementsByClass("Measure"))
        music_measure_count = len(measures)
    except Exception:
        measures = []
        music_measure_count = 0

    beats_map = build_measure_beats_map(ir)
    dance_measure_count = measure_count_from_ir(ir.get("symbols", []), beats_map)

    mismatched_time_signatures: list[dict] = []
    try:
        for measure in measures:
            ts = measure.timeSignature
            if ts is None:
                continue
            music_beats = ts.numerator * (4.0 / ts.denominator)
            dance_beats = beats_for_measure(measure.number, beats_map)
            if abs(music_beats - dance_beats) > 0.01:
                mismatched_time_signatures.append({
                    "measure": measure.number,
                    "music_beats": music_beats,
                    "dance_beats": dance_beats,
                })
    except Exception as exc:
        LOGGER.warning("Could not fully check time-signature alignment: %s", exc)

    aligned = (
        music_measure_count == dance_measure_count
        and not mismatched_time_signatures
    )
    return {
        "aligned": aligned,
        "music_measure_count": music_measure_count,
        "dance_measure_count": dance_measure_count,
        "mismatched_time_signatures": mismatched_time_signatures,
    }
