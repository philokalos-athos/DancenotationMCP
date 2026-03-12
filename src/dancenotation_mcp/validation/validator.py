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
