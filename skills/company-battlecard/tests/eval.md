# Company Battlecard Test Cases

Run these when iterating on the `company-battlecard` skill.

## Test Case 1: Two companies + CANDIDATE_PROFILE
**Objective**: Personalized 5-dimension battlecard.
- **Input**: Two COMPANY_PROFILE YAMLs + a CANDIDATE_PROFILE, "어디가 나한테 맞아?"
- **Criteria**:
  - All 5 dimensions scored (SPI3 culture fit / skill match / well-being / growth / practical factors).
  - Per-dimension winner marked; final verdict names one company with the deciding dimensions.
  - Candidate's wellbeing_priorities actually drive the well-being row (not generic).
  - ±10pt LLM-approximation disclaimer present at the report boundary.

## Test Case 2: Incomparable data marked, not guessed
**Objective**: Missing fields degrade honestly.
- **Input**: Company A has salary_range; Company B is a Wantedly-style profile with salary hidden.
- **Criteria**:
  - Salary row shows 比較不可 for B; the practical-factors dimension notes reduced confidence.
  - No estimated salary invented for B.

## Test Case 3: No candidate profile
**Objective**: Graceful generic mode + upstream suggestion.
- **Input**: Two company profiles only.
- **Criteria**:
  - Battlecard runs on company-side facts; personalization rows (SPI3 fit, well-being alignment) marked
    unavailable.
  - Suggests running `job-seeker-agent` (or pasting CANDIDATE_PROFILE) for personalized scoring.

## Test Case 4: Score honesty on a lopsided match
**Objective**: Anti-sentiment rule.
- **Input**: Candidate profile clearly misfits both companies (low skill overlap, opposite SPI3).
- **Criteria**:
  - Verdict states both are weak fits; it does NOT crown a "winner" as if it were a good option without
    stating the absolute level ("A wins 4/5 dimensions, but overall fit is C-level for both").

## Test Case 5: 3+ companies
**Objective**: Table scales beyond pairwise.
- **Input**: Three company profiles.
- **Criteria**: Single consolidated table (not sequential pairwise cards); one final ranking with rationale;
  offer decision hands off to `tenshoku-strategy` STEP 3 → 3-2 (negotiate/offer) → 3-3 (労働条件通知書
  review) → 4 (resign) → 4-2 (onboard).

## Test Case 6: Career Value Fit veto
**Objective**: A confirmed dealbreaker can override a higher numeric total without changing the five scores.
- **Input**: Two company profiles and confirmed `must_have`/`avoid` values; one company has direct
  conflicting evidence, the other has no evidence.
- **Criteria**:
  - The conflicting company is marked ineligible even if its numeric total is higher.
  - Missing evidence is `Unknown`, not a veto.
  - If all companies conflict, the verdict states that no acceptable winner exists.
