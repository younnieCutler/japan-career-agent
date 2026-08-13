"""GUI localization boundary contracts."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from gui.templates import render_shell, static_asset  # noqa: E402
from gui import views_read  # noqa: E402
from localization import SUPPORTED_LANGUAGES, gui_catalog, validate_gui_catalog  # noqa: E402


class GuiLocalizationTests(unittest.TestCase):
    def test_catalogs_have_identical_complete_keys(self) -> None:
        self.assertEqual(validate_gui_catalog(), [])
        keys = set(gui_catalog("ko"))
        self.assertGreater(len(keys), 40)
        for locale in SUPPORTED_LANGUAGES:
            with self.subTest(locale=locale):
                catalog = gui_catalog(locale)
                self.assertEqual(set(catalog), keys)
                self.assertTrue(all(isinstance(value, str) and value for value in catalog.values()))
        self.assertEqual(gui_catalog("ko")["enum.project_status.active"], "진행 중")
        self.assertEqual(gui_catalog("ja")["enum.self_analysis_state.reviewed_empty"], "確認済み・該当なし")
        self.assertEqual(gui_catalog("ko")["enum.case_status.active"], "진행 중")

    def test_approval_snapshot_localizes_status_and_hides_document_ids(self) -> None:
        script = static_asset("screens.js").decode("utf-8")
        self.assertIn('enumText("project_status", value)', script)
        self.assertIn('enumText("self_analysis_state", value)', script)
        self.assertIn('t("review.evidence_private_document")', script)
        self.assertIn('caseBadge(position.status)', script)
        self.assertIn('option.contains_confidential ? t("career.confidential_experience")', script)
        self.assertNotIn('position.status === "active" ? "draft"', script)
        self.assertNotEqual(gui_catalog("ko")["field.status"], gui_catalog("ko")["filter.all"])

    def test_missing_project_title_uses_a_human_label_not_its_internal_id(self) -> None:
        script = static_asset("screens.js").decode("utf-8")
        self.assertIn('project.label || t("career.project")', script)
        with (
            patch.object(views_read, "list_cases", return_value=[]),
            patch.object(views_read, "list_sessions", return_value={"sessions": []}),
            patch.object(views_read, "list_experiences", return_value={
                "contexts": {"context-1": {"kind": "company", "label": "Acme"}},
                "claims": [{
                    "claim_id": "claim-1", "context_id": "context-1",
                    "project_id": "internal-project-id", "label": "Experience",
                }],
            }),
            patch.object(views_read, "list_projects", return_value={
                "projects": [{"id": "internal-project-id"}],
            }),
        ):
            result = views_read.career_overview_payload(object())

        project = result["contexts"][0]["projects"][0]
        self.assertIsNone(project["label"])
        self.assertNotIn("internal-project-id", str(project["label"]))

    def test_active_language_controls_the_data_free_shell(self) -> None:
        expected = {
            "ko": ("<html lang=\"ko\">", "본문으로 건너뛰기"),
            "ja": ("<html lang=\"ja\">", "本文へ移動"),
            "en": ("<html lang=\"en\">", "Skip to main content"),
        }
        for locale, values in expected.items():
            with self.subTest(locale=locale):
                shell = render_shell(locale)
                self.assertIn(values[0], shell)
                self.assertIn(values[1], shell)
                self.assertIn(gui_catalog(locale)["app.tagline"], shell)

    def test_language_switch_uses_the_same_unsaved_work_guard_as_navigation(self) -> None:
        script = static_asset("app.js").decode("utf-8")
        control = script.split("function languageControl", 1)[1].split("function renderShell", 1)[0]

        self.assertLess(control.index("leaveGuard"), control.index("window.location.assign"))
        self.assertLess(control.index("clearRouteGuard"), control.index("window.location.assign"))
        self.assertIn("select.value = locale()", control)

    def test_route_changes_release_editor_cleanup_without_dropping_a_failed_archive_guard(self) -> None:
        app = static_asset("app.js").decode("utf-8")
        screens = static_asset("screens.js").decode("utf-8")
        self.assertIn("let routeCleanup = null", app)
        self.assertIn("if (cleanup) cleanup()", app)
        self.assertIn("app.setLeaveGuard(leave, cleanup)", screens)
        self.assertIn('window.removeEventListener("beforeunload", unload)', screens)
        archive = screens.split('const archive = button("action.archive"', 1)[1].split("actionsBar.append", 1)[0]
        self.assertLess(archive.index("await write"), archive.index("app.setLeaveGuard(null)"))

    def test_client_entrypoint_contains_keys_not_mixed_language_copy(self) -> None:
        script = b"".join(
            static_asset(name)
            for name in ("bootstrap.js", "app.js", "api.js", "i18n.js", "screens.js")
        ).decode("utf-8")

        self.assertIn("nav.home", script)
        self.assertNotRegex(script, r"[가-힣ぁ-ゖァ-ヺ]玉?")
        for leaked in ("Independent signals", "Waiting for your decision", "Archive case"):
            self.assertNotIn(leaked, script)

    def test_unknown_read_error_codes_fall_back_to_localized_copy(self) -> None:
        app = static_asset("app.js").decode("utf-8")
        i18n = static_asset("i18n.js").decode("utf-8")
        self.assertIn('errorText(error.code, "READ_FAILED")', app)
        self.assertIn('messages[`error.${code || ""}`] || t(`error.${fallback}`)', i18n)
        self.assertNotIn('t(`error.${error.code', app)

    def test_every_literal_client_message_key_exists(self) -> None:
        script = b"".join(
            static_asset(name) for name in ("app.js", "screens.js")
        ).decode("utf-8")
        prefixes = (
            "a11y|action|app|applications|career|common|confidentiality|date|documents|"
            "enum|error|evidence|field|filter|home|input|language|nav|review|search|"
            "self_analysis|state|status|success|timeline|trust|work|workflow"
        )
        used = set(re.findall(
            rf"[\"']((?:{prefixes})\.[A-Za-z0-9_.]+)[\"']",
            script,
        ))
        self.assertEqual(sorted(used - set(gui_catalog("ko"))), [])

    def test_core_catalogs_do_not_fall_back_to_another_language(self) -> None:
        product_tokens = {
            "Japan Career Agent", "Career Agent", "Career Vault", "Claude", "Codex", "CLI", "GUI",
        }
        for locale in ("ko", "ja"):
            offenders = []
            for key, value in gui_catalog(locale).items():
                if key in {"date.range", "language.en"} or any(token in value for token in product_tokens):
                    continue
                local = r"[가-힣]" if locale == "ko" else r"[ぁ-んァ-ヶ一-龯]"
                if re.search(r"[A-Za-z]{3,}", value) and not re.search(local, value):
                    offenders.append((key, value))
            self.assertEqual(offenders, [], f"untranslated {locale} GUI copy")

        intentional_japanese = {
            "language.ja", "track.shinsotsu", "track.chuto", "document.career_history",
            "enum.track.shinsotsu", "enum.track.chuto", "enum.document.career_history",
        }
        english_offenders = [
            (key, value)
            for key, value in gui_catalog("en").items()
            if re.search(r"[가-힣ぁ-んァ-ヶ一-龯]", value)
            and key not in intentional_japanese | {"language.ko"}
        ]
        self.assertEqual(english_offenders, [], "mixed-language English GUI copy")


if __name__ == "__main__":
    unittest.main()
