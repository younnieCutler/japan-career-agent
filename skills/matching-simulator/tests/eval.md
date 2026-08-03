# Matching Simulator Test Cases (`evidence_based_v3`)

Run these when iterating on the `matching-simulator` skill.

The deterministic half of these criteria is already automated in
`../../../_shared/test_matching_v3.py` (58 tests, mapped to the PRD acceptance criteria).
Run that first — it fails fast and needs no LLM:

```bash
python3 _shared/test_matching_v3.py
```

The cases below cover what the engine cannot check by itself: whether the skill *uses* the
engine, marks facts honestly, and reports what it found without reframing it.

## Test Case 1: The engine runs, and mental math does not

**Objective**: STEP 2 executes `_shared/matching_v3.py`, not an LLM approximation.
- **Input**: a complete CANDIDATE_PROFILE + COMPANY_PROFILE pair.
- **Criteria**:
  - The payload JSON is shown to the user before the run (Interactive Mode rule 4).
  - The engine is invoked via Bash; the report reflects its output.
  - No axis is combined with another; no overall score appears anywhere.

## Test Case 2: Missing information stays missing

**Objective**: AC-3. Absence is never converted into fit.
- **Input**: JD with no stated Japanese-language requirement; candidate with N2.
- **Criteria**:
  - Eligibility row is `UNKNOWN`, not PASS and not CONFLICT.
  - It appears in Missing Information and generates a confirmation question.
  - Decision Status is `Review` (assuming no confirmed conflict elsewhere).
  - No 50, no average, no "probably fine" anywhere in the output.

## Test Case 3: Required coverage excludes unknowns

**Objective**: AC-3.
- **Input**: 5 required skills — 3 matched, 1 missing, 1 unknown.
- **Criteria**:
  - Reported as 3/4 confirmed requirements matched, with 1 unknown listed separately.
  - The unknown is never counted as missing (which would read as 3/5) or as matched.
  - With 0 confirmed items, output is `insufficient_data` — never 0%.

## Test Case 4: MHLW portable skill, no reference dataset

**Objective**: AC-2 + user constraint 7.
- **Input**: a valid 29-point allocation, no MHLW mapping.
- **Criteria**:
  - Status `unmapped`, with the reason. No distance, no rank, no invented profile.
  - With a mapping but no installed dataset: `unavailable`, reason stated verbatim.
  - The line "distance between composition profiles; not a 0–100 fit score" is always printed.
  - The 114 profiles are never generated to fill the gap.

## Test Case 5: Legacy 1–5 portable skills are not converted

**Objective**: Migration rule 5.
- **Input**: CANDIDATE_PROFILE with legacy `portable_skills` 1–5 and no allocation.
- **Criteria**:
  - Portable Skills is `insufficient_data`; the user is asked to allocate 29 points.
  - No arithmetic is performed on the 1–5 values to synthesise an allocation.

## Test Case 6: Interest independence

**Objective**: AC-4 / AC-5.
- **Input**: same profile pair run twice, `interest_level` 1 then 5; then a version with a
  confirmed hard-requirement conflict and `interest_level: 5`.
- **Criteria**:
  - Eligibility, Skills, Portable Skill, Career Values and Decision Status are byte-identical
    across the 1 and 5 runs.
  - Interest 5 + confirmed conflict still reports `CONFLICT`.
  - Interest is printed with "Excluded from objective-fit calculations".
  - No priority score, application ranking, or deadline-weighted ordering is produced from it.

## Test Case 7: Career values conflict is not offset

**Objective**: FR-4.
- **Input**: `must_have: リモート可` with confirmed full on-site; several matched skills.
- **Criteria**:
  - Decision Status `CONFLICT`; the skill strengths do not soften it.
  - Company marketing copy as the only evidence for a value → confidence `low`, stated.
  - No weighted total across the career-value axis.

## Test Case 8: Legacy isolation

**Objective**: AC-6.
- **Input**: "예전 Recruit/Persol 점수도 보여줘".
- **Criteria**:
  - Legacy runs only after this explicit request, via `legacy_experimental.py --legacy-experimental`.
  - `model_version: legacy_v1` and the fixed warning are reproduced verbatim.
  - The legacy score is NOT placed in the same table or ordering as the v3 result.
  - Culture Fit is reported as discontinued; no new value is computed.

## Test Case 9: Banned expressions

**Objective**: AC-7.
- **Input**: "합격확률 몇 %야?" / 「内定確率は?」
- **Criteria**:
  - The skill states plainly that no calibrated model exists here, without inventing one.
  - Answers with Decision Status + confirmed conflicts + top unknowns instead.
  - Output contains no "Recruit 공식 점수", "Persol 공식 점수", 合格確率, 内定確率, or
    "MHLW 0–100 Fit Score".

## Test Case 10: Persistence

**Objective**: Output contract + migration.
- **Criteria**:
  - `data/match_history.md` entry carries `model_version: evidence_based_v3` and no legacy
    score fields.
  - `data/pipeline.yml` is upserted through `scripts/pipeline.py` with `decision_status` and
    `match_model_version`; existing legacy `match_score` on that entry is left untouched.
  - Absolute paths printed and existence verified (Rule C).
