# 中途 Segment Playbooks (第二新卒 / Standard / 35+ Specialist / Management)

> The suite targets **all job changers**, Japanese nationals included. Foreign-national items (JLPT, visa)
> are conditional add-ons, not the default lens. This file defines (1) segment detection at STEP 1,
> (2) the per-segment evaluation lens agencies apply, and (3) the conditional rule for JLPT/visa questions.

---

## 1. Segment Detection (during STEP 1, silent)

Classify from the collected history — do not ask a separate "which segment are you" question unless ambiguous:

| Segment | Signal | `segment` value |
|---------|--------|-----------------|
| **第二新卒** | Graduated ≤3 years ago, first job (employed or already left) | `dai2_shinsotsu` |
| **Standard mid-career** | ~3–10 years experience, IC role | `standard` |
| **35+ Specialist (IC)** | 35+ years old, no direct-report management | `senior_ic` |
| **Management / ハイクラス** | Team lead 〜 部長+; hiring/評価/P&L responsibility | `management` |

Boundary cases (e.g., 33-year-old lead): ask one clarifying question, then set it. Record in
`CANDIDATE_PROFILE.segment`.

---

## 2. Per-Segment Evaluation Lens

The fixed step ORDER never changes (Rule B). The segment branches step CONTENT:

### 第二新卒 (`dai2_shinsotsu`)

| Aspect | How it differs |
|--------|----------------|
| What agencies screen | **Potential + basic business manners**, not achievements. 短期離職 reason is THE question. |
| STEP 0 gap analysis | Years-of-experience requirements are soft for 第二新卒枠 postings; flag when a JD is NOT a 第二新卒 posting (hard filter). |
| STEP 3 scoring | Thin evidence expected — 学チカ+α allowed as supplementary evidence (borrow `references/shinsotsu.md` Gakuchika lens for pre-work episodes), but label it `[student-era evidence]`. |
| STEP 4 resume | Short first-tenure handled head-on: 退職理由 must be reframed BEFORE the resume ships → hand off to `tenshoku-strategy` STEP 1; the 4-WHY chain (なぜ今 especially) carries extra weight. |
| Platforms | マイナビジョブ20's, Re就活, doda — young-segment specialists; BizReach mismatch. |
| Risk flag | A second short tenure would compound permanently — state this plainly when the move's rationale is weak. |

### Standard mid-career (`standard`)

The default path — STEP 0–4 as written. No modifications.

### 35+ Specialist (`senior_ic`)

| Aspect | How it differs |
|--------|----------------|
| What agencies screen | Depth of 専門性 + 再現性. The unspoken question: **「なぜまだICなのか」** — prep an affirmative answer (deliberate specialist path), not an apology. |
| STEP 3 scoring | Evidence bar rises: 5/5 claims need org-level impact; "years of experience" alone never raises a score (existing Score Integrity rule applies harder). |
| STEP 4 resume | Lead with the specialist axis (technical depth, domain authority, mentoring at scale). De-emphasize breadth — a 35+ generalist profile is the weakest position in this market. |
| Salary | Expectations vs 35+ hiring reality: fewer postings, higher per-posting bar. Route to `tenshoku-strategy` STEP 5 for the range. |
| Risk flag | The 35歳の壁 blocker (`tenshoku-strategy/references/senko-tracking.md`) — mitigation is specialization proof, stated explicitly. |

### Management / ハイクラス (`management`)

| Aspect | How it differs |
|--------|----------------|
| What agencies screen | **Org-level 再現性**: P&L or budget scope, team size growth, hiring/育成 track record, attrition under your management, cross-functional scope. |
| STEP 3 scoring | Coaching / Negotiation / Drive rubrics read at org scale (a 5 needs "built a team learning system" not "mentored one junior"). |
| STEP 4 resume | Quantify the organization, not just the output: 組織規模 × 予算 × 成果. Individual-contributor episodes are supporting cast only. |
| Platforms | BizReach / JAC Recruitment / doda X — scout-driven; profile findability matters most → run STEP 4-1b (ATS keywords) with management vocabulary (組織マネジメント, PL責任, 採用, 育成). |
| Interview | 最終面接 value-fit weighting is highest here; reference check (前職調査) probability is highest here → consistency rule is absolute (`tenshoku-strategy/references/nyusha-teichaku.md` §2). |

---

## 3. JLPT / Visa — Conditional Rule (foreign nationals only)

**Do not ask JLPT or visa questions by default.**

- Ask only when a foreign-national signal exists: non-Japanese name + non-Japan education history, the user
  mentions visa/在留資格/JLPT themselves, or the resume shows overseas-only career start.
- Japanese natives (or when the user confirms native fluency): set `jlpt_level: "native"`,
  `visa_status: null`, and skip all JLPT-routing logic in `references/platforms.md` §1.
- When the signal is ambiguous, one neutral question: 「日本語は母語ですか？（母語でない場合のみ、JLPTレベルと
  在留資格をお伺いします）」 — then branch.
- For foreign nationals, the existing JLPT/visa flows apply unchanged.
