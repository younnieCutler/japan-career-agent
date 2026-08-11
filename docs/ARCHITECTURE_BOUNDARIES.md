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
Command line     command_line.py    │  the parser, and the one place a result becomes bytes
                 dispatch.py        │  command → owner, and nothing else
                                    ▼
Application      onboarding · diagnostics · views · experiences · documents
                 guided_flow · approvals · ingest
                                    ▼
Domain           models · validation · persistence · vault · routing · proposals
                 lifecycle · projection · document · render · personal_timeline
                 private_store · ux · localization
                                    ▼
Local data       Career Vault · event ledger · private store · data/pipeline.yml
```

Dependencies point down. Application modules may call each other sideways; the graph stays acyclic.
Nothing at any layer imports an entry point, and the domain does not know that a CLI exists.

`runtime.py` sits outside this stack. It imports from every layer and implements none of it.

## The rules

**1. No module imports `runtime`.** The facade is a leaf. `TRANSITIONAL_RUNTIME_IMPORTERS` is the
allowlist that made the staged extraction possible; it is empty and stays empty.

**2. `runtime.py` defines nothing.** No `def`, no `class`, at module level. This is the executable
form of "a new command needs no change to the facade", and it is checked by looking for definitions
rather than by counting lines — a size budget is satisfied by reformatting, this is not.
`scripts/test_career_agent_boundaries.py` drives the rule with a synthetic definition, so it is
known to fail and not merely known to pass.

**3. No owner imports the CLI layer.** An application module that reached back up into
`command_line` or `dispatch` would mean a command could only be understood by reading the parser,
which is the thing the split was for.

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

## The monkeypatch surface

`approvals.pipeline_file` is a binding integration tests patch to redirect where a projection lands.
The writer resolves that name in `approvals`, so patching a re-export of it elsewhere — including
`career_agent.pipeline_file` — has no effect on the write. `runtime`/`career_agent` still re-export
the name for callers that only read it.

This is worth knowing before moving `_pipeline_writer_for`: the test that catches the mistake is a
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

`career_agent.py` aliases the runtime into `sys.modules`, so `import career_agent` returns the same
module object.

## Adding a command

1. Write the function in the owner module for its area, or add an owner module if none fits.
2. Add the subparser to `command_line.build_parser`.
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
