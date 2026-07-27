from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ── Valid body parts ─────────────────────────────────────────────────

BODY_PARTS = [
    # Original 6
    "left_arm", "right_arm", "left_leg", "right_leg", "torso", "head",
    # Upper limb segments
    "left_upper_arm", "right_upper_arm", "left_lower_arm", "right_lower_arm",
    "left_hand", "right_hand",
    # Lower limb segments
    "left_upper_leg", "right_upper_leg", "left_lower_leg", "right_lower_leg",
    "left_foot", "right_foot",
    # Joints
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
    # Spine segments
    "upper_spine", "lower_spine", "neck",
    # Digits
    "left_fingers", "right_fingers", "left_toes", "right_toes",
    # Whole body / pelvis
    "pelvis", "whole_body",
]

# ── Stage zones ──────────────────────────────────────────────────────

# ── Valid directions ─────────────────────────────────────────────────

DIRECTIONS = [
    "place",
    "forward", "backward", "left", "right",
    "diagonal_forward_right", "diagonal_forward_left",
    "diagonal_backward_right", "diagonal_backward_left",
]

LEVELS = ["high", "middle", "low"]

_DIRECTION_TOKENS = frozenset(DIRECTIONS)
_LEVEL_TOKENS = frozenset(LEVELS)


def direction_and_level_from_id(symbol_id: str) -> tuple[str | None, str | None]:
    """Return the (direction, level) a dotted symbol id names, if any.

    564 of the 906 catalog ids encode a direction and 408 a level
    (``support.step.backward``, ``gesture.arm.forward.high``), and the
    list_symbols → insert_symbol workflow hands those ids straight into a
    score. Consumers that read only ``symbol["direction"]`` therefore saw
    nothing and fell back to ``place`` — a score saying "step backward"
    engraved as "step in place", silently.

    Only whole dot-separated segments count, so ``floor.facing.stage_left``
    and ``body.left_shoulder`` are not mistaken for a ``left`` direction.
    """
    direction = level = None
    for token in symbol_id.split("."):
        if direction is None and token in _DIRECTION_TOKENS:
            direction = token
        elif level is None and token in _LEVEL_TOKENS:
            level = token
    return direction, level


def resolve_direction_and_level(symbol: dict) -> tuple[str | None, str | None]:
    """(direction, level) for a raw IR symbol, filling gaps from its id.

    Explicit IR fields always win; the id is only consulted for what the
    symbol does not state.
    """
    direction = symbol.get("direction")
    level = symbol.get("level")
    if direction and level:
        return direction, level
    implied_direction, implied_level = direction_and_level_from_id(
        symbol.get("symbol_id", ""))
    return direction or implied_direction, level or implied_level

# ── Stage zones ──────────────────────────────────────────────────────

STAGE_ZONES = [
    "downstage_left", "downstage_center", "downstage_right",
    "center_left", "center", "center_right",
    "upstage_left", "upstage_center", "upstage_right",
    # Wing columns, per the LabanWriter manual: "Wing columns can also be
    # added to the floorplan to allow you to place pins outside the
    # floorplan(s)" — for dancers waiting offstage, not yet visible.
    "wing_left", "wing_right",
]

STAGE_FACINGS = [
    "downstage", "upstage", "stage_left", "stage_right",
    "diagonal_downstage_left", "diagonal_downstage_right",
    "diagonal_upstage_left", "diagonal_upstage_right",
]

# Floor-plan pin head shape, per the LabanWriter manual: "Replace arrowheads
# in floorplans with female pin (white) is the default. Select male pin
# (black) if most of the dancers are men or neuter pin (tack) if the dancers
# can be either male or female."
PIN_SEXES = ["male", "female", "neuter"]


# ── Data models ──────────────────────────────────────────────────────

@dataclass
class Timing:
    measure: int
    beat: float
    duration_beats: float


@dataclass
class StagePosition:
    zone: str  # one of STAGE_ZONES
    x: float | None = None  # normalized 0.0-1.0 within zone
    y: float | None = None  # normalized 0.0-1.0 within zone


@dataclass
class FloorPlanEntry:
    performer_id: str
    measure: int
    beat: float
    position: StagePosition
    facing: str | None = None  # one of STAGE_FACINGS
    path_to_next: str | None = None  # "straight", "curved", "spiral", "zigzag"


@dataclass
class TimeSignatureChange:
    measure: int
    numerator: int  # e.g. 7 for 7/8
    denominator: int  # e.g. 8 for 7/8


@dataclass
class EffortGraph:
    weight: str | None = None  # "strong" | "light"
    time: str | None = None    # "sudden" | "sustained"
    space: str | None = None   # "direct" | "indirect"
    flow: str | None = None    # "bound" | "free"


@dataclass
class SymbolInstance:
    symbol_id: str
    body_part: str
    direction: str | None = None
    level: str | None = None
    timing: Timing = field(default_factory=lambda: Timing(1, 1.0, 1.0))
    modifiers: dict[str, Any] = field(default_factory=dict)
    # Extended fields for LabanWriter parity
    rotation_degrees: float | None = None
    flexion_degrees: float | None = None
    stage_position: StagePosition | None = None
    facing: str | None = None
    retention: str | None = None  # "hold" | "release" | "cancel"
    effort_graph: EffortGraph | None = None
    cancellation_mode: str | None = None  # "return_to_natural" | "hold" | "explicit_cancel"


@dataclass
class RelationshipBow:
    source_symbol_index: int
    target_symbol_index: int
    bow_type: str  # "touch" | "near" | "grasp" | "support_on"
    side: str = "right"  # which side of staff to draw


@dataclass
class Section:
    name: str
    start_measure: int
    end_measure: int


@dataclass
class ScoreMetadata:
    title: str = "Untitled"
    source_prompt: str = ""
    ir_version: str = "0.2.0"
    schema_version: str = "0.2.0"
    choreographer: str = ""
    notator: str = ""
    notation_date: str = ""
    company: str = ""
    music_title: str = ""
    music_composer: str = ""
    copyright: str = ""


@dataclass
class Score:
    metadata: ScoreMetadata
    symbols: list[SymbolInstance]
    sections: list[Section] = field(default_factory=list)
    relationship_bows: list[RelationshipBow] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_score(data: dict[str, Any]) -> Score:
    metadata = ScoreMetadata(**data.get("metadata", {}))
    symbols: list[SymbolInstance] = []
    for raw in data.get("symbols", []):
        timing = Timing(**raw["timing"])
        stage_pos = None
        if raw.get("stage_position"):
            sp = raw["stage_position"]
            stage_pos = StagePosition(
                zone=sp["zone"],
                x=sp.get("x"),
                y=sp.get("y"),
            )
        symbols.append(
            SymbolInstance(
                symbol_id=raw["symbol_id"],
                body_part=raw["body_part"],
                direction=raw.get("direction"),
                level=raw.get("level"),
                timing=timing,
                modifiers=raw.get("modifiers", {}),
                rotation_degrees=raw.get("rotation_degrees"),
                flexion_degrees=raw.get("flexion_degrees"),
                stage_position=stage_pos,
                facing=raw.get("facing"),
                retention=raw.get("retention"),
                effort_graph=EffortGraph(**raw["effort_graph"]) if raw.get("effort_graph") else None,
                cancellation_mode=raw.get("cancellation_mode"),
            )
        )
    sections = [Section(**s) for s in data.get("sections", [])]
    relationship_bows = [RelationshipBow(**rb) for rb in data.get("relationship_bows", [])]
    return Score(metadata=metadata, symbols=symbols, sections=sections, relationship_bows=relationship_bows, extensions=data.get("extensions", {}))
