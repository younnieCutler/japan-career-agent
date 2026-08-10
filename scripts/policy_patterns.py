"""Shared detectors for candidate-outcome percentage claims.

Discussion of probability is allowed. These patterns only match an output-shaped
candidate outcome label followed by a numeric percentage.
"""

from __future__ import annotations

import re


_PERCENT = r"<?\s*\d+(?:[.,]\d+)?\s*(?:%|％)"

CANDIDATE_OUTCOME_PERCENTAGE_PATTERNS = (
    re.compile(
        r"\b(?:screening\s+(?:passage|pass|entry)|document\s+(?:screening|passage|pass|entry)|"
        r"interview\s+(?:entry|pass)|offer|hiring|pass)\s+"
        r"(?:probability|rate)\s*[:=]?\s*" + _PERCENT,
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:screening|document|interview|offer)\s+(?:passage|pass|entry|outcome)\s*"
        r"[:=]\s*" + _PERCENT,
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:합격\s*확률|서류\s*통과\s*(?:확률|율)|면접\s*(?:진입|통과)\s*(?:확률|율)|"
        r"오퍼\s*(?:확률|율)|내정\s*(?:확률|율))\s*[:=：]?\s*" + _PERCENT
    ),
    re.compile(
        r"(?:書類通過(?:率|確率)|面接(?:進入|通過)(?:率|確率)|内定(?:率|確率)|"
        r"オファー(?:率|確率))\s*[:=：]?\s*" + _PERCENT
    ),
)

# POLICY-004: a frozen legacy_v1 field constructed with a literal numeric value — a new code
# path fabricating a legacy-shaped score field instead of routing through
# `_shared/matching_v3.py` + `decision_status`. Deliberately narrow — it does not match the
# field name appearing in a Python set literal, a schema doc string, or a rejection message,
# only a quoted-field-name-immediately-followed-by-a-colon-and-a-digit construction shape.
BANNED_LEGACY_FIELD_NAMES = (
    "match_score", "predicted_tier", "culture_fit_score", "screening_probability",
    "platform_probability", "overall_score", "overall_grade",
    "hiring_probability", "acceptance_probability",
)
BANNED_OUTPUT_FIELD_PATTERNS = tuple(
    re.compile(r'["\']' + re.escape(name) + r'["\']\s*:\s*\d')
    for name in BANNED_LEGACY_FIELD_NAMES
)

# POLICY-007: a hook launcher command must resolve the plugin root at runtime, never bake in
# a specific installed version's cache directory (HOOK-005-A) — e.g. a marketplace cache path
# ending in a semver directory segment right before the scripts directory. `(?:segment/)+` (not
# a single segment) because a real Codex install nests the plugin name twice:
# `.codex/plugins/cache/japan-career-agent/japan-career-agent/1.6.1/scripts/...` — the
# original single-segment version of this pattern did not match that path.
VERSION_PINNED_CACHE_PATH_PATTERN = re.compile(
    r"plugins[/\\]cache[/\\](?:[^/\\'\"]+[/\\])+\d+\.\d+\.\d+[/\\]"
)

# STATIC-002: a hash-noqa with no rule code silences every rule on the line. Require a specific
# code so a future violation of a different rule on the same line is not hidden by accident.
BARE_NOQA_PATTERN = re.compile("#" + r"\s*noqa(?!\s*:)")
