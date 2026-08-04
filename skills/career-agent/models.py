"""Pure Career Agent vocabulary and typed data contracts.

This module intentionally has no filesystem, runtime, or import-time configuration side effects.
The dictionaries remain the serialized on-disk contract used by the existing Career Agent.
"""

from __future__ import annotations

from typing import Any, TypedDict


TRACKS = {"shinsotsu", "chuto"}
EVENT_STATUSES = {"draft", "confirmed", "superseded"}
CAREER_STATUSES = {"active", "confirmed", "onboarding"}
VAULT_DIRECTORIES = (
    "00-control",
    "01-capture",
    "02-state",
    "03-active",
    "04-evidence",
    "05-playbooks",
    "06-reference",
    "07-archive",
)
CONTEXT_KINDS = {"active", "evidence", "playbook", "reference"}
TRUSTED_SOURCE_TYPES = {"official", "personal_evidence", "curated_practice"}
REQUIRED_CONTEXT_METADATA = {"agent_read", "agent_scope", "status", "source_type", "reviewed_on"}
UNTRUSTED_DATA_MARKER = "untrusted_career_data"
CAREER_CONTEXT_FIELDS = ("career_anchors", "career_theme", "energy_map", "career_values")
SHINSOTSU_STAGES = (
    "自己分析・就活軸",
    "学チカ・自己PR素材",
    "業界研究・企業研究",
    "ES・履歴書",
    "適性検査（SPI3）",
    "書類選考・面接",
    "内々定・内定・入社準備",
)
CHUTO_STAGES = (
    "自己分析・転職軸",
    "職務経歴書・自己PR",
    "業界研究・企業研究",
    "応募・書類選考",
    "面接",
    "内定・条件交渉",
    "退職・入社準備",
)
# Agent stage → the 0–7 Japan market stage map stored in data/pipeline.yml.
PIPELINE_STAGE = {
    "自己分析・就活軸": 0,
    "自己分析・転職軸": 0,
    "学チカ・自己PR素材": 1,
    "職務経歴書・自己PR": 1,
    "ES・履歴書": 1,
    "業界研究・企業研究": 2,
    "応募・書類選考": 3,
    "適性検査（SPI3）": 3,
    "面接": 4,
    "書類選考・面接": 4,
    "内定・条件交渉": 5,
    "内々定・内定・入社準備": 5,
    "退職・入社準備": 6,
}
SKILL_BY_STAGE = {
    "自己分析・就活軸": "jiko-bunseki",
    "自己分析・転職軸": "jiko-bunseki",
    "学チカ・自己PR素材": "job-seeker-agent",
    "職務経歴書・自己PR": "job-seeker-agent",
    "業界研究・企業研究": "kigyou-bunseki",
    "ES・履歴書": "job-seeker-agent",
    "適性検査（SPI3）": "job-seeker-agent",
    "書類選考・面接": "job-seeker-agent",
    "応募・書類選考": "matching-simulator",
    "面接": "job-seeker-agent",
    "内々定・内定・入社準備": "job-seeker-agent",
    "内定・条件交渉": "tenshoku-strategy",
    "退職・入社準備": "tenshoku-strategy",
}
REFERENCE_BY_STAGE = {
    "自己分析・就活軸": ("references/questions.md",),
    "自己分析・転職軸": ("references/questions.md",),
    "学チカ・自己PR素材": ("references/shinsotsu.md",),
    "職務経歴書・自己PR": ("references/shokumukeireki-saigensei.md",),
    "業界研究・企業研究": ("references/frameworks.md",),
    "ES・履歴書": ("references/shinsotsu.md",),
    "適性検査（SPI3）": ("references/frameworks.md",),
    "書類選考・面接": ("references/mensetsu-rounds.md",),
    "応募・書類選考": ("references/senko-tracking.md",),
    "面接": ("references/mensetsu-rounds.md",),
    "内々定・内定・入社準備": ("references/naitei-taiou.md",),
    "内定・条件交渉": ("references/naitei-taiou.md",),
    "退職・入社準備": ("references/nyusha-teichaku.md",),
}
REQUIRED_EVENT_FIELDS = (
    "id",
    "track",
    "stage",
    "flow_phase",
    "type",
    "occurred_at",
    "title",
    "summary",
    "evidence",
    "source",
    "next_action",
    "deadline",
    "status",
)


class CareerError(ValueError):
    """A user-correctable Career Agent contract or lifecycle error."""


class Event(TypedDict, total=False):
    id: str
    track: str
    stage: str
    flow_phase: str
    type: str
    occurred_at: str
    title: str
    summary: str
    evidence: list[str]
    source: str
    next_action: str | None
    deadline: str | None
    status: str
    company: str
    compensation: int | float
    currency: str


class Proposal(TypedDict, total=False):
    id: str
    kind: str
    status: str
    created_at: str
    updated_at: str
    event: Event
    report: dict[str, Any]
    resolution: dict[str, Any]


class CareerState(TypedDict, total=False):
    track: str | None
    stage: str | None
    flow_phase: str | None
    career_status: str
    open_actions: list[dict[str, Any]]
    deadlines: list[dict[str, Any]]
    last_event_id: str | None
    updated_at: str | None
    version: str | None


class RoutingResult(TypedDict, total=False):
    language: str
    track: str
    stage: str
    flow_phase: str


class LifecycleResult(TypedDict, total=False):
    approved: bool
    applied: bool
    event: Event
    proposal: Proposal
    version: str
    pipeline: str


class ErrorResult(TypedDict, total=False):
    ok: bool
    error: str
    error_code: str
    retryable: bool
    state_changed: bool


def as_text(value: Any) -> str:
    """Render arbitrary evidence for deterministic claim checks."""
    import json

    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def default_state() -> CareerState:
    return {
        "track": None,
        "stage": None,
        "flow_phase": None,
        "career_status": "active",
        "open_actions": [],
        "deadlines": [],
        "last_event_id": None,
        "updated_at": None,
        "version": None,
    }


def normalized_state(value: dict[str, Any]) -> CareerState:
    state = default_state()
    state.update({key: item for key, item in value.items() if key in state})
    for key in ("track", "stage", "flow_phase", "last_event_id", "updated_at", "version"):
        if state.get(key) == "":
            state[key] = None
    return state
