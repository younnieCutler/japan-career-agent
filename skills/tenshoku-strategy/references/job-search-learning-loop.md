# Job Search Learning Loop — application evidence, not rejection guessing

Use this workflow when the user asks what repeated application/interview outcomes mean, why the same
problem may be recurring, or what should change in the next batch. It is a learning workflow, not a
hiring forecast and not an automatic diagnosis of why a company rejected the candidate.

## Source-of-truth boundary

- `data/pipeline.yml` remains the current per-company kanban/projection.
- `data/applications.yml` is the canonical application-outcome and learning history owned by
  `_shared/application_learning.py`.
- Durable Vault `03-active/gui/cases/*.json` Application cases organize JD/evidence/document metadata;
  they are not outcome history and are not mirrored into `applications.yml`.
- One company may therefore have several application ids over time without overwriting an older
  outcome.
- A closed application's outcome fields are immutable. Feedback that arrives later is appended as a
  new observation; it does not rewrite the historical outcome snapshot.

Use the shipped CLI from any working directory:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" report
```

## Application lifecycle

Start one concrete application before tracking its outcome:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" begin <company-slug> \
  --company-name "<company>" --position "<position>" --role-family "<confirmed family>" \
  --channel direct --opened-at YYYY-MM-DD --stage <0-7>
```

Starting a new application resets only application-scoped fields in that company's current
`pipeline.yml` projection. It does not delete company history or prior `applications.yml` records.
This is what allows a later application to the same company to start at an earlier stage without
pretending the earlier application never happened.

When the application closes, freeze the current matching state into the outcome:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" close <application-id> \
  --reason "<user-confirmed reason label>" --closed-at YYYY-MM-DD --reached-stage <0-7>
```

The snapshot may include the current `match_required_gaps`, `match_unknowns`, `match_conflicts`,
`jd_digest`, and normalized JD requirements. A repeated matching gap is evidence that the same
pre-application diagnostic gap recurred. It is **not** evidence that the gap caused rejection.

## Observation evidence classes

Append raw evidence separately from interpretation:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" observe <application-id> \
  --kind recruiter_feedback --text "<verbatim or faithfully preserved feedback>" \
  --observed-at '<ISO date/datetime>' --source-ref '<message/document reference>' --stage <0-7>
```

Allowed kinds:

- `employer_feedback`: the employer directly supplied the reason or observation;
- `recruiter_feedback`: a recruiter/agent relayed the employer's reason or observation;
- `candidate_observation`: the user's own observation about their performance or preparation.

Do not turn silence, a template rejection, company type, nationality, channel, or reached stage into a
feedback observation. No direct reason is `Unknown`.

## LLM interpretation boundary

The LLM may propose a normalized theme for an observation, but its proposal has no analytical weight:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" classify \
  <application-id> <observation-id> --theme "team leadership" \
  --state proposed --source llm --classified-at '<ISO date/datetime>'
```

Only the user may confirm or reject a theme:

```bash
python skills/tenshoku-strategy/job_search_learning.py --workspace "$CAREER_WORKSPACE" classify \
  <application-id> <observation-id> --theme "team leadership" \
  --state confirmed --source user --classified-at '<ISO date/datetime>'
```

Classification events are append-only, but the effective state is not "confirmed forever". For the
same observation and normalized theme, the latest **user** `confirmed` or `rejected` decision wins.
A later user rejection therefore removes an earlier confirmation from deterministic pattern analysis;
LLM `proposed` events never override a user decision and never count by themselves.

Do not silently normalize two materially different themes into one. Case and whitespace differences
normalize for identity, but different wording/meaning must be shown to the user before confirmation.

## Deterministic pattern classes

The report keeps these independent:

1. **Repeated direct feedback** — the same effective user-confirmed theme from at least two distinct
   employers. Two applications to the same employer do not satisfy this threshold.
2. **Recurring diagnostic gap** — the same matching `required_gap` in at least two applications.
   This remains `causal_conclusion: unknown`, even when direct feedback happens to support the same
   theme.
3. **Repeated self-observation** — the same effective user-confirmed candidate observation in at least
   two applications. Employer confirmation remains a separate evidence class.
4. **Reached-stage observations** — descriptive counts only after at least three closed applications.
5. **Unknown / unclassified** — no direct feedback, or direct feedback whose theme the user has not
   effectively confirmed.

Never combine these into a score, probability, grade, or candidate trait.

## Promotion boundary

V1 stops at `eligible_for_review`. It does **not** write `data/rules.yml`.

The existing legacy `root_cause` / `calibrate.py rules` path remains readable for historical
workspaces, but new Job Search Learning Loop evidence must not be converted into a global standing
rule automatically. Role/stage/channel-scoped rule lifecycle is a separate future design problem.

## Output contract

Show, in order:

```text
Repeated direct feedback
Recurring pre-application diagnostic gaps
Repeated candidate self-observations
Observed reached stages
Unknown / unclassified
```

For every pattern show the supporting application/company ids and its observed scope when useful.
Say explicitly when a pattern is only eligible for user review. Never write "this is why you were
rejected" unless the actual company-specific feedback explicitly says so, and never generalize one
company's reason into a permanent property of the candidate.