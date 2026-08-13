"""Deterministic P0 UX contract tests for the public Career Agent CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(SCRIPT.parent))
from ux import attach  # noqa: E402


def run(vault: Path, command: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        cwd=cwd or vault.parent,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def stdout_json(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


class UXContractTests(unittest.TestCase):
    def test_setup_pending_review_block_and_approval_are_additive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            missing = run(vault, "setup")
            self.assertEqual(missing.returncode, 2)
            missing_payload = stdout_json(missing)
            self.assertEqual(missing_payload["ux"]["state"], "needs_input")
            self.assertEqual(missing_payload["ux"]["reason"]["code"], "SETUP_REQUIRED")
            self.assertIn("next", missing_payload["ux"])

            setup = run(vault, "setup", "--track", "chuto", "--target-role", "Engineer")
            self.assertEqual(setup.returncode, 0, setup.stderr)
            original = stdout_json(setup)
            self.assertEqual(original["ux"]["state"], "ready")
            self.assertEqual(original["next"], "run --mode chat")

            proposed = run(vault, "run", "--mode", "chat", "--message", "prepare interview")
            self.assertEqual(proposed.returncode, 0, proposed.stderr)
            proposal_payload = stdout_json(proposed)
            proposal_id = proposal_payload["proposal"]["id"]
            self.assertEqual(proposal_payload["ux"]["state"], "needs_confirmation")
            self.assertEqual(proposal_payload["ux"]["reason"]["code"], "PENDING_PROPOSAL")
            self.assertTrue(any(item["id"] == "approve_proposal" for item in proposal_payload["ux"]["next"]["actions"]))

            listed = stdout_json(run(vault, "proposals"))
            self.assertEqual(listed["proposals"][0]["id"], proposal_id)
            self.assertNotIn("event", listed["proposals"][0])
            reviewed = stdout_json(run(vault, "proposals", "--id", proposal_id))
            self.assertEqual(reviewed["ux"]["state"], "needs_confirmation")
            self.assertIn("event", reviewed["proposal"])

            blocked = run(vault, "approve", proposal_id)
            self.assertEqual(blocked.returncode, 2)
            blocked_payload = json.loads(blocked.stderr)
            self.assertEqual(blocked_payload["error_code"], "EVIDENCE_REQUIRED")
            self.assertFalse(blocked_payload["state_changed"])
            self.assertEqual(blocked_payload["ux"]["effects"]["unchanged"], ["canonical state"])

            approved = run(vault, "approve", proposal_id, "--evidence", "prepare interview")
            self.assertEqual(approved.returncode, 0, approved.stderr)
            approved_payload = stdout_json(approved)
            self.assertEqual(approved_payload["ux"]["state"], "completed")
            self.assertIn("approved event/canonical state", approved_payload["ux"]["effects"]["changed"])

            human = run(vault, "status", "--format", "human")
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertIn("상태:", human.stdout)
            self.assertNotIn("—", human.stdout)

    def test_workspace_and_recovery_blockers_are_explicit_and_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            setup = run(vault, "setup", "--track", "chuto")
            self.assertEqual(setup.returncode, 0, setup.stderr)

            missing_workspace = run(vault, "status", "--workspace", str(root / "does-not-exist"))
            self.assertEqual(missing_workspace.returncode, 2)
            workspace_payload = json.loads(missing_workspace.stderr)
            self.assertEqual(workspace_payload["error_code"], "WORKSPACE_NOT_FOUND")
            self.assertFalse(workspace_payload["state_changed"])

            missing_version = run(vault, "restore-state", "version-does-not-exist")
            self.assertEqual(missing_version.returncode, 2)
            recovery_payload = json.loads(missing_version.stderr)
            self.assertEqual(recovery_payload["error_code"], "STATE_VERSION_NOT_FOUND")
            self.assertFalse(recovery_payload["state_changed"])

    def test_unknown_and_conflict_remain_domain_issues(self) -> None:
        unknown = attach(
            "personal-profile",
            {"mode": "personal-profile", "skills": {"aws": {"state": "unknown", "reason": "no verified evidence"}}},
        )
        self.assertEqual(unknown["ux"]["state"], "review")
        self.assertEqual(unknown["ux"]["issues"][0]["code"], "FACT_UNKNOWN")
        self.assertTrue(any(action["id"] == "keep_unknown" for action in unknown["ux"]["next"]["actions"]))

        conflict = attach(
            "personal-profile",
            {"mode": "personal-profile", "eligibility": {"japanese": {"state": "conflict", "reason": "confirmed evidence disagrees"}}},
        )
        self.assertEqual(conflict["ux"]["state"], "review")
        self.assertEqual(conflict["ux"]["issues"][0]["code"], "FACT_CONFLICT")
        self.assertTrue(any(action["id"] == "keep_conflict" for action in conflict["ux"]["next"]["actions"]))


class FirstRunVocabularyTests(unittest.TestCase):
    """What a user reads must be in their language; the machine payload is unaffected."""

    def test_every_effect_string_resolves_to_a_translated_phrase(self) -> None:
        """Every declared effect must have a label; unknown effects now fail rather than leak.

        This walks the source rather than a sample of results, because a missing label appears only
        on the command that produces that one effect.
        """
        import ast
        import localization

        source = (SCRIPT.parent / "ux.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        assignments: dict[str, list[ast.expr]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                assignments.setdefault(node.targets[0].id, []).append(node.value)

        def strings(node: ast.expr) -> list[str]:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return [node.value]
            if isinstance(node, ast.List):
                return [value for element in node.elts for value in strings(element)]
            if isinstance(node, ast.IfExp):
                return strings(node.body) + strings(node.orelse)
            if isinstance(node, ast.Name):
                return [value for source in assignments.get(node.id, []) for value in strings(source)]
            raise AssertionError(
                f"ux.py line {node.lineno}: cannot read this effect statically. Pass a list of "
                "string literals so the catalog can be checked at build time."
            )

        effects = {
            value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for keyword in node.keywords
            if keyword.arg in {"changed", "unchanged"}
            for value in strings(keyword.value)
        }
        self.assertTrue(effects)
        # Comparing the label against the raw string would not do: several English translations are
        # the same words as the internal name, so a real leak and a correct entry look identical.
        self.assertEqual(sorted(effects - set(localization.EFFECT_ALIASES)), [])

    def test_the_first_run_never_shows_an_identifier_or_an_internal_file(self) -> None:
        """Record, confirm, reuse. Getting to a first approved record never requires reading a
        proposal id, a store filename or a schema version.

        The user's own workspace directory is deliberately still shown: it is a directory they
        chose and will look inside, so hiding it would cost them more than the term does."""

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            human = ("--format", "human")
            transcript = [
                run(vault, "setup", "--track", "chuto", "--target-role", "SRE", *human),
                run(vault, "run", "--mode", "chat", "--message", "面接の準備をしたい", *human),
                run(vault, "status", *human),
                run(vault, "guided", *human),
            ]
            for result in transcript:
                self.assertEqual(result.returncode, 0, result.stderr)
            printed = "\n".join(result.stdout for result in transcript)

            self.assertNotRegex(printed, r"proposal-[0-9a-f]{12}", "a proposal id is visible")
            self.assertNotRegex(printed, r"[0-9a-f]{8}-[0-9a-f]{4}-", "an event id is visible")
            self.assertNotIn(str(vault), printed, "the Vault's internal path is visible")
            for internal in ("pipeline.yml", "events.jsonl", "proposals.jsonl", ".career-agent",
                             "schema_version", "proposal_id", "canonical", "projection", "revision"):
                self.assertNotIn(internal, printed, f"{internal!r} is an internal term")
            # The JSON contract is untouched: the same run still carries the id a caller needs.
            machine = json.loads(run(vault, "proposals").stdout)
            self.assertRegex(machine["proposals"][0]["id"], r"^proposal-[0-9a-f]{12}$")


if __name__ == "__main__":
    unittest.main()
