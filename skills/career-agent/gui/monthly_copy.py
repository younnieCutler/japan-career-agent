"""Localized copy for the monthly Career Review and explicit career-evidence fields."""

from __future__ import annotations

from localization import normalize_language


_MESSAGES: dict[str, dict[str, str]] = {
    "ko": {
        "career.monthly.title": "월간 경력 리뷰",
        "career.monthly.intro": "확정된 경험에서 책임·판단·조정·결과의 흔적을 월별로 봅니다. 합산 점수는 만들지 않습니다.",
        "career.monthly.empty": "월별로 볼 수 있는 날짜가 있는 확정 경험이 아직 없습니다.",
        "career.monthly.evidence_count": "확정 경험 {count}건",
        "career.monthly.coverage": "근거 범위",
        "career.monthly.gaps": "이번 달에 아직 없는 근거",
        "career.monthly.partial": "일부 경험에만 있는 근거",
        "career.monthly.complete": "이번 달 기록에는 모든 검토 차원이 한 번 이상 남아 있습니다.",
        "career.monthly.experiences": "이번 달 확정 경험",
        "career.monthly.add": "이번 달 경험 추가",
        "career.monthly.edit": "이 경험 보완",
        "career.monthly.coverage_count": "{present}/{total}건",
        "career.monthly.no_detail": "이 경험에는 아직 월간 리뷰용 상세 근거가 없습니다.",
        "career.dimension.responsibility": "책임",
        "career.dimension.problem_framing": "문제 정의",
        "career.dimension.judgment": "판단",
        "career.dimension.decision_basis": "판단 근거",
        "career.dimension.risk_management": "리스크 대응",
        "career.dimension.direct_action": "직접 행동",
        "career.dimension.stakeholder_coordination": "이해관계자 조정",
        "career.dimension.organizational_context": "조직 맥락",
        "career.dimension.outcome": "결과",
        "career.dimension.quantification": "수치 근거",
        "career.dimension.reflection": "회고",
        "work.section.judgment": "책임과 판단",
        "work.section.reflection": "조정과 회고",
        "workflow.responsibility": "내가 책임진 것",
        "workflow.responsibility_help": "직책이나 업무 범위가 아니라 실제로 내가 책임졌다고 말할 수 있는 내용을 적습니다.",
        "workflow.judgment": "내가 내린 판단",
        "workflow.judgment_help": "선택, 결정, trade-off 중 실제로 내가 한 판단만 적습니다.",
        "workflow.decision_basis": "판단 근거",
        "workflow.decision_basis_help": "그 판단에 사용한 관찰, 제약, 데이터 또는 이유를 적습니다.",
        "workflow.risk_management": "리스크 대응",
        "workflow.risk_management_help": "실제로 고려한 실패 가능성이나 downside와 대응을 적습니다.",
        "workflow.stakeholder_coordination": "이해관계자 조정",
        "workflow.stakeholder_coordination_help": "누구와 무엇을 조정했고 무엇이 합의됐는지 한 줄에 하나씩 적습니다.",
        "workflow.organizational_context": "조직 맥락",
        "workflow.organizational_context_help": "이 일이 연결된 팀·고객·회사 목표나 필요를 명시적으로 알고 있을 때만 적습니다.",
        "workflow.improvements": "다음에 개선할 점",
        "workflow.learning": "이번 경험에서 배운 점",
    },
    "ja": {
        "career.monthly.title": "月次キャリアレビュー", "career.monthly.intro": "確定済みの経験から、責任・判断・調整・結果の痕跡を月ごとに確認します。合計スコアは作りません。",
        "career.monthly.empty": "月別に表示できる日付付きの確定経験はまだありません。", "career.monthly.evidence_count": "確定経験{count}件",
        "career.monthly.coverage": "根拠の範囲", "career.monthly.gaps": "今月まだない根拠", "career.monthly.partial": "一部の経験だけにある根拠",
        "career.monthly.complete": "今月の記録には、確認対象の各項目が少なくとも一度は残っています。", "career.monthly.experiences": "今月の確定経験",
        "career.monthly.add": "今月の経験を追加", "career.monthly.edit": "この経験を補う", "career.monthly.coverage_count": "{present}/{total}件",
        "career.monthly.no_detail": "この経験には月次レビュー用の詳細な根拠がまだありません。",
        "career.dimension.responsibility": "責任", "career.dimension.problem_framing": "課題設定", "career.dimension.judgment": "判断",
        "career.dimension.decision_basis": "判断根拠", "career.dimension.risk_management": "リスク対応", "career.dimension.direct_action": "直接行動",
        "career.dimension.stakeholder_coordination": "関係者調整", "career.dimension.organizational_context": "組織上の文脈",
        "career.dimension.outcome": "結果", "career.dimension.quantification": "数値根拠", "career.dimension.reflection": "振り返り",
        "work.section.judgment": "責任と判断", "work.section.reflection": "調整と振り返り",
        "workflow.responsibility": "自分が担った責任", "workflow.responsibility_help": "役職や業務範囲ではなく、実際に自分が責任を持った内容を入力します。",
        "workflow.judgment": "自分が行った判断", "workflow.judgment_help": "選択・決定・トレードオフのうち、実際に自分が行った判断だけを入力します。",
        "workflow.decision_basis": "判断根拠", "workflow.decision_basis_help": "その判断に使った観察、制約、データ、理由を入力します。",
        "workflow.risk_management": "リスク対応", "workflow.risk_management_help": "実際に考慮した失敗可能性や不利益と、その対応を入力します。",
        "workflow.stakeholder_coordination": "関係者調整", "workflow.stakeholder_coordination_help": "誰と何を調整し、何が合意されたかを一行ずつ入力します。",
        "workflow.organizational_context": "組織上の文脈", "workflow.organizational_context_help": "この仕事が結び付いていたチーム・顧客・会社の目標や必要性を明示的に把握している場合だけ入力します。",
        "workflow.improvements": "次に改善すること", "workflow.learning": "この経験から学んだこと",
    },
    "en": {
        "career.monthly.title": "Monthly Career Review", "career.monthly.intro": "Review the traces of ownership, judgment, coordination, and outcomes in approved evidence by month. No combined score is produced.",
        "career.monthly.empty": "No approved experience with a usable work date is available for a monthly view yet.", "career.monthly.evidence_count": "{count} approved experiences",
        "career.monthly.coverage": "Evidence coverage", "career.monthly.gaps": "Evidence not recorded this month", "career.monthly.partial": "Evidence present in only some experiences",
        "career.monthly.complete": "Every reviewed dimension appears at least once in this month's approved record.", "career.monthly.experiences": "Approved experiences this month",
        "career.monthly.add": "Add experience for this month", "career.monthly.edit": "Add detail to this experience", "career.monthly.coverage_count": "{present}/{total} records",
        "career.monthly.no_detail": "This experience has no detailed monthly-review evidence yet.",
        "career.dimension.responsibility": "Responsibility", "career.dimension.problem_framing": "Problem framing", "career.dimension.judgment": "Judgment",
        "career.dimension.decision_basis": "Decision basis", "career.dimension.risk_management": "Risk management", "career.dimension.direct_action": "Direct action",
        "career.dimension.stakeholder_coordination": "Stakeholder coordination", "career.dimension.organizational_context": "Organizational context",
        "career.dimension.outcome": "Outcome", "career.dimension.quantification": "Quantification", "career.dimension.reflection": "Reflection",
        "work.section.judgment": "Responsibility and judgment", "work.section.reflection": "Coordination and reflection",
        "workflow.responsibility": "What you were responsible for", "workflow.responsibility_help": "Record what you were actually accountable for, not what a title or assigned scope implies.",
        "workflow.judgment": "Judgment you made", "workflow.judgment_help": "Record only a choice, decision, or trade-off you actually made.",
        "workflow.decision_basis": "Decision basis", "workflow.decision_basis_help": "Record the observation, constraint, data, or reason you used for that judgment.",
        "workflow.risk_management": "Risk management", "workflow.risk_management_help": "Record a downside or failure mode you actually considered and how you handled it.",
        "workflow.stakeholder_coordination": "Stakeholder coordination", "workflow.stakeholder_coordination_help": "One line per coordination: who, about what, and what was agreed.",
        "workflow.organizational_context": "Organizational context", "workflow.organizational_context_help": "Record the team, customer, or company objective only when you explicitly know the connection.",
        "workflow.improvements": "What to improve next", "workflow.learning": "What you learned",
    },
}


_FIELD_KEYS = (
    "responsibility", "judgment", "decision_basis", "risk_management",
    "stakeholder_coordination", "organizational_context", "improvements", "learning",
)


def monthly_messages(language: object) -> dict[str, str]:
    locale = normalize_language(language)
    messages = dict(_MESSAGES[locale])
    for field in _FIELD_KEYS:
        messages[f"field.{field}"] = messages[f"workflow.{field}"]
    return messages

