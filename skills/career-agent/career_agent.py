#!/usr/bin/env python3
"""Thin CLI entry point for the behavior-preserving Career Agent runtime."""

from __future__ import annotations

import sys

import runtime as _runtime

# Canonical context allowlist remains defined by the compatibility runtime:
# CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")

if __name__ == "__main__":
    raise SystemExit(_runtime.main())

# Preserve the historical import surface (including monkeypatch targets in integrations) while
# keeping CLI dispatch out of the runtime implementation. Importers receive the compatibility
# module so its globals and public function identities remain unchanged.
sys.modules[__name__] = _runtime
