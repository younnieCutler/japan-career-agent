from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"patch anchor missing in {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "skills/career-agent/gui/views_read.py",
    '''        month = str(month_row["month"])
        month_experiences: list[dict[str, Any]] = []
        for claim in canonical_experiences:
            if not isinstance(claim, Mapping):
                continue
            work_date = claim.get("work_date")
            # `months` already applied the canonical tolerant-date policy. Joining only to a
            # month that survived that projection prevents malformed legacy dates from leaking
            # back into the GUI through this presentation adapter.
            if not isinstance(work_date, str) or work_date[:7] != month:
                continue
''',
    '''        month = str(month_row["month"])
        # The deterministic projection already decided exactly which active confirmed claims
        # belong to this month. Use those ids only for the internal join, then omit them from the
        # public GUI payload; prefix-matching work_date would re-admit malformed legacy values such
        # as `2026-09-extra` whenever a valid September claim also existed.
        month_claim_refs = {
            str(ref) for ref in month_row.get("claim_refs", [])
            if isinstance(ref, str) and ref
        }
        month_experiences: list[dict[str, Any]] = []
        for claim in canonical_experiences:
            if not isinstance(claim, Mapping):
                continue
            if str(claim.get("claim_id") or "") not in month_claim_refs:
                continue
''',
)

replace_once(
    "skills/career-agent/gui/test_product_localization.py",
    "from gui.templates import render_shell  # noqa: E402",
    "from gui.templates import gui_messages, render_shell  # noqa: E402",
)
replace_once(
    "skills/career-agent/gui/test_product_localization.py",
    '        keys = set(gui_catalog("ko"))\n        self.assertGreater(len(keys), 40)\n        for locale in SUPPORTED_LANGUAGES:\n            with self.subTest(locale=locale):\n                catalog = gui_catalog(locale)',
    '        keys = set(gui_messages("ko"))\n        self.assertGreater(len(keys), 40)\n        for locale in SUPPORTED_LANGUAGES:\n            with self.subTest(locale=locale):\n                catalog = gui_messages(locale)',
)
replace_once(
    "skills/career-agent/gui/test_product_localization.py",
    '        self.assertEqual(sorted(used - set(gui_catalog("ko"))), [])',
    '        self.assertEqual(sorted(used - set(gui_messages("ko"))), [])',
)

for old, new in (
    ('"career.monthly.add": "이번 달 경험 추가"', '"career.monthly.add": "경험 추가"'),
    ('"career.monthly.add": "今月の経験を追加"', '"career.monthly.add": "経験を追加"'),
    ('"career.monthly.add": "Add experience for this month"', '"career.monthly.add": "Add experience"'),
):
    replace_once("skills/career-agent/gui/monthly_copy.py", old, new)

marker = "\n\nclass ProjectCaseTests(unittest.TestCase):"
test = r'''

class MonthlyCareerReviewProjectionTests(unittest.TestCase):
    def test_monthly_review_joins_only_claims_accepted_by_the_projection(self) -> None:
        views_read = import_module("gui.views_read")
        experience_result = {
            "contexts": {},
            "claims": [
                {
                    "claim_id": "evt-valid", "label": "Valid September work",
                    "work_date": "2026-09", "material_evidence_count": 1,
                    "contains_confidential": False, "detail": {"judgment": "ship"},
                },
                {
                    "claim_id": "evt-invalid", "label": "Malformed legacy work",
                    "work_date": "2026-09-extra", "material_evidence_count": 1,
                    "contains_confidential": False, "detail": {"judgment": "do not leak"},
                },
            ],
            "months": [{
                "month": "2026-09", "evidence_count": 1, "claim_refs": ["evt-valid"],
                "coverage": {"judgment": {"present": 1, "total": 1}},
                "gaps": [], "partial": [],
            }],
        }
        with (
            patch.object(views_read, "list_cases", return_value=[]),
            patch.object(views_read, "list_sessions", return_value={"sessions": []}),
            patch.object(views_read, "list_experiences", return_value=experience_result),
            patch.object(views_read, "list_projects", return_value={"projects": []}),
        ):
            result = views_read.career_overview_payload(object())

        september = result["monthly_reviews"][0]
        self.assertEqual([row["ref"] for row in september["experiences"]], ["evt-valid"])
        self.assertNotIn("claim_refs", september)
'''
file = Path("skills/career-agent/gui/test_projects.py")
text = file.read_text(encoding="utf-8")
if "test_monthly_review_joins_only_claims_accepted_by_the_projection" not in text:
    if marker not in text:
        raise SystemExit("ProjectCaseTests marker missing")
    file.write_text(text.replace(marker, test + marker, 1), encoding="utf-8", newline="\n")
