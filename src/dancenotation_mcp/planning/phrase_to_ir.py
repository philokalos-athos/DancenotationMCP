from __future__ import annotations

from dancenotation_mcp.ir.catalog import load_symbol_catalog
from dancenotation_mcp.ir.models import Score, ScoreMetadata, SymbolInstance, Timing

PRIMARY_MOTION_COLUMNS = {"support", "direction", "path", "gesture", "body", "flexion", "foothook", "digit", "turn", "travel", "jump", "floor"}
AUTO_ATTACH_COLUMNS = {"pin", "surface", "quality", "level", "timing"}


def _behavior(spec: dict) -> dict:
    return spec.get("behavior", {}) or {}


def _is_repeat_opening(spec: dict, symbol_id: str) -> bool:
    return _behavior(spec).get("boundary_role") == "opening" or symbol_id == "repeat.start"


def _is_repeat_closing(spec: dict, symbol_id: str) -> bool:
    return _behavior(spec).get("boundary_role") == "closing" or symbol_id in {"repeat.end", "repeat.double"}


def _resolve_symbol_id(symbol_id: str, direction: str | None, catalog: dict[str, dict]) -> str:
    """Expand a bare action hint to its directional catalog entry when the
    bare form doesn't exist on its own.

    phrase_parser.py is intentionally catalog-agnostic (pure NLP parsing),
    so its ACTION_PATTERNS table maps phrases like "plie"/"releve"/"stamp"/
    "heel"/"toe" to a bare base like "support.plie". Some families (e.g.
    support.step, support.lower) do have a standalone non-directional
    catalog entry, so the bare form is already valid. Others (support.plie,
    support.releve, support.stamp, support.heel, support.toe) only exist as
    "support.{type}.{direction}" — every one of their variants requires a
    direction — so the bare form fails validation with "Unknown symbol id"
    entirely. Expanding here (once we know the resolved direction) fixes it
    generally, for this and any future family with the same shape, rather
    than hardcoding a one-off list of affected action words.
    """
    if symbol_id in catalog:
        return symbol_id
    expanded = f"{symbol_id}.{direction or 'place'}"
    if expanded in catalog:
        return expanded
    return symbol_id


def phrase_plan_to_ir(phrase_plan: dict, source_prompt: str = "") -> dict:
    catalog = load_symbol_catalog()
    symbols: list[SymbolInstance] = []
    for step in phrase_plan.get("steps", []):
        t = step["timing"]
        modifiers = dict(step.get("modifiers", {}))
        modifiers["source_text"] = step.get("source_text", "")
        direction = step.get("direction")
        symbols.append(
            SymbolInstance(
                symbol_id=_resolve_symbol_id(step["symbol_id"], direction, catalog),
                body_part=step["body_part"],
                direction=direction,
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
        spec = catalog.get(symbol.symbol_id, {})
        if not _is_repeat_opening(spec, symbol.symbol_id):
            continue
        if symbol.modifiers.get("repeat_span_to"):
            continue
        for candidate in symbols[idx + 1 :]:
            candidate_spec = catalog.get(candidate.symbol_id, {})
            if _is_repeat_closing(candidate_spec, candidate.symbol_id):
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
