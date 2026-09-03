"""Visual contracts that carry product meaning.

These are not taste assertions. Each one guards a rule from DESIGN.md that encodes the trust
model: what has been attested, what is still a claim, and what contradicts something else. A
regression here degrades evidence legibility without breaking any behavioural test.

The client is a React application built on SEED. Contracts about intent are checked against
`frontend/src`, because that is what a reviewer reads; contracts about what the browser actually
receives are checked against the built bundle, because a rule that never reaches the stylesheet
is not a rule.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))

from _test_client import FRONTEND_SRC, client_source  # noqa: E402
from gui.templates import static_asset  # noqa: E402
from localization import SUPPORTED_LANGUAGES, gui_catalog  # noqa: E402


def source(name: str) -> str:
    """One hand-written client file, by path under `frontend/src`."""
    return (FRONTEND_SRC / name).read_text(encoding="utf-8")


def workspace_css() -> str:
    """The layout stylesheet the screens are written against."""
    return source("workspace.css")


def shipped_css() -> str:
    """What the browser actually gets, SEED included."""
    return static_asset("app/app.css").decode("utf-8")


def block(css: str, selector: str) -> str:
    """The declarations of the first rule whose selector contains `selector`."""
    head, marker, rest = css.partition(selector)
    if not marker:
        raise AssertionError(f"missing rule: {selector}")
    return rest.split("{", 1)[1].split("}", 1)[0]


def without_comments(text: str) -> str:
    """Source with its prose removed.

    A check for a banned word has to read the code, not the explanation of why the word is
    banned — otherwise documenting a rule is what breaks it.
    """
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


class AttestationDotTests(unittest.TestCase):
    """The dot states each row's evidence state on its left edge."""

    def setUp(self) -> None:
        self.css = workspace_css()

    def test_every_evidence_tone_has_a_dot(self) -> None:
        for tone in ("positive", "warning", "neutral"):
            with self.subTest(tone=tone):
                self.assertIn(f'.row[data-tone="{tone}"]::before', self.css)
        self.assertIn('.row[data-conflict="true"]::before', self.css)

    def test_conflict_dot_is_declared_after_the_lifecycle_dots(self) -> None:
        """A conflicted record is still approved, so both rules match the same row.

        Equal specificity means source order decides. If conflict were declared first, the
        approved dot would paint over it and a contradiction would be silently averaged into a
        lifecycle state — exactly what the product forbids.
        """
        for tone in ("positive", "warning", "neutral"):
            with self.subTest(tone=tone):
                self.assertLess(
                    self.css.index(f'.row[data-tone="{tone}"]::before'),
                    self.css.index('.row[data-conflict="true"]::before'),
                    "conflict dot must be able to override a lifecycle dot",
                )

    def test_draft_dot_is_drawn_not_coloured(self) -> None:
        """A draft is the absence of attestation, so it is a hollow ring rather than tinted.

        The rule it has to break is the one every other tone follows — filling the dot. Asserting
        the ring alone would still pass if a fill were added beside it, so both halves are checked.
        """
        draft = block(self.css, '.row[data-tone="neutral"]::before')
        self.assertIn("background: transparent", draft)
        self.assertIn("inset", draft)

    def test_draft_chip_is_outlined_rather_than_filled(self) -> None:
        chips = source("evidence.jsx")
        self.assertIn('variant={state === "draft" ? "outline" : "weak"}', chips)

    def test_conflict_colour_is_reserved_for_contradiction(self) -> None:
        """Critical must never be spent on emphasis, or it stops meaning "these disagree"."""
        allowed = ("data-conflict", ".confidential-note")
        for rule in self.css.split("}"):
            selector, _, declarations = rule.rpartition("{")
            if "critical" not in declarations:
                continue
            if not any(token in selector for token in allowed):
                self.fail(f"critical colour used outside contradiction: {selector.strip()}")

    def test_conflict_chip_is_the_one_solid_chip(self) -> None:
        """A contradiction is the single state that has to win a glance."""
        chips = source("evidence.jsx")
        conflict = chips.split("export function ConflictChip", 1)[1].split("\nexport ", 1)[0]
        self.assertIn('tone="critical"', conflict)
        self.assertIn('variant="solid"', conflict)


class SplitPaneTests(unittest.TestCase):
    """The index is scannable and the record is reachable."""

    def setUp(self) -> None:
        self.css = workspace_css()
        self.career = source("screens/Career.jsx")

    def test_index_rows_are_denser_than_a_touch_list(self) -> None:
        """The deliberate deviation from SEED: this screen exists to show a record densely."""
        row = block(self.css, "\n.row")
        height = float(re.search(r"min-height: ([\d.]+)rem", row).group(1))
        self.assertLessEqual(height, 2.5)

    def test_selecting_a_row_does_not_repaint_its_evidence_dot(self) -> None:
        """Selection is a view state; the dot states what the Vault holds.

        If selecting repainted the left edge, the column would stop being scannable as "what is
        real" the moment the user clicked anything. Checked across every rule rather than in the
        one we expect, so reaching the dot from a new selection selector fails too.
        """
        self.assertIn("background", block(self.css, '.row[data-selected="true"]'))
        for rule in self.css.split("}"):
            selector, _, _ = rule.rpartition("{")
            if "data-selected" in selector:
                with self.subTest(selector=selector.strip()):
                    self.assertNotIn("::before", selector)

    def test_the_record_is_reachable_on_a_phone(self) -> None:
        narrow = self.css.split("@media (max-width: 900px)", 1)[1]
        self.assertIn('.split[data-record-open="true"] .split__record { display: block; }', narrow)
        self.assertIn(".back-to-index { display: inline-flex", narrow)

    def test_selection_lives_in_the_url(self) -> None:
        app = source("App.jsx")
        self.assertIn('url.searchParams.set("sel", ref)', app)
        # Replacing rather than pushing: Back must not walk every row the user glanced at.
        self.assertIn("window.history.replaceState({}, \"\", url.toString())", app)
        self.assertIn("setSelection(row.ref)", self.career)
        self.assertIn("new URLSearchParams(search)", self.career)
        self.assertIn('params.get("sel")', self.career)


class CompanyExperienceRollupTests(unittest.TestCase):
    """A company shows its experiences, whichever project they sit under."""

    def setUp(self) -> None:
        self.career = source("screens/Career.jsx")

    def test_rollup_merges_project_and_context_level_experiences(self) -> None:
        rollup = self.career.split("function companyExperiences", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("context.projects", rollup)
        self.assertIn("project.experiences", rollup)
        # Experiences the Vault holds against the context with no project must not be dropped.
        self.assertIn("context.other_experiences", rollup)

    def test_adding_an_experience_can_start_unassigned_without_inventing_a_project(self) -> None:
        """Capture may start before the user models a project, but the UI must never manufacture
        one. The existing unassigned-work path holds the draft until its location is connected."""
        starter = self.career.split("function AddExperience", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn('/api/workflows/start', starter)
        self.assertIn('workflow: "career_inventory"', starter)
        self.assertIn("project ? { case_ref: project.ref } : {}", starter)
        self.assertNotIn("/api/career/projects", starter)
        self.assertIn('lifecycle === "approved"', starter)

    def test_starting_a_second_capture_asks_first(self) -> None:
        """Unfinished work on the same project is easy to forget you left open."""
        starter = self.career.split("function AddExperience", 1)[1].split("\nfunction ", 1)[0]
        self.assertIn("career.new_experience_confirm", starter)


class MultilingualTypographyTests(unittest.TestCase):
    """Korean and Japanese are the primary locales, so these are correctness issues."""

    def test_korean_does_not_break_mid_word(self) -> None:
        """`overflow-wrap: anywhere` splits hangul at arbitrary syllable blocks."""
        css = workspace_css()
        self.assertIn("word-break: keep-all", css)
        self.assertNotIn("overflow-wrap: anywhere", css)

    def test_no_synthesised_italics(self) -> None:
        """KO/JA have no italic face; browsers slant the upright one and it reads as a fault."""
        self.assertNotIn("font-style: italic", workspace_css())
        self.assertIn("font-style: normal", workspace_css())

    def test_the_shipped_stylesheet_carries_no_webfont(self) -> None:
        """CSP declares no `font-src`, so a webfont would silently fail to load."""
        self.assertNotIn("@font-face", shipped_css())

    def test_both_colour_schemes_are_defined(self) -> None:
        css = shipped_css()
        self.assertIn("color-scheme", css)
        self.assertIn("prefers-color-scheme", css)

    def test_status_vocabulary_is_translated_everywhere(self) -> None:
        for locale in SUPPORTED_LANGUAGES:
            with self.subTest(locale=locale):
                self.assertIn("status.conflict", gui_catalog(locale))


class HomeIsAQueueNotADashboardTests(unittest.TestCase):
    """Home answers "what do I do next", not "how am I doing"."""

    def setUp(self) -> None:
        self.home = source("screens/Home.jsx")

    def test_home_reports_a_conflict(self) -> None:
        """The runtime always counted conflicts; Home never read the count."""
        self.assertIn("home.conflicts?.count", self.home)
        self.assertIn("career.context_conflict_title", self.home)

    def test_home_reads_the_runtime_view_instead_of_recomputing_it(self) -> None:
        """`/api/home` already reports conflicts, pending approvals and readiness.

        Home previously rebuilt a weaker version of that from other endpoints, which is how it
        ended up unable to mention a conflict at all.
        """
        self.assertIn('read("/api/home")', self.home)
        self.assertIn("home.readiness?.bootstrap_suggested", self.home)

    def test_home_separates_review_from_draft(self) -> None:
        self.assertIn("home.review_title", self.home)
        self.assertIn("home.resume_title", self.home)


class DiagnosisScreenTests(unittest.TestCase):
    """Six independent answers, never a score."""

    def setUp(self) -> None:
        self.diagnosis = source("screens/Diagnosis.jsx")

    def test_every_runtime_dimension_is_named_and_evidenced(self) -> None:
        """A dimension the runtime adds must arrive with a label and its supporting counts.

        The rows themselves are rendered generically from the payload, so the screen cannot drop a
        dimension — but it can render one with a raw token for a name and no evidence behind it,
        which is the failure worth catching.
        """
        import inspect  # noqa: PLC0415

        from views import readiness  # noqa: PLC0415

        emitted = set(re.findall(
            r'^\s{12}"([a-z_]+)": (?:dimension\(|\()', inspect.getsource(readiness), re.MULTILINE))
        self.assertTrue(emitted, "could not read the runtime dimensions")
        catalog = gui_catalog("ko")
        evidence_map = self.diagnosis.split("const DIMENSION_EVIDENCE", 1)[1].split("};", 1)[0]
        for name in emitted:
            with self.subTest(dimension=name):
                self.assertIn(f"enum.readiness_dimension.{name}", catalog)
                self.assertIn(name, evidence_map)

    def test_states_use_the_vocabulary_the_runtime_emits(self) -> None:
        """Confirmed / Partial / Stale / Unknown, and nothing invented alongside them.

        Read out of `views.readiness` rather than written down here, so the client cannot drift
        from the runtime in either direction: a state the runtime starts emitting has to arrive
        with a translation and a tone, and a state only the client believes in fails immediately.
        """
        import inspect  # noqa: PLC0415

        from views import readiness  # noqa: PLC0415

        emitted = set(re.findall(r'"([A-Z][a-z]+)"', inspect.getsource(readiness)))
        self.assertEqual(emitted, {"Confirmed", "Partial", "Stale", "Unknown"})

        for locale in SUPPORTED_LANGUAGES:
            catalog = gui_catalog(locale)
            for state in emitted:
                with self.subTest(locale=locale, state=state):
                    self.assertIn(f"enum.readiness.{state.lower()}", catalog)
        self.assertNotIn("enum.readiness.low_confidence", gui_catalog("ko"))

        # `enum.readiness` is an alias of the canonical `fact_state` rows, so the chip cannot
        # introduce a state of its own: every key here has to be one the runtime emits.
        ramp = source("evidence.jsx").split("const READINESS_TONE", 1)[1].split("};", 1)[0]
        self.assertEqual(set(re.findall(r"^\s+(\w+):", ramp, re.MULTILINE)), emitted)

    def test_the_screen_states_that_it_does_not_total(self) -> None:
        self.assertIn("diagnosis.no_total", self.diagnosis)
        for banned in ("score", "percent", "average", "total("):
            with self.subTest(term=banned):
                self.assertNotIn(banned, without_comments(self.diagnosis).lower())

    def test_readiness_states_are_not_a_single_colour_ramp(self) -> None:
        """A shared gradient would invite the eye to average six separate answers.

        `Partial` and `Stale` deliberately share one tone rather than each taking a step on a
        ramp between neutral and positive.
        """
        chips = source("evidence.jsx")
        ramp = chips.split("const READINESS_TONE", 1)[1].split("};", 1)[0]
        self.assertIn('Confirmed: "positive"', ramp)
        self.assertIn('Unknown: "neutral"', ramp)
        self.assertEqual(ramp.count('"warning"'), 2, "Partial and Stale share one tone")
        self.assertNotIn("critical", ramp)

    def test_engine_facing_actions_are_not_rendered(self) -> None:
        """`guided.available_actions` carries CLI commands like `restore-state <version>`."""
        self.assertNotIn("available_actions", without_comments(client_source()))


class DesignTokensComeFromSeedTests(unittest.TestCase):
    """One scale, and it is not this repository's to invent."""

    def test_layout_css_declares_no_palette_of_its_own(self) -> None:
        """Every colour has to be a SEED token, or the design system can be drifted away from."""
        css = workspace_css()
        for literal in re.findall(r"#[0-9a-fA-F]{3,8}\b", css):
            self.fail(f"hard-coded colour in layout CSS: {literal}")
        for function in ("rgb(", "hsl(", "oklch("):
            with self.subTest(function=function):
                self.assertNotIn(function, css)

    def test_spacing_and_type_use_seed_scales(self) -> None:
        css = workspace_css()
        for token in ("--seed-dimension-x", "--seed-font-size-t", "--seed-radius-r", "--seed-color-"):
            with self.subTest(token=token):
                self.assertIn(token, css)

    def test_page_title_is_application_scale_not_landing_page_scale(self) -> None:
        """A display size pushes real content below the fold on a data screen."""
        for screen in ("screens/Home.jsx", "screens/Career.jsx", "screens/Diagnosis.jsx"):
            with self.subTest(screen=screen):
                sizes = re.findall(r'textStyle="t(\d+)', source(screen))
                self.assertTrue(sizes)
                self.assertLessEqual(max(int(size) for size in sizes), 8)


if __name__ == "__main__":
    unittest.main()
