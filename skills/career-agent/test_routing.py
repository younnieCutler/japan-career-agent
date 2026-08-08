import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "career-agent"))
import career_agent  # noqa: E402


class EnglishRoutingTests(unittest.TestCase):
    def test_extended_katakana_is_detected_as_japanese(self) -> None:
        self.assertEqual(career_agent.language_for("ヴ"), "ja")

    def test_stage_aliases_cover_common_english_requests(self) -> None:
        cases = (
            ("I need self-analysis", "自己分析・転職軸"),
            ("Help me understand my work style", "自己分析・転職軸"),
            ("Please improve my resume", "職務経歴書・自己PR"),
            ("I need a CV", "職務経歴書・自己PR"),
            ("Draft my cover letter", "職務経歴書・自己PR"),
            ("Prepare an entry sheet", "職務経歴書・自己PR"),
            ("I want to research companies", "業界研究・企業研究"),
            ("Let's do company research", "業界研究・企業研究"),
            ("I need job research", "業界研究・企業研究"),
            ("Help me prepare for an interview", "面接"),
            ("Interview prep for tomorrow", "面接"),
            ("I received a job offer", "内定・条件交渉"),
            ("Schedule the offer meeting", "内定・条件交渉"),
            ("I need to resign", "退職・入社準備"),
            ("My start date is set", "退職・入社準備"),
            ("Onboarding plan", "退職・入社準備"),
            ("I want a career change", "自己分析・転職軸"),
            ("I'm a mid-career hire", "自己分析・転職軸"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(career_agent.stage_for(message, "chuto"), expected)

    def test_track_aliases_cover_new_grad_and_mid_career(self) -> None:
        self.assertEqual(career_agent.infer_track("I'm a new graduate"), "shinsotsu")
        self.assertEqual(career_agent.infer_track("I'm a mid-career hire"), "chuto")
        self.assertEqual(career_agent.infer_track("I am graduating soon"), "shinsotsu")

    def test_flow_aliases_cover_common_english_requests(self) -> None:
        reference = career_agent.load_flow_reference()
        cases = (
            ("I am updating my resume", "documents"),
            ("I am writing my CV", "documents"),
            ("I want to apply", "application"),
            ("My application is in screening", "application"),
            ("I have an interview next week", "interview"),
            ("I need interview prep", "interview"),
            ("I need salary negotiation for this offer", "offer"),
            ("The compensation is under review", "offer"),
            ("I plan to resign", "exit_onboarding"),
            ("My onboarding starts next month", "exit_onboarding"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(career_agent.flow_phase_for(message, "chuto", {}, {}, reference), expected)


class OnboardingSignalTests(unittest.TestCase):
    def test_graduation_signal_reads_only_a_stated_year(self) -> None:
        for message, expected in (
            ("27卒で就活を始めたい", 2027),
            ("2027卒です", 2027),
            ("2027年卒", 2027),
            ("2027년 졸업 예정", 2027),
            ("class of 2027", 2027),
            # A year is a claim about the future; someone who already graduated has not made it.
            ("既卒です", None),
            ("第二新卒で転職したい", None),
            ("1999卒", None),
            ("売上を30%改善した", None),
        ):
            with self.subTest(message=message):
                self.assertEqual(career_agent.graduation_signal(message), expected)

    def test_stated_graduation_year_implies_the_shinsotsu_track(self) -> None:
        self.assertEqual(career_agent.infer_track("27卒です"), "shinsotsu")
        self.assertEqual(career_agent.infer_track("就活を始めたい"), "shinsotsu")
        self.assertIsNone(career_agent.infer_track("売上を30%改善した"))

    def test_explicit_stage_alias_ignores_track_only_signals(self) -> None:
        # "I am job hunting mid-career" says which track, not which task.
        self.assertIsNone(career_agent.explicit_stage_alias("일본에서 이직 준비를 시작하고 싶어"))
        self.assertIsNone(career_agent.explicit_stage_alias("売上を30%改善した"))
        self.assertEqual(career_agent.explicit_stage_alias("職務経歴書を整理したい"), "documents")
        self.assertEqual(career_agent.explicit_stage_alias("무슨 직무를 해야 할지 모르겠어"), "self")
        # A specific task outranks the fall-through direction group.
        self.assertEqual(career_agent.explicit_stage_alias("면접 준비를 어떻게 할지 모르겠어"), "interview")

    def test_applying_and_reviewing_a_posting_are_separate_stages(self) -> None:
        self.assertEqual(career_agent.stage_for("この求人に応募できるか見たい", "chuto"), "応募・書類選考")
        self.assertEqual(career_agent.stage_for("このJDと私の経験を比較したい", "chuto"), "職務経歴書・自己PR")
        self.assertEqual(career_agent.stage_for("이 공고에 지원하고 싶어", "shinsotsu"), "ES・履歴書")

    def test_short_ascii_terms_still_need_an_ascii_boundary(self) -> None:
        self.assertTrue(career_agent.term_present("jd", "このjdと私の経験"))
        self.assertFalse(career_agent.term_present("jd", "jda platform"))
        self.assertFalse(career_agent.term_present("es", "research"))


if __name__ == "__main__":
    unittest.main()
