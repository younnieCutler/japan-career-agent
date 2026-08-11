# Repository architecture

```text
_shared/
  decision_philosophy.md   # axes, vocabulary, trust boundary, legacy policy
  schemas.yml              # canonical data contracts
  career_claims.yml        # dated external claims
  matching_v3.py           # default evidence_based_v3 diagnosis
  mhlw_reference.py        # optional licensed reference interface
  legacy_experimental.py   # opt-in legacy_v1 compatibility
  pipeline_store.py        # lock/atomic pipeline writes
scripts/                   # deterministic checks and writers; no LLM in the path
data/                      # gitignored personal state
skills/                    # stage-specific user workflows and lazy references
hooks/                     # prompt-time status-bar integration
```

The local GUI is a peer entrypoint. Its resumable 棚卸し session store belongs to the
APPLICATION owner `skills/career-agent/sessions.py`; `gui/tanaoroshi.py` is only the deterministic
form adapter. Transient drafts live under `01-capture/gui/`, while canonical evidence remains an
approval-gated `02-state` write.

Durable GUI Company/Application cases and artifact metadata belong to the APPLICATION owners
`skills/career-agent/case_store.py` and `artifact_store.py`. They live under the existing
`03-active/gui/` directory, keep `data/pipeline.yml` company-scoped, and never mutate the canonical
ledger. `gui/cases.py` and `gui/artifacts.py` are adapters only.

The active default is evidence-based diagnosis. Legacy numeric data remains readable for
reproducibility but is deprecated, read-only, and never merged into a v3 result.
