# Real Application

## Goal

Review a synthetic job description and candidate evidence as independent states, then route the
user-owned next step to interview preparation.

## Starting state

- The input is `matching-input.example.json`.
- Company and candidate names, evidence, and source references are synthetic.

## Synthetic data

The Aozora Systems (Synthetic) Platform Engineer fixture contains:

- Python: `matched`
- Kubernetes: `missing`
- Japanese business communication: `unknown`
- work location: `conflict`

These states are emitted by the repository's real `evidence_based_v3` contract; the workflow does
not calculate a second score.

## Commands

```bash
python scripts/run_workflows.py --workflow real-application --format human
python _shared/matching_v3.py examples/workflows/real-application/matching-input.example.json --text
```

The runner then invokes the canonical Career Agent route for:

```text
I need interview prep
```

## Expected invariants

- Matched, Missing, Unknown, and Conflict remain independently represented.
- Decision Status is `conflict` for the confirmed hard disagreement.
- Unknown is not converted to zero or inferred from another axis.
- Conflict and Missing are not offset by Matched evidence.
- Candidate interest remains a separate recorded field.
- The interview transition is `flow_phase=interview` and still creates a pending proposal.

## Decision point

The user may provide more evidence, keep Unknown/Conflict, or continue where the existing route
allows. The system does not decide whether to apply.

## Product does not do

- No aggregate recommendation or company ranking.
- No hiring probability.
- No automatic application, message, or interview orchestration.

## Recovery

Use the Recovery workflow when workspace or provenance evidence is unavailable.

## Repeatability

The matching input is committed synthetic data and the Career Agent transition runs in a fresh
temporary vault each time.
