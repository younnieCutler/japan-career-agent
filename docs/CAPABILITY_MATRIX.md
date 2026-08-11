# Capability matrix

What works with no plugin host, what a host makes better, and what only a host can do. The point of
this table is that the gaps are written down rather than smoothed over: a capability listed as
equal has to be equal, and one that is not has to say so.

## How to read it

| Class | Meaning |
|---|---|
| `core` | Runs from the CLI with no host. Deterministic, and the same result from every entry point. Every `core` row names a command `build_parser()` actually defines, and `scripts/check_capability_matrix.py` fails the build if one does not. |
| `host-enhanced` | Works without a host, and works better with one. The underlying facts are identical; the host changes how you get to them. |
| `host-only` | Needs the host. Nothing in the canonical record depends on it. |
| `not-supported` | Deliberately absent everywhere. Listed so its absence is a decision rather than a gap. |

`local CLI` means `japan-career-agent <command>`, whether reached by `npx`, `uvx`, `pipx run`, or a
persistent install. Those four are the same program.

## The record

| Capability | Class | Command | Local CLI | Claude plugin | Codex plugin |
|---|---|---|---|:--:|:--:|
| Create a Career Vault | `core` | `setup` | ✅ | ✅ | ✅ |
| Start the local loopback GUI | `core` | `ui` | ✅ | — | — |
| Inspect resumable 棚卸し sessions | `core` | `sessions` | ✅ | ✅ | ✅ |
| Resume a 棚卸し draft and submit an approval-gated proposal | `host-enhanced` | `ui` | ✅ local form | — | — |
| Diagnose a Vault, repair its structure | `core` | `doctor` | ✅ | ✅ | ✅ |
| See what is confirmed and what is pending | `core` | `status` | ✅ | ✅ | ✅ |
| Record work as a proposal | `core` | `run` | ✅ | ✅ | ✅ |
| Review a pending item before deciding | `core` | `proposals` | ✅ | ✅ | ✅ |
| Approve, with evidence required | `core` | `approve` | ✅ | ✅ | ✅ |
| Replay an interrupted approval | `core` | `approve` | ✅ | ✅ | ✅ |
| Restore a state snapshot without rewinding the ledger | `core` | `restore-state` | ✅ | ✅ | ✅ |
| Record a context, a project, a work event | `core` | `add-context`, `add-project`, `link-work-event` | ✅ | ✅ | ✅ |
| Read the Context → Experience → Evidence structure | `core` | `contexts`, `experiences`, `projects` | ✅ | ✅ | ✅ |
| Readiness across independent dimensions | `core` | `readiness` | ✅ | ✅ | ✅ |
| Maintenance prompts while employed | `core` | `maintenance-check`, `weekly-review` | ✅ | ✅ | ✅ |
| Evidence pool for answering a JD | `core` | `evidence-pool` | ✅ | ✅ | ✅ |
| Build a document model for one target | `core` | `document-model` | ✅ | ✅ | ✅ |
| Deterministic fidelity gate over a draft | `core` | `document-check` | ✅ | ✅ | ✅ |
| Render a checked document to HTML | `core` | `document-render` | ✅ | ✅ | ✅ |
| Private document store, kept out of the repository | `core` | `private-doctor`, `private-import`, `private-list` | ✅ | ✅ | ✅ |
| Shared read-only context for other skills | `core` | `context` | ✅ | ✅ | ✅ |
| Guided menu: record, review, approve in one flow | `host-enhanced` | `guided` | ✅ deterministic menu | ✅ conversational | ✅ conversational |
| Turn a sentence into a proposal | `host-enhanced` | `run --mode chat` | ✅ keyword routing | ✅ model routing | ✅ model routing |
| Find the right skill for what you are doing | `host-enhanced` | — | ⚠️ read the table in the README | ✅ SKILL.md discovery | ✅ SKILL.md discovery |
| Draft a 職務経歴書 from confirmed evidence | `host-enhanced` | `document-model` then the host | ⚠️ model and gate only, no prose | ✅ | ✅ |
| Status line in the host's own chrome | `host-only` | — | — | ✅ | ⚠️ host-dependent |
| Submit an application, send a recruiter message | `not-supported` | — | — | — | — |
| Predict whether you will be hired | `not-supported` | — | — | — | — |
| Import an arbitrary `.docx` as a template | `not-supported` | — | — | — | — |

## Two rules this table exists to keep

**A plugin never writes canonical state outside the core contract.** Every write goes through the
same approval path, so a host cannot approve on your behalf, skip the evidence requirement, or add a
fact the CLI would have refused. If a host could, the `core` rows above would be a claim rather than
a fact.

**`host-enhanced` is not a euphemism for missing.** The rows marked `⚠️` say what the CLI actually
does, not what it approximately does. Keyword routing is not model routing; a document model is not
a drafted document. Making those look equal would be the failure this table is for — and the reverse
would be too, so `core` rows carry no asterisk.

## Where the boundary is enforced

- `scripts/check_capability_matrix.py` — every `core` row's command exists in the parser.
- `scripts/check_career_agent_boundaries.py` — the CLI, the owners and the domain stay in that order.
- [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md) — what those checks mean and why.
