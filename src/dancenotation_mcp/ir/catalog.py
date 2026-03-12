from __future__ import annotations

import json
from pathlib import Path


def load_symbol_catalog(base: Path | None = None) -> dict[str, dict]:
    if base is None:
        base = Path(__file__).resolve().parents[3] / "resources" / "symbol_catalog"
    catalog: dict[str, dict] = {}
    for p in sorted(base.glob("*.json")):
        items = json.loads(p.read_text())
        for item in items:
            catalog[item["id"]] = item
    return catalog
