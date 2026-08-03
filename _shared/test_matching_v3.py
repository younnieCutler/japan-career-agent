#!/usr/bin/env python3
"""Regression tests for the evidence-based v3 diagnosis (PRD §11 acceptance criteria).

    python3 _shared/test_matching_v3.py

Every test here maps to an AC. The two that matter most are the ones that would let the
old design back in: interest independence (AC-4) and the absence of any 0-100 fit number
in the default result (AC-7).

The MHLW fixture below is SYNTHETIC and named as such. It exists to test the distance
engine, not to stand in for the official 114-profile dataset — see `mhlw_reference.py`.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import legacy_experimental  # noqa: E402
import matching_v3 as v3  # noqa: E402
import mhlw_reference  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 9 elements, each >= 1, summing to 29.
BASE_ALLOCATION = {
    "current_state_assessment": 5,
    "task_setting": 4,
    "planning": 4,
    "task_execution": 5,
    "situational_response": 3,
    "internal_coordination": 3,
    "external_coordination": 2,
    "manager_response": 2,
    "subordinate_management": 1,
}


def fixture_dataset(tmp: Path) -> Path:
    """A deliberately synthetic reference file. Not MHLW data, and never presented as such."""
    import yaml

    keys = list(BASE_ALLOCATION.keys())
    profiles = []
    for index in range(114):
        allocation = dict(BASE_ALLOCATION)
        # Rotate which elements gain/lose points to create variety while keeping sum at 29
        shift_from = keys[index % len(keys)]
        shift_to = keys[(index + 1) % len(keys)]
        delta = min(allocation[shift_from] - 1, 3)  # never go below 1
        allocation[shift_from] -= delta
        allocation[shift_to] += delta
        assert sum(allocation.values()) == 29
        assert all(v >= 1 for v in allocation.values())
        profiles.append({"id": f"synthetic-{index}", "label": f"SYNTHETIC ROLE {index}", "allocation": allocation})
    path = tmp / "synthetic_profiles.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "dataset_version": "synthetic-test-fixture",
                "source": "test fixture — NOT MHLW data",
                "licence": "test fixture",
                "profiles": profiles,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path



def payload(**overrides):
    base = {
        "company_name": "B社",
        "position": "Product Analyst",
        "eligibility": [
            {"requirement": "勤務地", "candidate_evidence": "東京在住", "job_evidence": "東京勤務",
             "meets": True, "source": "observed", "source_type": "job_posting", "confidence": "high"},
        ],
        "skills": {
            "required": [
                {"name": "SQL", "status": "matched", "evidence": "3年", "source_type": "user"},
                {"name": "A/B testing", "status": "missing", "source_type": "job_posting"},
            ],
            "preferred": [],
            "experience": [],
        },
        "career_values": [
            {"value": "autonomy", "kind": "must_have", "satisfied": True,
             "company_evidence": "裁量あり (求人票)", "source_type": "job_posting", "confidence": "medium"},
        ],
        "portable_skill": {"allocation": dict(BASE_ALLOCATION), "level": 3},
        "candidate_interest": {"interest_level": None},
    }
    base.update(overrides)
    return base


OBJECTIVE_KEYS = ("decision_status", "decision_basis", "eligibility", "skills",
                  "portable_skill", "career_values", "missing_information")


class AllocationValidation(unittest.TestCase):
    """AC-1. MHLW input validation."""

    def test_sum_must_be_29(self):
        bad = dict(BASE_ALLOCATION, planning=BASE_ALLOCATION["planning"] + 1)
        with self.assertRaises(v3.ValidationError) as ctx:
            v3.validate_allocation(bad)
        self.assertIn("29", str(ctx.exception))

    def test_element_below_one_rejected(self):
        bad = dict(BASE_ALLOCATION, subordinate_management=0, task_execution=6)
        self.assertEqual(sum(bad.values()), 29)  # total is fine; the element is not
        with self.assertRaises(v3.ValidationError):
            v3.validate_allocation(bad)

    def test_missing_and_unknown_elements_rejected(self):
        short = {k: v for k, v in BASE_ALLOCATION.items() if k != "planning"}
        with self.assertRaises(v3.ValidationError):
            v3.validate_allocation(short)
        with self.assertRaises(v3.ValidationError):
            v3.validate_allocation(dict(BASE_ALLOCATION, level=3))

    def test_non_integer_rejected(self):
        with self.assertRaises(v3.ValidationError):
            v3.validate_allocation(dict(BASE_ALLOCATION, planning=4.0))

    def test_one_to_five_ratings_are_not_auto_converted(self):
        """Legacy 1-5 portable-skill data must not be silently reshaped into an allocation."""
        legacy_ratings = {key: 3 for key in v3.ALLOCATION_KEYS}  # sums to 27, not 29
        with self.assertRaises(v3.ValidationError):
            v3.validate_allocation(legacy_ratings)
        result = v3.portable_skill_result({"allocation": None, "level": 3})
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIn("not", result["reason"].lower())


class CompositionDistance(unittest.TestCase):
    """AC-2. MHLW calculation."""

    def test_identical_composition_is_zero(self):
        self.assertEqual(v3.composition_distance(BASE_ALLOCATION, dict(BASE_ALLOCATION)), 0.0)

    def test_same_proportions_different_units_are_equal(self):
        doubled = {key: value * 2 for key, value in BASE_ALLOCATION.items()}
        self.assertAlmostEqual(v3.composition_distance(BASE_ALLOCATION, doubled), 0.0, places=12)

    def test_level_is_excluded_from_the_distance_vector(self):
        low = v3.portable_skill_result({"allocation": dict(BASE_ALLOCATION), "level": 1})
        high = v3.portable_skill_result({"allocation": dict(BASE_ALLOCATION), "level": 5})
        self.assertEqual(low["composition"], high["composition"])
        self.assertEqual(low["level"], 1)
        self.assertEqual(high["level"], 5)
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(fixture_dataset(Path(tmp)))
            mapping = {"mapped_role_profile_id": "synthetic-1", "method": "manual",
                       "confidence": "high", "evidence": "fixture"}
            a = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION), "level": 1, "mhlw_mapping": mapping}, reference=reference)
            b = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION), "level": 5, "mhlw_mapping": mapping}, reference=reference)
        self.assertEqual(a["distance"], b["distance"])
        self.assertEqual(a["nearest_profiles"], b["nearest_profiles"])

    def test_no_zero_to_hundred_conversion_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(fixture_dataset(Path(tmp)))
            result = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION),
                 "mhlw_mapping": {"mapped_role_profile_id": "synthetic-0", "method": "manual",
                                  "confidence": "high", "evidence": "fixture"}},
                reference=reference)
        for key in walk_keys(result):
            self.assertNotIn("score", key.lower(), f"{key} looks like a converted score")
            self.assertNotIn("fit", key.lower(), f"{key} looks like a converted score")
        # A raw composition distance cannot exceed sqrt(2); anything on a 0-100 scale would.
        self.assertLessEqual(result["distance"], math_max_distance())
        self.assertIn("not a 0-100 fit score", result["note"])

    def test_ranking_is_stable_and_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(fixture_dataset(Path(tmp)))
            first = v3.rank_role_profiles(BASE_ALLOCATION, reference["profiles"])
            second = v3.rank_role_profiles(BASE_ALLOCATION, reference["profiles"])
        self.assertEqual(first, second)
        self.assertEqual([item["rank"] for item in first], list(range(1, len(first) + 1)))
        self.assertEqual(first, sorted(first, key=lambda item: (item["distance"], item["id"])))
        self.assertLessEqual(len(first), 5)


def math_max_distance() -> float:
    import math
    return math.sqrt(2)  # upper bound for the L2 distance between two unit-sum compositions


def walk_keys(node, prefix=""):
    """Every key path in a nested result, so a score field cannot hide one level down."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{prefix}{key}"
            yield from walk_keys(value, f"{prefix}{key}.")
    elif isinstance(node, list):
        for item in node:
            yield from walk_keys(item, prefix)


class ReferenceDataAvailability(unittest.TestCase):
    """PRD §7.3.2 / user constraint 7 — the 114-profile dataset is not fabricated."""

    def test_missing_dataset_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = mhlw_reference.load(Path(tmp) / "absent.yml")
        self.assertEqual(data["status"], "unavailable")
        self.assertEqual(data["profiles"], [])
        self.assertIn("licence", data["reason"].lower())

    def test_repo_ships_no_reference_dataset(self):
        self.assertFalse(mhlw_reference.DEFAULT_PATH.is_file(),
                         "an MHLW reference dataset appeared in the repo — verify its source and licence")

    def test_mapped_but_unavailable_dataset_is_reported_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(Path(tmp) / "absent.yml")
            result = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION),
                 "mhlw_mapping": {"mapped_role_profile_id": "kikaku", "method": "manual",
                                  "confidence": "high", "evidence": "JD 記載"}},
                reference=reference)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["distance"])
        self.assertIsNone(result["rank"])

    def test_unmapped_posting_produces_no_distance(self):
        result = v3.portable_skill_result({"allocation": dict(BASE_ALLOCATION)})
        self.assertEqual(result["status"], "unmapped")
        self.assertIsNone(result["distance"])

    def test_mapping_without_evidence_is_refused(self):
        result = v3.portable_skill_result({
            "allocation": dict(BASE_ALLOCATION),
            "mhlw_mapping": {"mapped_role_profile_id": "x", "method": "manual"},
        })
        self.assertEqual(result["status"], "unmapped")

    def test_heuristic_mapping_is_flagged_as_not_official(self):
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(fixture_dataset(Path(tmp)))
            result = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION),
                 "mhlw_mapping": {"mapped_role_profile_id": "synthetic-0", "method": "heuristic_mapping",
                                  "confidence": "low", "evidence": "LLM read of the JD"}},
                reference=reference)
        self.assertFalse(result["mapping"]["official_values"])
        self.assertIn("NOT official", result["mapping"]["warning"])

    def test_invalid_dataset_raises_rather_than_degrading(self):
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.yml"
            path.write_text(yaml.safe_dump({"profiles": [{"id": "a", "allocation": BASE_ALLOCATION}]}),
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                mhlw_reference.load(path)

    def test_full_114_fixture_is_available(self):
        """Verify the test fixture with 114 profiles returns 'available' status."""
        with tempfile.TemporaryDirectory() as tmp:
            reference = mhlw_reference.load(fixture_dataset(Path(tmp)))
        self.assertEqual(reference["status"], "available")
        self.assertIsNone(reference["expected_count_mismatch"])
        self.assertEqual(reference["profile_count"], 114)

    def test_partial_dataset_returns_partial_status(self):
        """A dataset with ≠114 profiles is 'partial', not 'available'."""
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.yml"
            profiles = [{"id": f"p-{i}", "label": f"ROLE {i}", "allocation": dict(BASE_ALLOCATION)}
                        for i in range(3)]
            path.write_text(yaml.safe_dump({
                "dataset_version": "partial-test", "source": "test", "licence": "test",
                "profiles": profiles,
            }, allow_unicode=True, sort_keys=False), encoding="utf-8")
            reference = mhlw_reference.load(path)
        self.assertEqual(reference["status"], "partial")
        self.assertIsNotNone(reference["expected_count_mismatch"])
        self.assertIn("3 profiles", reference["expected_count_mismatch"])

    def test_partial_dataset_suppresses_distance(self):
        """When the dataset is partial, portable_skill_result returns unavailable."""
        import yaml
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "small.yml"
            profiles = [{"id": f"p-{i}", "label": f"ROLE {i}", "allocation": dict(BASE_ALLOCATION)}
                        for i in range(10)]
            path.write_text(yaml.safe_dump({
                "dataset_version": "partial-test", "source": "test", "licence": "test",
                "profiles": profiles,
            }, allow_unicode=True, sort_keys=False), encoding="utf-8")
            reference = mhlw_reference.load(path)
            result = v3.portable_skill_result(
                {"allocation": dict(BASE_ALLOCATION),
                 "mhlw_mapping": {"mapped_role_profile_id": "p-0", "method": "manual",
                                  "confidence": "high", "evidence": "test"}},
                reference=reference)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["distance"])


class SkillCoverage(unittest.TestCase):
    """AC-3. Missing values."""

    def test_unknown_excluded_from_denominator(self):
        result = v3.skill_results({"required": [
            {"name": "SQL", "status": "matched"},
            {"name": "dbt", "status": "missing"},
            {"name": "presentation level", "status": "unknown"},
        ]})
        self.assertEqual(result["required_coverage"], 0.5)
        self.assertEqual(result["required_coverage_basis"],
                         {"confirmed_matched": 1, "confirmed_missing": 1, "unknown_excluded": 1})

    def test_no_confirmed_requirement_is_insufficient_data(self):
        result = v3.skill_results({"required": [{"name": "SQL", "status": "unknown"}]})
        self.assertEqual(result["required_coverage_status"], "insufficient_data")
        self.assertIsNone(result["required_coverage"])

    def test_all_unknown_never_becomes_a_pass(self):
        result = v3.evaluate(payload(skills={"required": [{"name": "SQL", "status": "unknown"}]}))
        self.assertEqual(result["decision_status"], v3.DECISION_REVIEW)
        self.assertIsNone(result["skills"]["required_coverage"])


class EligibilityTriState(unittest.TestCase):
    """AC-3 / FR-1. One-sided information is unknown, never a conflict and never a pass."""

    def test_missing_job_side_is_unknown(self):
        result = v3.eligibility_results([
            {"requirement": "日本語要求水準", "candidate_evidence": "N2", "job_evidence": None, "meets": False},
        ])
        self.assertEqual(result[0]["status"], "unknown")

    def test_missing_candidate_side_is_unknown(self):
        result = v3.eligibility_results([
            {"requirement": "在留資格", "candidate_evidence": None, "job_evidence": "ビザ支援なし", "meets": True},
        ])
        self.assertEqual(result[0]["status"], "unknown")

    def test_both_sides_confirmed_and_mismatched_is_conflict(self):
        result = v3.eligibility_results([
            {"requirement": "勤務地", "candidate_evidence": "大阪のみ", "job_evidence": "東京出社必須", "meets": False},
        ])
        self.assertEqual(result[0]["status"], "conflict")


class DecisionStatusRules(unittest.TestCase):
    """AC-5. Conflict rules."""

    def test_confirmed_hard_requirement_failure_is_conflict(self):
        result = v3.evaluate(payload(eligibility=[
            {"requirement": "勤務地", "candidate_evidence": "大阪のみ",
             "job_evidence": "東京出社必須", "meets": False},
        ]))
        self.assertEqual(result["decision_status"], v3.DECISION_CONFLICT)

    def test_must_have_violation_is_conflict(self):
        result = v3.evaluate(payload(career_values=[
            {"value": "リモート可", "kind": "must_have", "satisfied": False, "company_evidence": "full on-site"},
        ]))
        self.assertEqual(result["decision_status"], v3.DECISION_CONFLICT)

    def test_avoid_condition_present_is_conflict(self):
        result = v3.evaluate(payload(career_values=[
            {"value": "常駐SES", "kind": "avoid", "satisfied": True, "company_evidence": "客先常駐が中心"},
        ]))
        self.assertEqual(result["decision_status"], v3.DECISION_CONFLICT)

    def test_core_unknown_without_conflict_is_review(self):
        result = v3.evaluate(payload(eligibility=[
            {"requirement": "日本語要求水準", "candidate_evidence": "N2", "job_evidence": None, "meets": None},
        ]))
        self.assertEqual(result["decision_status"], v3.DECISION_REVIEW)
        self.assertIn("eligibility: 日本語要求水準", result["decision_basis"]["unknowns"])

    def test_conflicting_evidence_alone_is_review(self):
        result = v3.evaluate(payload(conflicting_evidence=["求人票は残業20h、口コミは45h"]))
        self.assertEqual(result["decision_status"], v3.DECISION_REVIEW)

    def test_clean_confirmed_input_is_proceed(self):
        self.assertEqual(v3.evaluate(payload())["decision_status"], v3.DECISION_PROCEED)

    def test_preferred_skill_unknown_does_not_force_review(self):
        result = v3.evaluate(payload(skills={
            "required": [{"name": "SQL", "status": "matched"}],
            "preferred": [{"name": "Looker", "status": "unknown"}],
        }))
        self.assertEqual(result["decision_status"], v3.DECISION_PROCEED)
        self.assertIn("preferred skill: Looker", result["missing_information"])

    def test_experience_unknown_triggers_review(self):
        """PRD: core required experience unknown → review, not proceed."""
        result = v3.evaluate(payload(skills={
            "required": [{"name": "SQL", "status": "matched"}],
            "experience": [{"name": "3年以上のPM経験", "status": "unknown"}],
        }))
        self.assertEqual(result["decision_status"], v3.DECISION_REVIEW)
        self.assertIn("experience: 3年以上のPM経験", result["decision_basis"]["unknowns"])

    def test_experience_unknown_in_missing_information(self):
        """Experience unknown should appear in both decision_basis and missing_information."""
        result = v3.evaluate(payload(skills={
            "required": [{"name": "SQL", "status": "matched"}],
            "experience": [{"name": "5年以上の開発経験", "status": "unknown"}],
        }))
        self.assertIn("experience: 5年以上の開発経験", result["missing_information"])


class InterestIndependence(unittest.TestCase):
    """AC-4. The whole reason the axis is separate."""

    def _objective(self, result):
        return {key: result[key] for key in OBJECTIVE_KEYS}

    def test_interest_1_to_5_changes_nothing_objective(self):
        low = v3.evaluate(payload(candidate_interest={"interest_level": 1, "interest_reason": "微妙"}))
        high = v3.evaluate(payload(candidate_interest={
            "interest_level": 5,
            "interest_reason": "説明会で印象が変わった",
            "interest_updated_at": "2026-08-01",
            "interest_evidence": [
                {"source": "event_experience", "note": "説明会", "observed_at": "2026-07-20"},
                {"source": "interview_experience", "note": "一次面接", "observed_at": "2026-08-01"},
            ],
        }))
        self.assertEqual(self._objective(low), self._objective(high))
        self.assertEqual(low["candidate_interest"]["interest_level"], 1)
        self.assertEqual(high["candidate_interest"]["interest_level"], 5)
        self.assertEqual(len(high["candidate_interest"]["interest_evidence"]), 2)

    def test_interest_5_does_not_turn_conflict_into_proceed(self):
        conflicting = payload(
            eligibility=[{"requirement": "勤務地", "candidate_evidence": "大阪のみ",
                          "job_evidence": "東京出社必須", "meets": False}],
            candidate_interest={"interest_level": 5, "interest_reason": "第一志望"},
        )
        self.assertEqual(v3.evaluate(conflicting)["decision_status"], v3.DECISION_CONFLICT)

    def test_absent_interest_stays_null(self):
        interest = v3.evaluate(payload())["candidate_interest"]
        self.assertIsNone(interest["interest_level"])
        self.assertIsNone(interest["interest_reason"])

    def test_decision_status_does_not_accept_interest(self):
        """A signature guard: re-adding interest as a parameter breaks this test on purpose."""
        import inspect
        params = set(inspect.signature(v3.decision_status).parameters)
        self.assertNotIn("candidate_interest", params)
        self.assertNotIn("interest_level", params)

    def test_invalid_interest_level_rejected(self):
        with self.assertRaises(v3.ValidationError):
            v3.candidate_interest({"interest_level": 0})
        with self.assertRaises(v3.ValidationError):
            v3.candidate_interest({"interest_level": 6})
        with self.assertRaises(v3.ValidationError):
            v3.candidate_interest({"interest_evidence": [{"source": "gut_feeling"}]})


class EmployerSignals(unittest.TestCase):
    """FR-6. Observed events only, no derived probability."""

    def test_signals_are_recorded_verbatim(self):
        result = v3.evaluate(payload(employer_signals=[
            {"type": "scout", "observed_at": "2026-07-01T09:00:00", "source": "doda"},
        ]))
        self.assertEqual(result["employer_signals"][0]["type"], "scout")
        self.assertNotIn("p_employer_interest", json.dumps(result))

    def test_absence_of_signals_is_not_a_negative(self):
        result = v3.evaluate(payload())
        self.assertEqual(result["employer_signals"], [])
        self.assertNotIn("employer", " ".join(result["missing_information"]).lower())

    def test_unknown_signal_type_rejected(self):
        with self.assertRaises(v3.ValidationError):
            v3.employer_signals([{"type": "vibes"}])


class NoLegacyScoresInDefaultResult(unittest.TestCase):
    """AC-6 / AC-7. The default output carries no composite score and no brand formula."""

    def test_no_score_fields(self):
        result = v3.evaluate(payload())
        blob = json.dumps(result, ensure_ascii=False).lower()
        for banned in ("recruit_style", "persol_style", "culture_fit", "overall_score",
                       "overall_grade", "match_score", "predicted_tier", "合格確率", "内定確率"):
            self.assertNotIn(banned, blob, f"{banned} leaked into the v3 result")
        self.assertEqual(result["model_version"], "evidence_based_v3")

    def test_no_numeric_total_anywhere(self):
        result = v3.evaluate(payload())
        self.assertNotIn("total", result)
        self.assertNotIn("grade", result)

    def test_rendered_report_has_no_score_line(self):
        text = v3.render(v3.evaluate(payload())).lower()
        for banned in ("/100", "recruit-style", "persol", "overall estimate", "match score"):
            self.assertNotIn(banned, text)
        self.assertIn("decision status:", text)
        self.assertIn("excluded from objective-fit calculations", text)


class LegacyIsolation(unittest.TestCase):
    """AC-6. Legacy runs only on request, and says what it is when it does."""

    def test_legacy_results_carry_version_and_warning(self):
        result = legacy_experimental.recruit_style(
            [{"name": "Python", "s": 70, "w": 1.0}], p_fit=75, b_behavioral=60)
        self.assertEqual(result["model_version"], "legacy_v1")
        self.assertIn("Not an official Recruit/Persol model", result["warning"])

    def test_cli_refuses_without_opt_in(self):
        self.assertEqual(legacy_experimental.main([]), 2)

    def test_culture_fit_is_discontinued(self):
        with self.assertRaises(legacy_experimental.DiscontinuedError):
            legacy_experimental.culture_fit({"autonomy": 5}, {"autonomy": 4})

    def test_v3_module_does_not_import_legacy(self):
        """The v3 engine may name the legacy module in prose; it may not call into it."""
        source = (ROOT / "_shared" / "matching_v3.py").read_text(encoding="utf-8")
        for banned in ("import legacy_experimental", "from legacy_experimental",
                       "recruit_style(", "persol_style(", "culture_fit("):
            self.assertNotIn(banned, source)
        self.assertNotIn("legacy_experimental", sys.modules.get("matching_v3").__dict__)

    def test_legacy_self_test_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "_shared" / "legacy_experimental.py"), "--self-test"],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("legacy_v1", result.stdout)


class Determinism(unittest.TestCase):
    """NFR-2."""

    def test_same_payload_same_bytes(self):
        data = payload()
        first = json.dumps(v3.evaluate(copy.deepcopy(data)), ensure_ascii=False, sort_keys=False)
        second = json.dumps(v3.evaluate(copy.deepcopy(data)), ensure_ascii=False, sort_keys=False)
        self.assertEqual(first, second)

    def test_staleness_needs_an_explicit_as_of(self):
        without = v3.evaluate(payload())
        self.assertIsNone(without["evidence_summary"]["stale"])
        with_date = v3.evaluate(payload(as_of="2026-08-03", eligibility=[
            {"requirement": "年収レンジ", "candidate_evidence": "希望600万",
             "job_evidence": "500-700万", "meets": True, "observed_at": "2024-01-01"},
        ]))
        self.assertEqual(len(with_date["evidence_summary"]["stale"]), 1)

    def test_cli_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "payload.json"
            path.write_text(json.dumps(payload(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "_shared" / "matching_v3.py"), str(path)],
                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision_status"], "proceed")


class EvidenceReporting(unittest.TestCase):
    """FR-7."""

    def test_low_confidence_items_are_listed(self):
        result = v3.evaluate(payload(career_values=[
            {"value": "風通しの良さ", "kind": "preferred", "satisfied": True,
             "company_evidence": "採用サイトの文言のみ", "source_type": "job_posting", "confidence": "low"},
        ]))
        self.assertIn("風通しの良さ", result["evidence_summary"]["low_confidence"])

    def test_clarifying_questions_come_from_unknowns_only(self):
        result = v3.evaluate(payload(eligibility=[
            {"requirement": "日本語要求水準", "candidate_evidence": "N2", "job_evidence": None, "meets": None},
        ]))
        self.assertEqual(len(result["clarifying_questions"]), len(result["decision_basis"]["unknowns"]))
        self.assertIn("日本語要求水準", result["clarifying_questions"][0])

    def test_invalid_source_type_rejected(self):
        with self.assertRaises(v3.ValidationError):
            v3.eligibility_results([{"requirement": "x", "source_type": "hearsay"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
