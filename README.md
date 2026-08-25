<!-- This file is the PyPI long description as well as the GitHub landing page, so links
     that leave the file are absolute: PyPI resolves a relative link against nothing. -->
<h1 align="center">Japan Career Agent</h1>

<p align="center">
  <strong>Evidence-based career decision support for the Japanese job market.<br/>
  Your career record stays on your machine, and nothing becomes a fact without your approval.</strong>
</p>

<p align="center">
  <a href="https://github.com/younnieCutler/japan-career-agent/releases"><img src="https://img.shields.io/github/v/release/younnieCutler/japan-career-agent?style=flat-square&color=0b7285" alt="Latest release"></a>
  <a href="https://github.com/younnieCutler/japan-career-agent/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/younnieCutler/japan-career-agent/test.yml?branch=main&style=flat-square&label=checks" alt="Repository checks"></a>
  <a href="https://pypi.org/project/japan-career-agent/"><img src="https://img.shields.io/pypi/v/japan-career-agent?style=flat-square&color=3775a9&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/japan-career-agent"><img src="https://img.shields.io/npm/v/japan-career-agent?style=flat-square&color=cb3837&logo=npm&logoColor=white" alt="npm"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.11 to 3.13">
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#what-this-is">What it is</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#install">Install</a> ·
  <a href="#what-it-can-help-with">Skills</a> ·
  <a href="#how-evidence-is-handled">Evidence</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CONTRIBUTING.md">Contributing</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  🌐 <strong>English</strong> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ko.md">한국어</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ja.md">日本語</a>
</p>

---

Current release: `2.13.0`.

## What this is

A local career record you build once and reuse: for a career direction, a resume or 職務経歴書, a job
description, an interview, or the next step. It runs as a Claude Code and Codex plugin, as a
standalone command, and as an optional local GUI — over one Python runtime and one Career Vault.
Not a hosted SaaS.

**Three steps:**

1. **Record what happened** — 棚卸し turns past work into contexts, experiences and checkable evidence. What you cannot verify stays `Unknown`.
2. **Approve it** — nothing enters your canonical career record until you confirm it. A number without a source is refused.
3. **Use it** — JD matching, a 職務経歴書, interview practice and next actions, all quoting only confirmed evidence.

**What makes it different:**

- Evidence, not invented scores or career history.
- If a fact is not confirmed, it stays `Unknown`.
- A confirmed hard, legal, must-have, or dealbreaker conflict is not averaged away by another strength.
- The system does not predict whether you will be hired.
- You make the final decision and keep approval control. It does not submit applications or send messages for you.

## Quick start

Nothing is installed. `npx` and `uvx` download, run, and discard.

```bash
npx japan-career-agent setup --track chuto --target-role "Platform Engineer"
npx japan-career-agent guided    # record, then confirm, in one guided flow
```

`setup` creates your Career Vault. `guided` walks you through recording something, shows what it
understood, and stores nothing until you say yes — it also reports what is confirmed and what is
still `Unknown`, so no separate `status` call is needed here.

Swap `npx` for `uvx`, or drop the prefix once you have installed the tool. Same program either way.

In a plugin host, the same thing is a normal request:

```text
I want to start preparing for a job change in Japan.
Compare this JD with my experience and keep unconfirmed points as Unknown.
Help me prepare for next week's interview.
Review this 職務経歴書 without inventing evidence.
```

You do not need to learn `proposal_id`, `CAREER_VAULT`, or `data/pipeline.yml` first. Those belong
to the advanced local workflow below.

## Install

### Run it once

Both commands install and run the same Python program, then leave nothing on your PATH. Pick
whichever runner you already have.

```bash
npx japan-career-agent setup    # via npm
uvx japan-career-agent setup    # via uv, or: pipx run japan-career-agent setup
```

Run `setup` bare and it tells you which flags are still missing. The command it prints assumes
`japan-career-agent` is on your PATH, which `npx` and `uvx` do not leave behind — put the same
prefix back in front of it yourself.

`npx` is an entrypoint, not the runtime. It ships an installer and no product code: it locates `uv`
or `pipx`, installs the matching PyPI release, and hands over. **The canonical runtime is Python**,
and every entry point runs that same program against the same Career Vault.

Python 3.11 or newer is required. `uv` downloads a matching interpreter by itself; `pipx` uses one
that is already installed. With neither runner present, `npx` prints how to install one and changes
nothing.

### Keep it installed

To keep the tool available instead of downloading it each time:

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

Selecting a Skill is not the same as running it. `run --mode chat` and `skills` report which Skill a
request would use; `skill-open` and `skill-report` are how a host records that it actually ran one.
When a Skill needs a host and none is available, the runtime returns `unsupported` instead of
answering as if it had run.

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
| Verify a planned artifact | Run the repository's existing checks at the end of a host-coordinated plan | `sip` |

## How evidence is handled

Every request follows the same path, and the confirmation step is not optional:

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

### Start the local GUI

The GUI is one more command from the same runtime. It binds to loopback on a random port and prints
a URL carrying a single-use token; `--no-browser` prints that URL instead of opening a browser.

```bash
python skills/career-agent/career_agent.py ui --vault "$VAULT" --port 0
python skills/career-agent/career_agent.py sessions --vault "$VAULT" --format human
```

Starting the server writes nothing. What the GUI saves — drafts, cases, artifact metadata — stays
out of the canonical ledger until you approve it. `sessions` reads the same resumable session store
from the terminal, so neither entry point owns it.

See [`skills/career-agent/SKILL.md`](skills/career-agent/SKILL.md) for the full CLI contract.

## Compatibility and upgrades

### Release channels

The repository version can be ahead of the stable marketplace channel while a release is being
prepared. The stable channel always points to the latest published immutable `vX.Y.Z` tag; it never
follows `main`.

Source metadata is `2.13.0` while the stable marketplace ref is still `v2.1.1`, because the release
workflow has not published a tag for this source yet. Installing from the marketplace therefore
gives you `2.1.1` today, and the gap closes when the next tag is published. `uvx` and `npx` are not
affected either way, since they resolve a published package version rather than this ref.

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
