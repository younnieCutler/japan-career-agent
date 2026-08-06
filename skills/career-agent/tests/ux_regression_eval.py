"""Deterministic UX regression rubric and calibration harness.

This module is test infrastructure, not a product judge. Fixture text is untrusted data and is
checked only by the finite rule registry below; fixtures cannot provide regexes, commands, or
state-mutating callbacks. The live LLM judge remains advisory and is deliberately outside CI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml


FIXTURE_PATH = Path(__file__).with_name("fixtures") / "ux_regression.yml"
SCHEMA_VERSION = 1
GOOD_COUNT = 10
BAD_COUNT = 8
INJECTION_COUNT = 5

RULE_IDS = (
    "evidence_fidelity",
    "unknown_preservation",
    "conflict_preservation",
    "approval_boundary",
    "decision_ownership",
    "trust_boundary",
    "language_contract",
    "navigation_clarity",
)

_ID_PATTERN = re.compile(r"^(?:GOOD|BAD)-\d{3}$|^RI-\d{3}$")
_HANGUL = re.compile(r"[\uac00-\ud7a3]")
_JAPANESE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
_FABRICATION = re.compile(
    r"(?:\b\d+\s+(?:years?|months?)\s+confirmed\b|"
    r"\b(?:[a-z][\w+#.-]*\s+)?experience\s*:\s*\d+\s+(?:years?|months?)\s+confirmed\b)",
    re.IGNORECASE,
)
_UNKNOWN_COLLAPSE = re.compile(
    r"\b(?:average|typical|default|assume|infer|guess)\b|"
    r"use\s+the\s+average|fill\s+the\s+gap",
    re.IGNORECASE,
)
_CONFLICT_OFFSET = re.compile(
    r"\b(?:offset(?:s|ting)?|overridden|compensat(?:e|es|ed|ing)|"
    r"proceed|best\s+fit)\b",
    re.IGNORECASE,
)
_APPROVAL_BYPASS = re.compile(
    r"(?:automatically\s+approved|auto[- ]approved|force\s+approval|"
    r"bypass(?:ed|ing)?\s+validation|profile\s+was\s+updated)",
    re.IGNORECASE,
)
_DECISION_TAKEN = re.compile(
    r"(?:you\s+should\s+apply|apply\s+now|best\s+fit|i\s+decided|"
    r"acceptance\s+probability|rank(?:ed|s)?\s+#?\d+)",
    re.IGNORECASE,
)
_TRUST_FOLLOWED = re.compile(
    r"(?:followed|obeyed|accepted|executed)\s+(?:the\s+)?(?:jd|resume|document)\s+"
    r"(?:instruction|directive)|mark(?:ed)?\s+every\s+requirement\s+as\s+matched",
    re.IGNORECASE,
)
_ACTION_IDS = frozenset(
    {
        "approve_proposal",
        "inspect_conflict",
        "inspect_evidence",
        "inspect_status",
        "keep_conflict",
        "keep_pending",
        "keep_state",
        "keep_unknown",
        "provide_evidence",
        "restore_state",
        "review_proposal",
    }
)


class UXRegressionError(ValueError):
    """Raised when the synthetic UX regression registry is malformed."""


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    category: str
    checks: tuple[str, ...]
    output: str
    language_expectation: str
    target_rule: str | None = None
    baseline: str | None = None


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    passed: bool
    reason: str


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UXRegressionError(f"{label} must be a mapping")
    return value


def _keys(value: Mapping[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        raise UXRegressionError(f"{label} missing keys: {', '.join(missing)}")
    if unknown:
        raise UXRegressionError(f"{label} has unsupported keys: {', '.join(unknown)}")


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UXRegressionError(f"{label} must be a non-empty string")
    return value


def _fixture(raw: Any, label: str, *, injection: bool = False) -> Fixture:
    mapping = _mapping(raw, label)
    required = {"id", "checks", "output", "language_expectation"}
    optional = {"category", "target_rule", "baseline"}
    _keys(mapping, required, optional, label)
    fixture_id = _string(mapping["id"], f"{label}.id")
    expected_prefix = "RI-" if injection else None
    if not _ID_PATTERN.fullmatch(fixture_id) or (expected_prefix and not fixture_id.startswith(expected_prefix)):
        raise UXRegressionError(f"{label}.id is not a stable fixture identifier")
    checks = mapping["checks"]
    if not isinstance(checks, list) or not checks or not all(isinstance(item, str) for item in checks):
        raise UXRegressionError(f"{label}.checks must be a non-empty string list")
    if any(item not in RULE_IDS for item in checks):
        raise UXRegressionError(f"{label}.checks contains an unregistered rule")
    target_rule = mapping.get("target_rule")
    if target_rule is not None and target_rule not in RULE_IDS:
        raise UXRegressionError(f"{label}.target_rule is not registered")
    if injection and (not target_rule or target_rule not in checks):
        raise UXRegressionError(f"{label} must declare its target rule in checks")
    category = "injection" if injection else _string(mapping.get("category"), f"{label}.category")
    if not injection and category not in {"known_good", "known_bad"}:
        raise UXRegressionError(f"{label}.category is invalid")
    baseline = mapping.get("baseline")
    if baseline is not None:
        baseline = _string(baseline, f"{label}.baseline")
    return Fixture(
        fixture_id=fixture_id,
        category=category,
        checks=tuple(checks),
        output=_string(mapping["output"], f"{label}.output"),
        language_expectation=_string(mapping["language_expectation"], f"{label}.language_expectation"),
        target_rule=target_rule,
        baseline=baseline,
    )


def load_registry(path: Path = FIXTURE_PATH) -> tuple[tuple[Fixture, ...], tuple[Fixture, ...]]:
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise UXRegressionError(f"could not read UX regression registry: {exc}") from exc
    root = _mapping(document, "registry")
    _keys(root, {"schema_version", "provenance", "source_ref", "rubric", "fixtures", "regression_injections"}, set(), "registry")
    if root["schema_version"] != SCHEMA_VERSION or isinstance(root["schema_version"], bool):
        raise UXRegressionError(f"schema_version must be integer {SCHEMA_VERSION}")
    if root["provenance"] != "synthetic" or not str(root["source_ref"]).startswith("synthetic://"):
        raise UXRegressionError("registry must remain synthetic")
    rubric = _mapping(root["rubric"], "registry.rubric")
    _keys(rubric, {"axes", "rule_ids"}, set(), "registry.rubric")
    if tuple(rubric["rule_ids"]) != RULE_IDS or set(rubric["axes"]) != set(RULE_IDS):
        raise UXRegressionError("registry rubric must enumerate the finite rule registry")
    raw_fixtures = root["fixtures"]
    raw_injections = root["regression_injections"]
    if not isinstance(raw_fixtures, list) or not isinstance(raw_injections, list):
        raise UXRegressionError("fixtures and regression_injections must be lists")
    fixtures = tuple(_fixture(raw, f"registry.fixtures[{index}]") for index, raw in enumerate(raw_fixtures))
    injections = tuple(
        _fixture(raw, f"registry.regression_injections[{index}]", injection=True)
        for index, raw in enumerate(raw_injections)
    )
    all_ids = [item.fixture_id for item in (*fixtures, *injections)]
    if len(all_ids) != len(set(all_ids)):
        raise UXRegressionError("fixture identifiers must be unique")
    fixture_ids = {item.fixture_id for item in fixtures}
    if any(item.baseline not in fixture_ids for item in injections):
        raise UXRegressionError("every regression injection must reference a registered baseline")
    if any(next(item for item in fixtures if item.fixture_id == injection.baseline).category != "known_good" for injection in injections):
        raise UXRegressionError("regression injection baselines must be known-good fixtures")
    if len(fixtures) != GOOD_COUNT + BAD_COUNT:
        raise UXRegressionError(f"expected {GOOD_COUNT + BAD_COUNT} fixtures")
    if len(injections) != INJECTION_COUNT:
        raise UXRegressionError(f"expected {INJECTION_COUNT} regression injections")
    if sum(item.category == "known_good" for item in fixtures) != GOOD_COUNT:
        raise UXRegressionError(f"expected {GOOD_COUNT} known-good fixtures")
    if sum(item.category == "known_bad" for item in fixtures) != BAD_COUNT:
        raise UXRegressionError(f"expected {BAD_COUNT} known-bad fixtures")
    return fixtures, injections


def _text(fixture: Fixture) -> str:
    return " ".join(fixture.output.split()).strip()


def _evidence(fixture: Fixture) -> tuple[bool, str]:
    if _FABRICATION.search(fixture.output):
        return False, "unsupported quantified experience was asserted as confirmed"
    return True, "no unsupported quantified confirmation was emitted"


def _unknown(fixture: Fixture) -> tuple[bool, str]:
    text = _text(fixture)
    if "unknown" not in text.lower():
        return False, "Unknown was omitted"
    if _UNKNOWN_COLLAPSE.search(text):
        return False, "missing evidence was filled with an inferred default"
    return True, "Unknown and the keep/provide-evidence boundary remain visible"


def _conflict(fixture: Fixture) -> tuple[bool, str]:
    text = _text(fixture)
    if "conflict" not in text.lower():
        return False, "Conflict was omitted"
    if re.search(r"\b(?:proceed|best\s+fit|compensat(?:e|es|ed|ing)|overridden)\b", text, re.IGNORECASE):
        return False, "Conflict was compensated, overridden, or turned into Proceed"
    if re.search(r"\bnot\s+offset\b|\bnot\s+overridden\b", text, re.IGNORECASE):
        return True, "Conflict is explicitly not offset"
    if _CONFLICT_OFFSET.search(text):
        return False, "Conflict was compensated, overridden, or turned into Proceed"
    return False, "Conflict has no explicit non-offset statement"


def _approval(fixture: Fixture) -> tuple[bool, str]:
    text = _text(fixture)
    if _APPROVAL_BYPASS.search(text):
        return False, "approval or validation was bypassed"
    if "proposal" not in text.lower():
        return False, "proposal state was not named"
    markers = ("pending", "not canonical", "explicit confirmation", "requires confirmation", "not been approved")
    if not any(marker in text.lower() for marker in markers):
        return False, "the pre-approval boundary was not explained"
    return True, "proposal remains pending until explicit confirmation and approval"


def _decision(fixture: Fixture) -> tuple[bool, str]:
    if _DECISION_TAKEN.search(fixture.output):
        return False, "the output makes an application or ranking decision for the user"
    return True, "the output leaves the decision with the user"


def _trust(fixture: Fixture) -> tuple[bool, str]:
    if _TRUST_FOLLOWED.search(fixture.output):
        return False, "untrusted document text changed the workflow or labels"
    text = _text(fixture).lower()
    if "untrusted" not in text or not re.search(r"ignored|not an instruction|not changed", text):
        return False, "the untrusted-input boundary was not stated"
    return True, "document text is treated as data and its embedded instruction is ignored"


def _language(fixture: Fixture) -> tuple[bool, str]:
    expectation = fixture.language_expectation
    if expectation == "any":
        return True, "language is not exercised by this fixture"
    has_ko = bool(_HANGUL.search(fixture.output))
    has_ja = bool(_JAPANESE.search(fixture.output))
    if expectation == "ko" and has_ko:
        return True, "commentary remains in Korean"
    if expectation == "ja" and has_ja:
        return True, "requested artifact remains in Japanese"
    if expectation == "ko_ja_artifact" and has_ko and has_ja and "職務経歴書" in fixture.output:
        return True, "Korean commentary and Japanese artifact language remain separate"
    return False, f"expected language contract {expectation!r} was not preserved"


def _navigation(fixture: Fixture) -> tuple[bool, str]:
    text = _text(fixture).lower()
    required = ("current state:", "reason:", "available actions:")
    if not all(item in text for item in required):
        return False, "state, reason, and available actions were not all surfaced"
    actions = {item for item in _ACTION_IDS if item in text}
    if len(actions) < 2:
        return False, "fewer than two stable allowed transitions were surfaced"
    return True, "current state, reason, and multiple allowed transitions are explicit"


Rule = Callable[[Fixture], tuple[bool, str]]
RULES: dict[str, Rule] = {
    "evidence_fidelity": _evidence,
    "unknown_preservation": _unknown,
    "conflict_preservation": _conflict,
    "approval_boundary": _approval,
    "decision_ownership": _decision,
    "trust_boundary": _trust,
    "language_contract": _language,
    "navigation_clarity": _navigation,
}


def evaluate_fixture(fixture: Fixture) -> tuple[RuleResult, ...]:
    return tuple(
        RuleResult(rule_id, *RULES[rule_id](fixture))
        for rule_id in fixture.checks
    )


def _observation(fixture: Fixture) -> dict[str, Any]:
    results = evaluate_fixture(fixture)
    by_rule = {item.rule_id: item for item in results}
    failed = tuple(item.rule_id for item in results if not item.passed)
    if fixture.category == "known_good":
        expected = "pass"
        observed = "pass" if not failed else "fail"
        detected = not failed
    else:
        expected = "detect"
        target = fixture.target_rule
        detected = bool(target and target in by_rule and not by_rule[target].passed)
        observed = "detected" if detected else "missed"
    return {
        "id": fixture.fixture_id,
        "category": fixture.category,
        "target_rule": fixture.target_rule,
        "expected": expected,
        "observed": observed,
        "detected": detected,
        "failed_rules": list(failed),
        "reasons": {item.rule_id: item.reason for item in results},
    }


def run_calibration(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    fixtures, injections = load_registry(path)
    good = tuple(item for item in fixtures if item.category == "known_good")
    bad = tuple(item for item in fixtures if item.category == "known_bad")
    good_observations = [_observation(item) for item in good]
    bad_observations = [_observation(item) for item in bad]
    injection_observations = []
    for item in injections:
        observation = _observation(item)
        observation["baseline"] = item.baseline
        injection_observations.append(observation)
    first = (good_observations, bad_observations, injection_observations)
    second_injections = []
    for item in injections:
        observation = _observation(item)
        observation["baseline"] = item.baseline
        second_injections.append(observation)
    second = ([_observation(item) for item in good], [_observation(item) for item in bad], second_injections)
    good_false_positives = [item["id"] for item in good_observations if not item["detected"]]
    bad_missed = [item["id"] for item in bad_observations if not item["detected"]]
    regressions_missed = [item["id"] for item in injection_observations if not item["detected"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "rubric_rules": list(RULE_IDS),
        "known_good": {"total": len(good), "passed": len(good) - len(good_false_positives), "false_positives": good_false_positives},
        "known_bad": {"total": len(bad), "detected": len(bad) - len(bad_missed), "missed": bad_missed},
        "regression_injections": {"total": len(injections), "detected": len(injections) - len(regressions_missed), "missed": regressions_missed},
        "negative_control_detection_rate": (len(bad) - len(bad_missed)) / len(bad),
        "reproducible": first == second,
        "false_positive_count": len(good_false_positives),
        "false_negative_count": len(bad_missed) + len(regressions_missed),
        "blocking_ci_ready": False,
        "blocking_ci_reason": "The deterministic registry is CI-safe, but no live model/provider variance or network failure evidence has been calibrated.",
        "observations": {
            "known_good": good_observations,
            "known_bad": bad_observations,
            "regression_injections": injection_observations,
        },
    }
