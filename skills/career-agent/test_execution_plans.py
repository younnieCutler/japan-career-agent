"""Gate D PR1: a host-coordinated plan over the existing invocation ledger."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"

sys.path.insert(0, str(ROOT / "skills" / "career-agent"))

from models import CareerError  # noqa: E402
from validation import validate_execution_plan  # noqa: E402


def run(vault: Path, command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def output(result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class ExecutionPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.vault = Path(self.tempdir.name) / "vault"
        output(run(self.vault, "init"))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create_plan(self, skill: str = "career-document", quality: tuple[str, ...] = ()) -> dict:
        args = [
            "--skill",
            skill,
            "--goal",
            "지원 회사용 職務経歴書 작성",
        ]
        for value in quality:
            args.extend(("--quality", value))
        return output(run(
            self.vault,
            "plan",
            *args,
        ))

    def complete_step(self, plan_id: str, *, signal: str | None = None) -> dict:
        step = output(run(self.vault, "plan-next", plan_id))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan_id,
            "--step-id",
            step["id"],
        ))
        report_args = [
            opened["invocation_id"],
            "--status",
            "completed",
            "--summary",
            f"{step['skill']} completed",
        ]
        if signal:
            report_args.extend(("--signal", signal))
        output(run(self.vault, "skill-report", *report_args))
        return step

    def test_career_document_plan_is_a_flat_quality_vertical_slice(self) -> None:
        plan = self.create_plan()

        self.assertEqual(plan["mode"], "plan")
        self.assertEqual(plan["status"], "running")
        self.assertEqual(
            [step["skill"] for step in plan["steps"]],
            ["career-document", "humanize-japanese-career", "factchk", "sip"],
        )
        self.assertEqual([step["status"] for step in plan["steps"]], ["pending"] * 4)
        self.assertEqual(plan["steps"][0]["depends_on"], [])
        self.assertEqual(plan["steps"][1]["depends_on"], [plan["steps"][0]["id"]])
        self.assertEqual(plan["steps"][2]["depends_on"], [plan["steps"][1]["id"]])

    def test_linked_invocation_advances_only_after_terminal_report(self) -> None:
        plan = self.create_plan()
        plan_id = plan["plan_id"]

        first = output(run(self.vault, "plan-next", plan_id))
        step = first["next_step"]
        self.assertEqual(step["skill"], "career-document")
        self.assertIn("--plan-id", step["invoke_with"])
        self.assertIn("--step-id", step["invoke_with"])

        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan_id,
            "--step-id",
            step["id"],
        ))
        self.assertEqual(opened["status"], "started")
        self.assertEqual(opened["plan_id"], plan_id)
        self.assertEqual(opened["step_id"], step["id"])

        waiting = output(run(self.vault, "plan-next", plan_id))
        self.assertEqual(waiting["current_step"]["id"], step["id"])
        self.assertNotIn("invoke_with", waiting["current_step"])
        self.assertIsNone(waiting["next_step"])

        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "completed",
            "--summary",
            "draft created",
            "--artifact",
            "career-docs/draft.json",
        ))
        advanced = output(run(self.vault, "plan-next", plan_id))
        self.assertEqual(advanced["next_step"]["skill"], "humanize-japanese-career")
        self.assertEqual(advanced["next_step"]["dependency_result"]["from_step"], "draft")
        self.assertEqual(advanced["next_step"]["dependency_result"]["summary"], "draft created")
        self.assertEqual(advanced["next_step"]["artifact_context"]["from_step"], "draft")
        self.assertEqual(advanced["next_step"]["artifact_context"]["artifacts"], ["career-docs/draft.json"])
        persisted = json.loads(
            (self.vault / "02-state" / "execution-plans" / f"{plan_id}.json").read_text(encoding="utf-8")
        )
        self.assertTrue(all("result" not in step for step in persisted["steps"]))

    def test_plan_status_recovers_an_open_invocation(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "codex",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))

        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(status["status"], "running")
        self.assertEqual(status["current_step"]["invocation_id"], opened["invocation_id"])

    def test_plan_status_projects_pause_result_for_resume(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "needs_input",
            "--summary",
            "confirm the target posting",
        ))
        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(status["current_step"]["result"]["summary"], "confirm the target posting")

    def test_required_artifact_contract_refuses_empty_report_before_append(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))
        refused = run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "completed",
            "--summary",
            "draft created without a path",
        )
        self.assertEqual(refused.returncode, 2)
        self.assertIn("artifact", refused.stderr)
        waiting = output(run(self.vault, "plan-next", plan["plan_id"]))
        self.assertEqual(waiting["current_step"]["status"], "started")
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "completed",
            "--summary",
            "draft created with a path",
            "--artifact",
            "career-docs/draft.json",
        ))
        self.assertEqual(
            output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]["skill"],
            "humanize-japanese-career",
        )

    def test_needs_approval_requires_resolution_without_reopening_skill(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "needs_approval",
            "--summary",
            "confirm the strategy before continuing",
        ))
        refused = run(self.vault, "plan-next", plan["plan_id"], "--resume")
        self.assertEqual(refused.returncode, 2)
        continued = output(run(self.vault, "plan-next", plan["plan_id"], "--approval", "continue"))
        self.assertEqual(continued["next_step"]["skill"], "humanize-japanese-career")
        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(status["steps"][0]["approval_resolution"]["decision"], "continue")

    def test_needs_approval_can_abort_without_reopening_skill(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "needs_approval",
            "--summary",
            "confirm the strategy before continuing",
        ))
        aborted = output(run(self.vault, "plan-next", plan["plan_id"], "--approval", "abort"))
        self.assertEqual(aborted["status"], "blocked")
        self.assertEqual(aborted["current_step"]["approval_resolution"]["decision"], "abort")

    def test_retry_reopens_after_historical_started_row(self) -> None:
        plan = self.create_plan()
        next_step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            next_step["id"],
        ))
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "failed",
            "--error",
            "transient failure",
        ))
        output(run(self.vault, "plan-next", plan["plan_id"]))
        retried = output(run(self.vault, "plan-next", plan["plan_id"], "--retry"))
        reopened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            next_step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            retried["next_step"]["id"],
        ))
        self.assertEqual(reopened["status"], "started")

    def test_vertical_slice_reaches_completed_plan(self) -> None:
        plan = self.create_plan()
        plan_id = plan["plan_id"]
        for expected_skill in ("career-document", "humanize-japanese-career", "sip"):
            step = output(run(self.vault, "plan-next", plan_id))["next_step"]
            self.assertEqual(step["skill"], expected_skill)
            opened = output(run(
                self.vault,
                "skill-open",
                "--skill",
                expected_skill,
                "--entrypoint",
                "claude",
                "--plan-id",
                plan_id,
                "--step-id",
                step["id"],
            ))
            output(run(
                self.vault,
                "skill-report",
                opened["invocation_id"],
                "--status",
                "completed",
                "--summary",
                f"{expected_skill} completed",
                "--artifact",
                f"career-docs/{expected_skill}.json",
            ))
        final = output(run(self.vault, "plan-next", plan_id))
        self.assertEqual(final["status"], "completed")
        self.assertIsNone(final["next_step"])

    def test_quality_policy_builds_company_and_strategy_chains(self) -> None:
        company = self.create_plan("kigyou-bunseki")
        self.assertEqual(
            [step["skill"] for step in company["steps"]],
            ["kigyou-bunseki", "factchk", "sip"],
        )
        self.assertIsNone(company["steps"][1]["condition"])

        strategy = self.create_plan("tenshoku-strategy", ("hate",))
        self.assertEqual(
            [step["skill"] for step in strategy["steps"]],
            ["tenshoku-strategy", "hate", "factchk", "sip"],
        )
        self.assertEqual(strategy["steps"][2]["condition"], "external_claims_present")
        self.assertEqual(strategy["steps"][3]["condition"], "substantial_artifact")

        rejected = run(self.vault, "plan", "--skill", "career-document", "--goal", "doc", "--quality", "hate")
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("reserved", rejected.stderr)

    def test_missing_quality_signals_skip_optional_steps(self) -> None:
        plan = self.create_plan("jiko-bunseki")
        self.complete_step(plan["plan_id"])
        final = output(run(self.vault, "plan-next", plan["plan_id"]))
        self.assertEqual(final["status"], "completed")
        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(
            [step["status"] for step in status["steps"]],
            ["completed", "skipped", "skipped"],
        )

    def test_external_claim_signal_runs_factchk_but_not_sip_without_artifact_signal(self) -> None:
        plan = self.create_plan("jiko-bunseki")
        self.complete_step(plan["plan_id"], signal="external_claims_present")
        factcheck = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        self.assertEqual(factcheck["skill"], "factchk")
        self.complete_step(plan["plan_id"])
        final = output(run(self.vault, "plan-next", plan["plan_id"]))
        self.assertEqual(final["status"], "completed")
        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(
            [step["status"] for step in status["steps"]],
            ["completed", "completed", "skipped"],
        )

    def test_substantial_artifact_signal_runs_sip_without_factchk(self) -> None:
        plan = self.create_plan("jiko-bunseki")
        self.complete_step(plan["plan_id"], signal="substantial_artifact")
        sip = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        self.assertEqual(sip["skill"], "sip")
        self.complete_step(plan["plan_id"])
        final = output(run(self.vault, "plan-next", plan["plan_id"]))
        self.assertEqual(final["status"], "completed")
        status = output(run(self.vault, "plan-status", plan["plan_id"]))
        self.assertEqual(
            [step["status"] for step in status["steps"]],
            ["completed", "skipped", "completed"],
        )

    def test_needs_input_pauses_and_resume_reopens_the_same_step(self) -> None:
        plan = self.create_plan("jiko-bunseki")
        step = output(run(self.vault, "plan-next", plan["plan_id"]))["next_step"]
        opened = output(run(
            self.vault,
            "skill-open",
            "--skill",
            step["skill"],
            "--entrypoint",
            "claude",
            "--plan-id",
            plan["plan_id"],
            "--step-id",
            step["id"],
        ))
        output(run(
            self.vault,
            "skill-report",
            opened["invocation_id"],
            "--status",
            "needs_input",
            "--summary",
            "one clarification is required",
        ))
        paused = output(run(self.vault, "plan-next", plan["plan_id"]))
        self.assertEqual(paused["status"], "paused")
        resumed = output(run(self.vault, "plan-next", plan["plan_id"], "--resume"))
        self.assertEqual(resumed["next_step"]["id"], step["id"])

    def test_failed_step_allows_one_retry_then_stops(self) -> None:
        plan = self.create_plan("jiko-bunseki")
        for attempt in range(2):
            next_result = output(
                run(self.vault, "plan-next", plan["plan_id"], "--retry")
                if attempt
                else run(self.vault, "plan-next", plan["plan_id"])
            )
            current = next_result["next_step"]
            opened = output(run(
                self.vault,
                "skill-open",
                "--skill",
                current["skill"],
                "--entrypoint",
                "claude",
                "--plan-id",
                plan["plan_id"],
                "--step-id",
                current["id"],
            ))
            output(run(
                self.vault,
                "skill-report",
                opened["invocation_id"],
                "--status",
                "failed",
                "--error",
                f"transient failure {attempt}",
            ))
            failed = output(run(self.vault, "plan-next", plan["plan_id"]))
            self.assertEqual(failed["status"], "failed")
        refused = run(self.vault, "plan-next", plan["plan_id"], "--retry")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("retry limit", refused.stderr)

    def test_plan_validator_rejects_duplicate_ids_missing_dependencies_and_excess(self) -> None:
        base = {
            "plan_schema_version": 1,
            "plan_id": "plan-aaaaaaaaaaaaaaaa",
            "goal": "test",
            "status": "running",
            "created_at": "2026-08-25T00:00:00Z",
            "updated_at": "2026-08-25T00:00:00Z",
        }
        duplicate = {
            **base,
            "steps": [
                {"id": "draft", "skill": "jiko-bunseki", "status": "pending", "depends_on": [], "condition": None, "invocation_id": None},
                {"id": "draft", "skill": "sip", "status": "pending", "depends_on": ["draft"], "condition": None, "invocation_id": None},
            ],
        }
        with self.assertRaises(CareerError):
            validate_execution_plan(duplicate)
        missing = {
            **base,
            "steps": [{"id": "draft", "skill": "jiko-bunseki", "status": "pending", "depends_on": ["nope"], "condition": None, "invocation_id": None}],
        }
        with self.assertRaises(CareerError):
            validate_execution_plan(missing)
        excessive = {
            **base,
            "steps": [
                {
                    "id": f"s{index}",
                    "skill": skill,
                    "status": "pending",
                    "depends_on": [] if index == 0 else [f"s{index - 1}"],
                    "condition": None,
                    "invocation_id": None,
                }
                for index, skill in enumerate([
                    "jiko-bunseki", "sip", "factchk", "readchk", "hate", "debloat",
                    "kigyou-bunseki", "tenshoku-strategy", "career-document",
                ])
            ],
        }
        with self.assertRaises(CareerError):
            validate_execution_plan(excessive)

        cycle = {
            **base,
            "steps": [
                {"id": "first", "skill": "jiko-bunseki", "status": "pending", "depends_on": ["second"], "condition": None, "invocation_id": None},
                {"id": "second", "skill": "sip", "status": "pending", "depends_on": ["first"], "condition": None, "invocation_id": None},
            ],
        }
        with self.assertRaises(CareerError):
            validate_execution_plan(cycle)


if __name__ == "__main__":
    unittest.main()
