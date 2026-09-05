# Architecture boundaries

The rules `scripts/check_career_agent_boundaries.py` enforces, and why each one is worth a build
failure. Read this before moving a function between modules in `skills/career-agent/`.

Its two companions: [`CAPABILITY_MATRIX.md`](CAPABILITY_MATRIX.md) for what runs with and without a
plugin host, and [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md) for verification, release and
schema migration.

## The layers

```
Entry            npx · uvx · pipx · installed CLI · Claude plugin · Codex plugin
                                    │
Command line     cli_parser.py      │  command/argument contract only
                 command_line.py    │  output projection and process exit behavior
                 dispatch.py        │  command → owner, and nothing else
                                    ▼
Application      onboarding · diagnostics · views · experiences · documents
                 guided_flow · approvals · ingest · sessions · case_store · artifact_store
                 judgments
                                    ▼
Domain           models · validation · persistence · vault · routing · proposals
                 lifecycle · projection · document · render · personal_timeline
                 private_store · ux · localization
                 execution_plans
                                    ▼
Local data       Career Vault · event ledger · judgment ledger · private store · data/pipeline.yml
```

The local GUI is a peer entrypoint, not a CLI frontend. `career-agent ui` has one directional
bridge in `dispatch.py` to `gui.server`; GUI modules do not import `cli_parser`, `command_line`,
`dispatch`, `runtime`, or domain modules directly. `gui.templates` is the application-owned adapter
that reuses the domain renderer's escaped slots. This keeps the browser surface from becoming a
second canonical writer or a hidden CLI dependency.

`sessions.py` is the shared APPLICATION owner for resumable workflow state. `gui.tanaoroshi.py`
translates semantic form actions into that owner; it does not own the files. A draft or checkpoint
can be written to the transient capture area, but only the existing `approvals.approve` →
`lifecycle.approve` path can append canonical evidence. The CLI `sessions` command reads this owner
directly for resume inspection; it does not import the GUI adapter, while `ui` remains the only
entrypoint bridge that launches `gui.server`.

`case_store.py` and `artifact_store.py` own durable GUI metadata under `03-active/gui/`. The
`gui.cases` and `gui.artifacts` modules are adapters: they never import persistence or Vault
directly. Case/archive/delete and artifact version operations are metadata-only; the canonical
ledger and the company-scoped `data/pipeline.yml` projection remain separate.

`case_store.context_relationship()` is the application-owned source of truth for whether a career
context is employment-like or non-work. Both strict writes and GUI projections call it, so company,
freelance, education, personal, volunteer, and other contexts cannot acquire different semantics
through different entrypoints. Human renderers call namespaced labels in `localization.py`; stored
enums, JSON/YAML output, and command arguments remain canonical.

`judgments.py` is the application owner for Human Oversight records. Its append-only
`02-state/judgments.jsonl` ledger is deliberately not part of canonical career evidence: recording a
human initial judgment, agent assessment, human final judgment, or later outcome never appends to
`events.jsonl`, never changes `proposals.jsonl`, and never projects into career state. It reuses the
Vault-wide lifecycle lock only to serialize phase order. Approval answers whether reviewed evidence
may become canonical; judgment records how a consequential decision was assessed. The two trust
boundaries must not collapse into one writer.

Dependencies point down. Application modules may call each other sideways; the graph stays acyclic.
Nothing at any layer imports an entry point, and the domain does not know that a CLI exists.

`runtime.py` sits outside this stack. It imports from every layer and implements none of it.

`execution_plans.py` owns only bounded Gate D plan snapshots and next-step reconciliation. It may
read the existing invocation ledger, but it never calls a Host, writes career facts, or creates a
second invocation ledger.

## The rules

**1. No module imports `runtime`.** The facade is a leaf. `TRANSITIONAL_RUNTIME_IMPORTERS` is the
allowlist that made the staged extraction possible; it is empty and stays empty.

**2. `runtime.py` defines nothing.** No `def`, no `class`, at module level. This is the executable
form of "a new command needs no change to the facade", and it is checked by looking for definitions
rather than by counting lines — a size budget is satisfied by reformatting, this is not.
`scripts/test_career_agent_boundaries.py` drives the rule with a synthetic definition, so it is
known to fail and not merely known to pass.

**3. No owner imports the CLI layer.** An application module that reached back up into
`cli_parser`, `command_line`, or `dispatch` would mean a command could only be understood by reading
the parser or execution boundary, which is the thing the split was for.

**4. `models` and `validation` are pure.** No `os`, `pathlib`, `tempfile`, `tomllib`, `yaml`,
`pipeline_store` or `self_analysis_profile`, and no module-level I/O. They are the contract every
other module agrees on, so they cannot depend on where anything is stored.

**5. Every owned symbol has one home.** `OWNED_SYMBOLS` maps a name to the module allowed to define
it. Re-exporting is fine — an import is not a definition — but two definitions of `approve` in two
files is how the two quietly start disagreeing.

**6. No cycles.** Checked over the whole module graph, not just the new modules.

## The one sanctioned exception

`approvals.approve` re-declares a symbol owned by `lifecycle`. It is allowed because it is a thin
facade: a single `return lifecycle.approve(...)` that injects the pipeline writer and the state
projector. The approval rules themselves stay in `lifecycle`.

`THIN_FACADES` names that one pair explicitly rather than allowing "any one-line wrapper anywhere",
because the general version of this exception is how ownership erodes.

## The monkeypatch surface, and what changed in 2.2.0

`approvals.pipeline_file` is the binding that decides where an approval's projection lands. Patch
that one. Patching a re-export of the name elsewhere — including `career_agent.pipeline_file` —
rebinds an attribute nothing reads, and the write goes to the real path.

**This is a behaviour change, stated rather than implied.** Before 2.2.0 the approval writer lived
in `runtime` and resolved `pipeline_file` as its own module global, so patching `career_agent`
worked. It no longer does. A name resolving and a binding redirecting are different promises, and
only the first one survived the split — an owner module that reached back through the façade to
resolve its imports would reintroduce the dependency the boundary rules exist to prevent.

The claim is narrowed on purpose rather than restored: the only patchers were this repository's own
tests, and `career_agent.pipeline_file` was a test seam, not a documented integration API. If that
turns out to be wrong for someone, the fix is a documented seam in `approvals`, not a global whose
value silently disagrees with the module that uses it.

Worth knowing before moving `_pipeline_writer_for` again: the test that catches this mistake is a
pipeline-content assertion several steps later, not an import error.

## The compatibility surface

`runtime.__all__` names every export explicitly, including the underscore-prefixed ones. They are
private to this package and public to the callers that already reached for them, so removing one is
a visible edit rather than a side effect of moving code.

Four bindings outside this package depend on it:

| Binding | Used by |
|---|---|
| `runtime.main` | `packaging/japan_career_agent/cli.py` — the console script |
| `runtime.build_parser` | `skills/career-agent/test_private_store.py` |
| `career_agent.{pipeline_file, PIPELINE_STAGE, upsert_pipeline_entry, select_context}` | `scripts/test_policy.py` |
| `career_agent.os` | `skills/career-agent/test_state_durability.py`, which patches `os.replace` and `os.fsync` to inject write failures |

`command_line.build_parser` remains a compatibility re-export of the canonical
`cli_parser.build_parser`; `runtime.build_parser` therefore keeps resolving without giving
`command_line.py` parser ownership again.

`career_agent.py` aliases the runtime into `sys.modules`, so `import career_agent` returns the same
module object.

## Adding a command

1. Write the function in the owner module for its area, or add an owner module if none fits.
2. Add the subparser to `cli_parser.build_parser`.
3. Add one branch to `dispatch._run_vault_command`, or to `run_command` if it must work before a
   Vault exists.
4. Add the symbol to `OWNED_SYMBOLS` and, if the module is new, to `DOMAIN_MODULES` and
   `APPLICATION_MODULES` in `scripts/check_career_agent_boundaries.py`.
5. Re-export from `runtime.py` only if something outside the package needs the name.

Nothing in that list is an edit to `runtime.py`'s behaviour. If a step seems to require one, the
function is in the wrong module.

## The exit-code contract

Only the commands that answer a question report the answer as an exit status: `setup`, `guided`,
`private-*`, `document-check`, `document-render`. Those set `context["ok_is_exit_status"]` in
`dispatch`, and `command_line._emit` returns 2 when their result is not `ok`.

Every other command returns 0 on success regardless of what it found. `doctor` reporting problems is
a successful `doctor`: a script that treated a new warning as a crash would stop working the day one
appeared. Errors are different — a `CareerError` exits 2 from any command.

`skills/career-agent/test_golden_cli.py` pins both halves.

## Human judgment boundary

`review_policy.py` owns deterministic L0-L3 interaction policy; callers never supply the effective impact. `judgments.py` owns the append-only decision lifecycle. `gui/judgments.py` adapts that lifecycle to browser-safe read/write payloads, while `gui/server.py` remains transport only. Raw unresolved evidence references do not cross the browser boundary. A Host may persist the Agent assessment with the `judgment assess` CLI command, but Python still never calls an LLM host.
