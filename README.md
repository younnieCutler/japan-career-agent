<!-- This file is the PyPI long description as well as the GitHub landing page, so every link
     that leaves the file is absolute: PyPI resolves a relative link against nothing.
     scripts/check_docs_drift.py enforces that. -->
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
  <a href="#documentation">Docs</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/CHANGELOG.md">Changelog</a>
</p>

<p align="center">
  🌐 <strong>English</strong> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ko.md">한국어</a> ·
  <a href="https://github.com/younnieCutler/japan-career-agent/blob/main/README_ja.md">日本語</a>
</p>

---

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

Install once, then run the command:

```bash
npm install -g japan-career-agent
japan-career-agent
```

That is the complete end-user installation path. The npm package prepares its own private runtime;
you do not need to install or configure Python, uv, or pipx. The first zero-argument launch prepares
only the empty local career record the GUI needs. It does not infer, approve, or upload a career
fact. Import or paste the history you already have, then confirm only what you want to keep.

The explicit `setup`, `guided`, `ui`, and other CLI commands remain available for terminal or
automation workflows. In a plugin host, use a normal request:

```text
I want to start preparing for a job change in Japan.
Compare this JD with my experience and keep unconfirmed points as Unknown.
Help me prepare for next week's interview.
Review this 職務経歴書 without inventing evidence.
```

## Install

### Install once

The normal installation is intentionally two lines:

```bash
npm install -g japan-career-agent
japan-career-agent
```

During `npm install`, the package downloads one pinned uv binary from uv's official immutable
release, verifies its SHA-256 checksum, and uses it only inside the npm package to prepare a managed
Python and the exact matching PyPI release. It does not write to system Python, global pip, or your
Python environments. npm's own global command shim is the only PATH entry this installation needs.

**The canonical product runtime is still Python**. npm owns only installation and the command
entrypoint; CLI, GUI, plugins, approval, and the Career Vault all reach the same Python package.

### One-off and direct alternatives

For a one-off npm run, or if you already manage Python tools yourself:

```bash
npx japan-career-agent
uvx japan-career-agent
uv tool install japan-career-agent
pipx install japan-career-agent
```

`npx` uses the same self-contained npm package in its temporary cache. `uvx`, `uv tool`, and `pipx`
are advanced direct-Python alternatives; they are not prerequisites for the global npm install.

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
[The capability matrix](https://github.com/younnieCutler/japan-career-agent/blob/main/docs/CAPABILITY_MATRIX.md)
lists which is which.
## What it can help with

| Need | What you can do | Skill |
|---|---|---|
| Recover past experience | Rebuild contexts, experiences and evidence from before you installed this, from documents you already have | `career-tanaoroshi` |
| Write a 職務経歴書 for one company | Map a posting onto recorded evidence, then generate and render a document whose wording cannot outrun it | `career-document`, `humanize-japanese-career` |
| Keep a career record current | Record what happened at work as reusable evidence, whether or not you are job hunting | `career-maintenance` |
| Find direction | Reflect on work style and explore career hypotheses | `jiko-bunseki` |
| Prepare documents | Work on a resume, 職務経歴書, self-PR, and candidate profile from stated evidence | `job-seeker-agent` |
| Read roles and employers | Turn JD requirements and company or posting sources into labelled observations | `hiring-manager-agent`, `kigyou-bunseki` |
| Compare opportunities | Review candidate/JD evidence on separate axes and compare companies or offers without a total score | `matching-simulator`, `company-battlecard` |
| Prepare and keep moving | Practise interviews, plan a transition, and manage local career state and next actions | `mock-interviewer`, `tenshoku-strategy`, `career-agent` |
| Verify a planned artifact | Run the repository's existing checks at the end of a host-coordinated plan | `verify` |
| Check or challenge a planned artifact | Request understanding, source audit, adversarial review, or user-requested compression | `intent`, `factcheck`, `challenge`, `trim` |

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

## Documentation

[**The documentation hub**](https://github.com/younnieCutler/japan-career-agent/blob/main/docs/README.md)
indexes everything. The pages people reach for first:

| Page | What it answers |
|---|---|
| [CLI reference](https://github.com/younnieCutler/japan-career-agent/blob/main/docs/cli-reference.md) | The local commands: setup, guided menu, recovering past experience, building and rendering a document, starting the GUI |
| [Compatibility and upgrades](https://github.com/younnieCutler/japan-career-agent/blob/main/docs/upgrading.md) | Which version the marketplace installs, and moving up from 2.0.x |
| [Capability matrix](https://github.com/younnieCutler/japan-career-agent/blob/main/docs/CAPABILITY_MATRIX.md) | What works with no host, what a host improves, and what needs one |
| [Contributing](https://github.com/younnieCutler/japan-career-agent/blob/main/CONTRIBUTING.md) | What to read before changing the repository |

## Local-first does not mean fully offline

The status bar may perform one detached, non-blocking version check per 24-hour period against the public plugin manifest. It does not send Vault, pipeline, or candidate data. To disable that check completely, set:

```bash
export JAPAN_CAREER_NO_UPDATE_CHECK=1
```

Release history, including the persistence, context, workspace and policy hardening details, is in
[`CHANGELOG.md`](https://github.com/younnieCutler/japan-career-agent/blob/main/CHANGELOG.md) rather
than on this entry page.

## Safety

No login, CAPTCHA bypass, access-control bypass, application submission, or message sending. The suite does not fabricate resume evidence or hiring outcomes.

MIT License.
