#!/usr/bin/env python3
"""Document to fact promotion tests (PRD phase 5).

The flow spans the private store, the approval gate, and the projection, so it is tested end to end
rather than per module. All fixtures are synthetic (AC-06).

    synthetic://test-fixtures
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import private_store  # noqa: E402
import proposals  # noqa: E402
from models import DOCUMENT_EVIDENCE_PREFIX, CareerError  # noqa: E402


class PromotionHarness(unittest.TestCase):
    """Vault + private store + the CLI. Held apart from the cases so that subclassing it to share
    the fixture does not re-run every sibling's tests -- an inflated count is a test suite that
    reports more coverage than it has."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.vault = self.base / "vault"
        self.private = self.base / "private"
        self.source = self.base / "synthetic-certificate.txt"
        self.source.write_text("synthetic://test-fixtures\n", encoding="utf-8")
        self._run("init")
        self._run("setup", "--track", "chuto", "--target-role", "Synthetic Engineer")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *arguments: str) -> subprocess.CompletedProcess:
        environment = dict(
            os.environ, CAREER_VAULT=str(self.vault), CAREER_PRIVATE_HOME=str(self.private),
        )
        return subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "career_agent.py"), *arguments],
            capture_output=True, text=True, encoding="utf-8", check=False, env=environment,
        )

    def _import(self, effective_from: str = "2026-01-20") -> str:
        result = self._run("private-import", str(self.source), "--type", "certificates",
                           "--effective-from", effective_from)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["document_id"]

    def _propose(self, document_id: str, *extra: str) -> dict:
        result = self._run("propose-fact", "--document-id", document_id,
                           "--category", "language", "--key", "jlpt", "--value", "N1", *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class FactPromotionTest(PromotionHarness):
    """The path the PRD describes, and the guards that keep a draft off it."""

    def test_the_whole_path_from_document_to_projection(self) -> None:
        document_id = self._import()
        proposed = self._propose(document_id, "--effective-from", "2026-01-20")
        self.assertTrue(proposed["needs_confirmation"])
        self.assertFalse(proposed["machine_read"], "nothing here reads the document")

        approved = self._run("approve", proposed["proposal"]["id"])
        self.assertEqual(approved.returncode, 0, approved.stderr)

        profile = self._run("personal-profile", "--as-of", "2026-08-05")
        self.assertEqual(profile.returncode, 0, profile.stderr)
        field = json.loads(profile.stdout)["language"]["jlpt"]
        self.assertEqual(field["state"], "confirmed")
        self.assertEqual(field["value"], "N1")
        self.assertIn(f"{DOCUMENT_EVIDENCE_PREFIX}{document_id}", field["evidence"])

    def test_a_proposal_is_a_draft_until_approved(self) -> None:
        """Section 5.3: the gate is the only thing that makes a fact canonical."""
        document_id = self._import()
        proposed = self._propose(document_id, "--effective-from", "2026-01-20")
        self.assertEqual(proposed["proposal"]["event"]["status"], "draft")

        # A pending proposal lives in proposals.jsonl, not in the event ledger, so the projection
        # does not know the key exists at all -- one step stronger than reporting it as Unknown.
        profile = json.loads(self._run("personal-profile", "--as-of", "2026-08-05").stdout)
        self.assertNotIn("language", profile, "an unreviewed proposal changes nothing")
        self.assertNotIn("N1", json.dumps(profile))

    def test_a_fact_cannot_point_at_a_document_that_was_never_imported(self) -> None:
        """Evidence that resolves to nothing looks provenance-backed and is not."""
        self._import()
        result = self._run("propose-fact", "--document-id", "doc_absent",
                           "--category", "language", "--key", "jlpt", "--value", "N1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no imported document", result.stderr + result.stdout)

    def test_approving_with_extra_evidence_keeps_the_document_link(self) -> None:
        """`--evidence` replaces the list; the provenance link must survive that."""
        document_id = self._import()
        proposed = self._propose(document_id, "--effective-from", "2026-01-20")
        approved = self._run("approve", proposed["proposal"]["id"],
                             "--evidence", "user confirmed against the paper certificate")
        self.assertEqual(approved.returncode, 0, approved.stderr)
        evidence = json.loads(approved.stdout)["event"]["evidence"]
        self.assertIn("user confirmed against the paper certificate", evidence)
        self.assertIn(f"{DOCUMENT_EVIDENCE_PREFIX}{document_id}", evidence)

    def test_a_correction_supersedes_the_approved_fact(self) -> None:
        document_id = self._import(effective_from="2024-07-01")
        first = self._propose(document_id, "--effective-from", "2024-07-01")
        self._run("approve", first["proposal"]["id"])
        approved_fact_id = first["proposal"]["event"]["id"]

        newer = self._run("propose-fact", "--document-id", document_id,
                          "--category", "language", "--key", "jlpt", "--value", "N0",
                          "--effective-from", "2026-01-20", "--supersedes", approved_fact_id)
        self.assertEqual(newer.returncode, 0, newer.stderr)
        second = json.loads(newer.stdout)
        self._run("approve", second["proposal"]["id"])

        field = json.loads(
            self._run("personal-profile", "--as-of", "2026-08-05").stdout
        )["language"]["jlpt"]
        self.assertEqual(field["value"], "N0")
        history = json.loads(
            self._run("personal-timeline", "--category", "language", "--key", "jlpt").stdout
        )["history"]
        retired = next(row for row in history if row["fact_id"] == approved_fact_id)
        self.assertEqual(retired["effective_to"], "2026-01-19")
        self.assertEqual(retired["status"], "superseded")

    def test_the_value_stays_out_of_the_prose(self) -> None:
        """A number in title/summary must appear in the evidence text to be confirmable.

        Satisfying that by echoing the value into the evidence string would make the check
        circular, so the value lives only in the structured payload.
        """
        document_id = self._import()
        result = self._run("propose-fact", "--document-id", document_id,
                           "--category", "compensation", "--key", "base",
                           "--value", "7200000", "--effective-from", "2026-04-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout)["proposal"]["event"]
        self.assertNotIn("7200000", event["title"] + event["summary"])
        self.assertNotIn("7200000", " ".join(event["evidence"]))
        self.assertEqual(event["fact"]["value"], "7200000")
        approved = self._run("approve", json.loads(result.stdout)["proposal"]["id"])
        self.assertEqual(approved.returncode, 0, approved.stderr)


class ApprovalPreflightTest(PromotionHarness):
    """Approval is the canonical commit, so every invariant is enforced before the append."""

    def _approved_fact(self) -> tuple[str, str]:
        document_id = self._import(effective_from="2024-07-01")
        first = self._propose(document_id, "--effective-from", "2024-07-01")
        approved = self._run("approve", first["proposal"]["id"])
        self.assertEqual(approved.returncode, 0, approved.stderr)
        return document_id, first["proposal"]["event"]["id"]

    def _propose_correction(self, document_id: str, value: str, effective_from: str,
                            supersedes: str) -> str:
        result = self._run("propose-fact", "--document-id", document_id,
                           "--category", "language", "--key", "jlpt", "--value", value,
                           "--effective-from", effective_from, "--supersedes", supersedes)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["proposal"]["id"]

    def test_a_second_competing_correction_cannot_be_approved(self) -> None:
        """Each proposal is valid alone; only the pair is a fork, so proposal time cannot see it."""
        document_id, fact_id = self._approved_fact()
        first = self._propose_correction(document_id, "N1", "2026-01-20", fact_id)
        second = self._propose_correction(document_id, "N0", "2026-02-20", fact_id)
        self.assertEqual(self._run("approve", first).returncode, 0)

        rejected = self._run("approve", second)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("more than one confirmed fact", rejected.stderr + rejected.stdout)
        # And the ledger still projects, which it would not if the bad row had been written.
        profile = self._run("personal-profile", "--as-of", "2026-08-05")
        self.assertEqual(profile.returncode, 0, profile.stderr)
        self.assertEqual(json.loads(profile.stdout)["language"]["jlpt"]["value"], "N1")

    def test_a_backdated_correction_cannot_be_approved(self) -> None:
        document_id, fact_id = self._approved_fact()
        proposal = self._propose_correction(document_id, "N1", "2020-01-01", fact_id)
        rejected = self._run("approve", proposal)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("effective after its predecessor", rejected.stderr + rejected.stdout)
        self.assertEqual(self._run("personal-profile", "--as-of", "2026-08-05").returncode, 0)

    def test_a_dangling_supersedes_cannot_be_approved(self) -> None:
        document_id = self._import()
        proposal = self._propose_correction(document_id, "N1", "2026-01-20", "evt-does-not-exist")
        rejected = self._run("approve", proposal)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("supersedes an unknown fact", rejected.stderr + rejected.stdout)

    def test_a_cross_key_supersedes_cannot_be_approved(self) -> None:
        document_id, fact_id = self._approved_fact()
        result = self._run("propose-fact", "--document-id", document_id,
                           "--category", "compensation", "--key", "base", "--value", "7200000",
                           "--effective-from", "2026-04-01", "--supersedes", fact_id)
        self.assertEqual(result.returncode, 0, result.stderr)
        rejected = self._run("approve", json.loads(result.stdout)["proposal"]["id"])
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("within one", rejected.stderr + rejected.stdout)

    def test_an_ordinary_event_is_not_blocked_by_the_fact_preflight(self) -> None:
        """The preflight guards fact-bearing events; unrelated approvals keep working."""
        chat = self._run("run", "--mode", "chat", "--track", "chuto",
                         "--message", "面接の準備をしたい", "--as-of", "2026-08-05")
        self.assertEqual(chat.returncode, 0, chat.stderr)
        proposal_id = json.loads(chat.stdout)["proposal"]["id"]
        approved = self._run("approve", proposal_id, "--evidence", "synthetic confirmation")
        self.assertEqual(approved.returncode, 0, approved.stderr)

    def test_a_document_that_disappeared_between_propose_and_approve_blocks_it(self) -> None:
        """A proposal that resolved against one store says nothing about another."""
        document_id = self._import()
        proposed = self._propose(document_id, "--effective-from", "2026-01-20")
        record = next(row for row in private_store.PrivateHome(self.private).records()
                      if row.get("document_id") == document_id)
        (self.private / record["storage_path"]).unlink()

        rejected = self._run("approve", proposed["proposal"]["id"])
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("stored bytes", rejected.stderr + rejected.stdout)

    def test_an_invented_document_reference_in_extra_evidence_is_refused(self) -> None:
        document_id = self._import()
        proposed = self._propose(document_id, "--effective-from", "2026-01-20")
        rejected = self._run("approve", proposed["proposal"]["id"],
                             "--evidence", "private-document:doc_ghost")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("no imported document", rejected.stderr + rejected.stdout)


class ProposeFactUnitTest(unittest.TestCase):
    """Guards that must hold without going through argparse."""

    def test_the_evidence_reference_is_the_document_id_alone(self) -> None:
        """A copied digest or storage path would be a second source of truth."""
        reference = proposals.document_evidence("doc_abc123")
        self.assertEqual(reference, f"{DOCUMENT_EVIDENCE_PREFIX}doc_abc123")

    def test_an_unknown_document_is_refused_by_the_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = private_store.PrivateHome(Path(tmp) / "private")
            private_store.initialize_private_home(home)
            with self.assertRaises(CareerError) as caught:
                proposals.propose_fact(
                    None, home,
                    document_id="doc_other", category="language", key="jlpt", value="N1",
                )
            self.assertIn("no imported document", str(caught.exception))

    def test_a_duplicate_document_id_is_not_usable_as_evidence(self) -> None:
        """The id is the whole link, so ambiguity in it is ambiguity in the provenance."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "synthetic.txt"
            source.write_text("synthetic://test-fixtures\n", encoding="utf-8")
            home = private_store.PrivateHome(base / "private")
            record = private_store.import_document(home, source, "certificates")
            # A hand-edited registry: the same id twice.
            with home.registry.open("a", encoding="utf-8") as handle:
                rows = [row for row in home.records() if row.get("document_id") == record["document_id"]]
                handle.write(json.dumps(rows[0], ensure_ascii=False) + "\n")
            with self.assertRaises(CareerError) as caught:
                private_store.resolve_document(home, record["document_id"])
            self.assertIn("must identify exactly one document", str(caught.exception))

    def test_a_missing_blob_makes_the_reference_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "synthetic.txt"
            source.write_text("synthetic://test-fixtures\n", encoding="utf-8")
            home = private_store.PrivateHome(base / "private")
            record = private_store.import_document(home, source, "certificates")
            (home.path / record["storage_path"]).unlink()
            with self.assertRaises(CareerError) as caught:
                private_store.resolve_document(home, record["document_id"])
            self.assertIn("stored bytes", str(caught.exception))

    def test_import_never_claims_to_have_read_the_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "synthetic.txt"
            source.write_text("synthetic://test-fixtures\n", encoding="utf-8")
            home = private_store.PrivateHome(base / "private")
            result = private_store.import_document(home, source, "certificates")
            self.assertEqual(result["facts_requiring_confirmation"], [])


if __name__ == "__main__":
    unittest.main()
