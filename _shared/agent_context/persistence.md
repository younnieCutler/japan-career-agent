# Data, Vault, and workspace projection

All data paths are relative to the invocation directory unless an explicit Vault/workspace path
is supplied.

| File | Primary writer | Readers |
|---|---|---|
| `data/self_analysis_profile.yml` | `jiko-bunseki` | downstream skills, confirmed values only |
| `data/candidate_profile.yml` | `job-seeker-agent` | matching and strategy skills |
| `data/company_profiles/{slug}.yml` | research/hiring skills | matching and comparison |
| `data/match_history.md` | matching skill | user review |
| `data/pipeline.yml` | domain skills and approved career events | status bar, tracking, calibration |

The Vault stores personal canonical flow state: track, stage, deadlines, and event ledger. The
workspace pipeline is the per-company projection. Approval projects confirmed stage/action/deadline
history but does not overwrite domain-owned decision, channel, legitimacy, interest, outcome, or
frozen legacy fields.

`interest_level` is recorded independently and is not a priority signal. No skill combines it with
deadline, stage, or fit. Rules are read-only to domain skills and are promoted only through
approval-gated `career-agent` events.

Career readiness and job-search intent live on separate axes with separate write paths.
`employment_status` and `job_search` are the user's declaration in `00-control/career-profile.toml`
and are written only by `set-employment-status` and `set-job-search`; every other path reads them.
`career_mode` is projected from events by `apply_event_to_state`, moves only when the user stated a
workflow intent, and cannot reach `active_search` while `job_search` is off. None of the three is copied into `data/pipeline.yml`: they belong to the
person, and a per-company copy would drift.

A JD's evidence selection is the opposite — per company, because it differs per JD. It is stored on
the pipeline entry as `primary_experience_ids`, `supporting_experience_ids`, and
`unknown_requirements`, and holds only ids and requirement names. The events themselves stay
append-only in the Vault ledger; a selection changes ordering and presentation, never the record.
Downstream skills read them through `career-agent work-events --confirmed`, never by parsing the
ledger.

When loading a profile, identify the file and ask whether it is current. When saving, print and
verify its absolute path. Existing files require user confirmation before overwrite.
