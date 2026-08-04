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


if __name__ == "__main__":
    unittest.main()
