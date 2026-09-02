"""Feature-owned GUI copy for consequential application judgment.

The main localization catalog is intentionally stable and broad.  This small catalog belongs to the
L3 judgment workflow and is merged at the GUI message boundary; all three locales must expose the
same keys.
"""

from __future__ import annotations


JUDGMENT_TEXT: dict[str, dict[str, str]] = {
    "ko": {
        "judgment.title": "지원 판단",
        "judgment.intro": "중요한 지원 결정은 AI 의견을 보기 전에 먼저 내 판단을 남깁니다.",
        "judgment.question": "지금 이 포지션에 지원하는 것에 대해 어떻게 생각하나요?",
        "judgment.help": "정답을 맞히는 단계가 아닙니다. 지금의 판단을 남긴 뒤 Agent 분석과 차이를 확인합니다.",
        "judgment.reason": "가장 큰 이유 (선택)",
        "judgment.submit_initial": "내 판단 저장",
        "judgment.choice.proceed": "진행하고 싶음",
        "judgment.choice.hold": "보류",
        "judgment.choice.stop": "진행하지 않음",
        "judgment.choice.unknown": "아직 모르겠음",
        "judgment.saving": "판단 저장 중",
        "judgment.save_failed": "판단을 저장하지 못했습니다. Agent 분석은 아직 표시하지 않았습니다.",
        "judgment.initial_title": "내 최초 판단",
        "judgment.waiting_title": "Agent 분석 대기 중",
        "judgment.waiting_body": "최초 판단은 저장되었습니다. Host가 이 판단에 대한 Agent 분석을 기록하면 비교 결과가 표시됩니다.",
        "judgment.agent_title": "Agent 판단",
        "judgment.confidence": "확신도",
        "judgment.reasons": "판단 이유",
        "judgment.unknowns": "아직 확인할 내용",
        "judgment.evidence_count": "분석에 연결된 근거 참조 {count}개",
        "judgment.no_reasons": "별도 이유 없음",
        "judgment.no_unknowns": "추가로 표시된 미확인 항목 없음",
        "judgment.aligned": "내 최초 판단과 Agent 판단이 같은 방향입니다.",
        "judgment.diverged": "내 최초 판단과 Agent 판단이 다릅니다. 차이를 확인한 뒤 최종 판단을 정하세요.",
        "judgment.final_title": "최종 판단",
        "judgment.final_intro": "Agent 의견을 확인한 뒤에도 결정은 내가 내립니다.",
        "judgment.final_reason": "최종 판단 이유 (선택)",
        "judgment.submit_final": "최종 판단 저장",
        "judgment.final_saved": "최종 판단이 저장되었습니다.",
        "judgment.outcome_title": "나중에 실제 결과 기록",
        "judgment.outcome_intro": "결과가 생긴 뒤에만 기록합니다. 아직 알 수 없으면 그대로 두세요.",
        "judgment.outcome_reason": "결과 메모 (선택)",
        "judgment.submit_outcome": "결과 저장",
        "judgment.outcome_saved": "결과가 저장되었습니다.",
        "judgment.new_round": "새 판단 시작",
    },
    "ja": {
        "judgment.title": "応募の判断",
        "judgment.intro": "重要な応募判断では、AIの意見を見る前にまず自分の判断を残します。",
        "judgment.question": "現時点で、このポジションへの応募をどう考えていますか？",
        "judgment.help": "正解を当てる段階ではありません。今の判断を残した後、Agentの分析との差を確認します。",
        "judgment.reason": "最も大きな理由（任意）",
        "judgment.submit_initial": "自分の判断を保存",
        "judgment.choice.proceed": "進めたい",
        "judgment.choice.hold": "保留",
        "judgment.choice.stop": "進めない",
        "judgment.choice.unknown": "まだ分からない",
        "judgment.saving": "判断を保存中",
        "judgment.save_failed": "判断を保存できませんでした。Agent分析はまだ表示していません。",
        "judgment.initial_title": "最初の自分の判断",
        "judgment.waiting_title": "Agent分析を待っています",
        "judgment.waiting_body": "最初の判断は保存済みです。Hostがこの判断へのAgent分析を記録すると比較結果を表示します。",
        "judgment.agent_title": "Agentの判断",
        "judgment.confidence": "確信度",
        "judgment.reasons": "判断理由",
        "judgment.unknowns": "まだ確認が必要な点",
        "judgment.evidence_count": "分析に接続された根拠参照 {count}件",
        "judgment.no_reasons": "追加の理由なし",
        "judgment.no_unknowns": "追加の未確認項目なし",
        "judgment.aligned": "最初の自分の判断とAgentの判断は同じ方向です。",
        "judgment.diverged": "最初の自分の判断とAgentの判断が異なります。差を確認してから最終判断を決めてください。",
        "judgment.final_title": "最終判断",
        "judgment.final_intro": "Agentの意見を確認した後も、決定するのは自分です。",
        "judgment.final_reason": "最終判断の理由（任意）",
        "judgment.submit_final": "最終判断を保存",
        "judgment.final_saved": "最終判断を保存しました。",
        "judgment.outcome_title": "後から実際の結果を記録",
        "judgment.outcome_intro": "結果が分かった後だけ記録します。まだ分からない場合はそのままにしてください。",
        "judgment.outcome_reason": "結果メモ（任意）",
        "judgment.submit_outcome": "結果を保存",
        "judgment.outcome_saved": "結果を保存しました。",
        "judgment.new_round": "新しい判断を開始",
    },
    "en": {
        "judgment.title": "Application judgment",
        "judgment.intro": "For consequential application decisions, record your own view before seeing the AI view.",
        "judgment.question": "Right now, how do you feel about applying for this position?",
        "judgment.help": "This is not a test. Record your current judgment first, then compare it with the Agent assessment.",
        "judgment.reason": "Main reason (optional)",
        "judgment.submit_initial": "Save my judgment",
        "judgment.choice.proceed": "I want to proceed",
        "judgment.choice.hold": "Hold",
        "judgment.choice.stop": "Do not proceed",
        "judgment.choice.unknown": "I do not know yet",
        "judgment.saving": "Saving judgment",
        "judgment.save_failed": "The judgment could not be saved. The Agent assessment is still hidden.",
        "judgment.initial_title": "My initial judgment",
        "judgment.waiting_title": "Waiting for Agent assessment",
        "judgment.waiting_body": "Your initial judgment is saved. The comparison appears after the Host records an Agent assessment for this decision.",
        "judgment.agent_title": "Agent judgment",
        "judgment.confidence": "Confidence",
        "judgment.reasons": "Reasons",
        "judgment.unknowns": "Still unknown",
        "judgment.evidence_count": "{count} evidence reference(s) attached to the assessment",
        "judgment.no_reasons": "No additional reasons recorded",
        "judgment.no_unknowns": "No additional unknowns recorded",
        "judgment.aligned": "Your initial judgment and the Agent judgment point in the same direction.",
        "judgment.diverged": "Your initial judgment and the Agent judgment differ. Review the difference before making the final decision.",
        "judgment.final_title": "Final judgment",
        "judgment.final_intro": "The Agent can advise, but the final decision remains yours.",
        "judgment.final_reason": "Reason for final judgment (optional)",
        "judgment.submit_final": "Save final judgment",
        "judgment.final_saved": "Final judgment saved.",
        "judgment.outcome_title": "Record what happened later",
        "judgment.outcome_intro": "Record an outcome only after one exists. Leave it open while the result is still unknown.",
        "judgment.outcome_reason": "Outcome note (optional)",
        "judgment.submit_outcome": "Save outcome",
        "judgment.outcome_saved": "Outcome saved.",
        "judgment.new_round": "Start a new judgment",
    },
}


def _normalize_language(language: object) -> str:
    raw = str(language or "").casefold().replace("_", "-")
    base = raw.split("-", 1)[0]
    return base if base in JUDGMENT_TEXT else "ko"


def judgment_messages(language: object) -> dict[str, str]:
    return dict(JUDGMENT_TEXT[_normalize_language(language)])


def validate_judgment_messages() -> list[str]:
    expected = set(JUDGMENT_TEXT["ko"])
    return [locale for locale, rows in JUDGMENT_TEXT.items() if set(rows) != expected]
