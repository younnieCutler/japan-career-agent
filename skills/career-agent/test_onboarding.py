#!/usr/bin/env python3
"""Progressive onboarding: track, graduation year, then the task the user actually wants.

Onboarding here is not profile completion. It is the shortest confirmed path to a real domain
workflow, so these tests assert what the runtime refuses to invent as much as what it routes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"


def run(vault: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        cwd=vault.parent,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class OnboardingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "career-vault"
        self.workdir = Path(self.tempdir.name) / "work"
        self.workdir.mkdir()
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @property
    def profile_path(self) -> Path:
        return self.vault / "00-control" / "career-profile.toml"

    def set_profile(self, **values: str | int) -> None:
        lines = [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()]
        self.profile_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def profile(self) -> dict:
        with self.profile_path.open("rb") as stream:
            return tomllib.load(stream)

    def career_status(self) -> str:
        return str(self.profile().get("career_status") or "")

    def chat(self, message: str, *args: str) -> dict:
        return output(run(self.vault, "run", "--mode", "chat", "--message", message, *args))

    def test_a_new_vault_starts_in_onboarding(self) -> None:
        self.assertEqual(self.career_status(), "onboarding")
        self.assertTrue(output(run(self.vault, "guided"))["guided"]["summary"]["onboarding"])

    # Scenario 1 -- fresh shinsotsu, graduation year stated in the message.
    def test_stated_graduation_year_is_read_back_but_never_written(self) -> None:
        before = self.profile_path.read_bytes()
        result = self.chat("27卒で就活を始めたい")
        self.assertEqual(result["track"], "shinsotsu")
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("2027", result["question"])
        self.assertIn("--graduation-year 2027", result["question"])
        # The user's own wording is not their approval. Only `setup` writes the year.
        self.assertEqual(self.profile_path.read_bytes(), before)
        self.assertFalse((self.vault / "02-state" / "proposals.jsonl").exists())

    # Scenario 2 -- fresh shinsotsu with no year anywhere.
    def test_missing_graduation_year_is_asked_for_without_inventing_one(self) -> None:
        result = self.chat("新卒で学チカを整理したい")
        self.assertEqual(result["track"], "shinsotsu")
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("卒業年", result["question"])
        self.assertNotIn("graduation_year", result["question"])
        self.assertNotRegex(result["question"], r"20\d{2}")
        self.assertNotIn("graduation_year", self.profile())

    # Scenario 3 + 12 -- chuto resolves the track and stops at the intent question. The chuto
    # alias is a track signal, so it must not count as a resolved intent.
    def test_chuto_track_alone_still_asks_for_the_current_intent(self) -> None:
        result = self.chat("일본에서 이직 준비를 시작하고 싶어")
        self.assertEqual(result["track"], "chuto")
        self.assertTrue(result["needs_confirmation"])
        self.assertNotIn("graduation_year", result["question"])
        self.assertIn("직무경력서", result["question"])
        self.assertNotIn("職務経歴書", result["question"])
        self.assertIsNone(result.get("proposal"))
        self.assertEqual(self.career_status(), "onboarding")

    # Scenario 4 -- "I don't know what to do" is a route, not a recommendation.
    def test_unknown_direction_routes_to_self_analysis_without_a_target_role(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        result = self.chat("무슨 직무를 해야 할지 모르겠어")
        self.assertEqual(result["stage"], "自己分析・転職軸")
        self.assertEqual(result["skill"]["skill"], "jiko-bunseki")
        self.assertNotIn("target_role", self.profile())

    # Scenario 5 -- a stated document task skips the onboarding question entirely.
    def test_resume_intent_routes_directly_to_job_seeker_agent(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        result = self.chat("職務経歴書を整理したい")
        self.assertEqual(result["stage"], "職務経歴書・自己PR")
        self.assertEqual(result["skill"]["skill"], "job-seeker-agent")
        self.assertNotIn("question", result)

    # Scenario 6 -- applying and reviewing a posting are different intents.
    def test_application_and_posting_review_route_to_different_skills(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        applying = self.chat("この求人に応募できるか見たい")
        self.assertEqual(applying["stage"], "応募・書類選考")
        self.assertEqual(applying["skill"]["skill"], "matching-simulator")

        self.set_profile(track="chuto", career_status="onboarding")
        reviewing = self.chat("このJDと私の経験を比較したい")
        self.assertEqual(reviewing["stage"], "職務経歴書・自己PR")
        self.assertEqual(reviewing["skill"]["skill"], "job-seeker-agent")

    # Scenario 7 -- a confirmed field is never asked for again.
    def test_confirmed_track_is_not_asked_again_during_onboarding(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        result = self.chat("面接の準備をしたい")
        self.assertEqual(result["track"], "chuto")
        self.assertEqual(result["stage"], "面接")
        self.assertNotIn("question", result)

    # Scenario 8 -- an existing workflow outranks a re-declared onboarding status.
    # Scenario 8 (chat-level scope only -- see the module docstring boundary note below).
    def test_existing_vault_state_keeps_priority_over_a_re_declared_onboarding_status(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        first = self.chat("転職の面接を準備したい")
        output(run(self.vault, "approve", first["proposal"]["id"], "--evidence", "転職の面接を準備したい"))
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="onboarding")

        result = self.chat("売上を30%改善した")
        self.assertNotIn("question", result)
        self.assertEqual(result["stage"], "面接")
        self.assertIsNotNone(result.get("proposal"))

    def test_chat_has_no_workspace_input_and_cannot_see_data_pipeline_yml(self) -> None:
        """Documents a real scope boundary, not a gap: `run --mode chat` takes no `--workspace`.

        The PRD's "an active pipeline company outranks onboarding" rule is enforced at session
        start (`_shared/agent_context/onboarding.md`'s CWD probe), before career-agent chat is ever
        invoked -- not inside this CLI. An active `data/pipeline.yml` company sitting right next to
        a fresh onboarding Vault has no effect on what chat does, because chat has nothing that
        would let it look.
        """
        self.set_profile(track="chuto", career_status="onboarding")
        pipeline = self.workdir / "data" / "pipeline.yml"
        pipeline.parent.mkdir(parents=True)
        pipeline.write_text(
            "companies:\n"
            "- name: Aozora Systems (Synthetic)\n"
            "  slug: aozora-systems-synthetic\n"
            "  stage: 4\n"
            "  closed: false\n"
            "  history: []\n"
            "updated: null\n",
            encoding="utf-8",
        )
        parser = run(self.vault, "run", "--help")
        self.assertNotIn("--workspace", parser.stdout)

        result = self.chat("売上を30%改善した")
        # No intent signal, no stage, career_status onboarding: the gate still fires. A workspace
        # sitting on disk changes nothing about this answer.
        self.assertTrue(result["needs_confirmation"])

    # Scenario 9 -- the question follows the latest message language; enums stay canonical.
    def test_intent_question_follows_the_latest_message_language(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        cases = (
            ("무엇부터 할까", "ko", "지금 가장 먼저"),
            ("何から始めればいい", "ja", "今いちばん先に"),
            ("Where should I start", "en", "What do you want to work on first"),
        )
        for message, language, marker in cases:
            with self.subTest(message=message):
                result = self.chat(message)
                self.assertEqual(result["language"], language)
                self.assertIn(marker, result["question"])
                self.assertEqual(result["track"], "chuto")

    # Scenario 10 -- a self-analysis hypothesis stays a hypothesis.
    def test_self_analysis_context_never_becomes_candidate_evidence(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        source = self.workdir / "self_analysis_profile.yml"
        source.write_text(
            "career_anchors:\n"
            "  primary: autonomy\n"
            "  secondary: [technical_competence]\n"
            "  will_not_give_up: '스스로 판단할 수 있는 환경'\n"
            "career_theme: '복잡한 문제를 구조화하고 직접 개선한다'\n"
            "energy_map:\n"
            "  energizes: ['새 문제 구조화']\n"
            "  drains: ['단순 반복 운영']\n"
            "  misfit_flag: null\n"
            "career_values:\n"
            "  must_have: ['전문성 축적']\n"
            "  avoid: ['단순 반복 운영']\n",
            encoding="utf-8",
        )
        proposed = output(run(self.vault, "propose-context", "--source", str(source)))
        output(run(self.vault, "approve", proposed["proposal"]["id"]))

        shared = output(run(self.vault, "context", "--track", "chuto"))
        self.assertTrue(shared["career_context_confirmed"])
        self.assertEqual(shared["career_context"]["career_values"]["must_have"], ["전문성 축적"])

        personal = output(run(self.vault, "personal-profile"))
        self.assertNotIn("전문성 축적", json.dumps(personal, ensure_ascii=False))
        # Confirming a hypothesis must not move the user through the market flow either.
        self.assertIsNone(shared["state"].get("stage"))

    # Scenario 11 -- `active` means "a workflow was chosen", not "a fact was confirmed".
    def test_onboarding_completes_on_routing_and_survives_an_unapproved_proposal(self) -> None:
        self.set_profile(track="chuto", career_status="onboarding")
        result = self.chat("職務経歴書を整理したい")
        self.assertTrue(result["onboarding_completed"])
        self.assertEqual(self.career_status(), "active")

        proposal = output(run(self.vault, "proposals"))["proposals"][0]
        self.assertEqual(proposal["status"], "pending")
        self.assertFalse((self.vault / "02-state" / "events.jsonl").exists())
        # A later turn must not flip anything back or repeat the transition.
        self.chat("面接の準備をしたい")
        self.assertEqual(self.career_status(), "active")

    def test_existing_active_profiles_keep_the_previous_behaviour(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        result = self.chat("売上を30%改善した")
        self.assertNotIn("question", result)
        self.assertEqual(result["stage"], "自己分析・転職軸")
        self.assertIsNone(result.get("onboarding_completed"))
        self.assertEqual(self.career_status(), "active")


class MaintenanceOnboardingTests(unittest.TestCase):
    """Career maintenance must not be gated behind a hiring-market question.

    Someone employed and not looking has no answer to "new graduate or mid-career?", and asking it
    before they can write down what they did at work is the friction this path removes.
    """

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "career-vault"
        (Path(self.tempdir.name) / "work").mkdir()
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    @property
    def profile_path(self) -> Path:
        return self.vault / "00-control" / "career-profile.toml"

    def set_profile(self, **values: str | int) -> None:
        lines = [f"{key} = {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()]
        self.profile_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def profile(self) -> dict:
        with self.profile_path.open("rb") as stream:
            return tomllib.load(stream)

    def career_status(self) -> str:
        return str(self.profile().get("career_status") or "")

    def chat(self, message: str, *args: str) -> dict:
        return output(run(self.vault, "run", "--mode", "chat", "--message", message, *args))

    def test_a_maintenance_request_routes_without_a_track(self) -> None:
        result = self.chat("오늘 한 일 기록해줘")
        self.assertIsNone(result.get("needs_confirmation"))
        self.assertIsNone(result["track"])
        self.assertIsNone(result["stage"])
        self.assertEqual(result["career_mode"], "maintenance")
        self.assertEqual(result["proposal"]["event"]["type"], "work_event")

    def test_maintenance_works_in_japanese_and_english_too(self) -> None:
        for message in ("今日やった仕事を記録して", "Add this to my work log"):
            with self.subTest(message=message):
                result = self.chat(message)
                self.assertIsNone(result.get("needs_confirmation"))
                self.assertIsNone(result["track"])

    def test_the_track_question_still_blocks_everything_else(self) -> None:
        result = self.chat("면접 준비 도와줘")
        self.assertTrue(result["needs_confirmation"])
        self.assertIn("신졸", result["question"])
        self.assertIn("경력채용", result["question"])
        self.assertNotIn("shinsotsu", result["question"])
        self.assertNotIn("chuto", result["question"])

        selected = self.chat("경력채용이에요")
        self.assertEqual(selected["track"], "chuto")

    def test_recording_evidence_ends_onboarding_without_choosing_a_track(self) -> None:
        self.chat("업무일지 남겨줘")
        self.assertEqual(self.career_status(), "active")
        self.assertIsNone(self.profile().get("track"))

    def test_the_track_is_asked_for_once_a_request_actually_needs_one(self) -> None:
        self.chat("업무일지 남겨줘")
        result = self.chat("면접 준비 도와줘")
        self.assertTrue(result["needs_confirmation"])

    def test_an_opportunity_review_counts_as_a_stated_intent(self) -> None:
        # The third gate asks "which task?" when no stage alias appears. A recruiter message names
        # a task as clearly as 면접 does; it just is not a stage.
        self.set_profile(career_status="onboarding", track="chuto")
        result = self.chat("헤드헌터가 보낸 건데 괜찮은 포지션인지만 봐줘")
        self.assertIsNone(result.get("needs_confirmation"))
        self.assertEqual(self.career_status(), "active")

    def test_a_vague_message_still_reaches_the_intent_question(self) -> None:
        self.set_profile(career_status="onboarding", track="chuto")
        result = self.chat("음")
        self.assertTrue(result["needs_confirmation"])


if __name__ == "__main__":
    unittest.main()
