#!/usr/bin/env python3
"""Regression tests for evidence-backed target-role exploration."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
CAREER_AGENT = ROOT / "skills" / "career-agent"
for import_path in (SHARED, CAREER_AGENT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from role_transition import (  # noqa: E402
    MODEL_VERSION,
    RoleTransitionError,
    evaluate,
    render_text,
    validate_payload,
)
from routing import skill_context  # noqa: E402


def role_by_id(result: dict, role_id: str) -> dict:
    return next(role for role in result["roles"] if role["id"] == role_id)


def requirement_by_id(role: dict, requirement_id: str) -> dict:
    return next(item for item in role["requirements"] if item["id"] == requirement_id)


class RoleTransitionTests(unittest.TestCase):
    def payload(self) -> dict:
        return {
            "candidate": {
                "evidence": [
                    {
                        "id": "ev-test-design",
                        "capability": "test design",
                        "relation": "demonstrates",
                        "state": "Confirmed",
                        "source_type": "user",
                        "source_ref": "vault:event:test-design",
                        "observed_at": "2026-08-01",
                        "confidence": "high",
                        "provenance": "user",
                    },
                    {
                        "id": "ev-stakeholder",
                        "capability": "stakeholder coordination",
                        "relation": "demonstrates",
                        "state": "Confirmed",
                        "source_type": "user",
                        "source_ref": "vault:event:stakeholder",
                        "observed_at": "2026-07-10",
                        "confidence": "high",
                        "provenance": "user",
                    },
                    {
                        "id": "ev-automation-memory",
                        "capability": "test automation",
                        "relation": "demonstrates",
                        "state": "Low Confidence",
                        "source_type": "user",
                        "source_ref": "conversation:2026-09-12",
                        "observed_at": "2026-09-12",
                        "confidence": "low",
                        "provenance": "user",
                    },
                    {
                        "id": "ev-no-automation",
                        "capability": "automated test implementation",
                        "relation": "absence",
                        "state": "Confirmed",
                        "source_type": "user",
                        "source_ref": "conversation:2026-09-12:no-automation",
                        "observed_at": "2026-09-12",
                        "confidence": "high",
                        "provenance": "user",
                    },
                    {
                        "id": "ev-no-ci",
                        "capability": "CI test operation",
                        "relation": "absence",
                        "state": "Confirmed",
                        "source_type": "user",
                        "source_ref": "conversation:2026-09-12:no-ci",
                        "observed_at": "2026-09-12",
                        "confidence": "high",
                        "provenance": "user",
                    },
                ]
            },
            "role_candidates": [
                {
                    "id": "qa-automation",
                    "label": "QA Automation Engineer",
                    "sources": [
                        {
                            "id": "jobtag-qa",
                            "source_type": "official_framework",
                            "source_ref": "https://shigoto.mhlw.go.jp/",
                            "observed_at": "2026-09-12",
                            "state": "Confirmed",
                            "confidence": "high",
                            "provenance": "official_framework",
                        },
                        {
                            "id": "jd-a",
                            "source_type": "job_posting",
                            "source_ref": "https://example.invalid/jobs/qa-a",
                            "observed_at": "2026-09-12",
                            "state": "Confirmed",
                            "confidence": "high",
                            "provenance": "job_posting",
                        },
                    ],
                    "requirements": [
                        {
                            "id": "req-test-design",
                            "text": "Design test cases from product requirements",
                            "kind": "core",
                            "source_refs": ["jd-a"],
                            "direct_evidence_ids": ["ev-test-design"],
                        },
                        {
                            "id": "req-automation",
                            "text": "Implement automated tests",
                            "kind": "core",
                            "source_refs": ["jd-a"],
                            "transfer_evidence_ids": ["ev-test-design"],
                            "transfer_rationale": "Test-design evidence may transfer to automation planning but does not prove implementation.",
                            "verification_question": "Which automated test code have you implemented and maintained?",
                        },
                        {
                            "id": "req-ci",
                            "text": "Operate tests in CI",
                            "kind": "preferred",
                            "source_refs": ["jd-a"],
                            "absence_evidence_ids": ["ev-no-ci"],
                        },
                    ],
                },
                {
                    "id": "qa-manual",
                    "label": "QA Engineer",
                    "sources": [
                        {
                            "id": "jd-b",
                            "source_type": "job_posting",
                            "source_ref": "https://example.invalid/jobs/qa-b",
                            "observed_at": "2026-09-12",
                            "state": "Confirmed",
                            "confidence": "high",
                            "provenance": "job_posting",
                        }
                    ],
                    "requirements": [
                        {
                            "id": "req-manual-design",
                            "text": "Design and execute tests",
                            "kind": "core",
                            "source_refs": ["jd-b"],
                            "direct_evidence_ids": ["ev-test-design"],
                        },
                        {
                            "id": "req-collab",
                            "text": "Coordinate defects with stakeholders",
                            "kind": "core",
                            "source_refs": ["jd-b"],
                            "direct_evidence_ids": ["ev-stakeholder"],
                        },
                    ],
                },
            ],
        }

    def test_direct_confirmed_evidence_matches_requirement(self) -> None:
        result = evaluate(self.payload())
        role = role_by_id(result, "qa-manual")
        self.assertEqual(role["targeting_state"], "evidence_supported")
        self.assertEqual(requirement_by_id(role, "req-manual-design")["state"], "Matched")
        self.assertEqual(requirement_by_id(role, "req-collab")["state"], "Matched")

    def test_transfer_hypothesis_never_becomes_matched(self) -> None:
        result = evaluate(self.payload())
        role = role_by_id(result, "qa-automation")
        requirement = requirement_by_id(role, "req-automation")
        self.assertEqual(requirement["state"], "Unknown")
        self.assertEqual(role["targeting_state"], "needs_validation")
        self.assertEqual(
            requirement["transfer_hypothesis"]["status"],
            "hypothesis_with_confirmed_basis",
        )
        self.assertIn("never changes", requirement["transfer_hypothesis"]["note"])

    def test_confirmed_absence_is_missing_but_silence_is_unknown(self) -> None:
        payload = self.payload()
        role = payload["role_candidates"][0]
        role["requirements"][1].pop("transfer_evidence_ids")
        role["requirements"][1].pop("transfer_rationale")
        role["requirements"][1].pop("verification_question")
        result = evaluate(payload)
        evaluated = role_by_id(result, "qa-automation")
        self.assertEqual(requirement_by_id(evaluated, "req-automation")["state"], "Unknown")
        self.assertEqual(requirement_by_id(evaluated, "req-ci")["state"], "Missing")

    def test_confirmed_core_absence_creates_core_gap(self) -> None:
        payload = self.payload()
        requirement = payload["role_candidates"][0]["requirements"][1]
        requirement.pop("transfer_evidence_ids")
        requirement.pop("transfer_rationale")
        requirement.pop("verification_question")
        requirement["absence_evidence_ids"] = ["ev-no-automation"]
        result = evaluate(payload)
        role = role_by_id(result, "qa-automation")
        self.assertEqual(requirement_by_id(role, "req-automation")["state"], "Missing")
        self.assertEqual(role["targeting_state"], "confirmed_core_gap")
        self.assertEqual(
            role["confirmed_gaps"],
            [{"requirement_id": "req-automation", "evidence_ids": ["ev-no-automation"]}],
        )

    def test_unconfirmed_absence_evidence_stays_unknown(self) -> None:
        payload = self.payload()
        absence = next(
            item for item in payload["candidate"]["evidence"] if item["id"] == "ev-no-automation"
        )
        absence["state"] = "Low Confidence"
        absence["confidence"] = "low"
        requirement = payload["role_candidates"][0]["requirements"][1]
        requirement.pop("transfer_evidence_ids")
        requirement.pop("transfer_rationale")
        requirement.pop("verification_question")
        requirement["absence_evidence_ids"] = ["ev-no-automation"]
        evaluated = requirement_by_id(role_by_id(evaluate(payload), "qa-automation"), "req-automation")
        self.assertEqual(evaluated["state"], "Unknown")
        self.assertEqual(evaluated["reason"], "candidate_absence_evidence_not_confirmed")

    def test_preferred_gap_does_not_override_supported_core(self) -> None:
        payload = self.payload()
        payload["candidate"]["evidence"].append(
            {
                "id": "ev-no-optional-tool",
                "capability": "optional tool experience",
                "relation": "absence",
                "state": "Confirmed",
                "source_type": "user",
                "source_ref": "conversation:2026-09-12:no-optional-tool",
                "observed_at": "2026-09-12",
                "confidence": "high",
                "provenance": "user",
            }
        )
        payload["role_candidates"] = [payload["role_candidates"][1]]
        payload["role_candidates"][0]["requirements"].append(
            {
                "id": "req-preferred-tool",
                "text": "Experience with a specific optional tool",
                "kind": "preferred",
                "source_refs": ["jd-b"],
                "absence_evidence_ids": ["ev-no-optional-tool"],
            }
        )
        role = role_by_id(evaluate(payload), "qa-manual")
        self.assertEqual(requirement_by_id(role, "req-preferred-tool")["state"], "Missing")
        self.assertEqual(role["targeting_state"], "evidence_supported")

    def test_unconfirmed_role_source_forces_unknown(self) -> None:
        payload = self.payload()
        payload["role_candidates"][1]["sources"][0]["state"] = "Stale"
        role = role_by_id(evaluate(payload), "qa-manual")
        self.assertEqual(role["targeting_state"], "needs_validation")
        for requirement in role["requirements"]:
            self.assertEqual(requirement["state"], "Unknown")
            self.assertEqual(requirement["reason"], "role_source_not_confirmed")

    def test_low_confidence_role_source_forces_unknown(self) -> None:
        payload = self.payload()
        payload["role_candidates"][1]["sources"][0]["confidence"] = "low"
        role = role_by_id(evaluate(payload), "qa-manual")
        self.assertEqual(role["targeting_state"], "needs_validation")
        for requirement in role["requirements"]:
            self.assertEqual(requirement["state"], "Unknown")
            self.assertEqual(requirement["reason"], "role_source_not_confirmed")

    def test_role_source_must_be_public_role_evidence(self) -> None:
        payload = self.payload()
        source = payload["role_candidates"][0]["sources"][0]
        source["source_type"] = "heuristic"
        source["provenance"] = "heuristic"
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_role_source_requires_observation_date(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["sources"][0].pop("observed_at")
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_role_source_provenance_must_match_source_type(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["sources"][0]["provenance"] = "job_posting"
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_low_confidence_candidate_evidence_cannot_match(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][1] = {
            "id": "req-automation",
            "text": "Implement automated tests",
            "kind": "core",
            "source_refs": ["jd-a"],
            "direct_evidence_ids": ["ev-automation-memory"],
        }
        role = role_by_id(evaluate(payload), "qa-automation")
        requirement = requirement_by_id(role, "req-automation")
        self.assertEqual(requirement["state"], "Unknown")
        self.assertEqual(requirement["reason"], "candidate_evidence_not_direct_confirmed")

    def test_heuristic_candidate_evidence_cannot_match_or_confirm_transfer(self) -> None:
        payload = self.payload()
        evidence = payload["candidate"]["evidence"][0]
        evidence["source_type"] = "heuristic"
        evidence["provenance"] = "heuristic"
        result = evaluate(payload)

        manual = role_by_id(result, "qa-manual")
        direct = requirement_by_id(manual, "req-manual-design")
        self.assertEqual(direct["state"], "Unknown")
        self.assertEqual(direct["reason"], "candidate_evidence_not_direct_confirmed")

        automation = role_by_id(result, "qa-automation")
        transfer = requirement_by_id(automation, "req-automation")["transfer_hypothesis"]
        self.assertEqual(transfer["status"], "hypothesis_basis_unconfirmed")

    def test_absence_relation_cannot_be_used_as_direct_evidence(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][0]["direct_evidence_ids"] = ["ev-no-ci"]
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_demonstrates_relation_cannot_be_used_as_absence_evidence(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][0]["absence_evidence_ids"] = ["ev-test-design"]
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_bare_confirmed_absence_boolean_is_rejected(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][0]["candidate_absence_confirmed"] = True
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_role_without_core_requirements_is_insufficient(self) -> None:
        payload = self.payload()
        payload["role_candidates"] = [payload["role_candidates"][1]]
        payload["role_candidates"][0]["requirements"] = [
            {
                "id": "req-preferred",
                "text": "Optional domain experience",
                "kind": "preferred",
                "source_refs": ["jd-b"],
                "direct_evidence_ids": ["ev-test-design"],
            }
        ]
        role = role_by_id(evaluate(payload), "qa-manual")
        self.assertEqual(role["targeting_state"], "insufficient_role_evidence")

    def test_unknown_evidence_reference_is_rejected(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][0]["direct_evidence_ids"] = ["missing"]
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_unknown_source_reference_is_rejected(self) -> None:
        payload = self.payload()
        payload["role_candidates"][0]["requirements"][0]["source_refs"] = ["missing"]
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_direct_evidence_and_absence_evidence_conflict_is_rejected(self) -> None:
        payload = self.payload()
        requirement = payload["role_candidates"][0]["requirements"][0]
        requirement["absence_evidence_ids"] = ["ev-test-design"]
        with self.assertRaises(RoleTransitionError):
            validate_payload(payload)

    def test_output_has_no_score_probability_or_rank(self) -> None:
        result = evaluate(self.payload())
        self.assertEqual(result["model_version"], MODEL_VERSION)

        forbidden = {"score", "probability", "rank", "distance", "fit"}

        def walk(value, path="root") -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    lowered = key.lower()
                    self.assertFalse(
                        any(token in lowered for token in forbidden),
                        f"forbidden ranking/scoring key at {path}.{key}",
                    )
                    walk(child, f"{path}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")

        walk(result)

    def test_text_output_keeps_unknown_and_transfer_boundary_visible(self) -> None:
        text = render_text(evaluate(self.payload()))
        self.assertIn("Targeting state: needs_validation", text)
        self.assertIn("Unknown: Implement automated tests", text)
        self.assertIn("transfer hypothesis:", text)

    def test_chuto_target_role_request_uses_targeting_reference(self) -> None:
        context = skill_context(
            ROOT / "skills",
            "自己分析・転職軸",
            message="이직할 건데 다음에 어떤 직무를 노려야 할까?",
            track="chuto",
        )
        self.assertEqual(context["skill"], "job-seeker-agent")
        self.assertEqual(context["references"], ["references/career-transition-targeting.md"])

    def test_target_role_mention_in_resume_request_does_not_hijack_routing(self) -> None:
        context = skill_context(
            ROOT / "skills",
            "職務経歴書・自己PR",
            message="target role에 맞춰 resume 수정해줘",
            track="chuto",
        )
        self.assertEqual(context["skill"], "job-seeker-agent")
        self.assertEqual(context["references"], ["references/shokumukeireki-saigensei.md"])

    def test_generic_chuto_self_analysis_still_routes_to_jiko(self) -> None:
        context = skill_context(
            ROOT / "skills",
            "自己分析・転職軸",
            message="이직 전에 자기분석부터 하고 싶어",
            track="chuto",
        )
        self.assertEqual(context["skill"], "jiko-bunseki")
        self.assertNotIn("references/career-transition-targeting.md", context["references"])

    def test_shipped_skill_wrapper_runs_from_unrelated_cwd(self) -> None:
        wrapper = ROOT / "skills" / "job-seeker-agent" / "scripts" / "role_transition.py"
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [sys.executable, str(wrapper)],
                cwd=temp_dir,
                input=json.dumps(self.payload()),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["model_version"], MODEL_VERSION)

    def test_input_is_not_mutated(self) -> None:
        payload = self.payload()
        before = copy.deepcopy(payload)
        evaluate(payload)
        self.assertEqual(payload, before)


if __name__ == "__main__":
    unittest.main()
