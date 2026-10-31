# Repository architecture

```text
_shared/
  decision_philosophy.md   # axes, vocabulary, trust boundary, legacy policy
  schemas.yml              # canonical shared data-contract documentation
  career_claims.yml        # dated external claims
  matching_v3.py           # default evidence_based_v3 diagnosis
  document.py              # deterministic document model & protected-claim fidelity gate
  render.py                # deterministic HTML template renderer (_shared/templates/)
  localization.py          # KO/JA/EN status-bar domain vocabulary
  application_learning.py  # application outcome/learning history + deterministic patterns
  mhlw_reference.py        # optional licensed reference interface
  legacy_experimental.py   # opt-in legacy_v1 compatibility
  pipeline_store.py        # lock/atomic pipeline and local YAML writes
scripts/                   # deterministic checks and writers; no LLM in the path
data/                      # gitignored personal workspace state
skills/                    # stage-specific user workflows and lazy references
hooks/                     # prompt-time status-bar integration
```

Workspace application state has separate surfaces under `./data/`. `data/pipeline.yml` is the
current per-company kanban/projection. `data/applications.yml` is the application-level outcome and
learning history owned by `_shared/application_learning.py`; repeated applications to one company do
not overwrite older closed outcomes. `data/evidence.yml` holds user-confirmed career contexts,
projects, and evidence entries. None silently mirrors another.

The active default is evidence-based diagnosis. Legacy numeric data remains readable for
reproducibility but is deprecated, read-only, and never merged into a v3 result.