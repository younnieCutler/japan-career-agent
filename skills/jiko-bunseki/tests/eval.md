# Jiko-Bunseki (Self-Analysis) Test Cases

Run these when iterating on the `jiko-bunseki` skill.

## Test Case 1: Interactive pacing
**Objective**: Forced-choice pairs are delivered in small batches with STOP, never dumped.
- **Input**: "자기분석 하고 싶어" (no other context).
- **Criteria**:
  - Track question (新卒/中途) asked first.
  - Strength pairs presented a few at a time; the skill STOPs and waits after each batch.
  - No final profile output before all phases' inputs are collected.

## Test Case 2: SELF_ANALYSIS_PROFILE schema conformance
**Objective**: Output YAML matches `_shared/schemas.yml` (v1.5).
- **Input**: Complete a full Phase 1–2 run with mock answers.
- **Criteria**:
  - All `required` fields present: candidate_name, language_preference, track, top_strengths (with
    name/score 0–16/cluster), strength_clusters (0–100), work_style (1–5), wellbeing_priorities (1–5).
  - Phase 3 fields (career_anchors, derailers, energy_map, career_theme) are `null` — not omitted, not
    fabricated — when Phase 3 has not run.
  - File written to `data/self_analysis_profile.yml` (CWD-relative per Output Contract Rule C); absolute
    path printed and existence verified after the save.

## Test Case 3: Phase 3 depth layer is evidence-bound
**Objective**: Anchors/derailers/energy map derive only from user answers.
- **Input**: Run Phase 3 with terse mock answers that leave one area (e.g., energy drains) unanswered.
- **Criteria**:
  - Unanswered area yields a follow-up question or `null` — never an inferred filler.
  - Each derailer ties to a scored top strength (overuse framing), not to a new invented trait.
  - `career_theme` is one line and traceable to the user's own words.

## Test Case 4: Language auto-detection
**Objective**: Suite Rule A holds.
- **Input**: Japanese question with a Korean request sentence appended ("이 내용으로 자기분석 해줘").
- **Criteria**: Response in Korean; domain terms (自己PR, 転職軸…) stay in Japanese script.

## Test Case 5: Handoff to job-seeker-agent
**Objective**: Downstream reuse without double-scoring.
- **Input**: After a completed profile, invoke job-seeker-agent with a resume.
- **Criteria**:
  - job-seeker-agent reuses work_style / wellbeing_priorities / self_pr_seeds (skips those questions).
  - SPI3 and Portable Skills are still scored fresh by job-seeker-agent — never copied from the
    self-analysis (ownership rule).
