"""Contract tests for the three career axes.

Career readiness and job-search intent are separate concepts, so they are separate fields with
separate owners. `employment_status` and `job_search` are the user's own declaration and have
exactly one write path each. `career_mode` is projected from events and may never escalate to
`active_search` on its own.
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


def run_cli(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(CLI), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode not in (0, 2):
        raise AssertionError(f"{args}\n{completed.stdout}\n{completed.stderr}")
    return json.loads(completed.stdout)


class ProfileAxisTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        run_cli("init", "--vault", self.vault)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def profile(self) -> dict:
        return career_agent.CareerVault(Path(self.vault)).load_profile()

    def test_a_new_vault_is_not_searching_and_declares_no_employment(self) -> None:
        self.assertEqual(career_agent.job_search_of(self.profile()), "off")
        self.assertEqual(career_agent.employment_status_of(self.profile()), "unknown")

    def test_a_missing_key_reads_as_off_never_on(self) -> None:
        self.assertEqual(career_agent.job_search_of({}), "off")
        self.assertEqual(career_agent.employment_status_of({}), "unknown")

    def test_an_unreadable_value_reads_as_the_safe_default(self) -> None:
        self.assertEqual(career_agent.job_search_of({"job_search": "yes"}), "off")
        self.assertEqual(career_agent.employment_status_of({"employment_status": 3}), "unknown")

    def test_employment_status_round_trips(self) -> None:
        result = run_cli("set-employment-status", "employed", "--vault", self.vault)
        self.assertEqual(result["employment_status"], "employed")
        self.assertEqual(result["previous"], "unknown")
        self.assertTrue(result["changed"])
        self.assertEqual(career_agent.employment_status_of(self.profile()), "employed")

    def test_employment_status_moves_when_the_job_ends(self) -> None:
        run_cli("set-employment-status", "employed", "--vault", self.vault)
        run_cli("set-employment-status", "unemployed", "--vault", self.vault)
        self.assertEqual(career_agent.employment_status_of(self.profile()), "unemployed")

    def test_job_search_round_trips_both_ways(self) -> None:
        run_cli("set-job-search", "on", "--vault", self.vault)
        self.assertEqual(career_agent.job_search_of(self.profile()), "on")
        run_cli("set-job-search", "off", "--vault", self.vault)
        self.assertEqual(career_agent.job_search_of(self.profile()), "off")

    def test_a_hand_edited_value_is_reported_not_silently_ignored(self) -> None:
        home = career_agent.CareerVault(Path(self.vault))
        profile = home.load_profile()
        profile["job_search"] = "maybe"
        career_agent.write_toml(home.profile, profile)
        diagnosis = run_cli("doctor", "--vault", self.vault)
        self.assertTrue(any("profile.job_search" in error for error in diagnosis["errors"]))


class CareerModeProjectionTests(unittest.TestCase):
    """`next_career_mode` is the whole escalation rule, so it is tested directly."""

    def test_a_work_event_is_always_maintenance(self) -> None:
        work = {"type": career_agent.WORK_EVENT_TYPE, "stage": None}
        self.assertEqual(career_agent.next_career_mode(work, "off"), "maintenance")
        self.assertEqual(career_agent.next_career_mode(work, "on"), "maintenance")

    def test_reviewing_an_opportunity_with_search_off_stays_opportunity_review(self) -> None:
        event = {"type": "event", "stage": "業界研究・企業研究"}
        self.assertEqual(career_agent.next_career_mode(event, "off"), "opportunity_review")

    def test_repeated_document_work_with_search_off_never_becomes_active_search(self) -> None:
        for stage in ("職務経歴書・自己PR", "応募・書類選考", "面接"):
            with self.subTest(stage=stage):
                event = {"type": "event", "stage": stage}
                self.assertEqual(career_agent.next_career_mode(event, "off"), "opportunity_review")

    def test_active_search_requires_the_declared_intent(self) -> None:
        event = {"type": "event", "stage": "応募・書類選考"}
        self.assertEqual(career_agent.next_career_mode(event, "on"), "active_search")

    def test_a_decided_move_is_a_transition_regardless_of_the_flag(self) -> None:
        for stage in ("内定・条件交渉", "退職・入社準備", "内々定・内定・入社準備"):
            with self.subTest(stage=stage):
                event = {"type": "event", "stage": stage}
                self.assertEqual(career_agent.next_career_mode(event, "off"), "transition")
                self.assertEqual(career_agent.next_career_mode(event, "on"), "transition")


class ProjectorTests(unittest.TestCase):
    def base_state(self) -> dict:
        return career_agent.default_state()

    def test_a_new_state_rests_in_maintenance(self) -> None:
        self.assertEqual(self.base_state()["career_mode"], "maintenance")

    def test_a_work_event_moves_no_route(self) -> None:
        state = dict(self.base_state(), track="chuto", stage="面接", flow_phase="interview")
        event = {
            "id": "evt-1",
            "type": career_agent.WORK_EVENT_TYPE,
            "track": None,
            "stage": None,
            "flow_phase": None,
        }
        projected = career_agent.apply_event_to_state(state, event, job_search="on")
        self.assertEqual(projected["track"], "chuto")
        self.assertEqual(projected["stage"], "面接")
        self.assertEqual(projected["flow_phase"], "interview")
        self.assertEqual(projected["last_event_id"], "evt-1")
        self.assertEqual(projected["career_mode"], "maintenance")

    def test_the_projector_defaults_to_not_searching(self) -> None:
        event = {
            "id": "evt-2",
            "type": "event",
            "track": "chuto",
            "stage": "応募・書類選考",
            "flow_phase": "application",
        }
        projected = career_agent.apply_event_to_state(self.base_state(), event)
        self.assertEqual(projected["career_mode"], "opportunity_review")


class IntentIsUserOwnedTests(unittest.TestCase):
    """The central invariant: career data may be read into a decision, never write the intent.

    A recruiter message, a JD review, a routed chat turn, and an approved event all pass through
    the runtime. None of them may turn job search on. `set-job-search` is the only thing that can.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        self.workdir = Path(self._tmp.name) / "work"
        self.workdir.mkdir()
        run_cli("setup", "--vault", self.vault, "--track", "chuto")
        run_cli("set-employment-status", "employed", "--vault", self.vault)
        self.home = career_agent.CareerVault(Path(self.vault))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def chat(self, message: str) -> dict:
        return run_cli("run", "--mode", "chat", "--vault", self.vault, "--message", message)

    def test_reviewing_a_recruiter_posting_does_not_turn_search_on(self) -> None:
        for message in (
            "헤드헌터가 보낸 JD 평가해줘",
            "この求人を見てほしい",
            "just review this job description for me",
            "시장 연봉만 보고 싶어",
        ):
            with self.subTest(message=message):
                self.chat(message)
                self.assertEqual(career_agent.job_search_of(self.home.load_profile()), "off")

    def test_approving_an_event_does_not_turn_search_on(self) -> None:
        proposed = self.chat("この求人を見てほしい")
        run_cli(
            "approve",
            proposed["proposal"]["id"],
            "--vault",
            self.vault,
            "--evidence",
            "https://example.invalid/posting",
        )
        profile = self.home.load_profile()
        self.assertEqual(career_agent.job_search_of(profile), "off")
        self.assertEqual(career_agent.employment_status_of(profile), "employed")

    def test_an_approved_event_lands_in_opportunity_review_not_active_search(self) -> None:
        proposed = self.chat("この求人に応募できるか見てほしい")
        run_cli(
            "approve",
            proposed["proposal"]["id"],
            "--vault",
            self.vault,
            "--evidence",
            "https://example.invalid/posting",
        )
        self.assertEqual(self.home.load_state()["career_mode"], "opportunity_review")

    def test_the_same_event_reaches_active_search_once_the_user_declares_it(self) -> None:
        run_cli("set-job-search", "on", "--vault", self.vault)
        proposed = self.chat("この求人に応募できるか見てほしい")
        run_cli(
            "approve",
            proposed["proposal"]["id"],
            "--vault",
            self.vault,
            "--evidence",
            "https://example.invalid/posting",
        )
        self.assertEqual(self.home.load_state()["career_mode"], "active_search")

    def test_turning_search_off_preserves_the_event_history(self) -> None:
        run_cli("set-job-search", "on", "--vault", self.vault)
        proposed = self.chat("この求人に応募できるか見てほしい")
        run_cli(
            "approve",
            proposed["proposal"]["id"],
            "--vault",
            self.vault,
            "--evidence",
            "https://example.invalid/posting",
        )
        events = Path(self.vault, "02-state", "events.jsonl").read_bytes()
        run_cli("set-job-search", "off", "--vault", self.vault)
        self.assertEqual(Path(self.vault, "02-state", "events.jsonl").read_bytes(), events)
        self.assertEqual(self.home.load_state()["career_mode"], "opportunity_review")


class WorkEventLeavesTheRouteAloneTests(unittest.TestCase):
    """Recording work must not move where the user is in a hiring flow, or create a company."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        self.workdir = Path(self._tmp.name) / "work"
        self.workdir.mkdir()
        run_cli("setup", "--vault", self.vault, "--track", "chuto")
        self.home = career_agent.CareerVault(Path(self.vault))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def capture_and_approve(self) -> None:
        proposed = run_cli(
            "run", "--mode", "chat", "--vault", self.vault, "--message", "업무일지 남겨줘"
        )
        run_cli(
            "approve",
            proposed["proposal"]["id"],
            "--vault",
            self.vault,
            "--evidence",
            "JIRA-123",
        )

    def test_the_routed_state_is_untouched(self) -> None:
        run_cli("run", "--mode", "chat", "--vault", self.vault, "--message", "면접 준비 도와줘")
        before = self.home.load_state()
        self.capture_and_approve()
        after = self.home.load_state()
        self.assertEqual(after["track"], before["track"])
        self.assertEqual(after["stage"], before["stage"])
        self.assertEqual(after["flow_phase"], before["flow_phase"])
        self.assertEqual(after["career_mode"], "maintenance")

    def test_no_company_is_projected_into_the_pipeline(self) -> None:
        self.capture_and_approve()
        self.assertFalse((self.workdir / "data" / "pipeline.yml").exists())

    def test_the_confirmed_work_event_reaches_the_ledger(self) -> None:
        self.capture_and_approve()
        rows = [
            json.loads(line)
            for line in Path(self.vault, "02-state", "events.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], career_agent.WORK_EVENT_TYPE)
        self.assertEqual(rows[0]["status"], "confirmed")
        self.assertIsNone(rows[0]["track"])


class ClampTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = str(Path(self._tmp.name) / "vault")
        run_cli("init", "--vault", self.vault)
        self.home = career_agent.CareerVault(Path(self.vault))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_turning_search_off_steps_active_search_down_to_opportunity_review(self) -> None:
        self.home.save_state(dict(career_agent.default_state(), career_mode="active_search"))
        result = run_cli("set-job-search", "off", "--vault", self.vault)
        self.assertEqual(result["career_mode"], "opportunity_review")
        self.assertEqual(self.home.load_state()["career_mode"], "opportunity_review")

    def test_the_clamp_does_not_reach_past_active_search(self) -> None:
        for mode in ("maintenance", "opportunity_review", "transition"):
            with self.subTest(mode=mode):
                state = dict(career_agent.default_state(), career_mode=mode)
                self.assertEqual(career_agent.clamp_career_mode(state, "off")["career_mode"], mode)

    def test_turning_search_on_does_not_move_the_mode_by_itself(self) -> None:
        self.home.save_state(dict(career_agent.default_state(), career_mode="maintenance"))
        run_cli("set-job-search", "on", "--vault", self.vault)
        self.assertEqual(self.home.load_state()["career_mode"], "maintenance")

    def test_doctor_reports_a_mode_that_outran_the_declared_intent(self) -> None:
        self.home.save_state(dict(career_agent.default_state(), career_mode="active_search"))
        diagnosis = run_cli("doctor", "--vault", self.vault)
        self.assertTrue(any("active_search" in error for error in diagnosis["errors"]))


if __name__ == "__main__":
    unittest.main()
