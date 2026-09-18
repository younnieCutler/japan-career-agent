import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


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
            ("Please improve my resume", "応募基盤・職務経歴書"),
            ("I need a CV", "応募基盤・職務経歴書"),
            ("Draft my cover letter", "応募基盤・職務経歴書"),
            ("Prepare an entry sheet", "応募基盤・職務経歴書"),
            ("Find open roles for me", "求人探索・候補整理"),
            ("Search job postings", "求人探索・候補整理"),
            ("I want to research companies", "企業研究・JD分析"),
            ("Let's do company research", "企業研究・JD分析"),
            ("I need job research", "企業研究・JD分析"),
            ("Help me prepare for an interview", "面接・選考"),
            ("Interview prep for tomorrow", "面接・選考"),
            ("I received a job offer", "内定・条件交渉"),
            ("Schedule the offer meeting", "内定・条件交渉"),
            ("I need to resign", "退職・引き継ぎ"),
            ("My start date is set", "入社準備・オンボーディング"),
            ("Onboarding plan", "入社準備・オンボーディング"),
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
        self.assertIsNone(career_agent.infer_track("SPI3 practice"))

    def test_flow_aliases_cover_common_english_requests(self) -> None:
        reference = career_agent.load_flow_reference()
        cases = (
            ("I am updating my resume", "base_documents"),
            ("I am writing my CV", "base_documents"),
            ("Find open roles for me", "opportunity_discovery"),
            ("Review this job posting", "opportunity_analysis"),
            ("I want to apply", "application_selection"),
            ("My application is in screening", "application_selection"),
            ("I have an interview next week", "interview"),
            ("I need interview prep", "interview"),
            ("I need salary negotiation for this offer", "offer"),
            ("The compensation is under review", "offer"),
            ("I plan to resign", "exit"),
            ("My onboarding starts next month", "onboarding"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    career_agent.flow_phase_for(message, "chuto", {}, {}, reference), expected
                )

    def test_flow_reference_is_the_runtime_chuto_contract(self) -> None:
        reference = career_agent.load_flow_reference()
        labels = tuple(phase["label"] for phase in reference["chuto"]["phases"])
        self.assertEqual(labels, career_agent.CHUTO_STAGES)
        self.assertEqual(career_agent.PIPELINE_STAGE["求人探索・候補整理"], 2)
        self.assertEqual(career_agent.PIPELINE_STAGE["企業研究・JD分析"], 2)
        self.assertEqual(career_agent.PIPELINE_STAGE["入社準備・オンボーディング"], 7)

    def test_chuto_messages_select_one_tenshoku_reference(self) -> None:
        skills_root = ROOT / "skills"
        cases = (
            ("年収交渉をしたいが、まだオファーはありません", "references/nenshu-koushou.md"),
            ("書面のオファーと口頭説明が矛盾しています", "references/roudou-joken-review.md"),
            ("面接のお礼を送りたいが、話題のメモがありません", "references/mensetsu-follow.md"),
            ("退職したいが就業規則の予告期間は不明です", "references/enman-taishoku.md"),
            ("市場年収を知りたいが情報が古いです", "references/market-positioning-2025-2026.md"),
            ("入社手続きだけ確認したいです", "references/nyusha-teichaku.md"),
            ("面接マナーと入室方法を確認したいです", "references/mensetsu-manner.md"),
            ("退職理由を面接向けに整理したいです", "references/taishoku-riyu-reframing.md"),
            ("内定への回答期限を確認したいです", "references/naitei-taiou.md"),
            ("選考状況を一覧で追跡したいです", "references/senko-tracking.md"),
            ("面接フィードバックを次の応募に活かしたい", "references/job-search-learning-loop.md"),
        )
        for message, reference in cases:
            with self.subTest(message=message):
                context = career_agent.skill_context(
                    skills_root, career_agent.stage_for(message, "chuto"), message, "chuto"
                )
                self.assertEqual(context["skill"], "tenshoku-strategy")
                self.assertEqual(context["references"], [reference])
                self.assertTrue((skills_root / context["skill"] / reference).is_file())

    def test_specialized_existing_skills_are_on_the_main_routes(self) -> None:
        skills_root = ROOT / "skills"
        cases = (
            (
                "このJD向けの職務経歴書を作りたい",
                "career-document",
                "references/targeted-application.md",
            ),
            (
                "このJDと自分の経験を比較したい",
                "matching-simulator",
                "references/evaluation_perspectives.md",
            ),
            (
                "面接練習をしたい",
                "mock-interviewer",
                "references/session-routing.md",
            ),
            (
                "中途のSPI3対策をしたい",
                "job-seeker-agent",
                "references/tekisei-kensa.md",
            ),
        )
        for message, skill, reference in cases:
            with self.subTest(message=message):
                stage = career_agent.stage_for(message, "chuto")
                context = career_agent.skill_context(skills_root, stage, message, "chuto")
                self.assertEqual(context["skill"], skill)
                self.assertEqual(context["references"], [reference])
                self.assertTrue((skills_root / skill / reference).is_file())

    def test_message_context_precedence_is_ordered(self) -> None:
        skills_root = ROOT / "skills"
        cases = (
            ("市場年収を調べてから年収交渉したい", "references/market-positioning-2025-2026.md"),
            ("書面の労働条件とオファー面談の説明が矛盾する", "references/roudou-joken-review.md"),
            ("面接マナーより先に面接のお礼を送りたい", "references/mensetsu-follow.md"),
            ("退職理由を整理してから円満退職したい", "references/taishoku-riyu-reframing.md"),
        )
        for message, reference in cases:
            with self.subTest(message=message):
                context = career_agent.skill_context(
                    skills_root, career_agent.stage_for(message, "chuto"), message, "chuto"
                )
                self.assertEqual(context["references"], [reference])

    def test_message_context_preserves_fallbacks_and_track_boundary(self) -> None:
        skills_root = ROOT / "skills"
        offer_stage = "内定・条件交渉"
        old_call = career_agent.skill_context(skills_root, offer_stage)
        self.assertEqual(old_call["references"], ["references/naitei-taiou.md"])
        self.assertEqual(
            career_agent.skill_context(skills_root, offer_stage, "次に何をすればよいですか", "chuto"),
            old_call,
        )
        cases = (
            ("面接の回答内容を準備したい", "面接・選考", "chuto", "job-seeker-agent"),
            ("企業研究を進めたい", "企業研究・JD分析", "chuto", "kigyou-bunseki"),
            ("職務経歴書を直したい", "応募基盤・職務経歴書", "chuto", "job-seeker-agent"),
            ("年収交渉をしたい", "内々定・内定・入社準備", "shinsotsu", "job-seeker-agent"),
        )
        for message, stage, track, skill in cases:
            with self.subTest(message=message, track=track):
                self.assertEqual(
                    career_agent.skill_context(skills_root, stage, message, track)["skill"], skill
                )

    def test_message_context_reference_shape_is_validated(self) -> None:
        valid_prefix = (
            "track:\n  shinsotsu: [new grad]\n  chuto: [mid-career]\n"
            "stage_alias:\n  - alias: chuto\n    terms: [mid-career]\n"
            "flow_phase:\n  shinsotsu: []\n  chuto: []\n"
        )
        malformed = (
            "message_context: {}\n",
            "message_context:\n  - reference: references/a.md\n    terms: [salary]\n",
            "message_context:\n  - skill: tenshoku-strategy\n    terms: [salary]\n",
            "message_context:\n  - skill: tenshoku-strategy\n    reference: references/a.md\n    terms: salary\n",
        )
        with tempfile.TemporaryDirectory() as tempdir:
            routing_reference = Path(tempdir) / "routing.yml"
            for suffix in malformed:
                with self.subTest(suffix=suffix):
                    routing_reference.write_text(valid_prefix + suffix, encoding="utf-8")
                    with patch("routing.ROUTING_REFERENCE", routing_reference):
                        with self.assertRaises(career_agent.CareerError):
                            career_agent.load_routing()


class OnboardingSignalTests(unittest.TestCase):
    def test_graduation_signal_reads_only_a_stated_year(self) -> None:
        for message, expected in (
            ("27卒で就活を始めたい", 2027),
            ("2027卒です", 2027),
            ("2027年卒", 2027),
            ("2027년 졸업 예정", 2027),
            ("class of 2027", 2027),
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
        self.assertIsNone(career_agent.infer_track("SPI3対策をしたい"))

    def test_second_new_graduate_is_a_mid_career_hire(self) -> None:
        for message in ("第二新卒で転職したい", "第二新卒です", "第2新卒"):
            with self.subTest(message=message):
                self.assertEqual(career_agent.infer_track(message), "chuto")
        self.assertEqual(
            career_agent.stage_for("第二新卒で職務経歴書を作りたい", "chuto"),
            "応募基盤・職務経歴書",
        )
        self.assertEqual(career_agent.infer_track("新卒で就活を始めたい"), "shinsotsu")

    def test_explicit_stage_alias_ignores_track_only_signals(self) -> None:
        self.assertIsNone(career_agent.explicit_stage_alias("일본에서 이직 준비를 시작하고 싶어"))
        self.assertIsNone(career_agent.explicit_stage_alias("売上を30%改善した"))
        self.assertEqual(career_agent.explicit_stage_alias("職務経歴書を整理したい"), "documents")
        self.assertEqual(career_agent.explicit_stage_alias("求人を探したい"), "discover")
        self.assertEqual(career_agent.explicit_stage_alias("무슨 직무를 해야 할지 모르겠어"), "self")
        self.assertEqual(career_agent.explicit_stage_alias("면접 준비를 어떻게 할지 모르겠어"), "interview")

    def test_applying_and_reviewing_a_posting_are_separate_stages(self) -> None:
        self.assertEqual(
            career_agent.stage_for("この求人に応募できるか見たい", "chuto"), "企業研究・JD分析"
        )
        self.assertEqual(
            career_agent.stage_for("このJDと私の経験を比較したい", "chuto"), "企業研究・JD分析"
        )
        self.assertEqual(career_agent.stage_for("応募したい", "chuto"), "応募・書類選考")
        for message in (
            "이 공고에 지원하고 싶어",
            "この求人に応募したい",
            "I want to apply for this job posting",
        ):
            with self.subTest(message=message):
                self.assertEqual(career_agent.stage_for(message, "shinsotsu"), "ES・履歴書")

    def test_a_more_specific_task_named_alongside_apply_wins(self) -> None:
        cases = (
            ("応募面接", "interview"),
            ("지원 면접 준비", "interview"),
            ("application interview", "interview"),
            ("応募して企業研究もしたい", "research"),
            ("応募と内定条件", "offer"),
            ("応募して退職準備をしたい", "exit"),
            ("応募して入社準備を確認したい", "onboarding"),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(career_agent.explicit_stage_alias(message), expected)

    def test_a_clause_that_closes_a_topic_out_does_not_select_its_reference(self) -> None:
        skills_root = ROOT / "skills"
        cases = (
            ("年収交渉は不要です。入社手続きだけ確認したいです", "references/nyusha-teichaku.md"),
            ("연봉 협상은 하지 않습니다. 입사 절차만 알고 싶어요", "references/nyusha-teichaku.md"),
            ("I am not sending a thank-you email; I need the handover plan", "references/enman-taishoku.md"),
            ("円満退職の話ではなく、入社書類を進めたいです", "references/nyusha-teichaku.md"),
            ("市場年収は調べ済みです。年収交渉の進め方を教えてください", "references/nenshu-koushou.md"),
        )
        for message, reference in cases:
            with self.subTest(message=message):
                context = career_agent.skill_context(
                    skills_root, career_agent.stage_for(message, "chuto"), message, "chuto"
                )
                self.assertEqual(context["references"], [reference])

    def test_an_exclusion_marker_only_scopes_to_its_own_clause(self) -> None:
        skills_root = ROOT / "skills"
        message = "すぐ転職するつもりはありません。ただ市場年収の相場は知っておきたいです"
        context = career_agent.skill_context(
            skills_root, career_agent.stage_for(message, "chuto"), message, "chuto"
        )
        self.assertEqual(context["references"], ["references/market-positioning-2025-2026.md"])

    def test_short_ascii_terms_still_need_an_ascii_boundary(self) -> None:
        self.assertTrue(career_agent.term_present("jd", "このjdと私の経験"))
        self.assertFalse(career_agent.term_present("jd", "jda platform"))
        self.assertFalse(career_agent.term_present("es", "research"))


if __name__ == "__main__":
    unittest.main()
