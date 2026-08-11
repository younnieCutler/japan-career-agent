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

Resumable GUI 棚卸し sessions and drafts are transient workflow material under
`01-capture/gui/{sessions,drafts}` and use the existing atomic writer. They are not canonical
evidence and do not belong under `.career-agent/` or `02-state/`; only proposal approval may create
confirmed evidence in the latter.

Durable GUI case and artifact metadata use the existing `03-active` Vault directory:
`03-active/gui/cases/*.json` and `03-active/gui/artifacts/*.json`; artifact bodies are below
`03-active/gui/artifacts/career-docs/` with digest-named filenames. These records are not a second
evidence ledger: archive/delete is a metadata tombstone, artifact updates create a new version, and
none of these operations changes `02-state` or `data/pipeline.yml`.

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

A generated document is a projection, never a source. `document-model` and `document-render` read
the ledger and write nothing to it; the target and its evidence selection live on the pipeline
entry, and rendered files go to `./career-docs/`, which Git does not track. A rendered file is
never overwritten: its name carries a digest of the evidence, JD, template and wording behind it,
and an earlier document whose inputs have since moved is reported as outdated rather than replaced.
Editing a rendered file by hand changes no career fact.

When loading a profile, identify the file and ask whether it is current. When saving, print and
verify its absolute path. Existing files require user confirmation before overwrite.
