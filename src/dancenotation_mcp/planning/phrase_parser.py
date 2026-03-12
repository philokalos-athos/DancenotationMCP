from __future__ import annotations

import re


DIRECTION_WORDS = {
    "forward": "forward",
    "backward": "backward",
    "left": "left",
    "right": "right",
    "diagonal": "diagonal_forward_left",
}

LEVEL_WORDS = {
    "high": "high",
    "middle": "middle",
    "low": "low",
}

BODY_WORDS = {
    "left arm": "left_arm",
    "right arm": "right_arm",
    "left leg": "left_leg",
    "right leg": "right_leg",
    "torso": "torso",
}

ACTION_TO_SYMBOL = {
    "step": "support.step",
    "gesture": "gesture.arm",
    "turn": "turn.pivot",
    "jump": "jump.small",
}


def parse_phrase(prompt: str) -> dict:
    clauses = [c.strip() for c in re.split(r"[,.]", prompt.lower()) if c.strip()]
    steps = []
    beat = 1.0
    for clause in clauses:
        action = next((a for a in ACTION_TO_SYMBOL if a in clause), "step")
        direction = next((v for k, v in DIRECTION_WORDS.items() if k in clause), "forward")
        level = next((v for k, v in LEVEL_WORDS.items() if k in clause), "middle")
        body = next((v for k, v in BODY_WORDS.items() if k in clause), "right_leg")
        dur = 2.0 if "hold" in clause else 1.0
        steps.append(
            {
                "action": action,
                "symbol_id": ACTION_TO_SYMBOL[action],
                "body_part": body,
                "direction": direction,
                "level": level,
                "timing": {"measure": 1, "beat": beat, "duration_beats": dur},
                "source_text": clause,
            }
        )
        beat += dur
    return {"version": "0.1.0", "steps": steps}
