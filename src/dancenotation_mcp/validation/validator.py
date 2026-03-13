from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from dancenotation_mcp.ir.catalog import load_symbol_catalog


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


def validate_semantic(data: dict) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    symbols = data.get("symbols", [])
    catalog = load_symbol_catalog()

    last_end = 0.0
    for idx, sym in enumerate(symbols):
        p = f"/symbols/{idx}"
        sid = sym.get("symbol_id")
        if sid not in catalog:
            issues.append(ValidationIssue("UNKNOWN_SYMBOL", f"Unknown symbol id '{sid}'", f"{p}/symbol_id", "error", {}))
        else:
            issues.extend(_validate_symbol_constraints(sym, catalog[sid], p))

        timing = sym.get("timing", {})
        beat = float(timing.get("beat", 0))
        dur = float(timing.get("duration_beats", 0))
        if dur <= 0:
            issues.append(ValidationIssue("TIMING_DURATION", "duration_beats must be > 0", f"{p}/timing/duration_beats", "error", {}))
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
        last_end = max(last_end, beat + dur)

    return issues


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
        elif issue.code == "SYMBOL_DIRECTION_REQUIRED":
            hints.append({"action": "set_direction", "path": issue.path, "value": "forward"})
        elif issue.code == "SYMBOL_LEVEL_REQUIRED":
            hints.append({"action": "set_level", "path": issue.path, "value": "middle"})
    return hints
