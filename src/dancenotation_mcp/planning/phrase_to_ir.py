from __future__ import annotations

from dancenotation_mcp.ir.models import Score, ScoreMetadata, SymbolInstance, Timing


def phrase_plan_to_ir(phrase_plan: dict, source_prompt: str = "") -> dict:
    symbols: list[SymbolInstance] = []
    for step in phrase_plan.get("steps", []):
        t = step["timing"]
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
                modifiers={"source_text": step.get("source_text", "")},
            )
        )
    score = Score(metadata=ScoreMetadata(source_prompt=source_prompt), symbols=symbols)
    return score.to_dict()
