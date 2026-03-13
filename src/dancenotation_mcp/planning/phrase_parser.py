from __future__ import annotations

import re


DIRECTION_PATTERNS = [
    ("forward left", "diagonal_forward_left"),
    ("forward-right", "diagonal_forward_right"),
    ("forward right", "diagonal_forward_right"),
    ("backward left", "diagonal_backward_left"),
    ("backward-right", "diagonal_backward_right"),
    ("backward right", "diagonal_backward_right"),
    ("diagonal left", "diagonal_forward_left"),
    ("diagonal right", "diagonal_forward_right"),
    ("forward", "forward"),
    ("backward", "backward"),
    ("left", "left"),
    ("right", "right"),
    ("place", "place"),
]

LEVEL_WORDS = {
    "high": "high",
    "middle": "middle",
    "low": "low",
}

BODY_WORDS = {
    "left arm": "left_arm",
    "right arm": "right_arm",
    "left hand": "left_arm",
    "right hand": "right_arm",
    "left leg": "left_leg",
    "right leg": "right_leg",
    "left foot": "left_leg",
    "right foot": "right_leg",
    "torso": "torso",
}

LEG_ACTIONS = {"step", "jump"}
ARM_ACTIONS = {"gesture", "glide", "brush"}
TORSO_ACTIONS = {"turn", "meter", "tempo", "cadence", "repeat"}
TIME_SIGNATURE_BEATS = {
    "music.time.2_4": 2.0,
    "music.time.3_4": 3.0,
    "music.time.4_4": 4.0,
}

ACTION_PATTERNS = [
    ("begin repeat", "repeat", "repeat.start"),
    ("repeat start", "repeat", "repeat.start"),
    ("end repeat", "repeat", "repeat.end"),
    ("repeat end", "repeat", "repeat.end"),
    ("double repeat", "repeat", "repeat.double"),
    ("a tempo", "cadence", "music.cadence.mark"),
    ("accelerando", "cadence", "music.cadence.mark"),
    ("accel.", "cadence", "music.cadence.mark"),
    ("accel", "cadence", "music.cadence.mark"),
    ("ritardando", "cadence", "music.cadence.mark"),
    ("rit.", "cadence", "music.cadence.mark"),
    ("rit", "cadence", "music.cadence.mark"),
    ("cadence", "cadence", "music.cadence.mark"),
    ("tempo", "tempo", "music.tempo.mark"),
    ("2/4", "meter", "music.time.2_4"),
    ("3/4", "meter", "music.time.3_4"),
    ("4/4", "meter", "music.time.4_4"),
    ("pivot", "turn", "turn.pivot"),
    ("spin", "turn", "turn.pivot"),
    ("turn", "turn", "turn.pivot"),
    ("leap", "jump", "jump.small"),
    ("hop", "jump", "jump.small"),
    ("jump", "jump", "jump.small"),
    ("glide", "glide", "surface.glide"),
    ("slide", "glide", "surface.glide"),
    ("brush", "brush", "surface.brush"),
    ("reach", "gesture", "gesture.arm"),
    ("gesture", "gesture", "gesture.arm"),
    ("walk", "step", "support.step"),
    ("step", "step", "support.step"),
]

DURATION_PATTERNS = [
    (r"\bhold\b", 2.0),
    (r"\bsustain\b", 2.0),
    (r"\blinger\b", 2.0),
    (r"\b(two|2) beats?\b", 2.0),
    (r"\bthree beats?\b", 3.0),
]

QUALITY_PATTERNS = [
    ("sudden", "quality.sudden"),
    ("sustained", "quality.sustained"),
    ("strong", "quality.strong"),
    ("light", "quality.light"),
    ("direct", "quality.direct"),
    ("flexible", "quality.flexible"),
    ("bound", "quality.bound"),
    ("free", "quality.free"),
]

TIMING_MARK_PATTERNS = [
    ("hold", "timing.hold"),
    ("sustain", "timing.hold"),
    ("linger", "timing.hold"),
    ("accented", "timing.accent"),
    ("accent", "timing.accent"),
    ("staccato", "timing.staccato"),
    ("tenuto", "timing.tenuto"),
    ("fermata", "timing.fermata"),
]


def _split_clauses(prompt: str) -> list[str]:
    normalized = re.sub(r"\bthen\b", ",", prompt.lower())
    normalized = re.sub(r"\bfollowed by\b", ",", normalized)
    return [c.strip() for c in re.split(r"[,.]", normalized) if c.strip()]


def _split_parallel_clauses(clause: str) -> list[str]:
    return [part.strip() for part in re.split(r"\b(?:while|with|simultaneously|together|alongside)\b", clause) if part.strip()]


def _split_temporal_sequence(clause: str) -> list[str]:
    after_parts = [part.strip() for part in re.split(r"\bafter\b", clause) if part.strip()]
    if len(after_parts) == 2:
        return [after_parts[1], after_parts[0]]
    before_parts = [part.strip() for part in re.split(r"\bbefore\b", clause) if part.strip()]
    if len(before_parts) == 2:
        return before_parts
    return [clause]


def _resolve_action(clause: str) -> tuple[str, str]:
    if re.search(r"\b\d{2,3}\s*bpm\b", clause):
        return "tempo", "music.tempo.mark"
    for token, action, symbol_id in ACTION_PATTERNS:
        if token in clause:
            return action, symbol_id
    return "step", "support.step"


def _resolve_direction(clause: str) -> str:
    for token, direction in DIRECTION_PATTERNS:
        if token in clause:
            return direction
    return "forward"


def _resolve_level(clause: str) -> str:
    return next((v for k, v in LEVEL_WORDS.items() if k in clause), "middle")


def _alternate_side(previous_body: str | None, left_value: str, right_value: str) -> str:
    if previous_body == right_value:
        return left_value
    return right_value


def _resolve_body(clause: str, action: str, previous_step: dict | None = None) -> str:
    body = next((v for k, v in BODY_WORDS.items() if k in clause), None)
    if body:
        return body
    previous_body = previous_step.get("body_part") if previous_step else None
    if action in ARM_ACTIONS:
        return _alternate_side(previous_body, "left_arm", "right_arm")
    if action in LEG_ACTIONS:
        return _alternate_side(previous_body, "left_leg", "right_leg")
    if action in TORSO_ACTIONS:
        return "torso"
    return "right_leg"


def _resolve_duration(clause: str) -> float:
    for pattern, duration in DURATION_PATTERNS:
        if re.search(pattern, clause):
            return duration
    return 1.0


def _resolve_modifiers(clause: str, action: str, symbol_id: str) -> dict:
    modifiers: dict = {}
    if symbol_id.startswith("music.time."):
        modifiers["measure_header"] = True
    elif symbol_id == "music.tempo.mark":
        modifiers["measure_header"] = True
        tempo_match = re.search(r"\btempo\s+(\d{2,3})\b", clause)
        bpm_match = re.search(r"\b(\d{2,3})\s*bpm\b", clause)
        tempo_value = int(tempo_match.group(1)) if tempo_match else int(bpm_match.group(1)) if bpm_match else None
        if tempo_value is not None:
            modifiers["tempo"] = tempo_value
    elif symbol_id == "music.cadence.mark":
        modifiers["measure_header"] = True
        if "a tempo" in clause:
            modifiers["label"] = "a tempo"
        elif "accelerando" in clause:
            modifiers["label"] = "accelerando"
        elif "accel." in clause or re.search(r"\baccel\b", clause):
            modifiers["label"] = "accel."
        elif "ritardando" in clause:
            modifiers["label"] = "ritardando"
        elif "rit." in clause or re.search(r"\brit\b", clause):
            modifiers["label"] = "rit."
        elif "cadence" in clause:
            modifiers["label"] = "cadence"
    elif action == "repeat":
        if symbol_id == "repeat.double":
            modifiers["repeat_count"] = 2
    return modifiers


def _resolve_companion_symbols(clause: str) -> list[str]:
    companions: list[str] = []
    for token, symbol_id in QUALITY_PATTERNS:
        if token in clause and symbol_id not in companions:
            companions.append(symbol_id)
    for token, symbol_id in TIMING_MARK_PATTERNS:
        if token in clause and symbol_id not in companions:
            companions.append(symbol_id)
    return companions


def _consumes_time(action: str, symbol_id: str, modifiers: dict) -> bool:
    if modifiers.get("measure_header"):
        return False
    if action == "repeat":
        return False
    return True


def parse_phrase(prompt: str) -> dict:
    clauses = _split_clauses(prompt)
    steps = []
    measure = 1
    beat = 1.0
    measure_beats = 4.0
    for clause in clauses:
        for sequential_clause in _split_temporal_sequence(clause):
            parallel_clauses = _split_parallel_clauses(sequential_clause)
            anchor_measure = measure
            anchor_beat = beat
            parallel_consumed = 0.0
            for parallel_clause in parallel_clauses:
                action, symbol_id = _resolve_action(parallel_clause)
                direction = _resolve_direction(parallel_clause)
                level = _resolve_level(parallel_clause)
                previous_step = steps[-1] if steps else None
                body = _resolve_body(parallel_clause, action, previous_step)
                dur = _resolve_duration(parallel_clause)
                modifiers = _resolve_modifiers(parallel_clause, action, symbol_id)
                local_measure = anchor_measure
                local_beat = anchor_beat
                if modifiers.get("measure_header"):
                    local_beat = 1.0
                steps.append(
                    {
                        "action": action,
                        "symbol_id": symbol_id,
                        "body_part": body,
                        "direction": direction,
                        "level": level,
                        "timing": {"measure": local_measure, "beat": local_beat, "duration_beats": dur},
                        "modifiers": modifiers,
                        "source_text": parallel_clause,
                    }
                )
                if symbol_id in TIME_SIGNATURE_BEATS:
                    measure_beats = TIME_SIGNATURE_BEATS[symbol_id]
                for companion_symbol_id in _resolve_companion_symbols(parallel_clause):
                    companion_action = companion_symbol_id.split(".", 1)[0]
                    steps.append(
                        {
                            "action": companion_action,
                            "symbol_id": companion_symbol_id,
                            "body_part": body,
                            "direction": direction,
                            "level": level,
                            "timing": {"measure": local_measure, "beat": local_beat, "duration_beats": dur},
                            "modifiers": {},
                            "source_text": parallel_clause,
                        }
                    )
                if _consumes_time(action, symbol_id, modifiers):
                    parallel_consumed = max(parallel_consumed, dur)
            beat += parallel_consumed
            while beat > measure_beats:
                beat -= measure_beats
                measure += 1
    return {"version": "0.1.0", "steps": steps}
