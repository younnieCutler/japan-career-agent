"""Deterministic user-facing language and domain terminology catalog."""

from __future__ import annotations

from typing import Any


DEFAULT_LANGUAGE = "ko"
SUPPORTED_LANGUAGES = ("ko", "ja", "en")


def _domain_token(value: Any) -> str:
    """Normalize presentation lookup only; serialized values are never rewritten."""
    return str(value).strip().casefold().replace(" ", "_")


_DOMAIN_ROWS: dict[str, dict[str, tuple[str, str, str]]] = {
    "fact_state": {
        "unknown": ("확인되지 않음", "未確認", "Unknown"),
        "confirmed": ("확인됨", "確認済み", "Confirmed"),
        "conflict": ("정보 충돌", "情報の矛盾", "Conflicting information"),
        "partial": ("일부 확인", "一部確認", "Partially confirmed"),
        "stale": ("재확인 필요", "要再確認", "Needs rechecking"),
        "invalid": ("사용할 수 없음", "無効", "Invalid"),
    },
    "decision": {
        "proceed": ("진행 가능", "続行可能", "Proceed"),
        "review": ("검토 필요", "要確認", "Review needed"),
        "conflict": ("조건 충돌", "条件の矛盾", "Condition conflict"),
    },
    "requirement": {
        "matched": ("요건 충족", "要件充足", "Requirement met"),
        "missing": ("요건 미충족", "要件不足", "Requirement not met"),
        "unknown": ("확인되지 않음", "未確認", "Unknown"),
        "required": ("필수", "必須", "Required"),
        "preferred": ("우대", "歓迎", "Preferred"),
    },
    "track": {
        "shinsotsu": ("신졸", "新卒", "New graduate"),
        "chuto": ("경력채용", "中途採用", "Mid-career hiring"),
    },
    "status_stage": {
        "0": ("자기분석", "自己分析", "Self analysis"),
        "1": ("서류 준비", "書類準備", "Document preparation"),
        "2": ("기업 조사", "企業研究", "Company research"),
        "3": ("지원·서류전형", "応募・書類", "Application and screening"),
        "4": ("면접", "面接", "Interview"),
        "5": ("내정", "内定", "Offer"),
        "6": ("퇴사 협의", "退職交渉", "Resignation negotiation"),
        "7": ("입사", "入社", "Joining"),
    },
    "rule_status": {
        "candidate": ("후보 규칙", "候補ルール", "Candidate rule"),
        "active": ("적용 중", "適用中", "Active"),
        "retired": ("사용 종료", "廃止", "Retired"),
    },
    "rule_source": {
        "self_authored": ("직접 작성", "自分で作成", "Self-authored"),
        "derived_from_rejections": ("불합격 기록에서 도출", "不採用結果から導出", "Derived from rejections"),
        "observed_workflow": ("전형 이력에서 도출", "選考履歴から導出", "Derived from workflow history"),
    },
    "model_version": {
        "evidence_based_v3": ("근거 기반 판정 v3", "根拠ベース判定 v3", "Evidence-based assessment v3"),
        "legacy_v1": ("이전 실험 모델 v1", "旧実験モデル v1", "Legacy experimental model v1"),
    },
}

DOMAIN_ROWS = {
    namespace: {_domain_token(value): labels for value, labels in values.items()}
    for namespace, values in _DOMAIN_ROWS.items()
}
_DOMAIN_LANGUAGE_INDEX = {"ko": 0, "ja": 1, "en": 2}


def normalize_language(value: Any) -> str:
    raw = str(value or "").casefold().replace("_", "-")
    base = raw.split("-", 1)[0]
    return base if base in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def domain_label(language: Any, namespace: str, value: Any) -> str:
    """Translate one canonical value at a human boundary; unknown values never leak raw."""
    locale = normalize_language(language)
    try:
        labels = DOMAIN_ROWS[str(namespace)][_domain_token(value)]
    except KeyError as exc:
        raise KeyError(f"missing domain translation: {namespace}.{_domain_token(value)}") from exc
    return labels[_DOMAIN_LANGUAGE_INDEX[locale]]


def validate_domain_catalog() -> list[str]:
    errors: list[str] = []
    for namespace, values in DOMAIN_ROWS.items():
        if not values:
            errors.append(f"empty namespace: {namespace}")
        for value, labels in values.items():
            if len(labels) != len(SUPPORTED_LANGUAGES) or not all(
                isinstance(label, str) and label for label in labels
            ):
                errors.append(f"invalid labels: {namespace}.{value}")
    return errors
