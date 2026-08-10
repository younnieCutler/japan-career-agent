"""Contract tests for PROJECT, the context a work event happened in.

A project is a container and a narrative layer. The work events are the evidence. The tests below
are mostly about keeping that distinction: a project may not become a claim about the person, a
link may not change what happened, and no amount of missing project information may stop someone
writing down what they did today.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))
import career_agent  # noqa: E402


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

    def capture(self, message: str = "오늘 한 일") -> str:
        # The maintenance marker is what routes to the work-event path; the tests here are about
        # what happens after that, not about the routing itself.
        note = self.cli(
            "run", "--mode", "chat", "--vault", self.vault, "--message", f"{message}. 업무일지 남겨줘",
        )
        return note["proposal"]["id"]

    def add_project(self, title: str, *extra: str) -> str:
        proposal = self.cli("add-project", title, "--vault", self.vault, *extra)
        self.cli("approve", proposal["proposal"]["id"], "--vault", self.vault, "--evidence", "user")
        return proposal["project"]["id"]

    def ledger(self) -> list[dict]:
        path = Path(self.vault, "02-state", "events.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CaptureIsNeverBlockedTests(VaultCase):
    def test_a_user_with_no_projects_can_still_record_work(self) -> None:
        proposal = self.capture("오늘 배치 장애 원인 찾고 알림 조건 수정")
        approved = self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        self.assertTrue(approved.get("applied", approved.get("approved")))
        self.assertEqual(self.cli("projects", "--vault", self.vault)["count"], 0)

    def test_a_work_event_with_no_project_is_valid(self) -> None:
        proposal = self.capture()
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        rows = self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"]
        self.assertEqual(career_agent.work_event_project_ids(rows[0]), [])

    def test_general_work_can_be_recorded_as_belonging_to_no_project(self) -> None:
        self.add_project("결제 시스템 안정화")
        proposal = self.capture()
        result = self.cli("link-work-event", proposal, "--vault", self.vault, "--none")
        self.assertIsNone(result["work_event"]["primary_project_id"])
        self.assertEqual(result["work_event"]["related_project_ids"], [])


class ProjectRecordTests(VaultCase):
    def test_a_title_is_the_only_thing_needed(self) -> None:
        self.add_project("결제 시스템 안정화")
        record = self.cli("projects", "--vault", self.vault)["projects"][0]
        self.assertEqual(record["title"], "결제 시스템 안정화")
        self.assertEqual(record["status"], "unknown")
        self.assertNotIn("role", record)

    def test_later_events_fill_the_record_without_erasing_it(self) -> None:
        project_id = self.add_project("결제 시스템 안정화", "--role", "운영 담당")
        self.add_project("결제 시스템 안정화", "--project-id", project_id, "--status", "completed")
        record = self.cli("projects", "--vault", self.vault)["projects"][0]
        self.assertEqual(record["role"], "운영 담당")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(self.cli("projects", "--vault", self.vault)["count"], 1)

    def test_a_period_learned_over_two_turns_keeps_both_ends(self) -> None:
        # A project gets a start when it begins and an end when it closes. Replacing the whole
        # object on the second turn would drop the start, which is the opposite of what the
        # projection promises everywhere else.
        project_id = self.add_project("결제 시스템 안정화", "--from", "2026-04")
        self.add_project("결제 시스템 안정화", "--project-id", project_id, "--to", "2026-06")
        record = self.cli("projects", "--vault", self.vault)["projects"][0]
        self.assertEqual(record["period"], {"from": "2026-04", "to": "2026-06"})

    def test_an_external_label_is_kept_beside_the_real_title(self) -> None:
        self.add_project("내부 결제 Phoenix 프로젝트",
                         "--external-label", "payment reliability project")
        record = self.cli("projects", "--vault", self.vault)["projects"][0]
        self.assertEqual(record["title"], "내부 결제 Phoenix 프로젝트")
        self.assertEqual(record["external_label"], "payment reliability project")

    def test_the_next_action_names_the_proposal_not_the_project(self) -> None:
        # `approve` takes a proposal id; naming the project id handed the user a command that
        # could not work.
        proposed = self.cli("add-project", "결제 시스템 안정화", "--vault", self.vault)
        listed = self.cli("proposals", "--vault", self.vault, "--id", proposed["proposal"]["id"])
        self.assertIn(proposed["proposal"]["id"], listed["proposal"]["next_action"])
        self.assertNotIn(proposed["project"]["id"], listed["proposal"]["next_action"])

    def test_a_draft_project_is_not_listed(self) -> None:
        self.cli("add-project", "아직 확정 안 함", "--vault", self.vault)
        self.assertEqual(self.cli("projects", "--vault", self.vault)["count"], 0)

    def test_an_unknown_project_id_is_refused(self) -> None:
        result = self.cli("add-project", "x", "--vault", self.vault, "--project-id", "prj-nope")
        self.assertEqual(result["error_code"], "PROJECT_NOT_FOUND")

    def test_a_project_event_moves_no_route_and_no_mode(self) -> None:
        before = self.cli("status", "--vault", self.vault)["state"]
        self.add_project("결제 시스템 안정화")
        after = self.cli("status", "--vault", self.vault)["state"]
        for field in ("track", "stage", "flow_phase", "career_mode"):
            self.assertEqual(after[field], before[field], field)


class LinkageTests(VaultCase):
    def test_one_work_event_serves_many_projects_without_being_copied(self) -> None:
        first = self.add_project("결제 시스템 안정화")
        second = self.add_project("데이터 파이프라인 개편")
        proposal = self.capture("스키마 변경하면서 결제 배치도 같이 손봄")
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", first, "--related", second)
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-2")

        work_rows = [row for row in self.ledger() if row["type"] == career_agent.WORK_EVENT_TYPE]
        self.assertEqual(len(work_rows), 1)
        self.assertEqual(self.cli("project-timeline", first, "--vault", self.vault)["count"], 1)
        self.assertEqual(self.cli("project-timeline", second, "--vault", self.vault)["count"], 1)
        self.assertEqual(
            self.cli("project-timeline", first, "--vault", self.vault)["timeline"][0]["event_id"],
            self.cli("project-timeline", second, "--vault", self.vault)["timeline"][0]["event_id"],
        )

    def test_primary_and_related_are_both_preserved(self) -> None:
        first, second, third = (self.add_project(name) for name in ("A", "B", "C"))
        proposal = self.capture()
        result = self.cli(
            "link-work-event", proposal, "--vault", self.vault,
            "--project", first, "--related", second, "--related", third,
        )
        self.assertEqual(result["work_event"]["primary_project_id"], first)
        self.assertEqual(result["work_event"]["related_project_ids"], [second, third])

    def test_relinking_does_not_change_what_happened(self) -> None:
        first = self.add_project("A")
        second = self.add_project("B")
        proposal = self.capture("배치 장애 원인 파악")
        self.cli("review-work-event", proposal, "--vault", self.vault,
                 "--json", '{"individual_contribution": "원인 분석을 직접 수행", "work_date": "2026-06"}')
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", first)
        before = self.cli("proposals", "--vault", self.vault, "--id", proposal)["proposal"]["event"]
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", second)
        after = self.cli("proposals", "--vault", self.vault, "--id", proposal)["proposal"]["event"]

        self.assertEqual(after["summary"], before["summary"])
        for field in ("individual_contribution", "work_date"):
            self.assertEqual(after["work_event"][field], before["work_event"][field])
        self.assertNotEqual(after["work_event"]["primary_project_id"],
                            before["work_event"]["primary_project_id"])

    def test_an_unknown_project_cannot_be_linked(self) -> None:
        proposal = self.capture()
        result = self.cli("link-work-event", proposal, "--vault", self.vault, "--project", "prj-nope")
        self.assertEqual(result["error_code"], "PROJECT_NOT_FOUND")

    def test_none_cannot_be_combined_with_a_project(self) -> None:
        first = self.add_project("A")
        proposal = self.capture()
        result = self.cli("link-work-event", proposal, "--vault", self.vault, "--project", first, "--none")
        self.assertEqual(result["error_code"], "INVALID_INPUT")

    def test_a_project_may_not_be_both_primary_and_related(self) -> None:
        first = self.add_project("A")
        proposal = self.capture()
        result = self.cli("link-work-event", proposal, "--vault", self.vault,
                          "--project", first, "--related", first)
        # The runtime drops the duplicate rather than storing the same project twice.
        self.assertEqual(result["work_event"]["related_project_ids"], [])


class WorkDateTests(VaultCase):
    def test_a_month_is_a_real_answer(self) -> None:
        proposal = self.capture("지난 6월 결제 migration 정리")
        result = self.cli("review-work-event", proposal, "--vault", self.vault,
                          "--json", '{"work_date": "2026-06"}')
        self.assertEqual(result["work_event"]["work_date"], "2026-06")

    def test_an_absent_work_date_does_not_block_anything(self) -> None:
        proposal = self.capture()
        approved = self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        self.assertTrue(approved.get("applied", approved.get("approved")))

    def test_an_impossible_date_is_refused(self) -> None:
        proposal = self.capture()
        for bad in ("2026-13", "2026-02-30", "yesterday", "2026"):
            with self.subTest(bad=bad):
                result = self.cli("review-work-event", proposal, "--vault", self.vault,
                                  "--json", json.dumps({"work_date": bad}))
                self.assertFalse(result.get("ok", False))

    def test_recency_prefers_the_stated_date_over_the_capture_time(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        proposal = self.capture("지난 6월 결제 migration")
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        self.cli("review-work-event", proposal, "--vault", self.vault, "--json", '{"work_date": "2026-06"}')
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-9")
        entry = self.cli("project-timeline", project_id, "--vault", self.vault)["timeline"][0]
        self.assertEqual(entry["date"], "2026-06")
        self.assertTrue(entry["dated"])

    def test_an_undated_event_falls_back_to_capture_time_and_says_so(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        proposal = self.capture()
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        entry = self.cli("project-timeline", project_id, "--vault", self.vault)["timeline"][0]
        self.assertFalse(entry["dated"])


class WeeklyReviewTests(VaultCase):
    def confirm(self, message: str, project_id: str | None = None, payload: dict | None = None) -> str:
        proposal = self.capture(message)
        if project_id:
            self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        if payload:
            self.cli("review-work-event", proposal, "--vault", self.vault, "--json", json.dumps(payload, ensure_ascii=False))
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        return proposal

    def test_events_are_grouped_by_project(self) -> None:
        first = self.add_project("결제 시스템 안정화")
        second = self.add_project("데이터 파이프라인 개편")
        self.confirm("배치 장애 원인 분석", first)
        self.confirm("schema migration", second)
        self.confirm("공통 업무 정리")
        groups = self.cli("weekly-review", "--vault", self.vault)["groups"]
        titles = [group["title"] for group in groups]
        self.assertIn("결제 시스템 안정화", titles)
        self.assertIn("데이터 파이프라인 개편", titles)
        self.assertIn(None, titles)  # work belonging to no project still shows up

    def test_a_backfilled_note_appears_in_the_week_it_was_captured(self) -> None:
        # The point of this view is "what did I write down and not finish structuring". A note
        # captured today about last June is exactly that, so windowing on `work_date` would hide
        # the one event most in need of a contribution and a result.
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm("지난 6월 결제 migration", project_id, {"work_date": "2026-06"})
        groups = self.cli("weekly-review", "--vault", self.vault)["groups"]
        entry = groups[0]["events"][0]
        self.assertEqual(entry["work_date"], "2026-06")
        self.assertNotEqual(entry["captured_on"], "2026-06")

    def test_the_gaps_named_are_the_ones_worth_asking_about(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm("배치 장애 원인 분석", project_id)
        entry = self.cli("weekly-review", "--vault", self.vault)["groups"][0]["events"][0]
        self.assertIn("individual_contribution", entry["gaps"])
        self.assertIn("result", entry["gaps"])

    def test_a_filled_event_is_not_nagged_about(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm("배치 장애 원인 분석", project_id, {
            "individual_contribution": "원인 분석과 알림 재설계를 직접 수행",
            "improvements": ["runbook 갱신"],
            "learning": ["배치 실패는 조용히 지나간다"],
        })
        entry = self.cli("weekly-review", "--vault", self.vault)["groups"][0]["events"][0]
        self.assertEqual(entry["gaps"], [])

    def test_pending_captures_are_the_point_of_the_review(self) -> None:
        # A quick note lives on proposals.jsonl until it is approved. Reading only the ledger
        # showed an empty week to a user who had been capturing all week — which is precisely
        # backwards, since the unfinished ones are what a review is for.
        project_id = self.add_project("결제 시스템 안정화")
        draft = self.capture("배치 장애 원인 분석")
        self.cli("link-work-event", draft, "--vault", self.vault, "--project", project_id)
        self.confirm("알림 조건 개선", project_id)

        review = self.cli("weekly-review", "--vault", self.vault)
        self.assertEqual(review["draft_count"], 1)
        self.assertEqual(review["confirmed_count"], 1)
        rows = {row["status"]: row for group in review["groups"] for row in group["events"]}
        self.assertEqual(rows["draft"]["proposal_id"], draft)
        self.assertIsNone(rows["confirmed"]["proposal_id"])

    def test_a_draft_can_be_acted_on_from_what_the_review_returns(self) -> None:
        self.add_project("결제 시스템 안정화")
        self.capture("배치 장애 원인 분석")
        row = self.cli("weekly-review", "--vault", self.vault)["groups"][0]["events"][0]
        filled = self.cli("review-work-event", row["proposal_id"], "--vault", self.vault,
                          "--json", '{"individual_contribution": "원인 분석을 직접 수행"}')
        self.assertTrue(filled["ok"])
        self.assertNotIn(
            "individual_contribution",
            self.cli("weekly-review", "--vault", self.vault)["groups"][0]["events"][0]["gaps"],
        )

    def test_an_empty_week_is_not_an_error(self) -> None:
        result = self.cli("weekly-review", "--vault", self.vault)
        self.assertEqual(result["event_count"], 0)
        self.assertEqual(result["groups"], [])


class TeamAttributionSurvivesProjectsTests(VaultCase):
    def test_a_team_result_is_not_promoted_by_belonging_to_a_project(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        proposal = self.capture("팀에서 처리량을 올렸다")
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        result = self.cli("review-work-event", proposal, "--vault", self.vault,
                          "--json", '{"team_result": "팀 전체 처리량이 늘었다"}')
        self.assertIsNone(result["work_event"].get("individual_contribution"))

    def test_a_metric_still_needs_evidence_inside_a_project(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        proposal = self.capture("배치 개선")
        self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        self.cli("review-work-event", proposal, "--vault", self.vault,
                 "--json", '{"metrics": ["야간 장애 30% 감소"]}')
        approved = self.cli("approve", proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        self.assertFalse(approved.get("ok", False))
        self.assertIn("numeric claim", approved["error"])


class BackwardCompatibilityTests(VaultCase):
    def test_a_work_event_without_project_fields_still_validates(self) -> None:
        # Every event written before this change looks like this.
        event = {
            "id": "evt-old", "track": None, "stage": None, "flow_phase": None,
            "type": career_agent.WORK_EVENT_TYPE, "occurred_at": "2026-08-01T00:00:00Z",
            "title": "t", "summary": "s", "evidence": ["JIRA-1"], "source": "user_message",
            "next_action": None, "deadline": None, "status": "confirmed",
            "work_event": {"role": "운영 담당"},
        }
        career_agent.validate_event(event, for_confirmation=True)
        self.assertEqual(career_agent.work_event_project_ids(event), [])
        self.assertEqual(career_agent.work_event_date(event), "2026-08-01")

    def test_a_vault_with_no_project_events_lists_none(self) -> None:
        self.assertEqual(self.cli("projects", "--vault", self.vault)["projects"], [])


if __name__ == "__main__":
    unittest.main()
