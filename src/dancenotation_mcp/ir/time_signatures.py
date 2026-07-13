"""Arbitrary time signature support.

Extracts per-measure beat counts from IR extensions.time_signatures,
replacing the previous hardcoded 4-beats-per-measure assumption.
"""

from __future__ import annotations

DEFAULT_BEATS_PER_MEASURE = 4.0

# Standard denominator → beat fraction mapping.
# e.g. denominator 8 means each beat unit is an eighth note = 0.5 quarter beats.
_DENOM_TO_BEAT_FRACTION = {
    2: 2.0,   # half note = 2 quarter beats
    4: 1.0,   # quarter note = 1 quarter beat
    8: 0.5,   # eighth note = 0.5 quarter beats
    16: 0.25, # sixteenth note = 0.25 quarter beats
}


def build_measure_beats_map(ir: dict) -> dict[int, float]:
    """Build a map of measure number → beats-per-measure from IR.

    Reads extensions.time_signatures (sorted by measure) and propagates
    each time signature forward until the next change. Measures before
    any time signature get DEFAULT_BEATS_PER_MEASURE.

    Returns {measure: beats_per_measure} for every measure in the score.
    """
    time_sigs = ir.get("extensions", {}).get("time_signatures", [])
    if not time_sigs:
        return {}

    # Sort by measure number
    sorted_sigs = sorted(time_sigs, key=lambda ts: ts.get("measure", 1))

    # Build change points: measure → beats_per_measure
    change_points: dict[int, float] = {}
    for ts in sorted_sigs:
        m = int(ts.get("measure", 1))
        num = int(ts.get("numerator", 4))
        den = int(ts.get("denominator", 4))
        beat_fraction = _DENOM_TO_BEAT_FRACTION.get(den, 1.0)
        # beats_per_measure = numerator * (beat_fraction relative to quarter note)
        change_points[m] = num * beat_fraction

    return change_points


def beats_for_measure(measure: int, beats_map: dict[int, float]) -> float:
    """Return the number of beats for a specific measure.

    Looks up the most recent time signature at or before this measure.
    Falls back to DEFAULT_BEATS_PER_MEASURE if no time signatures defined.
    """
    if not beats_map:
        return DEFAULT_BEATS_PER_MEASURE

    # Find the most recent change point at or before this measure
    active_beats = DEFAULT_BEATS_PER_MEASURE
    for change_measure in sorted(beats_map.keys()):
        if change_measure <= measure:
            active_beats = beats_map[change_measure]
        else:
            break
    return active_beats


def measure_count_from_ir(symbols: list[dict], beats_map: dict[int, float]) -> int:
    """Compute the total number of measures needed for a list of symbols.

    Unlike the old hardcoded version, this accounts for variable beats per measure.
    """
    if not symbols:
        return 1

    max_measure = 1
    for s in symbols:
        timing = s.get("timing", {})
        m = max(int(timing.get("measure", 1)), 1)
        beat = float(timing.get("beat", 1.0))
        duration = max(float(timing.get("duration_beats", 1.0)), 0.25)
        bpm = beats_for_measure(m, beats_map)
        # Check if this symbol extends into the next measure
        end_beat = beat + duration
        extra_measures = 0
        while end_beat > bpm + 1.0:  # +1 because beat 1 is the first beat
            extra_measures += 1
            next_m = m + extra_measures
            end_beat -= bpm
            bpm = beats_for_measure(next_m, beats_map)
        max_measure = max(max_measure, m + extra_measures)
    return max_measure


def symbol_absolute_time(symbol: dict, beats_map: dict[int, float]) -> tuple[float, float]:
    """Convert symbol timing to absolute beat position, respecting variable time signatures.

    Returns (start_abs, end_abs) in absolute beats from the beginning of the score.
    """
    timing = symbol.get("timing", {})
    measure = max(int(timing.get("measure", 1)), 1)
    beat = float(timing.get("beat", 1.0))
    duration = max(float(timing.get("duration_beats", 1.0)), 0.25)

    # Sum beats of all preceding measures
    abs_start = 0.0
    for m in range(1, measure):
        abs_start += beats_for_measure(m, beats_map)
    abs_start += (beat - 1.0)  # beat 1 is the start of the measure

    return abs_start, abs_start + duration
