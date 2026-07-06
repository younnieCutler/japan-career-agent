# Matching Simulator Test Cases

Run these when iterating on the `matching-simulator` skill.

## Test Case 1: Deterministic scorer parity
**Objective**: STEP 2 uses `_shared/scoring.py`, not mental math, and matches the frameworks.md §6 worked example.
- **Input**: `python3 _shared/scoring.py --self-test`, then the worked-example JSON via stdin
  (Python s=70/w=0.5, SQL s=80/w=0.3, K8s s=20/w=0.2, p_fit=75, b_behavioral=60).
- **Criteria**:
  - Self-test prints `recruit=65.0/C`.
  - Stdin run returns `raw: 97.5`, `total: 65.0`, `grade: "C"` — identical to the frameworks.md example.
  - Skill report cites the script output and applies ±10pt caveat to inputs only.

## Test Case 2: Full YAML fast-forward
**Objective**: Both profiles pasted → STEP 0 platform anchor → STEP 0.5 legitimacy check → STEP 2 (fast-forward, never skip).
- **Input**: A complete `CANDIDATE_PROFILE` + `COMPANY_PROFILE` pair + "doda로 점수만 줘" (no URL, no JD text).
- **Criteria**:
  - STEP 0.5 is skipped only because no URL/JD text was given (pure hypothetical) — noted as "legitimacy unverifiable," not silently dropped.
  - No re-asking of fields present in the YAML (uses them as-is per Cross-Skill Data Consumption).
  - Platform still anchored (doda) before scoring; doda modifier applied.
  - Intermediate scores shown for confirmation before the combined report (Interactive Mode rule 2).
  - Final scores rounded to nearest 5, never false precision like "78.3".

## Test Case 3: Direct-apply platform branch
**Objective**: Green/BizReach replace CA perspective with Hiring Manager Direct Evaluation.
- **Input**: Same profiles, platform = Green.
- **Criteria**:
  - STEP 3 runs "Hiring Manager Direct Evaluation" — no CA opinion section.
  - Platform verdict line uses the mandatory format `[Platform] verdict: [❌/⚠️/✅] ...`.
  - Verdicts listed only for the target platform (+ any explicitly mentioned), not all 6.

## Test Case 4: Missing well-being data degrades gracefully
**Objective**: Null `wellbeing_priorities` must not fabricate a culture-fit score.
- **Input**: CANDIDATE_PROFILE with `wellbeing_priorities: null` all four factors.
- **Criteria**:
  - Culture Fit reported as unavailable/low-confidence with the reason, or the user is asked the 4 questions —
    never silently invented.
  - `scoring.py` culture block either omitted or `missing_factors` surfaced in the report.

## Test Case 5: Divergent scores are explained, not averaged into comfort
**Objective**: Anti-sentiment rule on conflicting Recruit vs Persol scores.
- **Input**: Profile pair engineered so ontology similarity is high but Core Lead Tech / SPI3 fit is low
  (e.g., adjacent-capability-only skill match).
- **Criteria**:
  - Report explains the divergence cause (e.g., "cosine rewards adjacency; Recruit-style gates on Core Lead Tech").
  - No blended "overall it balances out" framing; C-or-below triggers the plain "not actively recommended" line.
  - Match history entry appended to `data/match_history.md` per `match_history_entry` schema, AND the
    company's `data/pipeline.yml` entry is upserted with `match_score` (feeds the tenshoku-strategy
    senko-tracking §2b calibration-by-predicted-grade analysis).
