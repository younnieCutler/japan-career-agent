#!/usr/bin/env python3
"""Golden CLI projections for the behavior-preserving Career Agent module split."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"


def invoke(vault: Path, command: str, *args: str, cwd: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(f"{command} failed ({result.returncode}): {result.stderr}")
    return json.loads(result.stdout)


class GoldenCliTests(unittest.TestCase):
    def test_public_cli_projections_remain_stable_after_entrypoint_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            workspace = root / "workspace"
            workspace.mkdir()
            setup = invoke(vault, "setup", "--track", "chuto", "--target-role", "Platform Engineer", cwd=root)
            self.assertEqual(
                {
                    "mode": setup["mode"],
                    "ok": setup["ok"],
                    "needs_input": setup["needs_input"],
                    "next": setup["next"],
                    "track": setup["profile"]["track"],
                    "target_role": setup["profile"]["target_role"],
                },
                {
                    "mode": "setup",
                    "ok": True,
                    "needs_input": [],
                    "next": "run --mode chat",
                    "track": "chuto",
                    "target_role": "Platform Engineer",
                },
            )

            message = "転職の面接を準備したい"
            chat = invoke(vault, "run", "--mode", "chat", "--message", message, cwd=root)
            self.assertEqual(
                {
                    "mode": chat["mode"],
                    "language": chat["language"],
                    "track": chat["track"],
                    "stage": chat["stage"],
                    "flow_phase": chat["flow_phase"],
                    "proposal_kind": chat["proposal"]["kind"],
                    "proposal_status": chat["proposal"]["status"],
                    "event_status": chat["proposal"]["event"]["status"],
                },
                {
                    "mode": "chat",
                    "language": "ja",
                    "track": "chuto",
                    "stage": "面接",
                    "flow_phase": "interview",
                    "proposal_kind": "event",
                    "proposal_status": "pending",
                    "event_status": "draft",
                },
            )
            proposal_id = chat["proposal"]["id"]

            proposals = invoke(vault, "proposals", cwd=root)
            self.assertEqual(proposals["mode"], "proposals")
            self.assertEqual(proposals["count"], 1)
            self.assertEqual(proposals["proposals"][0]["id"], proposal_id)
            self.assertEqual(proposals["proposals"][0]["kind"], "event")
            self.assertEqual(proposals["proposals"][0]["status"], "pending")

            approved = invoke(
                vault,
                "approve",
                proposal_id,
                "--evidence",
                message,
                "--company",
                "Aozora Systems (Synthetic)",
                "--workspace",
                str(workspace),
                cwd=workspace,
            )
            self.assertEqual(
                {
                    "approved": approved["approved"],
                    "event_status": approved["event"]["status"],
                    "company": approved["event"]["company"],
                    "proposal_status": approved["proposal"]["status"],
                },
                {
                    "approved": True,
                    "event_status": "confirmed",
                    "company": "Aozora Systems (Synthetic)",
                    "proposal_status": "approved",
                },
            )

            status = invoke(vault, "status", cwd=root)
            self.assertEqual(
                {
                    "track": status["profile"]["track"],
                    "target_role": status["profile"]["target_role"],
                    "event_count": status["event_count"],
                    "pending_proposals": status["pending_proposals"],
                    "state_track": status["state"]["track"],
                    "state_stage": status["state"]["stage"],
                },
                {
                    "track": "chuto",
                    "target_role": "Platform Engineer",
                    "event_count": 1,
                    "pending_proposals": 0,
                    "state_track": "chuto",
                    "state_stage": "面接",
                },
            )

            context = invoke(vault, "context", cwd=root)
            self.assertEqual(
                {
                    "mode": context["mode"],
                    "track": context["profile"]["track"],
                    "read_only": context["read_only"],
                    "note_bodies_included": context["note_bodies_included"],
                    "career_context_confirmed": context["career_context_confirmed"],
                },
                {
                    "mode": "context",
                    "track": "chuto",
                    "read_only": True,
                    "note_bodies_included": False,
                    "career_context_confirmed": False,
                },
            )

            doctor = invoke(vault, "doctor", cwd=root)
            self.assertEqual(
                {"mode": doctor["mode"], "ok": doctor["ok"], "safe_stop": doctor["safe_stop"]},
                {"mode": "doctor", "ok": True, "safe_stop": False},
            )

            self.assertTrue((workspace / "data" / "pipeline.yml").is_file())


if __name__ == "__main__":
    unittest.main()
