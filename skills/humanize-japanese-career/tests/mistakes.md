# humanize-japanese-career — recorded mistakes

## Reaching for a general humanizer

General writing advice says to merge short fragments into flowing prose and vary sentence
structure. Applied to a 職務経歴書 it destroys the thing the document is for: it is scanned in
about thirty seconds, and bullets, headings and short sentences are what make that possible. Hence
a separate genre contract rather than a general skill with a note attached.

## Polishing text without its claims

The first version received only the draft sentence. Asked to make `デプロイの効率化を実現` concrete,
it produced a plausible number — nothing in its input said which numbers existed. Passing
`protected_claims` alongside the text makes the boundary data instead of something to infer.

## Softening a claim into vagueness

Over-correcting is the other direction of the same failure. Removing `28.4%` because it "sounds
oddly precise" throws away the strongest thing in the document. Recorded numbers are quoted
exactly; only unrecorded ones are absent.

## Optimising for a detector

Briefly considered as a proxy metric, and dropped. A detector measures whether text looks
generated, which is unrelated to whether it describes the user's career accurately — and a sentence
rewritten to fool a classifier serves no reader.
