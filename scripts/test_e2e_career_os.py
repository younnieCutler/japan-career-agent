#!/usr/bin/env python3
"""The v2.0.0 release gate: one lifecycle, end to end, through the real CLI.

    install -> vault -> 棚卸し -> canonical evidence -> target JD -> evidence selection
    -> document model -> Japanese draft -> humanize -> fidelity gate -> template -> HTML

Every other test file covers one layer. This one covers the seams between them, which is where a
lifecycle actually breaks: a model built from a real ledger rather than a fixture, a selection
written by the real pipeline writer, a document rendered from the real templates.

Two invariants run through all of it. Career facts are identical no matter which target asked for
them, and generating documents never changes the record — asserted here by hashing the ledger
before and after, because "a document is a projection, not a source" is otherwise just a sentence.

All fixture content is synthetic; no real personal data appears in this file.

    synthetic://test-fixtures
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "skills" / "career-agent" / "career_agent.py"
PIPELINE = ROOT / "scripts" / "pipeline.py"


class Lifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault = str(self.root / "vault")
        self.workspace = self.root / "workspace"
        (self.workspace / "data").mkdir(parents=True)
        self.cli("setup", "--vault", self.vault, "--track", "chuto")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -- plumbing -----------------------------------------------------------------

    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI), *args], capture_output=True, text=True,
            encoding="utf-8", cwd=str(cwd or self.root),
        )

    def cli(self, *args: str, cwd: Path | None = None) -> dict:
        done = self.run_cli(*args, cwd=cwd)
        if done.returncode not in (0, 2):
            raise AssertionError(f"{args}\n{done.stdout}\n{done.stderr}")
        return json.loads(done.stdout or done.stderr)

    def pipeline(self, slug: str, payload: dict) -> None:
        done = subprocess.run(
            [
                sys.executable, str(PIPELINE), "--path",
                str(self.workspace / "data" / "pipeline.yml"), "upsert", slug,
                "--json", json.dumps(payload, ensure_ascii=False),
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        if done.returncode != 0:
            raise AssertionError(f"{slug}\n{done.stdout}\n{done.stderr}")

    def ledger_digest(self) -> str:
        path = Path(self.vault, "02-state", "events.jsonl")
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""

    def write(self, name: str, payload: dict) -> str:
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(path)

    # -- lifecycle steps ----------------------------------------------------------

    def add_context(self, kind: str, label: str, *extra: str) -> str:
        proposed = self.cli("add-context", label, "--kind", kind, "--vault", self.vault, *extra)
        self.cli("approve", proposed["proposal"]["id"], "--vault", self.vault, "--evidence", "書類")
        return proposed["context"]["id"]

    def capture(
        self, message: str, payload: dict, evidence: str = "記録", non_work: bool = False,
    ) -> str:
        flags = ["--non-work"] if non_work else []
        proposed = self.cli(
            "run", "--mode", "chat", "--vault", self.vault, *flags,
            "--message", message if non_work else f"{message} 업무일지 남겨줘",
        )
        proposal_id = proposed["proposal"]["id"]
        self.cli(
            "review-work-event", proposal_id, "--vault", self.vault,
            "--json", json.dumps(payload, ensure_ascii=False),
        )
        return self.cli(
            "approve", proposal_id, "--vault", self.vault, "--evidence", evidence
        )["event"]["id"]

    def build_career(self) -> dict[str, str]:
        """A career spanning an employer and a university, with project and non-project work."""
        company = self.add_context(
            "company", "内部決済A社", "--external-label", "決済系企業", "--from", "2022-04",
        )
        university = self.add_context("university", "○○大学", "--from", "2018-04", "--to", "2022-03")
        project = self.cli("add-project", "Phoenix", "--vault", self.vault,
                           "--external-label", "決済基盤刷新")
        self.cli("approve", project["proposal"]["id"], "--vault", self.vault, "--evidence", "社内資料")
        project_id = project["project"]["id"]
        return {
            "company": company,
            "university": university,
            "project": project_id,
            "deploy": self.capture(
                "GitHub Actionsで手動デプロイを自動化した。",
                {
                    "role": "支援", "individual_contribution": "手動デプロイの自動化",
                    "team_result": "リリース頻度が向上", "context_id": company,
                    "primary_project_id": project_id, "experience_kind": "project",
                },
                evidence="PR #123",
            ),
            "incident": self.capture(
                "決済障害でアラート条件を見直し runbook を更新した。",
                {
                    "role": "参加", "individual_contribution": "runbook の更新",
                    "context_id": company, "experience_kind": "incident",
                    "experience_ref": "決済障害対応",
                },
                evidence="インシデントチケット INC-9",
            ),
            "secret": self.capture(
                "社内システムの移行手順を作成した。",
                {
                    "individual_contribution": "移行手順の作成", "context_id": company,
                    "experience_kind": "improvement", "experience_ref": "社内移行",
                    "confidentiality": {"contains_confidential": True, "external_use": "unknown"},
                },
                evidence="社内Wiki",
            ),
            "thesis": self.capture(
                "卒業研究で計測スクリプトを実装した。",
                {
                    "role": "ゼミ長", "individual_contribution": "計測スクリプトの実装",
                    "context_id": university, "experience_kind": "research",
                    "experience_ref": "卒業研究",
                },
                evidence="研究発表資料",
                non_work=True,
            ),
        }

    def model_for(self, slug: str, name: str, **selection) -> dict:
        self.pipeline(slug, {"name": name, **selection})
        model = self.cli(
            "document-model", slug, "--vault", self.vault, "--workspace", str(self.workspace),
        )
        return model


class GateA_HistoricalBootstrap(Lifecycle):
    """棚卸し: contexts, experiences and evidence recovered from before the ledger existed."""

    def test_an_empty_vault_says_it_has_nothing_to_quote(self) -> None:
        report = self.cli("readiness", "--vault", self.vault)
        self.assertTrue(report["bootstrap_suggested"])
        self.assertTrue(report["no_total_by_design"])

    def test_it_is_independent_of_job_search_intent(self) -> None:
        self.cli("set-employment-status", "employed", "--vault", self.vault)
        self.cli("set-job-search", "off", "--vault", self.vault)
        self.assertTrue(self.cli("readiness", "--vault", self.vault)["bootstrap_suggested"])

    def test_a_company_and_a_university_are_both_contexts(self) -> None:
        self.build_career()
        contexts = self.cli("contexts", "--vault", self.vault)
        self.assertEqual(
            sorted(row["kind"] for row in contexts["contexts"]), ["company", "university"]
        )

    def test_a_new_graduate_records_evidence_without_a_job(self) -> None:
        ids = self.build_career()
        view = self.cli("experiences", "--vault", self.vault, "--context", ids["university"])
        self.assertEqual([row["experience_id"] for row in view["experiences"]], ["ref:卒業研究"])
        self.assertEqual(view["experiences"][0]["kind"], "research")
        # The reason the two types are separate: a seminar recorded as a work event would say the
        # user was employed at their university, and every work-scoped read would agree.
        ledger = [
            json.loads(line)
            for line in Path(self.vault, "02-state", "events.jsonl").read_text(
                encoding="utf-8"
            ).splitlines() if line.strip()
        ]
        thesis = next(row for row in ledger if row["id"] == ids["thesis"])
        self.assertEqual(thesis["type"], "experience_event")
        self.assertNotIn("work_event", thesis)
        self.assertEqual(thesis["experience"]["individual_contribution"], "計測スクリプトの実装")

    def test_a_thesis_never_needs_a_track_or_a_stage(self) -> None:
        ids = self.build_career()
        state = self.cli("status", "--vault", self.vault)
        self.assertIsNotNone(ids["thesis"])
        self.assertIsNone(state["state"]["stage"])

    def test_non_work_evidence_is_selectable_for_a_document(self) -> None:
        ids = self.build_career()
        model = self.model_for("corp-a", "Corp A", primary_experience_ids=[ids["thesis"]])
        self.assertEqual([e["evidence_id"] for e in model["entries"]], [ids["thesis"]])
        self.assertEqual(model["employment_history"][0]["kind"], "university")

    def test_project_and_non_project_work_both_become_experiences(self) -> None:
        ids = self.build_career()
        view = self.cli("experiences", "--vault", self.vault)
        kinds = {row["kind"] for row in view["experiences"]}
        self.assertIn("project", kinds)
        self.assertIn("incident", kinds)
        self.assertIn(f"project:{ids['project']}", [r["experience_id"] for r in view["experiences"]])

    def test_a_rejected_proposal_leaves_the_ledger_untouched(self) -> None:
        self.build_career()
        before = self.ledger_digest()
        self.cli("add-context", "会社B", "--kind", "company", "--vault", self.vault)
        self.assertEqual(self.ledger_digest(), before)

    def test_a_number_without_a_source_cannot_be_confirmed(self) -> None:
        proposed = self.cli(
            "run", "--mode", "chat", "--vault", self.vault,
            "--message", "バッチ処理を30%高速化した。업무일지 남겨줘",
        )
        result = self.cli(
            "approve", proposed["proposal"]["id"], "--vault", self.vault, "--evidence", "記憶",
        )
        self.assertFalse(result.get("ok", True))


class GateB_JDProjection(Lifecycle):
    """One career, several targets: the lens moves and the facts do not."""

    def setUp(self) -> None:
        super().setUp()
        self.ids = self.build_career()

    def test_two_targets_select_different_evidence(self) -> None:
        a = self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]])
        b = self.model_for("corp-b", "Corp B", primary_experience_ids=[self.ids["incident"]])
        self.assertEqual([e["evidence_id"] for e in a["entries"]], [self.ids["deploy"]])
        self.assertEqual([e["evidence_id"] for e in b["entries"]], [self.ids["incident"]])

    def test_the_employer_period_and_role_are_identical_in_both(self) -> None:
        a = self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]])
        b = self.model_for(
            "corp-b", "Corp B",
            primary_experience_ids=[self.ids["incident"]],
            supporting_experience_ids=[self.ids["deploy"]],
        )
        deploy_a = next(e for e in a["entries"] if e["evidence_id"] == self.ids["deploy"])
        deploy_b = next(e for e in b["entries"] if e["evidence_id"] == self.ids["deploy"])
        for claim in ("employer", "period", "role", "individual_contribution", "team_result"):
            with self.subTest(claim=claim):
                self.assertEqual(
                    deploy_a["protected_claims"][claim], deploy_b["protected_claims"][claim]
                )

    def test_an_unsupported_requirement_stays_unknown(self) -> None:
        model = self.model_for(
            "corp-a", "Corp A",
            primary_experience_ids=[self.ids["deploy"]],
            jd_requirements=[
                {"text": "CI/CD automation", "kind": "required", "status": "Matched",
                 "evidence_ids": [self.ids["deploy"]]},
                {"text": "large-scale Kubernetes", "kind": "preferred", "status": "Unknown"},
            ],
        )
        self.assertIn("large-scale Kubernetes", model["unknowns"])
        self.assertNotIn("Kubernetes", [s["label"] for s in model["skills"]])

    def test_unreviewed_confidential_evidence_never_enters_a_document(self) -> None:
        model = self.model_for(
            "corp-a", "Corp A", primary_experience_ids=[self.ids["secret"]],
        )
        self.assertEqual(model["entries"], [])
        self.assertEqual(model["excluded"][0]["evidence_id"], self.ids["secret"])

    def test_the_recruiter_facing_name_replaces_the_internal_one(self) -> None:
        model = self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]])
        self.assertEqual(model["entries"][0]["heading"], "決済基盤刷新")
        self.assertEqual(model["employment_history"][0]["label"], "決済系企業")
        self.assertIn("内部決済A社", model["internal_labels"])

    def test_generating_repeatedly_leaves_the_record_byte_identical(self) -> None:
        before = self.ledger_digest()
        for index in range(10):
            self.model_for(f"corp-{index}", f"Corp {index}",
                           primary_experience_ids=[self.ids["deploy"]])
        self.assertEqual(self.ledger_digest(), before)


class GateC_FidelityGate(Lifecycle):
    """Polished Japanese may say less than the evidence, never more."""

    def setUp(self) -> None:
        super().setUp()
        self.ids = self.build_career()
        self.model = self.write(
            "model.json",
            self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]]),
        )

    def check(self, slots: dict, humanized: dict | None = None) -> dict:
        args = ["document-check", "--model", self.model, "--draft", self.write("draft.json", {"slots": slots})]
        if humanized is not None:
            args += ["--humanized", self.write("humanized.json", {"slots": humanized})]
        return self.cli(*args)

    def entry(self, text: str) -> dict:
        return {f"entry:{self.ids['deploy']}": text}

    def test_evidence_grounded_japanese_passes(self) -> None:
        result = self.check(self.entry("GitHub Actionsで手動デプロイを自動化。"))
        self.assertTrue(result["pass"], result["violations"])
        self.assertEqual(result["factual_drift"], 0)

    def test_support_does_not_become_leadership(self) -> None:
        result = self.check(self.entry("デプロイ自動化を主導。"))
        self.assertIn("role_escalation", {v["rule"] for v in result["violations"]})

    def test_a_number_is_never_created(self) -> None:
        result = self.check(self.entry("デプロイ時間を50%短縮。"))
        self.assertIn("unsupported_metric", {v["rule"] for v in result["violations"]})

    def test_a_jd_keyword_is_never_promoted_to_a_technology(self) -> None:
        result = self.check(self.entry("DevOps基盤を担当。"))
        self.assertIn("unsupported_technology", {v["rule"] for v in result["violations"]})

    def test_an_internal_project_name_never_leaves(self) -> None:
        result = self.check(self.entry("Phoenixのデプロイを自動化。"))
        self.assertIn("confidentiality_bypass", {v["rule"] for v in result["violations"]})

    def test_a_team_outcome_needs_its_attribution(self) -> None:
        result = self.check({"section:self_pr": "リリース頻度が向上しました。"})
        self.assertIn("team_result_as_individual", {v["rule"] for v in result["violations"]})

    def test_polishing_may_improve_wording(self) -> None:
        before = self.entry("GitHub Actionsを活用することで、デプロイの効率化を実現しました。")
        after = self.entry("GitHub Actionsで手動デプロイを自動化。")
        self.assertTrue(self.check(before, humanized=after)["pass"])

    def test_polishing_may_not_strengthen_a_claim(self) -> None:
        before = self.entry("GitHub Actionsで手動デプロイを自動化。")
        after = self.entry("GitHub Actionsによる自動化を主導。")
        result = self.check(before, humanized=after)
        self.assertIn("role_escalation", {v["rule"] for v in result["violations"]})

    def test_polishing_may_not_merge_the_bullets(self) -> None:
        before = self.entry("GitHub Actionsで自動化。\n手順を文書化。")
        after = self.entry("GitHub Actionsで自動化し、手順を文書化しました。")
        result = self.check(before, humanized=after)
        self.assertIn("structure_changed", {v["rule"] for v in result["violations"]})

    def test_the_same_input_always_produces_the_same_verdict(self) -> None:
        slots = self.entry("DevOps基盤を主導し、50%短縮。")
        runs = [self.check(slots) for _ in range(3)]
        for run in runs[1:]:
            self.assertEqual(run["violations"], runs[0]["violations"])


class GateD_TemplateRendering(Lifecycle):
    """A template changes presentation and nothing else, and never overwrites."""

    def setUp(self) -> None:
        super().setUp()
        self.ids = self.build_career()
        self.model = self.write(
            "model.json",
            self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]]),
        )
        self.draft = self.write("draft.json", {"slots": {
            f"entry:{self.ids['deploy']}": "GitHub Actionsで手動デプロイを自動化。",
            "section:summary": "決済系企業でデプロイ改善を担当。",
        }})

    def render(self, template: str = "standard-chuto") -> dict:
        return self.cli(
            "document-render", "--model", self.model, "--draft", self.draft,
            "--template", template, "--out", "./career-docs",
        )

    def visible(self, path: str) -> str:
        import re
        markup = Path(path).read_text(encoding="utf-8")
        markup = re.sub(r"<style.*?</style>|<!--.*?-->", " ", markup, flags=re.DOTALL)
        return " ".join(re.sub(r"<[^>]+>", " ", markup).split())

    def test_a_checked_document_renders(self) -> None:
        result = self.render()
        self.assertTrue(result["ok"])
        self.assertTrue(Path(result["output_path"]).is_file())
        self.assertTrue(Path(result["manifest_path"]).is_file())

    def test_both_templates_state_the_same_facts(self) -> None:
        standard = self.visible(self.render("standard-chuto")["output_path"])
        simple = self.visible(self.render("simple-print")["output_path"])
        for fact in ("決済系企業", "決済基盤刷新", "GitHub Actionsで手動デプロイを自動化。", "2022-04"):
            with self.subTest(fact=fact):
                self.assertIn(fact, standard)
                self.assertIn(fact, simple)

    def test_neither_template_leaks_the_internal_name(self) -> None:
        for template in ("standard-chuto", "simple-print"):
            with self.subTest(template=template):
                text = self.visible(self.render(template)["output_path"])
                self.assertNotIn("内部決済A社", text)
                self.assertNotIn("Phoenix", text)

    def test_regenerating_unchanged_writes_nothing(self) -> None:
        self.render()
        self.assertTrue(self.render()["unchanged"])

    def test_a_different_template_lands_beside_the_first(self) -> None:
        first = self.render("standard-chuto")
        second = self.render("simple-print")
        self.assertNotEqual(first["output_path"], second["output_path"])
        self.assertTrue(Path(first["output_path"]).is_file())

    def test_a_failing_document_is_never_written(self) -> None:
        bad = self.write("bad.json", {"slots": {
            f"entry:{self.ids['deploy']}": "デプロイ自動化を主導し、50%短縮。",
        }})
        result = self.cli(
            "document-render", "--model", self.model, "--draft", bad,
            "--template", "standard-chuto", "--out", "./career-docs",
        )
        self.assertEqual(result["error_code"], "FIDELITY_GATE_FAILED")
        self.assertFalse((self.root / "career-docs").exists())

    def test_new_evidence_marks_an_existing_document_outdated(self) -> None:
        self.render()
        self.capture(
            "手順を標準化した。",
            {"individual_contribution": "手順の標準化", "context_id": self.ids["company"],
             "experience_kind": "improvement", "experience_ref": "標準化"},
        )
        refreshed = self.write(
            "model2.json",
            self.model_for("corp-a", "Corp A", primary_experience_ids=[self.ids["deploy"]]),
        )
        result = self.cli(
            "document-render", "--model", refreshed, "--draft", self.draft,
            "--template", "standard-chuto", "--out", "./career-docs",
        )
        self.assertTrue(result["outdated_documents"])

    def test_rendering_never_touches_the_record(self) -> None:
        before = self.ledger_digest()
        for template in ("standard-chuto", "simple-print", "standard-chuto"):
            self.render(template)
        self.assertEqual(self.ledger_digest(), before)


class GateE_Compatibility(Lifecycle):
    """Everything that worked in 1.24.0 still works, and still means what it meant."""

    def setUp(self) -> None:
        super().setUp()
        self.ids = self.build_career()

    def test_work_events_still_reads_confirmed_work(self) -> None:
        events = self.cli("work-events", "--confirmed", "--vault", self.vault)
        self.assertEqual(events["count"], 3)
        self.assertTrue(all(row["type"] == "work_event" for row in events["work_events"]))

    def test_projects_and_timelines_still_work(self) -> None:
        projects = self.cli("projects", "--vault", self.vault)
        self.assertEqual(projects["count"], 1)
        timeline = self.cli("project-timeline", self.ids["project"], "--vault", self.vault)
        self.assertEqual([row["event_id"] for row in timeline["timeline"]], [self.ids["deploy"]])

    def test_the_evidence_pool_a_jd_mapping_starts_from_still_works(self) -> None:
        pool = self.cli("evidence-pool", "--vault", self.vault)
        self.assertTrue(pool["ok"])

    def test_the_weekly_review_still_works(self) -> None:
        self.assertTrue(self.cli("weekly-review", "--vault", self.vault)["ok"])

    def test_readiness_keeps_its_original_dimensions(self) -> None:
        dimensions = self.cli("readiness", "--vault", self.vault)["dimensions"]
        for original in (
            "recent_work_evidence", "project_history", "individual_contribution", "metrics_evidence",
        ):
            self.assertIn(original, dimensions)

    def test_the_vault_still_passes_its_own_doctor(self) -> None:
        report = self.cli("doctor", "--vault", self.vault)
        self.assertEqual(report.get("errors"), [])

    def test_a_thesis_never_appears_as_work_history(self) -> None:
        # The reason the two types are separate. `work-events` is what career-maintenance,
        # weekly-review and the recency dimension all read; coursework in it would be employment.
        events = self.cli("work-events", "--confirmed", "--vault", self.vault)
        recorded = {row["id"] for row in events["work_events"]}
        self.assertNotIn(self.ids["thesis"], recorded)
        self.assertTrue(all(row["type"] == "work_event" for row in events["work_events"]))

    def test_the_thesis_is_still_evidence_everywhere_it_should_be(self) -> None:
        experiences = self.cli("experiences", "--vault", self.vault)
        self.assertIn("ref:卒業研究", [row["experience_id"] for row in experiences["experiences"]])
        self.assertEqual(
            self.cli("readiness", "--vault", self.vault)["counts"]["career_contexts"], 2
        )

    def test_no_command_here_writes_a_composite_score(self) -> None:
        for command in ("readiness", "experiences", "contexts"):
            with self.subTest(command=command):
                payload = json.dumps(self.cli(command, "--vault", self.vault))
                self.assertNotIn("score", payload)
                self.assertNotIn("readiness_total", payload)


if __name__ == "__main__":
    unittest.main(verbosity=1)
