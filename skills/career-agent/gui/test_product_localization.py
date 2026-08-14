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

from _test_client import FRONTEND_SRC, client_modules, client_source  # noqa: E402
from gui.templates import render_shell  # noqa: E402
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
        script = client_source()
        self.assertIn('enumText("project_status", value)', script)
        self.assertIn('enumText("self_analysis_state", value)', script)
        self.assertIn('t("review.evidence_private_document")', script)
        self.assertIn('<CaseChip state={position.status} />', script)
        self.assertIn('option.contains_confidential ? t("career.confidential_experience")', script)
        self.assertNotIn('position.status === "active" ? "draft"', script)
        self.assertNotEqual(gui_catalog("ko")["field.status"], gui_catalog("ko")["filter.all"])

    def test_missing_project_title_uses_a_human_label_not_its_internal_id(self) -> None:
        script = client_source()
        self.assertIn('project.label || labels.project', script)
        self.assertIn('project: t("career.project")', script)
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

    def test_leaving_a_screen_with_unsaved_work_asks_first(self) -> None:
        """Routing is client-side, so `beforeunload` alone would not see a sidebar click."""
        app = (FRONTEND_SRC / "App.jsx").read_text(encoding="utf-8")
        work = (FRONTEND_SRC / "screens" / "Work.jsx").read_text(encoding="utf-8")

        self.assertIn("let leaveGuard = null", app)
        # The guard runs before the URL changes, and a refusal aborts the navigation.
        guard = app.split("export async function navigate", 1)[1].split("export function", 1)[0]
        self.assertLess(guard.index("await guard()"), guard.index("window.history.pushState"))
        self.assertIn("setLeaveGuard(leave)", work)

    def test_language_switch_uses_the_same_unsaved_work_guard_as_navigation(self) -> None:
        """Switching language reloads the document, which would discard a draft without asking."""
        app = (FRONTEND_SRC / "App.jsx").read_text(encoding="utf-8")
        control = app.split("function LanguageControl", 1)[1].split("\nfunction Shell", 1)[0]

        self.assertLess(control.index("await guard()"), control.index("window.location.assign"))
        self.assertIn('url.searchParams.set("lang", next)', control)
        self.assertIn("value={language}", control)

    def test_the_editor_releases_its_guards_when_it_goes_away(self) -> None:
        """A guard left behind would block every later navigation with a stale question."""
        work = (FRONTEND_SRC / "screens" / "Work.jsx").read_text(encoding="utf-8")
        cleanup = work.split("window.addEventListener(\"beforeunload\", unload)", 1)[1].split("}, [leave", 1)[0]
        self.assertIn('window.removeEventListener("beforeunload", unload)', cleanup)
        self.assertIn("setLeaveGuard(null)", cleanup)
        # Archiving leaves only after the write lands, so a failed archive keeps the guard.
        archive = work.split("const archive = async", 1)[1].split("\n  };", 1)[0]
        self.assertLess(archive.index("await write"), archive.index("setLeaveGuard(null)"))

    def test_client_entrypoint_contains_keys_not_mixed_language_copy(self) -> None:
        # Comments are not copy. `evidence.jsx` quotes SEED's own Korean documentation to justify
        # its tone mapping, which is the sort of note that should survive this check.
        script = re.sub(r"/\*.*?\*/|//[^\n]*", " ", client_source(), flags=re.DOTALL)

        self.assertIn("nav.home", script)
        self.assertNotRegex(script, r"[가-힣ぁ-ゖァ-ヺ]玉?")
        for leaked in ("Independent signals", "Waiting for your decision", "Archive case"):
            self.assertNotIn(leaked, script)

    def test_unknown_read_error_codes_fall_back_to_localized_copy(self) -> None:
        """An error code the catalog has no copy for must not surface as a bare token."""
        i18n = (FRONTEND_SRC / "i18n.jsx").read_text(encoding="utf-8")
        states = (FRONTEND_SRC / "components" / "States.jsx").read_text(encoding="utf-8")
        self.assertIn('messages[`error.${code || ""}`] || t(`error.${fallback}`)', i18n)
        self.assertIn('ERROR_CODES.has(error?.code) ? error.code : "SAVE_FAILED"', states)

    def test_every_literal_client_message_key_exists(self) -> None:
        script = client_source(exclude=("api.js",))
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

    def test_client_modules_only_call_identifiers_they_define(self) -> None:
        """A call to an undefined identifier is a ReferenceError no Python test can otherwise see.

        The client is served as ES modules, so an undeclared name is not a silent global: it
        throws, `showCurrentRoute` catches it, and the screen is replaced by the read-failure
        panel. The Vault is untouched, but the user is told the data could not be loaded when the
        real fault is in the client. Every route request still answers 200, so the server-side
        suite stays green while the screen is unreachable.
        """
        keywords = {
            "async", "await", "catch", "class", "constructor", "delete", "do", "else", "for",
            "function", "if", "in", "instanceof", "new", "of", "return", "super", "switch",
            "throw", "typeof", "void", "while", "yield",
        }
        browser_globals = {
            "Array", "Boolean", "Date", "Error", "Event", "Intl", "JSON", "Map", "Number",
            "Object", "Promise", "Set", "String", "URL", "URLSearchParams", "encodeURIComponent",
            "fetch", "queueMicrotask", "setTimeout", "clearTimeout",
        }
        for path in client_modules():
            with self.subTest(module=path.name):
                source = path.read_text(encoding="utf-8")
                # Prose is not code. "separate views (the list…)" in a comment otherwise reads as a
                # call to an undeclared `views`. Protocol-relative slashes are left alone.
                source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
                source = re.sub(r"(?<!:)//[^\n]*", " ", source)
                declared = set(re.findall(
                    r"\b(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", source,
                ))
                # Destructured declarations bind names too: `const { t } = useI18n()` and
                # `const [state, setState] = React.useState()` are the shape most of this file
                # is written in, and reading them as calls would flag every screen.
                for group in re.findall(r"\b(?:const|let|var)\s*[\[{]([^\]}]*)[\]}]\s*=", source):
                    for part in group.split(","):
                        candidate = part.split(":")[-1].split("=")[0].strip().lstrip(".")
                        if re.fullmatch(r"[A-Za-z_$][\w$]*", candidate):
                            declared.add(candidate)
                # Class methods are called on an instance, never as bare names.
                declared |= set(re.findall(r"^\s{2}(?:static\s+)?([A-Za-z_$][\w$]*)\s*\(", source, re.M))
                for imported in re.findall(r"import\s*\{([^}]*)\}", source):
                    declared |= {
                        part.strip().split(" as ")[-1].strip()
                        for part in imported.split(",") if part.strip()
                    }
                parameters = set()
                for group in re.findall(
                    r"(?:function\s*[\w$]*\s*|\)\s*=>|(?<=[(,=]\s))\(([^()]*)\)\s*(?:=>|\{)", source,
                ):
                    # Destructured parameters are still bindings; braces would otherwise make
                    # `{ render, container }` look like undeclared names at the call site.
                    for part in group.replace("{", " ").replace("}", " ").split(","):
                        candidate = part.strip().split("=")[0].strip()
                        if re.fullmatch(r"[A-Za-z_$][\w$]*", candidate):
                            parameters.add(candidate)
                # String contents are data, not code: a CSS `var(--seed-…)` in a style value is
                # not a call to a JavaScript function named `var`.
                without_strings = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'|`[^`]*`', '""', source)
                called = set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(", without_strings))
                undefined = called - declared - parameters - keywords - browser_globals
                self.assertEqual(sorted(undefined), [], f"{path.name} calls undefined identifiers")

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
