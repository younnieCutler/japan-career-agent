"""Human domain vocabulary stays complete, namespaced, and out of machine contracts."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "skills" / "career-agent"
sys.path.insert(0, str(RUNTIME))

from gui._test_client import client_source  # noqa: E402
from guided import render_human as render_guided_human  # noqa: E402
from localization import (  # noqa: E402
    DOMAIN_ROWS,
    GUI_PRODUCT_TEXT,
    GUI_TEXT,
    UX_TEXT,
    artifact_kind_label,
    domain_label,
    effect_label,
    gui_catalog,
    validate_domain_catalog,
)
from models import (  # noqa: E402
    CAREER_MODES,
    CAREER_STATUSES,
    CHUTO_STAGES,
    CONTEXT_KINDS,
    EMPLOYMENT_STATUSES,
    EVENT_STATUSES,
    EXPERIENCE_CONTEXT_KINDS,
    EXPERIENCE_KINDS,
    EXTERNAL_USE_STATES,
    FACT_CATEGORIES,
    JOB_SEARCH_STATES,
    PROJECT_STATUSES,
    SHINSOTSU_STAGES,
    TRACKS,
    TRUSTED_SOURCE_TYPES,
    DecisionStatus,
    ProposalKind,
    ProposalStatus,
)
from ux import render_human as render_ux_human  # noqa: E402


class DomainVocabularyTests(unittest.TestCase):
    def test_material_human_vocabulary_namespaces_are_complete(self) -> None:
        required = {
            "ux_state": {"ready", "needs_input", "needs_confirmation", "review", "blocked", "completed", "recovery_required"},
            "fact_state": {"unknown", "confirmed", "conflict", "partial", "stale", "invalid"},
            "event_status": {"draft", "confirmed", "superseded"},
            "proposal_kind": {"event", "career_context", "heartbeat", "posting_candidates"},
            "proposal_status": {"pending", "approved", "rejected"},
            "decision": {"proceed", "review", "conflict"},
            "requirement": {"matched", "missing", "unknown", "required", "preferred"},
            "career_value": {"must_have", "preferred", "avoid", "aligned", "tradeoffs", "conflicts", "unknown"},
            "employment": {"employed", "unemployed", "student", "other", "unknown"},
            "job_search": {"on", "off"},
            "career_mode": {"maintenance", "opportunity_review", "active_search", "transition"},
            "career_status": {"onboarding", "active", "confirmed"},
            "project_status": {"active", "completed", "paused", "unknown"},
            "external_use": {"allowed", "blocked", "unknown"},
            "self_analysis_state": {"available", "unknown", "invalid", "reviewed", "reviewed_empty"},
            "readiness_dimension": {"recent_work_evidence", "project_history", "individual_contribution", "metrics_evidence", "career_contexts", "experience_coverage"},
            "weekly_gap": {"individual_contribution", "result", "metrics_evidence", "improvements", "learning"},
            "maintenance_suggestion": {"review_recent_project_activity", "project_ended_without_summary", "individual_contribution_unknown", "external_use_unreviewed"},
            "document_state": {"current", "superseded", "conflict", "not_yet_effective", "unknown_effective_date"},
            "candidate_segment": {"dai2_shinsotsu", "standard", "senior_ic", "management"},
            "visa_status": {"PR", "Engineer/Specialist", "Student"},
            "jlpt": {"native", "N1", "N2", "N3", "N4", "None"},
            "matching_availability": {"available", "unavailable", "insufficient_data", "unmapped"},
            "confidence": {"high", "medium", "low", "unknown"},
            "interest_source": {"self_report", "event_experience", "interview_experience"},
            "employer_signal": {"scout", "message", "interview_invite", "pass_notice", "rejection"},
            "portable_skill": {"current_state_assessment", "task_setting", "planning", "task_execution", "situational_response", "internal_coordination", "external_coordination", "manager_response", "subordinate_management"},
            "rule_status": {"candidate", "active", "retired"},
            "rule_source": {"self_authored", "derived_from_rejections", "observed_workflow"},
            "case_status": {"active", "archived", "deleted"},
            "artifact_status": {"current", "superseded", "deleted"},
            "session_stage": {"experience_evidence", "review", "completed", "tanaoroshi"},
            "session_status": {"draft", "review_pending", "completed", "archived"},
            "workflow": {"career_inventory", "self_analysis", "application"},
            "status_stage": {str(index) for index in range(8)},
            "model_version": {"evidence_based_v3", "legacy_v1"},
        }
        for namespace, values in required.items():
            with self.subTest(namespace=namespace):
                normalized = {str(value).strip().casefold().replace(" ", "_") for value in values}
                self.assertEqual(sorted(normalized - set(DOMAIN_ROWS[namespace])), [])

    def test_catalog_covers_every_model_owned_enum(self) -> None:
        expected = {
            "track": TRACKS,
            "event_status": EVENT_STATUSES,
            "proposal_kind": {item.value for item in ProposalKind},
            "proposal_status": {item.value for item in ProposalStatus},
            "decision": {item.value for item in DecisionStatus},
            "career_status": CAREER_STATUSES,
            "project_status": PROJECT_STATUSES,
            "context_kind": EXPERIENCE_CONTEXT_KINDS,
            "experience_kind": EXPERIENCE_KINDS,
            "employment": EMPLOYMENT_STATUSES,
            "job_search": JOB_SEARCH_STATES,
            "career_mode": CAREER_MODES,
            "external_use": EXTERNAL_USE_STATES,
            "fact_category": FACT_CATEGORIES,
            "context_note_kind": CONTEXT_KINDS,
            "context_source_type": TRUSTED_SOURCE_TYPES,
            "pipeline_stage": {*SHINSOTSU_STAGES, *CHUTO_STAGES},
        }
        self.assertEqual(validate_domain_catalog(), [])
        for namespace, values in expected.items():
            with self.subTest(namespace=namespace):
                normalized = {str(value).casefold().replace(" ", "_") for value in values}
                self.assertEqual(sorted(normalized - set(DOMAIN_ROWS[namespace])), [])

    def test_same_token_has_namespace_specific_meaning(self) -> None:
        self.assertEqual(domain_label("ko", "career_status", "active"), "사용 중")
        self.assertEqual(domain_label("ko", "project_status", "active"), "진행 중")
        self.assertEqual(domain_label("ko", "rule_status", "active"), "적용 중")
        self.assertEqual(domain_label("ja", "external_use", "blocked"), "外部利用不可")
        self.assertEqual(domain_label("ja", "ux_state", "blocked"), "実行できません")
        self.assertEqual(domain_label("ko", "fact_state", "confirmed"), "확인됨")
        self.assertEqual(domain_label("ko", "event_status", "confirmed"), "확정됨")

    def test_case_variants_share_display_semantics_without_changing_values(self) -> None:
        self.assertEqual(domain_label("ko", "fact_state", "Unknown"), "확인되지 않음")
        self.assertEqual(domain_label("ja", "fact_state", "Conflict"), "情報の矛盾")
        self.assertEqual(domain_label("ko", "fact_state", "Partial"), "일부 확인")
        self.assertEqual(domain_label("ja", "fact_state", "Stale"), "要再確認")

    def test_missing_human_labels_fail_instead_of_leaking_raw_tokens(self) -> None:
        with self.assertRaisesRegex(KeyError, "missing domain translation"):
            domain_label("ko", "decision", "internal_future_state")
        with self.assertRaises(KeyError):
            effect_label("ko", "unregistered internal effect")
        self.assertEqual(artifact_kind_label("ko", "vendor_generated_blob"), "기타 산출물")

    def test_korean_and_japanese_human_copy_does_not_leak_internal_vocabulary(self) -> None:
        forbidden = (
            "Unknown", "Conflict", "shinsotsu", "chuto", "needs_confirmation",
            "profile.", "career-profile.toml", "--proposal-id", "proposal_id",
            "event_id", "artifact_id", "case_id", "ledger_written", "state_written",
            "projection_written",
        )
        for table in (GUI_TEXT, GUI_PRODUCT_TEXT, UX_TEXT):
            for language in ("ko", "ja"):
                for key, value in table[language].items():
                    with self.subTest(language=language, key=key):
                        self.assertFalse(any(token in value for token in forbidden), value)

    def test_human_domain_details_hide_ids_and_raw_keys(self) -> None:
        cases = (
            (
                {
                    "mode": "readiness",
                    "dimensions": {"recent_work_evidence": "Unknown"},
                    "ux": {"language": "ko", "state": "review", "summary": "검토가 필요합니다."},
                },
                ("최근 업무 근거", "확인되지 않음"),
                ("recent_work_evidence", "Unknown"),
            ),
            (
                {
                    "mode": "weekly-review",
                    "groups": [{"title": "최근 경험", "events": [{"event_id": "event-secret", "title": "배포", "status": "confirmed", "gaps": ["metrics_evidence"]}]}],
                    "ux": {"language": "ko", "state": "review", "summary": "검토가 필요합니다."},
                },
                ("확정됨", "수치의 근거"),
                ("event-secret", "metrics_evidence"),
            ),
            (
                {
                    "mode": "proposals",
                    "proposals": [{"proposal_id": "proposal-secret", "kind": "event", "status": "pending"}],
                    "ux": {"language": "ja", "state": "needs_confirmation", "summary": "確認してください。"},
                },
                ("キャリア記録", "確認待ち"),
                ("proposal-secret", "pending"),
            ),
        )
        for payload, expected, hidden in cases:
            rendered = render_ux_human(payload)
            for value in expected:
                self.assertIn(value, rendered)
            for value in hidden:
                self.assertNotIn(value, rendered)

    def test_unknown_guided_blocker_uses_a_safe_user_sentence(self) -> None:
        rendered = render_guided_human(
            {
                "guided": {
                    "state": "blocked",
                    "summary": {
                        "language": "ko", "track": "chuto", "setup_complete": True,
                        "major_blockers": ["INTERNAL_FUTURE_BLOCKER"],
                    },
                    "available_actions": [],
                },
                "ux": {
                    "language": "ko", "state": "blocked", "summary": "진행할 수 없습니다.",
                    "reason": {"message": "현재 작업은 진행할 수 없습니다."},
                },
            }
        )
        self.assertIn("현재 작업은 진행할 수 없습니다.", rendered)
        self.assertNotIn("INTERNAL_FUTURE_BLOCKER", rendered)

    def test_gui_catalog_uses_the_same_domain_labels_and_all_context_choices(self) -> None:
        for language in ("ko", "ja", "en"):
            catalog = gui_catalog(language)
            for kind in EXPERIENCE_CONTEXT_KINDS:
                self.assertEqual(
                    catalog[f"enum.context_kind.{kind}"],
                    domain_label(language, "context_kind", kind),
                )
        # The context picker lives with the career records now; assert against the whole shipped
        # client so a move cannot silently drop a choice the domain still defines.
        client = client_source()
        for kind in EXPERIENCE_CONTEXT_KINDS:
            self.assertIn(f'"{kind}"', client)

    def test_human_guided_output_translates_track_but_json_keeps_canonical(self) -> None:
        script = RUNTIME / "career_agent.py"
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory) / "vault"
            setup = subprocess.run(
                [sys.executable, str(script), "setup", "--vault", str(vault), "--track", "chuto", "--language", "ko"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(setup.returncode, 0, setup.stderr)
            machine = subprocess.run(
                [sys.executable, str(script), "guided", "--vault", str(vault), "--format", "json"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            human = subprocess.run(
                [sys.executable, str(script), "guided", "--vault", str(vault), "--format", "human"],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(json.loads(machine.stdout)["guided"]["summary"]["track"], "chuto")
            self.assertIn("경력채용", human.stdout)
            self.assertNotIn("chuto", human.stdout)


if __name__ == "__main__":
    unittest.main()
