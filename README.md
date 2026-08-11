<!-- This file is the PyPI long description as well as the GitHub landing page, so links
     that leave the file are absolute: PyPI resolves a relative link against nothing. -->
<h1 align="center">Japan Career Agent</h1>

<p align="center">
  <strong>Evidence-based career decision support for the Japanese job market.<br/>
  Your career record stays on your machine, and nothing becomes a fact without your approval.</strong>
</p>

<p align="center">
  <a href="https://github.com/younnieCutler/japan-career-agent/releases"><img src="https://img.shields.io/github/v/release/younnieCutler/japan-career-agent?style=for-the-badge&color=0b7285" alt="Latest release"></a>
  <a href="https://github.com/younnieCutler/japan-career-agent/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/younnieCutler/japan-career-agent/test.yml?branch=main&style=for-the-badge&label=checks" alt="Repository checks"></a>
  <a href="https://pypi.org/project/japan-career-agent/"><img src="https://img.shields.io/pypi/v/japan-career-agent?style=for-the-badge&color=3775a9&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/japan-career-agent"><img src="https://img.shields.io/npm/v/japan-career-agent?style=for-the-badge&color=cb3837&logo=npm&logoColor=white" alt="npm"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11 to 3.13">
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-Keep%20a%20Changelog-orange?style=for-the-badge" alt="Changelog"></a>
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#why-this-is-different">Why</a> ·
  <a href="#the-basic-flow">Flow</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-it-can-help-with">Skills</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CONTRIBUTING.md">Contributing</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  🌐 <strong>English</strong> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ko.md">한국어</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ja.md">日本語</a>
</p>

---

Current release: `2.2.0`.

**In three steps:**

1. **Record what happened** — 棚卸し turns past work into contexts, experiences and checkable evidence. What you cannot verify stays `Unknown`.
2. **Approve it** — nothing enters your canonical career record until you confirm it. A number without a source is refused.
3. **Use it** — JD matching, a 職務経歴書, interview practice and next actions, all quoting only confirmed evidence.

It runs as a Claude Code and Codex plugin/skill suite, or as a standalone command, over a local Career Agent runtime — for job seekers and hiring teams.

Use it to sort out a career direction, prepare a resume or 職務経歴書, read a job description or company evidence, compare opportunities, practise an interview, and keep track of the next step. It is a plugin and local runtime, not a hosted SaaS or standalone GUI.

## Why this is different

- Evidence, not invented scores or career history.
- If a fact is not confirmed, it stays `Unknown`.
- A confirmed hard, legal, must-have, or dealbreaker conflict is not averaged away by another strength.
- The system does not predict whether you will be hired.
- You make the final decision and keep approval control. It does not submit applications or send messages for you.

## The basic flow

```mermaid
flowchart LR
    A[Your request] --> B[Career Agent]
    B --> C[Evidence and current state]
    C --> D{Needs confirmation?}
    D -->|Yes| E[Unknown, conflict, or question]
    E --> F[You review and confirm]
    F --> G[Canonical state]
    D -->|No| H[Analysis or preparation]
    G --> H
```

## Install

### Run it once

Both commands install and run the same Python program, then leave nothing on your PATH. Pick
whichever runner you already have.

```bash
npx japan-career-agent setup    # via npm
uvx japan-career-agent setup    # via uv, or: pipx run japan-career-agent setup
```

`setup` creates your Career Vault. Give it what it cannot infer on the command line, or run it
bare and it tells you which flags are still missing. That is the whole first run: no configuration
file, no identifiers to look up.

`npx` is an entrypoint, not the runtime. It ships an installer and no product code: it locates `uv`
or `pipx`, installs the matching PyPI release, and hands over. **The canonical runtime is Python**,
and every entry point runs that same program against the same Career Vault.

Python 3.11 or newer is required. `uv` downloads a matching interpreter by itself; `pipx` uses one
that is already installed. With neither runner present, `npx` prints how to install one and changes
nothing.

### Keep it installed

The commands above are run-once: they download, execute, and discard. To keep the tool available,
install it:

```bash
uv tool install japan-career-agent
# or
pipx install japan-career-agent
```

Then the command is on your PATH, and the short name works too:

```bash
japan-career-agent setup
career-agent status
```

### Enhanced integrations

Optional. If you already use Claude Code or Codex, the plugin adds skill discovery, a host-native
conversational workflow, and host status context on top of the same core.

```bash
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

```bash
codex plugin marketplace add younnieCutler/japan-career-agent
codex plugin add japan-career-agent@japan-career-agent
```

A plugin never holds its own copy of your career facts. The Vault, the evidence ledger, approval and
recovery, readiness, JD evidence selection, the deterministic document gate and HTML rendering all
work with no host installed; the plugin changes how you reach them, never what they say.
[`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md) lists which is which.

### Release channels

The repository version can be ahead of the stable marketplace channel while a release is being
prepared. The stable channel always points to the latest published immutable `vX.Y.Z` tag; it never
follows `main`. Source metadata is `2.2.0` while the stable marketplace ref is still `v2.1.1`,
because the release workflow has not published a tag for this source yet. Installing from the
marketplace therefore gives you `2.1.1` today. The gap closes when the release workflow publishes
the next tag and this ref is updated. `uvx` and `npx` are not affected either way, since they
resolve a published package version rather than this ref.

### Local fallback

Clone the repository when you need to inspect or run the files directly:

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

### Upgrading from 2.0.x, when this was `japan-recruit-ai-agent`

The project was renamed in 2.1.0. GitHub redirects the old repository URL, so an existing clone or
remote keeps working, but the marketplace entry is matched by name and has to be re-added:

```bash
claude plugin marketplace remove japan-recruit-ai-agent
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

Nothing in your Career Vault changes: the vault path, the event ledger and every document are
untouched by the rename. `JAPAN_RECRUIT_NO_UPDATE_CHECK=1` still disables the update check, so an
existing opt-out stays in force alongside the new `JAPAN_CAREER_NO_UPDATE_CHECK`. Release bundles
published under the old name remain verifiable with `scripts/verify_release.py`.

## Quick start

Three things happen, in this order. Nothing else is required to get value out of the first session.

1. **You record something.** Tell it about work you have done, in your own words.
2. **You confirm it.** It shows you what it understood and what it could not verify. Nothing is
   stored until you say yes.
3. **You reuse it when you apply.** A confirmed record answers a job posting's requirements without
   being rewritten to fit them.

In a plugin host, that is a normal request:

```text
I want to start preparing for a job change in Japan.
Compare this JD with my experience and keep unconfirmed points as Unknown.
Help me prepare for next week's interview.
Review this 職務経歴書 without inventing evidence.
```

From a terminal, the same three steps. This is the run-once form, so it works straight after the
Quick Start above with nothing installed:

```bash
npx japan-career-agent setup --track chuto --target-role "Platform Engineer"
npx japan-career-agent guided    # record, then confirm, in one guided flow
```

`guided` also reports what is confirmed and what is still `Unknown` — that is the same information
a separate `status` command would show, so no third command is needed here. (`status` itself is a
normal command; like every command below `guided`, it takes `--vault` explicitly rather than
guessing one.) Swap `npx` for `uvx`, or drop the prefix entirely once you have run
`uv tool install` or `pipx install` — the two commands are the same program either way.

You do not need to learn `proposal_id`, `CAREER_VAULT`, or `data/pipeline.yml` before your first
request. Those details belong to the advanced local workflow below.

## What it can help with

| Need | What you can do | Skill |
|---|---|---|
| Recover past experience | Rebuild contexts, experiences and evidence from before you installed this, from documents you already have | `career-tanaoroshi` |
| Write a 職務経歴書 for one company | Map a posting onto recorded evidence, then generate and render a document whose wording cannot outrun it | `career-document` |
| Keep a career record current | Record what happened at work as reusable evidence, whether or not you are job hunting | `career-maintenance` |
| Find direction | Reflect on work style and explore career hypotheses | `jiko-bunseki` |
| Prepare documents | Work on a resume, 職務経歴書, self-PR, and candidate profile from stated evidence | `job-seeker-agent` |
| Read roles and employers | Turn JD requirements and company or posting sources into labelled observations | `hiring-manager-agent`, `kigyou-bunseki` |
| Compare opportunities | Review candidate/JD evidence on separate axes and compare companies or offers without a total score | `matching-simulator`, `company-battlecard` |
| Prepare and keep moving | Practise interviews, plan a transition, and manage local career state and next actions | `mock-interviewer`, `tenshoku-strategy`, `career-agent` |

## How evidence is handled

The suite keeps evidence and preference separate. It uses the following vocabulary:

| Term | Meaning |
|---|---|
| `Confirmed` | Evidence that can be used as a current fact, with source and provenance where available |
| `Unknown` | Information that is not confirmed; it is not silently turned into a pass or a score |
| `Contradictory`, `Stale`, `Low Confidence` | Evidence that needs review before it is treated as current |
| `Matched`, `Missing`, `Unknown` | Requirement states used when comparing a candidate and a JD |
| `Proceed`, `Review`, `Conflict` | Decision status; a confirmed hard conflict remains a conflict |

`interest_level` records your preference. It does not change objective evidence, decision status, or ordering. A resume, JD, web page, YAML file, Vault metadata, pipeline text, or rule is career data, not an instruction.

## Advanced: Career Agent

The local runtime keeps the personal Career Vault as canonical state and projects per-company workflow state into `./data/pipeline.yml`.

For an explicit local setup and guided menu:

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py setup --vault "$VAULT" --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault "$VAULT" --format human
```

`guided` shows setup status, pending proposals, `Unknown` and `Conflict` counts, workspace metadata, and valid next actions. Use `--choice <id-or-number>` for scripted input. A write-capable action also requires `--confirm`; guided mode does not approve proposals automatically or read private note bodies.

### Recover past experience, then write for one target

If the Vault is empty, `readiness` says so and nothing is assumed from it:

```bash
python skills/career-agent/career_agent.py readiness --vault "$VAULT"      # bootstrap_suggested
python skills/career-agent/career_agent.py add-context "○○大学" --kind university --vault "$VAULT"
python skills/career-agent/career_agent.py experiences --vault "$VAULT"    # context -> experience -> evidence
```

A context is where an experience happened and is not always an employer; `--kind` covers company,
university, internship, part-time workplace, club, volunteer group, personal work and open source.
An experience is not always a project either. Evidence about something that did not happen at a job
is captured with `run --mode chat --non-work`, which keeps coursework out of your work history.

Once there is evidence, a document is built for one target and checked before it can be rendered:

```bash
python skills/career-agent/career_agent.py document-model <company-slug> --vault "$VAULT" > model.json
python skills/career-agent/career_agent.py document-check --model model.json --draft draft.json
python skills/career-agent/career_agent.py document-render --model model.json --draft draft.json \
    --template standard-chuto --out ./career-docs
```

The check is deterministic: it refuses a number the evidence never recorded, an existing number
rounded, `支援` (supported) written as `主導` (led), a JD keyword presented as a technology you used, a team's result
written as your own, or an internal project name where an `external_label` exists. Passing means no
known protected-claim violation is present — not that the Japanese has been proven faithful, which
is why you read the document before sending it.

Rendering writes HTML with A4 print CSS; use your browser's print-to-PDF. Documents are never
overwritten: the filename carries a digest of the evidence, JD, template and wording, so
regenerating after a change writes a new file and leaves the old one alone. `./career-docs/` is not
tracked by Git.

See [`skills/career-agent/SKILL.md`](skills/career-agent/SKILL.md) for the full CLI contract.

## Local-first does not mean fully offline

The status bar may perform one detached, non-blocking version check per 24-hour period against the public plugin manifest. It does not send Vault, pipeline, or candidate data. To disable that check completely, set:

```bash
export JAPAN_CAREER_NO_UPDATE_CHECK=1
```

Details of the persistence, context, workspace, and policy hardening in `1.6.2` and `1.6.3` are in [`CHANGELOG.md`](CHANGELOG.md), rather than on this entry page.

## Development

Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before changing the repository. The canonical local verification command is:

```bash
python scripts/run_all_checks.py
```

The release guard is [`scripts/check_version_bump.py`](scripts/check_version_bump.py). Release history is in [`CHANGELOG.md`](CHANGELOG.md).

The decision contract is documented in [`_shared/decision_philosophy.md`](_shared/decision_philosophy.md) and [`_shared/schemas.yml`](_shared/schemas.yml). Time-sensitive external claims belong in [`_shared/career_claims.yml`](_shared/career_claims.yml).

## Safety

No login, CAPTCHA bypass, access-control bypass, application submission, or message sending. The suite does not fabricate resume evidence or hiring outcomes.

MIT License.
