# Verified Outcomes (内定・採用実績)

Real-world offer outcomes reported by users of this skill suite in the Japanese job market.

## Reporting principles

- **Privacy-first (`synthetic` / anonymized):** Never include real candidate names, contact details, current or target company names, or verbatim resume text (`scripts/check_private_data.py` blocks personal career documents).
- **Evidence-based (`Unknown` preserved):** Unreported or private profile attributes remain `Unknown` rather than guessed.
- **Descriptive, not predictive:** Recorded outcomes document how a candidate used the skills and what happened; they are not a hiring-probability claim or outcome guarantee for future candidates.

---

## Summary

| Case ID | Period | Track | Role / Domain | Confirmed Outcome | Core Skill Chain |
|---|---|---|---|---|---|
| [`OUTCOME-2026-001`](#outcome-2026-001) | 2026-10 | 中途 (Mid-career) | `Unknown` (undisclosed) | **2 offers (`内定 2社`)** | `career-tanaoroshi` → `matching-simulator` → `career-document` → `mock-interviewer` |

---

## Case Studies

### `OUTCOME-2026-001`

- **Observed / Reported:** 2026-10 (provenance: maintainer-verified acquaintance report)
- **Track:** 中途 (Mid-career transition in Japan)
- **Role / Experience band:** `Unknown` (kept undisclosed for privacy)
- **Confirmed outcome:** **2 offers received (`内定 2社獲得`)**
- **Skills used (`core pipeline`):**
  1. **`career-tanaoroshi`** — Structured past work into reusable contexts, projects, and verifiable evidence (`data/evidence.yml`) while keeping unverified metrics as `Unknown`.
  2. **`matching-simulator`** — Compared target JDs against confirmed evidence across independent axes (hard eligibility, required skills, portable skills, conditions) without collapsing conflicts into a single score.
  3. **`career-document`** — Generated JD-tailored 職務経歴書 drafts checked by the deterministic fidelity gate (`scripts/document.py`) so wording never outran confirmed evidence.
  4. **`mock-interviewer`** — Practised structured interviews targeting the largest unresolved risks and `Unknown` gaps identified during JD matching.
- **Key takeaway:**
  - Separating confirmed evidence from `Unknown` gaps before applying prevented resume over-claiming, made JD selection disciplined, and turned missing points into concrete interview preparation topics.

---

## How to add a new outcome

When adding a new verified case to this file and the README summary table:

1. Assign the next sequential ID (`OUTCOME-YYYY-NNN`).
2. Record only user-confirmed facts (`Track`, `Period`, `Confirmed Outcome`, `Core Skill Chain`) and mark any undisclosed field as `Unknown`.
3. Run `python scripts/check_private_data.py`, `python scripts/check_policy.py`, `python scripts/check_readme_consistency.py`, and `python scripts/check_docs_drift.py` before committing.

