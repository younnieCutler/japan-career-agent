"""KO/JA/EN coverage for career-mode intents and the canonical lifecycle boundary.

Maintenance, inventory, opportunity review and active-search declarations remain independent from
market-stage routing. The tests below pin that separation while allowing the chuto stage vocabulary
to evolve deliberately.
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


class LifecycleSeparationTests(unittest.TestCase):
    def test_stage_routing_remains_independent_from_maintenance_intent(self) -> None:
        cases = (
            ("이력서 정리해줘", "chuto", "応募基盤・職務経歴書"),
            ("職務経歴書を書きたい", "chuto", "応募基盤・職務経歴書"),
            ("この求人に応募できるか", "chuto", "企業研究・JD分析"),
            ("面接の準備をしたい", "chuto", "面接・選考"),
            ("入社準備をしたい", "chuto", "入社準備・オンボーディング"),
        )
        for message, track, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(career_agent.stage_for(message, track), expected)

    def test_korean_career_document_term_is_a_base_document_signal(self) -> None:
        self.assertEqual(
            career_agent.stage_for("경력기술서 정리해줘", "chuto"), "応募基盤・職務経歴書"
        )

    def test_spi_name_alone_does_not_infer_a_hiring_track(self) -> None:
        self.assertIsNone(career_agent.infer_track("SPI3対策をしたい"))
        self.assertIsNone(career_agent.infer_track("적성검사 준비하고 싶어"))
        self.assertEqual(career_agent.infer_track("中途でSPI3対策をしたい"), "chuto")
        self.assertEqual(career_agent.infer_track("新卒でSPI3対策をしたい"), "shinsotsu")

    def test_track_inference_for_maintenance_is_unchanged(self) -> None:
        self.assertEqual(career_agent.infer_track("이직 생각은 없는데 경력은 정리해두고 싶어"), "chuto")
        self.assertIsNone(career_agent.infer_track("오늘 한 일 기록해줘"))
        self.assertIsNone(career_agent.infer_track("今日やった仕事を記録して"))

    def test_no_intent_phrase_is_a_substring_of_a_stage_alias_term(self) -> None:
        alias_terms = [
            term.lower()
            for group in career_agent.ROUTING["stage_alias"]
            for term in group["terms"]
        ]
        for table in ("maintenance", "tanaoroshi", "opportunity_review", "transition"):
            for phrase in career_agent.ROUTING[table]:
                for term in alias_terms:
                    with self.subTest(table=table, phrase=phrase, term=term):
                        self.assertNotIn(phrase.lower(), term)


class TanaoroshiIntentTests(unittest.TestCase):
    """Going back over experience from before the ledger existed, not keeping it current."""

    def test_korean_inventory_requests(self) -> None:
        for message in (
            "지금까지의 경력을 정리하고 싶어",
            "그동안 해온 일을 정리해줘",
            "경력 전체를 돌아보고 싶어요",
            "학창시절 경험을 정리해야 할 것 같아",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.tanaoroshi_intent(message))

    def test_japanese_inventory_requests(self) -> None:
        for message in (
            "キャリアの棚卸しをしたい",
            "これまでの経験を整理したいです",
            "経歴の棚卸から始めたい",
            "学生時代の経験を整理しておきたい",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.tanaoroshi_intent(message))

    def test_english_inventory_requests(self) -> None:
        for message in (
            "I want to do a career inventory.",
            "Help me take stock of my career.",
            "Let's go through my past experience first.",
        ):
            with self.subTest(message=message):
                self.assertTrue(career_agent.tanaoroshi_intent(message))

    def test_ordinary_upkeep_is_not_an_inventory(self) -> None:
        for message in (
            "오늘 한 일 기록해줘",
            "업무일지 남겨줘",
            "今日やった仕事を記録して",
            "今期の成果を整理したい",
            "Add this to my work log",
        ):
            with self.subTest(message=message):
                self.assertFalse(career_agent.tanaoroshi_intent(message))
                self.assertTrue(career_agent.maintenance_intent(message))

    def test_job_search_requests_are_not_an_inventory(self) -> None:
        for message in (
            "職務経歴書を添削してほしい",
            "この求人に応募できるか",
            "面接の準備をしたい",
            "Please improve my resume",
        ):
            with self.subTest(message=message):
                self.assertFalse(career_agent.tanaoroshi_intent(message))

    def test_an_inventory_request_is_not_a_declaration_of_a_search(self) -> None:
        message = "이직 생각은 없는데 지금까지의 경력을 정리해두고 싶어"
        self.assertTrue(career_agent.tanaoroshi_intent(message))
        self.assertFalse(career_agent.active_search_intent(message))

    def test_stage_routing_for_inventory_stays_at_direction(self) -> None:
        self.assertEqual(
            career_agent.stage_for("これまでの経験を整理したい", "chuto"), "自己分析・転職軸"
        )


if __name__ == "__main__":
    unittest.main()
