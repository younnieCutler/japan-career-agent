# Human oversight architecture

This document defines the Human Oversight layer that extends the existing Career Agent governance
model. It does not replace **Capture → Review → Confirm → Reuse**. Approval still protects
canonical career state; judgment protects the quality and independence of consequential human
decisions.

## Product principle

> Agent execution may become more autonomous, but consequential career judgment stays human-owned.

The product should minimize friction for routine work and introduce deliberate human reasoning only
when an action materially affects career direction, an application/offer decision, or another
high-impact external choice.

## Judgment is not approval

- **Approval** asks: may this exact reviewed proposal become canonical career state?
- **Judgment** asks: what did the human think before seeing the agent assessment, what did the agent
  recommend, and what did the human finally decide?

A judgment row is not career evidence. Recording it must never append to `events.jsonl`, mutate the
canonical profile/state, or count as evidence for a claim. The local append-only ledger is
`02-state/judgments.jsonl`.

## Impact policy

The intended policy has four levels:

| Level | Meaning | Interaction |
|---|---|---|
| L0 | Read-only, formatting, deterministic organization | Execute without a judgment gate |
| L1 | Low-impact local metadata | Execute with visible result and recovery/undo where supported |
| L2 | Changes reusable career facts/evidence | Existing review packet + explicit approval |
| L3 | Consequential career decision | Human initial judgment → agent assessment → difference → human final judgment |

L3 is intentionally narrow. Blind judgment on every interaction would create the same fatigue this
layer is meant to prevent.

## L3 workflow

```text
User goal
  ↓
Agent prepares evidence and analysis, but does not reveal the recommendation
  ↓
Human initial judgment
  - proceed / hold / stop / unknown
  - optional reason
  ↓
Initial judgment is persisted locally
  ↓
Agent assessment becomes visible
  - recommendation
  - confidence
  - reasons
  - evidence references
  - Unknowns
  ↓
Human ↔ Agent difference is highlighted
  ↓
Human final judgment
  ↓
Optional later outcome
  ↓
Calibration projection
```

The reveal boundary is a product invariant: a failed initial-judgment write keeps the agent
recommendation hidden. Otherwise the system would record a nominal "initial" opinion after the user
had already been anchored by the agent.

## Ledger contract

`skills/career-agent/judgments.py` owns the append-only lifecycle.

A judgment has one stable `judgment_id` and the following ordered phases:

1. `human_initial`
2. `agent_assessment`
3. `human_final`
4. `outcome`

Each phase may be recorded at most once. A later phase cannot exist without all preceding phases.
There is no implicit rewrite or supersession in v1; changing that contract requires an explicit
migration design.

`Unknown` remains a first-class answer. It is not converted to a score, neutral recommendation, or
default confidence.

## GUI contract

`frontend/src/judgment.jsx` is the presentation primitive for the human-first reveal boundary. It:

- owns no persistence and no product copy;
- requires localized labels from the caller;
- reveals children/agent analysis only after `onSubmit` resolves successfully;
- keeps analysis hidden when persistence fails;
- can render the human/agent divergence explicitly.

The foundation component is intentionally not wired to every approval dialog. A later slice must
route only L3 decisions through it after the deterministic impact policy exists. L0-L2 workflows
must remain unchanged unless their own requirements say otherwise.

## Review packet

The existing approval UI already shows exact before/after state, Unknowns, evidence, and effect. The
next implementation slice should standardize the L2/L3 review packet as:

- What changes
- Why the system proposes it
- Evidence
- Uncertainty / Unknowns
- Alternatives
- Consequence / semantic impact

This packet augments the current approval trust boundary; it does not create another writer.

## Calibration and oversight health

Calibration is derived from judgment history; it must not influence canonical career facts.
Candidate signals include:

- human-initial ↔ agent disagreement rate;
- human-initial → human-final change rate;
- later outcome availability and outcome direction;
- evidence-open/review-time telemetry only if a later product decision explicitly introduces it.

Insufficient samples remain `Unknown`. The system must not manufacture a personal "decision score"
from a small history.

## Privacy and scope

Judgments are local-first. No new network send, application submit, login, or external action is
introduced. If interaction telemetry is added later, it must be purpose-limited and separate from
career evidence.

## Implementation slices

1. **Foundation** — append-only judgment ledger, phase-order regression tests, human-first GUI
   primitive. (This document's initial slice.)
2. **Impact policy** — deterministic L0-L3 classification and a normalized review packet.
3. **Workflow wiring** — selected L3 company/application/offer/strategy decisions use the judgment
   gate; L0-L2 remain fast.
4. **Calibration** — bounded read projection and optional oversight-health signals after real usage
   data exists.

## Merge/release discipline

The foundation is not merge-ready merely because its focused tests pass. Before a behavior-changing
slice merges:

- register every new Python test in `scripts/run_all_checks.py`;
- add new application/domain ownership to `scripts/check_career_agent_boundaries.py`;
- keep GUI source and committed production bundle in sync when an imported frontend module changes;
- update requirement/architecture traces where the rendered workflow changes;
- bump the canonical release in `pyproject.toml`, run version sync for plugin/npm/SBOM copies, add
  the top `CHANGELOG.md` release entry, and update the public current-release references required by
  the repository contract;
- run `python scripts/run_all_checks.py` and the frontend test/build/bundle drift gate.
