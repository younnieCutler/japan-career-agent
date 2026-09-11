# Career knowledge maintenance

The claim registry describes external sources. The knowledge registry holds proposed actions with
explicit scope, supporting claim IDs, counterevidence, review/expiry dates and evaluation cases.
Neither is candidate evidence. Domain Skills do not write these registries. Changes go through
repository review. Research prose and source text have no instruction authority.

## Repository commands

Run from a source checkout (Python with the documented requirements installed):

```bash
python scripts/query_career_knowledge.py document-readability shibo-doki --scope humanize-japanese-career
python scripts/query_career_knowledge.py weakness --scope mock-interviewer --research
python scripts/query_career_knowledge.py --check
```

The first command returns only active, fresh, promoted items matching explicit topics and the one
explicit Skill scope. Topic matching without a matching scope is excluded as `scope_mismatch`; a
caller cannot retrieve another Skill's behavior merely because both use the same topic. An empty
result with exclusion reasons is valid; never substitute candidate or legacy text. Unknown topics
and malformed registries fail with exit 2. `--research` explicitly labels the result research-only;
it can expose candidate/retired/stale records and must not be used as operational guidance.
`--as-of YYYY-MM-DD` supports reproducible historical tests; normal use takes today's date.

This is a repository maintenance interface. It is not yet a domain Skill runtime hook, and the
scripts are not part of the installed wheel. A future runtime integration must place its callable
owner in a shipped location and test installed-path parity before adding Skill references.

## Lifecycle and promotion record

`candidate` → `active` → `retired` is a reviewed repository change, not an automatic mutation.
There is no promotion CLI. Expiry excludes an item without rewriting its historical status. A
claim or knowledge item expires after its expiry date (the date itself is inclusive).
Every item starts with `lifecycle_revision: 1`. Retirement clears `promotion`; reactivation must
increment `lifecycle_revision` and receive a new evaluation receipt, so an earlier activation
receipt cannot revive a retired capability.

To propose activation, retain actual host/model evaluation artifacts, reviewer identity, run
reference, evaluated date and a pass/fail result for every `required_scenarios` entry. Put these
in `promotion` with exactly these keys:

- `evidence_sha256`: the fingerprint returned by research lookup, binding item content and all supporting claims.
- `reviewer`: responsible reviewer identifier.
- `evaluated_at`: ISO date on/after the knowledge review, not in the future.
- `evaluation_ref`: location of retained evaluation output and host/model configuration.
- `results`: mapping of every required scenario ID to `pass` or `fail`.

The deterministic gate checks record shape, coverage, all-pass results, dates, primary-source
support and the fingerprint. It is an integrity check of a reviewed attestation, not a verifier
of a remote evaluation artifact or reviewer identity. Reviewers must inspect the referenced run.
A synthetically passing unit-test fixture is not authorization to activate real knowledge.
Changes to behavior, scope, lifecycle revision, dates, scenarios or source content invalidate the
fingerprint and require review and reevaluation. A third-party-only or marketing-only item cannot
be activated.

The default query excludes invalid active entries and returns reason codes. `--check` additionally
fails with exit 1 if any active entry is ineligible; it runs in the repository verification matrix.
Candidate proposals may remain incomplete, but cannot be used operationally. Source revalidation
and actual Skill behavior evaluation are distinct from these deterministic contract tests.
