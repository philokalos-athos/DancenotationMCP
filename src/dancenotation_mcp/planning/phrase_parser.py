from __future__ import annotations

import re


MULTI_BODY_PATTERNS = [
    ("both arms", ["left_arm", "right_arm"]),
    ("both hands", ["left_arm", "right_arm"]),
    ("hands", ["left_arm", "right_arm"]),
    ("both legs", ["left_leg", "right_leg"]),
    ("both feet", ["left_leg", "right_leg"]),
    ("feet", ["left_leg", "right_leg"]),
]

DIRECTION_PATTERNS = [
    ("counterclockwise", "left"),
    ("clockwise", "right"),
    ("downstage", "forward"),
    ("upstage", "backward"),
    ("in place", "place"),
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
    "face": "head",
    "head": "head",
    "chest": "torso",
    "hips": "torso",
    "hip": "torso",
    "waist": "torso",
    "spine": "torso",
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
TORSO_ACTIONS = {"turn", "meter", "tempo", "cadence", "repeat", "rest"}
ANNOTATION_ACTIONS = {"pin", "surface", "quality", "level", "timing"}
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
    ("silence", "rest", "music.rest.quarter"),
    ("pause", "rest", "music.rest.quarter"),
    ("rest", "rest", "music.rest.quarter"),
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
    (r"\bfor four beats?\b", 4.0),
    (r"\bfour beats?\b", 4.0),
    (r"\bhold\b", 2.0),
    (r"\bsustain\b", 2.0),
    (r"\blinger\b", 2.0),
    (r"\band a half\b", 1.5),
    (r"\bone and a half beats?\b", 1.5),
    (r"\bhalf beat\b", 0.5),
    (r"\bquarter beat\b", 0.25),
    (r"\b(two|2) beats?\b", 2.0),
    (r"\bthree beats?\b", 3.0),
]

QUALITY_PATTERNS = [
    ("immediately", "quality.sudden"),
    ("sudden", "quality.sudden"),
    ("slowly", "quality.sustained"),
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


def _split_top_level(text: str, delimiters: set[str]) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        if depth == 0 and char in delimiters:
            chunk = "".join(current).strip()
            if chunk:
                parts.append(chunk)
            current = []
            continue
        current.append(char)
    chunk = "".join(current).strip()
    if chunk:
        parts.append(chunk)
    return parts


def _split_clauses(prompt: str) -> list[str]:
    normalized = _normalize_prompt(prompt)
    normalized = re.sub(r"\bthen immediately\b", ",", normalized)
    normalized = re.sub(r"\bthen\b", ",", normalized)
    normalized = re.sub(r"\bfollowed by\b", ",", normalized)
    return _split_top_level(normalized, {",", ";"})


def _normalize_prompt(prompt: str) -> str:
    normalized = prompt.lower()
    normalized = re.sub(r"\baccel\s+\.\b", "accel.", normalized)
    normalized = re.sub(r"\brit\s+\.\b", "rit.", normalized)
    normalized = re.sub(r"\ba\s*tempo\b", "a tempo", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _split_parallel_clauses(clause: str) -> list[str]:
    connectors = {"while", "with", "simultaneously", "together", "alongside"}
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    tokens = re.split(r"(\b(?:while|with|simultaneously|together|alongside)\b|[()])", clause)
    for token in tokens:
        if not token:
            continue
        if token == "(":
            depth += 1
            current.append(token)
            continue
        if token == ")":
            depth = max(0, depth - 1)
            current.append(token)
            continue
        if depth == 0 and token.strip() in connectors:
            chunk = "".join(current).strip(" ()")
            if chunk:
                parts.append(chunk)
            current = []
            continue
        current.append(token)
    chunk = "".join(current).strip(" ()")
    if chunk:
        parts.append(chunk)
    return parts


def _split_temporal_sequence(clause: str) -> list[str]:
    after_parts = [part.strip(" ()") for part in re.split(r"\bafter\b", clause) if part.strip(" ()")]
    if len(after_parts) == 2:
        return [after_parts[1], after_parts[0]]
    before_parts = [part.strip(" ()") for part in re.split(r"\bbefore\b", clause) if part.strip(" ()")]
    if len(before_parts) == 2:
        return before_parts
    return [clause.strip(" ()")]


def _strip_negated_language(clause: str) -> str:
    cleaned = clause
    cleaned = re.sub(r"\bwithout\s+(?:turn|pivot|spin|repeat|jump|step|glide|slide|brush|gesture)\b", "", cleaned)
    cleaned = re.sub(r"\bno\s+repeat\b", "", cleaned)
    cleaned = re.sub(r"\brelease\s+hold\b", "", cleaned)
    cleaned = re.sub(r"\brelease\s+sustain\b", "", cleaned)
    cleaned = re.sub(r"\brelease\s+linger\b", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _resolve_action(clause: str) -> tuple[str, str]:
    if re.search(r"\b\d{2,3}\s*bpm\b", clause):
        return "tempo", "music.tempo.mark"
    for token, action, symbol_id in ACTION_PATTERNS:
        if token in clause:
            return action, symbol_id
    return "step", "support.step"


def _has_explicit_action(clause: str) -> bool:
    if re.search(r"\b\d{2,3}\s*bpm\b", clause):
        return True
    return any(token in clause for token, _, _ in ACTION_PATTERNS)


def _resolve_direction(clause: str) -> str:
    for token, direction in DIRECTION_PATTERNS:
        if token in clause:
            return direction
    return "forward"


def _resolve_level(clause: str) -> str:
    return next((v for k, v in LEVEL_WORDS.items() if k in clause), "middle")


def _has_explicit_direction(clause: str) -> bool:
    return any(token in clause for token, _direction in DIRECTION_PATTERNS)


def _has_explicit_level(clause: str) -> bool:
    return any(token in clause for token in LEVEL_WORDS)


def _has_explicit_body(clause: str) -> bool:
    return any(token in clause for token in BODY_WORDS) or any(token in clause for token, _bodies in MULTI_BODY_PATTERNS)


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


def _resolve_body_targets(clause: str, action: str, previous_step: dict | None = None) -> list[str]:
    for token, bodies in MULTI_BODY_PATTERNS:
        if token in clause:
            return bodies
    if (
        previous_step
        and not _has_explicit_body(clause)
        and not _has_explicit_direction(clause)
        and not _has_explicit_level(clause)
        and previous_step.get("action") == action
        and previous_step.get("body_part") in {"left_arm", "right_arm", "left_leg", "right_leg", "torso", "head"}
    ):
        return [previous_step["body_part"]]
    return [_resolve_body(clause, action, previous_step)]


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
        elif re.search(r"\b(?:twice|two times?)\b", clause):
            modifiers["repeat_count"] = 2
        elif re.search(r"\b(?:three times?)\b", clause):
            modifiers["repeat_count"] = 3
        elif re.search(r"\b(?:four times?)\b", clause):
            modifiers["repeat_count"] = 4
    return modifiers


def _resolve_repeat_symbol(clause: str, symbol_id: str) -> str:
    if "repeat" not in clause or symbol_id != "support.step":
        return symbol_id
    if re.search(r"\b(?:twice|two times?|double repeat)\b", clause):
        return "repeat.double"
    if re.search(r"\b(?:begin repeat|repeat start)\b", clause):
        return "repeat.start"
    if re.search(r"\b(?:end repeat|repeat end)\b", clause):
        return "repeat.end"
    return "repeat.end"


def _resolve_rest_symbol(duration: float, symbol_id: str) -> str:
    if not symbol_id.startswith("music.rest."):
        return symbol_id
    if duration <= 0.26:
        return "music.rest.sixteenth"
    if duration <= 0.51:
        return "music.rest.eighth"
    return "music.rest.quarter"


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


def _find_previous_primary_step(steps: list[dict]) -> dict | None:
    for step in reversed(steps):
        if step.get("action") in ANNOTATION_ACTIONS:
            continue
        if step.get("modifiers", {}).get("measure_header"):
            continue
        return step
    return None


def _advance_measure_position(measure: int, beat: float, duration: float, measure_beats: float) -> tuple[int, float]:
    beat += duration
    while beat > measure_beats:
        beat -= measure_beats
        measure += 1
    return measure, beat


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
            parallel_measure = measure
            parallel_beat = beat
            for parallel_clause in parallel_clauses:
                branch_measure = anchor_measure
                branch_beat = anchor_beat
                branch_measure_beats = measure_beats
                for branch_clause in _split_top_level(parallel_clause.strip(" ()"), {",", ";"}):
                    effective_clause = _strip_negated_language(branch_clause)
                    if not effective_clause:
                        continue
                    explicit_action = _has_explicit_action(effective_clause)
                    action, symbol_id = _resolve_action(effective_clause)
                    if "repeat" in effective_clause:
                        symbol_id = _resolve_repeat_symbol(effective_clause, symbol_id)
                        if symbol_id.startswith("repeat."):
                            action = "repeat"
                    previous_step = steps[-1] if steps else None
                    direction = _resolve_direction(effective_clause)
                    level = _resolve_level(effective_clause)
                    if previous_step and not _has_explicit_direction(effective_clause):
                        direction = previous_step.get("direction", direction)
                    if previous_step and not _has_explicit_level(effective_clause):
                        level = previous_step.get("level", level)
                    bodies = _resolve_body_targets(effective_clause, action, previous_step)
                    dur = _resolve_duration(effective_clause)
                    if action == "rest":
                        symbol_id = _resolve_rest_symbol(dur, symbol_id)
                    modifiers = _resolve_modifiers(effective_clause, action, symbol_id)
                    local_measure = branch_measure
                    local_beat = branch_beat
                    if modifiers.get("measure_header"):
                        local_beat = 1.0
                    companion_symbol_ids = _resolve_companion_symbols(effective_clause)
                    if not explicit_action and companion_symbol_ids:
                        previous_primary = _find_previous_primary_step(steps)
                        if previous_primary is None:
                            continue
                        local_measure = previous_primary["timing"]["measure"]
                        local_beat = previous_primary["timing"]["beat"]
                        prior_duration = float(previous_primary["timing"]["duration_beats"])
                        if "timing.hold" in companion_symbol_ids:
                            previous_primary["timing"]["duration_beats"] = max(prior_duration, dur)
                            extension = max(0.0, dur - prior_duration)
                            if extension:
                                branch_measure, branch_beat = _advance_measure_position(branch_measure, branch_beat, extension, branch_measure_beats)
                        for companion_symbol_id in companion_symbol_ids:
                            companion_action = companion_symbol_id.split(".", 1)[0]
                            steps.append(
                                {
                                    "action": companion_action,
                                    "symbol_id": companion_symbol_id,
                                    "body_part": previous_primary["body_part"],
                                    "direction": previous_primary["direction"],
                                    "level": previous_primary["level"],
                                    "timing": {"measure": local_measure, "beat": local_beat, "duration_beats": dur},
                                    "modifiers": {},
                                    "source_text": branch_clause,
                                }
                            )
                        continue
                    for body in bodies:
                        steps.append(
                            {
                                "action": action,
                                "symbol_id": symbol_id,
                                "body_part": body,
                                "direction": direction,
                                "level": level,
                                "timing": {"measure": local_measure, "beat": local_beat, "duration_beats": dur},
                                "modifiers": dict(modifiers),
                                "source_text": branch_clause,
                            }
                        )
                    if symbol_id in TIME_SIGNATURE_BEATS:
                        branch_measure_beats = TIME_SIGNATURE_BEATS[symbol_id]
                        measure_beats = branch_measure_beats
                    for body in bodies:
                        for companion_symbol_id in companion_symbol_ids:
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
                                    "source_text": branch_clause,
                                }
                            )
                    if _consumes_time(action, symbol_id, modifiers):
                        branch_measure, branch_beat = _advance_measure_position(branch_measure, branch_beat, dur, branch_measure_beats)
                if (branch_measure, branch_beat) > (parallel_measure, parallel_beat):
                    parallel_measure, parallel_beat = branch_measure, branch_beat
            measure, beat = parallel_measure, parallel_beat
    return {"version": "0.1.0", "steps": steps}
