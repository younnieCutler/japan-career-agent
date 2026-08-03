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
        r"(?:합격\s*확률|서류\s*통과\s*(?:확률|율)|면접\s*(?:진입|통과)\s*(?:확률|율)|"
        r"오퍼\s*(?:확률|율)|내정\s*(?:확률|율))\s*[:=：]?\s*" + _PERCENT
    ),
    re.compile(
        r"(?:書類通過(?:率|確率)|面接(?:進入|通過)(?:率|確率)|内定(?:率|確率)|"
        r"オファー(?:率|確率))\s*[:=：]?\s*" + _PERCENT
    ),
)
