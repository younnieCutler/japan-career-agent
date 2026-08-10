"""Contract tests for CONTEXT -> EXPERIENCE -> EVIDENCE.

Three claims are under test here.

A context is where an experience happened -- a company, a university, a part-time shop -- and it is
not always an employer. An experience is not always a project. And evidence about a university
seminar is not a work event, because storing it as one would say the user was employed there and
every work-scoped read in the runtime would start returning coursework as work history.

The fourth claim is the one that costs the most if it breaks: none of this may change what a
`work_event` already meant. The regression tests for that live in `test_work_event.py` and
`test_project.py`; what is here is the part that is new.
"""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

import projection  # noqa: E402
import validation  # noqa: E402
from models import (  # noqa: E402
    EXPERIENCE_CONTEXT_EVENT_TYPE,
    EXPERIENCE_EVENT_TYPE,
    PROJECT_EVENT_TYPE,
    WORK_EVENT_TYPE,
    CareerError,
    default_state,
)


def event(**overrides) -> dict:
    """A minimal valid event. Callers override only the field under test."""
    base = {
        "id": "evt-000000000001",
        "track": None,
        "stage": None,
        "flow_phase": None,
        "type": WORK_EVENT_TYPE,
        "occurred_at": "2026-08-10T00:00:00Z",
        "title": "note",
        "summary": "note",
        "evidence": [],
        "source": "user",
        "next_action": None,
        "deadline": None,
        "status": "draft",
    }
    base.update(overrides)
    return base


def context_payload(**overrides) -> dict:
    payload = {"id": "ctx-000000000001", "kind": "company", "label": "회사 A"}
    payload.update(overrides)
    return payload


def confirmed_context(context_id: str, occurred_at: str, **payload) -> dict:
    return event(
        id=f"evt-ctx-{context_id}-{occurred_at}",
        type=EXPERIENCE_CONTEXT_EVENT_TYPE,
        status="confirmed",
        occurred_at=occurred_at,
        evidence=["user"],
        experience_context={"id": context_id, **payload},
    )


def confirmed_evidence(event_id: str, *, type_: str = WORK_EVENT_TYPE, **payload) -> dict:
    key = "work_event" if type_ == WORK_EVENT_TYPE else "experience"
    return event(id=event_id, type=type_, status="confirmed", evidence=["user"], **{key: payload})


class ContextIsNotAlwaysAnEmployerTests(unittest.TestCase):
    def test_only_id_kind_and_label_are_required(self) -> None:
        validation.validate_experience_context(context_payload())

    def test_every_other_field_may_stay_unknown(self) -> None:
        validation.validate_experience_context(
            context_payload(external_label=None, role=None, summary=None, period=None)
        )

    def test_a_university_is_a_context(self) -> None:
        validation.validate_experience_context(context_payload(kind="university", label="○○大学"))

    def test_a_club_is_a_context(self) -> None:
        validation.validate_experience_context(context_payload(kind="club", label="軽音サークル"))

    def test_kind_is_closed(self) -> None:
        # The one field a later reader cannot recover from the label. "A社" and "A大学" both read
        # as either an employer or a school to a downstream skill, and guessing wrong turns
        # coursework into employment history.
        with self.assertRaises(CareerError):
            validation.validate_experience_context(context_payload(kind="workplace"))

    def test_kind_is_required(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_experience_context({"id": "ctx-1", "label": "회사 A"})

    def test_a_misspelled_field_is_an_error_not_a_dropped_value(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_experience_context(context_payload(externa_label="safe name"))

    def test_period_may_not_run_backwards(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_experience_context(
                context_payload(period={"from": "2024-04", "to": "2023-04"})
            )

    def test_month_precision_is_a_real_answer(self) -> None:
        validation.validate_experience_context(
            context_payload(period={"from": "2022-04", "to": None})
        )

    def test_a_context_event_must_carry_its_payload(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_event(event(type=EXPERIENCE_CONTEXT_EVENT_TYPE))

    def test_a_context_belongs_to_no_track_or_stage(self) -> None:
        validation.validate_event(
            event(type=EXPERIENCE_CONTEXT_EVENT_TYPE, experience_context=context_payload())
        )


class NonWorkEvidenceIsNotAWorkEventTests(unittest.TestCase):
    def test_an_experience_event_belongs_to_no_track_or_stage(self) -> None:
        validation.validate_event(event(type=EXPERIENCE_EVENT_TYPE, experience={"role": "班長"}))

    def test_the_payload_is_the_same_questions_as_a_work_event(self) -> None:
        validation.validate_event(
            event(
                type=EXPERIENCE_EVENT_TYPE,
                experience={
                    "role": "ゼミ長",
                    "problem": "計測が手作業だった",
                    "direct_actions": ["集計スクリプトを書いた"],
                    "individual_contribution": "スクリプト作成",
                    "team_result": "発表が期日に間に合った",
                    "learning": ["再現手順を残すこと"],
                },
            )
        )

    def test_an_error_names_the_key_the_user_actually_used(self) -> None:
        with self.assertRaises(CareerError) as caught:
            validation.validate_event(event(type=EXPERIENCE_EVENT_TYPE, experience={"role": "  "}))
        self.assertIn("event.experience.role", str(caught.exception))
        self.assertNotIn("work_event", str(caught.exception))

    def test_a_number_in_an_experience_still_needs_evidence(self) -> None:
        # claim_surface reads both payload keys. A thesis claiming a 40% speedup is a numeric claim
        # exactly like a release is, and confirming it without a source would be the hole the
        # work-event rule already closes.
        with self.assertRaises(CareerError):
            validation.validate_event(
                event(
                    type=EXPERIENCE_EVENT_TYPE,
                    status="confirmed",
                    evidence=["ゼミ資料"],
                    experience={"metrics": ["処理時間 40% 短縮"]},
                ),
                for_confirmation=True,
            )

    def test_the_same_number_present_in_evidence_confirms(self) -> None:
        validation.validate_event(
            event(
                type=EXPERIENCE_EVENT_TYPE,
                status="confirmed",
                evidence=["ゼミ発表資料 p.4: 処理時間 40% 短縮"],
                experience={"metrics": ["処理時間 40% 短縮"]},
            ),
            for_confirmation=True,
        )


class ExperienceIsNotAlwaysAProjectTests(unittest.TestCase):
    def test_recurring_work_is_an_experience_kind(self) -> None:
        validation.validate_work_event(
            {"experience_kind": "recurring_work", "experience_ref": "月次レポート運用"}
        )

    def test_an_incident_is_an_experience_kind(self) -> None:
        validation.validate_work_event({"experience_kind": "incident"})

    def test_research_is_an_experience_kind(self) -> None:
        validation.validate_work_event({"experience_kind": "research"}, field="event.experience")

    def test_experience_kind_is_closed(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_work_event({"experience_kind": "그냥 일"})

    def test_a_project_id_and_a_free_reference_cannot_both_name_one_experience(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_work_event(
                {"primary_project_id": "prj-1", "experience_ref": "月次レポート運用"}
            )

    def test_all_three_new_fields_stay_optional(self) -> None:
        validation.validate_work_event({"role": "担当"})

    def test_context_id_must_be_an_id_when_present(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_work_event({"context_id": "   "})


class WorkEventContractIsUnchangedTests(unittest.TestCase):
    def test_an_existing_payload_still_validates(self) -> None:
        validation.validate_work_event(
            {
                "role": "運用担当",
                "direct_actions": ["アラート条件を変更"],
                "individual_contribution": "runbook を更新",
                "team_result": "再発なし",
                "metrics": ["対応時間 30分"],
                "primary_project_id": "prj-1",
                "related_project_ids": ["prj-2"],
                "work_date": "2026-06",
                "confidentiality": {"contains_confidential": True, "external_use": "unknown"},
            }
        )

    def test_its_errors_still_name_event_work_event(self) -> None:
        with self.assertRaises(CareerError) as caught:
            validation.validate_work_event({"role": ""})
        self.assertIn("event.work_event.role", str(caught.exception))

    def test_an_unknown_key_is_still_refused(self) -> None:
        with self.assertRaises(CareerError):
            validation.validate_work_event({"metric": ["30% 감소"]})


class NoneOfThisMovesTheUserTests(unittest.TestCase):
    def routed(self) -> dict:
        state = dict(default_state())
        state.update({"track": "chuto", "stage": "面接", "career_mode": "active_search"})
        return state

    def test_a_context_leaves_track_stage_and_mode_alone(self) -> None:
        before = self.routed()
        after = projection.apply_event_to_state(
            before,
            event(type=EXPERIENCE_CONTEXT_EVENT_TYPE, experience_context=context_payload()),
            job_search="on",
        )
        self.assertEqual(after["track"], "chuto")
        self.assertEqual(after["stage"], "面接")
        self.assertEqual(after["career_mode"], "active_search")
        self.assertEqual(after["last_event_id"], "evt-000000000001")

    def test_an_experience_leaves_track_stage_and_mode_alone(self) -> None:
        after = projection.apply_event_to_state(
            self.routed(),
            event(type=EXPERIENCE_EVENT_TYPE, experience={"role": "ゼミ長"}, career_mode="maintenance"),
            job_search="on",
        )
        self.assertEqual(after["stage"], "面接")
        self.assertEqual(after["career_mode"], "active_search")

    def test_neither_reaches_the_application_pipeline(self) -> None:
        # `company` on one of these names a place the user worked, not a place they are applying
        # to. Projecting it would put a past job in the kanban as a live opportunity.
        for event_type in (EXPERIENCE_CONTEXT_EVENT_TYPE, EXPERIENCE_EVENT_TYPE, WORK_EVENT_TYPE):
            with self.subTest(event_type=event_type):
                self.assertIsNone(
                    projection.upsert_pipeline_entry(
                        event(type=event_type, company="회사 A", status="confirmed")
                    )
                )


class ContextProjectionTests(unittest.TestCase):
    def test_a_later_event_fills_in_what_an_earlier_one_left_out(self) -> None:
        contexts = projection.contexts_from_events(
            [
                confirmed_context("ctx-1", "2026-08-01T00:00:00Z", kind="company", label="회사 A"),
                confirmed_context("ctx-1", "2026-08-02T00:00:00Z", role="バックエンド"),
            ]
        )
        self.assertEqual(contexts["ctx-1"]["label"], "회사 A")
        self.assertEqual(contexts["ctx-1"]["role"], "バックエンド")

    def test_a_period_learns_its_two_ends_at_different_times(self) -> None:
        contexts = projection.contexts_from_events(
            [
                confirmed_context(
                    "ctx-1", "2026-08-01T00:00:00Z", label="회사 A", period={"from": "2022-04"}
                ),
                confirmed_context("ctx-1", "2026-08-02T00:00:00Z", period={"to": "2026-03"}),
            ]
        )
        self.assertEqual(contexts["ctx-1"]["period"], {"from": "2022-04", "to": "2026-03"})

    def test_a_draft_context_is_not_a_context_yet(self) -> None:
        draft = confirmed_context("ctx-1", "2026-08-01T00:00:00Z", label="회사 A")
        draft["status"] = "draft"
        self.assertEqual(projection.contexts_from_events([draft]), {})


class ExperienceGroupingTests(unittest.TestCase):
    def ledger(self) -> list[dict]:
        return [
            confirmed_context(
                "ctx-company", "2026-08-01T00:00:00Z", kind="company", label="회사 A"
            ),
            confirmed_context(
                "ctx-univ", "2026-08-01T00:00:00Z", kind="university", label="○○大学"
            ),
            event(
                id="evt-prj",
                type=PROJECT_EVENT_TYPE,
                status="confirmed",
                evidence=["user"],
                project={"id": "prj-1", "title": "内部決済 Phoenix", "external_label": "決済基盤"},
            ),
            confirmed_evidence(
                "evt-w1",
                context_id="ctx-company",
                primary_project_id="prj-1",
                individual_contribution="移行手順を作成",
            ),
            confirmed_evidence(
                "evt-w2",
                context_id="ctx-company",
                primary_project_id="prj-1",
                team_result="無停止で移行",
                metrics=["停止時間 0分"],
            ),
            confirmed_evidence(
                "evt-w3",
                context_id="ctx-company",
                experience_kind="recurring_work",
                experience_ref="月次レポート運用",
                confidentiality={"contains_confidential": True, "external_use": "unknown"},
            ),
            confirmed_evidence(
                "evt-e1",
                type_=EXPERIENCE_EVENT_TYPE,
                context_id="ctx-univ",
                experience_kind="research",
                experience_ref="卒業研究",
                individual_contribution="計測スクリプトを実装",
            ),
            confirmed_evidence("evt-loose"),
        ]

    def test_a_project_and_a_non_project_are_both_experiences(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        ids = [item["experience_id"] for item in result["experiences"]]
        self.assertIn("project:prj-1", ids)
        self.assertIn("ref:月次レポート運用", ids)
        self.assertIn("ref:卒業研究", ids)

    def test_a_university_experience_keeps_its_own_context(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        research = next(i for i in result["experiences"] if i["experience_id"] == "ref:卒業研究")
        self.assertEqual(research["context_id"], "ctx-univ")
        self.assertEqual(research["kind"], "research")
        self.assertEqual(result["contexts"]["ctx-univ"]["kind"], "university")

    def test_evidence_is_referenced_never_copied(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        project = next(i for i in result["experiences"] if i["experience_id"] == "project:prj-1")
        self.assertEqual(project["evidence_event_ids"], ["evt-w1", "evt-w2"])

    def test_individual_and_team_are_counted_apart(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        project = next(i for i in result["experiences"] if i["experience_id"] == "project:prj-1")
        self.assertEqual(project["individual_contribution"], 1)
        self.assertEqual(project["team_result"], 1)

    def test_an_unreviewed_confidential_note_is_named_not_hidden(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        recurring = next(
            i for i in result["experiences"] if i["experience_id"] == "ref:月次レポート運用"
        )
        self.assertEqual(recurring["external_use_review_required"], ["evt-w3"])

    def test_evidence_that_hangs_on_nothing_is_still_reported(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        self.assertEqual(result["unattached_evidence_ids"], ["evt-loose"])

    def test_a_project_experience_carries_its_recruiter_safe_label(self) -> None:
        result = projection.experiences_from_events(self.ledger())
        project = next(i for i in result["experiences"] if i["experience_id"] == "project:prj-1")
        self.assertEqual(project["label"], "内部決済 Phoenix")
        self.assertEqual(project["external_label"], "決済基盤")

    def test_a_draft_is_not_evidence_yet(self) -> None:
        ledger = self.ledger()
        ledger[3]["status"] = "draft"
        result = projection.experiences_from_events(ledger)
        project = next(i for i in result["experiences"] if i["experience_id"] == "project:prj-1")
        self.assertEqual(project["evidence_event_ids"], ["evt-w2"])


class VaultCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        self.cli("setup", "--vault", self.vault, "--track", "chuto")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str) -> dict:
        done = subprocess.run(
            [sys.executable, str(CLI), *args], capture_output=True, text=True, encoding="utf-8",
        )
        if done.returncode not in (0, 2):
            raise AssertionError(f"{args}\n{done.stdout}\n{done.stderr}")
        return json.loads(done.stdout or done.stderr)

    def approve(self, proposal_id: str, evidence: str = "user") -> dict:
        return self.cli("approve", proposal_id, "--vault", self.vault, "--evidence", evidence)

    def add_context(self, kind: str, label: str, *extra: str) -> str:
        proposal = self.cli("add-context", label, "--kind", kind, "--vault", self.vault, *extra)
        self.approve(proposal["proposal"]["id"])
        return proposal["context"]["id"]

    def ledger_digest(self) -> str:
        path = Path(self.vault, "02-state", "events.jsonl")
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


class BootstrapIsAFactNotAScoreTests(VaultCase):
    def test_an_empty_vault_says_there_is_nothing_to_quote(self) -> None:
        report = self.cli("readiness", "--vault", self.vault)
        self.assertTrue(report["bootstrap_suggested"])
        self.assertTrue(report["no_total_by_design"])

    def test_it_does_not_depend_on_wanting_to_leave(self) -> None:
        # Someone employed and staying put still deserves a record worth having.
        self.cli("set-job-search", "off", "--vault", self.vault)
        before = self.cli("readiness", "--vault", self.vault)
        self.cli("set-job-search", "on", "--vault", self.vault)
        after = self.cli("readiness", "--vault", self.vault)
        self.assertEqual(before["bootstrap_suggested"], after["bootstrap_suggested"])

    def test_one_confirmed_context_is_already_something_to_stand_on(self) -> None:
        self.add_context("university", "○○大学")
        self.assertFalse(self.cli("readiness", "--vault", self.vault)["bootstrap_suggested"])

    def test_readiness_reports_dimensions_and_never_a_total(self) -> None:
        report = self.cli("readiness", "--vault", self.vault)
        self.assertIn("career_contexts", report["dimensions"])
        self.assertIn("experience_coverage", report["dimensions"])
        for key in report:
            self.assertNotIn("score", key)


class ContextCommandTests(VaultCase):
    def test_a_context_needs_a_kind(self) -> None:
        done = subprocess.run(
            [sys.executable, str(CLI), "add-context", "회사 A", "--vault", self.vault],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertNotEqual(done.returncode, 0)

    def test_a_proposal_alone_changes_no_canonical_state(self) -> None:
        before = self.ledger_digest()
        self.cli("add-context", "회사 A", "--kind", "company", "--vault", self.vault)
        self.assertEqual(self.ledger_digest(), before)

    def test_an_approved_context_is_listed(self) -> None:
        self.add_context("company", "회사 A")
        listed = self.cli("contexts", "--vault", self.vault)
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["contexts"][0]["kind"], "company")

    def test_contexts_filter_by_kind(self) -> None:
        self.add_context("company", "회사 A")
        self.add_context("university", "○○大学")
        self.assertEqual(self.cli("contexts", "--kind", "university", "--vault", self.vault)["count"], 1)

    def test_updating_an_unknown_context_is_refused(self) -> None:
        result = self.cli(
            "add-context", "회사 A", "--kind", "company", "--context-id", "ctx-nope",
            "--vault", self.vault,
        )
        self.assertEqual(result["error_code"], "CONTEXT_NOT_FOUND")

    def test_a_context_never_reaches_the_application_pipeline(self) -> None:
        self.add_context("company", "회사 A")
        self.assertFalse(Path(self.vault, "data", "pipeline.yml").exists())


class ExperiencesViewTests(VaultCase):
    def test_an_empty_view_is_empty_not_an_error(self) -> None:
        view = self.cli("experiences", "--vault", self.vault)
        self.assertEqual(view["count"], 0)
        self.assertEqual(view["unattached_evidence_ids"], [])

    def test_the_view_names_gaps_instead_of_scoring_them(self) -> None:
        view = self.cli("experiences", "--vault", self.vault)
        self.assertIn("experiences_without_individual_contribution", view["gaps"])
        self.assertTrue(view["no_total_by_design"])
        self.assertTrue(view["entries_are_references"])

    def test_an_unknown_context_filter_is_refused_rather_than_returning_nothing(self) -> None:
        result = self.cli("experiences", "--context", "ctx-nope", "--vault", self.vault)
        self.assertEqual(result["error_code"], "CONTEXT_NOT_FOUND")

    def test_reading_the_view_leaves_the_ledger_byte_identical(self) -> None:
        self.add_context("company", "회사 A")
        before = self.ledger_digest()
        for _ in range(3):
            self.cli("experiences", "--vault", self.vault)
            self.cli("contexts", "--vault", self.vault)
            self.cli("readiness", "--vault", self.vault)
        self.assertEqual(self.ledger_digest(), before)


class InventoryRoutingTests(VaultCase):
    """棚卸し routes to the inventory workflow and writes nothing on the way in."""

    def chat(self, message: str, vault: str | None = None) -> dict:
        return self.cli(
            "run", "--mode", "chat", "--vault", vault or self.vault, "--message", message,
        )

    def test_it_routes_to_the_inventory_skill(self) -> None:
        result = self.chat("지금까지의 경력을 정리하고 싶어")
        self.assertEqual(result["skill"]["skill"], "career-tanaoroshi")

    def test_it_proposes_nothing(self) -> None:
        # A seven-year career summarised from one sentence is exactly the invented history the
        # ledger exists to refuse. The next thing that happens is a question.
        result = self.chat("キャリアの棚卸しをしたい")
        self.assertIsNone(result["proposal"])
        self.assertTrue(result["changes_nothing"])
        self.assertEqual(self.ledger_digest(), "")

    def test_ordinary_upkeep_still_reaches_maintenance(self) -> None:
        result = self.chat("오늘 한 일 기록해줘")
        self.assertEqual(result["skill"]["skill"], "career-maintenance")
        self.assertIsNotNone(result["proposal"])

    def test_it_does_not_ask_which_hiring_market_first(self) -> None:
        # Someone recovering what they did at a university and two employers is answering "what
        # happened", not "new graduate or mid-career".
        untracked = str(Path(self._tmp.name) / "fresh")
        self.cli("init", "--vault", untracked)
        result = self.chat("キャリアの棚卸しをしたい", vault=untracked)
        self.assertNotIn("question", result)
        self.assertEqual(result["skill"]["skill"], "career-tanaoroshi")
        self.assertIsNone(result["track"])

    def test_it_leaves_job_search_alone(self) -> None:
        self.cli("set-job-search", "off", "--vault", self.vault)
        self.chat("이직 생각은 없는데 지금까지의 경력을 정리해두고 싶어")
        self.assertEqual(self.cli("status", "--vault", self.vault)["profile"]["job_search"], "off")


if __name__ == "__main__":
    unittest.main(verbosity=1)
