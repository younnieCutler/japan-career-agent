---
name: tenshoku-strategy
description: >
  Japanese job-change (転職) execution-strategy skill. Covers resignation reason reframing
  (negative → positive), interview manner protocol (room entry/exit, dress, timing), salary
  negotiation, offer handling, graceful resignation, 2025-2026 labor-market positioning,
  and application tracking with rejection-pattern analysis.
  Consumes CANDIDATE_PROFILE to output role/skill-tailored strategy.

  Use when:
  - "why I left", resignation reason reframing
  - Interview etiquette: room entry/exit protocol, dress code, timing
  - Salary negotiation, counter-offer handling
  - Offer meetings, declining an offer, adjusting the start date
  - Written labor-condition notice (労働条件通知書) review, checking for downgraded terms vs the current job
  - How to resign gracefully, handover planning
  - Onboarding paperwork, resident-tax timing, reference checks, probation-period survival
  - Job market trends (2025-2026)
  - Post-interview thank-you emails, follow-up cadence
  - Application tracking, rejection pattern analysis
  Use for HOW to execute the job-change process.
  Resume content → job-seeker-agent. Match score → matching-simulator.
---

# tenshoku-strategy — Japanese Job-Change Execution Strategy

## Shared Career Vault Context

When `CAREER_VAULT` is set, read the shared `career-agent context` response before STEP 0. Use the
shared profile, state, and confirmed `career_context` as the factual baseline, and route new facts
through Career Agent drafts.
Follow `career-agent/references/shared-vault-context.md`.

This skill provides the tactical playbook from "decided to change jobs" to "first day at the new company."
It does not handle resume analysis or company matching — those are other skills' domains.

**Core Principle:** Deliver protocol, not encouragement. Every piece of advice cites its basis in Japanese
business norms.

---

## Interactive Mode (Required)

- Ask 2–3 questions at a time. Wait for the answer before moving to the next step.
- Do not dump the whole strategy in one message. Proceed module by module, confirm, then move on.
- Do not apply generic advice before confirming the user's specific situation.
  - e.g., "Is your current employer a Japanese firm or foreign-capital? The 円満退職 protocol differs."

---

## Language Auto-Detection (Suite-Wide Rule — applies before STEP 0)

Detect the language of the user's latest message and respond in that language. No setting, no menu.
- 한국어 입력 → 한국어 / 日本語入力 → 日本語 / English input → English. Match the user every turn.
- An explicit instruction overrides detection ("일본어로 답해줘", "answer in English", "日本語で").
- Japanese domain terms stay in original script in every language: 職務経歴書, 志望動機, 転職軸, 退職理由,
  年収, 内定, 退職届, 敬語, 円満退職, 再現性.
- If the message mixes languages, follow the language of the request sentence, not of pasted material.

## Fixed Step Sequence (Workflow Standardization)

Every run follows the SAME ordered steps, for every user, regardless of background. Branching changes the
CONTENT of a step — never its ORDER or existence.
- Always run STEP 0 (Situation Assessment) first; it is the fixed entry point. Then run only the modules the
  user prioritized, but always in the canonical order STEP 1 → 2 → 2-2 → 3 → 3-2 → 3-3 → 4 → 4-2 → 5 → 6.
- Branch points are fixed and explicit: STEP 0 module routing (退職理由 / 面接マナー / 面接後フォロー / 年収交渉 /
  内定対応 / 労働条件通知書レビュー / 円満退職 / 入社手続き・定着 / 市場 / 選考トラッキング); 日系 vs 外資 in STEP 4;
  正社員 / 契約社員 / 派遣社員 / SES in STEP 4. The branch decides
  *what* a step asks, not *whether* or *when* it runs.
- If the user jumps ahead ("just the salary negotiation"), silently verify the prerequisite data (STEP 0 minimal
  info) exists; if missing, collect it first, then proceed. The sequence is fast-forwarded, never skipped.

---

## STEP 0: Situation Assessment

### Profile Loading
1. Check `data/candidate_profile.yml` or a CANDIDATE_PROFILE YAML block in the conversation.
2. If it exists: "Using the saved profile: [candidate_name]. Is that correct?"
3. If not: collect the minimal info below (the skill works without a profile too).

When available, also load confirmed `career_context` from `career-agent context` or
`data/self_analysis_profile.yml` with `career_context_confirmed: true`. Missing or unconfirmed values
must not be replaced with generic motivation language.

### Minimal info to collect (ask 2–3 at a time)

**Round 1:**
- Current employment status: employed / already resigned / no Japan work experience yet
- Target job-change timing: immediate / 1–3 months / 3–6 months

**Round 2:**
- Top priorities (pick up to 2):
  - A) 退職理由 reframing
  - B) 面接マナー (interview manner)
  - B-2) Post-interview follow-up / お礼メール (面接後フォロー)
  - C) 年収交渉 (salary negotiation)
  - D) 内定対応 (offer handling — オファー面談 / 内定辞退 / 回答期限 / 入社日)
  - D-2) 労働条件通知書 review (written-offer downgrade check vs current job)
  - E) 円満退職 (graceful resignation)
  - E-2) Onboarding paperwork + first-90-days survival (入社手続き・定着90日)
  - F) Market positioning
  - G) 選考トラッキング (application tracking / pattern analysis)

### Module Routing
- Adjust the STEP order to the user's chosen priorities.
- All modules are optional; if the user says "I already know this," skip it.
- But at the start of each module, you MUST read its reference file first.

---

## STEP 1: 退職理由 Strategic Reframing

> **Reference:** `references/taishoku-riyu-reframing.md` — read before starting.

### Process

1. **Collect the real reason:**
   > "What is the real reason you are leaving (left) your current/previous job? Tell me honestly — strategic
   > reframing comes after."

   If confirmed `career_anchors`, `career_theme`, or `career_values` exists, show which field supports
   the desired 転職軸. If it does not exist, keep the 転職理由 factual and ask for the user's own
   criterion rather than supplying "growth" or "new challenge".

2. **Apply the conversion table:** match the reason to the closest of the reference's 6 categories and convert.

3. **Output Format:**
   ```
   ■ Original reason: [exactly as the user said it]
   ■ Category: [one of the 6]
   ■ Reframed (Japanese): 「...」
   ■ Reframed (English): "..."
   ■ One-sentence interview version: 「...」
   ■ Expected follow-up questions + preparation points
   ```

4. **Special-case handling:**
   - Creators/engineers: must include "努力の過程" (see reference)
   - Foreign applicants: safe phrasing for visa-related reasons (see reference)
   - Compound reasons: lead with the single most strategically favorable one; keep the rest for deep-dive prep.

5. **Feedback loop:**
   > "Shall I feed this 退職理由 phrasing into job-seeker-agent's resume improvements?"

### Anti-Fabrication Gate
- Reframing ≠ lying. If the logic collapses under the interviewer's deep-dive (深掘り), trust is lost instantly.
- If "努力の過程" did not actually happen, do not invent it.
- Always confirm with the user that the converted result is fact-based.

---

## STEP 2: 面接マナー Protocol

> **Reference:** `references/mensetsu-manner.md` — read before starting.

### Process

1. **Confirm interview format:**
   > "Is it an in-person interview, or online (Zoom/Teams)?"

2. **In-person:** output the reference's full protocol as a numbered checklist
   - Time Management
   - Grooming Checklist
   - 入室 7 Steps
   - 着席 Protocol
   - 退室 5 Steps

3. **Online:** output the Online Interview Variant.

4. **Common Mistakes:** output the severity table.

5. **Output suggestion:**
   > "Want to print this checklist or save it to a note?"

---

## STEP 2-2: 面接後フォロー (Post-Interview Follow-up)

> **Reference:** `references/mensetsu-follow.md` — read before starting.
> Fixed position: right after 面接マナー (STEP 2). The window between just-after-interview and the result.

### Process
1. **Confirm application route:** direct application / via agent (CA) → branches お礼 and follow-up.
2. **お礼メール:** for direct applications / final interviews, give a same-day (当日中) keigo template (one
   point raised in the interview + one sentence of 再現性). If via an agent, send feedback/thanks **to the CA first**.
3. **Follow-up cadence:** light, Japan-style intervals (for 書類 non-response, confirm via the CA after 1–2 weeks).
   **Warn that excessive 催促 is a minus.**

### Honesty Gate
- Do not fabricate, in the お礼 mail, a point that did not come up in the interview or a result you do not have.
- Do not use a non-existent other-company process as follow-up leverage.

---

## STEP 3: 年収交渉 (Salary Negotiation)

> **Reference:** `references/nenshu-koushou.md` + `references/market-positioning-2025-2026.md` — read before starting.

### Info to collect

**Round 1:**
- Current annual income (base + bonus total)
- Desired annual income

**Round 2:**
- Current interview stage (document / 1st / 2nd / final / 内定)
- Whether a competing offer exists

### Process

1. **Timing judgment:** advise whether salary can be raised at the current stage.
2. **Market-rate context:** if CANDIDATE_PROFILE has target_role + skill_stack, give that role's salary range
   from the market-positioning reference.
3. **Leverage analysis:** assess the user's situation against the reference's leverage strengthen/weaken table.
4. **Negotiation script:** output a branching script per the Decision Tree.

   ```
   [Situation] Company offers 6M yen, target is 7M yen
   [Leverage] Has a competing offer + 5 years DE experience
   [Recommended Phrase] #4 (competing-offer leverage)
   [Japanese] 「他社様のオファーとの比較よりも...」
   [English] "Rather than comparing with other companies' offers..."
   ```

5. **Alternatives:** if salary itself is hard → negotiate other conditions (remote, review timing, grade/level).

### Pipeline update
If the negotiation concerns a specific company, upsert its entry in `data/pipeline.yml` (PIPELINE schema
in `_shared/schemas.yml`): set `stage: 5`, `deadline` = 回答期限 if known, and append a `history` event
(e.g., "年収交渉 script prepared"). Use the shared writer from CWD, for example:
`python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json '{"stage":5,"deadline":"YYYY-MM-DD"}' --history "年収交渉 script prepared"`.
Never edit `data/pipeline.yml` directly; the CLI preserves foreign fields and uses the shared lock/atomic write.
Follow the Output Contract: print the absolute path and confirm the file exists after writing.

### Honesty & Cultural Safety Gate
- **Cultural Safety Warning:** In Japanese corporate culture, aggressive salary demands after receiving an offer can be perceived as lacking "和 (harmony)" and commitment. Always frame requests humbly around contribution value.
- **Agency Channel Routing:** If applying via a recruitment agency (Recruit, doda, etc.), **never negotiate directly with the target company's HR**. Route all requests through the CA (Career Advisor) who understands internal grade bands and HR dynamics.
- **Do not inflate current salary:** Companies routinely request a 源泉徴収票 (withholding tax slip) prior to formal contract issuance.
- **Do not fabricate competing offers:** Inventing non-existent offers will be exposed during start-date alignment or agent verification.

---

## STEP 3-2: 内定対応 (Offer Handling)

> **Reference:** `references/naitei-taiou.md` — read before starting.
> Fixed position: after 年収交渉 (STEP 3), before 円満退職 (STEP 4). Covers just-after-offer → joining confirmed.

### Info to collect (2–3 at a time)

**Round 1:**
- Current offer status: single offer / multiple offers / in progress (no offer yet)
- Application route: direct / via agent (CA) / scout

### Process

1. **オファー面談 checklist:** output the reference's 5+1 items (understand salary / evaluation & promotion
   criteria / mission & career path / actual working style / start date / extra: work location) as a numbered
   checklist. State that this is a place for "understanding," not negotiation.
2. **回答期限 negotiation:** to align multiple processes (揃える), provide a deadline-adjustment script. Warn
   against unreasonable extensions.
3. **内定辞退 contact:** if there is an offer to decline, provide a phone script + mail template. **Fast +
   grateful + no room for reversal.**
4. **入社日 negotiation:** adjust the start date based on current 就業規則 + handover. Warn that careless
   delay = wobbling 内定 (法律 vs 就業規則 ties into `enman-taishoku.md`).
5. **Via-agent branch:** if via a CA, advise consulting the CA first on schedule / negotiation / 辞退.
6. **Pipeline update:** use `python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json '{"stage":5,"deadline":"YYYY-MM-DD"}' --history "内定受領"` for an offer;
   use `python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" close <slug> --reason "内定辞退"` when declining;
   use `python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json '{"stage":6}' --history "入社意思確認"` when joining.
   Close other abandoned entries with the same `close` command. Never edit `data/pipeline.yml` directly.
   Follow the Output Contract (print path, verify exists).

### Structural Problem Flag
- Unemployed + single offer but demanding a long 回答期限 → warn: no leverage, offer-rescind risk.
- Delaying a 辞退 → directly point out that sooner = minimal reputational/relationship loss; delay only adds risk.

### Honesty Gate
- Do not fabricate a non-existent other-company offer as 回答期限/negotiation leverage.
- Do not fabricate false circumstances as a 辞退 reason. A concise truth + politeness is enough.

---

## STEP 3-3: 労働条件通知書 Review (Downgrade Check)

> **Reference:** `references/roudou-joken-review.md` — read before starting.
> Fixed position: after 内定対応 (STEP 3-2), before 円満退職 (STEP 4). The last gate before 承諾.

### Info to collect (2–3 at a time)

**Round 1:**
- Which document arrived: 内定通知書 only / 労働条件通知書 / 雇用契約書
- Current-job condition sources available: payslip / 就業規則 / 現職の雇用契約書

### Process

1. **Document check:** if only a 内定通知書 exists, provide the request script — no 承諾 without the written
   労働条件通知書. Verify the 労基法15条 必須記載事項 are all present.
2. **Downgrade comparison table:** build the 現職 vs オファー(書面) table per the reference's 11 items
   (年収 decomposition / みなし残業 / 賞与 / 年間休日 / 試用期間 / 勤務地・転勤 / 労働時間 / 評価・昇給 /
   退職金・DC / 競業避止・副業 / 手当). Every ↓ row shows the concrete delta. Rows without current-job
   evidence → 比較不可, never guessed.
3. **Verbal-vs-written check:** compare against what was said at the オファー面談 (STEP 3-2); discrepancies
   get the polite confirmation script. Via agent → raise through the CA.
4. **Verdict:** 承諾可 / 承諾前に要確認・要交渉 N件 / 重大な下方 — 再考推奨. Red flags (2+) stated plainly.
5. **Bridges:** salary-item renegotiation → STEP 3 (`nenshu-koushou.md`); accept-vs-decline value judgment →
   `company-battlecard`; conditions confirmed → STEP 4 円満退職.

### Honesty Gate
- Quantify downgrades; do not editorialize them away ("growth opportunity"). The trade-off call is the user's.
- Require documentary current-job figures — memory inflates.
- State before (not after) that post-承諾 renegotiation has near-zero leverage.

---

## STEP 4: 円満退職 (Graceful Resignation)

> **Reference:** `references/enman-taishoku.md` — read before starting.

### Info to collect

**Round 1:**
- Employment type: 正社員 / 契約社員 / 派遣社員 / SES
- Notice period required by the work rules (就業規則), if known

**Round 2:**
- Destination offer (内定) status: secured / in progress / none
- Project situation at the current job: in progress / completed / handover-ready

### Process

1. **Legal framework:** minimum notice period by employment type + the practical standard.
2. **Boss Meeting Script:** provide the reference's meeting script (Opening + reason + thanks).
3. **Resignation timeline:** customize the D-60 ~ D+1 timeline template to the user's situation.
4. **Handover guide:** provide the Handover Document Template.
5. **Counter-offer response:**
   - Explain with data why declining is wise
   - Provide a decline script
   - Cover the exception case fairly too

6. **Paid-leave strategy:** explain the 2 usage patterns.
7. **Resignation greeting:** mail template + send timing.

### Structural Problem Flag
Point out structural problems directly when present:
- Announcing resignation before securing a destination → warn: loss of negotiation leverage
- Resigning right before a project deadline → warn: reputation risk
- Resigning with only the legal 2 weeks left → warn: graceful resignation may be impossible

---

## STEP 4-2: 入社手続き & 定着90日 (Onboarding Paperwork · First 90 Days)

> **Reference:** `references/nyusha-teichaku.md` — read before starting.
> Fixed position: after 円満退職 (STEP 4). Covers 退職日 → surviving the 試用期間 — this is the skill
> attached to Market Stage 7 (入社) in CLAUDE.md's Japan 転職 Market Flow.

### Info to collect (2–3 at a time)

**Round 1:**
- Gap between 退職日 and 入社日: none / N days
- Resignation timing: month-end or mid-month; 退職 month (for the 住民税 branch)

### Process

1. **Paperwork checklist:** documents to receive from the old employer (雇用保険被保険者証, 源泉徴収票,
   離職票 if a gap, etc.) + to submit to the new one. Chase-before-leaving items flagged.
2. **住民税 branch:** 特別徴収 continuation vs 一括徴収 (1–5月退職) vs 普通徴収 — warn about the small final
   payslip / home payment slips per the reference table.
3. **Insurance gap branch:** if a gap exists, 任意継続 vs 国民健康保険 comparison + 国民年金 switch deadlines;
   month-end rule explained before the 退職日 is finalized (ties into STEP 4).
4. **前職調査 / reference check (if applicable):** consent basis, referee selection and briefing, the
   consistency rule, and the "no current-employer contact before resignation announced" constraint.
5. **定着90日 plan:** the 30/60/90 table adapted to the user's actual role (never pasted generic), including
   the early 報連相 over-communication rule and the early-mismatch protocol (documented conditions breach vs
   adjustment period — reference `roudou-joken-review.md` when the written offer is breached).
6. **Pipeline update:** run `python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json '{"stage":7}' --history "入社完了"`.
   Never edit `data/pipeline.yml` directly. Follow the Output Contract (print path, verify exists).

### Honesty Gate
- Money warnings (一括徴収, double premiums) delivered undiluted.
- Referee briefing = fact alignment, never scripted praise.
- Do not judge "mismatch" from atmosphere inside 30 days; require documented deltas.

---

## STEP 5: Market Positioning Summary

> **Reference:** `references/market-positioning-2025-2026.md` — read before starting.

### Staleness Gate (run first, every time)

Compare today's date against the reference's `last_verified` date **using a shell `date` command, not mental
math**. If more than 90 days have passed: verify the key figures (有効求人倍率, role salary ranges for the
user's target_role) via web search before quoting them, and update `last_verified` in the reference file with
what was re-verified. If verification is not possible in this session, prefix every quoted figure with
`[stale — verify before use]`.

### Process

1. If CANDIDATE_PROFILE exists: tailored analysis based on target_role + skill_stack.
2. If not: confirm the user's role / years of experience, then analyze.

### Output
- Market demand trend for the role
- Salary range (by years of experience)
- Regional differences
- For foreign applicants: additional leverage points
- Optimal job-change timing vs current timing assessment

### Disclaimer (required)
> "This market data is as of [last_verified date]. Before any actual negotiation, verify current figures via
> doda salary surveys, OpenWork, and your agent."

---

## STEP 6: 選考トラッキング + パターン分析 (Application Tracking)

> **Reference:** `references/senko-tracking.md` — read before starting.
> Fixed position: last. A job-search PM layer that tracks many applications longitudinally (separate from the
> single-shot modules).

### Process
1. **Source of truth:** `data/pipeline.yml` (PIPELINE schema in `_shared/schemas.yml`) — one entry per
   company, keyed by `slug`. This STEP owns stage transitions (0–7, per the CLAUDE.md Market Stage Map),
   `history` events, `next_action`, `deadline`, and `closed`/`closed_reason`. Use
   `python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert|update|close|history` for every write; never edit the YAML directly
   or delete entries (closed entries feed the funnel).
2. **Rendered view:** after every tracking session, regenerate `career-docs/applications.md`
   (# / 日付 / 企業 / 職種 / プラットフォーム / スコア / ステータス / 求人真正性 / メモ) from pipeline.yml.
   The yml is authoritative; the markdown is for human review only.
3. **States:** 評価済 → 応募 → 書類通過 → 一次 → 二次 → 最終 → 内定 / 内定辞退 · お見送り · 見送り(self) —
   stage/closed mapping in `references/senko-tracking.md` §2. **On お見送り with channel = agent | scout,
   ask for the recruiter's verbatim feedback (原文) and store it in `agent_feedback` unedited** — site /
   referral rarely give a real reason, leave null (senko-tracking §2).
3-b. **Outcome record — required before `closed: true`.** Ask for all four and write them to the entry.
   Do not set `closed` while any is missing; a closed entry without them is a prediction that can never
   be scored, which is the structural reason calibration was impossible before v1.7.
   | Field | Question to ask | If the user does not know |
   |---|---|---|
   | `reached_stage` | どこまで進みましたか (0–7)? | Infer from `history`; state that you inferred it |
   | `feedback_obtained` | 落ちた理由の原文をもらえましたか? | `false` — a 定型お祈りメール does not count |
   | `root_cause` | 一言で言うと何が原因でしたか? | `null`. **Never guess** — a fabricated cause becomes a rule |
   | `demo_slot` | 自分の成果物を見せる場はありましたか? | `unknown` |
   `root_cause` must reuse an existing label from other entries whenever it fits. Free-wording every
   entry makes the counts meaningless, and the counts are what promote a rule.
   Also record `prep_lines` (lines written for this company) and `gate_override` (whether a blocking
   gate was passed) if either is known. Both are recorded only — nothing branches on them.
4. **Pattern analysis (≥5 confirmed-outcome entries in pipeline.yml):** funnel · score-vs-outcome ·
   **calibration by predicted grade** (bucket each closed entry's `match_score` into A/B/C/D per the
   `_shared/frameworks.md` §6 grade bands, then compute conversion rate to Positive outcome per band — this
   tests whether `matching-simulator`'s own grade labels are trustworthy for this user/platform combination;
   a band that under- or over-converts vs its label should be flagged, e.g. "B-grade predictions converted
   at 12% here — treat future B as C for this profile") · two-tier blockers — **Tier A 属性ミスマッチ**
   (ビザ/JLPT/県外onsite/35歳/skill/短期離職) and **Tier B 面接遂行品質** (read `agent_feedback` quotes:
   数値なしエピソード / PREP構造欠如 / 自己弱点の自白 / 企業理解不足) · top-3 recommendations. A Tier B blocker
   repeated across companies is the #1 fix (fully in the candidate's control). Calibration explains whether
   the score itself is trustworthy; Tier A/B explain why an outcome diverged from it — report both, do not
   conflate them. **LLM aggregation, no Node script, with a "±approximate, sample N" disclaimer.**
4-b. **Deterministic pass first:** run `python3 scripts/calibrate.py` before writing any analysis of
   your own. It computes predicted-tier-vs-reached-stage, feedback capture rate per route, override
   outcomes, and prep-volume-vs-outcome straight from the file, and it prints nothing at all below 3
   scored outcomes. Report its output; add interpretation only on top of it. Never restate its numbers
   from memory — recomputing them by reading the file is how the counts drift.
   `python3 scripts/calibrate.py rules` lists which rejection causes recur. A cause with a single
   supporting entry is not actionable and the tool will refuse to promote it: one company's rejection
   reason is that company's measurement. Always surface the caveat it prints — the axis the candidate
   actually wins on produces no row in that table at all.
5. **Action suggestions:** filters / score threshold / target adjustment (after user approval).
6. Both files follow the Output Contract: CWD-relative, print the absolute path after each write and
   confirm the file exists.

### Honesty Gate
- Do not fill missing results with inference. With a small sample, give "direction," not a verdict.

---

## Comprehensive Strategy Document

After the relevant STEPs are done, consolidate the full strategy into a single saved document.

### Save path
```
career-docs/strategy-[name]-[YYYYMMDD].md
```

If the `career-docs/` folder does not exist, create it in the invocation directory (CWD) — never inside
the skill's install directory. After saving, print the file's absolute path and confirm it exists
(e.g., `ls -la <path>`) so the user can verify the output on disk. The same rule applies to the
`career-docs/applications.md` tracker in STEP 6.

### Document structure
```markdown
# 転職戦略レポート — [Name]
**Created:** [YYYY-MM-DD]
**Modules used:** [list of executed STEPs]

## 1. 退職理由 (if applicable)
[reframing result]

## 2. 面接マナー (if applicable)
[checklist]

## 3. 年収交渉 (if applicable)
[negotiation script]

## 3-3. 労働条件比較 (if applicable)
[現職 vs オファー downgrade table + verdict]

## 4. 円満退職 (if applicable)
[timeline + script]

## 4-2. 入社手続き・定着90日 (if applicable)
[paperwork checklist + 30/60/90 plan]

## 5. Market Positioning (if applicable)
[market analysis]

---
*LLM approximation ±10pts. The final call is yours and your agent's.*
```

---

## Tone & Style Rules

- **Anti-sentiment (absolute):** no "파이팅", "you'll do great", "頑張ってください" — banned.
- **Protocol delivery:** "This is the correct order. Deviating creates risk." — protocol delivery, not a soft suggestion.
- **Flag structural problems directly:** when the situation is unfavorable, state it clearly with the consequence.
- **Response language:** follow the Language Auto-Detection rule at the top (auto-detect the user's language).
  Always keep domain terms in original Japanese (退職届, 内定, 年収, 敬語, 円満退職).
- **Evidence grounding:** cite the basis for every piece of advice (Civil Code Art. 627, doda survey data, etc.).

---

## Related Skills — Before or After tenshoku-strategy

| Situation | Recommended skill | Why |
|-----------|------------------|-----|
| No CANDIDATE_PROFILE | `job-seeker-agent` | Profile data improves the precision of STEP 1, 3, 5 |
| Check the target company's matching score | `matching-simulator` | The score affects negotiation leverage |
| Multiple offers → decide which to take | `company-battlecard` | Decide first, then negotiate/resign |
| Company URL → interview-prep data | `kigyou-bunseki` | Use the 企業カルテ to prep likely interview questions |

---

## Disambiguation with job-seeker-agent

For a "面接対策 (interview prep)" request:
- **Content** (answer strategy, STAR examples, technical appeal) → `job-seeker-agent`
- **Manner** (入室, dress, greeting, timing) → `tenshoku-strategy`
- If unclear, confirm with the user:
  > "Is this interview **content** prep (answer strategy), or interview **manner** prep (入室 · dress · greeting)?"
