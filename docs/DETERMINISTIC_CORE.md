# Deterministic core, probabilistic edge

Career Agent uses an LLM or Agent Host only where interpretation is genuinely uncertain. Everything that can be expressed as a stable rule stays in Python.

The architecture rule is:

> Agent decides meaning. Runtime guarantees state.

## Boundary

The probabilistic edge may:

- interpret ambiguous user language;
- extract candidate facts;
- assess relevance or confidence;
- draft recommendations or wording;
- create or refine a proposal through supported application commands.

It must not directly mutate canonical career evidence.

The deterministic core owns:

- schema and field validation;
- routing and allowed state transitions;
- approval and recovery semantics;
- canonical event persistence;
- state projection and document generation;
- permissions, invariants, and regression checks.

Canonical evidence lives in `02-state/events.jsonl`. A candidate fact becomes canonical only through the existing approval lifecycle. `lifecycle.approve` validates the event, runs preflight invariants, records a recoverable transaction, appends the confirmed event, and only then projects state. Recovery uses the same lifecycle owner.

A Host result is therefore input, not authority. If an LLM infers a role, date, skill, company, or other fact, that output must re-enter the runtime as a proposal or review patch and pass the same validation and approval path as any other input.

## Why this is not "remove the LLM"

Pure Python is preferable for deterministic workloads because the same input can produce the same result and ordinary tests can prove the behavior. Semantic interpretation is different: wording can be ambiguous, evidence can require judgment, and useful recommendations can have more than one valid answer. Those tasks remain appropriate for the Host.

The goal is not fewer model calls by itself. The goal is a smaller model-owned state space.

## Evaluation split

Use normal unit, contract, process, and browser E2E tests for deterministic behavior. Use model evaluation only for the probabilistic edge, such as extraction quality, semantic relevance, ambiguous judgment, and generated wording.

This separation makes failures attributable: a schema, routing, persistence, or projection failure is a software defect; an extraction or judgment miss is a model-quality defect.

## Rule for new AI features

Before adding a Host/LLM step, answer two questions:

1. Can the result be computed from structured local state with a deterministic rule? If yes, keep it in Python.
2. If model judgment is necessary, what proposal or reviewed input crosses back into the deterministic core? The model must not become a second writer.

`scripts/test_career_agent_boundaries.py` pins the current canonical-writer invariant: among production Career Agent modules, only `lifecycle` may directly mutate the canonical event ledger. A future second writer fails CI even if its output appears valid in happy-path tests.
