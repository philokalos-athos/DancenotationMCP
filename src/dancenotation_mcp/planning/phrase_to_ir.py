from __future__ import annotations

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.models import Score, ScoreMetadata, SymbolInstance, Timing

PRIMARY_MOTION_COLUMNS = {"support", "direction", "path", "gesture", "body", "flexion", "foothook", "digit", "turn", "travel", "jump", "floor"}
AUTO_ATTACH_COLUMNS = {"pin", "surface", "quality", "level", "timing"}


def phrase_plan_to_ir(phrase_plan: dict, source_prompt: str = "") -> dict:
    catalog = load_symbol_catalog()
    symbols: list[SymbolInstance] = []
    for step in phrase_plan.get("steps", []):
        t = step["timing"]
        modifiers = dict(step.get("modifiers", {}))
        modifiers["source_text"] = step.get("source_text", "")
        symbols.append(
            SymbolInstance(
                symbol_id=step["symbol_id"],
                body_part=step["body_part"],
                direction=step.get("direction"),
                level=step.get("level"),
                timing=Timing(
                    measure=t["measure"],
                    beat=float(t["beat"]),
                    duration_beats=float(t["duration_beats"]),
                ),
                modifiers=modifiers,
            )
        )
    for idx, symbol in enumerate(symbols):
        if symbol.symbol_id != "repeat.start":
            continue
        if symbol.modifiers.get("repeat_span_to"):
            continue
        for candidate in symbols[idx + 1 :]:
            if candidate.symbol_id in {"repeat.end", "repeat.double"}:
                symbol.modifiers["repeat_span_to"] = candidate.symbol_id
                break
    for idx, symbol in enumerate(symbols):
        spec = catalog.get(symbol.symbol_id, {})
        column = spec.get("geometry", {}).get("staff_column")
        if column not in AUTO_ATTACH_COLUMNS:
            continue
        if symbol.modifiers.get("measure_header") or symbol.modifiers.get("attach_to"):
            continue
        candidates: list[tuple[int, int, int, float, float, str]] = []
        for candidate in symbols[:idx]:
            candidate_spec = catalog.get(candidate.symbol_id, {})
            candidate_column = candidate_spec.get("geometry", {}).get("staff_column")
            if candidate_column not in PRIMARY_MOTION_COLUMNS:
                continue
            if candidate.timing.measure != symbol.timing.measure:
                continue
            if candidate.timing.beat > symbol.timing.beat:
                continue
            ends_at = candidate.timing.beat + max(candidate.timing.duration_beats, 0.0)
            same_body = 0 if candidate.body_part == symbol.body_part else 1
            coverage_penalty = 0 if ends_at + 0.01 >= symbol.timing.beat else 1
            primary_family = 0 if candidate.symbol_id.startswith(("support.", "direction.", "path.", "body.", "gesture.", "turn.", "jump.")) else 1
            beat_distance = abs(symbol.timing.beat - candidate.timing.beat)
            candidates.append((coverage_penalty, same_body, primary_family, beat_distance, -candidate.timing.beat, candidate.symbol_id))
        if candidates:
            _, _, _, _, _, target_id = min(candidates)
            symbol.modifiers["attach_to"] = target_id
    score = Score(metadata=ScoreMetadata(source_prompt=source_prompt), symbols=symbols)
    return score.to_dict()
