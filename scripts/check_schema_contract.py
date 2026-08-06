#!/usr/bin/env python3
"""Check that the shared catalog is a valid executable JSON Schema contract."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "_shared") not in sys.path:
    sys.path.insert(0, str(ROOT / "_shared"))

from schema_contract import SCHEMA_NAMES, load_catalog  # noqa: E402


def main() -> int:
    try:
        catalog = load_catalog()
    except ValueError as exc:
        print(f"schema contract: FAIL ({exc})")
        return 1
    print(f"schema contract: PASS (Draft 2020-12, {len(SCHEMA_NAMES)} definitions)")
    print("definitions: " + ", ".join(sorted(catalog["$defs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
