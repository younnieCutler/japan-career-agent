# Data and workspace projection

All data paths are relative to the invocation directory unless an explicit workspace path is supplied.

| File | Primary writer | Readers |
|---|---|---|
| `data/self_analysis_profile.yml` | `jiko-bunseki` | downstream skills, confirmed values only |
| `data/candidate_profile.yml` | `job-seeker-agent` | matching and strategy skills |
| `data/evidence.yml` | `career-tanaoroshi` (user-confirmed) | `scripts/document.py`, matching, and interview skills |
| `data/company_profiles/{slug}.yml` | research/hiring skills | matching and comparison |
| `data/match_history.md` | matching skill | user review |
| `data/pipeline.yml` | `scripts/pipeline.py` (user-confirmed) | status bar, current tracking, document model, calibration |
| `data/applications.yml` | `_shared/application_learning.py` via shipped `job_search_learning.py` | tenshoku-strategy learning report |

The workspace `data/pipeline.yml` is the **current per-company projection**.

`data/applications.yml` is a separate workspace concern: it is the canonical application-outcome
and learning history for Job Search Learning Loop V1. One company can have multiple application ids.
Starting a later application may reset application-scoped fields in that company's `pipeline.yml`
projection, while the older closed application remains immutable in `applications.yml`; feedback
arriving later appends observation/classification evidence instead of rewriting the outcome.

`interest_level` is recorded independently and is not a priority signal. No skill combines it with
deadline, stage, or fit. Rules are read-only to domain skills and are promoted only through
user-approved calibration (`scripts/calibrate.py`).

A JD's evidence selection is stored per company on the pipeline entry as `primary_experience_ids`,
`supporting_experience_ids`, and `unknown_requirements`, and holds only ids and requirement names.
The confirmed evidence records stay in `data/evidence.yml`; a selection changes ordering and
presentation, never the record.

A generated document is a projection, never a source. `scripts/document.py model` and
`scripts/document.py render` read `data/evidence.yml` and write nothing to it; the target and its
evidence selection live on the pipeline entry, and rendered files go to `./career-docs/`, which Git
does not track. A rendered file is never overwritten: its name carries a digest of the evidence, JD,
template and wording behind it, and an earlier document whose inputs have since moved is reported as
outdated rather than replaced. Editing a rendered file by hand changes no career fact.

When loading a profile, identify the file and ask whether it is current. When saving, print and
verify its absolute path. Existing files require user confirmation before overwrite.