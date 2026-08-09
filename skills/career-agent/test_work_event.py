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


# Seeded rows use a fixed past instant so the query tests never depend on the day, the timezone,
# or the clock of the machine running them.
PAST_DAY = "2026-08-01"
PAST = f"{PAST_DAY}T09:00:00Z"


def work_event_record(**overrides):
    """A minimal valid work event: no track, no stage, nothing invented."""
    event = {
        "id": "evt-work-1",
        "track": None,
        "stage": None,
        "flow_phase": None,
        "type": career_agent.WORK_EVENT_TYPE,
        "occurred_at": PAST,
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
            work_event_record(id="evt-a", occurred_at=PAST, status="confirmed", evidence=["JIRA-1"]),
            {"id": "evt-b", "type": "user_report", "status": "confirmed", "occurred_at": PAST},
        )
        result = self.query("--as-of", PAST_DAY)
        self.assertEqual([row["id"] for row in result["work_events"]], ["evt-a"])

    def test_confirmed_excludes_drafts_and_superseded(self) -> None:
        self.seed(
            work_event_record(id="evt-draft", occurred_at=PAST, status="draft"),
            work_event_record(id="evt-old", occurred_at=PAST, status="superseded", evidence=["JIRA-1"]),
            work_event_record(id="evt-now", occurred_at=PAST, status="confirmed", evidence=["JIRA-2"]),
        )
        self.assertEqual(self.query("--as-of", PAST_DAY)["count"], 3)
        confirmed = self.query("--confirmed", "--as-of", PAST_DAY)
        self.assertEqual([row["id"] for row in confirmed["work_events"]], ["evt-now"])

    def test_the_default_boundary_is_the_utc_date(self) -> None:
        # The regression CI caught. `occurred_at` is a UTC instant; the default boundary used to be
        # the local calendar day, and the two disagree for the hours after UTC midnight. West of
        # UTC that means an event the user just recorded carries tomorrow's UTC day and their own
        # query drops it. Asserting the default directly pins the decision at every hour — a
        # behavioural test would only fail during the window where the dates actually diverge.
        default = career_agent.build_parser().parse_args(
            ["work-events", "--vault", str(self.vault)]
        ).as_of
        self.assertEqual(default, career_agent.utc_now()[:10])

    def test_an_event_recorded_now_is_visible(self) -> None:
        self.seed(work_event_record(id="evt-now", occurred_at=career_agent.utc_now(),
                                    status="confirmed", evidence=["JIRA-1"]))
        self.assertEqual([row["id"] for row in self.query()["work_events"]], ["evt-now"])
        self.assertEqual([row["id"] for row in self.query("--confirmed")["work_events"]], ["evt-now"])

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


class ReviewMutationTests(unittest.TestCase):
    """Capture is one sentence, so the structure has to be fillable before confirmation.

    Without this path the payload stayed `{}` from capture through confirmation and the JD
    requirement mapping, which reads `individual_contribution` and the rest, had nothing to read.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        self.cli("setup", "--vault", self.vault, "--track", "chuto")
        self.proposal = self.cli(
            "run", "--mode", "chat", "--vault", self.vault, "--message", "업무일지 남겨줘"
        )["proposal"]["id"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def cli(self, *args: str) -> dict:
        # Expected blockers are reported as JSON on stderr with exit 2, as every other command
        # here does; only the stream differs from the success path.
        completed = subprocess.run(
            [sys.executable, str(CLI), *args], capture_output=True, text=True, encoding="utf-8",
        )
        if completed.returncode not in (0, 2):
            raise AssertionError(f"{args}\n{completed.stdout}\n{completed.stderr}")
        return json.loads(completed.stdout or completed.stderr)

    def review(self, payload: dict, *extra: str) -> dict:
        return self.cli(
            "review-work-event", self.proposal, "--vault", self.vault,
            "--json", json.dumps(payload, ensure_ascii=False), *extra,
        )

    def confirmed_payload(self) -> dict:
        self.cli("approve", self.proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        rows = self.cli("work-events", "--vault", self.vault, "--confirmed")["work_events"]
        return rows[0]["work_event"]

    def test_capture_starts_empty(self) -> None:
        rows = self.cli("proposals", "--vault", self.vault, "--id", self.proposal)
        self.assertEqual(rows["proposal"]["event"]["work_event"], {})

    def test_fields_reach_the_confirmed_event(self) -> None:
        self.review({
            "role": "운영 담당",
            "direct_actions": ["원인 로그 추적"],
            "individual_contribution": "알림 조건 재설계를 직접 수행",
            "team_result": "대응 절차가 팀 표준이 됨",
        })
        payload = self.confirmed_payload()
        self.assertEqual(payload["individual_contribution"], "알림 조건 재설계를 직접 수행")
        self.assertEqual(payload["team_result"], "대응 절차가 팀 표준이 됨")
        self.assertEqual(payload["direct_actions"], ["원인 로그 추적"])

    def test_a_review_can_happen_over_several_turns(self) -> None:
        self.review({"role": "운영 담당"})
        result = self.review({"learning": ["배치 실패는 조용히 지나간다"]})
        self.assertEqual(result["filled"], ["learning", "role"])

    def test_replace_can_clear_a_field_back_to_unknown(self) -> None:
        self.review({"role": "운영 담당", "team_result": "잘못 적은 값"})
        result = self.review({"role": "운영 담당"}, "--replace")
        self.assertEqual(result["filled"], ["role"])
        self.assertNotIn("team_result", result["work_event"])

    def test_a_confidentiality_patch_does_not_drop_the_flag(self) -> None:
        # The two keys answer different questions and are answered at different times: the material
        # is flagged at capture, and whether it may leave is decided after review. A shallow merge
        # would let the second turn quietly unflag a confidential record.
        self.review({"confidentiality": {"contains_confidential": True, "external_use": "unknown"}})
        result = self.review({"confidentiality": {"external_use": "blocked"}})
        self.assertEqual(
            result["work_event"]["confidentiality"],
            {"contains_confidential": True, "external_use": "blocked"},
        )
        self.assertEqual(
            self.confirmed_payload()["confidentiality"],
            {"contains_confidential": True, "external_use": "blocked"},
        )

    def test_replace_still_clears_confidentiality_outright(self) -> None:
        self.review({"confidentiality": {"contains_confidential": True, "external_use": "blocked"}})
        result = self.review({"role": "운영 담당"}, "--replace")
        self.assertNotIn("confidentiality", result["work_event"])

    def test_other_fields_still_replace_wholesale(self) -> None:
        # A corrected list means that list, not the old one with additions.
        self.review({"direct_actions": ["첫 번째", "잘못 적은 항목"]})
        result = self.review({"direct_actions": ["첫 번째"]})
        self.assertEqual(result["work_event"]["direct_actions"], ["첫 번째"])

    def test_an_unknown_field_is_refused(self) -> None:
        result = self.review({"metric": ["30% 감소"]})
        self.assertFalse(result.get("ok", False))
        self.assertIn("metric", result["error"])

    def test_the_merged_result_is_what_gets_validated(self) -> None:
        # A patch that is fine alone can still be invalid once combined, so the check runs on the
        # stored shape rather than on the incoming keys.
        self.review({"confidentiality": {"contains_confidential": False}})
        result = self.review({"confidentiality": {"contains_confidential": True}})
        self.assertFalse(result.get("ok", False))
        self.assertIn("external_use", result["error"])

    def test_a_metric_without_evidence_still_cannot_be_confirmed(self) -> None:
        self.review({"metrics": ["야간 장애 30% 감소"]})
        approved = self.cli("approve", self.proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        self.assertFalse(approved.get("ok", False))
        self.assertIn("numeric claim", approved["error"])

    def test_a_confirmed_event_is_not_editable(self) -> None:
        self.cli("approve", self.proposal, "--vault", self.vault, "--evidence", "JIRA-1")
        result = self.review({"role": "고쳐치기"})
        self.assertFalse(result.get("ok", False))
        self.assertEqual(result["error_code"], "PROPOSAL_NOT_PENDING")

    def test_a_routed_event_is_not_a_work_event(self) -> None:
        other = self.cli(
            "run", "--mode", "chat", "--vault", self.vault, "--message", "면접 준비 도와줘"
        )["proposal"]["id"]
        result = self.cli(
            "review-work-event", other, "--vault", self.vault, "--json", '{"role": "x"}',
        )
        self.assertFalse(result.get("ok", False))
        self.assertIn("not a work event", result["error"])

    def test_malformed_json_is_refused(self) -> None:
        result = self.cli(
            "review-work-event", self.proposal, "--vault", self.vault, "--json", "{not json",
        )
        self.assertFalse(result.get("ok", False))
        self.assertEqual(result["error_code"], "INVALID_INPUT")


if __name__ == "__main__":
    unittest.main()
