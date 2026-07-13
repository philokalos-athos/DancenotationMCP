from __future__ import annotations

import json
from pathlib import Path

_catalog_cache: dict[str, dict] | None = None


def load_symbol_catalog(base: Path | None = None) -> dict[str, dict]:
    global _catalog_cache
    if base is None and _catalog_cache is not None:
        return _catalog_cache
    if base is None:
        base = Path(__file__).resolve().parents[3] / "resources" / "symbol_catalog"
    catalog: dict[str, dict] = {}
    for p in sorted(base.glob("*.json")):
        items = json.loads(p.read_text())
        for item in items:
            catalog[item["id"]] = item
    if base == Path(__file__).resolve().parents[3] / "resources" / "symbol_catalog":
        _catalog_cache = catalog
    return catalog
