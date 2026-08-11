#!/usr/bin/env python3
"""Thin CLI entry point for the behavior-preserving Career Agent runtime."""

from __future__ import annotations

import sys

import runtime as _runtime

# Canonical context allowlist remains defined by the compatibility runtime:
# CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")

if __name__ == "__main__":
    raise SystemExit(_runtime.main())

# Preserve the historical import surface while keeping CLI dispatch out of the runtime
# implementation. Importers receive the compatibility module, so every name that ever resolved here
# still resolves and still refers to the same object.
#
# What that is NOT: a promise that patching a name here redirects the module that uses it. Since
# 2.2.0 the owner modules resolve their own imports, so `patch("career_agent.pipeline_file")`
# rebinds this module's attribute and nothing reads it. Patch the owner instead —
# `approvals.pipeline_file` for the approval writer. See docs/ARCHITECTURE_BOUNDARIES.md.
sys.modules[__name__] = _runtime
