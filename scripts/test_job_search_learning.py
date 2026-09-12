#!/usr/bin/env python3
"""Regression tests for application-level Job Search Learning Loop v1."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "_shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import application_learning as learning  # noqa: E402
import pipeline_store  # noqa: E402


def workspace() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory()


def begin(
    root: Path,
    slug: str,
    position: str,
    *,
    company: str | None = None,
    role: str | None = None,
    channel: str = "direct",
    day: str = "2026-09-01",
    stage: int = 2,
    application_id: str | None = None,
) -> dict:
    return learning.begin_application(
        workspace=root,
        company_slug=slug,
        company_name=company or slug,
        position_title=position,
        role_family=role,
        channel=channel,
        opened_at=day,
        stage=stage,
        application_id=application_id,
    )


def observe_and_confirm(
    root: Path,
    app_id: str,
    *,
    kind: str,
    theme: str,
    text: str | None = None,
    observed_at: str = "2026-09-10T10:00:00+09:00",
    stage: int = 4,
) -> tuple[dict, dict]:
    observation = learning.add_observation(
        workspace=root,
        application_id=app_id,
        kind=kind,
        text=text or theme,
        observed_at=observed_at,
        source_ref="test:feedback",
        stage=stage,
    )
    classification = learning.classify_observation(
        workspace=root,
        application_id=app_id,
        observation_id=observation["id"],
        theme=theme,
        state="confirmed",
        source="user",
        classified_at=observed_at,
    )
    return observation, classification


def close(root: Path, app_id: str, *, stage: int = 4, day: str = "2026-09-10") -> dict:
    return learning.close_application(
        workspace=root,
        application_id=app_id,
        closed_reason="rejection",
        closed_at=day,
        reached_stage=stage,
    )


def test_same_company_reapplication_is_distinct_and_resets_projection_stage() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        first = begin(root, "acme", "QA Engineer", role="QA", stage=4, application_id="app-acme-1")
        close(root, first["id"], stage=5)
        second = begin(
            root,
            "acme",
            "SDET",
            role="QA Automation",
            day="2026-10-01",
            stage=2,
            application_id="app-acme-2",
        )
        assert first["id"] != second["id"]
        data = learning.load_store(learning.applications_path(root))
        assert len(data["applications"]) == 2
        assert data["applications"][0]["reached_stage"] == 5
        pipeline = pipeline_store.load(learning.pipeline_path(root))
        entry = pipeline["companies"][0]
        assert entry["stage"] == 2, entry
        assert entry["closed"] is False
        assert "closed_reason" not in entry
        assert "reached_stage" not in entry


def test_begin_resets_old_application_scoped_matching_state() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        first = begin(root, "acme", "SRE", stage=3, application_id="app-1")
        pipeline_store.update_company(
            learning.pipeline_path(root),
            "acme",
            {
                "match_model_version": "evidence_based_v3",
                "decision_status": "review",
                "match_required_gaps": ["production operation"],
                "match_unknowns": ["people management"],
                "jd_digest": "old-digest",
            },
        )
        close(root, first["id"], stage=3)
        begin(root, "acme", "QA", day="2026-10-01", stage=1, application_id="app-2")
        entry = pipeline_store.load(learning.pipeline_path(root))["companies"][0]
        for field in (
            "match_model_version",
            "decision_status",
            "match_required_gaps",
            "match_unknowns",
            "jd_digest",
        ):
            assert field not in entry, (field, entry)


def test_begin_rerun_preserves_progress_and_heals_missing_projection() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        app = begin(root, "acme", "SRE", role="SRE", stage=2, application_id="app-1")
        observation = learning.add_observation(
            workspace=root,
            application_id=app["id"],
            kind="candidate_observation",
            text="system design answer was rushed",
            observed_at="2026-09-03",
            source_ref="user:self-report",
            stage=3,
        )
        pipeline_store.update_company(
            learning.pipeline_path(root),
            "acme",
            {
                "stage": 4,
                "match_model_version": "evidence_based_v3",
                "decision_status": "review",
                "match_required_gaps": ["production operation"],
            },
        )

        rerun = begin(root, "acme", "SRE", role="SRE", stage=2, application_id="app-1")
        assert rerun["observations"][0]["id"] == observation["id"]
        entry = pipeline_store.load(learning.pipeline_path(root))["companies"][0]
        assert entry["stage"] == 4
        assert entry["match_required_gaps"] == ["production operation"]

        # If the second half of a cross-file begin was interrupted, rerunning begin can recreate
        # the missing current projection without duplicating or clearing the application history.
        learning.pipeline_path(root).unlink()
        healed = begin(root, "acme", "SRE", role="SRE", stage=2, application_id="app-1")
        assert healed["observations"][0]["id"] == observation["id"]
        entry = pipeline_store.load(learning.pipeline_path(root))["companies"][0]
        assert entry["stage"] == 2
        assert entry["channel"] == "direct"
        assert entry["closed"] is False


def test_close_freezes_matching_snapshot() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        app = begin(root, "acme", "SRE", role="SRE", stage=3, application_id="app-1")
        pipeline_store.update_company(
            learning.pipeline_path(root),
            "acme",
            {
                "match_model_version": "evidence_based_v3",
                "decision_status": "review",
                "match_required_gaps": ["production operation"],
                "match_unknowns": ["on-call ownership"],
                "match_conflicts": [],
                "jd_digest": "digest-1",
                "jd_requirements": [
                    {
                        "text": "production operation",
                        "kind": "required",
                        "status": "Missing",
                        "evidence_ids": [],
                    }
                ],
            },
        )
        outcome = close(root, app["id"], stage=3)
        assert outcome["match_snapshot"]["required_gaps"] == ["production operation"]
        assert outcome["match_snapshot"]["unknowns"] == ["on-call ownership"]
        assert outcome["match_snapshot"]["jd_digest"] == "digest-1"

        # A later application cannot rewrite the historical outcome snapshot.
        begin(root, "acme", "QA", day="2026-10-01", stage=1, application_id="app-2")
        data = learning.load_store(learning.applications_path(root))
        historical = next(one for one in data["applications"] if one["id"] == "app-1")
        assert historical["match_snapshot"]["required_gaps"] == ["production operation"]
        assert historical["match_snapshot"]["jd_digest"] == "digest-1"


def test_feedback_can_arrive_after_application_closes() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        app = begin(root, "acme", "SRE", application_id="app-1")
        close(root, app["id"], stage=4)
        observation, _ = observe_and_confirm(
            root,
            app["id"],
            kind="recruiter_feedback",
            theme="team leadership",
        )
        data = learning.load_store(learning.applications_path(root))
        closed = data["applications"][0]
        assert closed["closed_at"] == "2026-09-10"
        assert closed["observations"][0]["id"] == observation["id"]


def test_llm_theme_proposal_never_counts_without_user_confirmation() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b"), start=1):
            app = begin(root, slug, "SRE", application_id=f"app-{index}")
            observation = learning.add_observation(
                workspace=root,
                application_id=app["id"],
                kind="recruiter_feedback",
                text="leadership was insufficient",
                observed_at=f"2026-09-0{index}T10:00:00+09:00",
                source_ref=f"test:{slug}",
                stage=4,
            )
            learning.classify_observation(
                workspace=root,
                application_id=app["id"],
                observation_id=observation["id"],
                theme="team leadership",
                state="proposed",
                source="llm",
                classified_at=f"2026-09-0{index}T10:01:00+09:00",
            )
            close(root, app["id"], stage=4, day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        assert result["repeated_direct_feedback"] == []
        assert len(result["unknowns"]["direct_feedback_without_user_confirmed_theme"]) == 2


def test_llm_cannot_confirm_or_reject_theme() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        app = begin(root, "a", "SRE", application_id="app-1")
        observation = learning.add_observation(
            workspace=root,
            application_id=app["id"],
            kind="employer_feedback",
            text="leadership",
            observed_at="2026-09-01",
            source_ref="mail:1",
        )
        try:
            learning.classify_observation(
                workspace=root,
                application_id=app["id"],
                observation_id=observation["id"],
                theme="team leadership",
                state="confirmed",
                source="llm",
                classified_at="2026-09-01",
            )
        except ValueError as exc:
            assert "only the user" in str(exc)
        else:
            raise AssertionError("LLM confirmation must be rejected")


def test_latest_user_rejection_cancels_prior_theme_confirmation() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        first = begin(root, "a", "SRE", application_id="app-a")
        observation, _ = observe_and_confirm(
            root,
            first["id"],
            kind="employer_feedback",
            theme="team leadership",
            observed_at="2026-09-01T10:00:00+09:00",
        )
        learning.classify_observation(
            workspace=root,
            application_id=first["id"],
            observation_id=observation["id"],
            theme="TEAM   LEADERSHIP",
            state="rejected",
            source="user",
            classified_at="2026-09-01T10:05:00+09:00",
        )
        close(root, first["id"], stage=4, day="2026-09-01")

        second = begin(root, "b", "SRE", day="2026-09-02", application_id="app-b")
        observe_and_confirm(
            root,
            second["id"],
            kind="employer_feedback",
            theme="team leadership",
            observed_at="2026-09-02T10:00:00+09:00",
        )
        close(root, second["id"], stage=4, day="2026-09-02")

        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        assert result["repeated_direct_feedback"] == []
        assert "app-a" in result["unknowns"]["direct_feedback_without_user_confirmed_theme"]


def test_two_applications_same_employer_do_not_become_repeated_direct_feedback() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        first = begin(root, "acme", "SRE", application_id="app-1")
        observe_and_confirm(root, first["id"], kind="recruiter_feedback", theme="team leadership")
        close(root, first["id"])
        second = begin(
            root,
            "acme",
            "Engineering Manager",
            day="2026-10-01",
            application_id="app-2",
        )
        observe_and_confirm(
            root,
            second["id"],
            kind="recruiter_feedback",
            theme="team leadership",
            observed_at="2026-10-10T10:00:00+09:00",
        )
        close(root, second["id"], day="2026-10-10")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        assert result["repeated_direct_feedback"] == []


def test_two_distinct_employers_make_direct_feedback_review_eligible() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b"), start=1):
            app = begin(root, slug, "SRE", role="SRE", application_id=f"app-{index}")
            observe_and_confirm(
                root,
                app["id"],
                kind="recruiter_feedback",
                theme="team leadership",
                observed_at=f"2026-09-0{index}T10:00:00+09:00",
            )
            close(root, app["id"], day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        row = result["repeated_direct_feedback"][0]
        assert row["theme"] == "team leadership"
        assert row["distinct_employers"] == 2
        assert row["eligible_for_review"] is True
        assert row["role_scope"] == "SRE"
        assert result["automatic_rule_promotion"] is False


def test_recurring_match_gap_is_not_called_rejection_cause() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b"), start=1):
            app = begin(root, slug, "SRE", role="SRE", application_id=f"app-{index}")
            pipeline_store.update_company(
                learning.pipeline_path(root),
                slug,
                {
                    "match_model_version": "evidence_based_v3",
                    "decision_status": "review",
                    "match_required_gaps": ["production operation"],
                },
            )
            close(root, app["id"], stage=3, day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        row = result["recurring_diagnostic_gaps"][0]
        assert row["gap"] == "production operation"
        assert len(row["applications"]) == 2
        assert row["direct_feedback_support_applications"] == []
        assert row["causal_conclusion"] == "unknown"


def test_direct_feedback_can_support_same_gap_without_changing_causal_label() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b"), start=1):
            app = begin(root, slug, "SRE", role="SRE", application_id=f"app-{index}")
            pipeline_store.update_company(
                learning.pipeline_path(root),
                slug,
                {
                    "match_model_version": "evidence_based_v3",
                    "decision_status": "review",
                    "match_required_gaps": ["production operation"],
                },
            )
            observe_and_confirm(
                root,
                app["id"],
                kind="employer_feedback",
                theme="production operation",
                observed_at=f"2026-09-0{index}T10:00:00+09:00",
            )
            close(root, app["id"], stage=3, day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        row = result["recurring_diagnostic_gaps"][0]
        assert len(row["direct_feedback_support_applications"]) == 2
        assert row["causal_conclusion"] == "unknown"


def test_repeated_self_observation_stays_separate_from_employer_feedback() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b"), start=1):
            app = begin(root, slug, "Backend Engineer", application_id=f"app-{index}")
            observe_and_confirm(
                root,
                app["id"],
                kind="candidate_observation",
                theme="system design answer structure",
                observed_at=f"2026-09-0{index}T10:00:00+09:00",
            )
            close(root, app["id"], day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        assert result["repeated_direct_feedback"] == []
        row = result["repeated_self_observations"][0]
        assert row["theme"] == "system design answer structure"
        assert "employer confirmation" in row["meaning"]


def test_unknown_feedback_is_preserved_instead_of_inferred() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        for index, slug in enumerate(("a", "b", "c"), start=1):
            app = begin(root, slug, "QA", stage=index, application_id=f"app-{index}")
            close(root, app["id"], stage=index, day=f"2026-09-0{index}")
        result = learning.analyze(learning.load_store(learning.applications_path(root)))
        assert result["unknowns"]["no_direct_feedback"] == ["app-1", "app-2", "app-3"]
        assert len(result["stage_observations"]) == 3
        rendered = learning.render_report(result)
        assert "no direct feedback: 3" in rendered
        assert "No pattern is promoted" in rendered


def test_closed_application_core_is_immutable_but_evidence_is_append_only() -> None:
    with workspace() as tmp:
        root = Path(tmp)
        app = begin(root, "a", "QA", application_id="app-1")
        close(root, app["id"], stage=3)
        try:
            learning.close_application(
                workspace=root,
                application_id=app["id"],
                closed_reason="offer_declined",
                closed_at="2026-09-11",
                reached_stage=5,
            )
        except ValueError as exc:
            assert "already closed with different data" in str(exc)
        else:
            raise AssertionError("closed outcome must be immutable")
        observation = learning.add_observation(
            workspace=root,
            application_id=app["id"],
            kind="candidate_observation",
            text="answer structure",
            observed_at="2026-09-12",
            source_ref="user:self-report",
        )
        assert observation["id"].startswith("obs-")


def test_cli_runs_from_arbitrary_working_directory() -> None:
    with workspace() as tmp, tempfile.TemporaryDirectory() as elsewhere:
        root = Path(tmp)
        cli = ROOT / "skills" / "tenshoku-strategy" / "job_search_learning.py"
        begin_run = subprocess.run(
            [
                sys.executable,
                str(cli),
                "--workspace",
                str(root),
                "begin",
                "acme",
                "--company-name",
                "Acme",
                "--position",
                "QA Engineer",
                "--role-family",
                "QA",
                "--channel",
                "direct",
                "--opened-at",
                "2026-09-01",
                "--stage",
                "2",
                "--id",
                "app-cli",
            ],
            cwd=elsewhere,
            text=True,
            capture_output=True,
            check=False,
        )
        assert begin_run.returncode == 0, begin_run.stderr
        assert json.loads(begin_run.stdout)["id"] == "app-cli"
        report_run = subprocess.run(
            [sys.executable, str(cli), "--workspace", str(root), "report", "--json"],
            cwd=elsewhere,
            text=True,
            capture_output=True,
            check=False,
        )
        assert report_run.returncode == 0, report_run.stderr
        assert json.loads(report_run.stdout)["model_version"] == "learning_loop_v1"


def run_all() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print(f"OK: {len(tests)} job-search learning tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_all())
