# Job Seeker Agent — Test Cases

Run these when iterating on `job-seeker-agent`. Focus: the suite-wide **Language Auto-Detection (Rule A)**
and **Fixed Step Sequence (Rule B)**, plus the new 志望動機 / 職務経歴書 reproducibility modules.

## Test Case 1: Rule A — Korean request with pasted Japanese resume
**Objective**: Response language follows the *request sentence*, not the pasted source material.
- **Input**:
  ```
  일본에서 이직하려고 해요. 제 경력 좀 봐주세요.
  職務経歴: SIerでJavaの開発を5年担当しました。
  ```
- **Criteria**:
  - Responds in **Korean** (the request sentence is Korean; the pasted 職務経歴 is source material).
  - Japanese domain terms (職務経歴書, 転職軸) remain in Japanese script.
  - First action is the **STEP -1 Track Confirmation** logic — and because "이직" makes the track obvious,
    it branches directly to **中途** (does not skip the entry point, just fast-forwards it).

## Test Case 2: Rule A + Rule B — Japanese request, identical sequence
**Objective**: A Japanese user reaches the SAME fixed entry/sequence as the Korean user — only the language differs.
- **Input**:
  ```
  日本で転職したいです。職務経歴を見てください。
  職務経歴: SIerでJavaの開発を5年担当しました。
  ```
- **Criteria**:
  - Responds in **Japanese**.
  - Same first step as Test Case 1: STEP -1 → branch to **中途** (proves the order is language-invariant).
  - Side-by-side with TC1, the *step taken* is identical; only the output language changes.

## Test Case 3: Rule B — fast-forward must not skip prerequisites
**Objective**: Jumping ahead fast-forwards the sequence; it never skips it.
- **Input**: `바로 志望動機만 써줘. 회사는 메르카리야.` (no prior resume/scores in the session)
- **Criteria**:
  - Does **not** immediately emit a finished 志望動機.
  - Silently checks for prerequisite data (STEP 1 history, STEP 3 scores); finding none, runs the minimal
    prerequisite collection first, then produces the 志望動機.
  - The 志望動機 follows the forced 3-part order from `references/shibo-doki.md`:
    ① 会社理解 → ② 自分の経験 → ③ 入社後貢献, and is rejected if it reads as a Taker or omits ①.

## Test Case 5: STEP 4-3 audience-segmented interview prep (transplant)
**Objective**: Route to STEP 4-3; classify rounds to audiences; tag questions; reuse existing frames; no fabrication.
- **Input**: `메르카리 백엔드 2차 면접하고 1주일 뒤에 최종 면접이야. 면접 준비 도와줘.`
- **Criteria**:
  - Routes to STEP 4-3 (`references/mensetsu-rounds.md`).
  - Classifies 2次 → `genba-manager` (or `peer-tech` if technical) and 最終 → `exec-final` (value-fit).
  - Every example question tagged `[sourced: …]` or `[inferred from JD]` — never invents a 口コミ/Glassdoor question.
  - Reuses the 4-WHY chain + 再現性 frames (shibo-doki.md / shokumukeireki-saigensei.md), not new invented frames.
  - Japan research sources named (OpenWork/転職会議/ビズリーチ/Geekly), not Glassdoor/Levels/Blind.

## Test Case 4: 職務経歴書 reproducibility rewrite (担当業務 → 再現性)
**Objective**: A duty-list bullet is rewritten along 役割 / 工夫 / 成果 / 再現性, never fabricating numbers.
- **Input**: `職務経歴書を直して: 「ECサイトの運用を担当」`
- **Criteria**:
  - Flags the bullet as a *duty, not an achievement* and asks a follow-up to recover the **工夫** and **役割**
    (per `references/shokumukeireki-saigensei.md` §1).
  - Does not invent metrics; if none are recoverable, uses qualitative-but-specific phrasing.

## Test Case 6: 新卒 first-draft path
**Objective**: A student gets a usable 学チカ / 自己PR draft before any assessment.
- **Input**: `신졸이고 카페 아르바이트 경험으로 자기PR 초안을 만들고 싶어요.`
- **Criteria**:
  - Branches to 新卒 without asking about SPI3 or the self-analysis checklist.
  - Asks at most three questions about role, challenge, action, and outcome/learning.
  - On the next response emits `Facts used`, a 学チカ draft, a 自己PR draft, and at most three evidence questions.
  - Does not create scores, `CANDIDATE_PROFILE`, or a pipeline entry; does not invent a metric.

## Test Case 7: 中途 first-draft path and 第二新卒 boundary
**Objective**: A career changer gets a defensible 職務要約 / 転職軸 draft, with 第二新卒 staying in 中途.
- **Input**: `입사 2년 차인데 데이터 엔지니어로 이직하려고 해요. 경력 요약 초안부터 만들고 싶어요.`
- **Criteria**:
  - Branches to 中途 / 第二新卒 and asks at most three questions about target, role, contribution, and reason to move.
  - On the next response emits `Facts used`, a 職務要約 draft, a 転職軸 draft, and at most three evidence questions.
  - Student-era evidence, if supplied, is labelled supplementary; it does not switch to 新卒 scoring.
  - Does not estimate a metric or create a profile or pipeline entry.

## Test Case 8: Confirmed career context reuse
**Objective**: Confirmed values guide writing; unconfirmed values never become invented motivation.
- **Input**: A SELF_ANALYSIS_PROFILE with `career_context_confirmed: true`, then a second profile with the
  same fields set to `false`.
- **Criteria**:
  - Confirmed anchors/theme/energy/values are cited in 自己PR, 志望動機, and 転職軸.
  - Unconfirmed or missing context yields facts/actions or a follow-up question, not "growth" or
    "new challenge" filler.
  - No values are copied into `CANDIDATE_PROFILE`.
