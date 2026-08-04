import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"


def run(vault: Path, command: str, *args: str, input_text: str | None = None,
        cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # cwd matters: approve projects company events onto CWD-relative data/pipeline.yml.
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        input=input_text,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(cwd) if cwd else None,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class CareerAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "career-vault"
        self.workdir = Path(self.tempdir.name) / "work"
        self.workdir.mkdir()
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def set_profile(self, **values: str | int) -> None:
        lines = [f'{key} = {json.dumps(value, ensure_ascii=False)}' for key, value in values.items()]
        (self.vault / "00-control" / "career-profile.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def test_init_creates_vault_contract_and_missing_vault_safe_stops(self) -> None:
        for directory in ("00-control", "01-capture", "02-state", "03-active", "04-evidence", "05-playbooks", "06-reference", "07-archive"):
            self.assertTrue((self.vault / directory).is_dir())
        self.assertTrue((self.vault / "00-control" / "career-profile.toml").exists())
        self.assertTrue((self.vault / "02-state" / "career-state.toml").exists())

        # CAREER_VAULT is exported in a real user's shell, and a subprocess inherits it.
        # Scrub it, or this asserts the opposite of what it means to on a working machine.
        env = {k: v for k, v in os.environ.items() if k != "CAREER_VAULT"}
        failed = subprocess.run([sys.executable, str(SCRIPT), "status"], text=True, encoding="utf-8", capture_output=True, check=False, env=env)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("CAREER_VAULT is required", failed.stderr)

    def test_setup_initializes_vault_fills_profile_and_runs_doctor(self) -> None:
        fresh_vault = self.vault.parent / "setup-vault"
        result = output(run(fresh_vault, "setup", "--track", "chuto",
                             "--target-role", "LLMOps Engineer"))
        self.assertTrue(result["created"])
        self.assertEqual(result["profile"]["track"], "chuto")
        self.assertEqual(result["profile"]["target_role"], "LLMOps Engineer")
        self.assertTrue(result["doctor"]["ok"], result["doctor"])
        self.assertEqual(result["next"], "run --mode chat")

        # Re-running setup on the same vault must not wipe what's already there.
        again = output(run(fresh_vault, "setup", "--graduation-year", "2027"))
        self.assertFalse(again["created"])
        self.assertEqual(again["profile"]["track"], "chuto")
        self.assertEqual(again["profile"]["graduation_year"], 2027)

    def test_setup_without_track_is_incomplete_and_actionable(self) -> None:
        fresh_vault = self.vault.parent / "missing-track-vault"
        result = run(fresh_vault, "setup")
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["needs_input"], ["track"])
        self.assertIn("--track <shinsotsu|chuto>", payload["next"])
        self.assertTrue((fresh_vault / "00-control" / "career-profile.toml").exists())

    def test_setup_shinsotsu_without_graduation_year_is_actionable(self) -> None:
        fresh_vault = self.vault.parent / "missing-graduation-year-vault"
        result = run(fresh_vault, "setup", "--track", "shinsotsu")
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["needs_input"], ["graduation_year"])
        self.assertIn("--track shinsotsu --graduation-year <YYYY>", payload["next"])

    def test_fresh_onboarding_quickstart_e2e(self) -> None:
        """The README setup → proposal → approval → projection path works in one fresh workspace."""
        fresh_vault = self.vault.parent / "quickstart-vault"
        fresh_workspace = self.vault.parent / "quickstart-workspace"
        fresh_workspace.mkdir()

        setup = run(fresh_vault, "setup", "--track", "chuto", "--target-role", "Platform Engineer")
        self.assertEqual(setup.returncode, 0, setup.stderr)
        setup_payload = json.loads(setup.stdout)
        self.assertTrue(setup_payload["ok"])
        self.assertEqual(setup_payload["next"], "run --mode chat")

        message = "転職の面接を準備したい"
        proposed = run(fresh_vault, "run", "--mode", "chat", "--message", message)
        self.assertEqual(proposed.returncode, 0, proposed.stderr)
        proposed_payload = json.loads(proposed.stdout)
        proposal_id = proposed_payload["proposal"]["id"]

        listed = run(fresh_vault, "proposals")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        listing = json.loads(listed.stdout)
        self.assertEqual(listing["count"], 1)
        self.assertEqual(listing["proposals"][0]["id"], proposal_id)

        company = "Aozora Systems (Synthetic)"
        approved = run(
            fresh_vault,
            "approve",
            proposal_id,
            "--evidence",
            message,
            "--company",
            company,
            "--workspace",
            str(fresh_workspace),
            cwd=fresh_workspace,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        approved_payload = json.loads(approved.stdout)
        self.assertEqual(approved_payload["event"]["status"], "confirmed")
        self.assertEqual(approved_payload["event"]["company"], company)

        status = run(fresh_vault, "status")
        self.assertEqual(status.returncode, 0, status.stderr)
        status_payload = json.loads(status.stdout)
        self.assertEqual(status_payload["event_count"], 1)
        self.assertEqual(status_payload["pending_proposals"], 0)

        import yaml

        pipeline_path = fresh_workspace / "data" / "pipeline.yml"
        self.assertTrue(pipeline_path.is_file())
        pipeline = yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}
        self.assertEqual(pipeline["companies"][0]["name"], company)
        self.assertEqual(pipeline["companies"][0]["stage"], 4)  # 面接 → market stage 4

    def test_proposals_lists_metadata_only_and_filters_status(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        first = output(run(self.vault, "run", "--mode", "chat", "--message", "転職の面接を準備したい"))
        second = output(run(self.vault, "run", "--mode", "chat", "--message", "職務経歴書を直したい"))
        proposals_path = self.vault / "02-state" / "proposals.jsonl"

        pending = output(run(self.vault, "proposals"))
        self.assertEqual(pending["count"], 2)
        self.assertEqual({item["id"] for item in pending["proposals"]}, {first["proposal"]["id"], second["proposal"]["id"]})
        self.assertTrue(all(set(item) == {"id", "kind", "status", "created_at", "title", "stage", "company"}
                            for item in pending["proposals"]))
        self.assertNotIn("summary", json.dumps(pending, ensure_ascii=False))

        output(run(self.vault, "approve", first["proposal"]["id"], "--evidence", "転職の面接を準備したい"))
        after_approval = proposals_path.read_bytes()
        filtered = output(run(self.vault, "proposals"))
        self.assertEqual(filtered["count"], 1)
        self.assertEqual(filtered["proposals"][0]["id"], second["proposal"]["id"])
        all_rows = output(run(self.vault, "proposals", "--all", "--limit", "1"))
        self.assertEqual(all_rows["count"], 1)
        self.assertEqual(all_rows["proposals"][0]["id"], second["proposal"]["id"])
        self.assertEqual(proposals_path.read_bytes(), after_approval)

    def test_setup_defaults_to_home_vault_when_no_vault_given(self) -> None:
        # CAREER_VAULT is exported in a real user's shell and would leak in; scrub it, and
        # HOME too so this can't ever touch the real ~/.career-agent-vault on a dev machine.
        env = {k: v for k, v in os.environ.items() if k != "CAREER_VAULT"}
        env["HOME"] = self.tempdir.name
        env["USERPROFILE"] = self.tempdir.name  # Path.home() reads this on Windows, not HOME
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "setup"],
            text=True, encoding="utf-8", capture_output=True, check=False, env=env,
        )
        payload = json.loads(result.stdout)
        expected = (Path(self.tempdir.name) / ".career-agent-vault").resolve()
        self.assertEqual(payload["vault"], str(expected))

    def test_shinsotsu_requires_graduation_year_then_proposes_event(self) -> None:
        missing = output(run(self.vault, "run", "--mode", "chat", "--track", "shinsotsu", "--message", "신졸이고 가쿠치카 경험을 정리하고 싶어요"))
        self.assertTrue(missing["needs_confirmation"])
        self.assertIn("graduation_year", missing["question"])
        self.assertFalse((self.vault / "02-state" / "proposals.jsonl").exists())

        self.set_profile(track="shinsotsu", graduation_year=2027, target_role="LLMOps Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "신졸이고 가쿠치카 경험을 정리하고 싶어요"))
        self.assertEqual(proposed["track"], "shinsotsu")
        self.assertEqual(proposed["stage"], "学チカ・自己PR素材")
        self.assertEqual(proposed["flow_phase"], "preparation")
        self.assertEqual(proposed["language"], "ko")
        self.assertEqual(proposed["skill"]["references"], ["references/shinsotsu.md"])

    def test_chuto_japanese_request_routes_to_chuto_and_approval_persists(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "転職の面接を準備したい"))
        self.assertEqual(proposed["track"], "chuto")
        self.assertEqual(proposed["stage"], "面接")
        self.assertEqual(proposed["flow_phase"], "interview")
        self.assertEqual(proposed["language"], "ja")
        proposal_id = proposed["proposal"]["id"]

        failed = run(self.vault, "approve", proposal_id)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("require evidence", failed.stderr)
        self.assertIn(f"Retry with: approve {proposal_id} --evidence", failed.stderr)
        self.assertIn("Unsupported claims remain drafts.", failed.stderr)
        approved = output(run(self.vault, "approve", proposal_id, "--evidence", "転職の面接を準備したい"))
        self.assertEqual(approved["event"]["status"], "confirmed")
        self.assertTrue((self.vault / "02-state" / "events.jsonl").exists())
        self.assertTrue((self.vault / "02-state" / "career-state.toml").exists())

    def test_numeric_claim_without_evidence_is_rejected(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "売上を30%改善した"))
        failed = run(self.vault, "approve", proposed["proposal"]["id"])
        self.assertEqual(failed.returncode, 2)
        self.assertIn("numeric claim", failed.stderr)
        error = json.loads(failed.stderr)["error"]
        self.assertIn(
            f'Retry with: approve {proposed["proposal"]["id"]} --evidence "<source or confirmation containing the exact numeric claim>"',
            error,
        )

    def test_numeric_claim_with_unrelated_evidence_is_still_rejected(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "売上を30%改善した"))
        failed = run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "面接の準備をした")
        self.assertEqual(failed.returncode, 2)
        self.assertIn("numeric claim", failed.stderr)
        error = json.loads(failed.stderr)["error"]
        self.assertIn("--evidence \"<source or confirmation containing the exact numeric claim>\"", error)

    def test_every_agent_stage_maps_to_a_market_stage(self) -> None:
        sys.path.insert(0, str(SCRIPT.parent))
        import career_agent

        for stage in career_agent.SHINSOTSU_STAGES + career_agent.CHUTO_STAGES:
            self.assertIn(stage, career_agent.PIPELINE_STAGE, stage)

    def pipeline_companies(self) -> list[dict]:
        import yaml

        path = self.workdir / "data" / "pipeline.yml"
        self.assertTrue(path.is_file(), f"pipeline not written: {path}")
        return (yaml.safe_load(path.read_text(encoding="utf-8")) or {})["companies"]

    def test_approve_with_company_projects_onto_pipeline(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらった"))
        approved = output(run(
            self.vault, "approve", proposed["proposal"]["id"],
            "--evidence", "内定をもらった",
            "--company", "GAO",
            "--compensation", "5130000",
            "--currency", "JPY",
            cwd=self.workdir,
        ))
        self.assertEqual(approved["event"]["company"], "GAO")
        self.assertEqual(approved["event"]["compensation"], 5130000)
        self.assertEqual(approved["event"]["currency"], "JPY")
        # Per-company progress is projected onto data/pipeline.yml, not duplicated into vault state.
        self.assertNotIn("applications", output(run(self.vault, "status"))["state"])
        companies = self.pipeline_companies()
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["slug"], "gao")
        self.assertEqual(companies[0]["name"], "GAO")
        self.assertEqual(companies[0]["stage"], 5)  # 内定・条件交渉 → market stage 5
        self.assertEqual(len(companies[0]["history"]), 1)

    def test_pipeline_stage_never_rewinds_and_preserves_foreign_fields(self) -> None:
        import yaml

        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        offer = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらった"))
        output(run(self.vault, "approve", offer["proposal"]["id"], "--evidence", "内定をもらった",
                   "--company", "GAO", cwd=self.workdir))
        # A domain skill owns these fields; the runtime must not clobber them.
        path = self.workdir / "data" / "pipeline.yml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["companies"][0]["match_score"] = 72
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

        earlier = output(run(self.vault, "run", "--mode", "chat", "--message", "職務経歴書を直したい"))
        output(run(self.vault, "approve", earlier["proposal"]["id"], "--evidence", "職務経歴書を直したい",
                   "--company", "GAO", cwd=self.workdir))
        companies = self.pipeline_companies()
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0]["stage"], 5)
        self.assertEqual(companies[0]["match_score"], 72)
        self.assertEqual(len(companies[0]["history"]), 2)

    def test_heartbeat_is_capped_and_discover_deduplicates(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接の締切を確認したい"))
        output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "面接の締切を確認したい", "--deadline", "2099-01-01"))
        heartbeat = output(run(self.vault, "run", "--mode", "heartbeat"))
        self.assertLessEqual(len(heartbeat["actions"]), 3)
        self.assertIn("estimated_minutes", heartbeat["actions"][0])
        self.assertIn("flow_phase", heartbeat["actions"][0])
        postings = json.dumps([
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
        ], ensure_ascii=False)
        first = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        second = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        self.assertEqual(first["added"], 1)
        self.assertEqual(first["duplicates"], 1)
        self.assertEqual(second["duplicates"], 2)
        self.assertFalse(second["auto_apply"])

    def test_context_selector_excludes_capture_and_archive_bodies(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        trusted = self.vault / "05-playbooks" / "interview.md"
        trusted.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2026-08-01\n---\n\n# Interview\n\nUseful private body.\n",
            encoding="utf-8",
        )
        capture = self.vault / "01-capture" / "raw.md"
        capture.write_text("---\nagent_read: true\n---\nRaw VTT must stay out.", encoding="utf-8")
        archive = self.vault / "07-archive" / "old.md"
        archive.write_text("---\nagent_read: true\n---\nOld personal example.", encoding="utf-8")
        legacy = self.vault / "03-projects" / "old.md"
        legacy.parent.mkdir()
        legacy.write_text("---\nagent_read: true\n---\nLegacy PARA material.", encoding="utf-8")

        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接を準備したい"))
        self.assertEqual([item["path"] for item in proposed["context"]], ["05-playbooks/interview.md"])
        self.assertNotIn("Useful private body", json.dumps(proposed, ensure_ascii=False))
        indexed = output(run(self.vault, "index"))
        self.assertEqual(indexed["indexed"], 1)

        shared = output(run(self.vault, "context", "--stage", "面接"))
        self.assertTrue(shared["read_only"])
        self.assertFalse(shared["note_bodies_included"])
        self.assertEqual(shared["profile"]["target_role"], "Platform Engineer")
        self.assertEqual([item["path"] for item in shared["context"]], ["05-playbooks/interview.md"])

    def test_career_context_requires_approval_and_projects_latest_value(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        source = self.workdir / "data" / "self_analysis_profile.yml"
        source.parent.mkdir(parents=True)
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
        proposal_id = proposed["proposal"]["id"]
        pending = output(run(self.vault, "context", "--track", "chuto"))
        self.assertFalse(pending["career_context_confirmed"])
        self.assertIsNone(pending["career_context"])

        duplicate = output(run(self.vault, "propose-context", "--source", str(source)))
        self.assertTrue(duplicate["deduplicated"])
        self.assertEqual(duplicate["proposal"]["id"], proposal_id)

        approved = output(run(self.vault, "approve", proposal_id))
        self.assertEqual(approved["event"]["type"], "career_context")
        shared = output(run(self.vault, "context", "--track", "chuto"))
        self.assertTrue(shared["career_context_confirmed"])
        self.assertEqual(shared["career_context"]["career_values"]["must_have"], ["전문성 축적"])
        self.assertIsNone(shared["state"].get("stage"))

        source.write_text(source.read_text(encoding="utf-8").replace("전문성 축적", "기술 전문성 축적"), encoding="utf-8")
        changed = output(run(self.vault, "propose-context", "--source", str(source)))
        output(run(self.vault, "approve", changed["proposal"]["id"]))
        latest = output(run(self.vault, "context", "--track", "chuto"))
        self.assertEqual(latest["career_context"]["career_values"]["must_have"], ["기술 전문성 축적"])

    def test_career_context_rejects_invalid_shape_without_proposal(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        source = self.workdir / "invalid.yml"
        source.write_text("career_values:\n  must_have: not-a-list\n  avoid: []\n", encoding="utf-8")
        result = run(self.vault, "propose-context", "--source", str(source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("career_values requires", result.stderr)
        self.assertFalse((self.vault / "02-state" / "proposals.jsonl").exists())

    def test_career_context_rejects_raw_checklist_submission(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        source = self.workdir / "raw-checklist.yml"
        source.write_text(
            "jiko_bunseki_submission: true\n"
            "submission_version: 2\n"
            "name: Test User\n"
            "language: ko\n"
            "track: chuto\n"
            "behavior_tendencies: {analysis: 5}\n",
            encoding="utf-8",
        )
        result = run(self.vault, "propose-context", "--source", str(source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("raw checklist submission", result.stderr)
        self.assertFalse((self.vault / "02-state" / "proposals.jsonl").exists())

    def test_doctor_reports_profile_and_expired_reference_problems(self) -> None:
        incomplete = output(run(self.vault, "doctor"))
        self.assertTrue(incomplete["ok"])
        self.assertTrue(any("profile.track" in warning for warning in incomplete["warnings"]))
        self.set_profile(track="shinsotsu", graduation_year=2027, target_role="LLMOps Engineer", career_status="invalid")
        invalid = output(run(self.vault, "doctor"))
        self.assertFalse(invalid["ok"])
        self.assertTrue(any("career_status" in error for error in invalid["errors"]))

    def test_doctor_warns_on_legacy_nested_pipeline_shape(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        pipeline_path = self.workdir / "data" / "pipeline.yml"
        pipeline_path.parent.mkdir(parents=True, exist_ok=True)
        pipeline_path.write_text(
            "pipeline:\n  companies:\n  - slug: gao\n    name: GAO\n  updated: '2026-08-02'\n",
            encoding="utf-8",
        )
        result = output(run(self.vault, "doctor", cwd=self.workdir))
        self.assertTrue(any("legacy nested" in warning for warning in result["warnings"]), result)

    def test_doctor_fix_migrates_and_merges_legacy_pipeline_shape(self) -> None:
        import yaml

        pipeline_path = self.workdir / "data" / "pipeline.yml"
        pipeline_path.parent.mkdir(parents=True, exist_ok=True)
        pipeline_path.write_text(yaml.safe_dump({
            "pipeline": {
                "updated": "2026-07-31",
                "companies": [{"slug": "gao", "name": "GAO", "history": [{"date": "2026-07-31", "event": "old"}]}],
            },
            "updated": "2026-08-01",
            "companies": [{"slug": "gao", "match_score": 78}, {"slug": "other", "name": "Other"}],
        }, allow_unicode=True, sort_keys=False), encoding="utf-8")

        before = output(run(self.vault, "doctor", cwd=self.workdir))
        self.assertTrue(any("legacy nested" in warning for warning in before["warnings"]), before)
        fixed = output(run(self.vault, "doctor", "--fix", cwd=self.workdir))
        self.assertEqual(len(fixed["migrations"]), 1, fixed)
        data = yaml.safe_load(pipeline_path.read_text(encoding="utf-8"))
        self.assertNotIn("pipeline", data)
        self.assertEqual(data["updated"], "2026-08-01")
        self.assertEqual({company["slug"] for company in data["companies"]}, {"gao", "other"})
        gao = next(company for company in data["companies"] if company["slug"] == "gao")
        self.assertEqual(gao["match_score"], 78)
        self.assertEqual(len(gao["history"]), 1)

    def test_invalid_tool_input_safe_stops_and_restore_state_recovers_snapshot(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        failed = run(self.vault, "run", "--mode", "discover", input_text=json.dumps({"company": "missing url"}))
        self.assertEqual(failed.returncode, 2)
        error = json.loads(failed.stderr)
        self.assertTrue(error["safe_stop"])
        self.assertFalse(error["external_side_effect"])

        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途の面接を準備する"))
        approved = output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "中途の面接を準備する"))
        state_path = self.vault / "02-state" / "career-state.toml"
        state_path.write_text(state_path.read_text(encoding="utf-8").replace('stage = "面接"', 'stage = "退職・入社準備"'), encoding="utf-8")
        self.assertEqual(output(run(self.vault, "status"))["state"]["stage"], "退職・入社準備")
        restored = output(run(self.vault, "restore-state", approved["version"]))
        self.assertTrue(restored["restored"])
        self.assertEqual(restored["state"]["last_event_id"], approved["event"]["id"])

    def test_restore_state_keeps_the_ledger_and_says_so(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        first = output(run(self.vault, "run", "--mode", "chat", "--message", "職務経歴書を直したい"))
        early = output(run(self.vault, "approve", first["proposal"]["id"], "--evidence", "職務経歴書を直したい"))
        second = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらった"))
        output(run(self.vault, "approve", second["proposal"]["id"], "--evidence", "内定をもらった"))

        restored = output(run(self.vault, "restore-state", early["version"]))
        self.assertTrue(restored["ledger_retained"])
        self.assertEqual(restored["state"]["stage"], "職務経歴書・自己PR")
        # The later event is still in the ledger and still drives heartbeat. This is the documented
        # limitation of restore-state; if it ever stops being true, the docstring is wrong.
        status_after = output(run(self.vault, "status"))
        self.assertEqual(status_after["event_count"], 2)
        actions = output(run(self.vault, "run", "--mode", "heartbeat"))["actions"]
        self.assertEqual(actions[0]["stage"], "内定・条件交渉")

    def test_japanese_exit_keywords_route_to_exit_stage(self) -> None:
        # STAGE_ALIASES had 퇴직/입사 (Korean) but not 退職/入社 (Japanese), so a Japanese
        # resignation message fell through to the self-analysis default instead of the exit stage.
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "退職届を提出した。円満退職したい。"))
        self.assertEqual(proposed["stage"], "退職・入社準備")
        self.assertEqual(proposed["flow_phase"], "exit_onboarding")

        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "入社日が決まった"))
        self.assertEqual(proposed["stage"], "退職・入社準備")

    def test_english_research_message_routes_to_research_stage(self) -> None:
        # "es" (meant to catch the ES/entry-sheet abbreviation) must not match as a bare substring
        # inside "research"; the English research alias then routes to company research.
        sys.path.insert(0, str(SCRIPT.parent))
        import career_agent

        stage = career_agent.stage_for("I want to research companies", "chuto")
        self.assertEqual(stage, "業界研究・企業研究")

    def test_flow_phase_does_not_stick_after_a_confirmed_event(self) -> None:
        # flow_phase_for() used to check state.flow_phase before the message, so once any event
        # was confirmed, every later message returned that same phase forever — a real resignation
        # message arriving after an offer was confirmed never moved flow_phase off "offer".
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        offer = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらった"))
        self.assertEqual(offer["flow_phase"], "offer")
        output(run(self.vault, "approve", offer["proposal"]["id"], "--evidence", "内定をもらった"))

        resignation = output(run(self.vault, "run", "--mode", "chat", "--message", "退職届を提出した"))
        self.assertEqual(resignation["flow_phase"], "exit_onboarding")

    def test_approve_failure_logs_trajectory(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "売上を30%改善した"))
        failed = run(self.vault, "approve", proposed["proposal"]["id"])
        self.assertEqual(failed.returncode, 2)

        trajectories = read_jsonl(self.vault / "02-state" / "trajectories.jsonl")
        last = trajectories[-1]
        self.assertEqual(last["mode"], "approve")
        self.assertFalse(last["verify"]["passed"])
        self.assertTrue(last["correct"]["escalated_to_user"])

    def test_discover_drops_invalid_postings_but_keeps_the_rest(self) -> None:
        postings = json.dumps([
            {"company": "A", "role": "Data", "url": "https://example.com/a"},
            {"company": "B", "role": "Data"},
        ], ensure_ascii=False)
        result = output(run(self.vault, "run", "--mode", "discover", input_text=postings))
        self.assertEqual(result["added"], 1)
        self.assertEqual(result["dropped"], 1)

        trajectories = read_jsonl(self.vault / "02-state" / "trajectories.jsonl")
        last = trajectories[-1]
        self.assertEqual(last["correct"]["action"], "dropped_invalid_postings")
        self.assertEqual(last["correct"]["dropped"], 1)

    def test_chat_repeated_missing_info_flags_retry(self) -> None:
        self.set_profile(track="shinsotsu", target_role="LLMOps Engineer", career_status="active")
        message = "신졸이고 가쿠치카 경험을 정리하고 싶어요"
        first = output(run(self.vault, "run", "--mode", "chat", "--message", message))
        output(run(self.vault, "run", "--mode", "chat", "--message", message))
        third = output(run(self.vault, "run", "--mode", "chat", "--message", message))
        self.assertNotIn("asked before", first["question"])
        self.assertIn("asked before", third["question"])

    def test_generic_followup_keeps_current_stage_instead_of_resetting(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "内定をもらったので条件を確認したい"))
        self.assertEqual(proposed["stage"], "内定・条件交渉")
        output(run(self.vault, "approve", proposed["proposal"]["id"], "--evidence", "内定をもらったので条件を確認したい"))

        followup = output(run(self.vault, "run", "--mode", "chat", "--message", "다음에 뭘 해야 해?"))
        self.assertEqual(followup["stage"], "内定・条件交渉")

    def test_context_selector_excludes_expired_notes(self) -> None:
        self.set_profile(track="chuto", target_role="Platform Engineer", career_status="active")
        trusted = self.vault / "05-playbooks" / "interview.md"
        trusted.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2026-08-01\n---\n\n# Interview\n\nUseful.\n",
            encoding="utf-8",
        )
        expired = self.vault / "05-playbooks" / "old-interview.md"
        expired.write_text(
            "---\nagent_read: true\nagent_scope: chuto\nagent_stage: 面接\nstatus: verified\nsource_type: curated_practice\nreviewed_on: 2020-01-01\nexpires_on: 2020-06-01\n---\n\n# Old Interview\n\nStale.\n",
            encoding="utf-8",
        )
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "中途で面接を準備したい"))
        self.assertEqual([item["path"] for item in proposed["context"]], ["05-playbooks/interview.md"])

    def test_concurrent_approve_does_not_duplicate_the_event(self) -> None:
        self.set_profile(track="chuto", target_role="Data Engineer", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "転職の面接を準備したい"))
        proposal_id = proposed["proposal"]["id"]

        cmd = [sys.executable, str(SCRIPT), "approve", "--vault", str(self.vault), proposal_id, "--evidence", "面接を準備したい"]
        first = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        second = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        first.communicate()
        second.communicate()
        returncodes = [first.returncode, second.returncode]

        self.assertEqual(sorted(returncodes), [0, 2])
        events = read_jsonl(self.vault / "02-state" / "events.jsonl")
        self.assertEqual(len(events), 1)

    def test_heartbeat_surfaces_profile_deadline(self) -> None:
        self.set_profile(
            track="chuto",
            target_role="Data Engineer",
            career_status="active",
            current_company_end_date=(date.today() + timedelta(days=3)).isoformat(),
        )
        heartbeat = output(run(self.vault, "run", "--mode", "heartbeat"))
        reasons = [action["reason"] for action in heartbeat["actions"]]
        self.assertIn("profile_deadline", reasons)

    def test_approve_failure_injection_and_end_to_end_idempotency(self) -> None:
        """Requirement 5 & 6: Artificially inject failures at pipeline/state/proposal stages, then retry and verify state is identical to single approval."""
        from unittest.mock import patch
        from career_agent import CareerVault, approve

        home = CareerVault(self.vault)
        self.set_profile(track="chuto", target_role="Backend Dev", career_status="active")
        proposed = output(run(self.vault, "run", "--mode", "chat", "--message", "A社に面接を申し込んだ", cwd=self.workdir))
        proposal_id = proposed["proposal"]["id"]

        pipeline_target = self.workdir / "data" / "pipeline.yml"

        with patch("career_agent.pipeline_file", return_value=pipeline_target):
            # Failure 1: Simulated failure during pipeline store write
            with patch("pipeline_store.upsert_company", side_effect=ValueError("simulated pipeline error")):
                with self.assertRaises(ValueError):
                    approve(home, proposal_id, evidence=["面接申込完了"], company="A社")

            # Verify vault is unchanged and proposal remains pending
            events_file = self.vault / "02-state" / "events.jsonl"
            self.assertEqual(len(read_jsonl(events_file)) if events_file.exists() else 0, 0)
            pending_props = [p for p in read_jsonl(self.vault / "02-state" / "proposals.jsonl") if p["id"] == proposal_id]
            self.assertEqual(pending_props[0]["status"], "pending")

            # Failure 2: Simulated failure during save_state (pipeline succeeds, state fails)
            with patch.object(CareerVault, "save_state", side_effect=OSError("simulated state error")):
                with self.assertRaises(OSError):
                    approve(home, proposal_id, evidence=["面接申込完了"], company="A社")

            # Verify proposal is STILL pending after failure 2
            pending_props = [p for p in read_jsonl(self.vault / "02-state" / "proposals.jsonl") if p["id"] == proposal_id]
            self.assertEqual(pending_props[0]["status"], "pending")

            # Failure 3: proposal replacement fails after all projection stores committed.
            # The proposal must remain retryable, while the committed projection is reusable.
            with patch.object(CareerVault, "replace_proposal", side_effect=OSError("simulated proposal error")):
                with self.assertRaises(OSError):
                    approve(home, proposal_id, evidence=["面接申込完了"], company="A社")

            pending_props = [p for p in read_jsonl(self.vault / "02-state" / "proposals.jsonl") if p["id"] == proposal_id]
            self.assertEqual(pending_props[0]["status"], "pending")
            state_after_failure = home.load_state()
            committed_version = state_after_failure["version"]
            checkpoint_versions = [row["version"] for row in read_jsonl(home.checkpoints)]
            version_files = sorted(path.name for path in home.versions.glob("*.json"))
            self.assertEqual(checkpoint_versions, [committed_version])
            self.assertEqual(version_files, [f"{committed_version}.json"])

            # Retry the pending proposal. It must reuse the committed version rather than
            # creating another checkpoint/version for the same event.
            clean_result = approve(home, proposal_id, evidence=["面接申込完了"], company="A社")
            self.assertTrue(clean_result["approved"])
            self.assertEqual(clean_result["version"], committed_version)

            # Check deduplication across all projection stores and state-version side effects.
            events = read_jsonl(self.vault / "02-state" / "events.jsonl")
            self.assertEqual(len(events), 1)

            state = home.load_state()
            action_event_ids = [a["event_id"] for a in state.get("open_actions", [])]
            self.assertEqual(len(action_event_ids), len(set(action_event_ids)))

            import pipeline_store
            p_data = pipeline_store.load(pipeline_target)
            company_entry = p_data["companies"][0]
            history_ids = [h.get("event_id") for h in company_entry.get("history", []) if isinstance(h, dict) and "event_id" in h]
            self.assertEqual(len(history_ids), len(set(history_ids)))
            self.assertEqual(history_ids, [events[0]["id"]])
            self.assertEqual([row["version"] for row in read_jsonl(home.checkpoints)], [committed_version])
            self.assertEqual(sorted(path.name for path in home.versions.glob("*.json")), [f"{committed_version}.json"])

            # The retry projection must be logically identical to one clean approve; UUIDs
            # and timestamps are deliberately excluded from this projection comparison.
            fresh_vault = self.vault.parent / "exactly-once-vault"
            output(run(fresh_vault, "init"))
            (fresh_vault / "00-control" / "career-profile.toml").write_text(
                (self.vault / "00-control" / "career-profile.toml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            fresh_home = CareerVault(fresh_vault)
            fresh_proposed = output(run(
                fresh_vault, "run", "--mode", "chat", "--message", "A社に面接を申し込んだ", cwd=self.workdir,
            ))
            fresh_target = fresh_home.path.parent / "fresh-data" / "pipeline.yml"
            with patch("career_agent.pipeline_file", return_value=fresh_target):
                approve(fresh_home, fresh_proposed["proposal"]["id"], evidence=["面接申込完了"], company="A社")

            def logical_projection(vault, target):
                data = pipeline_store.load(target)
                entry = data["companies"][0]
                state = vault.load_state()
                return {
                    "company": {
                        "slug": entry["slug"],
                        "name": entry["name"],
                        "stage": entry.get("stage"),
                        "next_action": entry.get("next_action"),
                        "history": [(item.get("date"), item.get("event")) for item in entry["history"]],
                    },
                    "state": {
                        "track": state.get("track"),
                        "stage": state.get("stage"),
                        "flow_phase": state.get("flow_phase"),
                        "open_actions": [
                            {"text": item.get("text"), "stage": item.get("stage")}
                            for item in state["open_actions"]
                        ],
                        "deadlines": [
                            {key: item.get(key) for key in ("date", "title", "status")}
                            for item in state["deadlines"]
                        ],
                    },
                }

            self.assertEqual(logical_projection(home, pipeline_target), logical_projection(fresh_home, fresh_target))



if __name__ == "__main__":
    unittest.main()
