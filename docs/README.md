# Documentation

🌐 **English** · [한국어](README_ko.md) · [日本語](README_ja.md)

Everything that is not on the [project README](../README.md). Start at the top if you are new;
the later sections are reference and history.

## Getting started

| Document | What it answers |
|---|---|
| [`cli-reference.md`](cli-reference.md) | The local commands: setup, guided menu, recovering past experience, building and rendering a 職務経歴書, starting the GUI |
| [`upgrading.md`](upgrading.md) | Which version the marketplace installs, local fallback, and moving up from 2.0.x when this was `japan-recruit-ai-agent` |

## Concepts and contracts

| Document | What it answers |
|---|---|
| [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) | What works with no host, what a host improves, and what needs one |
| [`FOUR_SKILL_EVOLUTION_DECISIONS.md`](FOUR_SKILL_EVOLUTION_DECISIONS.md) | Run identity and the routing decision rule behind the four-skill split |
| [`HUMAN_OVERSIGHT.md`](HUMAN_OVERSIGHT.md) | Why judgment is separate from approval, the L0-L3 impact model, and the human-first reveal contract |
| [`_shared/decision_philosophy.md`](../_shared/decision_philosophy.md) | Why evidence, `Unknown` and confirmed conflicts behave the way they do |
| [`_shared/schemas.yml`](../_shared/schemas.yml) | The canonical profile, pipeline and rules schemas |
| [`_shared/career_claims.yml`](../_shared/career_claims.yml) | Time-sensitive external claims and their expiry |

## GUI

| Document | What it answers |
|---|---|
| [`GUI_DESIGN_DECISIONS.md`](GUI_DESIGN_DECISIONS.md) | Durable design source of truth and the UI implementation contract |
| [`GUI_REQUIREMENT_TRACE.md`](GUI_REQUIREMENT_TRACE.md) | The Capture → Review → Confirm acceptance record |
| [`GUI_MUTATION_COMPLETENESS.md`](GUI_MUTATION_COMPLETENESS.md) | Which GUI mutations are complete, and against which revision |

## Architecture

| Document | What it answers |
|---|---|
| [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md) | The module-layer rules the boundary check enforces, and how to add a command |
| [`PRIVATE_CAREER_DATA_PRD.md`](PRIVATE_CAREER_DATA_PRD.md) | The private career data store, personal timeline and fresh-context design |

## Maintainer

| Document | What it answers |
|---|---|
| [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md) | Verify, release, publish to the registries, move the marketplace ref, recover from a failure |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | What to read before changing the repository |
| [`CHANGELOG.md`](../CHANGELOG.md) | Release history |

The canonical local verification command is:

```bash
python scripts/run_all_checks.py
```

The release guard is [`scripts/check_version_bump.py`](../scripts/check_version_bump.py). The
release version is owned by `pyproject.toml` and written into the plugin and npm manifests by
[`scripts/sync_version.py`](../scripts/sync_version.py); nothing else should be edited by hand.
Documentation facts that can be derived from code are held in place by
[`scripts/check_docs_drift.py`](../scripts/check_docs_drift.py).

## History and experiments

Records of work that has already concluded. Kept because the reasoning is not recoverable from the
code, not because they describe current behaviour.

| Document | What it answers |
|---|---|
| [`LLM_JUDGE_PILOT.md`](LLM_JUDGE_PILOT.md) | The LLM-as-judge pilot on `job-seeker-agent`, and why it was not adopted |
| [`LLM_JUDGE_V2_AUTORESEARCH.md`](LLM_JUDGE_V2_AUTORESEARCH.md) | The v2 fixed-corpus judge experiment and its provisional result |
| [`ROUTING_AUTORESEARCH.md`](ROUTING_AUTORESEARCH.md) | The phase 0–2 routing-autoresearch implementation record |
| [`routing-autoresearch-program.md`](routing-autoresearch-program.md) | The operating instructions given to the research agent |
| [`routing-autoresearch-results.tsv`](routing-autoresearch-results.tsv) | The append-only experiment log |
| [`UX_REGRESSION_EVAL.md`](UX_REGRESSION_EVAL.md) | The P2 UX evaluation contract for synthetic conversation output |