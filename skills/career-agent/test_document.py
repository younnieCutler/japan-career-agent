"""Contract tests for the JD projection and the Career Fidelity Gate.

The claim under test is one sentence: a target changes which evidence is shown and how, and never
what any of it says. Everything below is a way for that to fail -- a number that was not measured,
a role that grew, a team's outcome written as one person's, a JD keyword arriving as a fact, an
internal project name leaving the building -- and an assertion that it does not.

The gate is literal string work by design. These tests are also the record of what "literal" is
able to catch, so a later semantic layer can be added knowing which cases already hold without it.
"""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import document  # noqa: E402
from models import CareerError  # noqa: E402


def context(context_id: str, label: str, **payload) -> dict:
    return {
        "id": f"evt-{context_id}",
        "type": "experience_context",
        "status": "confirmed",
        "occurred_at": "2026-08-01T00:00:00Z",
        "title": label,
        "summary": label,
        "evidence": ["user"],
        "experience_context": {"id": context_id, "kind": "company", "label": label, **payload},
    }


def project(project_id: str, title: str, **payload) -> dict:
    return {
        "id": f"evt-{project_id}",
        "type": "project",
        "status": "confirmed",
        "occurred_at": "2026-08-01T00:00:00Z",
        "title": title,
        "summary": title,
        "evidence": ["user"],
        "project": {"id": project_id, "title": title, **payload},
    }


def evidence(event_id: str, *, title: str = "note", summary: str = "note", **payload) -> dict:
    return {
        "id": event_id,
        "type": "work_event",
        "status": "confirmed",
        "occurred_at": "2026-08-02T00:00:00Z",
        "title": title,
        "summary": summary,
        "evidence": ["PR #123"],
        "work_event": payload,
    }


LEDGER = [
    context("ctx-a", "内部決済A社", external_label="決済系企業", period={"from": "2022-04"}),
    project("prj-1", "Phoenix", external_label="決済基盤刷新"),
    evidence(
        "evt-deploy",
        title="デプロイ自動化",
        summary="GitHub Actionsで手動デプロイを自動化",
        role="支援",
        direct_actions=["GitHub Actionsのワークフローを作成"],
        individual_contribution="手動デプロイの自動化",
        team_result="リリース頻度が向上",
        metrics=["所要時間 28.4% 短縮"],
        context_id="ctx-a",
        primary_project_id="prj-1",
    ),
    evidence(
        "evt-incident",
        title="障害対応",
        summary="アラート条件を見直し runbook を更新",
        role="参加",
        individual_contribution="runbook の更新",
        context_id="ctx-a",
        experience_kind="incident",
        experience_ref="決済障害対応",
    ),
    evidence(
        "evt-secret",
        title="社内案件",
        summary="社内システムの移行",
        individual_contribution="移行手順の作成",
        context_id="ctx-a",
        confidentiality={"contains_confidential": True, "external_use": "unknown"},
    ),
]


def company(**overrides) -> dict:
    base = {
        "slug": "example-corp",
        "name": "Example Corp",
        "primary_experience_ids": ["evt-deploy", "evt-incident"],
    }
    base.update(overrides)
    return base


def model(**overrides) -> dict:
    return document.document_model(LEDGER, company(**overrides))


def draft(**slots) -> dict:
    return {"slots": slots}


class TheTargetChangesTheLensNotTheFactTests(unittest.TestCase):
    def test_two_targets_select_differently(self) -> None:
        a = model(primary_experience_ids=["evt-deploy"])
        b = model(primary_experience_ids=["evt-incident"])
        self.assertEqual([e["evidence_id"] for e in a["entries"]], ["evt-deploy"])
        self.assertEqual([e["evidence_id"] for e in b["entries"]], ["evt-incident"])

    def test_the_employer_and_period_are_the_same_in_both(self) -> None:
        a = model(primary_experience_ids=["evt-deploy"])
        b = model(primary_experience_ids=["evt-incident"], name="Other Corp")
        self.assertEqual(a["employment_history"][0]["label"], b["employment_history"][0]["label"])
        self.assertEqual(a["employment_history"][0]["period"], b["employment_history"][0]["period"])

    def test_supporting_evidence_follows_primary_without_repeating(self) -> None:
        built = model(
            primary_experience_ids=["evt-deploy"],
            supporting_experience_ids=["evt-deploy", "evt-incident"],
        )
        self.assertEqual([e["evidence_id"] for e in built["entries"]], ["evt-deploy", "evt-incident"])
        self.assertTrue(built["entries"][0]["lead"])
        self.assertFalse(built["entries"][1]["lead"])

    def test_an_unsupported_document_type_is_refused_by_name(self) -> None:
        with self.assertRaises(CareerError):
            document.document_model(LEDGER, company(), document_type="rirekisho")


class WhatNeverReachesTheDocumentTests(unittest.TestCase):
    def test_evidence_awaiting_confidentiality_review_is_excluded(self) -> None:
        # "Not decided yet" is not permission. That is the whole reason `external_use` exists
        # separately from the flag.
        built = model(primary_experience_ids=["evt-secret"])
        self.assertEqual(built["entries"], [])
        self.assertEqual(built["excluded"][0]["evidence_id"], "evt-secret")

    def test_a_selection_pointing_at_a_draft_is_reported_not_silently_dropped(self) -> None:
        built = model(primary_experience_ids=["evt-nope"])
        self.assertEqual(built["excluded"][0]["reason"], "not confirmed evidence")

    def test_an_external_label_replaces_the_internal_project_name(self) -> None:
        built = model()
        self.assertEqual(built["entries"][0]["heading"], "決済基盤刷新")
        self.assertEqual(built["employment_history"][0]["label"], "決済系企業")

    def test_unsupported_requirements_stay_unknown(self) -> None:
        built = model(
            jd_requirements=[
                {"text": "CI/CD automation", "status": "Matched", "evidence_ids": ["evt-deploy"]},
                {"text": "large-scale Kubernetes", "status": "Unknown"},
            ]
        )
        self.assertIn("large-scale Kubernetes", built["unknowns"])
        self.assertNotIn("Kubernetes", [item["label"] for item in built["skills"]])

    def test_a_skill_carries_the_evidence_that_shows_it_being_used(self) -> None:
        built = model()
        self.assertEqual(built["skills"], [{"label": "GitHub Actions", "evidence_ids": ["evt-deploy"]}])


class EmploymentHistoryReadsNewestFirstTests(unittest.TestCase):
    """The ordinary Japanese convention, and the only ordering the data supports."""

    def ledger_with_two_employers(self) -> list[dict]:
        return [
            *LEDGER,
            context("ctx-b", "以前の会社", period={"from": "2019-04", "to": "2022-03"}),
            evidence("evt-old", summary="月次レポートを定型化", role="担当", context_id="ctx-b"),
        ]

    def test_the_more_recent_employer_comes_first(self) -> None:
        built = document.document_model(
            self.ledger_with_two_employers(),
            company(primary_experience_ids=["evt-deploy", "evt-old"]),
        )
        self.assertEqual(
            [block["context_id"] for block in built["employment_history"]], ["ctx-a", "ctx-b"]
        )

    def test_a_context_with_no_period_sorts_last(self) -> None:
        # Absent is Unknown, and an Unknown start is not evidence of a recent one.
        ledger = [
            *self.ledger_with_two_employers(),
            context("ctx-c", "期間未記録の会社", period=None),
            evidence("evt-undated", summary="担当業務", role="担当", context_id="ctx-c"),
        ]
        built = document.document_model(
            ledger, company(primary_experience_ids=["evt-deploy", "evt-old", "evt-undated"]),
        )
        self.assertEqual(built["employment_history"][-1]["context_id"], "ctx-c")

    def test_the_order_does_not_depend_on_the_context_id(self) -> None:
        # It used to sort on the uuid, which made the order stable for one vault and arbitrary
        # between any two. A career history whose order means nothing is worse than an odd one.
        built = document.document_model(
            self.ledger_with_two_employers(),
            company(primary_experience_ids=["evt-deploy", "evt-old"]),
        )
        ids = [block["context_id"] for block in built["employment_history"]]
        self.assertNotEqual(ids, sorted(ids, reverse=True))
        self.assertEqual(ids, ["ctx-a", "ctx-b"])


class SkillsAreProposedAndMayOnlyBeNarrowedTests(unittest.TestCase):
    def test_a_draft_may_drop_a_noisy_proposal(self) -> None:
        # "API" out of 決済API is evidence-backed and useless as a skill label, so the writer is
        # allowed to remove it.
        built = model()
        result = document.fidelity_gate(built, {"slots": {}, "skills": ["GitHub Actions"]})
        self.assertTrue(result["pass"], result["violations"])

    def test_a_draft_may_not_add_one(self) -> None:
        built = model()
        result = document.fidelity_gate(built, {"slots": {}, "skills": ["Kubernetes"]})
        self.assertIn("unsupported_technology", {item["rule"] for item in result["violations"]})

    def test_omitting_the_list_keeps_every_proposal(self) -> None:
        self.assertTrue(document.fidelity_gate(model(), draft())["pass"])


class TheGateRefusesStrongerWordingTests(unittest.TestCase):
    def assertBlocked(self, slots: dict, rule: str) -> None:
        result = document.fidelity_gate(model(), draft(**slots))
        self.assertFalse(result["pass"])
        self.assertIn(rule, {item["rule"] for item in result["violations"]})

    def test_evidence_grounded_wording_passes(self) -> None:
        result = document.fidelity_gate(
            model(),
            draft(**{"entry:evt-deploy": "GitHub Actionsで手動デプロイを自動化し、所要時間 28.4% 短縮。"}),
        )
        self.assertTrue(result["pass"], result["violations"])

    def test_support_does_not_become_leadership(self) -> None:
        self.assertBlocked({"entry:evt-deploy": "デプロイ自動化を主導しました。"}, "role_escalation")

    def test_taking_part_does_not_become_designing(self) -> None:
        self.assertBlocked(
            {"entry:evt-deploy": "デプロイ基盤の全体設計を担当しました。"}, "role_escalation"
        )

    def test_a_number_that_was_never_measured_is_refused(self) -> None:
        self.assertBlocked(
            {"entry:evt-incident": "対応時間を50%短縮しました。"}, "unsupported_metric"
        )

    def test_an_existing_number_may_not_be_rounded(self) -> None:
        # 28.4% is what the evidence says. "약 30%" is a different claim wearing the same clothes.
        self.assertBlocked({"entry:evt-deploy": "所要時間を30%短縮。"}, "unsupported_metric")

    def test_a_jd_keyword_may_not_arrive_as_a_fact(self) -> None:
        self.assertBlocked(
            {"entry:evt-deploy": "DevOps基盤の設計・構築を担当。"}, "unsupported_technology"
        )

    def test_an_internal_project_name_may_not_leave(self) -> None:
        self.assertBlocked(
            {"entry:evt-deploy": "Phoenixのデプロイを自動化。"}, "confidentiality_bypass"
        )

    def test_excluded_evidence_may_not_be_written_about(self) -> None:
        result = document.fidelity_gate(
            model(primary_experience_ids=["evt-secret"]),
            draft(**{"entry:evt-secret": "社内システムの移行手順を作成。"}),
        )
        self.assertIn("excluded_evidence_used", {item["rule"] for item in result["violations"]})

    def test_a_slot_the_model_never_defined_is_refused(self) -> None:
        self.assertBlocked({"entry:evt-invented": "何かをしました。"}, "unknown_slot")

    def test_a_team_outcome_in_a_summary_must_say_whose_it_was(self) -> None:
        result = document.fidelity_gate(
            model(), draft(**{"section:self_pr": "リリース頻度が向上しました。"})
        )
        self.assertIn("team_result_as_individual", {item["rule"] for item in result["violations"]})

    def test_the_same_outcome_attributed_to_the_team_passes(self) -> None:
        result = document.fidelity_gate(
            model(),
            draft(**{"section:self_pr": "チームとしてリリース頻度が向上し、自動化を担当しました。"}),
        )
        self.assertTrue(result["pass"], result["violations"])


class PolishingPreservesStructureTests(unittest.TestCase):
    def test_wording_may_change(self) -> None:
        before = draft(**{"entry:evt-deploy": "GitHub Actionsを活用することで、デプロイの効率化を実現しました。"})
        after = draft(**{"entry:evt-deploy": "GitHub Actionsで手動デプロイを自動化。"})
        result = document.fidelity_gate(model(), before, humanized=after)
        self.assertTrue(result["pass"], result["violations"])
        self.assertEqual(result["stage"], "humanized")

    def test_bullets_may_not_be_merged_into_prose(self) -> None:
        before = draft(**{"entry:evt-deploy": "GitHub Actionsで自動化。\n所要時間 28.4% 短縮。"})
        after = draft(**{"entry:evt-deploy": "GitHub Actionsで自動化し、所要時間 28.4% 短縮しました。"})
        result = document.fidelity_gate(model(), before, humanized=after)
        self.assertIn("structure_changed", {item["rule"] for item in result["violations"]})

    def test_a_slot_may_not_disappear_during_polishing(self) -> None:
        before = draft(**{"entry:evt-deploy": "自動化。", "section:summary": "決済系企業で従事。"})
        after = draft(**{"entry:evt-deploy": "自動化。"})
        result = document.fidelity_gate(model(), before, humanized=after)
        self.assertIn("structure_changed", {item["rule"] for item in result["violations"]})

    def test_polishing_may_not_introduce_a_stronger_claim(self) -> None:
        before = draft(**{"entry:evt-deploy": "GitHub Actionsで手動デプロイを自動化。"})
        after = draft(**{"entry:evt-deploy": "GitHub Actionsによる自動化を主導。"})
        result = document.fidelity_gate(model(), before, humanized=after)
        self.assertIn("role_escalation", {item["rule"] for item in result["violations"]})


class TheGateIsTheSameGateEveryTimeTests(unittest.TestCase):
    def test_identical_input_produces_identical_violations(self) -> None:
        built = model()
        slots = draft(**{"entry:evt-deploy": "DevOps基盤を主導し、50%短縮。"})
        runs = [document.fidelity_gate(built, slots) for _ in range(5)]
        for run in runs[1:]:
            self.assertEqual(run, runs[0])

    def test_building_the_model_twice_gives_the_same_model(self) -> None:
        self.assertEqual(model(), model())

    def test_the_verdict_is_named_for_what_it_counts(self) -> None:
        # `factual_drift: 0` read as "the wording did not move", which is more than this gate
        # establishes. It counts breaches of enumerated rules, and the name says so.
        result = document.fidelity_gate(model(), draft())
        self.assertIn("protected_claim_violations", result)
        self.assertNotIn("factual_drift", result)
        for key in result:
            self.assertNotIn("detector", key)
            self.assertNotIn("score", key)

    def test_passing_means_no_enumerated_violation_not_proven_fidelity(self) -> None:
        # The honest limit, asserted rather than left to a docstring. A synonym outside
        # ESCALATION_TERMS raises the claim's strength and the gate does not see it, which is why
        # the humanize contract and the user's own review are the other half of the defence.
        outside_the_list = "デプロイ自動化を推進。"
        self.assertTrue(all(term not in outside_the_list for term in document.ESCALATION_TERMS))
        result = document.fidelity_gate(model(), draft(**{"entry:evt-deploy": outside_the_list}))
        self.assertTrue(result["pass"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
