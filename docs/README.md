# Documentation

🌐 **English** · [한국어](README_ko.md) · [日本語](README_ja.md)

Everything that is not on the [project README](../README.md). Start at the top if you are new;
the later sections are reference and history.

## Getting started

| Document | What it answers |
|---|---|
| [`OUTCOMES.md`](OUTCOMES.md) | Anonymized real-world `内定` (offer) cases and the skill chains used |
| [`upgrading.md`](upgrading.md) | Which version the marketplace installs, local fallback, and workspace files |

## Concepts and contracts

| Document | What it answers |
|---|---|
| [`_shared/decision_philosophy.md`](../_shared/decision_philosophy.md) | Why evidence, `Unknown` and confirmed conflicts behave the way they do |
| [`_shared/schemas.yml`](../_shared/schemas.yml) | The canonical profile, pipeline and rules schemas |
| [`_shared/career_claims.yml`](../_shared/career_claims.yml) | Time-sensitive external claims and their expiry |

## Architecture

| Document | What it answers |
|---|---|
| [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md) | How the skills, shared modules, and deterministic scripts fit together |
| [`AGENT_OBSERVATION_PACK.md`](AGENT_OBSERVATION_PACK.md) | How coding agents compact long local command output while preserving exact recallable evidence |

## Maintainer

- [Career knowledge maintenance](CAREER_KNOWLEDGE.md): source review, topic lookup and candidate promotion.
- [Japanese career research dossier](research/japan-career-market-2026.md): verified sources and remaining research.

| Document | What it answers |
|---|---|
| [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md) | Verify, release, move the marketplace ref, recover from a failure |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | What to read before changing the repository |
| [`CHANGELOG.md`](../CHANGELOG.md) | Release history |

The canonical local verification command is:

```bash
python scripts/run_all_checks.py
```

The release guard is [`scripts/check_version_bump.py`](../scripts/check_version_bump.py). The
release version is owned by `pyproject.toml` and written into the plugin manifests and SBOM by
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
