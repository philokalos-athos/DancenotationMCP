from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from dancenotation_mcp.ir.catalog import load_symbol_catalog

PRIMARY_MOTION_COLUMNS = {"support", "direction", "path", "gesture", "body", "flexion", "foothook", "digit", "turn", "travel", "jump", "floor"}
ATTACHABLE_SOURCE_COLUMNS = {"pin", "surface", "music", "repeat", "quality", "level", "timing"}
ANNOTATION_ATTACHMENT_COLUMNS = {"pin", "surface", "quality", "level", "timing"}
REPEAT_SPAN_SOURCE_SYMBOLS = {"repeat.start", "repeat.generic"}
REPEAT_SPAN_TARGET_SYMBOLS = {"repeat.end", "repeat.double", "repeat.generic"}
MEASURE_HEADER_SYMBOLS = {"music.tempo.mark", "music.cadence.mark", "music.time.2_4", "music.time.3_4", "music.time.4_4"}
MEASURE_BEATS = 4.0
TIME_SIGNATURE_BEATS = {
    "music.time.2_4": 2.0,
    "music.time.3_4": 3.0,
    "music.time.4_4": 4.0,
}
HEADER_FAMILY_BY_SYMBOL = {
    "music.time.2_4": "time_signature",
    "music.time.3_4": "time_signature",
    "music.time.4_4": "time_signature",
    "music.tempo.mark": "tempo",
    "music.cadence.mark": "cadence",
}
HEADER_FAMILY_ORDER = {"time_signature": 0, "tempo": 1, "cadence": 2}
CONFLICTING_TIMING_SYMBOLS = {
    frozenset({"timing.hold", "timing.staccato"}),
    frozenset({"timing.hold", "timing.accent"}),
}
CONFLICTING_QUALITY_SYMBOLS = {
    frozenset({"quality.bound", "quality.free"}),
    frozenset({"quality.direct", "quality.flexible"}),
}
SEMANTIC_ERROR_CODES = {
    "UNKNOWN_SYMBOL",
    "TIMING_DURATION",
    "TIMING_BEAT_RANGE",
    "MODIFIER_ATTACH_SOURCE_ROLE",
    "MODIFIER_ATTACH_TARGET_MISSING",
    "MODIFIER_ATTACH_TARGET_ROLE",
    "MODIFIER_REPEAT_SPAN_SOURCE_ROLE",
    "MODIFIER_REPEAT_SPAN_TARGET_MISSING",
    "MODIFIER_REPEAT_SPAN_TARGET_ROLE",
    "MODIFIER_REPEAT_SPAN_TARGET_ORDER",
    "MODIFIER_MEASURE_HEADER_UNSUPPORTED",
}
REPAIR_ACTION_PRIORITY = {
    "remove_symbol": 0,
    "remove_modifier": 1,
    "replace_symbol": 2,
    "set_body_part": 3,
    "set_direction": 4,
    "set_level": 5,
    "set_modifier": 6,
    "retarget_attachment": 7,
    "retarget_repeat_span": 8,
    "set_beat": 9,
    "set_duration": 10,
    "split_duration": 11,
    "insert_continuation_symbol": 12,
    "reorder_measure_headers": 13,
    "reorder_repeat_boundaries": 14,
}


def _catalog_behavior(catalog: dict[str, dict], symbol_id: str) -> dict:
    return catalog.get(symbol_id, {}).get("behavior", {}) or {}


def _header_family(catalog: dict[str, dict], symbol_id: str) -> str | None:
    return _catalog_behavior(catalog, symbol_id).get("header_role") or HEADER_FAMILY_BY_SYMBOL.get(symbol_id)


def _repeat_boundary_role(catalog: dict[str, dict], symbol_id: str) -> str | None:
    return _catalog_behavior(catalog, symbol_id).get("boundary_role")


def _is_measure_header_symbol(catalog: dict[str, dict], symbol_id: str) -> bool:
    return _header_family(catalog, symbol_id) in HEADER_FAMILY_ORDER


def _is_repeat_span_source(catalog: dict[str, dict], symbol_id: str) -> bool:
    role = _repeat_boundary_role(catalog, symbol_id)
    return symbol_id in REPEAT_SPAN_SOURCE_SYMBOLS or role == "opening"


def _is_repeat_span_target(catalog: dict[str, dict], symbol_id: str) -> bool:
    role = _repeat_boundary_role(catalog, symbol_id)
    return symbol_id in REPEAT_SPAN_TARGET_SYMBOLS or role == "closing"


def _is_repeat_opening(catalog: dict[str, dict], symbol_id: str) -> bool:
    return _repeat_boundary_role(catalog, symbol_id) == "opening" or symbol_id == "repeat.start"


def _is_repeat_closing(catalog: dict[str, dict], symbol_id: str) -> bool:
    return _repeat_boundary_role(catalog, symbol_id) == "closing" or symbol_id in {"repeat.end", "repeat.double"}


def _continuation_scope(catalog: dict[str, dict], symbol_id: str) -> str | None:
    return _catalog_behavior(catalog, symbol_id).get("continuation_scope")


def _attachment_coverage_expectation(catalog: dict[str, dict], symbol_id: str) -> str | None:
    return _catalog_behavior(catalog, symbol_id).get("coverage_expectation")


@dataclass
class ValidationIssue:
    code: str
    message: str
    path: str
    severity: str
    details: dict

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
            "details": self.details,
        }


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "notation-ir.schema.json"


def validate_schema(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    schema = json.loads(_schema_path().read_text())
    required_root = schema.get("required", [])
    for key in required_root:
        if key not in data:
            issues.append(ValidationIssue("SCHEMA_REQUIRED", f"Missing required field '{key}'", f"/{key}", "error", {}))
    if "symbols" in data and not isinstance(data["symbols"], list):
        issues.append(ValidationIssue("SCHEMA_TYPE", "symbols must be an array", "/symbols", "error", {}))
    return issues


def _validate_symbol_constraints(sym: dict, catalog_entry: dict, path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    body = sym.get("body_part")
    if body and body not in catalog_entry.get("allowed_body_parts", []):
        issues.append(
            ValidationIssue(
                "SYMBOL_BODY_PART",
                f"body_part '{body}' not allowed for symbol '{catalog_entry['id']}'",
                f"{path}/body_part",
                "error",
                {"allowed_body_parts": catalog_entry.get("allowed_body_parts", [])},
            )
        )

    direction = sym.get("direction")
    if catalog_entry.get("requires_direction") and not direction:
        issues.append(
            ValidationIssue(
                "SYMBOL_DIRECTION_REQUIRED",
                f"direction required for symbol '{catalog_entry['id']}'",
                f"{path}/direction",
                "error",
                {},
            )
        )
    if direction and direction not in catalog_entry.get("allowed_directions", []):
        issues.append(
            ValidationIssue(
                "SYMBOL_DIRECTION_INVALID",
                f"direction '{direction}' not allowed for symbol '{catalog_entry['id']}'",
                f"{path}/direction",
                "error",
                {"allowed_directions": catalog_entry.get("allowed_directions", [])},
            )
        )

    level = sym.get("level")
    if catalog_entry.get("requires_level") and not level:
        issues.append(
            ValidationIssue(
                "SYMBOL_LEVEL_REQUIRED",
                f"level required for symbol '{catalog_entry['id']}'",
                f"{path}/level",
                "error",
                {},
            )
        )
    if level and level not in catalog_entry.get("allowed_levels", []):
        issues.append(
            ValidationIssue(
                "SYMBOL_LEVEL_INVALID",
                f"level '{level}' not allowed for symbol '{catalog_entry['id']}'",
                f"{path}/level",
                "error",
                {"allowed_levels": catalog_entry.get("allowed_levels", [])},
            )
        )

    geom = catalog_entry.get("geometry")
    if not isinstance(geom, dict) or not geom.get("glyph"):
        issues.append(
            ValidationIssue(
                "SYMBOL_GEOMETRY_MISSING",
                f"symbol '{catalog_entry['id']}' missing geometry definition",
                f"{path}/symbol_id",
                "error",
                {},
            )
        )

    modifiers = sym.get("modifiers", {})
    if isinstance(modifiers, dict):
        degree = modifiers.get("degree")
        if degree is not None and not isinstance(degree, (int, float)):
            issues.append(
                ValidationIssue(
                    "MODIFIER_DEGREE_INVALID",
                    "modifier 'degree' must be numeric",
                    f"{path}/modifiers/degree",
                    "error",
                    {},
                )
            )

        line_style = modifiers.get("line_style")
        if line_style and line_style not in {"single", "double", "dotted", "double_dotted"}:
            issues.append(
                ValidationIssue(
                    "MODIFIER_LINE_STYLE_INVALID",
                    f"modifier 'line_style' value '{line_style}' is invalid",
                    f"{path}/modifiers/line_style",
                    "error",
                    {"allowed": ["single", "double", "dotted", "double_dotted"]},
                )
            )

        for numeric_key in ("stretch", "rotation", "pin_length", "rest_height"):
            numeric_value = modifiers.get(numeric_key)
            if numeric_value is not None and not isinstance(numeric_value, (int, float)):
                issues.append(
                    ValidationIssue(
                        "MODIFIER_NUMERIC_INVALID",
                        f"modifier '{numeric_key}' must be numeric",
                        f"{path}/modifiers/{numeric_key}",
                        "error",
                        {},
                    )
                )

        repeat_count = modifiers.get("repeat_count")
        if repeat_count is not None and (not isinstance(repeat_count, int) or repeat_count < 1):
            issues.append(
                ValidationIssue(
                    "MODIFIER_REPEAT_COUNT_INVALID",
                    "modifier 'repeat_count' must be an integer >= 1",
                    f"{path}/modifiers/repeat_count",
                    "error",
                    {},
                )
            )

        attach_to = modifiers.get("attach_to")
        if attach_to is not None and not isinstance(attach_to, str):
            issues.append(
                ValidationIssue(
                    "MODIFIER_ATTACH_TO_INVALID",
                    "modifier 'attach_to' must be a symbol id string",
                    f"{path}/modifiers/attach_to",
                    "error",
                    {},
                )
            )

        attach_side = modifiers.get("attach_side")
        if attach_side is not None and attach_side not in {"auto", "left", "right", "top", "bottom"}:
            issues.append(
                ValidationIssue(
                    "MODIFIER_ATTACH_SIDE_INVALID",
                    "modifier 'attach_side' must be auto, left, right, top, or bottom",
                    f"{path}/modifiers/attach_side",
                    "error",
                    {"allowed": ["auto", "left", "right", "top", "bottom"]},
                )
            )

        repeat_span_to = modifiers.get("repeat_span_to")
        if repeat_span_to is not None and not isinstance(repeat_span_to, str):
            issues.append(
                ValidationIssue(
                    "MODIFIER_REPEAT_SPAN_TO_INVALID",
                    "modifier 'repeat_span_to' must be a symbol id string",
                    f"{path}/modifiers/repeat_span_to",
                    "error",
                    {},
                )
            )

        measure_header = modifiers.get("measure_header")
        if measure_header is not None and not isinstance(measure_header, bool):
            issues.append(
                ValidationIssue(
                    "MODIFIER_MEASURE_HEADER_INVALID",
                    "modifier 'measure_header' must be a boolean",
                    f"{path}/modifiers/measure_header",
                    "error",
                    {},
                )
            )

        pin_head = modifiers.get("pin_head")
        if pin_head and pin_head not in {"circle", "diamond"}:
            issues.append(
                ValidationIssue(
                    "MODIFIER_PIN_HEAD_INVALID",
                    "modifier 'pin_head' must be circle or diamond",
                    f"{path}/modifiers/pin_head",
                    "error",
                    {"allowed": ["circle", "diamond"]},
                )
            )

        separator_mode = modifiers.get("separator_mode")
        if separator_mode and separator_mode not in {"single", "double", "hooked"}:
            issues.append(
                ValidationIssue(
                    "MODIFIER_SEPARATOR_MODE_INVALID",
                    "modifier 'separator_mode' must be single, double, or hooked",
                    f"{path}/modifiers/separator_mode",
                    "error",
                    {"allowed": ["single", "double", "hooked"]},
                )
            )

        behavior = catalog_entry.get("behavior", {}) or {}
        preferred_pin_head = behavior.get("preferred_pin_head")
        if preferred_pin_head and modifiers.get("pin_head") != preferred_pin_head:
            issues.append(
                ValidationIssue(
                    "PIN_VARIANT_HEAD_REQUIRED",
                    f"symbol '{catalog_entry['id']}' should use pin_head '{preferred_pin_head}'",
                    f"{path}/modifiers/pin_head",
                    "warning",
                    {"suggested_pin_head": preferred_pin_head, "symbol_id": catalog_entry["id"]},
                )
            )

        preferred_separator_mode = behavior.get("preferred_separator_mode")
        if preferred_separator_mode and modifiers.get("separator_mode") != preferred_separator_mode:
            issues.append(
                ValidationIssue(
                    "SEPARATOR_VARIANT_MODE_REQUIRED",
                    f"symbol '{catalog_entry['id']}' should use separator_mode '{preferred_separator_mode}'",
                    f"{path}/modifiers/separator_mode",
                    "warning",
                    {"suggested_separator_mode": preferred_separator_mode, "symbol_id": catalog_entry["id"]},
                )
            )

        for key in ("level_fill_top", "level_fill_bottom"):
            if modifiers.get(key) and modifiers[key] not in {"high", "middle", "low", "blank"}:
                issues.append(
                    ValidationIssue(
                        "MODIFIER_LEVEL_FILL_INVALID",
                        f"modifier '{key}' value '{modifiers[key]}' is invalid",
                        f"{path}/modifiers/{key}",
                        "error",
                        {"allowed": ["high", "middle", "low", "blank"]},
                    )
                )

        surface_marks = modifiers.get("surface_marks")
        if surface_marks is not None:
            allowed_surface_marks = {"left", "right", "forward", "backward"}
            if not isinstance(surface_marks, list) or any(mark not in allowed_surface_marks for mark in surface_marks):
                issues.append(
                    ValidationIssue(
                        "MODIFIER_SURFACE_MARK_INVALID",
                        "modifier 'surface_marks' must be an array of left/right/forward/backward",
                        f"{path}/modifiers/surface_marks",
                        "error",
                        {"allowed": sorted(allowed_surface_marks)},
                    )
                )

        spring_jump = modifiers.get("spring_jump")
        if spring_jump is not None:
            allowed_support = {"left", "right"}
            if not isinstance(spring_jump, dict):
                issues.append(
                    ValidationIssue(
                        "MODIFIER_SPRING_JUMP_INVALID",
                        "modifier 'spring_jump' must be an object",
                        f"{path}/modifiers/spring_jump",
                        "error",
                        {},
                    )
                )
            else:
                for side_key in ("takeoff", "landing"):
                    values = spring_jump.get(side_key, [])
                    if not isinstance(values, list) or any(value not in allowed_support for value in values):
                        issues.append(
                            ValidationIssue(
                                "MODIFIER_SPRING_JUMP_INVALID",
                                f"modifier 'spring_jump.{side_key}' must contain left/right values",
                                f"{path}/modifiers/spring_jump/{side_key}",
                                "error",
                                {"allowed": sorted(allowed_support)},
                            )
                        )

    return issues


def _measure_beats_by_measure(symbols: list[dict]) -> dict[int, float]:
    explicit: dict[int, float] = {}
    for sym in symbols:
        if not sym.get("modifiers", {}).get("measure_header"):
            continue
        beats = TIME_SIGNATURE_BEATS.get(sym.get("symbol_id", ""))
        if beats is None:
            continue
        measure = int(sym.get("timing", {}).get("measure", 1))
        explicit[measure] = beats
    if not explicit:
        return {}
    derived: dict[int, float] = {}
    current = MEASURE_BEATS
    max_measure = max(
        [int(sym.get("timing", {}).get("measure", 1)) for sym in symbols] + list(explicit.keys())
    )
    for measure in range(1, max_measure + 1):
        if measure in explicit:
            current = explicit[measure]
        derived[measure] = current
    return derived


def _normalize_semantic_issue_severities(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    for issue in issues:
        issue.severity = "error" if issue.code in SEMANTIC_ERROR_CODES else "warning"
    return issues


def validate_semantic(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    symbols = data.get("symbols", [])
    catalog = load_symbol_catalog()
    measure_beats_by_measure = _measure_beats_by_measure(symbols)
    symbol_index = {sym.get("symbol_id"): (idx, sym) for idx, sym in enumerate(symbols) if sym.get("symbol_id")}
    primary_body_entries: list[tuple[int, dict, dict]] = []
    measure_headers_by_measure: dict[int, list[tuple[int, dict]]] = {}

    last_end_by_measure: dict[int, float] = {}
    for idx, sym in enumerate(symbols):
        p = f"/symbols/{idx}"
        sid = sym.get("symbol_id")
        staff_column = None
        if sid not in catalog:
            issues.append(ValidationIssue("UNKNOWN_SYMBOL", f"Unknown symbol id '{sid}'", f"{p}/symbol_id", "error", {}))
        else:
            issues.extend(_validate_symbol_constraints(sym, catalog[sid], p))
            staff_column = catalog[sid].get("geometry", {}).get("staff_column")
            if staff_column in PRIMARY_MOTION_COLUMNS:
                primary_body_entries.append((idx, sym, catalog[sid]))

        timing = sym.get("timing", {})
        beat = float(timing.get("beat", 0))
        measure = int(timing.get("measure", 1))
        dur = float(timing.get("duration_beats", 0))
        measure_beats = measure_beats_by_measure.get(measure, MEASURE_BEATS)
        if dur <= 0:
            issues.append(ValidationIssue("TIMING_DURATION", "duration_beats must be > 0", f"{p}/timing/duration_beats", "error", {}))
        if beat < 1.0:
            issues.append(ValidationIssue("TIMING_BEAT_RANGE", "beat must be >= 1 within the measure", f"{p}/timing/beat", "error", {}))
        if beat + dur - 1.0 > measure_beats + 0.01:
            max_duration = max(0.0, measure_beats - beat + 1.0)
            carry_duration = max(0.0, dur - max_duration)
            issues.append(
                ValidationIssue(
                    "TIMING_MEASURE_OVERFLOW",
                    "symbol duration extends past the end of the measure",
                    f"{p}/timing/duration_beats",
                    "warning",
                    {
                        "measure": measure,
                        "measure_beats": measure_beats,
                        "max_duration": max_duration,
                        "carry_duration": carry_duration,
                        "next_measure": measure + 1,
                    },
                )
            )
        if staff_column in PRIMARY_MOTION_COLUMNS:
            last_end = last_end_by_measure.get(measure, 0.0)
            if beat < last_end:
                issues.append(
                    ValidationIssue(
                        "TIMING_OVERLAP",
                        "symbol starts before previous symbol ended",
                        f"{p}/timing/beat",
                        "warning",
                        {"prev_end": last_end},
                    )
                )
            last_end_by_measure[measure] = max(last_end, beat + dur)

        modifiers = sym.get("modifiers", {}) if isinstance(sym.get("modifiers", {}), dict) else {}
        attach_to = modifiers.get("attach_to")
        attach_side = modifiers.get("attach_side")
        measure_header = modifiers.get("measure_header")
        if attach_side is not None and not isinstance(attach_to, str):
            issues.append(
                ValidationIssue(
                    "MODIFIER_ATTACH_SIDE_ORPHANED",
                    "attach_side requires attach_to to reference a target symbol",
                    f"{p}/modifiers/attach_side",
                    "warning",
                    {"symbol_id": sid},
                )
            )

        if isinstance(attach_to, str):
            source_column = staff_column
            source_role_valid = True
            if source_column not in ATTACHABLE_SOURCE_COLUMNS:
                source_role_valid = False
                issues.append(
                    ValidationIssue(
                        "MODIFIER_ATTACH_SOURCE_ROLE",
                        f"symbol '{sid}' should not carry attach_to",
                        f"{p}/modifiers/attach_to",
                        "error",
                        {"symbol_id": sid, "source_staff_column": source_column},
                    )
                )
            target_entry = symbol_index.get(attach_to) if source_role_valid else None
            if not target_entry:
                if source_role_valid:
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_TARGET_MISSING",
                            f"attach_to target '{attach_to}' does not exist",
                            f"{p}/modifiers/attach_to",
                            "error",
                            {"attach_to": attach_to},
                        )
                    )
            else:
                _target_idx, target = target_entry
                target_sid = target.get("symbol_id", "")
                target_column = catalog.get(target_sid, {}).get("geometry", {}).get("staff_column")
                if target_column not in PRIMARY_MOTION_COLUMNS:
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_TARGET_ROLE",
                            f"attach_to target '{attach_to}' should reference a primary motion symbol",
                            f"{p}/modifiers/attach_to",
                            "error",
                            {"attach_to": attach_to, "target_staff_column": target_column},
                        )
                    )
                source_behavior = _catalog_behavior(catalog, sid)
                valid_anchor_families = source_behavior.get("valid_anchor_families")
                if (
                    isinstance(valid_anchor_families, list)
                    and target_column in PRIMARY_MOTION_COLUMNS
                    and target_column not in valid_anchor_families
                ):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_TARGET_FAMILY_INCOMPATIBLE",
                            f"attach_to target '{attach_to}' uses primary family '{target_column}' which is incompatible with '{sid}'",
                            f"{p}/modifiers/attach_to",
                            "warning",
                            {"attach_to": attach_to, "target_staff_column": target_column, "allowed_families": valid_anchor_families},
                        )
                    )
                preferred_anchor_side = source_behavior.get("preferred_anchor_side")
                if (
                    attach_side in {"left", "right", "top", "bottom"}
                    and preferred_anchor_side in {"left", "right", "top", "bottom"}
                    and attach_side != preferred_anchor_side
                ):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_SIDE_PREFERRED_MISMATCH",
                            f"symbol '{sid}' prefers attach_side '{preferred_anchor_side}'",
                            f"{p}/modifiers/attach_side",
                            "warning",
                            {"suggested_attach_side": preferred_anchor_side, "symbol_id": sid},
                        )
                    )
                elif source_column in {"music", "repeat"}:
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_FAMILY_INCOMPATIBLE",
                            f"symbol '{sid}' should not attach across movement lanes from the {source_column} family",
                            f"{p}/modifiers/attach_to",
                            "warning",
                            {"symbol_id": sid, "source_staff_column": source_column, "attach_to": attach_to},
                        )
                    )
                source_body = sym.get("body_part")
                target_body = target.get("body_part")
                if (
                    source_body
                    and target_body
                    and source_body != "torso"
                    and target_body != "torso"
                    and source_body != target_body
                ):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_BODY_PART_MISMATCH",
                            f"attach_to target '{attach_to}' should match the attached symbol body_part",
                            f"{p}/modifiers/attach_to",
                            "warning",
                            {"attach_to": attach_to, "source_body_part": source_body, "target_body_part": target_body},
                        )
                    )
                target_time = target.get("timing", {})
                target_beat = float(target_time.get("beat", 0))
                target_measure = int(target_time.get("measure", 1))
                target_duration = float(target_time.get("duration_beats", 0))
                target_end = target_beat + max(target_duration, 0.0)
                if target_measure > int(timing.get("measure", 1)) or (
                    target_measure == int(timing.get("measure", 1)) and target_beat > beat + 0.01
                ):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_TARGET_FUTURE",
                            f"attach_to target '{attach_to}' occurs after the attached symbol",
                            f"{p}/modifiers/attach_to",
                            "warning",
                            {"attach_to": attach_to},
                        )
                    )
                elif target_measure != int(timing.get("measure", 1)):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_ATTACH_TARGET_MEASURE_MISMATCH",
                            f"attach_to target '{attach_to}' should stay within the same measure as the attached symbol",
                            f"{p}/modifiers/attach_to",
                            "warning",
                            {"attach_to": attach_to, "source_measure": int(timing.get("measure", 1)), "target_measure": target_measure},
                        )
                    )
                else:
                    coverage_expectation = _attachment_coverage_expectation(catalog, sid)
                    enforce_covering_motion = coverage_expectation in {"covering_motion", "must_cover_annotation_beat"}
                    if coverage_expectation is None and source_column in ANNOTATION_ATTACHMENT_COLUMNS:
                        enforce_covering_motion = True
                    if enforce_covering_motion and target_end + 0.01 < beat:
                        issues.append(
                            ValidationIssue(
                                "MODIFIER_ATTACH_TARGET_OUTSIDE_COVERAGE",
                                f"attach_to target '{attach_to}' ends before the attached symbol occurs",
                                f"{p}/modifiers/attach_to",
                                "warning",
                                {"attach_to": attach_to, "target_end": target_end, "source_beat": beat},
                            )
                        )

        source_column = staff_column
        if source_column in ANNOTATION_ATTACHMENT_COLUMNS and not isinstance(attach_to, str) and measure_header is not True:
            issues.append(
                ValidationIssue(
                    "MODIFIER_ATTACH_MISSING_FOR_ANNOTATION",
                    f"annotation symbol '{sid}' should attach to a primary motion symbol",
                    f"{p}/modifiers/attach_to",
                    "warning",
                    {"symbol_id": sid, "staff_column": source_column},
                )
            )

        repeat_span_to = modifiers.get("repeat_span_to")
        if _repeat_boundary_role(catalog, sid) and sym.get("body_part") != "torso":
            issues.append(
                ValidationIssue(
                    "REPEAT_BODY_PART_INVALID",
                    "repeat-family symbols should use body_part 'torso'",
                    f"{p}/body_part",
                    "warning",
                    {"symbol_id": sid, "suggested_body_part": "torso"},
                )
            )
        if _is_repeat_opening(catalog, sid) and abs(beat - 1.0) > 0.01:
            issues.append(
                ValidationIssue(
                    "REPEAT_START_TIMING",
                    "repeat.start should begin at beat 1 of its measure",
                    f"{p}/timing/beat",
                    "warning",
                    {"suggested_beat": 1.0, "measure": measure},
                )
            )
        if _is_repeat_closing(catalog, sid) and abs(beat - measure_beats) > 0.01:
            issues.append(
                ValidationIssue(
                    "REPEAT_END_TIMING",
                    "closing repeat signs should align with the last beat of their measure",
                    f"{p}/timing/beat",
                    "warning",
                    {"suggested_beat": measure_beats, "measure": measure},
                )
            )
        if isinstance(repeat_span_to, str):
            source_role_valid = True
            if not _is_repeat_span_source(catalog, sid):
                source_role_valid = False
                issues.append(
                    ValidationIssue(
                        "MODIFIER_REPEAT_SPAN_SOURCE_ROLE",
                        f"symbol '{sid}' should not carry repeat_span_to",
                        f"{p}/modifiers/repeat_span_to",
                        "error",
                        {"symbol_id": sid},
                    )
                )
            target_entry = symbol_index.get(repeat_span_to) if source_role_valid else None
            if not target_entry:
                if source_role_valid:
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_REPEAT_SPAN_TARGET_MISSING",
                            f"repeat_span_to target '{repeat_span_to}' does not exist",
                            f"{p}/modifiers/repeat_span_to",
                            "error",
                            {"repeat_span_to": repeat_span_to},
                        )
                    )
            else:
                _target_idx, target = target_entry
                target_sid = target.get("symbol_id", "")
                target_column = catalog.get(target_sid, {}).get("geometry", {}).get("staff_column")
                if target_column != "repeat":
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_REPEAT_SPAN_TARGET_ROLE",
                            f"repeat_span_to target '{repeat_span_to}' must reference a repeat-family symbol",
                            f"{p}/modifiers/repeat_span_to",
                            "error",
                            {"repeat_span_to": repeat_span_to, "target_staff_column": target_column},
                        )
                    )
                if not _is_repeat_span_target(catalog, target_sid):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_REPEAT_SPAN_TARGET_VARIANT",
                            f"repeat_span_to target '{repeat_span_to}' should close the span with a repeat.end/double symbol",
                            f"{p}/modifiers/repeat_span_to",
                            "warning",
                            {"repeat_span_to": repeat_span_to, "target_symbol_id": target_sid},
                        )
                    )
                target_time = target.get("timing", {})
                target_measure = int(target_time.get("measure", 1))
                target_beat = float(target_time.get("beat", 0))
                if target_measure < int(timing.get("measure", 1)) or (
                    target_measure == int(timing.get("measure", 1)) and target_beat <= beat
                ):
                    issues.append(
                        ValidationIssue(
                            "MODIFIER_REPEAT_SPAN_TARGET_ORDER",
                            f"repeat_span_to target '{repeat_span_to}' must occur after the span start",
                            f"{p}/modifiers/repeat_span_to",
                            "error",
                            {"repeat_span_to": repeat_span_to},
                        )
                    )

        if measure_header is True and sid in catalog:
            measure_headers_by_measure.setdefault(measure, []).append((idx, sym))
            staff_column = catalog[sid].get("geometry", {}).get("staff_column")
            if staff_column != "music":
                issues.append(
                    ValidationIssue(
                        "MODIFIER_MEASURE_HEADER_UNSUPPORTED",
                        "measure_header is only supported for music-family symbols",
                        f"{p}/modifiers/measure_header",
                        "error",
                        {"symbol_id": sid},
                    )
                )
            elif not _is_measure_header_symbol(catalog, sid):
                issues.append(
                    ValidationIssue(
                        "MODIFIER_MEASURE_HEADER_SYMBOL_ROLE",
                        "measure_header should be used on time, tempo, or cadence music symbols",
                        f"{p}/modifiers/measure_header",
                        "warning",
                        {"symbol_id": sid},
                    )
                )
            if sym.get("body_part") != "torso":
                issues.append(
                    ValidationIssue(
                        "MODIFIER_MEASURE_HEADER_BODY_PART",
                        "measure_header symbols should use body_part 'torso'",
                        f"{p}/body_part",
                        "warning",
                        {"symbol_id": sid, "suggested_body_part": "torso"},
                    )
                )
            if abs(beat - 1.0) > 0.01:
                issues.append(
                    ValidationIssue(
                        "MODIFIER_MEASURE_HEADER_TIMING",
                        "measure_header symbols should start at beat 1 of the measure",
                        f"{p}/timing/beat",
                        "warning",
                        {"measure": measure, "suggested_beat": 1.0},
                    )
                )
        if _header_family(catalog, sid) == "tempo":
            tempo_value = modifiers.get("tempo")
            if not isinstance(tempo_value, int) or tempo_value <= 0:
                issues.append(
                    ValidationIssue(
                        "MUSIC_TEMPO_VALUE_MISSING",
                        "music.tempo.mark should include a positive integer tempo modifier",
                        f"{p}/modifiers/tempo",
                        "warning",
                        {"suggested_tempo": 120},
                    )
                )
        if _header_family(catalog, sid) == "cadence":
            label = modifiers.get("label")
            if not isinstance(label, str) or not label.strip():
                issues.append(
                    ValidationIssue(
                        "MUSIC_CADENCE_LABEL_MISSING",
                        "music.cadence.mark should include a non-empty label modifier",
                        f"{p}/modifiers/label",
                        "warning",
                        {"suggested_label": "rit."},
                    )
                )

    for measure, headers in measure_headers_by_measure.items():
        family_seen: dict[str, int] = {}
        for idx, sym in sorted(headers, key=lambda item: item[0]):
            family = _header_family(catalog, sym.get("symbol_id", ""))
            if not family:
                continue
            if family in family_seen:
                issues.append(
                    ValidationIssue(
                        "MEASURE_HEADER_FAMILY_DUPLICATE",
                        f"measure {measure} contains multiple {family} headers",
                        f"/symbols/{idx}/symbol_id",
                        "warning",
                        {"measure": measure, "symbol_id": sym.get("symbol_id"), "family": family},
                    )
                )
            else:
                family_seen[family] = idx
        ordered_headers = [(idx, sym, _header_family(catalog, sym.get("symbol_id", ""))) for idx, sym in sorted(headers, key=lambda item: item[0])]
        filtered_order = [(idx, family) for idx, _sym, family in ordered_headers if family in HEADER_FAMILY_ORDER]
        expected_order = sorted(filtered_order, key=lambda item: (HEADER_FAMILY_ORDER[item[1]], item[0]))
        if [family for _, family in filtered_order] != [family for _, family in expected_order]:
            for (actual_idx, actual_family), (expected_idx, expected_family) in zip(filtered_order, expected_order):
                if actual_family != expected_family:
                    issues.append(
                        ValidationIssue(
                            "MEASURE_HEADER_ORDER_INVALID",
                            f"measure {measure} header order should be time signature, then tempo, then cadence",
                            f"/symbols/{actual_idx}/symbol_id",
                            "warning",
                            {"measure": measure, "family": actual_family, "expected_family": expected_family},
                        )
                    )
                    break
        first_non_header_idx = next(
            (
                idx
                for idx, sym in enumerate(symbols)
                if int(sym.get("timing", {}).get("measure", 1)) == measure and not sym.get("modifiers", {}).get("measure_header")
            ),
            None,
        )
        if first_non_header_idx is not None:
            misplaced_header_idx = next((idx for idx, _sym in sorted(headers, key=lambda item: item[0]) if idx > first_non_header_idx), None)
            if misplaced_header_idx is not None:
                issues.append(
                    ValidationIssue(
                        "MEASURE_HEADER_POSITION_INVALID",
                        f"measure {measure} headers should appear before content symbols in the same measure",
                        f"/symbols/{misplaced_header_idx}/symbol_id",
                        "warning",
                        {"measure": measure, "first_content_index": first_non_header_idx},
                    )
                )

    time_signature_headers: list[tuple[int, dict]] = []
    for idx, sym in enumerate(symbols):
        if _header_family(catalog, sym.get("symbol_id", "")) == "time_signature" and sym.get("modifiers", {}).get("measure_header"):
            time_signature_headers.append((idx, sym))
    time_signature_headers.sort(key=lambda item: int(item[1].get("timing", {}).get("measure", 1)))
    for pos in range(1, len(time_signature_headers)):
        prev_idx, prev_sym = time_signature_headers[pos - 1]
        idx, sym = time_signature_headers[pos]
        prev_measure = int(prev_sym.get("timing", {}).get("measure", 1))
        measure = int(sym.get("timing", {}).get("measure", 1))
        if measure == prev_measure + 1 and sym.get("symbol_id") == prev_sym.get("symbol_id"):
            issues.append(
                ValidationIssue(
                    "MUSIC_TIME_SIGNATURE_REDUNDANT",
                    f"time signature '{sym.get('symbol_id')}' is repeated in consecutive measures without changing meter",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"symbol_id": sym.get("symbol_id"), "measure": measure, "previous_measure": prev_measure},
                )
            )

    tempo_headers: list[tuple[int, dict]] = []
    tempo_headers: list[tuple[int, dict]] = []
    for idx, sym in enumerate(symbols):
        if _header_family(catalog, sym.get("symbol_id", "")) == "tempo" and sym.get("modifiers", {}).get("measure_header"):
            tempo_headers.append((idx, sym))
    tempo_headers.sort(key=lambda item: int(item[1].get("timing", {}).get("measure", 1)))
    for pos in range(1, len(tempo_headers)):
        prev_idx, prev_sym = tempo_headers[pos - 1]
        idx, sym = tempo_headers[pos]
        prev_measure = int(prev_sym.get("timing", {}).get("measure", 1))
        measure = int(sym.get("timing", {}).get("measure", 1))
        prev_tempo = prev_sym.get("modifiers", {}).get("tempo")
        tempo = sym.get("modifiers", {}).get("tempo")
        if measure == prev_measure + 1 and tempo is not None and tempo == prev_tempo:
            issues.append(
                ValidationIssue(
                    "MUSIC_TEMPO_REDUNDANT",
                    f"tempo header '{tempo}' is repeated in consecutive measures without changing tempo",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"tempo": tempo, "measure": measure, "previous_measure": prev_measure},
                )
            )

    cadence_headers: list[tuple[int, dict]] = []
    for idx, sym in enumerate(symbols):
        if _header_family(catalog, sym.get("symbol_id", "")) == "cadence" and sym.get("modifiers", {}).get("measure_header"):
            cadence_headers.append((idx, sym))
    cadence_headers.sort(key=lambda item: int(item[1].get("timing", {}).get("measure", 1)))
    for pos in range(1, len(cadence_headers)):
        prev_idx, prev_sym = cadence_headers[pos - 1]
        idx, sym = cadence_headers[pos]
        prev_measure = int(prev_sym.get("timing", {}).get("measure", 1))
        measure = int(sym.get("timing", {}).get("measure", 1))
        prev_label = prev_sym.get("modifiers", {}).get("label") or prev_sym.get("modifiers", {}).get("source_text")
        label = sym.get("modifiers", {}).get("label") or sym.get("modifiers", {}).get("source_text")
        if measure == prev_measure + 1 and label == prev_label:
            issues.append(
                ValidationIssue(
                    "MUSIC_CADENCE_REDUNDANT",
                    "cadence header is repeated in consecutive measures without changing cadence label",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": measure, "previous_measure": prev_measure, "label": label},
                )
            )

    previous_score_tempo: int | None = None
    for idx, sym in tempo_headers:
        if _continuation_scope(catalog, sym.get("symbol_id", "")) != "score":
            continue
        tempo = sym.get("modifiers", {}).get("tempo")
        if isinstance(tempo, int) and tempo > 0:
            previous_score_tempo = tempo
            continue
        if previous_score_tempo is not None:
            issues.append(
                ValidationIssue(
                    "MUSIC_TEMPO_CONTINUATION_VALUE_MISSING",
                    "music.tempo.mark omits tempo even though a previous score-scoped tempo can be carried forward",
                    f"/symbols/{idx}/modifiers/tempo",
                    "warning",
                    {"suggested_tempo": previous_score_tempo},
                )
            )

    previous_score_cadence: str | None = None
    for idx, sym in cadence_headers:
        if _continuation_scope(catalog, sym.get("symbol_id", "")) != "score":
            continue
        label = sym.get("modifiers", {}).get("label")
        if isinstance(label, str) and label.strip():
            previous_score_cadence = label
            continue
        if previous_score_cadence is not None:
            issues.append(
                ValidationIssue(
                    "MUSIC_CADENCE_CONTINUATION_LABEL_MISSING",
                    "music.cadence.mark omits its label even though a previous score-scoped cadence can be carried forward",
                    f"/symbols/{idx}/modifiers/label",
                    "warning",
                    {"suggested_label": previous_score_cadence},
                )
            )

    repeat_starts: list[tuple[int, dict]] = []
    repeat_ends: list[tuple[int, dict]] = []
    symbols_by_measure: dict[int, list[tuple[int, dict]]] = {}
    for idx, sym in enumerate(symbols):
        sid = sym.get("symbol_id")
        measure = int(sym.get("timing", {}).get("measure", 1))
        symbols_by_measure.setdefault(measure, []).append((idx, sym))
        if _is_repeat_opening(catalog, sid):
            repeat_starts.append((idx, sym))
        elif _is_repeat_closing(catalog, sid):
            repeat_ends.append((idx, sym))

    repeat_start_slots_seen: set[tuple[int, float]] = set()
    for idx, sym in sorted(
        repeat_starts,
        key=lambda item: (
            int(item[1].get("timing", {}).get("measure", 1)),
            float(item[1].get("timing", {}).get("beat", 0)),
            item[0],
        ),
    ):
        timing = sym.get("timing", {})
        slot = (int(timing.get("measure", 1)), float(timing.get("beat", 0)))
        if slot in repeat_start_slots_seen:
            issues.append(
                ValidationIssue(
                    "REPEAT_START_SLOT_DUPLICATE",
                    "multiple opening repeat signs share the same measure and beat slot",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": slot[0], "beat": slot[1], "symbol_id": sym.get("symbol_id")},
                )
            )
        else:
            repeat_start_slots_seen.add(slot)

    repeat_end_slots_seen: set[tuple[int, float]] = set()
    for idx, sym in sorted(
        repeat_ends,
        key=lambda item: (
            int(item[1].get("timing", {}).get("measure", 1)),
            float(item[1].get("timing", {}).get("beat", 0)),
            item[0],
        ),
    ):
        timing = sym.get("timing", {})
        slot = (int(timing.get("measure", 1)), float(timing.get("beat", 0)))
        if slot in repeat_end_slots_seen:
            issues.append(
                ValidationIssue(
                    "REPEAT_END_SLOT_DUPLICATE",
                    "multiple closing repeat signs share the same measure and beat slot",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": slot[0], "beat": slot[1], "symbol_id": sym.get("symbol_id")},
                )
            )
        else:
            repeat_end_slots_seen.add(slot)

    start_slots = {
        (
            int(sym.get("timing", {}).get("measure", 1)),
            float(sym.get("timing", {}).get("beat", 0)),
        ): idx
        for idx, sym in repeat_starts
    }
    for idx, sym in repeat_ends:
        timing = sym.get("timing", {})
        slot = (int(timing.get("measure", 1)), float(timing.get("beat", 0)))
        if slot in start_slots:
            issues.append(
                ValidationIssue(
                    "REPEAT_SLOT_MIXED_BOUNDARY_CONFLICT",
                    "opening and closing repeat signs share the same measure and beat slot",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": slot[0], "beat": slot[1], "symbol_id": sym.get("symbol_id")},
                )
            )

    ordered_repeat_events = sorted(
        [
            (
                int(sym.get("timing", {}).get("measure", 1)),
                float(sym.get("timing", {}).get("beat", 0)),
                idx,
                sym,
            )
            for idx, sym in repeat_starts + repeat_ends
        ],
        key=lambda item: (item[0], item[1], item[2]),
    )
    open_repeat_start: tuple[int, dict] | None = None
    for _measure, _beat, idx, sym in ordered_repeat_events:
        sid = sym.get("symbol_id")
        if _is_repeat_opening(catalog, sid):
            if open_repeat_start is not None:
                open_idx, open_sym = open_repeat_start
                issues.append(
                    ValidationIssue(
                        "REPEAT_START_NESTED_UNSUPPORTED",
                        "repeat.start appears before the previous repeat structure has closed",
                        f"/symbols/{idx}/symbol_id",
                        "warning",
                        {"open_repeat_start": open_sym.get("symbol_id"), "measure": _measure},
                    )
                )
            else:
                open_repeat_start = (idx, sym)
        elif _is_repeat_closing(catalog, sid) and open_repeat_start is not None:
            open_repeat_start = None

    for idx, sym in repeat_starts:
        timing = sym.get("timing", {})
        measure = int(timing.get("measure", 1))
        beat = float(timing.get("beat", 0))
        measure_content_indices = [
            other_idx
            for other_idx, other_sym in enumerate(symbols)
            if int(other_sym.get("timing", {}).get("measure", 1)) == measure
            and not other_sym.get("modifiers", {}).get("measure_header")
            and not str(other_sym.get("symbol_id", "")).startswith("repeat.")
        ]
        if measure_content_indices and idx > min(measure_content_indices):
            issues.append(
                ValidationIssue(
                    "REPEAT_START_POSITION_INVALID",
                    "repeat.start should appear before content symbols in its measure",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": measure},
                )
            )
        target_id = sym.get("modifiers", {}).get("repeat_span_to")
        if isinstance(target_id, str):
            explicit_target = symbol_index.get(target_id)
            if explicit_target:
                _target_idx, target_sym = explicit_target
                target_measure = int(target_sym.get("timing", {}).get("measure", 1))
                target_beat = float(target_sym.get("timing", {}).get("beat", 0))
                earlier_closing = any(
                    (
                        int(candidate.get("timing", {}).get("measure", 1)) > measure
                        or (
                            int(candidate.get("timing", {}).get("measure", 1)) == measure
                            and float(candidate.get("timing", {}).get("beat", 0)) > beat
                        )
                    )
                    and (
                        int(candidate.get("timing", {}).get("measure", 1)) < target_measure
                        or (
                            int(candidate.get("timing", {}).get("measure", 1)) == target_measure
                            and float(candidate.get("timing", {}).get("beat", 0)) < target_beat
                        )
                    )
                    for _other_idx, candidate in repeat_ends
                )
                if earlier_closing:
                    issues.append(
                        ValidationIssue(
                            "REPEAT_SPAN_TARGET_SKIPS_CLOSER_END",
                            f"repeat.start targets '{target_id}' even though a closer closing repeat sign exists",
                            f"/symbols/{idx}/modifiers/repeat_span_to",
                            "warning",
                            {"repeat_span_to": target_id},
                        )
                    )
            continue
        has_later_end = any(
            int(candidate.get("timing", {}).get("measure", 1)) > measure
            or (
                int(candidate.get("timing", {}).get("measure", 1)) == measure
                and float(candidate.get("timing", {}).get("beat", 0)) > beat
            )
            for _other_idx, candidate in repeat_ends
        )
        if target_id is None and has_later_end:
            issues.append(
                ValidationIssue(
                    "REPEAT_START_MISSING_SPAN_TARGET",
                    "repeat.start should explicitly target a later closing repeat sign",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"symbol_id": "repeat.start", "measure": measure, "beat": beat},
                )
            )
        if not has_later_end:
            issues.append(
                ValidationIssue(
                    "REPEAT_START_UNCLOSED",
                    "repeat.start does not have any later closing repeat sign",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"symbol_id": "repeat.start", "measure": measure, "beat": beat},
                )
            )

    for idx, sym in repeat_ends:
        timing = sym.get("timing", {})
        measure = int(timing.get("measure", 1))
        beat = float(timing.get("beat", 0))
        measure_content_indices = [
            other_idx
            for other_idx, other_sym in enumerate(symbols)
            if int(other_sym.get("timing", {}).get("measure", 1)) == measure
            and not other_sym.get("modifiers", {}).get("measure_header")
            and not str(other_sym.get("symbol_id", "")).startswith("repeat.")
        ]
        if measure_content_indices and idx < max(measure_content_indices):
            issues.append(
                ValidationIssue(
                    "REPEAT_END_POSITION_INVALID",
                    "closing repeat signs should appear after content symbols in their measure",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"measure": measure, "symbol_id": sym.get("symbol_id")},
                )
            )
        has_earlier_start = any(
            int(candidate.get("timing", {}).get("measure", 1)) < measure
            or (
                int(candidate.get("timing", {}).get("measure", 1)) == measure
                and float(candidate.get("timing", {}).get("beat", 0)) < beat
            )
            for _other_idx, candidate in repeat_starts
        )
        if not has_earlier_start:
            issues.append(
                ValidationIssue(
                    "REPEAT_END_ORPHANED",
                    f"{sym.get('symbol_id')} does not have any earlier repeat.start",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"symbol_id": sym.get("symbol_id"), "measure": measure, "beat": beat},
                )
            )

    for measure, entries in symbols_by_measure.items():
        repeat_entries = [(idx, sym) for idx, sym in entries if str(sym.get("symbol_id", "")).startswith("repeat.")]
        if not repeat_entries:
            continue
        has_repeat_start = any(_is_repeat_opening(catalog, sym.get("symbol_id", "")) for _idx, sym in repeat_entries)
        has_repeat_end = any(_is_repeat_closing(catalog, sym.get("symbol_id", "")) for _idx, sym in repeat_entries)
        if not (has_repeat_start and has_repeat_end):
            continue
        has_headers = any(sym.get("modifiers", {}).get("measure_header") for _idx, sym in entries)
        content_entries = [
            (idx, sym)
            for idx, sym in entries
            if not sym.get("modifiers", {}).get("measure_header") and not str(sym.get("symbol_id", "")).startswith("repeat.")
        ]
        non_rest_content = [
            (idx, sym) for idx, sym in content_entries if not str(sym.get("symbol_id", "")).startswith("music.rest.")
        ]
        rest_content = [
            (idx, sym) for idx, sym in content_entries if str(sym.get("symbol_id", "")).startswith("music.rest.")
        ]
        if not has_headers and not content_entries:
            for idx, _sym in repeat_entries:
                issues.append(
                    ValidationIssue(
                        "REPEAT_BOUNDARY_EMPTY_MEASURE",
                        "repeat boundaries should not wrap an otherwise empty measure",
                        f"/symbols/{idx}/symbol_id",
                        "warning",
                        {"measure": measure},
                    )
                )
        elif has_headers and not content_entries:
            for idx, _sym in repeat_entries:
                issues.append(
                    ValidationIssue(
                        "REPEAT_BOUNDARY_HEADER_ONLY_MEASURE",
                        "repeat boundaries should not wrap a measure that contains only headers and boundary signs",
                        f"/symbols/{idx}/symbol_id",
                        "warning",
                        {"measure": measure},
                    )
                )
        elif rest_content and not non_rest_content:
            for idx, _sym in repeat_entries:
                issues.append(
                    ValidationIssue(
                        "REPEAT_BOUNDARY_REST_ONLY_MEASURE",
                        "repeat boundaries should not wrap a measure that contains only rests",
                        f"/symbols/{idx}/symbol_id",
                        "warning",
                        {"measure": measure},
                    )
                )

    for idx, sym, spec in primary_body_entries:
        timing = sym.get("timing", {})
        measure = int(timing.get("measure", 1))
        beat = float(timing.get("beat", 0))
        end = beat + float(timing.get("duration_beats", 0))
        body_part = sym.get("body_part")
        for other_idx, other_sym, other_spec in primary_body_entries:
            if other_idx <= idx:
                continue
            if other_sym.get("body_part") != body_part:
                continue
            other_timing = other_sym.get("timing", {})
            other_measure = int(other_timing.get("measure", 1))
            other_beat = float(other_timing.get("beat", 0))
            other_end = other_beat + float(other_timing.get("duration_beats", 0))
            if other_measure != measure:
                continue
            if other_beat >= end or beat >= other_end:
                continue
            issues.append(
                ValidationIssue(
                    "BODY_PART_SIMULTANEITY_CONFLICT",
                    f"body_part '{body_part}' has overlapping primary motion symbols '{sym.get('symbol_id')}' and '{other_sym.get('symbol_id')}'",
                    f"/symbols/{other_idx}/timing/beat",
                    "warning",
                    {
                        "body_part": body_part,
                        "conflicts_with": sym.get("symbol_id"),
                        "suggested_beat": end,
                        "staff_columns": [
                            spec.get("geometry", {}).get("staff_column"),
                            other_spec.get("geometry", {}).get("staff_column"),
                        ],
                    },
                )
            )
            if sym.get("direction") != other_sym.get("direction") or sym.get("level") != other_sym.get("level"):
                issues.append(
                    ValidationIssue(
                        "BODY_PART_DIRECTION_LEVEL_CONFLICT",
                        f"body_part '{body_part}' carries conflicting simultaneous direction/level semantics between '{sym.get('symbol_id')}' and '{other_sym.get('symbol_id')}'",
                        f"/symbols/{other_idx}/timing/beat",
                        "warning",
                        {
                            "body_part": body_part,
                            "conflicts_with": sym.get("symbol_id"),
                            "suggested_beat": end,
                            "left_direction": sym.get("direction"),
                            "right_direction": other_sym.get("direction"),
                            "left_level": sym.get("level"),
                            "right_level": other_sym.get("level"),
                        },
                    )
                )

    annotation_entries: list[tuple[int, dict, str]] = []
    for idx, sym in enumerate(symbols):
        spec = catalog.get(sym.get("symbol_id", ""), {})
        column = spec.get("geometry", {}).get("staff_column")
        if column in {"timing", "quality"}:
            annotation_entries.append((idx, sym, column))
    for idx, sym, column in annotation_entries:
        modifiers = sym.get("modifiers", {})
        attach_to = modifiers.get("attach_to")
        if not isinstance(attach_to, str):
            continue
        timing = sym.get("timing", {})
        measure = int(timing.get("measure", 1))
        beat = float(timing.get("beat", 0))
        for other_idx, other_sym, other_column in annotation_entries:
            if other_idx <= idx or other_column != column:
                continue
            other_modifiers = other_sym.get("modifiers", {})
            if other_modifiers.get("attach_to") != attach_to:
                continue
            other_timing = other_sym.get("timing", {})
            if int(other_timing.get("measure", 1)) != measure or float(other_timing.get("beat", 0)) != beat:
                continue
            pair = frozenset({sym.get("symbol_id", ""), other_sym.get("symbol_id", "")})
            if column == "timing" and pair in CONFLICTING_TIMING_SYMBOLS:
                issues.append(
                    ValidationIssue(
                        "TIMING_COMPANION_CONFLICT",
                        f"timing companions '{sym.get('symbol_id')}' and '{other_sym.get('symbol_id')}' conflict on the same anchor and beat",
                        f"/symbols/{other_idx}/symbol_id",
                        "warning",
                        {"attach_to": attach_to, "conflicts_with": sym.get("symbol_id"), "measure": measure, "beat": beat},
                    )
                )
            if column == "quality" and pair in CONFLICTING_QUALITY_SYMBOLS:
                issues.append(
                    ValidationIssue(
                        "QUALITY_COMPANION_CONFLICT",
                        f"quality companions '{sym.get('symbol_id')}' and '{other_sym.get('symbol_id')}' conflict on the same anchor and beat",
                        f"/symbols/{other_idx}/symbol_id",
                        "warning",
                        {"attach_to": attach_to, "conflicts_with": sym.get("symbol_id"), "measure": measure, "beat": beat},
                    )
                )

    for idx, sym in enumerate(symbols):
        sid = str(sym.get("symbol_id", ""))
        if not sid.startswith("music.rest."):
            continue
        if sym.get("modifiers", {}).get("measure_header"):
            continue
        timing = sym.get("timing", {})
        measure = int(timing.get("measure", 1))
        beat = float(timing.get("beat", 0))
        end = beat + float(timing.get("duration_beats", 0))
        for other_idx, other_sym in enumerate(symbols):
            if other_idx == idx:
                continue
            other_sid = str(other_sym.get("symbol_id", ""))
            if other_sid.startswith("music.rest."):
                continue
            if other_sym.get("modifiers", {}).get("measure_header"):
                continue
            if other_sid.startswith("repeat."):
                continue
            other_timing = other_sym.get("timing", {})
            if int(other_timing.get("measure", 1)) != measure:
                continue
            other_beat = float(other_timing.get("beat", 0))
            other_end = other_beat + float(other_timing.get("duration_beats", 0))
            if other_beat >= end or beat >= other_end:
                continue
            issues.append(
                ValidationIssue(
                    "REST_CONTENT_CONFLICT",
                    f"rest symbol '{sid}' overlaps active content '{other_sid}' in the same measure window",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"conflicts_with": other_sid, "measure": measure, "beat": beat},
                )
            )
            break

    for idx, sym in enumerate(symbols):
        sid = str(sym.get("symbol_id", ""))
        if sid not in {"timing.hold", "quality.sustained"}:
            continue
        modifiers = sym.get("modifiers", {})
        attach_to = modifiers.get("attach_to")
        if not isinstance(attach_to, str):
            continue
        target_entry = symbol_index.get(attach_to)
        if not target_entry:
            continue
        _target_idx, target_sym = target_entry
        target_timing = target_sym.get("timing", {})
        target_measure = int(target_timing.get("measure", 1))
        target_beat = float(target_timing.get("beat", 0))
        target_duration = float(target_timing.get("duration_beats", 0))
        target_end = target_beat + target_duration - 1.0
        target_measure_beats = measure_beats_by_measure.get(target_measure, MEASURE_BEATS)
        if target_end + 0.01 < target_measure_beats:
            continue
        target_body = target_sym.get("body_part")
        next_candidates = []
        for candidate in symbols:
            candidate_sid = str(candidate.get("symbol_id", ""))
            candidate_column = catalog.get(candidate_sid, {}).get("geometry", {}).get("staff_column")
            if candidate_column not in PRIMARY_MOTION_COLUMNS:
                continue
            candidate_timing = candidate.get("timing", {})
            if int(candidate_timing.get("measure", 1)) != target_measure + 1:
                continue
            if abs(float(candidate_timing.get("beat", 0)) - 1.0) > 0.01:
                continue
            if candidate.get("body_part") != target_body:
                continue
            next_candidates.append(candidate)
        if not next_candidates:
            continue
        continued = any(
            other.get("symbol_id") == sid and other.get("modifiers", {}).get("attach_to") == candidate.get("symbol_id")
            for candidate in next_candidates
            for other in symbols
        )
        if continued:
            continue
        if sid == "timing.hold":
            issues.append(
                ValidationIssue(
                    "HOLD_CONTINUATION_MISSING",
                    "timing.hold reaches the end of a measure but is not continued onto the next measure's matching motion",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"attach_to": attach_to, "measure": target_measure, "body_part": target_body},
                )
            )
        elif sid == "quality.sustained":
            issues.append(
                ValidationIssue(
                    "SUSTAINED_QUALITY_CONTINUATION_MISSING",
                    "quality.sustained reaches the end of a measure but is not continued onto the next measure's matching motion",
                    f"/symbols/{idx}/symbol_id",
                    "warning",
                    {"attach_to": attach_to, "measure": target_measure, "body_part": target_body},
                )
            )

    return _normalize_semantic_issue_severities(issues)


def validate_ir(data: dict) -> dict:
    issues = validate_schema(data) + validate_semantic(data)
    return {
        "ok": not any(i.severity == "error" for i in issues),
        "issues": [i.to_dict() for i in issues],
        "repair_hints": build_repair_hints(issues),
    }


def build_repair_hints(issues: list[ValidationIssue]) -> list[dict]:
    hints = []
    for issue in issues:
        if issue.code == "UNKNOWN_SYMBOL":
            hints.append({"action": "replace_symbol", "path": issue.path, "message": "Use a symbol from symbol_catalog"})
        elif issue.code == "TIMING_DURATION":
            hints.append({"action": "set_duration", "path": issue.path, "value": 1.0})
        elif issue.code == "TIMING_MEASURE_OVERFLOW":
            if issue.details.get("carry_duration", 0.0) > 0:
                hints.append(
                    {
                        "action": "split_duration",
                        "path": issue.path,
                        "value": issue.details.get("max_duration", 1.0) or 1.0,
                        "carry_duration": issue.details.get("carry_duration", 0.0),
                        "next_measure": issue.details.get("next_measure"),
                    }
                )
            hints.append({"action": "set_duration", "path": issue.path, "value": issue.details.get("max_duration", 1.0) or 1.0})
        elif issue.code in {"REPEAT_START_UNCLOSED", "REPEAT_END_ORPHANED"}:
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove the orphaned repeat sign or add its matching counterpart"})
        elif issue.code == "REPEAT_START_SLOT_DUPLICATE":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove duplicate opening repeat signs occupying the same beat slot"})
        elif issue.code == "REPEAT_END_SLOT_DUPLICATE":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove duplicate closing repeat signs occupying the same beat slot"})
        elif issue.code == "REPEAT_SLOT_MIXED_BOUNDARY_CONFLICT":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove the conflicting repeat boundary sign so a slot is either opening or closing, not both"})
        elif issue.code == "REPEAT_START_NESTED_UNSUPPORTED":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove nested repeat.start because nested repeat structures are not supported"})
        elif issue.code == "REPEAT_START_MISSING_SPAN_TARGET":
            hints.append({"action": "retarget_repeat_span", "path": issue.path, "message": "Fill repeat_span_to with the nearest later closing repeat sign"})
        elif issue.code == "REPEAT_SPAN_TARGET_SKIPS_CLOSER_END":
            hints.append({"action": "retarget_repeat_span", "path": issue.path, "message": "Retarget repeat_span_to to the nearest later closing repeat sign"})
        elif issue.code == "MUSIC_TIME_SIGNATURE_REDUNDANT":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove redundant consecutive time signature headers when the meter does not change"})
        elif issue.code == "MUSIC_TEMPO_REDUNDANT":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove redundant consecutive tempo headers when the tempo does not change"})
        elif issue.code == "MUSIC_CADENCE_REDUNDANT":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove redundant consecutive cadence headers when the cadence label does not change"})
        elif issue.code == "MUSIC_TEMPO_VALUE_MISSING":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "tempo", "value": issue.details.get("suggested_tempo", 120)})
        elif issue.code == "MUSIC_TEMPO_CONTINUATION_VALUE_MISSING":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "tempo", "value": issue.details.get("suggested_tempo", 120)})
        elif issue.code == "MUSIC_CADENCE_LABEL_MISSING":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "label", "value": issue.details.get("suggested_label", "rit.")})
        elif issue.code == "MUSIC_CADENCE_CONTINUATION_LABEL_MISSING":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "label", "value": issue.details.get("suggested_label", "rit.")})
        elif issue.code == "PIN_VARIANT_HEAD_REQUIRED":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "pin_head", "value": issue.details.get("suggested_pin_head", "diamond")})
        elif issue.code == "SEPARATOR_VARIANT_MODE_REQUIRED":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "separator_mode", "value": issue.details.get("suggested_separator_mode", "single")})
        elif issue.code == "SYMBOL_DIRECTION_REQUIRED":
            hints.append({"action": "set_direction", "path": issue.path, "value": "forward"})
        elif issue.code == "SYMBOL_LEVEL_REQUIRED":
            hints.append({"action": "set_level", "path": issue.path, "value": "middle"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_MISSING":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Remove attach_to or point it to an existing earlier symbol id"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_FUTURE":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to an existing symbol at or before the current beat"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_MEASURE_MISMATCH":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to a primary motion symbol in the same measure"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_OUTSIDE_COVERAGE":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to a primary motion whose duration still covers the annotation beat"})
        elif issue.code == "MODIFIER_ATTACH_MISSING_FOR_ANNOTATION":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Attach annotation symbols to the nearest earlier primary motion, preferably on the same body_part"})
        elif issue.code == "MODIFIER_ATTACH_SOURCE_ROLE":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Remove attach_to from symbols that are not attachment-capable families"})
        elif issue.code == "MODIFIER_ATTACH_SIDE_ORPHANED":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Remove attach_side when there is no attach_to target"})
        elif issue.code == "MODIFIER_ATTACH_BODY_PART_MISMATCH":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to a primary motion symbol on the same body_part"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_ROLE":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to a primary motion symbol"})
        elif issue.code == "MODIFIER_ATTACH_FAMILY_INCOMPATIBLE":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Remove attach_to from music/repeat families until family-specific anchor semantics are modeled"})
        elif issue.code == "MODIFIER_ATTACH_TARGET_FAMILY_INCOMPATIBLE":
            hints.append({"action": "retarget_attachment", "path": issue.path, "message": "Retarget attach_to to a primary family allowed by the source symbol behavior metadata"})
        elif issue.code == "MODIFIER_ATTACH_SIDE_PREFERRED_MISMATCH":
            hints.append({"action": "set_modifier", "path": issue.path, "key": "attach_side", "value": issue.details.get("suggested_attach_side", "auto")})
        elif issue.code == "MODIFIER_REPEAT_SPAN_TARGET_MISSING":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Remove repeat_span_to or set it to an existing later repeat symbol id"})
        elif issue.code == "MODIFIER_REPEAT_SPAN_SOURCE_ROLE":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Use repeat_span_to only on repeat.start or repeat.generic symbols"})
        elif issue.code == "MODIFIER_REPEAT_SPAN_TARGET_ORDER":
            hints.append({"action": "retarget_repeat_span", "path": issue.path, "message": "Set repeat_span_to to a later repeat symbol id"})
        elif issue.code == "MODIFIER_REPEAT_SPAN_TARGET_ROLE":
            hints.append({"action": "retarget_repeat_span", "path": issue.path, "message": "Set repeat_span_to to a repeat-family symbol"})
        elif issue.code == "MODIFIER_REPEAT_SPAN_TARGET_VARIANT":
            hints.append({"action": "retarget_repeat_span", "path": issue.path, "message": "Retarget repeat_span_to to a closing repeat symbol such as repeat.end"})
        elif issue.code == "MODIFIER_MEASURE_HEADER_UNSUPPORTED":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Use measure_header only on music-family symbols"})
        elif issue.code == "MODIFIER_MEASURE_HEADER_SYMBOL_ROLE":
            hints.append({"action": "remove_modifier", "path": issue.path, "message": "Reserve measure_header for time signatures, tempo marks, and cadence marks"})
        elif issue.code == "MEASURE_HEADER_FAMILY_DUPLICATE":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove duplicate header signs of the same family within one measure"})
        elif issue.code == "MEASURE_HEADER_ORDER_INVALID":
            hints.append({"action": "reorder_measure_headers", "path": issue.path, "message": "Reorder measure headers to time signature, then tempo, then cadence"})
        elif issue.code == "MEASURE_HEADER_POSITION_INVALID":
            hints.append({"action": "reorder_measure_headers", "path": issue.path, "message": "Move measure headers before content symbols in the same measure"})
        elif issue.code in {"REPEAT_START_POSITION_INVALID", "REPEAT_END_POSITION_INVALID"}:
            hints.append({"action": "reorder_repeat_boundaries", "path": issue.path, "message": "Move repeat boundary signs to the edges of their measure content"})
        elif issue.code == "MODIFIER_MEASURE_HEADER_BODY_PART":
            hints.append({"action": "set_body_part", "path": issue.path, "value": "torso"})
        elif issue.code == "REPEAT_BODY_PART_INVALID":
            hints.append({"action": "set_body_part", "path": issue.path, "value": "torso"})
        elif issue.code == "REPEAT_START_TIMING":
            hints.append({"action": "set_beat", "path": issue.path, "value": issue.details.get("suggested_beat", 1.0)})
        elif issue.code == "REPEAT_END_TIMING":
            hints.append({"action": "set_beat", "path": issue.path, "value": issue.details.get("suggested_beat", 1.0)})
        elif issue.code == "MODIFIER_MEASURE_HEADER_TIMING":
            hints.append({"action": "set_beat", "path": issue.path, "value": 1.0})
        elif issue.code == "BODY_PART_SIMULTANEITY_CONFLICT":
            hints.append({"action": "set_beat", "path": issue.path, "value": issue.details.get("suggested_beat", 1.0)})
        elif issue.code == "BODY_PART_DIRECTION_LEVEL_CONFLICT":
            hints.append({"action": "set_beat", "path": issue.path, "value": issue.details.get("suggested_beat", 1.0)})
        elif issue.code in {"TIMING_COMPANION_CONFLICT", "QUALITY_COMPANION_CONFLICT"}:
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove the later conflicting companion symbol on the same anchor and beat"})
        elif issue.code == "REST_CONTENT_CONFLICT":
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove the rest symbol because active content already occupies the same measure window"})
        elif issue.code in {"REPEAT_BOUNDARY_EMPTY_MEASURE", "REPEAT_BOUNDARY_HEADER_ONLY_MEASURE", "REPEAT_BOUNDARY_REST_ONLY_MEASURE"}:
            hints.append({"action": "remove_symbol", "path": issue.path, "message": "Remove repeat boundaries from measures that contain no repeatable movement content"})
        elif issue.code in {"HOLD_CONTINUATION_MISSING", "SUSTAINED_QUALITY_CONTINUATION_MISSING"}:
            hints.append({"action": "insert_continuation_symbol", "path": issue.path, "message": "Insert the missing continuation companion on the next measure's matching motion"})
    hints.sort(
        key=lambda hint: (
            REPAIR_ACTION_PRIORITY.get(hint.get("action", ""), 99),
            hint.get("path", ""),
            str(hint.get("key", "")),
            str(hint.get("value", "")),
        )
    )
    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for hint in hints:
        signature = (hint.get("action", ""), hint.get("path", ""), str(hint.get("key", "")))
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(hint)
    return deduped
