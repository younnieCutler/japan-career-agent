# AGENTS.md — Agent System Architecture & Fast Code Map

This file is the single source of truth for all AI Agents (Claude Code, Codex, Cursor, Antigravity, etc.) operating in this repository.

---

## ⚡ Fast Code Map (Token-Optimized Navigation)

To minimize token consumption, do **NOT** read entire source files. Use line-offset slicing (`view_file` with `StartLine`/`EndLine`) targeting these specific line ranges:

### 1. `skills/career-agent/career_agent.py` (Local Runtime Engine)
- **`L39–L64`**: Constants, Tracks (`shinsotsu`/`chuto`), Stage definitions
- **`L76–L90`**: `PIPELINE_STAGE` — agent stage to the 0–7 market stage map
- **`L91–L105`**: `SKILL_BY_STAGE` — Stage-to-Skill mapping
- **`L136–L139`**: Regular expressions (`NUMERIC_CLAIM`, `DATE_VALUE`, `HEADING`, `WIKILINK`)
- **`L142–L162`**: `load_routing()` / `ROUTING` / `term_present()` — loads `references/routing.yml`,
  the single KO/JA/EN keyword lexicon `infer_track()`, `stage_for()` and `flow_phase_for()` all read
  (no more per-function keyword copies to drift out of sync). `term_present()` word-bounds the
  short ASCII tokens (currently just `"es"`) that false-substring-match inside unrelated English
  words (`"research"` contains `"es"`); everything else, including intentional stems like
  `"graduat"`, still matches as a plain substring.
- **`L329–L369`**: Vault Note Indexer (`index_vault_notes`)
- **`L379–L414`**: `infer_track()` / `stage_for()` — routing, both driven by `ROUTING`
- **`L452–L471`**: `flow_phase_for()` — message signal checked *before* the profile/state fallback,
  driven by `ROUTING["flow_phase"]`. Getting this order backwards was a real bug: once any event
  was confirmed, state.flow_phase stayed `in allowed` forever, freezing flow_phase at whatever the
  first confirmed event happened to be regardless of what later messages said.
- **`L497–L515`**: Context Selector (`select_context` - metadata-only, no body loading)
- **`L516–L552`**: Event validation (`validate_event`) & Evidence verification logic
- **`L616–L690`**: `CareerVault` Class (State management, proposal handling, checkpoints)
- **`L725–L755`**: `upsert_pipeline_entry()` Projection onto `data/pipeline.yml`, via
  `_shared/pipeline_store.mutate()` (lock + atomic write). Writes flat top-level `companies:`/
  `updated:` — matching `_shared/schemas.yml` and what `status_bar.py`/`check_action.py`/
  `calibrate.py` already read. An earlier version nested this under a `pipeline:` key that no
  reader looked for, silently hiding every company career-agent projected.
- **`L758–L774`**: `apply_event_to_state()` Vault flow state only, no company list
- **`L777–L889`**: Legacy pipeline merge + `doctor()` Vault Diagnostic runner — `doctor --fix` migrates
  the old nested shape without dropping either company list; plain `doctor` only warns. It also warns if the CWD's `data/pipeline.yml`
  still has the legacy nested `pipeline:` shape, or errors if `companies` isn't a list
- **`L892–L931`**: `DEFAULT_VAULT_PATH` / `setup()` — one-shot first run: init + profile fields + doctor
- **`L964–L1042`**: `run_chat()` Session router & Proposal builder
- **`L1043–L1060`**: `run_heartbeat()` Action proposal engine (capped at 3)
- **`L1061–L1088`**: `run_discover()` Job Posting deduplication & Candidate recorder
- **`L1116–L1138`**: `run_context()` Shared metadata API provider
- **`L1187–L1232`**: `approve()` 2-step Ledger Commit processor
- **`L1233–L1260`**: `restore_state()` State snapshot restore — ledger is NOT rewound

### 2. `_shared/matching_v3.py` (Evidence-Based Diagnosis — the default matching engine)
`model_version: evidence_based_v3`. Independent axes; **nothing here is summed into a score**.
- **`ALLOCATION_KEYS` / `validate_allocation()`**: MHLW 9 elements, integer >= 1, sum exactly 29.
  `level: 1–5` is rejected as an allocation key and never enters the distance vector.
- **`composition()` / `composition_distance()` / `rank_role_profiles()`**: normalise to ratios
  summing to 1, Euclidean distance, stable `(distance, id)` ordering. No 0–100 conversion exists,
  and adding one is a spec violation, not an enhancement.
- **`portable_skill_result()`**: `available | insufficient_data | unmapped | unavailable`. A JD
  distance requires an `mhlw_mapping` with both `method` and `evidence`.
- **`eligibility_results()`**: tri-state. `conflict` only when BOTH sides are evidenced and
  disagree; one-sided information is `unknown`, never a pass.
- **`skill_results()`**: coverage = confirmed matched ÷ (confirmed matched + confirmed missing).
  `unknown` is excluded from the denominator; zero confirmed → `insufficient_data`.
- **`career_value_results()`**: aligned / tradeoffs / conflicts / unknown, never totalled.
- **`candidate_interest()` / `employer_signals()`**: recorded and passed through. Interest is not
  a parameter of `decision_status()` and must never become one — `test_matching_v3.py` guards the
  signature on purpose.
- **`decision_status()`**: conflict > review > proceed, from confirmed facts only.
- **`evaluate()` / `render()`**: full result and the PRD §9 text report. CLI: `python3
  _shared/matching_v3.py payload.json [--text]`.

### 2b. `_shared/mhlw_reference.py` (MHLW 114-profile reference interface)
- `load()` returns `status: unavailable` with a reason when no dataset is installed — the
  dataset's licence is unconfirmed and the profiles are **never** LLM-generated. A present but
  invalid file raises instead of degrading to "unavailable".
- Requires `dataset_version`, `source`, `licence`; validates every profile allocation.

### 2c. `_shared/legacy_experimental.py` (retired scorer — `legacy_v1`, opt-in only)
Was `_shared/scoring.py`. Off the default path; kept so historical scores stay reproducible.
- **`recruit_style()` / `persol_style()`**: every result stamped `model_version: legacy_v1` plus
  the fixed "not an official Recruit/Persol model" warning.
- **`culture_fit()`**: **discontinued** — raises `DiscontinuedError`. `100 − Σdiff × 10` produced
  a percentage from four ordinal ratings. Historical values stay on disk; no new one is computed.
- CLI refuses to run without `--legacy-experimental`. Self-test: `--self-test`.

### 2d. `_shared/test_matching_v3.py`
58 regression tests mapped to the PRD acceptance criteria. The two that matter most: interest
independence (AC-4) and the absence of any 0–100 field in the default result (AC-7).

### 2b. `_shared/pipeline_store.py` (Shared write path for `data/pipeline.yml`)
- **`L27–L41`**: `locked()` — fcntl/msvcrt exclusive lock on a `.lock` sibling file
- **`L44–L49`**: `load()` — safe_load, `{}` if the file doesn't exist yet
- **`L52–L60`**: `atomic_write()` — write to a `.tmp-<pid>` sibling, then `os.replace()`
- **`L63–L67`**: `mutate()` — load → fn(data) → atomic_write, all inside `locked()`. Both
  `career_agent.py`'s `upsert_pipeline_entry()` and `scripts/check_action.py`'s `check()` go
  through this now instead of each doing their own read-whole-file/rewrite-whole-file.
- **`L81–L108`**: `_validate_fields()` — stage range, `interest_level` 1–5, `decision_status` and
  `match_model_version` enums, and the refusal to write a new legacy `match_score` (existing
  values are preserved; only new writes are blocked).
- **`L111–L175`**: `upsert_company()`, `update_company()`, and `append_history()` — deterministic
  company operations used by `scripts/pipeline.py`; stage updates are forward-only.

### 3. `_shared/schemas.yml` (Canonical Data Contracts)
`schema_version: 2.0`. Read the **MODEL VERSIONS** block at the top first: every numeric field is
tagged `evidence_based_v3` or `legacy_v1`, and the two are never merged into one score, grade, or
sort key. Legacy values already on disk are preserved and never backfilled or rewritten.
- `SELF_ANALYSIS_PROFILE` (Produced by `jiko-bunseki`, consumed by `job-seeker-agent`)
- `CANDIDATE_PROFILE` — adds `portable_skill_allocation` (29 points), `portable_skill_level`
  (excluded from distance), `career_values`. Legacy 1–5 `portable_skills` is preserved and
  **not convertible** to an allocation.
- `COMPANY_PROFILE` — adds `requirements` (hard / required_skills / preferred_skills /
  experience), `conditions`, `mhlw_mapping`.
- `MATCH_HISTORY` — `model_version` is required per entry; v3 entries carry `decision_status`
  and coverage, and no 0–100 score. Legacy entries keep theirs verbatim.
- `PIPELINE` — the suite's only per-company store. Adds `match_model_version`,
  `decision_status`, `match_conflicts`, `match_unknowns`, `interest_*`, `employer_signals`.
  `match_score` / `predicted_tier` are frozen legacy history.
- `RULES` — the user's standing rules (`career-agent` writes on approval only)

### 4. `scripts/` (Deterministic Loop — no LLM in the path)
- **`status_bar.py`**: `build_status()` → the `<career_status>` block. Run by the UserPromptSubmit hook
  in `hooks/hooks.json`. Silent when `data/pipeline.yml` is absent.
- **`check_action.py`**: user-run. Ticks one action item; the assistant must not.
- **`pipeline.py`**: shared `upsert` / `update` / `history` / `close` CLI for every domain Skill writer.
- **`calibrate.py`**: route feedback, user overrides, preparation, and other workflow observations. It
  prints nothing below 3 reached-stage entries. `rules` promotes a cause only at 2+ supporting entries.
  **`legacy_calibrate.py --legacy-experimental`** is the separate read-only viewer for old tier history.
  The tier table is **legacy_v1 only** — `evidence_based_v3` records no predicted grade, so there
  is deliberately no forecast to score. Scoring a Decision Status against a hiring outcome would
  turn it back into the outcome estimate v3 exists to avoid. Route / feedback / override /
  root-cause analysis is unaffected and applies to all entries.
- **`test_status_bar.py`**, **`test_calibrate.py`**, **`test_pipeline_cli.py`**: run before touching the
  corresponding deterministic writer/reader scripts.

---

## 🌐 Language Auto-Detection (Suite-Wide, applies to all 9 skills)

Detect the language of the user's latest message and respond in that language — no setup, no menu. Korean →
Korean, Japanese → Japanese, English → English; re-detect every turn. An explicit instruction ("일본어로",
"in English", "日本語で") overrides detection. Japanese domain terms (職務経歴書, 志望動機, 転職軸, 退職理由,
年収, 内定, 円満退職, 再現性) always stay in original Japanese script. A pasted Japanese resume/JD is source
material, not a language instruction. Onboarding/disambiguation prompts are written in English for
readability — render them in the user's detected language.

## 📤 Output Contract (Suite-Wide Rule C, applies to all 9 skills)

All artifacts are written **relative to the directory where the session was invoked (CWD)** — the same
layout for every user on every machine:

- `./career-docs/` — human-readable reports (profiles, strategies, match reports, 企業カルテ, trackers)
- `./data/` — machine-readable state (`self_analysis_profile.yml`, `candidate_profile.yml`,
  `company_profiles/*.yml`, `match_history.md`)

Never write into the skill's install directory, and never to an absolute personal path. Create the folders
on first use. **After every save, print the file's absolute path and verify it exists (e.g., `ls -la <path>`)**
so the user can confirm the output on disk. If a target file already exists, ask before overwriting.

## 📟 Career Status Bar & Execution Gate (Suite-Wide)

`hooks/hooks.json` runs `scripts/status_bar.py` on every prompt. It reads `data/pipeline.yml` and
`data/rules.yml` and injects a `<career_status>` block: active companies by stage, the nearest
deadline, unchecked action items, the user's active rules, the scored-outcome count, and a notice
when a newer plugin version is published. No pipeline file, no output.
Pipeline resolution is explicit `--workspace` first, then `CAREER_WORKSPACE`, then the current
working directory. This prevents a prompt launched from an unrelated CWD from reading the wrong
workspace projection.

**Trust it, but only within its schema.** Every value is computed in code from the files on disk —
none is estimated, and nothing in it is a summary of the conversation. It is also a lossy projection:
it precomputes only those fields. A question it was not built to answer must be answered from
`data/pipeline.yml` directly, never inferred from the bar.

**Execution gate — obey it.** When the bar reports `gate: interview-prep generation BLOCKED for X`,
do not produce new interview-prep material for company X. Show the unchecked items and stop there.

The gate exists because of a documented, repeated failure: a checklist was written days before an
interview, went unopened, and the rejection reason came back naming the first unchecked item. A second
case repeated a rule the user had written six weeks earlier. In both, the knowledge existed on time and
only the execution was missing — writing more material on top of unread material is what the gate stops.

**Never mark an item checked yourself**, and never edit `checked` while upserting the pipeline for
another reason. The user runs `python3 scripts/check_action.py <slug> <id>`. An assistant that can
clear its own gate does not have one.

Likewise, skills may read `data/rules.yml` but never write it. Rules are promoted through
`career-agent` with the user's approval, so a constraint the assistant keeps failing cannot be
quietly relaxed by the assistant.

## 🔒 Context Isolation (Career Vault)

- When `CAREER_VAULT` is set, always use `python3 skills/career-agent/career_agent.py context --vault "$CAREER_VAULT"`.
- Never load Vault note bodies automatically; load only metadata returned by `context`.
- If `CAREER_VAULT` or `CAREER_AGENT_RUNTIME` is missing, ask for the Vault path rather than creating a
  separate career state in the current directory (see `skills/career-agent/references/shared-vault-context.md`).

## 🚪 Onboarding Check (Run Silently on Every Session Start)

Before doing anything, check silently (paths relative to CWD):
1. Does `data/candidate_profile.yml` exist and have a non-null `candidate_name`?
2. Does `data/company_profiles/` contain any `.yml` files?
3. Does `data/pipeline.yml` exist with any `closed: false` entries?

**If `data/pipeline.yml` has active entries (takes priority over the menus below):** greet with a
kanban summary — one line per active company: name, stage number + stage label from the Market Stage
Map, status, deadline. List any deadline within 3 days FIRST with a ⚠️ marker. Then ask which company
to continue with, or whether to add a new one. Example shape:

> "Active pipeline:
> ⚠️ Bloom Tech — stage 5 内定・オファー面談, 回答期限 2026-07-04 (in 2 days)
> Acme KK — stage 4 面接, 一次面接 2026-07-10
> Continue with which company, or add a new one?"

**If both are missing (first session):** ask where the user stands in the real market flow —

> "Where are you in the 転職 / 就活 process right now?
> 0) No direction yet — self-analysis first (강점·업무스타일·가치관 진단) → `/jiko-bunseki`
> 1) Preparing documents — resume / 職務経歴書 / 履歴書 → `/job-seeker-agent`
> 2) Researching companies — company URL → 企業カルテ, fit scoring → `/kigyou-bunseki` · `/matching-simulator`
> 3) Applying / interviewing — 面接マナー · 面接後フォロー · 応募 tracking → `/tenshoku-strategy`
> 4) Offer stage — オファー面談 · 年収交渉 · 内定対応 · comparing offers → `/tenshoku-strategy` · `/company-battlecard`
> 5) Resigning — 円満退職 · 引き継ぎ · counter-offer 대응 → `/tenshoku-strategy`
> H) Hiring side — JD optimization → `/hiring-manager-agent`"
>
> If the user is unsure, recommend 0 → 1 (direction first, then documents — the order the Japanese market
> expects: agents ask your 転職軸 in the very first CA meeting).

**If `candidate_profile.yml` exists:**
> "A saved profile exists: [candidate_name].
> Continue from here? Tell me which market stage you're at (書類 / 応募 / 面接 / 内定 / 退職) and I'll route:
> - matching-simulator or company-battlecard (match / compare)
> - tenshoku-strategy (退職理由 · 面接マナー · 年収交渉 · 円満退職 · offer handling · tracking)"

---

## 🧭 Auto-Detection Routing Table

When the user's message or attached content matches a pattern below, activate the corresponding skill **before responding**.
(Trigger cells stay multilingual — they are matching keywords for KO/JA/EN input.)

| Trigger | Activate |
|---------|---------|
| "자기분석", "自己分析", "강점 분석", "강점/약점 심층", "work style 진단", "가치관", "커리어 앵커", "career anchors", "나를 더 깊이 파악" | `jiko-bunseki` |
| User wants direction/self-understanding *before* resume work | `jiko-bunseki` |
| 이력서, 職務経歴書, 履歴書, resume text pasted | `job-seeker-agent` |
| JD text pasted — 必須条件, 歓迎条件, 募集要項 (no URL) | `hiring-manager-agent` |
| Japanese job/company site URL pasted | `kigyou-bunseki` |
| "매칭", "합격확률", "スコア", "マッチ", "fit", "screening" | `matching-simulator` (answers the evidence question; does not produce an outcome rate) |
| Two company names + "비교", "vs", "どっちが", "compare" | `company-battlecard` |
| CANDIDATE_PROFILE + COMPANY_PROFILE both in conversation | `matching-simulator` |
| "신졸", "新卒", "学チカ", "graduating soon" | `job-seeker-agent` (新卒 track) |
| "이직하고 싶어", "転職したい", "mid-career hire" | `job-seeker-agent` (中途 track) |
| "퇴직 사유", "退職理由", "resignation reason", "why I left" | `tenshoku-strategy` |
| "면접 매너", "面接マナー", "interview etiquette", "입실", "入室", "退室" | `tenshoku-strategy` |
| "연봉 협상", "年収交渉", "salary negotiation", "希望年収" | `tenshoku-strategy` |
| "원만 퇴직", "円満退職", "how to resign", "퇴직 절차", "인수인계", "引き継ぎ" | `tenshoku-strategy` |
| "이직 시장", "転職市場", "job market trend", "2025 채용", "2026 채용" | `tenshoku-strategy` |
| "카운터 오퍼", "counter-offer", "引き止め", "퇴직 만류" | `tenshoku-strategy` |
| "면접 복장", "服装", "dress code", "what to wear" | `tenshoku-strategy` |
| "오퍼 면담", "オファー面談", "offer meeting", "내정 사퇴", "内定辞退", "回答期限", "입사일 조정", "入社日" | `tenshoku-strategy` (内定対応) |
| "노동조건통지서", "労働条件通知書", "雇用契約書", "조건 하향", "현직보다 나빠", "みなし残業", "고정잔업", "offer letter 확인" | `tenshoku-strategy` (STEP 3-3 労働条件レビュー) |
| "입사 수속", "入社手続き", "源泉徴収票", "住民税", "이직 서류", "레퍼런스 체크", "前職調査", "시용기간", "試用期間", "온보딩", "정착", "입사 후 90일" | `tenshoku-strategy` (STEP 4-2 入社・定着) |
| "ATS", "키워드 최적화", "스카우트 검색", "検索キーワード", "職務要約 키워드", "검색에 걸리게", "서치 히트" | `job-seeker-agent` (STEP 4-1b ATSキーワード) |
| "第二新卒", "제2신졸", "제2신입", "입사 3년차 이직", "첫 직장 그만" | `job-seeker-agent` (中途 dai2_shinsotsu segment) |
| "35세 이직", "40대 이직", "관리직 이직", "ハイクラス", "管理職 転職", "매니저 이직" | `job-seeker-agent` (中途 senior_ic/management segment) |
| "면접 라운드", "一次/二次/最終 면접", "カジュアル面談", "ケース면접", "면접관 유형", "audience prep" | `job-seeker-agent` (STEP 4-3 面接ラウンド別) |
| "お礼メール", "면접 후 메일", "面接後フォロー", "thank-you mail", "면접 후속" | `tenshoku-strategy` (面接後フォロー) |
| "지원 관리", "선고 추적", "応募管理", "選考トラッキング", "거절 패턴", "application tracker", "선고 패턴" | `tenshoku-strategy` (選考トラッキング) |
| "면접 연습", "모의 면접", "mock interview", "面接練習", "深掘り 対策", "stress test" | `mock-interviewer` |
| "career state", "다음 행동", "heartbeat", "마감 알림", "이벤트 원장", "キャリア状態" | `career-agent` |

**JD disambiguation rule:**
- JD text + URL → `kigyou-bunseki` (research mode)
- JD text, no URL → `hiring-manager-agent` (optimization mode)
- If unclear, ask: "Do you want to analyze this as a job seeker, or optimize it as the hiring side?"

**Interview disambiguation rule:**
- Interview **content** (answer strategy, STAR examples) → `job-seeker-agent`
- Interview **manner** (入室, dress, greeting, timing) → `tenshoku-strategy`
- If unclear, ask: "Is this interview **content** prep (answer strategy), or interview **manner** prep (入室 · dress · greeting)?"

**Self-analysis disambiguation rule:**
- "자기분석 / 自己分析" with **no resume**, asking about strengths · values · work style · direction → `jiko-bunseki`
- A resume / 職務経歴書 is pasted, or the user wants evidence mapping / CANDIDATE_PROFILE → `job-seeker-agent`
- jiko-bunseki produces SELF_ANALYSIS_PROFILE (direction and reflection); job-seeker-agent consumes it and produces CANDIDATE_PROFILE (evidence mapping). They are sequential, not interchangeable.

---

## 🗾 Japan 転職 Market Flow (Suite Backbone)

The suite mirrors the real Japanese mid-career hiring process. Every user moves through the same stages;
skills are tools attached to stages. When the user asks "what should I do next?", answer from this map —
name the stage they are at and the stage that comes next.

| Stage | Market reality / planning use | Timing source | Skill |
|-------|---------------|------------------|-------|
| 0. 自己分析 | Direction before documents; record the user's confirmed 転職軸 and unknowns | User state and dated notes | `jiko-bunseki` |
| 1. 書類準備 | 履歴書 + 職務経歴書; route-specific requirements must come from the dated posting or channel | Posting / channel evidence | `job-seeker-agent` |
| 2. 情報収集・企業研究 | Channels and review sites are options; keep company facts separate from hypotheses | Dated company sources | `kigyou-bunseki`, `matching-simulator` |
| 3. 応募・書類選考 | Track each application and record actual responses or rejection feedback | Pipeline events | `tenshoku-strategy` STEP 6 (tracking) |
| 4. 面接 | Round names and participants vary by company; follow the invitation and confirmed recruiter guidance | Invitation / recruiter message | `job-seeker-agent` STEP 4-3 (content), `tenshoku-strategy` STEP 2 / 2-2 (manner / follow-up) |
| 5. 内定・オファー面談 | Confirm written conditions, response deadline, negotiation channel, and start-date constraints | Offer documents / company message | `tenshoku-strategy` STEP 3 / 3-2, `company-battlecard` (multiple offers) |
| 6. 退職交渉・引き継ぎ | Applicable law, contract, work rules, and handover facts must be checked for this user; do not generalize a notice period | Official source / contract / work rules | `tenshoku-strategy` STEP 4 |
| 7. 入社 | Coordinate start date and verify tax, insurance, authorization, reference-check, and probation documents | Official source / employer documents | `tenshoku-strategy` STEP 4-2 |

Stages 0–2 may overlap, and stages 3–5 run per-company in parallel. No universal duration is asserted here;
time-sensitive market claims belong in `_shared/career_claims.yml` and must be reverified.
Per-company progress lives in `data/pipeline.yml` (PIPELINE schema in `_shared/schemas.yml`) — each
company carries its own stage number from this map.

**Compressed skill chains (same map, chain form):**

```
[Full job-seeker flow]     jiko-bunseki → job-seeker-agent → kigyou-bunseki → matching-simulator → tenshoku-strategy → company-battlecard
[Resume already in hand]   job-seeker-agent → kigyou-bunseki → matching-simulator → tenshoku-strategy → company-battlecard
[Execution only]           tenshoku-strategy standalone — 退職理由 · 面接マナー · 年収交渉 · 円満退職 work without a profile
[After an offer]           company-battlecard (decide) → tenshoku-strategy STEP 3+3-2 (negotiate) → STEP 3-3 (labor-condition review) → STEP 4 (resign) → STEP 4-2 (onboard)
[Hiring side]              hiring-manager-agent → matching-simulator
[Company research]         kigyou-bunseki → company-battlecard
```

---

## 💾 Data Persistence (Session Memory)

This suite stores data between sessions in the `data/` directory **under the invocation directory (CWD)** —
see the Output Contract (Rule C) above:

| File | Written by | Read by |
|------|-----------|---------|
| `data/self_analysis_profile.yml` | jiko-bunseki (Phase 2/3) | job-seeker-agent, matching-simulator, company-battlecard, tenshoku-strategy, mock-interviewer (confirmed values only) |
| `data/candidate_profile.yml` | job-seeker-agent (STEP 4) | matching-simulator, company-battlecard, tenshoku-strategy |
| `data/company_profiles/{slug}.yml` | hiring-manager-agent, kigyou-bunseki | matching-simulator, company-battlecard |
| `data/match_history.md` | matching-simulator | User review |
| `data/pipeline.yml` | kigyou-bunseki, matching-simulator, tenshoku-strategy, company-battlecard, career-agent (`approve` of a company event) | Onboarding (session-resume kanban), tenshoku-strategy STEP 6, `scripts/status_bar.py`, `scripts/calibrate.py` |

`data/pipeline.yml` is the single home for per-company progress. The Career Vault holds the agent's
own flow state (track · stage · deadlines · event ledger) and does **not** keep a second copy of the
company list — on `approve`, career-agent projects the confirmed event onto `data/pipeline.yml`
(stage · next_action · deadline · history) and never touches the fields the domain skills own
(`decision_status`, `channel`, `kyujin_legitimacy`, the interest fields, the outcome record, and
the frozen legacy `match_score`).

**Interest is not a priority signal.** `interest_level` exists so the user can record that they
like a company independently of fit. No skill combines it with deadline, stage, or match data
into a ranking or priority score, and none may start. Application-priority ordering, if it is
ever wanted, is a separate feature with its own design.

When loading a profile from `data/`, tell the user which file was loaded and ask if it's still current.
When writing any of these, follow Rule C: print the absolute path and confirm the file exists.

---

## 🛡️ Suite-Wide Ethical Rules

These apply to all 9 skills equally:

1. **No fabrication** — Never invent STAR stories, metrics, skill evidence, or reference data not in
   the user's input. This includes reference datasets: an unavailable dataset is reported as
   unavailable, never generated.
2. **No submissions without review** — Never submit applications or send communications on the user's behalf
3. **Result honesty** — A confirmed conflict is a conflict. No reframing, no encouragement, no
   "potential". A `Review` means specific things are unknown; say which.
4. **Missing is not neutral** — An unknown stays `unknown`. Never a mean, never 50, never a
   default pass, and never inside a coverage denominator.
5. **No invented outcome rate** — No pass rate, offer rate, or company-formula claim is emitted here.
   Observed events are reported as events with dates; dated external claims remain descriptive.
6. **Evidence grounding** — Every claim cites its source in the user's input (resume line, JD line,
   interview answer), with the observation date and confidence where it matters.

---

## 🩹 Learning From Mistakes

`tests/eval.md` (per skill) checks that known scenarios still work — it does not, by itself, make the
suite learn from a real failure. Each skill has a `tests/mistakes.md` for that: an append-only log of
actual bad outputs, not speculative edge cases.

**When something goes wrong in real use** (wrong score, fabricated claim, bad routing, advice a user had
to correct): append one row to that skill's `tests/mistakes.md` — date, what was asked, what happened,
what was expected, status `open`. Do this in the moment; don't wait to write a polished summary.

**Periodically, not every session:** review the log(s). A single row is not evidence of anything —
sporadic, unconfirmed failures should stay logged and unactioned. Only when the same pattern repeats
2–3+ times across sessions, promote it to the smallest medium that fits:
- A judgment call or instruction the model should follow → edit that skill's `SKILL.md` wording.
- A deterministic rule or routing bug → edit `career_agent.py`'s keyword lists in
  `skills/career-agent/references/routing.yml` (or the skill's own logic, if any).
- Either way: re-run `tests/eval.md` (or `test_career_agent.py` for career-agent) after the change to
  confirm nothing else regressed, then mark the row `Promoted` with a one-line pointer to what changed.

Don't skip the re-run step — a fix for one logged mistake that breaks an existing eval case is not a net
improvement.

---

## ✅ Commit Gate (All Agents)

Before preparing any commit, read `.agents/PRE_COMMIT_CHECKLIST.md` when it exists. It is deliberately
gitignored because it is a local operating contract; never add it to a commit. At minimum, verify the
seven questions in that document: data-contract readers/writers, pre-existing state transitions,
KO/JA/EN routing, Windows compatibility, existing-data compatibility, retry safety, and one lifecycle
smoke test. Run the listed deterministic checks before committing.

---

## 🗂️ Suite Architecture

```
_shared/
├── frameworks.md            # Canonical: work-style reflection, Portable Skills, Ontology, values,
│                            #   Gakuchika, provenance, and verification questions.
├── decision_philosophy.md   # Suite-wide axes, vocabulary, trust boundary, and legacy policy
├── career_claims.yml        # Dated external claims; empty until a sourced claim is recorded
├── schemas.yml              # Canonical data contracts (schema_version 2.0, model-version tagged)
├── matching_v3.py           # DEFAULT matching engine — evidence_based_v3
├── mhlw_reference.py        # MHLW 114-profile reference interface (dataset not bundled)
├── legacy_experimental.py   # legacy_v1 scorer — opt-in flag required, off by default
├── test_matching_v3.py      # acceptance-criteria regression tests
└── pipeline_store.py        # shared lock/atomic write path for data/pipeline.yml

data/                 # Session memory (gitignored — personal data)
├── candidate_profile.yml
├── match_history.md
└── company_profiles/

skills/
├── career-agent/          # local runtime: routing, event ledger, heartbeat, discovery
├── jiko-bunseki/         # Self-analysis: strengths/values → SELF_ANALYSIS_PROFILE (runs before job-seeker-agent)
├── job-seeker-agent/     # CA simulator: resume → CANDIDATE_PROFILE
├── hiring-manager-agent/ # RA simulator: JD → COMPANY_PROFILE
├── matching-simulator/   # Evidence-based fit diagnosis (no composite score)
├── company-battlecard/   # Head-to-head company comparison
├── kigyou-bunseki/       # URL → company data extraction
└── tenshoku-strategy/    # 転職 execution strategy (resignation, interview, negotiation, offer,
                          #   労働条件通知書 review, onboarding/定着90日, tracking + calibration)
```
