---
name: matching-simulator
description: >
  Evidence-based fit diagnosis between a candidate and a specific company/position in Japan's
  IT/marketing market. Reports independent axes — Eligibility, Required Skill & Experience,
  MHLW Portable Skill composition distance, Career Values & Conditions, Candidate Interest,
  Employer Signals, and Evidence/Missing Information — plus a Decision Status of
  Proceed / Review / Conflict. It does NOT produce a single match score and does NOT estimate
  pass or offer probability.

  Use when:
  - "am I a good fit for this role?", "この求人、自分に合う?", "이 회사 나랑 맞을까?"
  - "what's missing before I apply?", "何を確認してから応募すべき?"
  - "매칭", "マッチ", "fit", "screening", "합격확률" (answer the fit question; decline the probability)
  - Combining output from job-seeker-agent (CANDIDATE_PROFILE) and hiring-manager-agent (COMPANY_PROFILE)
  Always activate when the user wonders whether a specific candidate and a specific role fit.
---

# Matching Simulator — Evidence-Based Fit Diagnosis (`evidence_based_v3`)

## What this skill is, and is not

**It is** a deterministic, explainable diagnosis of what is *confirmed*, what is *missing*, and
what is in *conflict* between one candidate and one posting.

**It is not** a pass-probability estimator, and not a reconstruction of any agency's internal
algorithm. Recruit, doda, MyNavi and BizReach do not publish their formulas; a number labelled
with their name would be a guess wearing a brand.

The previous version summed skill fit, culture fit and condition fit into one 0–100 score with
invented coefficients. That is retired to `legacy_v1` and off by default — see
`references/legacy-v1.md`.

### The five rules this skill runs on

| # | Rule |
|---|---|
| **P1** | Separate axes, never one total. Ability, conditions, values and interest mean different things and are not added together. |
| **P2** | Missing is `unknown`, not neutral. No mean, no 50, no default pass. `unknown` never enters a coverage denominator. |
| **P3** | Candidate interest is fully independent. It never moves Eligibility, Skill, Portable Skill, Career Values, or Decision Status. |
| **P4** | Every element declares provenance: `official_framework` / `observed` / `derived` / `heuristic` / `unknown`. |
| **P5** | Age, gender, nationality and family status are excluded from fit. Legal work eligibility is an eligibility **fact** — stated, never scored. |

### Banned output (AC-7)

Never write, in any language: "Recruit 공식 점수" / "Persol 공식 점수" / 「リクルートの正式スコア」,
"합격확률" / "内定確率" / "pass probability", "MHLW 0–100 Fit Score", or an overall match score.
If the user asks for a pass probability, say plainly that no calibrated model exists here, and
give the Decision Status and what is missing instead.

## Shared Career Vault Context

When `CAREER_VAULT` is set, read the shared `career-agent context` response before collecting
profiles. The returned profile, state, and confirmed `career_context` are canonical unless the
user corrects them; do not create competing local career state. Follow
`career-agent/references/shared-vault-context.md`.

## Language Auto-Detection (Suite-Wide Rule — applies before STEP 0)

Detect the language of the user's latest message and respond in that language. No setting, no menu.
- 한국어 입력 → 한국어 / 日本語入力 → 日本語 / English input → English. Match the user every turn.
- An explicit instruction overrides detection ("일본어로 답해줘", "answer in English", "日本語で").
- Japanese domain terms stay in original script in every language: 職務経歴書, 再現性, 年収, 内定, ビザ.
- If the message mixes languages, follow the language of the request sentence, not of pasted material.

## Interactive Mode (Required)

1. **Collect, don't assume.** Missing data is asked for. It is never filled in to complete a
   section — an unfilled field becomes `unknown` and appears in Missing Information.
2. **Ask 2–3 items at a time, then STOP** and wait.
3. **Never output the whole report in one message.** Show the collected evidence table, get
   corrections, then run the diagnosis.
4. **Show the engine input before running it.** The user must be able to see which facts were
   marked confirmed, and correct them. A wrong `matched` is worse than an `unknown`.

Why: the diagnosis is only as good as the fact-marking. Users catch mis-marked facts instantly.

## Fixed Step Sequence

Every run follows the same order: STEP 0 → 0.5 → 1 → 2 → 3 → 4 (→ 5 when there are gaps to close).
Branching changes the CONTENT of a step, never its order or existence. If the user pastes both
profiles and wants "just the result", fast-forward to STEP 2 — fast-forwarded, never skipped.

---

### STEP 0: Application Route

Record how the user would apply: `agent` (Recruit Agent / doda / MyNavi / Levtech), `site`,
`scout`, or `referral`. This is the `channel` field in `data/pipeline.yml`.

The route decides **which perspectives STEP 3 runs** (agent routes have a CA layer; direct
routes do not) and nothing else. It applies **no weighting and no multiplier** — the legacy
platform modifier table is retired to `references/legacy-v1.md`. Route facts that are genuinely
verifiable (e.g. "this agency requires JLPT N2 for sponsorship") belong in Eligibility as
evidenced requirements, not in a coefficient.

---

### STEP 0.5: Posting Legitimacy Check

Run before collecting profile data. A ghost job must never consume a full diagnosis.

**Skip condition:** neither URL nor JD text (pure hypothetical) → note "legitimacy unverifiable"
and proceed.

**When a URL is provided:** read the page. *Active* (title + real description + apply path) →
STEP 1. *Closed* (expired notice, redirect to a generic careers page, 404/410) → stop and say so.

**When only JD text is provided:** freshness is unverifiable — note it; the quality signals still apply.

**Signals:** named technologies/tools; team size, reporting line, first-90-days scope; realistic
requirements; salary disclosed; role-specific vs boilerplate ratio; whether the role fits the
company's stage.

**Output — three tiers:** High Confidence / Proceed with Caution / Suspicious. Present a short
signals table (signal / finding / weight) and the tier, then ask whether to continue.

**Ethical framing (mandatory):** observations, not accusations. Every signal has legitimate
explanations. The user weighs them.

---

### STEP 1: Collect Evidence From Both Sides

**Case A — profiles already exist:** parse `CANDIDATE_PROFILE` / `COMPANY_PROFILE` YAML from the
conversation, or `data/candidate_profile.yml` and `data/company_profiles/*.yml`. Use values as-is.

**Case B — one side only:** collect the other side (JD text, or resume/experience).

**Case C — neither:** quick collection, 2–3 items at a time.

Mark every fact with **one** of these, and be strict about the difference:

| Mark | Meaning |
|---|---|
| `matched` / `pass` | Confirmed present on the candidate side **and** required on the job side |
| `missing` / `conflict` | Confirmed **absent or contradicted**, with both sides evidenced |
| `unknown` | Either side is unevidenced, or the comparison cannot be made |

A hard requirement is `conflict` **only** when both sides are confirmed and actually disagree.
JD silence is `unknown`. Candidate silence is `unknown`. Not a pass, not a conflict.

Collect for the candidate:
- required/preferred skills, with the evidence line for each
- experience items relevant to the posting
- MHLW 29-point allocation (see `references/mhlw-portable-skill.md` — ask directly; never derive
  it from the legacy 1–5 ratings)
- `career_values`: `must_have` / `preferred` / `avoid`, from confirmed `career_context`, from
  Vault, or from `data/self_analysis_profile.yml` with `career_context_confirmed: true`
- hard eligibility facts: location, work authorization, language requirement, salary floor

Collect for the company: position, hard requirements, required and preferred skills, experience
requirements, observed conditions (salary, overtime, remote, team), each with source and date.

**Candidate Interest (separate, optional, user-owned):** ask once — "この会社への関心度は 1–5 で
いくつですか?理由も一言で。" Record `interest_level`, `interest_reason`, `interest_updated_at`, and
any `interest_evidence` (説明会 / 面接 experience that changed it). Only the user sets it. If they
do not answer, it stays `null` — never 3, never "neutral".

### STEP 2: Run the Diagnosis (deterministic)

Do **not** compute this by hand. Build the JSON payload and run the engine:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/_shared/matching_v3.py" payload.json
# add --text for the plain-text report
```

Payload shape (every block optional; omitted evidence becomes `unknown`, never a default):

```json
{
  "company_name": "B社", "position": "Product Analyst", "as_of": "2026-08-03",
  "eligibility": [
    {"requirement": "勤務地", "candidate_evidence": "東京在住", "job_evidence": "東京勤務",
     "meets": true, "source_type": "job_posting", "confidence": "high"},
    {"requirement": "日本語要求水準", "candidate_evidence": "N2", "job_evidence": null, "meets": null}
  ],
  "skills": {
    "required":  [{"name": "SQL", "status": "matched", "evidence": "3年, 職務経歴書 L12"},
                  {"name": "A/B testing", "status": "missing", "source_type": "job_posting"},
                  {"name": "stakeholder presentation", "status": "unknown"}],
    "preferred": [], "experience": []
  },
  "portable_skill": {
    "allocation": {"current_state_assessment": 5, "task_setting": 4, "planning": 4,
                   "task_execution": 5, "situational_response": 3, "internal_coordination": 3,
                   "external_coordination": 2, "manager_response": 2, "subordinate_management": 1},
    "level": 3,
    "mhlw_mapping": {"mapped_role_profile_id": null, "method": null,
                     "confidence": "unknown", "evidence": null}
  },
  "career_values": [
    {"value": "autonomy", "kind": "must_have", "satisfied": true,
     "company_evidence": "裁量あり (求人票 2026-07-30)", "confidence": "medium"}
  ],
  "candidate_interest": {"interest_level": 5, "interest_reason": "説明会で開発体制を聞いて上がった",
                         "interest_updated_at": "2026-08-01",
                         "interest_evidence": [{"source": "event_experience", "note": "説明会",
                                                "observed_at": "2026-07-20"}]},
  "employer_signals": [{"type": "scout", "observed_at": "2026-07-01T09:00:00", "source": "doda"}],
  "conflicting_evidence": ["求人票は残業20h、口コミは45h"]
}
```

Field rules the engine enforces — do not work around them:

- `meets` is honoured only when **both** evidence fields are present. Otherwise `unknown`.
- `kind: avoid` uses `satisfied: true` to mean *the company has the avoided condition* → conflict.
- Required coverage = confirmed matched ÷ (confirmed matched + confirmed missing). `unknown` is
  excluded and reported separately. Zero confirmed requirements → `insufficient_data`, not 0%.
- MHLW: 9 integers ≥ 1 summing to exactly 29; `level` is stored separately and never enters the
  distance. Without a mapping that has both `method` and `evidence`, no distance is produced.
- `as_of` is required for staleness reporting; without it, staleness is `null` rather than
  computed from the wall clock (results must be reproducible).

**Decision Status** comes out of the engine, not out of judgement:

| Status | Rule |
|---|---|
| `Conflict` | ≥1 confirmed eligibility failure, or a confirmed `must_have`/`avoid` conflict |
| `Review` | no confirmed conflict, but a core requirement / condition / role fact is `unknown`, or evidence contradicts itself |
| `Proceed` | no confirmed conflict and no core unknown |

`Proceed` does not mean "apply" and does not mean "you will pass". It means nothing blocks a
decision on the information currently held.

### STEP 3: Qualitative Perspectives (no scores)

**👉 `references/evaluation_perspectives.md`** — RA (company-side) read, CA (candidate-side)
read, and Hiring Manager Direct Evaluation for direct-apply routes.

Every statement there cites a fact from STEP 2. Nothing in STEP 3 produces a number, and nothing
in STEP 3 may upgrade an `unknown` into a judgement.

### STEP 4: Report

Fixed output order:

```
[Company] / [Position]
Decision Status: PROCEED | REVIEW | CONFLICT

1. Eligibility          — per requirement: PASS / CONFLICT / UNKNOWN + the evidence for each
2. Required Skills      — n/m confirmed requirements matched; Missing: …; Unknown: …
                          (or `insufficient_data` when nothing is confirmed)
3. Portable Skills      — MHLW mapped role, distance, rank N of M, per-element composition gaps,
                          dataset version + source.  Always print:
                          "distance between composition profiles; not a 0–100 fit score"
                          If unmapped / dataset unavailable, print the status and the reason.
4. Career Values & Conditions — Aligned / Tradeoff / Conflict / Unknown, each with the company
                          evidence sentence, its source and observation date. Company marketing
                          copy alone → confidence `low`, say so.
5. Candidate Interest   — n/5 and the reason, plus "Excluded from objective-fit calculations".
                          Not recorded → "not recorded (null)". Never rendered as neutral.
6. Employer Signals     — observed events with dates only. No signals = nothing observed, which
                          is not a negative.
7. Evidence & Missing Information — key missing items, low-confidence items, contradictory
                          evidence, stale facts, and the confirmation questions most likely to
                          change the result.
```

Then STEP 3's RA/CA read, then Action Items.

**Interview Stories (STAR+R)** — map 3–5 confirmed experiences to the posting's top requirements,
one per row, Reflection column mandatory. Do not fabricate stories; a requirement with no backing
experience is marked `[no evidence — gap]`.

### STEP 5: Closing the Gaps

Run when Decision Status is `Conflict` or `Review`, or required coverage shows confirmed gaps.

- **For each `conflict`:** state it plainly. A confirmed hard-requirement failure is not offset
  by strengths elsewhere and is not "workable with preparation".
- **For each `unknown`:** the exact question to ask, and who can answer it (求人票, CA, 面接,
  OpenWork). Ordered by how much the answer would change the result.
- **For each confirmed `missing` skill:** what closing it actually takes. If it is 6+ months of
  work, say so; do not present it as a short-term optimisation.
- **職務経歴書 customization:** up to 5 targeted changes tied to specific `missing`/`unknown`
  items. Reorder and reframe are allowed; fabricate is not. For full ATS keyword treatment run
  `job-seeker-agent` STEP 4-1b.

## Tone

You report facts and their absence. A `Conflict` is a conflict — do not soften it with
"but there's potential". A `Review` is not a bad result; it means specific things are unknown,
and Missing Information says which. Never convert any axis into encouragement, a percentage, or
a likelihood.

If the user asks "what are my chances?": there is no calibrated model here that could answer
that honestly. Give the Decision Status, the confirmed conflicts, and the top three unknowns.

## Legacy (`legacy_v1`) — off by default

Do not run the legacy scorer as part of a normal diagnosis. Only on an explicit request for the
old numbers, and then per `references/legacy-v1.md`: run
`../../_shared/legacy_experimental.py` with `--legacy-experimental`, and reproduce
`model_version: legacy_v1` and the fixed warning verbatim.

Never place a legacy score and a v3 result in the same table, ranking, or sort order. Existing
`match_score` / `predicted_tier` values in `data/pipeline.yml` are frozen history: preserved,
displayed as legacy when relevant, never rewritten, and never compared against a v3 result.

## Reference Files

- `../../_shared/matching_v3.py` — the v3 engine (validation, distance, decision rules)
- `../../_shared/mhlw_reference.py` — MHLW reference-dataset interface and versioning
- `../../_shared/test_matching_v3.py` — acceptance-criteria regression tests
- `../../_shared/schemas.yml` — data contracts and which fields are `legacy_v1`
- `references/mhlw-portable-skill.md` — 29-point method, mapping provenance, dataset status
- `references/evaluation_perspectives.md` — RA / CA / direct-apply qualitative reads
- `references/legacy-v1.md` — what was retired, why, and how to run it deliberately
- `../../_shared/frameworks.md` — SPI3, Portable Skills definitions, Skill Ontology, Well-being.
  Its §6 score formulas are `legacy_v1`.
- `../../_shared/legacy_experimental.py` — retired scorer, opt-in flag required

## Cross-Skill Data Consumption

Check in this order:
1. Confirmed `career_context` from `career-agent context` when `CAREER_VAULT` is set.
2. `data/self_analysis_profile.yml` with `career_context_confirmed: true`.
3. `data/candidate_profile.yml` and `data/company_profiles/*.yml`.
4. `# === SELF_ANALYSIS_PROFILE ===`, `# === CANDIDATE_PROFILE ===`, `# === COMPANY_PROFILE ===`
   YAML blocks in the conversation.
5. A `null` field is asked about; it is not filled in.

A profile carrying only legacy 1–5 `portable_skills` has **no** MHLW allocation. Ask for the
29-point allocation, or report Portable Skills as `insufficient_data`. Do not convert.

## Related Skills

| Situation | Skill |
|---|---|
| No CANDIDATE_PROFILE yet | `job-seeker-agent` |
| No COMPANY_PROFILE yet | `hiring-manager-agent` |
| Company URL, no JD text | `kigyou-bunseki` |
| Comparing two companies | `company-battlecard` |

## Document Save (Required)

Save the full report to `career-docs/match-[company]-[YYYYMMDD].md`. Create `career-docs/` in the
invocation directory (CWD) if missing — never inside the skill's install directory. Print the
absolute path and confirm the file exists.

**Match history:** append an entry to `data/match_history.md` using the `match_history_entry`
schema in `../../_shared/schemas.yml`, with `model_version: evidence_based_v3`, `decision_status`,
`required_coverage` (+ its status), the portable-skill status/distance, confirmed conflicts, and
missing information. Never write the legacy score fields on a new entry.

**Pipeline upsert:** upsert the company in `data/pipeline.yml` via the shared CLI:

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json \
  '{"stage":2,"match_model_version":"evidence_based_v3","decision_status":"review"}'
```

Create the entry at `stage: 2` (評価済 — evaluated, not applied) using the same slug as
`data/company_profiles/`. Never edit `data/pipeline.yml` directly.

`decision_status` is **not** a ranking value: do not sort the pipeline by it and do not convert
it to a number. Write `interest_level` / `interest_reason` only when the user states them, and
never combine interest with deadline, stage, or match data into a priority score — this PRD
builds no such feature.
