"""Pure Career Agent vocabulary and typed data contracts.

This module intentionally has no filesystem, runtime, or import-time configuration side effects.
The dictionaries remain the serialized on-disk contract used by the existing Career Agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypedDict


class ProposalKind(StrEnum):
    EVENT = "event"
    CAREER_CONTEXT = "career_context"
    HEARTBEAT = "heartbeat"
    POSTING_CANDIDATES = "posting_candidates"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UXState(StrEnum):
    READY = "ready"
    NEEDS_CONFIRMATION = "needs_confirmation"
    REVIEW = "review"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class DecisionStatus(StrEnum):
    PROCEED = "proceed"
    REVIEW = "review"
    CONFLICT = "conflict"


class ApprovalStage(StrEnum):
    PREPARED = "prepared"
    LEDGER_WRITTEN = "ledger_written"
    STATE_WRITTEN = "state_written"
    PROJECTION_WRITTEN = "projection_written"
    COMMITTED = "committed"


@dataclass(frozen=True)
class ApprovalTransactionRecord:
    """Typed in-memory boundary for the single-slot approval journal."""

    transaction_id: str
    proposal_id: str
    proposal_kind: str
    event: dict[str, Any]
    event_fingerprint: str
    workspace: str | None
    created_at: str
    stage: ApprovalStage
    companion_event: dict[str, Any] | None = None
    companion_event_fingerprint: str | None = None
    state_version: str | None = None
    pipeline: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ApprovalTransactionRecord":
        try:
            return cls(
                transaction_id=str(value["transaction_id"]),
                proposal_id=str(value["proposal_id"]),
                proposal_kind=str(value.get("proposal_kind") or "event"),
                event=dict(value["event"]),
                event_fingerprint=str(value["event_fingerprint"]),
                companion_event=(
                    dict(value["companion_event"])
                    if isinstance(value.get("companion_event"), dict) else None
                ),
                companion_event_fingerprint=(
                    str(value["companion_event_fingerprint"])
                    if value.get("companion_event_fingerprint") else None
                ),
                workspace=str(value["workspace"]) if value.get("workspace") else None,
                created_at=str(value["created_at"]),
                stage=ApprovalStage(str(value["stage"])),
                state_version=str(value["state_version"]) if value.get("state_version") else None,
                pipeline=str(value["pipeline"]) if value.get("pipeline") else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid approval transaction record") from exc

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "version": 1,
            "transaction_id": self.transaction_id,
            "proposal_id": self.proposal_id,
            "proposal_kind": self.proposal_kind,
            "event": self.event,
            "event_fingerprint": self.event_fingerprint,
            "workspace": self.workspace,
            "created_at": self.created_at,
            "stage": self.stage.value,
        }
        if self.companion_event is not None:
            value["companion_event"] = self.companion_event
            value["companion_event_fingerprint"] = self.companion_event_fingerprint
        if self.state_version:
            value["state_version"] = self.state_version
        if self.pipeline:
            value["pipeline"] = self.pipeline
        return value


TRACKS = {"shinsotsu", "chuto"}
EVENT_STATUSES = {"draft", "confirmed", "superseded"}
# Personal fact categories an event may carry (PRD section 8). Facts extend the existing event
# ledger rather than opening a second canonical store; `superseded` above is the status this
# finally gives meaning to, derived from the forward `supersedes` link.
FACT_CATEGORIES = {
    "compensation",
    "certification",
    "language",
    "employment",
    "education",
    "role",
    "skill",
    "portfolio",
}
CAREER_STATUSES = {"active", "confirmed", "onboarding"}
# The event type that records something that happened at the job the user already has. It is a
# type on the existing ledger rather than a second store: the approval gate, the idempotent
# append, supersession, and the numeric-claim rule below all apply to it unchanged.
WORK_EVENT_TYPE = "work_event"
# A project is the context a work event happened in, not evidence about the person. It is another
# type on the same ledger for the same reason work events are: durability, the approval gate, and
# append-only history come with it, and a project's later state is a projection over its events
# rather than a second store to keep in sync.
#
# `project_id` is minted once and reused by every later event about that project, so the record
# accumulates the way the user fills it in. No counter: a sequential PRJ-001 would need a shared
# allocator, which is the one thing an append-only ledger should not need.
PROJECT_EVENT_TYPE = "project"
PROJECT_STATUSES = {"active", "completed", "paused", "unknown"}
# The place an experience happened in: a company, a university, a part-time shop, a club, a
# personal effort. Another type on the same ledger for the same reason projects are, and its later
# state is a projection over its events rather than a second store.
#
# The `experience_` prefix is deliberate. `career_context` is already the anchors/theme/values
# payload and `CONTEXT_KINDS` below already names the Vault note kinds, so a bare `context` would
# collide with two existing meanings and the collision would read as a typo rather than a bug.
EXPERIENCE_CONTEXT_EVENT_TYPE = "experience_context"
EXPERIENCE_CONTEXT_KINDS = {
    "company",
    "freelance",
    "university",
    "graduate_school",
    "internship_organization",
    "part_time_workplace",
    "club",
    "student_organization",
    "volunteer_organization",
    "personal",
    "open_source",
    "other",
}
WORK_EXPERIENCE_CONTEXT_KINDS = frozenset({
    "company", "freelance", "internship_organization", "part_time_workplace",
})
# Evidence about something that happened outside a job: a seminar, a thesis, a club, a volunteer
# shift, a personal project. It carries the same payload as a work event -- role, problem, actions,
# individual contribution, team result, metrics and confidentiality describe a ゼミ project as well
# as they describe a release -- so the two share one validator.
#
# It is nevertheless a separate type. Storing a university seminar as a `work_event` would say the
# user was employed there, and every work-scoped read (`readiness.recent_work_evidence`,
# `weekly-review`, career-maintenance, which is explicitly the while-employed workflow) would start
# returning coursework as work history.
EXPERIENCE_EVENT_TYPE = "experience_event"
EVIDENCE_EVENT_TYPES = {WORK_EVENT_TYPE, EXPERIENCE_EVENT_TYPE}
# A correction is an append-only audit link, never a rewrite of the evidence it retires.  The
# replacement remains an ordinary evidence event; this row only names the two immutable ids.
EXPERIENCE_SUPERSESSION_EVENT_TYPE = "experience_supersession"
# Which kind of experience a piece of evidence belongs to. `project` is one entry among many on
# purpose: regular operations, an incident, a thesis and a part-time shift are experiences too, and
# a model that only had projects would push the user to describe their work as one.
EXPERIENCE_KINDS = {
    "project",
    "recurring_work",
    "improvement",
    "incident",
    "research",
    "academic_work",
    "internship",
    "part_time_work",
    "extracurricular",
    "leadership",
    "mentoring",
    "customer_support",
    "operations",
    "personal_project",
    "open_source_contribution",
    "other",
}
# Career readiness and job-search intent are separate concepts, so they are separate axes.
# `employment_status` and `job_search` are the user's own declaration and live in the profile;
# only the dedicated `set-employment-status` / `set-job-search` commands write them. Every other
# code path reads them. `career_mode` is projected from events by apply_event_to_state().
EMPLOYMENT_STATUSES = {"employed", "unemployed", "student", "other", "unknown"}
JOB_SEARCH_STATES = {"off", "on"}
# The two axes together, so the parser, the diagnostics and the writer read one definition instead
# of three copies that can disagree about which values are allowed.
PROFILE_AXES = {
    "job_search": JOB_SEARCH_STATES,
    "employment_status": EMPLOYMENT_STATUSES,
}
CAREER_MODES = {"maintenance", "opportunity_review", "active_search", "transition"}
# A work event's confidentiality review answers "may this leave the vault", not "is this true".
EXTERNAL_USE_STATES = {"allowed", "blocked", "unknown"}
# The outcome answer is independent from the optional metric list. A qualitative result, an
# explicitly unmeasured result, and an unknown result are all honest completed answers; only the
# quantitative state implies that metrics should exist.
OUTCOME_STATES = {"quantitative", "qualitative", "not_measured", "unknown"}
USER_CONFIRMATION_EVIDENCE = "user_confirmation"
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
# How an event says "this came from that imported private document". The `document_id`
# alone: the registry already maps it to a digest and a storage path, and a copy of either
# here would go stale the moment the registry changes.
DOCUMENT_EVIDENCE_PREFIX = "private-document:"


def document_evidence_ids(evidence: Any) -> list[str]:
    """The document ids an evidence list claims, in order and without duplicates."""
    seen: list[str] = []
    for item in evidence or []:
        if not isinstance(item, str) or not item.startswith(DOCUMENT_EVIDENCE_PREFIX):
            continue
        document_id = item[len(DOCUMENT_EVIDENCE_PREFIX):].strip()
        if document_id and document_id not in seen:
            seen.append(document_id)
    return seen
def job_search_of(profile: dict[str, Any]) -> str:
    """The user's declared job-search intent, `off` until they say otherwise.

    A missing or unreadable key is `off`, never `on`: an absent declaration is not permission to
    treat someone as actively job hunting. Every reader goes through here so the profile and the
    projector cannot disagree about what a blank field means.
    """
    value = str(profile.get("job_search") or "").strip().lower()
    return value if value in JOB_SEARCH_STATES else "off"


def employment_status_of(profile: dict[str, Any]) -> str:
    """The user's declared employment status; missing stays `unknown`, never an inferred value.

    This is the user's current declaration. The dated `employment` facts on the event ledger are a
    separate history with their own supersession, and the two are never merged.
    """
    value = str(profile.get("employment_status") or "").strip().lower()
    return value if value in EMPLOYMENT_STATUSES else "unknown"


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
    """A user-correctable Career Agent contract or lifecycle error.

    ``message`` remains the historical string representation.  The optional metadata gives the
    CLI UX adapter a stable way to describe an expected blocker without changing existing callers
    that only catch the exception or compare ``str(exc)``.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        retryable: bool = True,
        details: dict[str, Any] | None = None,
        state_changed: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = details or {}
        self.state_changed = state_changed


class Event(TypedDict, total=False):
    id: str
    # None only for WORK_EVENT_TYPE: a work event records what happened at the current job, which
    # belongs to no hiring-market track and no transition stage. validate_event() enforces that.
    track: str | None
    stage: str | None
    flow_phase: str | None
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
    work_event: dict[str, Any]
    # The same payload a work event carries, for an experience that did not happen at a job.
    # Separate key rather than a reused `work_event` one: a reader that finds `work_event` on a
    # university record would be right to read it as employment.
    experience: dict[str, Any]
    experience_context: dict[str, Any]
    project: dict[str, Any]
    # The workflow intent the user stated in the turn that produced this event, when they stated
    # one. Absent is the normal case and means "leave the mode where it is".
    career_mode: str


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
    career_mode: str
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
    recovered: bool
    event: Event
    proposal: Proposal
    version: str
    pipeline: str
    message: str


class ErrorResult(TypedDict, total=False):
    ok: bool
    error: str
    error_code: str
    retryable: bool
    details: dict[str, Any]
    state_changed: bool
    ux: dict[str, Any]


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
        # Maintenance is the resting state: a user keeps career evidence current whether or not
        # they are looking. Nothing here implies an intention to leave.
        "career_mode": "maintenance",
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
