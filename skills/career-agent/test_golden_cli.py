#!/usr/bin/env python3
"""Golden CLI projections for the behavior-preserving Career Agent module split."""

from __future__ import annotations

import json
import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "career-agent" / "career_agent.py"
sys.path.insert(0, str(ROOT / "scripts"))
from e2e_capture import capture  # noqa: E402


def invoke(vault: Path, command: str, *args: str, cwd: Path, log_path: Path | None = None) -> dict:
    argv = [sys.executable, str(SCRIPT), command, "--vault", str(vault), *args]
    if log_path:
        result = capture(argv, cwd=cwd, log_path=log_path)
        stdout = result.stdout.decode("utf-8")
        stderr = result.stderr.decode("utf-8")
    else:
        result = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        stdout = result.stdout
        stderr = result.stderr
    if result.returncode:
        raise AssertionError(f"{command} failed ({result.returncode}): {stderr}")
    return json.loads(stdout)


def write_json_lf(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def captured_json(argv: list[str], *, cwd: Path, log_path: Path) -> dict:
    result = capture(argv, cwd=cwd, log_path=log_path)
    if result.returncode:
        raise AssertionError(result.stderr.decode("utf-8"))
    return json.loads(result.stdout.decode("utf-8"))


class GoldenCliTests(unittest.TestCase):
    def test_capture_preserves_invalid_utf8_output_and_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands_log = root / "e2e" / "commands.jsonl"
            child = (
                "import sys; "
                "sys.stdout.buffer.write(b'bad\\xff'); "
                "sys.stderr.buffer.write(b'err\\xfe'); "
                "raise SystemExit(7)"
            )
            result = capture(
                [sys.executable, "-c", child],
                cwd=root,
                log_path=commands_log,
            )
            self.assertEqual(result.returncode, 7)
            row = json.loads(commands_log.read_text(encoding="utf-8").strip())
            self.assertEqual(row["exit_code"], 7)
            self.assertEqual(row["stdout"], "bad�")
            self.assertEqual(row["stderr"], "err�")
            self.assertFalse(row["stdout_utf8_valid"])
            self.assertFalse(row["stderr_utf8_valid"])

    def test_public_cli_projections_remain_stable_after_entrypoint_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            workspace = root / "workspace"
            workspace.mkdir()
            commands_log = root / "e2e" / "commands.jsonl"
            invoke_args = {"cwd": root, "log_path": commands_log}
            setup = invoke(vault, "setup", "--track", "chuto", "--target-role", "Platform Engineer", **invoke_args)
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
            chat = invoke(vault, "run", "--mode", "chat", "--message", message, **invoke_args)
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

            proposals = invoke(vault, "proposals", **invoke_args)
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
                log_path=commands_log,
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

            status = invoke(vault, "status", **invoke_args)
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

            context = invoke(vault, "context", **invoke_args)
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

            doctor = invoke(vault, "doctor", **invoke_args)
            self.assertEqual(
                {"mode": doctor["mode"], "ok": doctor["ok"], "safe_stop": doctor["safe_stop"]},
                {"mode": "doctor", "ok": True, "safe_stop": False},
            )

            self.assertTrue((workspace / "data" / "pipeline.yml").is_file())
            approved_proposal = json.loads((vault / "02-state" / "proposals.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(approved_proposal["event"]["status"], "draft")
            self.assertEqual(approved_proposal["resolution"]["approved_event_id"], approved["event"]["id"])
            rows = [json.loads(line) for line in commands_log.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(rows), 7)
            for row in rows:
                self.assertEqual(row["exit_code"], 0)
                for key in ("started_at", "finished_at", "argv", "cwd", "stdout", "stderr"):
                    self.assertIn(key, row)
                serialized = json.dumps(row, ensure_ascii=False)
                self.assertNotIn(str(Path.home()), serialized)
                self.assertNotIn(str(root), serialized)
            self.assertNotIn(b"\r\n", commands_log.read_bytes())

    def test_fresh_vault_matching_projection_and_full_lifecycle_e2e(self) -> None:
        """Run the real matching, pipeline, and career-agent CLIs in one fresh workspace."""
        import yaml

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault = root / "vault"
            workspace = root / "workspace"
            workspace.mkdir()
            commands_log = root / "e2e" / "commands.jsonl"
            invoke_args = {"cwd": root, "log_path": commands_log}

            setup = invoke(vault, "setup", "--track", "chuto", "--target-role", "Backend Engineer", **invoke_args)
            self.assertTrue(setup["ok"])

            postings = [
                {"company": "Proceed Systems (Synthetic)", "role": "Backend Engineer", "provenance": "synthetic", "source_ref": "synthetic://e2e/postings/proceed"},
                {"company": "Review Systems (Synthetic)", "role": "Backend Engineer", "provenance": "synthetic", "source_ref": "synthetic://e2e/postings/review"},
                {"company": "Conflict Systems (Synthetic)", "role": "Backend Engineer", "provenance": "synthetic", "source_ref": "synthetic://e2e/postings/conflict"},
            ]
            postings_path = root / "postings.json"
            write_json_lf(postings_path, postings)
            discovered = invoke(vault, "run", "--mode", "discover", "--source", str(postings_path), **invoke_args)
            self.assertEqual(discovered["added"], 3)
            self.assertTrue(all(item["provenance"] == "synthetic" for item in discovered["postings"]))

            base = json.loads((ROOT / "examples" / "demo-workspace" / "matching-input.example.json").read_text(encoding="utf-8"))
            cases = {
                "proceed": ("Proceed Systems (Synthetic)", "proceed"),
                "review": ("Review Systems (Synthetic)", "review"),
                "conflict": ("Conflict Systems (Synthetic)", "conflict"),
            }
            from career_agent import company_slug

            pipeline_slugs = {key: company_slug(company) for key, (company, _) in cases.items()}
            for slug, (company, expected) in cases.items():
                payload = copy.deepcopy(base)
                payload["company_name"] = company
                for item in payload["eligibility"]:
                    item["source_ref"] = f"synthetic://e2e/{slug}/{item['requirement']}"
                for bucket in ("required", "preferred"):
                    for item in payload["skills"][bucket]:
                        if item.get("source_ref"):
                            item["source_ref"] = f"synthetic://e2e/{slug}/skill/{item['name']}"
                for item in payload["career_values"]:
                    item["source_ref"] = f"synthetic://e2e/{slug}/value/{item['value']}"
                if slug == "proceed":
                    for item in payload["eligibility"]:
                        item.update({"candidate_evidence": "confirmed", "job_evidence": "confirmed", "meets": True})
                    for item in payload["skills"]["required"]:
                        item.update({"status": "matched", "evidence": "confirmed evidence"})
                    for item in payload["career_values"]:
                        item.update({"satisfied": True, "company_evidence": "confirmed"})
                elif slug == "review":
                    payload["eligibility"][1].update({"candidate_evidence": "remote preferred", "job_evidence": "hybrid", "meets": True})
                    payload["career_values"][0].update({"satisfied": True, "company_evidence": "hybrid"})
                fixture = root / "matching" / f"{slug}.json"
                write_json_lf(fixture, payload)
                result = captured_json([sys.executable, str(ROOT / "_shared" / "matching_v3.py"), str(fixture)], cwd=root, log_path=commands_log)
                self.assertEqual(result["decision_status"], expected)
                fields = {
                    "name": company,
                    "match_model_version": result["model_version"],
                    "decision_status": result["decision_status"],
                    "match_conflicts": result["decision_basis"]["conflicts"],
                    "match_required_gaps": result["decision_basis"]["required_gaps"],
                    "match_unknowns": result["decision_basis"]["unknowns"],
                }
                captured = capture(
                    [sys.executable, str(ROOT / "scripts" / "pipeline.py"), "--path", str(workspace / "data" / "pipeline.yml"), "upsert", pipeline_slugs[slug], "--json", json.dumps(fields, ensure_ascii=False)],
                    cwd=root,
                    log_path=commands_log,
                )
                self.assertEqual(captured.returncode, 0, captured.stderr.decode("utf-8"))

            event_message = "confirmed interview evidence"
            chat = invoke(vault, "run", "--mode", "chat", "--message", event_message, **invoke_args)
            proposal_id = chat["proposal"]["id"]
            listed = invoke(vault, "proposals", **invoke_args)
            self.assertTrue(any(item["id"] == proposal_id for item in listed["proposals"]))
            approved = invoke(
                vault, "approve", proposal_id, "--evidence", "https://example.invalid/evidence/" + "x" * 220,
                "--company", "Conflict Systems (Synthetic)", "--workspace", str(workspace), log_path=commands_log, cwd=workspace,
            )
            self.assertEqual(approved["event"]["status"], "confirmed")
            status = invoke(vault, "status", **invoke_args)
            context = invoke(vault, "context", **invoke_args)
            doctor = invoke(vault, "doctor", "--workspace", str(workspace), **invoke_args)
            self.assertTrue(context["read_only"])
            self.assertTrue(doctor["ok"])
            self.assertEqual(status["state"]["open_actions"], [])

            pipeline = yaml.safe_load((workspace / "data" / "pipeline.yml").read_text(encoding="utf-8")) or {}
            by_slug = {item["slug"]: item for item in pipeline["companies"]}
            self.assertEqual({by_slug[pipeline_slugs[key]]["decision_status"] for key in cases}, {"proceed", "review", "conflict"})
            conflict_history = by_slug[pipeline_slugs["conflict"]]["history"]
            self.assertEqual(conflict_history[-1]["event_id"], approved["event"]["id"])
            self.assertNotIn("evidence", json.dumps(conflict_history, ensure_ascii=False))
            events = [json.loads(line) for line in (vault / "02-state" / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(events), 1)
            event = events[0]
            conflict_entry = by_slug[pipeline_slugs["conflict"]]
            self.assertEqual(conflict_entry["name"], event["company"])
            self.assertEqual(conflict_entry["stage"], 4)
            history = next(item for item in conflict_entry["history"] if item["event_id"] == event["id"])
            self.assertEqual(history["date"], event["occurred_at"][:10])
            self.assertEqual(history["event"], event["title"])
            self.assertEqual(event["evidence"][0], "https://example.invalid/evidence/" + "x" * 220)
            self.assertNotIn(event["evidence"][0], json.dumps(pipeline, ensure_ascii=False))

            rows = [json.loads(line) for line in commands_log.read_text(encoding="utf-8").splitlines() if line]
            self.assertEqual(len(rows), 14)
            for row in rows:
                self.assertEqual(row["exit_code"], 0)
                self.assertNotIn(str(Path.home()), json.dumps(row, ensure_ascii=False))
                self.assertNotIn(str(root), json.dumps(row, ensure_ascii=False))
            self.assertNotIn(b"\r\n", commands_log.read_bytes())


if __name__ == "__main__":
    unittest.main()
