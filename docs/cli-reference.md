# CLI reference

The local runtime keeps the personal Career Vault as canonical state and projects per-company
workflow state into `./data/pipeline.yml`.

Everything here runs the same program the plugin and the `npx`/`uvx` entry points run. Nothing on
this page needs a host.

## Setup and the guided menu

For an explicit local setup and guided menu:

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py setup --vault "$VAULT" --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault "$VAULT"
```

`guided` shows setup status, pending proposals, `Unknown` and `Conflict` counts, workspace metadata,
and valid next actions. Use `--choice <id-or-number>` for scripted input. A write-capable action
also requires `--confirm`; guided mode does not approve proposals automatically or read private note
bodies.

### Output format

`--format` accepts `human` or `json` and defaults to whichever suits the caller: `human` when both
stdin and stdout are an interactive terminal, `json` otherwise. A pipe, a redirect, `$(...)`, a
plugin host and a test all fall on the `json` side of that, so the machine contract is unchanged;
pass `--format json` explicitly if you want it at a terminal too.

At a terminal `guided` goes further than printing the menu: it reads your choice from stdin and runs
it, which is the walkthrough the README describes. `--choice` bypasses the prompt.

## Recover past experience, then write for one target

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
rounded, `支援` (supported) written as `主導` (led), a JD keyword presented as a technology you used,
a team's result written as your own, or an internal project name where an `external_label` exists.
Passing means no known protected-claim violation is present — not that the Japanese has been proven
faithful, which is why you read the document before sending it.

Rendering writes HTML with A4 print CSS; use your browser's print-to-PDF. Documents are never
overwritten: the filename carries a digest of the evidence, JD, template and wording, so
regenerating after a change writes a new file and leaves the old one alone. `./career-docs/` is not
tracked by Git.

## Start the local GUI

The GUI is one more command from the same runtime. It binds to loopback on a random port and prints
a URL carrying a single-use token; `--no-browser` prints that URL instead of opening a browser.

```bash
python skills/career-agent/career_agent.py ui --vault "$VAULT" --port 0
python skills/career-agent/career_agent.py sessions --vault "$VAULT" --format human
```

Starting the server writes nothing. What the GUI saves — drafts, cases, artifact metadata — stays
out of the canonical ledger until you approve it. `sessions` reads the same resumable session store
from the terminal, so neither entry point owns it.

Design decisions and the UI implementation contract are in
[`GUI_DESIGN_DECISIONS.md`](GUI_DESIGN_DECISIONS.md).

## Skill invocation

Selecting a Skill is not the same as running it. `run --mode chat` and `skills` report which Skill a
request would use; `skill-open` and `skill-report` are how a host records that it actually ran one.
When a Skill needs a host and none is available, the runtime returns `unsupported` instead of
answering as if it had run.

## The full contract

This page covers the commands most people reach for. The complete CLI contract — every subcommand,
flag, exit code and output shape — is in
[`skills/career-agent/SKILL.md`](../skills/career-agent/SKILL.md).
