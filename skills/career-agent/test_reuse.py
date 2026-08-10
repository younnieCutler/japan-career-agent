"""Evidence reuse and maintenance intelligence.

The reads a JD answer is built from, and the check-ins that keep the record from going stale. Both
are read-only by contract: selecting evidence for a posting must not touch the ledger, and a
maintenance suggestion must not touch anything at all.
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

    def add_project(self, title: str, *extra: str) -> str:
        proposal = self.cli("add-project", title, "--vault", self.vault, *extra)
        self.cli("approve", proposal["proposal"]["id"], "--vault", self.vault, "--evidence", "user")
        return proposal["project"]["id"]

    def confirm_work(self, message: str, project_id: str | None = None,
                     payload: dict | None = None, evidence: str = "JIRA-1") -> str:
        note = self.cli("run", "--mode", "chat", "--vault", self.vault,
                        "--message", f"{message}. 업무일지 남겨줘")
        proposal = note["proposal"]["id"]
        if project_id:
            self.cli("link-work-event", proposal, "--vault", self.vault, "--project", project_id)
        if payload:
            self.cli("review-work-event", proposal, "--vault", self.vault,
                     "--json", json.dumps(payload, ensure_ascii=False))
        self.cli("approve", proposal, "--vault", self.vault, "--evidence", evidence)
        return proposal

    def ledger_bytes(self) -> bytes:
        return Path(self.vault, "02-state", "events.jsonl").read_bytes()


class EvidencePoolTests(VaultCase):
    def test_only_confirmed_evidence_is_returned(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("배치 장애 원인 분석", project_id)
        # A pending capture that was never approved.
        self.cli("run", "--mode", "chat", "--vault", self.vault, "--message", "초안입니다. 업무일지")
        pool = self.cli("evidence-pool", "--vault", self.vault)
        self.assertTrue(pool["confirmed_only"])
        self.assertEqual(pool["confirmed_work_event_count"], 1)

    def test_evidence_is_grouped_under_its_projects(self) -> None:
        first = self.add_project("결제 시스템 안정화")
        second = self.add_project("데이터 파이프라인 개편")
        self.confirm_work("배치 장애 원인 분석", first)
        self.confirm_work("schema migration", second)
        pool = self.cli("evidence-pool", "--vault", self.vault)
        by_title = {p["title"]: p for p in pool["projects"]}
        self.assertEqual(len(by_title["결제 시스템 안정화"]["work_events"]), 1)
        self.assertEqual(len(by_title["데이터 파이프라인 개편"]["work_events"]), 1)

    def test_work_belonging_to_no_project_is_still_offered(self) -> None:
        self.confirm_work("공통 운영 업무")
        pool = self.cli("evidence-pool", "--vault", self.vault)
        self.assertEqual(len(pool["unattached_work_events"]), 1)

    def test_capture_time_is_never_presented_as_a_work_date(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("지난 6월 migration", project_id, {"work_date": "2026-06"})
        self.confirm_work("날짜 안 밝힘", project_id)
        rows = self.cli("evidence-pool", "--vault", self.vault)["projects"][0]["work_events"]
        dated = {row["recency"]: row["dated"] for row in rows}
        self.assertTrue(dated["2026-06"])
        self.assertIn(False, dated.values())

    def test_a_dangling_project_reference_does_not_hide_the_evidence(self) -> None:
        # `link-work-event` refuses an unknown project, so this should be unreachable. Dropping
        # confirmed evidence out of the view a JD is answered from is the wrong way to find out
        # otherwise, so it lands in the unattached list instead of vanishing.
        self.confirm_work("장애 대응")
        path = Path(self.vault, "02-state", "events.jsonl")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row["type"] == "work_event":
                row["work_event"]["primary_project_id"] = "prj-vanished"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )
        pool = self.cli("evidence-pool", "--vault", self.vault)
        self.assertEqual(pool["confirmed_work_event_count"], 1)
        self.assertEqual(len(pool["unattached_work_events"]), 1)

    def test_reading_the_pool_does_not_change_the_ledger(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("배치 장애 원인 분석", project_id)
        before = self.ledger_bytes()
        self.cli("evidence-pool", "--vault", self.vault)
        self.cli("evidence-pool", "--vault", self.vault, "--as-of", "2026-08-10")
        self.assertEqual(self.ledger_bytes(), before)


class SelectionDoesNotTouchTheRecordTests(VaultCase):
    """A JD may change the lens, never the fact — asserted against the bytes."""

    def test_recording_a_selection_leaves_the_ledger_identical(self) -> None:
        import yaml

        workdir = Path(self._tmp.name) / "work"
        workdir.mkdir()
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("배치 장애 원인 분석", project_id,
                          {"individual_contribution": "원인 분석을 직접 수행"})
        event_id = self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"][0]["id"]
        before = self.ledger_bytes()

        pipeline_cli = ROOT / "scripts" / "pipeline.py"
        subprocess.run(
            [sys.executable, str(pipeline_cli), "upsert", "acme", "--json",
             json.dumps({"name": "Acme"})],
            cwd=workdir, capture_output=True, text=True, check=True,
        )
        subprocess.run(
            [sys.executable, str(pipeline_cli), "update", "acme", "--json", json.dumps({
                "primary_project_ids": [project_id],
                "primary_experience_ids": [event_id],
                "unknown_requirements": ["people management"],
            })],
            cwd=workdir, capture_output=True, text=True, check=True,
        )
        self.assertEqual(self.ledger_bytes(), before)

        entry = yaml.safe_load((workdir / "data" / "pipeline.yml").read_text(encoding="utf-8"))["companies"][0]
        self.assertEqual(entry["primary_project_ids"], [project_id])
        self.assertEqual(entry["unknown_requirements"], ["people management"])

    def test_two_companies_can_select_the_same_evidence_differently(self) -> None:
        import yaml

        workdir = Path(self._tmp.name) / "work2"
        workdir.mkdir()
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("장애 대응과 운영 개선", project_id)
        event_id = self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"][0]["id"]
        before = self.ledger_bytes()

        pipeline_cli = ROOT / "scripts" / "pipeline.py"
        for slug, primary in (("alpha", [event_id]), ("beta", [])):
            subprocess.run(
                [sys.executable, str(pipeline_cli), "upsert", slug, "--json",
                 json.dumps({"name": slug})],
                cwd=workdir, capture_output=True, text=True, check=True,
            )
            subprocess.run(
                [sys.executable, str(pipeline_cli), "update", slug, "--json", json.dumps({
                    "primary_project_ids": [project_id],
                    "primary_experience_ids": primary,
                    "supporting_experience_ids": [] if primary else [event_id],
                })],
                cwd=workdir, capture_output=True, text=True, check=True,
            )
        companies = yaml.safe_load((workdir / "data" / "pipeline.yml").read_text(encoding="utf-8"))["companies"]
        angles = {c["slug"]: (c["primary_experience_ids"], c["supporting_experience_ids"]) for c in companies}
        self.assertNotEqual(angles["alpha"], angles["beta"])
        self.assertEqual(self.ledger_bytes(), before)


class MaintenanceCheckTests(VaultCase):
    def test_an_empty_vault_produces_no_nudge(self) -> None:
        result = self.cli("maintenance-check", "--vault", self.vault)
        self.assertEqual(result["suggestions"], [])

    def test_a_quiet_but_tidy_record_produces_no_nudge(self) -> None:
        project_id = self.add_project("결제 시스템 안정화", "--summary", "결제 배치 안정화")
        self.confirm_work("배치 장애 원인 분석", project_id,
                          {"individual_contribution": "원인 분석을 직접 수행"})
        self.assertEqual(self.cli("maintenance-check", "--vault", self.vault)["suggestions"], [])

    def test_a_pile_of_notes_on_one_project_is_worth_mentioning(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        for index in range(3):
            self.confirm_work(f"작업 {index}", project_id,
                              {"individual_contribution": "직접 수행"}, evidence=f"JIRA-{index}")
        kinds = [s["kind"] for s in self.cli("maintenance-check", "--vault", self.vault)["suggestions"]]
        self.assertIn("review_recent_project_activity", kinds)

    def test_a_pile_of_pending_notes_is_worth_mentioning_too(self) -> None:
        # The moment a review helps most is before any of the week's notes has been approved.
        # Reading only the ledger reports "nothing this week" to the user who has been capturing
        # all week, which is exactly backwards.
        project_id = self.add_project("결제 시스템 안정화")
        for index in range(3):
            note = self.cli("run", "--mode", "chat", "--vault", self.vault,
                            "--message", f"작업 {index} 기록. 업무일지 남겨줘")
            self.cli("link-work-event", note["proposal"]["id"], "--vault", self.vault,
                     "--project", project_id)
        suggestions = self.cli("maintenance-check", "--vault", self.vault)["suggestions"]
        activity = [s for s in suggestions if s["kind"] == "review_recent_project_activity"]
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity[0]["count"], 3)
        self.assertEqual(activity[0]["project_id"], project_id)

    def test_a_pending_note_is_not_reported_as_a_finished_record(self) -> None:
        # Drafts count towards "you have been busy here"; they must not count towards the checks
        # that describe confirmed records, or every fresh capture would raise its own complaint.
        self.cli("run", "--mode", "chat", "--vault", self.vault,
                 "--message", "이번 작업 기록. 업무일지 남겨줘")
        kinds = [s["kind"] for s in self.cli("maintenance-check", "--vault", self.vault)["suggestions"]]
        self.assertNotIn("individual_contribution_unknown", kinds)

    def test_a_closed_project_without_a_summary_is_worth_mentioning(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.add_project("결제 시스템 안정화", "--project-id", project_id, "--status", "completed")
        kinds = [s["kind"] for s in self.cli("maintenance-check", "--vault", self.vault)["suggestions"]]
        self.assertIn("project_ended_without_summary", kinds)

    def test_unreviewed_external_use_is_worth_mentioning(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("고객사 관련 작업", project_id, {
            "individual_contribution": "직접 수행",
            "confidentiality": {"contains_confidential": True, "external_use": "unknown"},
        })
        kinds = [s["kind"] for s in self.cli("maintenance-check", "--vault", self.vault)["suggestions"]]
        self.assertIn("external_use_unreviewed", kinds)

    def test_at_most_one_suggestion_is_meant_to_be_said(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("작업", project_id)
        self.assertEqual(self.cli("maintenance-check", "--vault", self.vault)["mention_at_most"], 1)

    def test_maintenance_changes_nothing(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("작업", project_id)
        before_ledger = self.ledger_bytes()
        before_state = self.cli("status", "--vault", self.vault)
        result = self.cli("maintenance-check", "--vault", self.vault)
        after_state = self.cli("status", "--vault", self.vault)

        self.assertTrue(result["changes_nothing"])
        self.assertEqual(self.ledger_bytes(), before_ledger)
        self.assertEqual(after_state["state"], before_state["state"])
        self.assertEqual(after_state["profile"]["job_search"], before_state["profile"]["job_search"])


class ReadinessTests(VaultCase):
    def test_there_is_no_total(self) -> None:
        result = self.cli("readiness", "--vault", self.vault)
        self.assertTrue(result["no_total_by_design"])
        self.assertNotIn("score", json.dumps(result))

    def test_dimensions_are_reported_separately(self) -> None:
        project_id = self.add_project("결제 시스템 안정화", "--summary", "안정화")
        self.confirm_work("장애 대응", project_id, {"individual_contribution": "직접 수행"})
        dimensions = self.cli("readiness", "--vault", self.vault)["dimensions"]
        self.assertEqual(dimensions["individual_contribution"], "Confirmed")
        self.assertEqual(dimensions["metrics_evidence"], "Unknown")
        self.assertEqual(dimensions["project_history"], "Confirmed")

    def test_an_undated_record_is_not_recent_experience(self) -> None:
        # "I wrote this down today about work I did five years ago" must not read as confirmed
        # recent experience. Capture time is a fine tiebreak for ordering a timeline and a wrong
        # answer to "is this recent"; Unknown stays Unknown.
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("오래 전 일인데 날짜는 기억 안 남", project_id)
        result = self.cli("readiness", "--vault", self.vault)
        self.assertEqual(result["dimensions"]["recent_work_evidence"], "Unknown")
        self.assertEqual(result["counts"]["dated_work_events"], 0)
        self.assertEqual(result["counts"]["undated_work_events"], 1)

    def test_dated_recent_evidence_reads_as_confirmed(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("이번 달 작업", project_id, {"work_date": "2026-08"})
        self.assertEqual(
            self.cli("readiness", "--vault", self.vault)["dimensions"]["recent_work_evidence"],
            "Confirmed",
        )

    def test_dated_but_old_evidence_reads_as_stale(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("한참 전 작업", project_id, {"work_date": "2019-03"})
        self.assertEqual(
            self.cli("readiness", "--vault", self.vault)["dimensions"]["recent_work_evidence"],
            "Stale",
        )

    def test_a_mix_of_dated_and_undated_is_partial(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("이번 달 작업", project_id, {"work_date": "2026-08"}, evidence="JIRA-1")
        self.confirm_work("날짜 모르는 작업", project_id, evidence="JIRA-2")
        self.assertEqual(
            self.cli("readiness", "--vault", self.vault)["dimensions"]["recent_work_evidence"],
            "Partial",
        )

    def test_old_dated_work_beside_an_undated_note_is_not_stale(self) -> None:
        # Stale asserts the recent record is empty. The undated note could be last week's work, so
        # that assertion is not available -- the honest reading is Partial, the same as when the
        # dated half is recent.
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("한참 전 작업", project_id, {"work_date": "2019-03"}, evidence="JIRA-1")
        self.confirm_work("날짜 모르는 작업", project_id, evidence="JIRA-2")
        self.assertEqual(
            self.cli("readiness", "--vault", self.vault)["dimensions"]["recent_work_evidence"],
            "Partial",
        )

    def test_readiness_is_not_intent(self) -> None:
        project_id = self.add_project("결제 시스템 안정화", "--summary", "안정화")
        self.confirm_work("장애 대응", project_id,
                          {"work_date": "2026-08", "individual_contribution": "직접 수행"})
        result = self.cli("readiness", "--vault", self.vault)
        # A record that is current in every dimension still says nothing about wanting to leave.
        self.assertEqual(result["dimensions"]["recent_work_evidence"], "Confirmed")
        self.assertEqual(result["dimensions"]["individual_contribution"], "Confirmed")
        self.assertEqual(result["job_search"], "off")

    def test_reading_readiness_does_not_change_the_ledger(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("장애 대응", project_id)
        before = self.ledger_bytes()
        self.cli("readiness", "--vault", self.vault)
        self.assertEqual(self.ledger_bytes(), before)


class ProjectEndReviewTests(VaultCase):
    def test_closing_a_project_does_not_touch_its_work_events(self) -> None:
        project_id = self.add_project("결제 시스템 안정화")
        self.confirm_work("장애 대응", project_id, {"individual_contribution": "직접 수행"})
        events_before = [
            row for row in self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"]
        ]
        self.add_project("결제 시스템 안정화", "--project-id", project_id,
                         "--status", "completed", "--summary", "장애 대응부터 재발 방지까지 담당",
                         "--from", "2026-04", "--to", "2026-06")
        events_after = [
            row for row in self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"]
        ]
        self.assertEqual(events_after, events_before)

        record = self.cli("projects", "--vault", self.vault)["projects"][0]
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["period"], {"from": "2026-04", "to": "2026-06"})

    def test_a_summary_is_not_evidence_on_its_own(self) -> None:
        # The summary lives on the project. The evidence query returns work events, and a project
        # with no work events under it contributes none.
        project_id = self.add_project("서머리만 있는 프로젝트", "--summary", "대단한 성과를 냈다")
        pool = self.cli("evidence-pool", "--vault", self.vault)
        entry = next(p for p in pool["projects"] if p["id"] == project_id)
        self.assertEqual(entry["work_events"], [])
        self.assertEqual(pool["confirmed_work_event_count"], 0)


if __name__ == "__main__":
    unittest.main()
