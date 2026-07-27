#!/usr/bin/env python3
"""Fetch the ICKL proceedings and technical reports into references/ickl/.

The PDFs are third-party publications (~56 MB) and are gitignored, so this
script is how a fresh checkout gets them. See references/ickl/README.md for
what they do and do not settle.

ickl.org returns 403 to requests without a browser User-Agent.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

BASE = "https://ickl.org/wp-content/uploads"

DOCUMENTS = {
    "2017_Technical_Report_Addendum.pdf": f"{BASE}/2022/07/2017_Technical_Report_Addendum.pdf",
    "Proceedings_ICKL22_web.pdf":         f"{BASE}/2025/01/Proceedings_ICKL22_web.pdf",
    "Proceedings_ICKL_2019_web.pdf":      f"{BASE}/2026/03/Proceedings_ICKL_2019_web.pdf",
    "Proceedings_ICKL_2017_web.pdf":      f"{BASE}/2020/03/Proceedings_ICKL_2017_web.pdf",
    "Proceedings_ICKL_2015_web.pdf":      f"{BASE}/2017/07/Proceedings_ICKL_2015_web.pdf",
    "Proceedings2013_web.pdf":            f"{BASE}/2016/01/Proceedings2013_web.pdf",
    "Proceedings_ICKL_2011_web.pdf":      f"{BASE}/2014/02/Proceedings_ICKL_2011_web.pdf",
}

USER_AGENT = "Mozilla/5.0 (compatible; DancenotationMCP reference fetcher)"


def fetch(name: str, url: str, dest_dir: Path) -> bool:
    dest = dest_dir / name
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"  skip     {name} (already present)")
        return True
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
    except Exception as exc:  # noqa: BLE001 - report and continue to the next file
        print(f"  FAILED   {name}: {exc}")
        return False
    if not body.startswith(b"%PDF"):
        # A 403 or an error page still arrives with a 200 in some configs.
        print(f"  FAILED   {name}: response was not a PDF ({len(body)} bytes)")
        return False
    dest.write_bytes(body)
    print(f"  fetched  {name}  {len(body) / 1_048_576:.1f} MB")
    return True


def main() -> int:
    dest_dir = Path(__file__).resolve().parent / "ickl"
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {len(DOCUMENTS)} ICKL documents into {dest_dir}")
    failures = [n for n, u in DOCUMENTS.items() if not fetch(n, u, dest_dir)]
    if failures:
        print(f"\n{len(failures)} document(s) failed: {', '.join(failures)}")
        print("Check https://ickl.org/publications/ — URLs move between years.")
        return 1
    print("\nAll documents present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
