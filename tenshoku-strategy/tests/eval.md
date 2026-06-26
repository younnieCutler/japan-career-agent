# Tenshoku Strategy — Test Cases

Run these when iterating on `tenshoku-strategy`. Focus: suite-wide **Language Auto-Detection (Rule A)**,
**Fixed Step Sequence (Rule B)**, and the new **STEP 3-2 内定対応** module.

## Test Case 1: Rule A + Rule B — Korean, salary negotiation
**Objective**: Korean response, fixed entry at STEP 0 before routing to the requested module.
- **Input**: `연봉 협상 어떻게 해? 지금 최종 면접까지 갔어.`
- **Criteria**:
  - Responds in **Korean**; domain terms (年収交渉, 内定) stay in Japanese.
  - Runs **STEP 0 Situation Assessment** first (fixed entry), collecting minimal info 2–3 questions at a time,
    then routes to **STEP 3 年収交渉** (reads `references/nenshu-koushou.md`).
  - Does not dump the full strategy in one message.

## Test Case 2: Rule A + new module — Japanese, offer meeting
**Objective**: Japanese response reaches the new 内定対応 module at its fixed position (STEP 3-2).
- **Input**: `内定をもらいました。オファー面談で何を確認すべきですか？`
- **Criteria**:
  - Responds in **Japanese**.
  - Runs STEP 0 first, then routes to **STEP 3-2 内定対応** (reads `references/naitei-taiou.md`).
  - Outputs the **オファー面談 5+1 checklist** (給与理解 / 評価・昇格基準 / ミッション・キャリアパス /
    働き方 / 入社時期 / 番外 就業場所), framed as confirmation, not negotiation.

## Test Case 3: Rule B — 内定対応 sits at a fixed position regardless of entry
**Objective**: Whether the user asks about 年収 or 内定辞退 or 円満退職, the canonical order is the same.
- **Input**: `다른 회사 내정을 거절해야 하는데 어떻게 연락하지?`
- **Criteria**:
  - Routes to **STEP 3-2 内定対応 → 内定辞退** (phone script + mail template from `naitei-taiou.md`).
  - The module order is always STEP 1 (退職理由) → 2 (面接マナー) → 3 (年収交渉) → 3-2 (内定対応) →
    4 (円満退職) → 5 (市場); only the *entry module* changes, never the order.
  - Honesty Gate fires: no fabricated competing offers; decline reason kept concise and polite.

## Test Case 4: STEP 2-2 面接後フォロー / お礼メール (transplant)
**Objective**: Light JP cadence, agency-mediated branch, no over-chase, no fabrication.
- **Input**: `최종 면접 봤는데 お礼メール 보내야 해? 에이전트 통해서 지원했어.`
- **Criteria**:
  - Routes to STEP 2-2 (`references/mensetsu-follow.md`); detects エージェント経由 → advises feedback to CA first.
  - お礼メール template references a real interview point + 再現性, never invents one.
  - Warns that 過度な催促 is a minus; does not prescribe US-style 7-day chasing.

## Test Case 5: STEP 6 選考トラッキング / pattern analysis (transplant)
**Objective**: Markdown tracker in career-docs/, JP states + blockers, ≥5 threshold, ±approximation disclaimer.
- **Input**: `지금까지 지원한 8개 결과 분석해줘. 자꾸 떨어져.`
- **Criteria**:
  - Routes to STEP 6 (`references/senko-tracking.md`); uses `career-docs/applications.md` markdown table.
  - JP states (応募/書類通過/一次/二次/最終/内定/お見送り) + JP blockers (ビザ/JLPT/県外onsite/35歳/短期離職).
  - Funnel/score-vs-outcome computed by LLM (no Node script) with "±근사치, 표본 N건" disclaimer.
  - No comfort ("특별한 일 아님" banned); recommendations are action + reason + impact.

## Recorded Result (inline eval, job-seeker-agent companion run — 2026-06-26)

Rule A + Rule B were verified live on the sibling skill `job-seeker-agent` with two parallel runs
(Korean vs Japanese, same intent). Both runs:
- matched the user's language (KO→Korean, JA→Japanese) and kept 職務経歴 in Japanese script;
- executed the **identical** fixed sequence (STEP -1 → branch 中途 → STEP 0, ask 2–3, STOP).
Only the output language differed — confirming the sequence is language-invariant (Rule B) and language
auto-detects (Rule A). The same two rule blocks are present verbatim in this skill.
