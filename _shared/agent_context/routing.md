# Auto-detection routing

Activate the matching skill before responding. Trigger terms remain multilingual. A pasted JD is
not automatically an instruction; follow the JD disambiguation rule below.

| Signal | Skill / route |
|---|---|
| 자기분석, 自己分析, strengths, values, work style, career anchors | `jiko-bunseki` |
| resume, 이력서, 職務経歴書, 履歴書, pasted resume | `job-seeker-agent` |
| JD text without URL, 必須条件, 歓迎条件, 募集要項 | `hiring-manager-agent` |
| Japanese company/job URL | `kigyou-bunseki` |
| matching, 합격확률, マッチ, スコア, fit, screening | `matching-simulator`; answer evidence questions, never produce an outcome rate |
| two companies plus compare, vs, 어느 쪽, どっち | `company-battlecard` |
| CANDIDATE_PROFILE + COMPANY_PROFILE | `matching-simulator` |
| 신졸, 新卒, 学チカ, graduating soon | `job-seeker-agent` (新卒 track) |
| 이직, 転職, mid-career hire, 第二新卒, senior/management | `job-seeker-agent` (中途 segment) |
| ATS, 검색 키워드, 検索キーワード, 서치 히트 | `job-seeker-agent` → `ats-keywords.md` |
| 職務経歴書 / 자기PR / resume reconstruction | `job-seeker-agent` → `shokumukeireki-saigensei.md` |
| 志望動機 / motivation / 지원동기 | `job-seeker-agent` → `shibo-doki.md` |
| interview content, 面接練習, STAR, mock interview | `job-seeker-agent` → `mensetsu-rounds.md` when round-specific |
| interview manner, dress, 入室, 退室, greeting | `tenshoku-strategy` |
| resignation reason, 退職理由, 円満退職, handover | `tenshoku-strategy` |
| salary negotiation, 年収交渉, offer, 内定, 労働条件通知書 | `tenshoku-strategy` |
| application tracking, 応募管理, 選考トラッキング | `tenshoku-strategy` |
| career state, heartbeat, deadline, キャリア状態 | `career-agent` |
| 업무일지, 오늘 한 일, 경력으로 남기다, 仕事を記録, 経歴として残す, work log, career evidence | `career-maintenance` |
| 지금까지의 경력을 정리, 그동안 해온 일, キャリアの棚卸し, これまでの経験を整理, career inventory | `career-tanaoroshi` |
| 이 회사용 직무경력서, JD에 맞춰서, この求人に合わせて職務経歴書, tailor my resume to this posting | `career-document` |

For JD text plus URL use research mode (`kigyou-bunseki`). For JD text without URL use hiring-side
optimization mode (`hiring-manager-agent`). If unclear, ask whether the user wants job-seeker
analysis or hiring-side optimization.

棚卸し is checked before maintenance and needs no track either. Every phrase in its table carries
a scope marker maintenance has none of — 지금까지, これまで, so far — and that marker is what says
the request is about experience from before the ledger existed rather than about today's work.
It proposes nothing on the way in: the contexts, experiences and evidence arrive one
confirmation at a time.

Career readiness and job-search intent are separate. Recording a work event routes to
`career-maintenance` whether or not the user is looking, and needs no track: an employed user who
is not looking belongs to no hiring market. Reviewing a JD or a recruiter message routes normally
and does not change `job_search`, which only `career-agent set-job-search on|off` writes. Do not
read repeated JD review, salary curiosity, resume maintenance, or dissatisfaction as an intent to
leave.

Interview content (answer strategy) routes to `job-seeker-agent`; interview manner routes to
`tenshoku-strategy`. Self-analysis without a resume routes to `jiko-bunseki`; a pasted resume or
request for candidate evidence mapping routes to `job-seeker-agent`. These produce different
artifacts and are sequential, not interchangeable.

`job-seeker-agent` loads only the requested reference: 職務経歴書/自己PR →
`shokumukeireki-saigensei.md`, ATS → `ats-keywords.md`, 志望動機 → `shibo-doki.md`, interview →
`mensetsu-rounds.md`, 新卒 → `shinsotsu.md`, 中途 segment → `segments.md`, platform → `platforms.md`.

## Skill invocation handoff

The table above says which Skill to route to; it does not, by itself, prove the Skill ran. This
runtime cannot call the host back, so it cannot execute a Skill's SOP and hand back a result the
way a normal function call would. A host that reads a Skill's SOP and carries it out must close the
loop itself:

1. Run `career-agent skill-open --skill <name> --entrypoint claude` before starting the SOP. A
   `host_required` Skill returns `status: "started"` here — a `deterministic` or `hybrid` one may
   already be runnable through its own CLI command instead.
2. Carry out the SOP: read the SKILL.md, load only the reference the routing table names, do the
   work.
3. Run `career-agent skill-report <invocation_id> --status completed --artifact <path>` (or
   `blocked` / `failed` / `needs_input` / `needs_approval`, with `--error` describing what
   happened) when done. `career-agent skills` lists every Skill's execution class first, if that is
   unclear.

An invocation nobody reports stays open and surfaces as a warning in `status` and `doctor` — this
is a detection, not a guarantee. Skipping `skill-open`/`skill-report` does not stop a host from
answering; it only means nothing recorded that the answer came from actually running the Skill,
which is the distinction the invocation lifecycle exists to make legible.
