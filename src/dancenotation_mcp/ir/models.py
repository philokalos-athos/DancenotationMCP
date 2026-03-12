from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Timing:
    measure: int
    beat: float
    duration_beats: float


@dataclass
class SymbolInstance:
    symbol_id: str
    body_part: str
    direction: str | None = None
    level: str | None = None
    timing: Timing = field(default_factory=lambda: Timing(1, 1.0, 1.0))
    modifiers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoreMetadata:
    title: str = "Untitled"
    source_prompt: str = ""
    ir_version: str = "0.1.0"
    schema_version: str = "0.1.0"


@dataclass
class Score:
    metadata: ScoreMetadata
    symbols: list[SymbolInstance]
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_score(data: dict[str, Any]) -> Score:
    metadata = ScoreMetadata(**data.get("metadata", {}))
    symbols: list[SymbolInstance] = []
    for raw in data.get("symbols", []):
        timing = Timing(**raw["timing"])
        symbols.append(
            SymbolInstance(
                symbol_id=raw["symbol_id"],
                body_part=raw["body_part"],
                direction=raw.get("direction"),
                level=raw.get("level"),
                timing=timing,
                modifiers=raw.get("modifiers", {}),
            )
        )
    return Score(metadata=metadata, symbols=symbols, extensions=data.get("extensions", {}))
