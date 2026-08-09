"""KO/JA/EN coverage for the three intent lexicons, and the collisions they must not cause.

The maintenance, opportunity-review and active-search tables sit beside the four routing tables
that were already there. The tests below check both directions: the new phrases fire when they
should, and every stage the old tables owned still resolves the way it did.
"""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))
import career_agent  # noqa: E402


class MaintenanceIntentTests(unittest.TestCase):
    def test_korean_maintenance_requests(self) -> None:
        for message in (
            "오늘 한 일 기록해줘",
            "업무일지 남겨줘",
            "이 프로젝트 나중에 경력으로 쓸 수 있게 남겨줘",
            "이번 분기 성과 정리",
            "이직 생각은 없는데 경력은 정리해두고 싶어",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.maintenance_intent(message))

    def test_japanese_maintenance_requests(self) -> None:
        for message in (
            "今日やった仕事を記録して",
            "このプロジェクトを職務経歴として残しておきたい",
            "今期の成果を整理したい",
            "転職する予定はないけど、経歴は更新しておきたい",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.maintenance_intent(message))

    def test_english_maintenance_requests(self) -> None:
        for message in (
            "Save this project as career evidence.",
            "I am not job hunting, but I want to keep my work history current.",
            "Add this to my work log",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.maintenance_intent(message))

    def test_ordinary_job_search_requests_are_not_maintenance(self) -> None:
        for message in (
            "職務経歴書を添削してほしい",
            "경력기술서 고쳐줘",
            "이력서 봐줘",
            "面接の準備をしたい",
            "この求人に応募できるか",
            "Please improve my resume",
        ):
            with self.subTest(message=message):
                self.assertFalse(career_agent.maintenance_intent(message))


class OpportunityReviewIntentTests(unittest.TestCase):
    def test_reviewing_without_declaring_a_search(self) -> None:
        for message in (
            "헤드헌터가 JD 보냈는데 그냥 괜찮은 포지션인지 봐줘. 이직 시작하는 건 아냐.",
            "スカウトが来たので見てほしいだけ",
            "A recruiter reached out, is this a good position?",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.opportunity_review_intent(message))

    def test_an_ordinary_document_request_is_not_an_opportunity_review(self) -> None:
        self.assertFalse(career_agent.opportunity_review_intent("職務経歴書を添削してほしい"))


class ActiveSearchIntentTests(unittest.TestCase):
    def test_an_explicit_declaration(self) -> None:
        for message in (
            "이제 진짜 이직 준비 시작할래",
            "이 회사 지원하고 싶어",
            "転職活動を始めるつもりです",
            "応募したいです",
            "I want to start job hunting",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.active_search_intent(message))

    def test_a_negated_declaration_is_not_a_declaration(self) -> None:
        for message in (
            "이직 준비 시작할 생각은 없어",
            "이직 준비 시작하는 건 아니야",
            "転職活動を始める予定はない",
            "I am not starting a job search yet",
        ):
            with self.subTest(message=message):
                self.assertFalse(career_agent.active_search_intent(message))

    def test_curiosity_is_not_a_declaration(self) -> None:
        for message in (
            "이 회사 좀 궁금한데",
            "시장 연봉만 보고 싶어",
            "헤드헌터가 보낸 JD 평가해줘",
            "この求人を見てほしい",
        ):
            with self.subTest(message=message):
                self.assertFalse(career_agent.active_search_intent(message))


class NoRegressionInTheOlderTablesTests(unittest.TestCase):
    """The four original tables must behave exactly as before the intent tables were added."""

    def test_stage_routing_is_unchanged_for_maintenance_vocabulary(self) -> None:
        # These messages now match `maintenance`, but `stage_for` never reads that table, so a
        # caller that ignores the intent still gets the same stage it always did.
        cases = (
            ("이력서 정리해줘", "chuto", "職務経歴書・自己PR"),
            ("職務経歴書を書きたい", "chuto", "職務経歴書・自己PR"),
            ("この求人に応募できるか", "chuto", "応募・書類選考"),
            ("面接の準備をしたい", "chuto", "面接"),
        )
        for message, track, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(career_agent.stage_for(message, track), expected)

    def test_the_known_korean_document_gap_is_unchanged(self) -> None:
        # Pre-existing and out of scope here: `경력기술서` is in the chuto flow_phase table but not
        # in the `documents` stage alias, so it falls through to the self-analysis default. Pinned
        # so that closing the gap later is a deliberate lexicon change with a benchmark behind it,
        # not an accident of some other edit.
        self.assertEqual(career_agent.stage_for("경력기술서 정리해줘", "chuto"), "自己分析・転職軸")

    def test_track_inference_is_unchanged(self) -> None:
        self.assertEqual(career_agent.infer_track("이직 생각은 없는데 경력은 정리해두고 싶어"), "chuto")
        self.assertIsNone(career_agent.infer_track("오늘 한 일 기록해줘"))
        self.assertIsNone(career_agent.infer_track("今日やった仕事を記録して"))

    def test_no_maintenance_phrase_is_a_substring_of_a_stage_alias_term(self) -> None:
        # The failure this guards against is silent: a fragment like 経歴 would make every
        # 職務経歴書 request read as a maintenance note.
        alias_terms = [
            term.lower()
            for group in career_agent.ROUTING["stage_alias"]
            for term in group["terms"]
        ]
        for phrase in career_agent.ROUTING["maintenance"]:
            for term in alias_terms:
                with self.subTest(phrase=phrase, term=term):
                    self.assertNotIn(phrase.lower(), term)


if __name__ == "__main__":
    unittest.main()
