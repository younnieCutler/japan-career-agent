# Architecture boundaries

How the repository's skills, shared modules (`_shared/`), deterministic scripts (`scripts/`), and
workspace state (`data/`) fit together. See [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md) for
verification, release, and schema migration.

## The layers

```
Entry            Claude Code plugin · Codex plugin · direct script invocations
                                    │
Skills           skills/*/SKILL.md  │  conversational SOPs and evidence contracts
                                    ▼
CLI helpers      scripts/pipeline.py · scripts/document.py · scripts/job_search_learning.py
                 scripts/check_action.py · scripts/status_bar.py
                                    ▼
Shared core      _shared/pipeline_store.py · _shared/application_learning.py
                 _shared/document.py · _shared/render.py · _shared/localization.py
                 _shared/schema_contract.py · _shared/self_analysis_profile.py
                                    ▼
Local data       data/pipeline.yml · data/applications.yml · data/evidence.yml
                 data/profile.yml · data/rules.yml · career-docs/
```

## Ownership rules

1. **`_shared/pipeline_store.py` owns `data/pipeline.yml`.** All lock and atomic-write semantics for
   company-scoped pipeline state live here (`scripts/pipeline.py` is its CLI entrypoint).
2. **`_shared/application_learning.py` owns `data/applications.yml`.** Application-outcome snapshots
   and append-only learning evidence stay separate from the current per-company projection in
   `data/pipeline.yml` (`scripts/job_search_learning.py` is its CLI entrypoint).
3. **`_shared/document.py` and `_shared/render.py` own deterministic document projection, validation,
   and HTML rendering.** `scripts/document.py` projects `data/evidence.yml`, validates numbers,
   forbidden phrases, `Unknown` handling, and required sections, and renders self-contained HTML
   through `_shared/templates/shokumu_keirekisho.html`.
4. **`scripts/status_bar.py` is a read-only projection.** It reads workspace state (`data/pipeline.yml`,
   `data/rules.yml`, `data/profile.yml`) and emits a bounded `<career_status>` block without sending
   career data over the network.
5. **Domain skills do not invent evidence or bypass gates.** Missing evidence remains `Unknown`, a
   confirmed hard conflict is never offset by another strength, `interest_level` stays independent of
   objective evidence, and an unchecked interview action item keeps interview-prep generation blocked
   for that company until the user runs `python scripts/check_action.py <slug> <id>`.
