# Recovery

## Goal

Show safe, actionable recovery for a missing workspace, missing evidence, missing private-document
bytes, and snapshot restoration.

## Starting state

The runner creates isolated synthetic vault, workspace, and private-store directories. It injects
missing artifacts only inside that temporary state; no repository or user file is changed.

## Commands

```bash
python scripts/run_workflows.py --workflow recovery --format human
```

The runner exercises these canonical operations:

```text
career_agent.py status --workspace <missing-workspace>
career_agent.py approve <proposal-id>                 # no evidence
career_agent.py private-import
career_agent.py propose-fact
career_agent.py approve <fact-proposal-id>             # private bytes removed in the fixture
career_agent.py restore-state <persisted-version>
```

## Expected invariants

- A missing workspace reports `WORKSPACE_NOT_FOUND`, the resolved path, and a non-mutating action.
- Approval without evidence reports `EVIDENCE_REQUIRED`; no confirmed event is written.
- Approval revalidates private-document bytes and blocks when provenance is missing.
- Blocked operations report `state_changed=false` and leave canonical state unchanged.
- `restore-state` replaces only the current snapshot and retains append-only events/proposals.
- The UX explains that restore-state is recovery, not a general undo.

## Decision point

The user chooses whether to repair the missing evidence/storage or keep the proposal unapproved.

## Product does not do

- It does not bypass validation after an error.
- It does not silently recreate missing provenance.
- It does not rewind append-only history or submit an application.

## Recovery

Repair the indicated path, re-import or provide evidence, and retry the same canonical operation.
Use the persisted version only to recover the current snapshot; inspect the ledger separately.

## Repeatability

All failures are injected into a disposable synthetic temporary directory. Re-running the workflow
starts from an empty state and produces the same semantic result without relying on timestamps,
UUIDs, or full-output snapshots.
