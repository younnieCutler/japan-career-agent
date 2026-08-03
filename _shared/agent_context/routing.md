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

For JD text plus URL use research mode (`kigyou-bunseki`). For JD text without URL use hiring-side
optimization mode (`hiring-manager-agent`). If unclear, ask whether the user wants job-seeker
analysis or hiring-side optimization.

Interview content (answer strategy) routes to `job-seeker-agent`; interview manner routes to
`tenshoku-strategy`. Self-analysis without a resume routes to `jiko-bunseki`; a pasted resume or
request for candidate evidence mapping routes to `job-seeker-agent`. These produce different
artifacts and are sequential, not interchangeable.

`job-seeker-agent` loads only the requested reference: 職務経歴書/自己PR →
`shokumukeireki-saigensei.md`, ATS → `ats-keywords.md`, 志望動機 → `shibo-doki.md`, interview →
`mensetsu-rounds.md`, 新卒 → `shinsotsu.md`, 中途 segment → `segments.md`, platform → `platforms.md`.
