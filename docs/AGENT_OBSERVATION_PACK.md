# Agent observation pack

This repository has a local, opt-in observation pack for coding-agent development loops. Its goal
is narrow: reduce repeated model context spent on long command output **without** hiding the exact
evidence needed to debug or review a failure.

## Default agent workflow

For a full repository verification pass during agent-driven development, prefer:

```bash
python scripts/run_agent_checks.py
```

It runs the unchanged canonical matrix:

```bash
python scripts/run_all_checks.py
```

but captures the matrix stdout/stderr locally and returns a compact receipt. The wrapper preserves
the canonical exit code. It does not skip tests, change their order, retry failures, or reinterpret
a result.

A successful run is retained by default because it can be useful as release evidence. To avoid
retaining a successful run while still preserving failures:

```bash
python scripts/run_agent_checks.py --no-pack-success
```

CI and release workflows continue to use `scripts/run_all_checks.py` directly. The observation pack
is an agent-facing presentation/storage layer, not a new source of pass/fail truth.

## Generic command packing

Any noisy local command can be run through the generic entry point:

```bash
python scripts/agent_observation_pack.py run \
  --label "focused routing tests" \
  -- python skills/career-agent/test_routing.py
```

A failed command always produces a handle and an exact bounded tail excerpt. A successful command
is packed only when its combined stdout/stderr reaches the default 8 KiB threshold, unless
`--always-pack` is supplied.

## Exact recall

A receipt such as `obs-0123456789abcdef` can be recalled in bounded windows:

```bash
python scripts/agent_observation_pack.py show obs-0123456789abcdef
python scripts/agent_observation_pack.py show obs-0123456789abcdef --stream stderr --start-line 120 --lines 40
```

The archive stores stdout and stderr as base64-encoded raw bytes and records SHA-256, byte count,
and line count for each stream. A read verifies the content-derived handle and those recorded
properties before displaying anything. The compact failure excerpt is copied directly from the
archived stream; there is no LLM summarizer and no generated causal explanation.

Invalid handles are rejected before path construction, so a handle cannot escape the archive
root. Writes use a temporary file followed by atomic replacement. On POSIX systems the directory
and observation files are also restricted to owner access on a best-effort basis.

## Storage and security

The default archive is:

```text
.agent-observations/
```

It is explicitly gitignored. It may contain test output, local paths, environment-dependent
messages, or other sensitive diagnostics. Treat it as local debugging data:

- do not attach or publish an observation without reviewing it;
- do not treat the archive as a product or career-data persistence layer;
- delete it manually when the evidence is no longer needed;
- no archive is uploaded automatically and no remote model is called by this mechanism.

The archive is intentionally not auto-deleted when a command finishes. Automatic deletion would
make a compact receipt unverifiable after the fact.

## Why this is separate from Routing Autoresearch

`docs/routing-autoresearch-program.md` describes a frozen judging harness. Its evaluator, runner,
contract tests, and fixtures are digested into each experiment identity. Injecting this helper into
that runner would change the judging harness and invalidate existing baselines.

The existing Routing Autoresearch loop already implements the more important capability-floor
rule: decision-philosophy, safety, and focused regressions are evaluated before held-out accuracy,
and higher accuracy cannot buy back an earlier contract failure. This change therefore does not
rebuild that logic. It addresses the remaining development-harness cost: transporting and rereading
large command observations.

## Non-goals

This is not a general model-context compressor, not an automatic semantic log summarizer, and not a
replacement for the canonical repository matrix. It does not patch Claude Code, Codex, Pi, or any
other host. It only gives repository-aware coding agents a smaller default observation with exact,
local recall when they need the full evidence.
