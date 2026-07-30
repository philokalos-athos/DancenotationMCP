"""Build the full 'Collapse of Symmetry' Labanotation score IR and render it."""

import json
from pathlib import Path

# We'll build the IR dict directly, then call generate_score via the MCP server

ir = {
    "metadata": {
        "title": "Collapse of Symmetry — Solo in Seven Fractures",
        "source_prompt": "Full proscenium solo, 7/8 time, ♩=144, atonal percussive score",
        "ir_version": "0.2.0",
        "schema_version": "0.2.0",
    },
    "symbols": [],
    "extensions": {
        "time_signatures": [
            {"measure": 1, "numerator": 7, "denominator": 8},
        ],
        "floor_plan": [],
    },
}

syms = ir["symbols"]
fp = ir["extensions"]["floor_plan"]


EIGHTH_NOTES_PER_QUARTER_BEAT = 2.0


def _count_beat(count: float) -> float:
    return min(1.0 + (count - 1.0) / EIGHTH_NOTES_PER_QUARTER_BEAT, 3.5)


def _count_duration(counts: float) -> float:
    return counts / EIGHTH_NOTES_PER_QUARTER_BEAT


def sym(sid, bp, d, lv, m, bt, dur, **kw):
    """Append a symbol authored in eighth-note counts to quarter-beat IR."""
    entry = {
        "symbol_id": sid,
        "body_part": bp,
        "direction": d,
        "level": lv,
        "timing": {
            "measure": m,
            "beat": _count_beat(bt),
            "duration_beats": _count_duration(dur),
        },
        "modifiers": kw.get("modifiers", {}),
        "rotation_degrees": kw.get("rotation_degrees"),
        "flexion_degrees": kw.get("flexion_degrees"),
        "stage_position": kw.get("stage_position"),
        "facing": kw.get("facing"),
        "retention": kw.get("retention"),
    }
    syms.append(entry)


def floor(m, bt, zone, facing, x=None, y=None, path="straight"):
    entry = {
        "performer_id": "dancer_1",
        "measure": m,
        "beat": _count_beat(bt),
        "position": {"zone": zone},
        "facing": facing,
        "path_to_next": path,
    }
    if x is not None:
        entry["position"]["x"] = x
    if y is not None:
        entry["position"]["y"] = y
    fp.append(entry)


# ── Tempo mark ────────────────────────────────────────────────────────
# music.tempo.mark, not timing.tempo: there is no timing.tempo in the catalog,
# and the validator rejects the score outright when the builder emits one.
sym("music.tempo.mark", "torso", None, None, 1, 1, 1,
    modifiers={"tempo": 144, "measure_header": True, "label": "♩=144"})

# ══════════════════════════════════════════════════════════════════════
# SECTION A — "Eruption" (Measures 1–16)
# ══════════════════════════════════════════════════════════════════════

# Floor plan: start upstage-right, facing stage-left
floor(1, 1, "upstage_right", "stage_left", x=0.8, y=0.2)

# ── Measure 1–2: Beat 1–3 — Grand plié in 2nd with torso contraction ──
# Left leg: plié (support, place, low — full weight, deep bend)
sym("support.step.forward", "left_leg", "place", "low", 1, 1, 3,
    modifiers={"label": "grand plié 2nd"})
# Right leg: plié (place, low)
sym("support.step.forward", "right_leg", "place", "low", 1, 1, 3)
# Torso: forward contraction to flat back
sym("direction.forward", "torso", "forward", "middle", 1, 1, 3,
    modifiers={"label": "flat-back table"})
# Arms: slash down then shoot to wide V overhead
sym("direction.forward", "left_arm", "forward", "low", 1, 1, 1.5,
    modifiers={"label": "slash down"})
sym("direction.forward", "right_arm", "forward", "low", 1, 1, 1.5)
sym("direction.forward", "left_arm", "diagonal_forward_left", "high", 1, 2.5, 1.5,
    modifiers={"label": "wide V overhead"})
sym("direction.forward", "right_arm", "diagonal_forward_right", "high", 1, 2.5, 1.5)
# Head: chin to chest
sym("direction.forward", "head", "forward", "low", 1, 1, 3)
# Effort: explosive
sym("effort.weight.strong", "whole_body", None, None, 1, 1, 3,
    modifiers={"effort_weight": "strong", "effort_time": "sudden"})

# ── Measure 1–2: Beat 4–5 — Spring to relevé, right leg à la seconde ──
sym("support.step.forward", "left_leg", "place", "high", 1, 4, 2,
    modifiers={"label": "relevé L foot"})
sym("direction.forward", "right_leg", "right", "middle", 1, 4, 2,
    modifiers={"label": "à la seconde 90°"})
# Torso: quarter turn right spiral
sym("direction.forward", "torso", "right", "middle", 1, 4, 2,
    rotation_degrees=90, modifiers={"label": "spiral upstage"})
# Arms: L crosses to R hip, R reaches high-right-forward diagonal
sym("direction.forward", "left_arm", "right", "low", 1, 4, 2,
    modifiers={"label": "cross to R hip"})
sym("direction.forward", "right_arm", "diagonal_forward_right", "high", 1, 4, 2)

# ── Measure 1–2: Beat 6–7 — Controlled sideways fall into lunge ──
sym("support.step.forward", "right_leg", "right", "low", 1, 6, 2,
    modifiers={"label": "deep lunge R"})
sym("support.step.forward", "left_leg", "backward", "low", 1, 6, 2,
    modifiers={"label": "extended behind"})
sym("direction.forward", "torso", "right", "middle", 1, 6, 2,
    modifiers={"label": "lateral arch over R"})
# Arms: windmill sagittal plane
sym("direction.forward", "left_arm", "forward", "middle", 1, 6, 2,
    modifiers={"label": "windmill finish: fwd-mid"})
sym("direction.forward", "right_arm", "backward", "low", 1, 6, 2,
    modifiers={"label": "windmill finish: bk-low"})
# Effort: sustained fall
sym("effort.time.sustained", "whole_body", None, None, 1, 6, 2,
    modifiers={"effort_weight": "strong", "effort_time": "sustained"})

# ── Measure 3–4: Chainé turns traveling downstage ──
floor(3, 1, "upstage_right", "downstage", path="straight")

# Turn 1: slow, arms first position
sym("support.step.forward", "right_leg", "forward", "high", 3, 1, 2.33,
    modifiers={"label": "chainé 1"})
sym("support.step.forward", "left_leg", "forward", "high", 3, 1, 2.33)
sym("direction.forward", "left_arm", "forward", "middle", 3, 1, 2.33,
    modifiers={"label": "1st position"})
sym("direction.forward", "right_arm", "forward", "middle", 3, 1, 2.33)
sym("turn.full", "torso", "right", "middle", 3, 1, 2.33,
    rotation_degrees=360)

# Turn 2: medium, arms demi-seconde
sym("support.step.forward", "right_leg", "forward", "high", 3, 3.33, 2.33)
sym("support.step.forward", "left_leg", "forward", "high", 3, 3.33, 2.33)
sym("direction.forward", "left_arm", "left", "middle", 3, 3.33, 2.33,
    modifiers={"label": "demi-seconde"})
sym("direction.forward", "right_arm", "right", "middle", 3, 3.33, 2.33)
sym("turn.full", "torso", "right", "middle", 3, 3.33, 2.33,
    rotation_degrees=360)

# Turn 3: fast, arms full second with flexed hands
sym("support.step.forward", "right_leg", "forward", "high", 3, 5.66, 2.34)
sym("support.step.forward", "left_leg", "forward", "high", 3, 5.66, 2.34)
sym("direction.forward", "left_arm", "left", "middle", 3, 5.66, 2.34,
    modifiers={"label": "full 2nd, flexed hands"})
sym("direction.forward", "right_arm", "right", "middle", 3, 5.66, 2.34)
sym("turn.full", "torso", "right", "middle", 3, 5.66, 2.34,
    rotation_degrees=360)

# ── Measure 4: Forced-arch fall, développé from kneeling ──
floor(4, 1, "center_right", "downstage", path="straight")

sym("direction.forward", "torso", "backward", "high", 4, 1, 3.5,
    modifiers={"label": "cambré derrière"})
sym("support.step.forward", "left_leg", "place", "high", 4, 1, 3.5,
    modifiers={"label": "relevé turned-out"})
# Beat 6-7: R knee to floor, L leg développé
sym("support.step.forward", "right_leg", "place", "low", 4, 4.5, 3.5,
    modifiers={"label": "R knee floor", "contact_type": "touch"})
sym("direction.forward", "left_leg", "left", "high", 4, 4.5, 3.5,
    modifiers={"label": "développé seconde 120°"})

# ── Measures 5–8: Floor sequence, stage-right to center ──
floor(5, 1, "center_right", "stage_left", path="curved")
floor(7, 1, "center", "downstage")

# M5: Body roll from kneel
sym("support.step.forward", "right_leg", "place", "low", 5, 1, 3.5,
    modifiers={"label": "kneel R", "contact_type": "touch"})
sym("direction.forward", "torso", "forward", "low", 5, 1, 3.5,
    modifiers={"label": "body roll fwd"})
sym("direction.forward", "left_arm", "forward", "low", 5, 1, 3.5)
sym("direction.forward", "right_arm", "forward", "low", 5, 1, 3.5)
# Sequential successive movement through spine
sym("sequential.successive.upward", "torso", None, None, 5, 1, 3.5,
    modifiers={"wave_direction": "upward", "sequential_type": "successive"})

# M5 beat 4.5-7: Transition to supine
sym("support.step.forward", "torso", "backward", "low", 5, 4.5, 3.5,
    modifiers={"label": "roll supine", "contact_type": "touch"})
sym("direction.forward", "left_leg", "forward", "high", 5, 4.5, 3.5,
    modifiers={"label": "legs overhead"})
sym("direction.forward", "right_leg", "forward", "high", 5, 4.5, 3.5)

# M6: Shoulder roll to standing
sym("support.step.forward", "left_leg", "place", "low", 6, 1, 3.5,
    modifiers={"label": "shoulder roll", "contact_type": "touch"})
sym("direction.forward", "torso", "backward", "low", 6, 1, 3.5,
    modifiers={"label": "roll through shoulders"})
sym("support.step.forward", "right_leg", "forward", "middle", 6, 4.5, 3.5,
    modifiers={"label": "push to stand"})
sym("support.step.forward", "left_leg", "forward", "middle", 6, 4.5, 3.5)
# Effort: gliding
sym("effort.space.direct", "whole_body", None, None, 6, 1, 7,
    modifiers={"effort_weight": "light", "effort_space": "direct"})

# M7-8: Sweeping arc gesture traveling to center
sym("support.step.forward", "right_leg", "forward", "middle", 7, 1, 3.5)
sym("support.step.forward", "left_leg", "forward", "middle", 7, 1, 3.5)
sym("direction.forward", "left_arm", "left", "high", 7, 1, 3.5,
    modifiers={"label": "sweeping arc L"})
sym("direction.forward", "right_arm", "right", "high", 7, 1, 3.5,
    modifiers={"label": "sweeping arc R"})
sym("direction.forward", "torso", "forward", "middle", 7, 1, 3.5)
# Traveling
sym("support.step.forward", "right_leg", "forward", "middle", 7, 4.5, 3.5)
sym("support.step.forward", "left_leg", "forward", "middle", 7, 4.5, 3.5)
sym("direction.forward", "left_arm", "diagonal_forward_left", "high", 7, 4.5, 3.5)
sym("direction.forward", "right_arm", "diagonal_forward_right", "high", 7, 4.5, 3.5)

# M8: Continue travel with increasing amplitude
sym("support.step.forward", "right_leg", "right", "middle", 8, 1, 3.5,
    modifiers={"label": "wide steps"})
sym("support.step.forward", "left_leg", "left", "middle", 8, 1, 3.5)
sym("direction.forward", "left_arm", "left", "high", 8, 1, 7,
    modifiers={"label": "full reach"})
sym("direction.forward", "right_arm", "right", "high", 8, 1, 7)

# ── Measures 9–12: Section A continued — angular phrase ──
floor(9, 1, "center", "stage_left", path="zigzag")

# M9: Sharp directional changes (angular, percussive)
sym("support.step.forward", "right_leg", "forward", "middle", 9, 1, 2,
    modifiers={"label": "sharp step fwd"})
sym("support.step.forward", "left_leg", "left", "middle", 9, 3, 2,
    modifiers={"label": "sharp step L"})
sym("support.step.forward", "right_leg", "backward", "middle", 9, 5, 3,
    modifiers={"label": "sharp step bk"})
sym("direction.forward", "left_arm", "forward", "high", 9, 1, 2)
sym("direction.forward", "right_arm", "right", "high", 9, 3, 2)
sym("direction.forward", "left_arm", "backward", "low", 9, 5, 3)
sym("effort.weight.strong", "whole_body", None, None, 9, 1, 7,
    modifiers={"effort_weight": "strong", "effort_time": "sudden"})

# M10: Suspension and fall
sym("support.step.forward", "left_leg", "place", "high", 10, 1, 3.5,
    modifiers={"label": "balance relevé"})
sym("direction.forward", "right_leg", "forward", "high", 10, 1, 3.5,
    modifiers={"label": "développé devant"})
sym("direction.forward", "left_arm", "left", "high", 10, 1, 3.5)
sym("direction.forward", "right_arm", "right", "high", 10, 1, 3.5)
# Hold
sym("retention.hold.arm", "left_arm", None, None, 10, 4, 1, retention="hold")
sym("retention.hold.arm", "right_arm", None, None, 10, 4, 1, retention="hold")
# Fall
sym("support.step.forward", "right_leg", "forward", "low", 10, 4.5, 3.5,
    modifiers={"label": "controlled fall"})
sym("effort.time.sustained", "whole_body", None, None, 10, 4.5, 3.5,
    modifiers={"effort_weight": "strong", "effort_time": "sustained"})

# M11-12: Recovery and spiral turn
sym("support.step.forward", "left_leg", "forward", "middle", 11, 1, 3.5)
sym("support.step.forward", "right_leg", "forward", "middle", 11, 1, 3.5)
sym("direction.forward", "torso", "right", "middle", 11, 1, 7,
    rotation_degrees=180, modifiers={"label": "spiral recovery"})
sym("direction.forward", "left_arm", "diagonal_forward_left", "middle", 11, 1, 3.5)
sym("direction.forward", "right_arm", "diagonal_forward_right", "middle", 11, 1, 3.5)
sym("turn.full", "torso", "right", "middle", 11, 4.5, 3.5,
    rotation_degrees=360, modifiers={"label": "pirouette en dehors"})
sym("support.step.forward", "left_leg", "place", "high", 11, 4.5, 3.5,
    modifiers={"label": "passé relevé"})

# M12: Landing and transition
sym("support.step.forward", "right_leg", "forward", "low", 12, 1, 3.5,
    modifiers={"label": "plié landing"})
sym("support.step.forward", "left_leg", "forward", "low", 12, 1, 3.5)
sym("direction.forward", "left_arm", "forward", "middle", 12, 1, 3.5)
sym("direction.forward", "right_arm", "forward", "middle", 12, 1, 3.5)
# Transition walking DSL
floor(12, 1, "center_left", "downstage", path="straight")
sym("support.step.forward", "left_leg", "diagonal_forward_left", "middle", 12, 4.5, 3.5)
sym("support.step.forward", "right_leg", "diagonal_forward_left", "middle", 12, 4.5, 3.5)

# ── Measures 13–16: Diagonal phrase USR to DSL ──
floor(13, 1, "downstage_left", "diagonal_upstage_right", path="straight")

# M13: Jump sequence — small jumps along diagonal
sym("jump.assemble", "left_leg", "diagonal_forward_left", "middle", 13, 1, 2,
    modifiers={"label": "assemblé"})
sym("jump.small", "right_leg", "diagonal_forward_left", "middle", 13, 3, 2,
    modifiers={"label": "jeté"})
sym("jump.large", "left_leg", "diagonal_forward_left", "high", 13, 5, 3,
    modifiers={"label": "grand jeté", "spring_jump": {"takeoff": ["left"], "landing": ["right"]}})

# M14: Aerial turn
sym("support.step.forward", "left_leg", "place", "high", 14, 1, 2,
    modifiers={"label": "take-off"})
sym("jump.large", "right_leg", "forward", "high", 14, 3, 3,
    modifiers={"label": "tour en l'air", "spring_jump": {"takeoff": ["left", "right"], "landing": ["left", "right"]}})
sym("turn.full", "torso", "right", "high", 14, 3, 3,
    rotation_degrees=720, modifiers={"label": "double tour"})
sym("support.step.forward", "right_leg", "place", "low", 14, 6, 2,
    modifiers={"label": "plié landing"})
sym("support.step.forward", "left_leg", "place", "low", 14, 6, 2)

# M15: Sequential floor descent
sym("support.step.forward", "right_leg", "place", "low", 15, 1, 7,
    modifiers={"label": "kneel descent", "contact_type": "touch"})
sym("direction.forward", "torso", "forward", "low", 15, 1, 3.5,
    modifiers={"label": "torso folds"})
sym("sequential.successive.downward", "torso", None, None, 15, 1, 7,
    modifiers={"wave_direction": "downward", "sequential_type": "successive"})
sym("direction.forward", "left_arm", "forward", "low", 15, 1, 7,
    modifiers={"label": "arms fold"})
sym("direction.forward", "right_arm", "forward", "low", 15, 1, 7)

# M16: Stillness (arrival at DSL corner)
floor(16, 1, "downstage_left", "stage_right")
sym("support.step.forward", "left_leg", "place", "low", 16, 1, 7,
    modifiers={"label": "seated floor", "contact_type": "touch"})
sym("support.step.forward", "right_leg", "place", "low", 16, 1, 7,
    modifiers={"contact_type": "touch"})
sym("direction.forward", "torso", "forward", "low", 16, 1, 7,
    modifiers={"label": "curled"})
sym("retention.hold.arm", "left_arm", None, None, 16, 1, 7, retention="hold")
sym("retention.hold.arm", "right_arm", None, None, 16, 1, 7, retention="hold")

# ══════════════════════════════════════════════════════════════════════
# SECTION B — "Tessellation" (Measures 17–24, Figure-8 path)
# ══════════════════════════════════════════════════════════════════════

floor(17, 1, "downstage_left", "upstage", path="curved")
floor(19, 1, "center", "stage_right", path="curved")
floor(21, 1, "downstage_right", "upstage", path="curved")
floor(23, 1, "center", "stage_left", path="curved")

# M17-18: Rising from floor, initial figure-8 loop
sym("support.step.forward", "right_leg", "forward", "middle", 17, 1, 3.5,
    modifiers={"label": "push up from floor"})
sym("support.step.forward", "left_leg", "forward", "middle", 17, 4.5, 3.5)
sym("direction.forward", "torso", "forward", "middle", 17, 1, 7,
    modifiers={"label": "unfurl spine"})
sym("sequential.successive.upward", "torso", None, None, 17, 1, 7,
    modifiers={"wave_direction": "upward"})
sym("direction.forward", "left_arm", "left", "middle", 17, 1, 7,
    modifiers={"label": "opens L"})
sym("direction.forward", "right_arm", "right", "middle", 17, 1, 7,
    modifiers={"label": "opens R"})

# M18: Traveling waltz-step pattern on figure-8
sym("support.step.forward", "right_leg", "diagonal_forward_right", "middle", 18, 1, 2.33)
sym("support.step.forward", "left_leg", "forward", "middle", 18, 3.33, 2.33)
sym("support.step.forward", "right_leg", "forward", "middle", 18, 5.66, 2.34)
sym("direction.forward", "left_arm", "diagonal_forward_left", "high", 18, 1, 7)
sym("direction.forward", "right_arm", "diagonal_forward_right", "high", 18, 1, 7)
sym("turn.full", "torso", "right", "middle", 18, 1, 7,
    rotation_degrees=180, modifiers={"label": "traveling turn"})

# M19-20: Center crossing of figure-8
sym("support.step.forward", "left_leg", "forward", "middle", 19, 1, 3.5)
sym("support.step.forward", "right_leg", "forward", "middle", 19, 4.5, 3.5)
sym("direction.forward", "torso", "left", "middle", 19, 1, 3.5,
    rotation_degrees=90)
sym("direction.forward", "left_arm", "left", "high", 19, 1, 7)
sym("direction.forward", "right_arm", "left", "middle", 19, 1, 7)
sym("effort.space.direct", "whole_body", None, None, 19, 1, 7,
    modifiers={"effort_space": "indirect", "effort_flow": "free"})

# M20: Continue figure-8
sym("support.step.forward", "left_leg", "diagonal_forward_left", "middle", 20, 1, 3.5)
sym("support.step.forward", "right_leg", "forward", "middle", 20, 4.5, 3.5)
sym("direction.forward", "left_arm", "diagonal_forward_left", "high", 20, 1, 7)
sym("direction.forward", "right_arm", "diagonal_forward_right", "high", 20, 1, 7)
sym("turn.full", "torso", "left", "middle", 20, 1, 7,
    rotation_degrees=180)

# M21-22: Second loop of figure-8 (DSR area)
sym("support.step.forward", "right_leg", "right", "middle", 21, 1, 3.5)
sym("support.step.forward", "left_leg", "right", "middle", 21, 4.5, 3.5)
sym("direction.forward", "left_arm", "right", "high", 21, 1, 7,
    modifiers={"label": "port de bras R"})
sym("direction.forward", "right_arm", "right", "high", 21, 1, 7)
sym("direction.forward", "torso", "right", "middle", 21, 1, 7)

sym("support.step.forward", "left_leg", "diagonal_backward_left", "middle", 22, 1, 3.5)
sym("support.step.forward", "right_leg", "backward", "middle", 22, 4.5, 3.5)
sym("direction.forward", "left_arm", "backward", "middle", 22, 1, 7,
    modifiers={"label": "reach behind"})
sym("direction.forward", "right_arm", "backward", "middle", 22, 1, 7)
sym("turn.full", "torso", "left", "middle", 22, 1, 7,
    rotation_degrees=360, modifiers={"label": "manège turn"})

# M23-24: Return to center, complete figure-8
sym("support.step.forward", "left_leg", "forward", "middle", 23, 1, 3.5)
sym("support.step.forward", "right_leg", "forward", "middle", 23, 4.5, 3.5)
sym("direction.forward", "left_arm", "forward", "high", 23, 1, 7)
sym("direction.forward", "right_arm", "forward", "high", 23, 1, 7)
sym("direction.forward", "torso", "forward", "high", 23, 1, 7,
    modifiers={"label": "full extension"})

# M24: Arrive center, hold
floor(24, 1, "center", "downstage")
sym("support.step.forward", "left_leg", "place", "middle", 24, 1, 7,
    modifiers={"label": "5th position"})
sym("support.step.forward", "right_leg", "place", "middle", 24, 1, 7)
sym("direction.forward", "left_arm", "left", "high", 24, 1, 3.5,
    modifiers={"label": "2nd position"})
sym("direction.forward", "right_arm", "right", "high", 24, 1, 3.5)
sym("retention.hold.leg", "left_leg", None, None, 24, 4.5, 3.5, retention="hold")
sym("retention.hold.leg", "right_leg", None, None, 24, 4.5, 3.5, retention="hold")

# ══════════════════════════════════════════════════════════════════════
# SECTION C — "Dissolution" (Measures 25–32, Final)
# ══════════════════════════════════════════════════════════════════════

floor(25, 1, "center", "downstage")

# M25-26: Controlled off-balance tilt sequence
sym("support.step.forward", "left_leg", "place", "high", 25, 1, 3.5,
    modifiers={"label": "5th relevé"})
sym("support.step.forward", "right_leg", "place", "high", 25, 1, 3.5)
sym("direction.forward", "left_arm", "forward", "high", 25, 1, 7,
    modifiers={"label": "high-5th"})
sym("direction.forward", "right_arm", "forward", "high", 25, 1, 7)
# Tilt forward — progressive fall
sym("direction.forward", "torso", "forward", "high", 25, 1, 2,
    modifiers={"label": "tilt 30°"})
sym("support.step.forward", "right_leg", "forward", "middle", 25, 3, 2,
    modifiers={"label": "catch step R"})
sym("direction.forward", "torso", "forward", "middle", 25, 3, 2,
    modifiers={"label": "tilt 45°"})
sym("support.step.forward", "left_leg", "forward", "middle", 25, 5, 3,
    modifiers={"label": "catch step L"})
sym("direction.forward", "torso", "forward", "low", 25, 5, 3,
    modifiers={"label": "tilt 60° → fall"})

# M26: Hands catch floor, body wave
sym("support.step.forward", "left_arm", "forward", "low", 26, 1, 2,
    modifiers={"label": "hands to floor", "contact_type": "touch"})
sym("support.step.forward", "right_arm", "forward", "low", 26, 1, 2,
    modifiers={"contact_type": "touch"})
sym("sequential.successive.downward", "torso", None, None, 26, 1, 7,
    modifiers={"wave_direction": "downward", "label": "body wave: plank→cobra→stand"})
sym("direction.forward", "torso", "forward", "low", 26, 1, 2,
    modifiers={"label": "plank"})
sym("direction.forward", "torso", "backward", "low", 26, 3, 2,
    modifiers={"label": "cobra arch"})
sym("direction.forward", "torso", "forward", "middle", 26, 5, 3,
    modifiers={"label": "push to stand"})
sym("effort.weight.strong", "whole_body", None, None, 26, 1, 7,
    modifiers={"effort_weight": "strong", "effort_flow": "bound"})

# M27-28: Manège circle
floor(27, 1, "center", "stage_right", path="curved")
floor(28, 1, "center", "stage_left", path="curved")

# M27: Manège piqué turns
sym("support.step.forward", "right_leg", "forward", "high", 27, 1, 2.33,
    modifiers={"label": "piqué turn 1"})
sym("turn.full", "torso", "right", "high", 27, 1, 2.33,
    rotation_degrees=360)
sym("support.step.forward", "left_leg", "forward", "high", 27, 3.33, 2.33,
    modifiers={"label": "piqué turn 2"})
sym("turn.full", "torso", "right", "high", 27, 3.33, 2.33,
    rotation_degrees=360)
sym("support.step.forward", "right_leg", "forward", "high", 27, 5.66, 2.34,
    modifiers={"label": "piqué turn 3"})
sym("turn.full", "torso", "right", "high", 27, 5.66, 2.34,
    rotation_degrees=360)
sym("direction.forward", "left_arm", "left", "middle", 27, 1, 7,
    modifiers={"label": "2nd position"})
sym("direction.forward", "right_arm", "right", "middle", 27, 1, 7)

# M28: Continue manège
sym("support.step.forward", "left_leg", "forward", "high", 28, 1, 2.33)
sym("turn.full", "torso", "right", "high", 28, 1, 2.33,
    rotation_degrees=360)
sym("support.step.forward", "right_leg", "forward", "high", 28, 3.33, 2.33)
sym("turn.full", "torso", "right", "high", 28, 3.33, 2.33,
    rotation_degrees=360)
sym("support.step.forward", "left_leg", "forward", "high", 28, 5.66, 2.34,
    modifiers={"label": "final turn"})
sym("turn.full", "torso", "right", "high", 28, 5.66, 2.34,
    rotation_degrees=360)
sym("direction.forward", "left_arm", "left", "high", 28, 1, 7)
sym("direction.forward", "right_arm", "right", "high", 28, 1, 7)

# M29-30: Deceleration, arrive center
floor(29, 1, "center", "downstage")
sym("support.step.forward", "right_leg", "forward", "middle", 29, 1, 3.5,
    modifiers={"label": "decel step"})
sym("support.step.forward", "left_leg", "forward", "middle", 29, 4.5, 3.5)
sym("direction.forward", "left_arm", "left", "middle", 29, 1, 7,
    modifiers={"label": "lowering to side"})
sym("direction.forward", "right_arm", "right", "middle", 29, 1, 3.5,
    modifiers={"label": "lowering"})
sym("direction.forward", "right_arm", "place", "low", 29, 4.5, 3.5,
    modifiers={"label": "hangs at side"})
sym("effort.time.sustained", "whole_body", None, None, 29, 1, 7,
    modifiers={"effort_time": "sustained", "effort_flow": "free"})

# M30: Settle into final position
sym("support.step.forward", "left_leg", "place", "middle", 30, 1, 7,
    modifiers={"label": "forced arch"})
sym("support.step.forward", "right_leg", "place", "middle", 30, 1, 7,
    modifiers={"label": "forced arch"})
sym("direction.forward", "torso", "diagonal_forward_right", "middle", 30, 1, 7,
    modifiers={"label": "slight spiral: R shoulder fwd"})
sym("direction.forward", "head", "right", "middle", 30, 1, 7,
    modifiers={"label": "tilted right"})

# M31: Final image — static pose
sym("support.step.forward", "left_leg", "place", "middle", 31, 1, 7,
    modifiers={"label": "forced arch stance"})
sym("support.step.forward", "right_leg", "place", "middle", 31, 1, 7)
sym("direction.forward", "left_arm", "diagonal_forward_left", "middle", 31, 1, 7,
    modifiers={"label": "extended 45° above horiz, palm up"})
sym("direction.forward", "right_arm", "place", "low", 31, 1, 7,
    modifiers={"label": "hangs, fingers brush thigh"})
sym("direction.forward", "torso", "diagonal_forward_right", "middle", 31, 1, 7,
    modifiers={"label": "spiral posture"})
sym("direction.forward", "head", "diagonal_backward_left", "middle", 31, 1, 7,
    modifiers={"label": "gaze USL corner"})
# Hold all
sym("retention.hold.arm", "left_arm", None, None, 31, 1, 4, retention="hold")
sym("retention.hold.arm", "right_arm", None, None, 31, 1, 4, retention="hold")
sym("retention.hold.leg", "left_leg", None, None, 31, 1, 4, retention="hold")
sym("retention.hold.leg", "right_leg", None, None, 31, 1, 4, retention="hold")

# M32: Closing gestures — fist close, hand open, blackout
sym("support.step.forward", "left_leg", "place", "middle", 32, 1, 7,
    modifiers={"label": "hold stance"})
sym("support.step.forward", "right_leg", "place", "middle", 32, 1, 7)
sym("direction.forward", "left_arm", "diagonal_forward_left", "middle", 32, 1, 4,
    modifiers={"label": "hold"})
sym("direction.forward", "right_arm", "place", "low", 32, 1, 4)
# Beat 5: L hand closes to fist
sym("contact.touch", "left_hand", None, None, 32, 5, 1,
    modifiers={"contact_type": "grasp", "label": "fist close"})
# Beat 6: R hand opens, fingers spread
sym("direction.forward", "right_hand", "place", "low", 32, 6, 1,
    modifiers={"label": "fingers spread"})
# Beat 7: blackout.
#
# Left out, not re-signed. A blackout is a production cue, not a movement, and
# the catalog has no id that carries a written cue -- there is no text or
# annotation family, and music.* is tempo, time signatures, rests and cadence
# marks only. It was written as timing.tempo, which does not exist and which
# the validator rejects; putting it on some other real id would say something
# the notation does not mean. The gap is recorded rather than papered over.

# ── Repeat markers (section boundaries) ──
sym("repeat.start", "whole_body", None, None, 1, 1, 1,
    modifiers={"label": "Section A: Eruption"})
sym("repeat.end", "whole_body", None, None, 16, 7, 1)
sym("repeat.start", "whole_body", None, None, 17, 1, 1,
    modifiers={"label": "Section B: Tessellation"})
sym("repeat.end", "whole_body", None, None, 24, 7, 1)
sym("repeat.start", "whole_body", None, None, 25, 1, 1,
    modifiers={"label": "Section C: Dissolution"})
sym("repeat.end", "whole_body", None, None, 32, 7, 1)

# ── Write output ──────────────────────────────────────────────────────
out_path = Path(__file__).parent / "collapse_of_symmetry_full.ir.json"
out_path.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"IR written: {out_path}")
print(f"Total symbols: {len(syms)}")
print(f"Floor plan entries: {len(fp)}")
