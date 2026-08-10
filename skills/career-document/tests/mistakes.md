# career-document — recorded mistakes

## Letting the JD supply vocabulary

An early draft mapped JD keywords onto the skills section directly, on the grounds that the JD
names the words a recruiter searches for. It produced documents claiming technologies the user had
never touched. A requirement says what the company wants; only evidence says what the user did, and
`unknown_requirements` exists so the gap can be visible instead of filled.

## Treating the gate as advisory

The first version ran the fidelity gate as a reporting step and let the caller render anyway. The
failure being guarded against is a document reaching a recruiter, so "the caller was supposed to
check" is not a guarantee. `document-render` now runs the gate itself and writes nothing on
failure.

## Overwriting the previous document

Regenerating replaced the file at the same path. A user who had already sent the earlier version
had no way to see what changed. Filenames now carry a digest of the evidence, JD, template and
wording, so a regeneration lands beside its predecessor and staleness is reported rather than
resolved by deletion.

## Fixing a gate failure by editing the evidence

Tempting, and backwards. A violation means the sentence claims more than the record supports; if
the record is genuinely incomplete, that is a new fact and goes through approval. Editing evidence
to make prose pass turns the ledger into a function of the document.
