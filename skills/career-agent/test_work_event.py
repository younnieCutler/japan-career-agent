"""Contract tests for the `work_event` event type.

A work event records something that happened at the job the user already has. It rides the
existing append-only ledger, so the approval gate, supersession, and the numeric-claim rule all
apply to it unchanged. What is new here is what it may leave blank and what it must never invent.
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


def work_event_record(**overrides):
    """A minimal valid work event: no track, no stage, nothing invented."""
    event = {
        "id": "evt-work-1",
        "track": None,
        "stage": None,
        "flow_phase": None,
        "type": career_agent.WORK_EVENT_TYPE,
        "occurred_at": "2026-08-10T09:00:00Z",
        "title": "배치 장애 원인 파악",
        "summary": "운영팀과 알림 조건을 바꾸고 runbook을 수정했다.",
        "evidence": [],
        "source": "user",
        "next_action": None,
        "deadline": None,
        "status": "draft",
    }
    event.update(overrides)
    return event


class UnroutedFieldTests(unittest.TestCase):
    def test_a_work_event_may_have_no_track_stage_or_flow_phase(self) -> None:
        career_agent.validate_event(work_event_record())

    def test_a_work_event_may_still_state_a_track(self) -> None:
        career_agent.validate_event(work_event_record(track="chuto"))

    def test_a_work_event_rejects_a_track_outside_the_vocabulary(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(work_event_record(track="employed"))

    def test_other_event_types_still_require_a_track(self) -> None:
        record = work_event_record(type="event")
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(record)

    def test_other_event_types_still_require_a_stage(self) -> None:
        record = work_event_record(type="event", track="chuto", flow_phase="documents")
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(record)


class PayloadTests(unittest.TestCase):
    def test_every_payload_field_is_optional(self) -> None:
        career_agent.validate_event(work_event_record(work_event={}))

    def test_a_full_payload_is_accepted(self) -> None:
        career_agent.validate_event(
            work_event_record(
                work_event={
                    "role": "운영 담당",
                    "scope": "결제 배치",
                    "problem": "야간 배치가 조용히 실패했다",
                    "direct_actions": ["원인 로그 추적", "알림 조건 재정의"],
                    "stakeholder_coordination": ["운영팀과 알림 임계값 합의"],
                    "reporting": ["팀 리드에게 영향 범위와 복구 계획 공유"],
                    "individual_contribution": "원인 분석과 알림 조건 재설계를 직접 수행",
                    "team_result": "야간 장애 대응 절차가 팀 표준이 됨",
                    "metrics": [],
                    "improvements": ["runbook 갱신", "재발 방지 알림 추가"],
                    "learning": ["배치 실패는 조용히 지나간다는 것"],
                    "confidentiality": {"contains_confidential": False},
                }
            )
        )

    def test_a_misspelled_field_is_an_error_not_a_silent_unknown(self) -> None:
        with self.assertRaises(career_agent.CareerError) as caught:
            career_agent.validate_event(work_event_record(work_event={"metric": ["30% 감소"]}))
        self.assertIn("metric", str(caught.exception))

    def test_a_list_field_rejects_a_bare_string(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(work_event_record(work_event={"direct_actions": "로그 추적"}))

    def test_a_text_field_rejects_an_empty_string(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(work_event_record(work_event={"role": "   "}))

    def test_individual_contribution_and_team_result_stay_separate(self) -> None:
        payload = {"team_result": "팀 전체 처리량이 늘었다"}
        record = work_event_record(work_event=payload)
        career_agent.validate_event(record)
        # Nothing may promote a team outcome into a personal one by filling the blank.
        self.assertIsNone(record["work_event"].get("individual_contribution"))


class ConfidentialityTests(unittest.TestCase):
    def test_flagged_confidential_material_must_state_external_use(self) -> None:
        with self.assertRaises(career_agent.CareerError) as caught:
            career_agent.validate_event(
                work_event_record(work_event={"confidentiality": {"contains_confidential": True}})
            )
        self.assertIn("external_use", str(caught.exception))

    def test_unreviewed_is_a_valid_answer(self) -> None:
        career_agent.validate_event(
            work_event_record(
                work_event={
                    "confidentiality": {"contains_confidential": True, "external_use": "unknown"}
                }
            )
        )

    def test_external_use_rejects_a_value_outside_the_vocabulary(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(
                work_event_record(work_event={"confidentiality": {"external_use": "maybe"}})
            )

    def test_contains_confidential_rejects_a_non_boolean(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(
                work_event_record(work_event={"confidentiality": {"contains_confidential": "yes"}})
            )


class MetricTests(unittest.TestCase):
    def test_a_metric_without_evidence_cannot_be_confirmed(self) -> None:
        record = work_event_record(
            evidence=["JIRA-123"],
            status="confirmed",
            work_event={"metrics": ["야간 장애 30% 감소"]},
        )
        with self.assertRaises(career_agent.CareerError) as caught:
            career_agent.validate_event(record, for_confirmation=True)
        self.assertIn("numeric claim", str(caught.exception))

    def test_a_metric_present_in_evidence_confirms(self) -> None:
        career_agent.validate_event(
            work_event_record(
                evidence=["JIRA-123: 야간 장애 30% 감소를 확인"],
                status="confirmed",
                work_event={"metrics": ["야간 장애 30% 감소"]},
            ),
            for_confirmation=True,
        )

    def test_a_work_event_without_metrics_confirms_on_evidence_alone(self) -> None:
        career_agent.validate_event(
            work_event_record(
                evidence=["JIRA-123"],
                status="confirmed",
                work_event={"learning": ["배치 실패는 조용히 지나간다"]},
            ),
            for_confirmation=True,
        )

    def test_the_title_and_summary_check_is_unchanged(self) -> None:
        with self.assertRaises(career_agent.CareerError):
            career_agent.validate_event(
                work_event_record(
                    summary="장애를 50% 줄였다", evidence=["JIRA-123"], status="confirmed"
                ),
                for_confirmation=True,
            )


class QueryContractTests(unittest.TestCase):
    """`work-events` is the read contract downstream skills use instead of parsing the ledger."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name) / "vault"
        subprocess.run(
            [sys.executable, str(CLI), "init", "--vault", str(self.vault)],
            capture_output=True, text=True, check=True,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def seed(self, *rows: dict) -> None:
        path = self.vault / "02-state" / "events.jsonl"
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
        )

    def query(self, *args: str) -> dict:
        completed = subprocess.run(
            [sys.executable, str(CLI), "work-events", "--vault", str(self.vault), *args],
            capture_output=True, text=True, encoding="utf-8",
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr)
        return json.loads(completed.stdout)

    def test_an_empty_ledger_returns_an_empty_list(self) -> None:
        result = self.query()
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["work_events"], [])

    def test_only_work_events_are_returned(self) -> None:
        self.seed(
            work_event_record(id="evt-a", status="confirmed", evidence=["JIRA-1"]),
            {"id": "evt-b", "type": "user_report", "status": "confirmed", "occurred_at": "2026-08-01T00:00:00Z"},
        )
        result = self.query()
        self.assertEqual([row["id"] for row in result["work_events"]], ["evt-a"])

    def test_confirmed_excludes_drafts_and_superseded(self) -> None:
        self.seed(
            work_event_record(id="evt-draft", status="draft"),
            work_event_record(id="evt-old", status="superseded", evidence=["JIRA-1"]),
            work_event_record(id="evt-now", status="confirmed", evidence=["JIRA-2"]),
        )
        self.assertEqual(self.query()["count"], 3)
        confirmed = self.query("--confirmed")
        self.assertEqual([row["id"] for row in confirmed["work_events"]], ["evt-now"])

    def test_as_of_includes_the_boundary_day(self) -> None:
        self.seed(
            work_event_record(id="evt-1", occurred_at="2026-08-01T09:00:00Z", status="confirmed", evidence=["a"]),
            work_event_record(id="evt-2", occurred_at="2026-08-10T09:00:00Z", status="confirmed", evidence=["b"]),
        )
        self.assertEqual([row["id"] for row in self.query("--as-of", "2026-08-10")["work_events"]], ["evt-1", "evt-2"])
        self.assertEqual([row["id"] for row in self.query("--as-of", "2026-08-01")["work_events"]], ["evt-1"])
        self.assertEqual(self.query("--as-of", "2026-07-31")["count"], 0)

    def test_a_malformed_as_of_is_refused(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(CLI), "work-events", "--vault", str(self.vault), "--as-of", "2026-13-40"],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertNotEqual(completed.returncode, 0)

    def test_the_result_is_marked_untrusted(self) -> None:
        self.seed(work_event_record(status="confirmed", evidence=["JIRA-1"]))
        result = self.query()
        self.assertEqual(result["data_trust"], "untrusted_career_data")
        self.assertEqual(result["instruction_authority"], "none")

    def test_reading_does_not_change_the_ledger(self) -> None:
        # The strongest form of "a JD may change the lens, never the fact": running the query a
        # downstream mapping depends on leaves the canonical history byte-identical.
        self.seed(work_event_record(status="confirmed", evidence=["JIRA-1"]))
        path = self.vault / "02-state" / "events.jsonl"
        before = path.read_bytes()
        self.query("--confirmed", "--as-of", "2026-08-10")
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
