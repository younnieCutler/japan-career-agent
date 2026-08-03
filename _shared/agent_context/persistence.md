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

When loading a profile, identify the file and ask whether it is current. When saving, print and
verify its absolute path. Existing files require user confirmation before overwrite.
