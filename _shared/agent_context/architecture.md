# Repository architecture

```text
_shared/
  decision_philosophy.md   # axes, vocabulary, trust boundary, legacy policy
  schemas.yml              # canonical shared data-contract documentation
  career_claims.yml        # dated external claims
  matching_v3.py           # default evidence_based_v3 diagnosis
  application_learning.py  # application outcome/learning history + deterministic patterns
  mhlw_reference.py        # optional licensed reference interface
  legacy_experimental.py   # opt-in legacy_v1 compatibility
  pipeline_store.py        # lock/atomic pipeline and local YAML writes
scripts/                   # deterministic checks and writers; no LLM in the path
data/                      # gitignored personal workspace state
skills/                    # stage-specific user workflows and lazy references
hooks/                     # prompt-time status-bar integration
```

Workspace application state has three deliberately separate surfaces. `data/pipeline.yml` is the
current per-company kanban/projection. `data/applications.yml` is the application-level outcome and
learning history owned by `_shared/application_learning.py`; repeated applications to one company do
not overwrite older closed outcomes. Durable Vault `03-active/gui/cases/*.json` Application cases are
GUI project metadata for JD/evidence/document organization, not outcome history. None silently mirrors
another.

The local GUI is a peer entrypoint. Its resumable 棚卸し session store belongs to the
APPLICATION owner `skills/career-agent/sessions.py`; `gui/tanaoroshi.py` is only the deterministic
form adapter. The read-only CLI `sessions --format json` command calls that same owner directly;
neither entrypoint owns a second session store. Transient drafts live under `01-capture/gui/`, while
canonical evidence remains an approval-gated `02-state` write.

Durable GUI Company/Application cases and artifact metadata belong to the APPLICATION owners
`skills/career-agent/case_store.py` and `artifact_store.py`. They live under the existing
`03-active/gui/` directory, keep `data/pipeline.yml` company-scoped, do not replace
`data/applications.yml`, and never mutate the canonical ledger. `gui/cases.py` and
`gui/artifacts.py` are adapters only.

The active default is evidence-based diagnosis. Legacy numeric data remains readable for
reproducibility but is deprecated, read-only, and never merged into a v3 result.