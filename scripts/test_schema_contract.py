#!/usr/bin/env python3
"""Executable-schema contract tests: strict on the way in, tolerant on the way out.

The two directions are tested against the same documents on purpose. A test that only proved the
strict validator rejects something would not show that the tolerant one still accepts it, and that
second half is the whole reason the split exists: an unknown field must be an error for a producer
and a non-event for a reader of somebody's existing Vault.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "_shared"))
FIXTURES = ROOT / "_shared" / "tests" / "fixtures" / "legacy"

from schema_contract import SchemaContractError, load_catalog, validate_document, validate_new_write  # noqa: E402
import pipeline_store  # noqa: E402


VALID_PROFILE = {
    "self_analysis_version": 2,
    "candidate_name": "candidate",
    "language_preference": "ko",
    "track": "chuto",
    "interest_hypotheses": None,
    "behavior_tendencies": None,
    "evidence_episodes": None,
    "career_self_efficacy": None,
    "perceived_barriers": None,
    "perceived_supports": None,
    "environment_preferences": None,
    "value_candidates": None,
    "avoid_candidates": None,
}
VALID_CANDIDATE = {
    "candidate_name": "candidate",
    "work_style_reflection": {},
    "skill_stack": [],
    "target_role": "Data Engineer",
    "jlpt_level": None,
}
VALID_COMPANY = {"company_name": "A", "position": "Engineer", "required_skills": []}
VALID_RULES = {
    "rules": [{
        "id": "numbers-in-episodes", "text": "エピソードに数値を入れる", "status": "active",
        "source": "observed_workflow", "supported_by": ["a-corp", "b-corp"], "created": "2026-08-11",
    }],
}


class SchemaContractTests(unittest.TestCase):
    def test_catalog_has_all_canonical_definitions(self) -> None:
        catalog = load_catalog()
        self.assertEqual(
            {"SELF_ANALYSIS_PROFILE", "CANDIDATE_PROFILE", "COMPANY_PROFILE", "MATCH_HISTORY", "PIPELINE", "RULES"},
            set(catalog["$defs"]),
        )

    def test_representative_documents_validate(self) -> None:
        validate_document("SELF_ANALYSIS_PROFILE", VALID_PROFILE)
        validate_document("CANDIDATE_PROFILE", VALID_CANDIDATE)
        validate_document("COMPANY_PROFILE", VALID_COMPANY)
        validate_document("MATCH_HISTORY", [])
        validate_document("PIPELINE", {"companies": []})
        validate_document("RULES", VALID_RULES)

    def test_representative_documents_pass_the_strict_writer(self) -> None:
        validate_new_write("SELF_ANALYSIS_PROFILE", VALID_PROFILE)
        validate_new_write("CANDIDATE_PROFILE", VALID_CANDIDATE)
        validate_new_write("COMPANY_PROFILE", VALID_COMPANY)
        validate_new_write("PIPELINE", {"companies": [{"slug": "a", "name": "A"}]})
        validate_new_write("RULES", VALID_RULES)

    def test_missing_shape_and_legacy_new_write_are_rejected(self) -> None:
        with self.assertRaises(SchemaContractError):
            validate_document("PIPELINE", {"companies": [{"name": "missing slug"}]})
        with self.assertRaises(SchemaContractError):
            validate_new_write("CANDIDATE_PROFILE", dict(VALID_CANDIDATE, overall_score=80))


class StrictWriteTests(unittest.TestCase):
    """Every shape a producer can get wrong, and what each direction does about it."""

    def assertWriteRejected(self, name: str, document: object, expected: str) -> None:
        with self.assertRaises(SchemaContractError) as caught:
            validate_new_write(name, document)
        self.assertIn(expected, str(caught.exception))
        # The same document must still read, or the strictness has broken somebody's Vault.
        validate_document(name, document)

    def test_an_unknown_top_level_field_is_rejected(self) -> None:
        self.assertWriteRejected(
            "CANDIDATE_PROFILE", dict(VALID_CANDIDATE, favourite_colour="blue"), "favourite_colour",
        )

    def test_the_typo_the_open_schema_used_to_accept_is_rejected(self) -> None:
        """The example from the v2.2 PRD: one transposed letter, silently stored, never read."""
        entry = {"slug": "a", "name": "A", "decison_status": "proceed"}
        self.assertWriteRejected("PIPELINE", {"companies": [entry]}, "decison_status")

    def test_an_unknown_nested_jd_requirement_field_is_rejected(self) -> None:
        entry = {
            "slug": "a", "name": "A",
            "jd_requirements": [{"text": "Kubernetes", "evidence_id": "evt-1"}],
        }
        self.assertWriteRejected("PIPELINE", {"companies": [entry]}, "evidence_id")

    def test_an_invalid_enum_is_rejected_on_both_paths(self) -> None:
        """A declared enum is a shape claim, not a legacy allowance: it fails reads too."""
        entry = {"slug": "a", "name": "A", "decision_status": "probably"}
        for validate in (validate_document, validate_new_write):
            with self.assertRaises(SchemaContractError):
                validate("PIPELINE", {"companies": [entry]})

    def test_a_frozen_legacy_field_reads_but_never_writes(self) -> None:
        self.assertWriteRejected(
            "SELF_ANALYSIS_PROFILE", dict(VALID_PROFILE, preferred_company_type="startup"),
            "cannot write legacy fields",
        )

    def test_checked_at_is_writable_because_check_action_writes_it(self) -> None:
        """It survived only because the schema was open; naming it is what keeps it legal."""
        entry = {
            "slug": "a", "name": "A",
            "action_items": [{"id": "x", "text": "send", "checked": True, "checked_at": "2026-08-11"}],
        }
        validate_new_write("PIPELINE", {"companies": [entry]})


class LegacyReadTests(unittest.TestCase):
    """Historical shapes on disk. Every one of these must keep reading, forever."""

    def test_every_legacy_fixture_still_reads(self) -> None:
        fixtures = sorted(FIXTURES.glob("*.yml"))
        self.assertTrue(fixtures, f"no legacy fixtures under {FIXTURES}")
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                document = yaml.safe_load(fixture.read_text(encoding="utf-8"))
                validate_document(document["schema"], document["value"])

    def test_a_legacy_fixture_would_be_refused_as_a_new_write(self) -> None:
        """Proof the fixtures are actually legacy, rather than documents that pass either way."""
        refused = 0
        for fixture in sorted(FIXTURES.glob("*.yml")):
            document = yaml.safe_load(fixture.read_text(encoding="utf-8"))
            if not document.get("writable", False):
                with self.assertRaises(SchemaContractError, msg=fixture.name):
                    validate_new_write(document["schema"], document["value"])
                refused += 1
        self.assertTrue(refused, "no fixture exercises the read/write asymmetry")

    def test_the_pipeline_this_repository_ships_is_canonical(self) -> None:
        """A pipeline the repository hands a user must pass the writer, not merely the reader.

        The demo workspace is the only one: `/data/pipeline.yml` is gitignored working state that
        exists on a maintainer's machine and not in a checkout, so asserting on it would pass
        locally and fail in CI. And only pipelines -- `examples/demo-workspace/*.example.yml` are
        matching-simulator inputs despite their names, not CANDIDATE_PROFILE and COMPANY_PROFILE
        documents, so validating them against those schemas would assert a shape nothing produces.
        """
        path = ROOT / "examples" / "demo-workspace" / "data" / "pipeline.yml"
        validate_new_write("PIPELINE", yaml.safe_load(path.read_text(encoding="utf-8")))


class ProducerContractTests(unittest.TestCase):
    """Each producer with a Python write path: run it, validate the write, then read it back.

    Validating a producer's output alone would only prove it matches the schema. The consumer leg is
    what proves the schema describes the thing the consumer actually reads -- a producer and a
    consumer can agree with a schema and still disagree with each other.
    """

    def test_pipeline_store_upsert_produces_a_document_the_status_bar_can_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline.yml"
            pipeline_store.upsert_company(path, "aozora", {
                "name": "Aozora Systems", "stage": 3, "decision_status": "review",
                "match_model_version": "evidence_based_v3", "next_action": "一次面接の準備",
                "deadline": "2026-09-01",
                "jd_requirements": [{"text": "Kubernetes", "kind": "required", "status": "Unknown"}],
            })
            written = pipeline_store.load(path)
            validate_new_write("PIPELINE", written)

            sys.path.insert(0, str(ROOT / "scripts"))
            import datetime as dt  # noqa: PLC0415

            import status_bar  # noqa: PLC0415

            block = status_bar.build_status(written, {"rules": []}, dt.date(2026, 8, 11))
            self.assertIn("Aozora Systems", block)

    def test_a_frozen_field_is_refused_for_being_frozen_and_not_for_being_unknown(self) -> None:
        """Five of the seven frozen score fields are deliberately absent from the schema, so an
        unknown-key check running first would answer a caller still writing `overall_score` with
        "unknown field" -- true, but not the reason, and not what to write instead."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline.yml"
            for field in ("overall_score", "match_score"):
                with self.subTest(field=field):
                    with self.assertRaises(ValueError) as caught:
                        pipeline_store.upsert_company(path, "a", {"name": "A", field: 80})
                    self.assertIn("legacy_v1 fields are frozen", str(caught.exception))

    def test_pipeline_store_refuses_a_field_the_schema_does_not_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline.yml"
            with self.assertRaises(ValueError) as caught:
                pipeline_store.upsert_company(path, "aozora", {"name": "A", "decison_status": "proceed"})
            self.assertIn("decison_status", str(caught.exception))
            self.assertFalse(path.exists(), "a refused write must not create the file")

    def test_calibrate_produces_a_rules_file_that_validates(self) -> None:
        """The writer whose output never matched its own schema until this release."""
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            data = workspace / "data"
            data.mkdir()
            (data / "pipeline.yml").write_text(
                yaml.safe_dump({"companies": [
                    {"slug": "a-corp", "name": "A", "closed": True, "root_cause": "数値なしエピソード",
                     "feedback_obtained": True, "reached_stage": 3},
                    {"slug": "b-corp", "name": "B", "closed": True, "root_cause": "数値なしエピソード",
                     "feedback_obtained": True, "reached_stage": 2},
                ]}, allow_unicode=True),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "calibrate.py"), "rules",
                 "--approve", "数値なしエピソード", "--text", "エピソードに必ず数値を入れる",
                 "--workspace", str(workspace)],
                capture_output=True, text=True, encoding="utf-8", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            written = yaml.safe_load((data / "rules.yml").read_text(encoding="utf-8"))
            validate_new_write("RULES", written)
            self.assertEqual(written["rules"][0]["source"], "observed_workflow")

            # The consumer leg: status_bar is what re-surfaces a rule before an interview, and it
            # reads the mapping shape the schema was wrong about until this release.
            sys.path.insert(0, str(ROOT / "scripts"))
            import datetime as dt  # noqa: PLC0415

            import status_bar  # noqa: PLC0415

            pipeline = yaml.safe_load((data / "pipeline.yml").read_text(encoding="utf-8"))
            block = status_bar.build_status(pipeline, written, dt.date(2026, 8, 11))
            self.assertIn("エピソードに必ず数値を入れる", block)

    def test_the_career_agent_projects_a_strictly_valid_pipeline_entry(self) -> None:
        """The end of the real path: approve an event, then validate what landed on disk."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vault, workspace = root / "vault", root / "workspace"
            workspace.mkdir()
            agent = ROOT / "skills" / "career-agent" / "career_agent.py"

            def cli(*args: str) -> dict:
                result = subprocess.run(
                    [sys.executable, str(agent), *args, "--vault", str(vault)],
                    cwd=workspace, capture_output=True, text=True, encoding="utf-8", check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            cli("setup", "--track", "chuto", "--target-role", "SRE")
            proposed = cli("run", "--mode", "chat", "--message", "A社に面接を申し込んだ")
            cli("approve", proposed["proposal"]["id"], "--evidence", "面接申込完了", "--company", "A社")
            validate_new_write("PIPELINE", pipeline_store.load(workspace / "data" / "pipeline.yml"))


if __name__ == "__main__":
    unittest.main()
