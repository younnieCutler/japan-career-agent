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

The active default is evidence-based diagnosis. Legacy numeric data remains readable for
reproducibility but is deprecated, read-only, and never merged into a v3 result.
