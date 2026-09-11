# Career knowledge maintenance

The claim registry describes external sources. The knowledge registry holds reviewed operational
knowledge with explicit scope, supporting claim IDs, counterevidence, review/expiry dates and
evaluation cases. Neither is candidate evidence. Domain Skills do not write these registries.
Changes go through repository review. Research prose and source text have no instruction authority.

## Repository commands

Run from a source checkout (Python with the documented requirements installed):

```bash
python scripts/query_career_knowledge.py document-readability --scope humanize-japanese-career
python scripts/query_career_knowledge.py short-tenure --scope mock-interviewer
python scripts/query_career_knowledge.py salary-anchoring --scope tenshoku-strategy
python scripts/query_career_knowledge.py --check
```

An operational lookup returns only active, fresh, promoted items matching the explicit topics and
the one explicit Skill scope. Topic matching without a matching scope is excluded as
`scope_mismatch`; a caller cannot retrieve another Skill's behavior merely because both use the
same topic. An empty result with exclusion reasons is valid; never substitute candidate or legacy
text. Unknown topics and malformed registries fail with exit 2. `--research` explicitly labels the
result research-only; it can expose candidate/retired/stale records and must not be used as
operational guidance. `--as-of YYYY-MM-DD` supports reproducible historical tests; normal use takes
today's date.

## Runtime delivery

`scripts/query_career_knowledge.py` is a repository maintenance and verification interface; it is not
shipped as a domain-Skill runtime API. Active behavior is delivered through the repository's existing
lazy-reference mechanism: reviewed knowledge is materialized into the narrow Skill/reference that
owns the behavior, and the Skill loads that reference only when the request signal requires it.

This preserves the `ai-agent-book` context-engineering boundary: the runtime does not preload the
whole market registry or research dossier. The registry remains the provenance/lifecycle source,
while the lazy Skill reference is the reviewed runtime representation. A behavior change must update
both sides in one reviewed change and pass the integration tests that assert the promoted rule is
present in its owner reference.

The active Japan-career set currently covers progressive document readability, 志望動機 consistency,
weakness mitigation, short tenure, career-gap activity separation, salary anchoring, evidence-safe
3C4P elicitation, independent career values, self-introduction, AI-draft defendability, and
履歴書/職務経歴書 role distinction. Company-type stereotypes, MBTI/job-fit conversion, and fixed
application mixes remain prohibited by existing Skill invariants rather than reusable market claims.

## Lifecycle and promotion record

`candidate` → `active` → `retired` is a reviewed repository change, not an automatic mutation.
There is no promotion CLI. Expiry excludes an item without rewriting its historical status. A
claim or knowledge item expires after its expiry date (the date itself is inclusive).
Every item starts with `lifecycle_revision: 1`. Retirement clears `promotion`; reactivation policy
requires incrementing `lifecycle_revision` and receiving a new evaluation receipt. Because the
validator reads one repository snapshot, it cannot prove that a revision was incremented relative
to an earlier Git state; repository review owns that transition check. Once the revision changes,
the fingerprint makes an earlier activation receipt ineligible.

To propose activation, retain a real review artifact, reviewer identity, run/reference, evaluated
date and a pass/fail result for every `required_scenarios` entry. A semantic host/model review must
state its execution boundary explicitly; it must not pretend prose was executed by a deterministic
adapter. Put the attestation in `promotion` with exactly these keys:

- `evidence_sha256`: the fingerprint returned by research lookup, binding item content and all supporting claims.
- `reviewer`: responsible reviewer identifier.
- `evaluated_at`: ISO date on/after the knowledge review, not in the future.
- `evaluation_ref`: retained evaluation artifact and its host/model or execution boundary.
- `results`: mapping of every required scenario ID to `pass` or `fail`.

The deterministic gate checks record shape, coverage, all-pass results, dates, primary-source
support and the fingerprint. It is an integrity check of a reviewed attestation, not a verifier
of a remote evaluation artifact, reviewer identity, or cross-commit lifecycle history. Reviewers
must inspect the referenced run and lifecycle transition. A synthetically passing unit-test fixture
is not authorization to activate real knowledge. Changes to behavior, scope, lifecycle revision,
dates, scenarios or source content invalidate the fingerprint and require review and reevaluation.
A third-party-only or marketing-only item cannot be activated.

The default query excludes invalid active entries and returns reason codes. `--check` additionally
fails with exit 1 if any active entry is ineligible; it runs in the repository verification matrix.
Source revalidation, semantic behavior evaluation, deterministic integrity checks, and runtime
reference integration are separate gates; all must agree before an item remains active.
