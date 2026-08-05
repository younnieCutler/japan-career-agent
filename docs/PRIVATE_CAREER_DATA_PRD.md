# PRD: Private Career Data Store, Timeline, and Fresh Context

**Status:** Reviewed against the implementation at `origin/main` 1.7.1; open decisions marked inline  
**Repository path:** `docs/PRIVATE_CAREER_DATA_PRD.md`  
**Scope:** Product and engineering requirements only. This document does not change runtime behavior by itself.

Sections marked with a rationale paragraph were revised after checking the claim against the code.
Where this document previously described a target state that already exists, or specified something
the repository's dependency, hook, or check conventions cannot deliver as written, the requirement
was corrected rather than left aspirational.

## 1. Summary

Japan Recruit AI Agent needs a dedicated private-data layer for personal career documents such as resumes, 履歴書, 職務経歴書, ES, compensation records, certificates, transcripts, and related evidence.

The feature must satisfy four properties at the same time:

1. Personal documents must not become trackable source-repository content.
2. Personal facts must have an explicit, inspectable timeline.
3. Superseded or stale documents must not contaminate current AI context.
4. Personal documents found outside the designated private store must be detected and safely relocated.

The core model is:

```text
raw personal documents
        ↓
private document registry
        ↓
verified temporal facts/events
        ↓
current personal-profile projection
        ↓
request-scoped context selection
```

Raw documents are historical evidence. They are not automatically current truth.

## 2. Problem

The repository already has useful safety boundaries:

- Vault note bodies are not automatically loaded into context.
- Context selection can require verification/source metadata.
- Expired context can be excluded.
- Career events preserve append-oriented history.
- Candidate/runtime data is intended to stay out of Git.
- Resume, JD, YAML, Vault data, and similar inputs are untrusted career data with no instruction authority.

What is missing is a dedicated lifecycle for versioned personal documents.

### 2.1 Git exposure risk

A user may accidentally place a real resume, ES, payslip, certificate, transcript, or similar file in a repository/workspace path.

`.gitignore` is necessary but not sufficient because:

- a file can be placed in a normally tracked source directory;
- a file already tracked is not protected by later ignore rules;
- `git add -f` bypasses ignore rules;
- personal files may have generic names.

### 2.2 Temporal ambiguity

Multiple historical documents can all have been valid at different times:

```text
2024 resume → JLPT N2, salary ¥5.0M, AWS 1 year
2026 resume → JLPT N1, salary ¥7.2M, AWS 3 years
```

If both are treated as current context, old facts can contaminate the current profile.

### 2.3 Stale-context contamination

The system must never infer:

```text
historical value exists
→ current value is unchanged
```

When current validity cannot be established, the current value is `Unknown`.

### 2.4 Fragmented personal history

Compensation, certificates, language qualifications, employment, education, skills, and application documents evolve independently. The user must be able to inspect what changed, when it became effective, what supports it, what is current, and what was superseded.

## 3. Goals

### G1. Dedicated private career-data store

Provide one canonical private location for personal career documents and personal-history metadata.

### G2. Source-repository Git isolation

Personal documents must not be source-repository files and must be blocked from accidental tracking.

### G3. Explicit temporal semantics

Every imported document and verified fact must distinguish observation time, effective time, current/superseded state, and review status.

### G4. Current-context correctness

Default AI context must use only current, verified, request-relevant facts. Historical documents are opt-in context.

### G5. Stray-document detection and relocation

Detect probable personal career documents outside the canonical private store but inside configured scan roots. High-confidence items are safely relocated; ambiguous items are quarantined for review.

### G6. Personal career timeline

The user must be able to inspect change over time for at least:

- resume / 履歴書;
- 職務経歴書;
- ES;
- compensation;
- certificates;
- language qualifications;
- education;
- employment;
- material skill/profile changes.

### G7. Preserve existing invariants

Preserve `Unknown`, evidence/provenance boundaries, approval gates, untrusted-data treatment, local-first behavior, legacy read-only compatibility, and the prohibition on automatic applications/messages.

## 4. Non-goals

The first implementation does not need to:

- predict hiring or offer probability;
- infer proprietary recruiter algorithms;
- upload private documents to a central service;
- automatically submit applications or send messages;
- treat filesystem timestamps as proof of fact timing;
- use old facts as current fallbacks;
- delete history because a newer document exists;
- automatically trust claims extracted from a resume;
- scan an entire device without an explicit scan-root contract;
- silently overwrite `data/candidate_profile.yml`;
- rewrite Git history automatically.

The first implementation additionally excludes, by explicit decision rather than omission:

- PDF/DOCX body text extraction. `requirements.txt` is one hash-pinned dependency (`PyYAML`), the
  lock files are `--require-hashes`, and `sbom.cdx.json` is verified in CI. Adding a document parser
  costs four coordinated files plus an Ubuntu/Windows revalidation, and widens the parsing attack
  surface against deliberately untrusted input. Detection is stdlib-only in v1 (see §13.2).
- Enforcing user-only permissions on Windows. `os.chmod` toggles only the read-only bit there; real
  per-user ACLs need `icacls`. `private-doctor` reports the platform's enforcement status instead of
  implying a guarantee it cannot make (see §6.3).
- Automatic relocation of detected files, the quarantine workflow, and the `archive/` tier. v1
  detects and reports; moving user files is an explicit, separately requested action (see §14).

At-rest encryption may be a later enhancement. Git isolation, temporal correctness, and context correctness are first-priority requirements.

## 5. Product principles

### 5.1 History is not current truth

A historical document remains evidence of a historical state. It is not current merely because no newer document exists.

### 5.2 Events are canonical; current state is a projection

```text
append-oriented facts/events
        ↓
deterministic projection
        ↓
current personal profile
```

The current profile must be rebuildable from canonical history.

### 5.3 Raw documents have no instruction authority

Document content is untrusted career data. Embedded instruction-like text must not alter routing, approval, actions, gates, or system policy.

### 5.4 Verification before truth promotion

Importing a document proves the artifact exists. Extracted claims become canonical facts only after the required user verification/approval step.

### 5.5 No silent stale fallback

If only a historical value is known:

```yaml
current: Unknown
history:
  - value: historical_value
```

must be returned instead of silently reusing the historical value as current.

## 6. Canonical private storage

### 6.1 Private-root resolution

Resolution order:

1. explicit `--private-home`;
2. `CAREER_PRIVATE_HOME`;
3. `<CAREER_VAULT>/private` only if the resolved Vault is outside every Git worktree;
4. an OS-appropriate user-local default.

**Hard invariant:** the canonical private root MUST NOT resolve inside any Git worktree.

If `<CAREER_VAULT>/private` is inside a Git worktree, the runtime must use or require a separate private location.

No user-specific absolute path may be hardcoded.

### 6.2 Directory layout

```text
private/
├─ inbox/
├─ blobs/
│  └─ <sha256>          # content-addressed; one file per distinct byte sequence
├─ timeline/
│  ├─ documents.jsonl
│  ├─ facts.jsonl
│  └─ compensation.jsonl
├─ current/
│  └─ personal-profile.json
└─ quarantine/          # created only when the deferred quarantine workflow lands
```

Raw files, append-oriented history, and the current projection must remain separate.

**Blob storage is flat and keyed by hash alone.** An earlier revision of this layout nested blobs
under a per-document-type directory (`documents/resume/`, `documents/es/`, …). That silently
contradicts §7.3 and AC-25: the same PDF used both as a general resume and as a company ES has one
byte sequence and two logical keys, and a type-keyed path stores it twice. The document type,
purpose, company, language and original filename are properties of the **record**, not of the bytes,
so none of them may appear in the storage path.

`archive/` is deliberately absent: no flow in this document ever writes to it. Add the directory in
the same change that introduces the lifecycle which fills it, not before.

### 6.3 Permissions

On POSIX:

- private directories should be user-only;
- private files should not be world-readable;
- `private-doctor` must surface unsafe permission state.

On Windows, permission *enforcement* is a non-goal for v1 (§4). `os.chmod` there toggles only the
read-only bit, and real per-user ACLs require `icacls`. `private-doctor` must report the honest
platform state — `permissions: not enforced on this platform` — rather than printing `OK` for a
guarantee it did not make. The test requirement is that this reporting difference is asserted on
both platforms, not that POSIX semantics are simulated on Windows.

## 7. Document model

Each imported document requires a stable record.

Minimum fields:

```yaml
document_id: doc_<stable-id>
document_type: resume
logical_key:
  type: resume
  company: null
  purpose: general
  language: ja

storage_path: blobs/<sha256>
original_name: resume.pdf

sha256: <content-hash>
size_bytes: 12345

observed_at: 2026-08-05T10:00:00Z
effective_from: 2026-07-15

status: observed

source_type: personal_evidence
verified_by_user: true
reviewed_on: 2026-08-05
```

**Import writes no temporal judgment.** `status` is always `observed`; `effective_to`, `supersedes`,
`superseded_by`, and any notion of "current" are **derived** by the projection (§12) for an explicit
`as_of`, never stamped at import time.

Rationale, added after the first implementation got this wrong. If import marks the newest arrival
`current` and supersedes whatever it finds, then importing a 2024 resume after a 2026 one makes the
2024 document current — ordering by arrival instead of by `effective_from`, which is precisely the
stale-context contamination in §2.3. Adding an ordering comparison at import time does not fix it
either: a document with `effective_from: Unknown` still has no defensible position in the chain, and
§19.3 already says such a document must not become current automatically. The derivation belongs in
one place, with `as_of` in hand.

This also removes a crash-consistency hazard. Stamping supersession requires two appends — the new
record and the old record's state change — and a process that dies between them leaves two documents
both claiming to be current. A lock serializes concurrent processes but does nothing about a crash
mid-sequence. **One import appends exactly one canonical line.** Reverse links are derived, not
stored; the forward `effective_from` on each record already contains the ordering information.

### 7.1 Time semantics

- `observed_at`: when the system received/inspected the artifact.
- `effective_from`: when the artifact/fact became applicable.
- `effective_to`: when applicability ended, when known.
- `reviewed_on`: when the user last confirmed the record.

File creation/modification timestamps are metadata only and must not silently become `effective_from`.

**Timezone rule.** `observed_at` is a UTC instant (`...Z`), matching the existing `utc_now()` helper,
and the trailing `Z` is **required, not merely tolerated** — an offset (`+09:00`) or a naive local
time would store instants in three notations that sort differently as strings, in a ledger whose
ordering is load-bearing.
`effective_from`, `effective_to`, and `reviewed_on` are bare calendar dates in the user's local civil
calendar and are **never timezone-converted**. Without this rule a JLPT result effective `2026-01-20`
in JST compared against a UTC `as_of` is off by up to a day, and `as_of` reproducibility (§12.4)
silently depends on the runner's timezone.

### 7.2 Version identity

Version chains are scoped by logical identity.

General resume:

```text
(type=resume, purpose=general, language=ja)
```

Company-specific ES:

```text
(type=es, company=<company>, purpose=<application-purpose>, language=ja)
```

An ES for Company A must not supersede an ES for Company B.

### 7.3 Duplicate handling

Same SHA-256 must not create duplicate stored bytes or inconsistent current versions. Re-observation can be recorded without pretending the bytes are a new version.

Identity is `(sha256, logical_key)`, not `sha256` alone. The two cases are distinct and both must be
specified:

- **Same hash, same logical key** — re-observation. Update `observed_at`/`reviewed_on`; do not create
  a second version and do not store the bytes twice.
- **Same hash, different logical key** — one stored blob referenced by two document records. This is
  normal: the same PDF can be both `(type=resume, purpose=general)` and `(type=es, company=X)`.
  Storage is content-addressed once; each logical key keeps its own independent version chain and
  supersession state.

A design that keys storage only by hash cannot express the second case, and a design that copies
bytes per logical key breaks the "no duplicate stored bytes" rule. Content-addressed storage plus
per-logical-key records satisfies both.

## 8. Personal fact model

A document and a fact are not the same entity. One document can support many facts, and one fact can have multiple evidence documents.

Minimum fact record:

```yaml
fact_id: fact_<stable-id>
category: certification
key: jlpt
value: N1

effective_from: 2026-01-20
effective_to: null
observed_at: 2026-08-05T10:00:00Z

status: confirmed
supersedes: fact_<older-id>
superseded_by: null

evidence:
  - document_id: doc_<certificate-id>

provenance: personal_evidence
verified_by_user: true
```

Supported categories must include at least:

- compensation;
- certification;
- language qualification;
- employment;
- education;
- role/title;
- skill/capability;
- portfolio/project evidence.

### 8.1 Supersession and interval derivation

`supersedes`/`superseded_by` are the canonical links. `effective_to` is **derived, never
hand-authored**, by exactly one rule:

> When fact B supersedes fact A and `B.effective_from` is known, `A.effective_to` becomes the day
> before `B.effective_from`. If `B.effective_from` is `Unknown`, `A.effective_to` stays `null` and
> **both** facts are reported as a conflict for any `as_of` on or after `A.effective_from` — not
> silently resolved in favour of the newer record.

Without a stated rule, §21's invariant "at most one unconflicted current value per logical fact key
and `as_of` date" is unverifiable, because two implementations can disagree about whether an
open-ended older fact still applies. Deriving the interval also makes the projection a pure function
of the links, so AC-14 (rebuild) and AC-15 (`as_of` determinism) can actually be asserted.

Superseding never deletes: A keeps its record, its evidence, and its original `effective_from`.

### 8.2 Fact provenance vocabulary

Fact records reuse the repository's existing evidence vocabulary rather than inventing a parallel
one — `provenance`, `source_type`, `confidence`, `observed_at`, `source_ref` as already validated for
matching evidence, plus the existing `personal_evidence` source type used by Vault context selection.
A second, incompatible provenance enum for personal facts would have to be reconciled at every
downstream consumer.

## 9. Compensation timeline

Compensation must be a timeline, not one mutable number.

Example:

```text
2023-04  JPY 4,800,000
2024-04  JPY 5,400,000
2025-04  JPY 6,100,000
2026-04  JPY 7,200,000
```

Where available, preserve:

- base salary;
- bonus;
- total compensation;
- currency;
- gross/net meaning;
- effective period;
- evidence.

Missing components remain `Unknown`. The system must not guess a total from incomplete components.

## 10. Certificate and qualification timeline

Support:

- acquired/issued date;
- expiration date;
- issuer;
- credential name;
- optional credential ID;
- supporting document;
- current / expired / superseded status.

Expired qualifications stay visible historically but must not be presented as currently valid.

## 11. Current personal-profile projection

`current/personal-profile.json` is a derived projection, not immutable history.

It contains current verified facts only.

Example:

```json
{
  "as_of": "2026-08-05",
  "language": {
    "jlpt": {
      "value": "N1",
      "effective_from": "2026-01-20",
      "evidence": ["doc_..."]
    }
  },
  "compensation": {
    "current": {
      "amount": 7200000,
      "currency": "JPY",
      "effective_from": "2026-04-01",
      "evidence": ["doc_..."]
    }
  }
}
```

The projection must be deterministic and rebuildable.

If confirmed facts overlap and conflict, output a conflict instead of arbitrarily choosing a value.

### 11.1 `Unknown` and `Conflict` are output shapes, not prose

The happy-path example above is the least important one. `Unknown` is this repository's central
invariant and `Conflict` is required by §19.1 and §21, so both need a fixed serialized shape or every
consumer will invent its own.

Every projected field carries an explicit `state` of `confirmed`, `unknown`, or `conflict`:

```json
{
  "as_of": "2026-08-05",
  "compensation": {
    "current": {
      "state": "unknown",
      "value": null,
      "reason": "no confirmed fact effective at as_of",
      "history_available": true
    }
  },
  "certification": {
    "jlpt": {
      "state": "conflict",
      "value": null,
      "candidates": [
        {"value": "N1", "effective_from": "2026-01-20", "evidence": ["doc_a"]},
        {"value": "N2", "effective_from": "2026-01-20", "evidence": ["doc_b"]}
      ]
    }
  }
}
```

Rules:

- `state: unknown` sets `value: null`. It must never be omitted, defaulted, averaged, or filled from
  history — `history_available` says history exists without leaking the stale value into `value`.
- `state: conflict` sets `value: null` and lists every candidate with its evidence. Newest-file-wins
  is forbidden (§19.1).
- Conflict and unknown vocabulary follows the repository's existing decision vocabulary rather than
  new synonyms, so downstream consumers already know how to branch on it.

A consumer that reads `value` and ignores `state` gets `null`, not a wrong answer. That is the point
of the shape.

## 12. Fresh-context contract

### 12.1 Default current context

Personal context may include only facts that are:

1. confirmed;
2. effective at the requested `as_of` date;
3. not superseded for that date;
4. relevant to the request, where relevance is the **same mechanical track/stage match the Vault
   context selector already applies** — not a judgement call. "Relevant" as an undefined word is the
   only untestable condition in this list, and an untestable condition in a privacy boundary is a
   condition that will be quietly skipped;
5. provenance-backed;
6. permitted by context/privacy policy;
7. within the selection cap.

**Selection cap.** Personal context is capped the same way Vault context already is (a small fixed
maximum, deterministic ordering, newest effective date first). The Vault path caps its selection and
the personal path must not be the unbounded exception — an uncapped personal projection is how a
"current facts only" context quietly grows into the whole profile.

### 12.2 Historical documents are opt-in

Historical document bodies must never enter default current context.

They can be selected when the user explicitly asks for historical work:

```text
Compare my 2024 resume with my current resume.
```

The result must label temporal roles:

```text
Context mode: historical-comparison

CURRENT
- resume / effective 2026-07-15

HISTORICAL
- resume / effective 2024-05-01

Historical values are not treated as current facts.
```

### 12.3 No stale fallback

Given:

```text
Historical salary exists for 2024.
No confirmed current salary exists.
```

Required:

```text
current salary: Unknown
historical salary: available for 2024
```

Forbidden: silently returning the 2024 salary as current.

### 12.4 `as_of` reproducibility

An explicit historical projection such as:

```text
personal-context --as-of 2025-04-30
```

must produce equivalent output when canonical history is unchanged.

**`as_of` is a required parameter of the projection, not an option.** Timeline, projection, and
context-selection functions take `as_of` and **must never call a wall clock internally**. The default
("today") is injected once, at the CLI boundary.

This is not a style preference. The repository already made this exact decision for evidence
staleness in matching, where the helper returns `None` rather than consulting the clock, with an
in-code comment stating it deliberately avoids wall-clock nondeterminism. The Vault context path did
the opposite and calls `today()` inside its eligibility predicate — which is why that path cannot be
tested for reproducibility today.

If any function on the personal path reads the clock, AC-15 is untestable and the projection changes
at midnight without any change to canonical history.

## 13. Stray personal-document detection

### 13.1 Scan roots

Do not scan the entire device by default.

Default configured roots should include:

- repository root;
- active workspace;
- Career Vault non-private directories;
- explicit import paths.

Additional roots may be configured explicitly.

Within the repository root, the directories that actually matter are the ones `.gitignore`
**re-includes** after its deny-by-default `/*` rule: `skills/`, `scripts/`, `_shared/`, `hooks/`,
`docs/`, and `examples/`. A file dropped in any of them is fully trackable — verified directly:
`git check-ignore -v docs/resume.pdf` reports the `!/docs/**` re-inclusion rule, and
`skills/resume.pdf` matches no ignore rule at all. `docs/` in particular is easy to overlook because
it reads like a documentation-only area.

Skipping is split by what the name is allowed to mean where it is found:

- **Universally skipped:** tool caches and dependency trees — `.git/`, `node_modules/`,
  `__pycache__/`, `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`. Nobody keeps a 履歴書
  in `node_modules`, so walking them is wasted I/O rather than extra safety.
- **Skipped only at the top level of a scan root that is itself a Git worktree:** `data/`,
  `career-home/`, `dist/`, `build/`. These are *this repository's* ignored runtime state and build
  outputs, and they are not Git-exposure risks here. Applying the same list to an arbitrary
  configured scan root would silently blind the scan to `~/Documents/data/履歴書.pdf`. A scan root a
  user names explicitly gets no repository-shaped assumptions, and a detector with unexplained blind
  spots is exactly the failure this gate was rewritten to remove.

**A capped scan is incomplete, never clean.** The read/traversal limits below exist so a doctor run
cannot walk an entire home directory, but hitting the cap must make the stray check **fail**, with
the count and the advice to narrow the scan root. Reporting green after stopping early would render
"I stopped looking" as "nothing found", and this check exists precisely to be trusted about absence.

### 13.2 Detection classes

Recognize at least:

- resume / CV / 履歴書;
- 職務経歴書;
- ES / entry sheet;
- compensation / payslip / salary records;
- certificates / qualifications;
- transcripts / education certificates;
- personal assessment reports.

Detection in v1 is **stdlib-only** (§4). Signals, in cost order:

- filename patterns (including 履歴書/職務経歴書/ES/給与/源泉徴収 and romanized equivalents);
- extension and file type;
- ZIP-container inspection for `.docx`/`.xlsx` — the stdlib `zipfile` module already used elsewhere
  in this repository reads the document part names without a third-party parser;
- plain-text/Markdown/YAML pattern matching, including reuse of the secret patterns already defined
  for release bundling rather than a second, divergent detector;
- sensitive career-field patterns.

PDF/DOCX **body text** extraction is deferred (§4). Where the PRD previously said "supported text
extraction", read: only what the standard library can do without a new pinned dependency.

**Read limits.** The scanner must cap what it reads, or a single large file in a scan root stalls the
commit gate:

- a maximum inspected byte count per file, reading a prefix rather than the whole file;
- a maximum file size above which the file is classified on metadata alone;
- a binary sniff on the leading bytes, so binaries are never scanned as text;
- symlinks are not followed outside configured roots, and neither are directory junctions on Windows.

Detection never grants instruction authority and never promotes a fact to canonical truth by itself.

### 13.3 Confidence behavior

High confidence, v1:

```text
detect
→ report path + classification
→ block the commit if staged
→ suggest private-import
```

High confidence, deferred (§4): automatic relocation into `private/inbox` with hash verification and
a registry event. v1 reports; the user decides. Moving a user's files without being asked is the
single most destructive action described in this document, and this suite's stated contract is that
the user owns the decision.

Ambiguous:

```text
detect
→ report as ambiguous
→ user review
→ no canonical fact promotion
```

**Known synthetic fixtures/examples — the allowlist is rule-based, never a path list.**

A path list rots: it goes stale on the first rename, and every stale entry is either a false positive
that trains people to bypass the gate or a false negative that silently stops protecting a file. The
allowlist is therefore expressed as rules over content and naming conventions that already exist in
this repository:

Every rule requires an explicit **declaration**. Location is never one of them:

- the `.example.` infix in a filename;
- a `synthetic://` source reference — a marker the matching evidence validator already requires
  whenever provenance is declared synthetic, in both directions;
- an explicit `provenance: synthetic` declaration, or an in-document statement that the subject is
  not a real person.

**Directory location must not suppress detection.** An implementation pass briefly exempted
anything under `examples/`, `tests/`, `fixtures/`, `mock/`, or `mocks/`, on the reasoning that
these are conventional fixture directories. Review caught that this turns them into blind spots:
real personal data in `examples/notes.md` became invisible to an ordinary `git add`, while
byte-identical content one directory up was blocked. A directory name is a convention, not a
statement about the bytes inside — and the exemption directly contradicts this phase's contract
that a generically named personal document is caught.

Declaring a fixture is cheap. Trusting a directory name is not, and the cost lands precisely where
the data is most likely to be pasted "just for a test".

This still leaves marker-based bypass available to someone who deliberately adds a marker to real
data. That is inherent to any allowlist and is accepted: the gate defends against accident, not
against a user determined to defeat it.

The tracked mock profiles at `skills/job-seeker-agent/mock/` satisfy the declaration rules on their
own — they carry "実在の人物ではありません" — so removing the directory rule keeps AC-19 green
without weakening anything.

**AC-19 (new, and the most important acceptance criterion in this document): the repository check
must report clean against the repository's own `HEAD`.**

This is not a formality. The detector's false-positive surface on this very repository is large and
entirely made of legitimately tracked files:

- `examples/demo-workspace/candidate-profile.example.yml` — a synthetic candidate profile;
- `_shared/schemas.yml` — contains `candidate_profile`, `jlpt_level`, and compensation field names;
- `skills/job-seeker-agent/**` — reference material saturated with 履歴書/職務経歴書 vocabulary;
- **this PRD itself** — it contains the words resume, payslip, transcript, `JLPT N1`, and a
  `¥7.2M`-shaped compensation figure.

A gate that fires on its own repository is a gate that gets bypassed within a day, and a bypassed
gate protects nothing. If satisfying AC-19 requires weakening detection to the point of uselessness,
that is the signal that the signal set is wrong — not that the criterion should be dropped.

Repository tests must use fictional data only.

## 14. Safe import contract

**The default is copy-then-report, not move.** Steps 1–9 are the import and always run. Steps 10–11
delete the user's original and run **only** when deletion was explicitly requested for that
invocation.

Required logical sequence:

```text
1. resolve and validate source
2. calculate source SHA-256
3. resolve destination identity
4. check collision/duplicate
5. copy to temporary private location
6. fsync where supported
7. verify destination SHA-256 == source SHA-256
8. atomically publish destination where supported
9. append registry/timeline event
--- import complete; the source still exists ---
10. remove original source          # only on explicit request
11. verify source absence and destination presence
```

Steps 5–8 are the tmp-write → fsync → atomic-replace sequence the repository's canonical writers
already implement; the import path needs a byte-mode variant of the same helper, not a new
persistence strategy (§20).

Rationale for the split: "successful import" and "your original file is gone" are different
promises, and only the second one is unrecoverable if the classification was wrong. AC-12 covers
preserving the source when verification *fails*; this rule additionally preserves it when everything
*succeeds*, which is the case a misclassified file actually lands in.

If verification fails before successful publication:

- preserve the source;
- clean incomplete temporary output where safe;
- report failure;
- do not record successful import.

Retry must be idempotent.

Concurrent imports of the same document must not create inconsistent duplicate current versions.

## 15. Git protection

Defense in depth is required. The layers below are ordered cheapest-first, and each one is required
because the next one can fail.

### 15.0 Ignore-rule hardening

§2.1 correctly argues that `.gitignore` is not *sufficient*. It is still **necessary**, and the
original draft omitted it entirely — skipping the cheapest and most reliable layer because it is not
the strongest one.

Required, as the first implementation step:

- ignore document extensions that carry personal career data (`*.pdf`, `*.docx`, `*.xlsx`) inside the
  re-included source directories listed in §13.1;
- ignore resume-shaped filename patterns (履歴書/職務経歴書/ES/給与/源泉徴収/resume/cv/payslip);
- ignore `**/private/` anywhere in the tree;
- keep the existing `.example.`/`examples/` allowances intact so §13.3's synthetic fixtures still work.

Verification is direct and does not need new tooling: `git check-ignore -v <path>` must report a
matching ignore rule for each pattern, and must still report the re-inclusion rule for the synthetic
example fixtures.

This layer stops the ordinary accident. The layers below exist for `git add -f`, for files that are
already tracked, and for generically named files — the three cases §2.1 identifies where ignore rules
provably do not help.

### 15.1 Storage boundary

Canonical private root cannot reside in any Git worktree.

### 15.2 Repository scanner

Add a deterministic repository check conceptually equivalent to:

```bash
python scripts/check_private_data.py
```

It must detect probable tracked personal career data without uploading content.

### 15.3 Pre-commit protection

Staged probable personal documents must block commit with actionable output.

Example:

```text
BLOCKED: probable personal career document is staged.

File: <relative-or-redacted-path>
Classification: resume
Action: import it into CAREER_PRIVATE_HOME instead.
```

**Delivery mechanism — this must be specified, because the obvious reading does not work.**

The repository has no pre-commit infrastructure today: no `.pre-commit-config.yaml`, no active hook
in `.git/hooks/` (only the stock `*.sample` files), no `core.hooksPath` setting, and no installer.
`hooks/hooks.json` is unrelated — it is a Claude plugin prompt hook, not a Git hook.

More importantly, **a Git hook cannot be shipped by committing it**: `.git/hooks/` is not tracked
content. A PRD requirement that staged files "must block commit" is therefore not implementable as
stated without naming how the hook reaches the developer's clone.

Required design:

1. A tracked `.githooks/pre-commit` that calls `scripts/check_private_data.py` against the staged
   set, enabled by a one-time `git config core.hooksPath .githooks`. Tracked means reviewable and
   versioned; the one-time command means it is **opt-in**, which must be stated rather than assumed.
2. The same check running in CI, so a clone without the hook installed still fails the pull request.

Layer 2 alone is explicitly insufficient for this threat model: by the time CI runs, the document has
already been pushed to the remote, which is the outcome the whole feature exists to prevent. Layer 1
alone is insufficient because it depends on a manual step the user may never run. Both are required.

`private-doctor` must report whether the hook is actually installed, so "protected" is an observed
state rather than an assumption.

**The staged check must read the index, never the working tree.** The commit will contain the
staged blob, so that is the only content whose classification means anything. Reading the worktree
file is a bypass, not a shortcut:

```text
git add resume-shaped-notes.md     # personal bytes enter the index
echo "harmless" > resume-shaped-notes.md
git commit                          # a worktree-reading gate inspects "harmless" and passes
```

The personal bytes are committed while the gate reports clean. Filename and extension signals still
work under a worktree read — the name comes from the index — which is what makes this failure mode
easy to miss: the gate looks like it works right up until the content signals are the ones that
matter. Read staged content with `git cat-file blob :<path>`, size-checked first.

The same applies to a path staged and then deleted from the working tree: the blob is still in the
index and still lands in the commit.

### 15.4 Forced-add coverage

Tests must cover a synthetic personal document staged with `git add -f`. Protection must not depend only on `.gitignore`.

### 15.5 Already-tracked coverage

`private-doctor` must identify probable personal documents already tracked by Git.

It must not claim deletion removes Git history and must not rewrite history automatically.

Refusing to act is correct, but refusing to *explain* leaves the user with a finding and no path
forward. The report must state all four of the following:

1. the file is already in Git history, so ignore rules will not retroactively help;
2. `git rm --cached <path>` stops future tracking but **does not** remove the file from history;
3. removing it from history requires a deliberate history rewrite and force-push, which the user
   performs — this tool will not do it;
4. **if the commit has been pushed to a remote, and especially a public one, the contents must be
   treated as already disclosed.** Rewriting history afterwards does not un-disclose them; clones,
   forks, caches, and platform views may retain the content. Act on the content itself — rotate
   anything credential-like, and treat the personal data as exposed.

Point 4 is the one that changes what the user actually does, and it was missing from the original
draft. A tool that reports a leak while implying that a history rewrite fixes it gives false
assurance, which is worse than reporting nothing.

## 16. Privacy-safe logs

Normal repository logs, CI output, status output, and E2E artifacts must not print raw private document bodies.

Outside the private registry, prefer:

- relative path;
- basename;
- stable document ID;
- redacted path.

Absolute path provenance may be stored only inside the private store when necessary.

Most of this already exists and must be reused rather than reimplemented: the E2E artifact pipeline
already replaces home/temp/repository roots with placeholder tokens, scans the staged output for
surviving local absolute paths, and **fails the build rather than emitting an artifact** when any are
found. The private feature needs that redaction applied to its own output, not a second redaction
implementation with its own divergent idea of what a sensitive path looks like.

## 17. CLI requirements

Exact names may change, but equivalent functionality is required.

### 17.1 Diagnose

```bash
python skills/career-agent/career_agent.py private-doctor [--scan-root DIR]...
```

Reports, with the phase that owns each line — a diagnostic that lists a check it does not perform is
worse than one that omits it:

- private-root resolution — phase 2;
- Git boundary — phase 2;
- permission state (including "not enforced on this platform", §6.3) — phase 2;
- stray documents in configured scan roots (§13.1), via the Phase 1 detector — phase 2;
- stored-blob integrity: records with missing blobs, and orphan blobs left by an import that failed
  after publication — phase 2;
- already-tracked probable personal documents — phase 1, `scripts/check_private_data.py` with no
  arguments; it needs the repository index, which `private-doctor` deliberately does not assume;
- commit-hook installation state (§15.3) — phase 4;
- invalid timeline/supersession states and current-projection drift — phase 3, which is where those
  concepts first exist.

`--scan-root` is repeatable and defaults to the current working directory. The default is applied at
the CLI boundary, never inside the store, so a caller always knows exactly which trees were walked.
The private root is always excluded: documents there are where they belong. If the walk hits its file
cap the stray check fails rather than passing with an empty finding list (§13.1).

**`private-doctor` must not require an initialized Career Vault.** The current runtime rejects every
subcommand except `setup` when neither `--vault` nor `CAREER_VAULT` is present, and calls
`require_initialized()` for everything except `init`. But the private store is deliberately
independent of the Vault — `CAREER_PRIVATE_HOME` ranks *above* `<CAREER_VAULT>/private` in §6.1's
resolution order, and §25 already requires that unrelated repository checks not depend on private
initialization. The converse matters just as much: a user diagnosing whether their resume is about to
be committed must not first be told to initialize an unrelated Vault. The private subcommands branch
before the Vault requirement, the way `setup` already does.

### 17.2 Diagnose and fix

```bash
python skills/career-agent/career_agent.py private-doctor --fix
```

May:

- create missing private directories;
- rebuild replaceable indexes/projections.

Must not:

- rewrite Git history;
- promote ambiguous facts;
- delete history;
- overwrite conflicting current facts silently;
- **move or delete any file the user did not name.**

Relocating stray documents is deliberately not part of `--fix`. `--fix` is the flag people run when
something is already wrong and they want it to stop being wrong, which is exactly the moment they are
least likely to be reading the file list carefully. Creating a directory and rebuilding a derived
projection are recoverable; moving a misclassified document out of a user's working directory is not.

If relocation ships later (§4), it requires its own explicit flag, and that flag copies first and
deletes only per §14.

### 17.3 Import

```bash
python skills/career-agent/career_agent.py private-import ./resume.pdf \
  --type resume \
  --effective-from 2026-07-15
```

Return:

- document ID;
- SHA-256;
- canonical private path;
- detected type;
- timeline status;
- facts requiring confirmation.

### 17.4 Timeline

```bash
python skills/career-agent/career_agent.py private-timeline
python skills/career-agent/career_agent.py private-timeline --type compensation
python skills/career-agent/career_agent.py private-timeline --type certification
```

The output must make change over time obvious.

### 17.5 Current profile

```bash
python skills/career-agent/career_agent.py private-current
```

Returns current confirmed facts and `Unknown` fields without stale fallback.

### 17.6 Historical context

```bash
python skills/career-agent/career_agent.py personal-context --as-of 2025-04-30
```

Historical output must label its time boundary explicitly.

## 18. User flows

### Flow A: New resume

```text
resume appears in configured scan root
→ scanner detects high confidence
→ report path + classification (the file is not moved)
→ user runs private-import
→ hash verification
→ document record (source file still in place)
→ fact proposals
→ user confirmation
→ canonical temporal facts
→ current profile rebuild
→ old resume remains historical
→ default context uses current confirmed facts only
```

### Flow B: Old resume remains

```text
2024 resume exists
2026 resume is current
User asks for interview preparation
→ selector loads current projection
→ 2024 body is not loaded
→ no stale contamination
```

### Flow C: Historical comparison

```text
User asks to compare 2024 and 2026 resumes
→ historical-comparison mode
→ requested versions loaded
→ effective periods labeled
→ historical facts cannot override current profile
```

### Flow D: Unknown current salary

```text
2024 salary exists
No effective current salary fact
→ current salary = Unknown
→ 2024 salary remains visible in timeline
```

### Flow E: Accidental staging

```text
User force-adds synthetic resume fixture
→ pre-commit private-data check
→ commit blocked
→ import path suggested
```

## 19. Error and conflict semantics

### 19.1 Conflicting current facts

Overlapping confirmed facts that disagree produce:

```text
current state = Conflict
```

not newest-file-wins.

### 19.2 Invalid dates

Impossible calendar dates must be rejected. A shape-only check (`\d{4}-\d{2}-\d{2}`) is not enough:
`2026-99-99` passes it. Real parsing is required, and a parse failure is an error — never a silently
skipped check.

**This rule must also be applied to the two existing paths that currently violate it, or the
guarantee holds only inside the new module while the old paths keep leaking.**

1. Vault context eligibility parses `expires_on` inside a `try` and swallows the failure with
   `except ValueError: pass`. The effect is the precise failure mode this section exists to prevent:
   a typo in an expiry date makes a note **permanently non-expiring**, so stale context stays
   eligible forever. This is live today.
2. The same value is treated inconsistently across the codebase — `doctor` raises an error on a
   malformed `expires_on` while the eligibility predicate silently accepts it. One input, two
   verdicts, and the *unsafe* verdict is the one that governs what reaches the model.
3. Event `occurred_at` has no calendar validation at all. Release 1.7.1 added real
   `date.fromisoformat` parsing, but only for `deadline`.

That 1.7.1 `deadline` check is the pattern to reuse verbatim — parse, and raise a domain error on
failure. Extending it is a small change; leaving it unextended means §12's freshness guarantees are
defeated by a single typo in an unrelated file.

### 19.3 Missing effective date

If `effective_from` cannot be established:

- keep the document;
- keep fact applicability as `Unknown`;
- do not make it current automatically.

### 19.4 Corrupt document

Corrupt artifacts may remain in quarantine with hash/error metadata but cannot contribute canonical facts/context.

## 20. Architecture constraints

Modules:

```text
skills/career-agent/private_store.py       # new
skills/career-agent/personal_timeline.py   # new
scripts/check_private_data.py              # new
```

Responsibilities:

- `private_store.py`: private-root resolution, Git-worktree refusal, hash-verified import, registry,
  permission reporting.
- `personal_timeline.py`: temporal fact validation, supersession, deterministic projection, and
  current/historical context selection.
- `scripts/check_private_data.py`: detection/classification **and** the deterministic
  repository/commit safety gate.
- `runtime.py`: CLI subparsers and dispatch.

An earlier draft proposed five new modules (`private_models`, `private_store`, `private_scan`,
`personal_timeline`, `personal_context`). Three are collapsed, for reasons specific to this codebase:

- **`private_models` → the existing `models.py`.** That module is already the designated pure-contract
  home, and the architecture guard already enforces exactly the property the draft wanted
  ("no filesystem side effects") for it. A parallel pure-contract module gains nothing and is only
  guarded if someone remembers to register it.
- **`personal_context` → `personal_timeline`.** Projection and selection are one deterministic pass
  over the same append-only records at the same `as_of`. Splitting them creates a module boundary
  that every call has to cross with the same arguments.
- **`private_scan` → `scripts/check_private_data.py`.** The detector must have exactly one
  implementation. If the commit gate and `private-doctor` can reach different verdicts about the same
  file, the gate is not a gate — it is a suggestion with a second opinion attached.

The career-agent package already carries nine domain modules across roughly 3.8k lines; the default
should be to add the fewest new ones that hold.

### 20.1 Registration is part of the change, not follow-up

The repository's guards are explicit lists, not discovery. A new module that is not registered is not
"partially checked" — it is entirely unchecked, and silently so:

- new career-agent modules must be added to the architecture guard's domain-module list, and any
  public symbol to its symbol-ownership map;
- the same modules must be added to the boundary-import smoke test's symbol table;
- any module that writes canonical state must be added to the policy check's canonical-writer set,
  which forbids bare `write_text` in those files. That set currently still names `career_agent.py`,
  which has since become a 19-line shim while the real writer moved to `persistence.py` — the stale
  entry should be corrected in the same change;
- every new test file, and `check_private_data.py` itself, must be appended to the canonical check
  runner. It has no test discovery: it executes a hardcoded list and stops at the first failure, so
  an unregistered test is never run by the command §23.5 tells implementers to trust.

Persistence writes must use the existing canonical persistence approach rather than ad-hoc writers.
The import path needs a byte-mode variant of the existing atomic writer (tmp → fsync → atomic
replace), and cross-process serialization should reuse the existing lock helper rather than a new
locking scheme.

## 21. Data-contract requirements

Define deterministic schemas for:

- document record;
- fact record;
- supersession link;
- compensation record;
- current projection;
- detector result;
- import result;
- doctor result.

Required invariants:

- stable IDs;
- real ISO calendar validation;
- explicit `Unknown`;
- preserved provenance;
- no composite candidate score;
- no hiring/offer probability;
- no instruction authority from raw documents;
- no historical-to-current implicit promotion;
- deterministic conflict representation;
- at most one unconflicted current value per logical fact key and `as_of` date.

## 22. Acceptance criteria

### AC-01: Private root Git boundary
Given a Git repository and normal configuration, the resolved private root is outside the Git worktree.

### AC-02: Refuse unsafe private root
If configured private storage resolves inside any Git worktree, initialization/import fails safely with an actionable error.

### AC-03: Stray resume detection and byte-exact import
A high-confidence synthetic resume outside the private root but inside a configured scan root is
detected and reported. An explicit `private-import` of it stores byte-identical content (same
SHA-256) **and leaves the source file in place** (§14).

### AC-04: Ambiguous quarantine
An ambiguous document is not promoted to canonical evidence and requires review.

### AC-05: Forced Git staging blocked
A synthetic personal document force-staged with Git causes the private-data commit check to fail.

### AC-06: No real personal data in tests
All fixtures use clearly synthetic names, companies, identifiers, compensation, and content.

### AC-07: Current resume temporal selection
Given a superseded 2024 resume and confirmed current 2026 resume, ordinary current-context selection excludes historical body/values.

### AC-08: No stale fallback
Given historical compensation only, current compensation is `Unknown`.

### AC-09: Historical query
Explicit historical comparison can retrieve requested historical/current versions with correct labels.

### AC-10: Certificate expiration
Expired certificates remain in history but are not shown as currently valid.

### AC-11: Duplicate idempotency
Repeated import of identical bytes does not create inconsistent duplicate current versions.

### AC-12: Failed relocation preserves source
Destination verification failure preserves the source and records no successful import.

### AC-13: Concurrent import safety
Concurrent imports cannot silently create duplicate conflicting current versions.

### AC-14: Projection rebuild
Deleting only replaceable current projection and rebuilding from canonical history yields equivalent current state.

### AC-15: `as_of` determinism
Same history + same `as_of` date yields equivalent projection.

### AC-16: Untrusted instructions ignored
Instruction-like text embedded in a synthetic resume cannot alter routing, approval, blockers, or policy.

### AC-17: Windows paths
Import, scan, collision, relocation, and private-root tests pass on Windows and Ubuntu.

### AC-18: Existing invariants preserved
Existing `Unknown`, hard-conflict, interest-independence, approval, untrusted-data, action-gate, and legacy read-only behavior remains unchanged.

### AC-19: The gate is clean on this repository
`scripts/check_private_data.py` reports clean against the repository's own `HEAD`, including
`examples/demo-workspace/candidate-profile.example.yml`, `_shared/schemas.yml`,
`skills/job-seeker-agent/**`, and this PRD (§13.3). A gate that fires on its own repository gets
bypassed, and a bypassed gate protects nothing.

### AC-20: Ignore rules cover the obvious accident
`git check-ignore -v` reports a matching ignore rule for each pattern added in §15.0, and still
reports the re-inclusion rule for the synthetic example fixtures.

### AC-21: No wall clock on the projection path
The timeline, projection, and context-selection functions produce identical output for a fixed
`as_of` regardless of the system clock, and none of them consults the clock internally (§12.4). A
test that freezes nothing and changes only the clock must not change the result.

### AC-22: Malformed dates do not extend validity
A malformed `expires_on` on a Vault context note makes that note **ineligible**, not permanently
non-expiring, and a malformed `occurred_at` is rejected (§19.2). The same value must not be accepted
by one code path and rejected by another.

### AC-23: `private-doctor` runs without a Vault
`private-doctor` reports private-root, Git-boundary, and stray-document state with neither `--vault`
nor `CAREER_VAULT` set, and without an initialized Vault (§17.1).

### AC-24: Already-tracked report names the disclosure risk
The already-tracked finding states that pushed content must be treated as disclosed and that a
history rewrite does not undo disclosure (§15.5).

### AC-25: Same bytes, two logical keys
Importing identical bytes under two different logical keys yields one stored blob and two independent
document records with independent version chains (§7.3).

### AC-26: Supersession derives the interval
When a newer fact supersedes an older one, the older fact's `effective_to` is derived from the newer
fact's `effective_from`; when the newer `effective_from` is `Unknown`, the result is a conflict rather
than a silent newest-wins resolution (§8.1).

## 23. Test plan

### 23.1 Focused unit tests

Cover:

- private-root resolution;
- Git-worktree detection;
- valid/invalid dates;
- logical keys;
- supersession;
- duplicate hashes;
- current projection;
- stale fallback rejection;
- conflicts;
- detector confidence;
- destination naming;
- path traversal;
- symlink escape.

### 23.2 Persistence tests

Cover:

- atomic registry/projection writes;
- append behavior;
- fsync where supported;
- partial failure;
- retry/idempotency;
- concurrent import;
- cross-filesystem copy/verify/publish behavior.

### 23.3 Context regression tests

Minimum:

1. current resume only;
2. current + superseded resume;
3. current + multiple historical resumes;
4. historical-only salary;
5. valid current certificate + expired certificate;
6. overlapping conflicting facts;
7. explicit historical comparison;
8. malformed/impossible date;
9. unknown effective date;
10. untrusted instruction embedded in document.

### 23.4 Git safety tests

Cover:

- ignored personal file;
- force-added file;
- already-tracked synthetic personal file;
- allowed synthetic example fixture;
- ordinary non-personal source document;
- generic filename with recognizable personal structure where supported.

### 23.5 Canonical verification

Implementation PRs must run the commands CI actually runs — hash-pinned, not range-resolved:

```bash
python -m pip install --require-hashes -r requirements.lock
python -m pip install --require-hashes -r requirements-dev.lock
python scripts/run_all_checks.py
```

An earlier draft specified `pip install -r requirements.txt` plus `pip install "ruff>=0.8,<1"`. That
installs an unpinned linter whose version differs from CI's, so local and CI results can disagree for
reasons unrelated to the change. The dependency-lock check and the SBOM check both enforce the pinned
set, so the loose form would also have to be undone before merge.

Test conventions, which this repository does not make discoverable:

- there is no pytest, no `pyproject.toml`, and no `conftest.py`. Tests are standalone scripts run
  directly by the check runner;
- follow one of the two existing shapes — `unittest.TestCase` with `unittest.main()`, or bare
  `test_*()` functions with the manual collector used elsewhere in `scripts/`;
- there is no package, so tests bootstrap imports with an explicit `sys.path` insert;
- register the new test in the check runner (§20.1) or it will not run.

Writer/schema changes also require focused tests and a lifecycle smoke test.

## 24. Migration plan

Ordering principle: **the cheapest effective defence ships first, with zero new dependencies.** The
original ordering built the store before the guard, which leaves the actual leak path open for the
whole of Phase 1.

### Phase 0: PRD only
No runtime behavior change.

### Phase 1: Git leak prevention
Ignore-rule hardening (§15.0); `scripts/check_private_data.py` with the stdlib detector, the
rule-based synthetic allowlist (§13.3) and reuse of the existing release secret patterns; registration
in the check runner (§20.1); tracked `.githooks/pre-commit` with documented opt-in installation
(§15.3).
Exit criteria: AC-19, AC-20, AC-05.

This phase alone closes the accident described in §2.1, and it does so before any private storage
exists — which matters, because a user with a resume in `docs/` today is exposed today.

### Phase 2: Private root and registry
Root resolution with Git-worktree refusal; hash-verified import that copies and preserves the source
(§14); flat content-addressed blob storage (§6.2); registry records that carry observation only and
no derived temporal state (§7); read-only `private-doctor` that does not require a Vault (§17.1) and
reports strays in configured scan roots using the Phase 1 detector (§13.1); already-tracked reporting
including disclosure guidance (§15.5).
Exit criteria: AC-01, AC-02, AC-03, AC-11, AC-12, AC-23, AC-24, AC-25.

Phase 2 answers "which artifacts exist and where are the bytes". It deliberately answers nothing
about currency; `private-list` therefore reports `status: observed` for every record rather than
guessing. The stray scan reuses `check_private_data.classify_bytes` directly — a second detector that
could disagree with the commit gate would make both verdicts meaningless.

### Phase 3: Timeline and current projection
Personal fact timeline; supersession and interval derivation (§8.1); `as_of` as a required parameter
with no internal clock reads (§12.4); calendar-date rejection extended to the existing paths (§19.2);
conflict/`Unknown` output shapes (§11.1). **This phase also owns document currency**: `effective_to`
and current/superseded state for document records are derived here from `effective_from` and `as_of`,
not read from the registry.
Exit criteria: AC-08, AC-10, AC-14, AC-15, AC-21, AC-22, AC-26.

**Decision (resolved and implemented): option (a).** The personal timeline extends the existing
append-only career event ledger — implementing the already-declared but never-written `superseded`
status plus `effective_from`/`effective_to` — rather than introducing a second canonical state store,
which the agent contract warns against. The shape is:

```text
raw documents
    -> private document registry        (separate; an artifact inventory, not a fact ledger)
    -> existing events.jsonl            (effective_from / effective_to / superseded /
                                         evidence.document_id)
    -> derived personal-profile projection
```

The document registry stays separate because it inventories artifacts, not claims. Personal **facts**
get no new ledger. `current/personal-profile.json` is a derived cache that must be reconstructible
from history alone (AC-14), and `as_of` is a required parameter on every internal function on this
path (AC-21).

An event carries an optional `fact` object: `category`, `key`, `value`, `effective_from`,
`expires_on`, and `supersedes`. `effective_to` is **rejected** in that payload — it is derived from
the supersession links (§8.1), and a hand-authored copy is a second source of truth that goes stale
silently the moment a link changes. `value` is required and may be explicitly `null`; a missing
`value` is a contract error, not an implicit Unknown.

**Only confirmed facts participate in supersession.** A `draft` fact never enters the projection and
never closes a confirmed fact's interval. Allowing it to would route a state change around the
approval gate: merely proposing a correction would blank the current value before the user accepted
it. A fact-bearing event may therefore only be stored as `draft` or `confirmed`; `superseded` is
derived from another fact's link, and a stored copy is a second way to say the same thing that can
disagree with the links. Ordinary career events keep the status.

**Supersession is a single chain inside one logical fact key**, and this is enforced, not assumed:

- a successor must carry the predecessor's `category` and `key` — otherwise a JLPT record can close
  a compensation record's interval and blank the salary;
- a predecessor may have at most one confirmed successor. A fork is not a value ambiguity to report
  as a `Conflict`, it is a broken chain: each successor derives a different `effective_to` for the
  same predecessor, so the last one processed wins and the projection depends on ledger order,
  breaking AC-15. It is rejected like the other topology errors (a dangling or self-referential
  `supersedes`), because the data has to be corrected rather than rendered;
- the chain must be **acyclic**. `A supersedes B` together with `B supersedes A` satisfies every
  per-node rule above — one successor, one predecessor, one key — and still derives `effective_to`
  values that precede their own `effective_from`. The projection would then report an ordinary
  `Unknown` for history that is actually corrupt, which is the worst available outcome: a wrong
  answer wearing the shape of a correct one. This layer is the canonical temporal source, so it
  fails closed.

**Anything capped must be ordered first.** Candidate lists are sorted by effective date, then fact
id, before the §12.1 cap is applied. Capping unordered input makes the *visible* subset depend on
ledger order even when the conflict itself does not — a determinism hole that a test asserting only
the happy path will not find.

### Phase 4: Context integration and the downstream read path
Current-only default context; explicit labelled historical mode; stale-context regressions; **and the
minimal read path into `data/candidate_profile.yml`** — `private-current` output becomes the value the
job-seeker skill quotes when filling that file, with the user confirming, per the existing
save-and-confirm rule.
Exit criteria: AC-07, AC-09, AC-16.

The read path moves here from the old Phase 5 deliberately. Deferring it leaves Phases 1–3 building a
store that nothing reads, and "define the relationship later" is not a requirement — it is a promise
to decide later whether the feature has a consumer at all. Note that `candidate_profile.yml` is
written by a skill following Markdown instructions rather than by Python, so "must not silently
overwrite" is satisfied by construction; "is actually usable" is the part that needs specifying.

## 25. Backward compatibility

Existing users without private storage continue to use existing flows.

The feature must not:

- reinterpret legacy data as new current facts;
- move personal documents silently on unrelated startup;
- change pipeline stages;
- require private-store initialization for unrelated repository checks.

Migration/import occurs explicitly or through `private-doctor --fix` within configured scan roots.

## 26. Observability

`private-doctor` should expose counts without leaking content.

Example:

```text
Private root: OK
Git boundary: OK
Permissions: OK

Documents:
  current: 4
  historical: 9
  quarantine: 1
  duplicates: 0

Timeline:
  compensation events: 4
  certifications: 5
  unresolved conflicts: 0

Stray documents:
  high confidence: 0
  ambiguous: 1

Current projection:
  status: consistent
```

## 27. Success metrics

Success means:

- personal documents do not need to live in the source repository;
- tracked/force-added personal documents are deterministically detected, and blocked at commit time
  wherever the tracked hook is installed;
- the detector produces no findings against this repository's own tracked content;
- documents can be imported byte-for-byte without the original being moved or deleted;
- resume/compensation/certificate history is inspectable;
- current context excludes superseded documents;
- missing current facts remain `Unknown`;
- historical comparison remains available only on explicit request;
- repository checks pass on Ubuntu and Windows.

## 28. Security and privacy requirements

- Private document bodies stay local to configured private storage unless a user explicitly invokes a model workflow that needs their contents.
- The source repository must not contain real resumes, ES, salary records, certificates, secrets, Vault data, pipeline data, or generated private runtime state.
- Test fixtures are synthetic only.
- Raw document text has `instruction_authority: none`.
- Non-private logs do not emit raw document bodies.
- Path traversal and symlink escape are tested before destructive relocation.
- The scanner does not follow arbitrary links outside configured roots by default.
- Source deletion occurs only after destination integrity verification, and only when explicitly
  requested (§14).

### 28.1 Model egress gate

The first bullet above contains the largest privacy hole in this design inside a subordinate clause:
"unless a user explicitly invokes a model workflow that needs their contents". Sending a resume body
to a model is network egress of the most sensitive data this feature stores, in a suite whose status
projection is specified never to send career data at all.

That clause therefore needs the same treatment as every other consequential action here:

- private document bodies are **never** included in context by default — neither current nor
  historical mode loads a body (§12.2 already says this; this makes it a security requirement rather
  than a context-selection preference);
- including a body requires a per-invocation confirmation naming the specific document, in the same
  shape as the existing approval gate. Consent to one document is not consent to the store;
- the confirmation states that the content leaves the machine;
- a metadata-only path (document ID, type, effective dates, headings) must be available and preferred,
  mirroring how Vault note bodies are already excluded while their metadata flows;
- no configuration setting may make body inclusion the default. An "always allow" switch converts a
  deliberate disclosure into an ambient one.

## 29. Existing commit/PR checklist alignment

This PRD is intentionally documentation-only.

For implementation changes:

- read `AGENTS.md`;
- read the relevant `_shared/agent_context/` reference;
- keep unrelated cleanup out of scope;
- preserve `Unknown`, hard-conflict, interest independence, untrusted-data boundaries, action gates, and legacy read-only behavior;
- include behavior regression tests;
- include Windows path coverage where relevant;
- include focused writer/schema tests and a lifecycle smoke test where relevant;
- include no real personal data, secrets, Vault files, pipeline data, or generated runtime state;
- run `python scripts/run_all_checks.py`.

Registration steps that are easy to miss because nothing discovers them automatically (§20.1):

- register new career-agent modules in the architecture guard's domain-module list, its
  symbol-ownership map, and the boundary-import smoke test;
- register any new canonical writer in the policy check's canonical-writer set, and fix the stale
  entry that still names `career_agent.py`;
- register every new test and `check_private_data.py` in the canonical check runner;
- if a Git-hook installation path is added, note that the Codex plugin manifest must not gain a
  `hooks` key — manifest consistency forbids it;
- CI pins its GitHub Actions by commit SHA as of 1.7.1; any new workflow step follows that.

Any non-test/non-doc behavior change under `skills/`, `_shared/`, `scripts/`, or `hooks/` must also:

1. bump both plugin versions;
2. add a `CHANGELOG.md` entry;
3. update `Current release` in `README.md`, `README_ko.md`, and `README_ja.md` — note the Japanese
   line ends with `。`, not `.`;
4. pass `scripts/check_version_bump.py` via the canonical runner.

The version baseline is **1.7.1** on `origin/main`. Implementation branches start from `origin/main`
and bump from there; the version-bump gate diffs against that ref, so a branch cut from an older
merged branch will compare against the wrong base.

PR descriptions must state:

- contract/behavior changed;
- why the change is in scope;
- files touched;
- regression tests;
- exact verification commands/results;
- remaining limitations.

## 30. Definition of done

The feature is complete only when:

- private storage cannot resolve inside a Git worktree;
- import is hash-verified, retry-safe, and preserves the source by default;
- stray-document detection exists and is clean against this repository's own `HEAD`;
- ignore rules cover the ordinary accident, and the commit check blocks staged and force-added
  personal documents **when the tracked hook is installed**, with CI failing the pull request
  otherwise. "Blocked" is scoped to the layer that is actually in effect: claiming unconditional
  blocking would overstate what an opt-in hook can guarantee, and `private-doctor` reports the
  installation state so the user can see which layer is protecting them;
- document/fact temporal history is preserved;
- compensation and certificate history is inspectable;
- current personal profile is deterministically projected;
- superseded documents are excluded from default context;
- historical context is explicit and labeled;
- stale values never silently become current;
- missing current values remain `Unknown`;
- synthetic tests cover Git, temporal, context, failure, concurrency, and Windows behavior;
- `python scripts/run_all_checks.py` passes in the repository CI matrix;
- version/release documentation is updated for every behavior-changing implementation PR as required.
