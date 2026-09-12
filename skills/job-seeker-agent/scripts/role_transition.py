#!/usr/bin/env python3
"""Run the shared role-transition evaluator from a shipped Skill tree."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SHARED = PACKAGE_ROOT / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from role_transition import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
