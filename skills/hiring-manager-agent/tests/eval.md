# Hiring Manager Agent Test Cases

Run these when iterating on the `hiring-manager-agent` skill.

## Test Case 1: COMPANY_PROFILE schema conformance
**Objective**: Output YAML matches `_shared/schemas.yml` (v1.6) `company_profile`.
- **Input**: Paste a JD (必須条件/歓迎条件 format) and complete the flow with mock answers.
- **Criteria**:
  - Required fields present: company_name, position, required_skills.
  - top_performer_spi3 / top_performer_portable_skills use the shared sub-schemas (0–10 floats, 1–5 ints,
    9-element `portable_skills_schema`).
  - Unassessed fields are `null`, not guessed.
  - Saved to `data/company_profiles/{slug}.yml`.

## Test Case 2: Top-performer profiling is interactive
**Objective**: Top-performer traits come from the hiring manager's answers, not inference from the JD.
- **Input**: JD only, no team information volunteered.
- **Criteria**:
  - Skill asks about the actual top performer (behaviors, background) 2–3 questions at a time with STOP.
  - It does not silently derive top-performer SPI3 from the JD text alone.

## Test Case 3: JD optimization never invents facts
**Objective**: Semantic optimization = rewording real conditions for ontology match, not adding benefits.
- **Input**: A sparse JD with no salary/remote info; ask "make it attractive".
- **Criteria**:
  - Rewrite improves skill-ontology recognizability (canonical skill names, 表記揺れ fixed).
  - No invented salary range, remote policy, or culture claims; missing attractors are flagged as
    questions back to the company, not filled in.

## Test Case 4: Well-being self-rating honesty
**Objective**: Culture branding grounded in the company's own 1–5 self-rating.
- **Input**: Manager self-rates Manager Quality = 2.
- **Criteria**:
  - The branding output does NOT claim strong management culture; it flags the gap and its retention
    implication instead (score honesty rule).

## Test Case 5: Disambiguation
**Objective**: JD + URL routes away correctly.
- **Input**: JD text plus a doda URL.
- **Criteria**: Skill applies the suite JD-disambiguation rule — offers `kigyou-bunseki` (research mode)
  or confirms the user wants hiring-side optimization; does not silently do both.
