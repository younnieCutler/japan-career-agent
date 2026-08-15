# Design Direction — Career Workspace

## Product Goal
Let one person keep an honest, local record of what they actually did at work, and decide
deliberately what becomes part of that record. The GUI is a peer entrypoint over the same runtime
as the CLI; the Career Vault stays authoritative.

## Audience
A single person mid-job-change in Japan, working alone on their own machine, often at night, in
Korean, Japanese, or English. Not a recruiter, not a team, not a manager reviewing a pipeline.

## Visual Thesis
**棚卸し — a ledger you keep about yourself.**

棚卸し is an accounting word: taking inventory, counting what is actually on the shelf. The
product's own vocabulary is bookkeeping — entries, evidence, approval, revision, canonical versus
draft. So the artifact this interface should resemble is a ledger, not a magazine and not a
dashboard.

What that buys us: a ledger is the one document type whose entire visual grammar exists to answer
"what has been attested, and by whom?" That is this product's central question. A dashboard's
grammar answers "how am I doing?" — a question this product refuses to answer.

We take the ledger's **structure** (ruled rows, aligned figures, a margin that carries state,
discipline about alignment) and reject its **skeuomorphism** (paper texture, stamps, faux aging).

### Explicitly moving away from
The previous system was warm cream + high-contrast serif display + warm accent. That is a
reasonable look, but it is also the single most common default in machine-generated design, and it
was doing nothing for this subject in particular. The ledger reading is specific to 棚卸し.

## Signature: the attestation dot
Every record row opens with a dot in a fixed left column whose colour and form state that row's
evidence state. Scanning only the left edge of the screen tells you what is real and what is still
a claim. It is the trust model made visible, and it is the one element the screen is remembered by.

This was a ruled left margin until the screen was reviewed as a whole. The rail was correct about
*what* to say and wrong about *how*: it added a third vertical line to rows that already sat inside
a bordered split inside a bordered panel, and at that density the left edge read as ruling rather
than as state. The dot keeps the column, the four states, and the two colour rules below; it drops
the line. The lines it competed with — the box around the split, the fieldset outline, the dashed
unknown box — went with it, so the remaining hairlines separate things instead of enclosing them.

A draft is drawn as a **hollow ring** rather than a tinted dot: the same rule the dashed rail
carried, in the dot's vocabulary. Nothing has been written in ink yet.

Everything else stays quiet: no gradients, no glass, no shadows except the two genuinely floating
surfaces (modal, sticky action bar).

Driven from the `data-tone` and `data-conflict` attributes the row already carries, as a `::before`
pseudo-element, so it needs no markup change and no JavaScript.

## Colour & Materials
Six roles. Hue carries meaning; nothing is coloured for decoration.

| Token | Light | Role |
|---|---|---|
| `--ground` | `#faf8f4` | the page — the paper the ledger is written on |
| `--ink` | `#1b1d22` | primary text, near-black with a blue cast |
| `--ink-2` | `#5d6470` | secondary text, labels, metadata |
| `--rule` | `#ddd8ce` | hairlines; the ruling of the page |
| `--attest` | `#2c4a7c` | indigo. Confirmed / canonical / primary action |
| `--pending` | `#8a6a1f` | ochre. Waiting on the user's decision |
| `--conflict` | `#a32c1e` | vermilion (朱). Contradiction only |

Two rules about colour that are not negotiable:

1. **Vermilion means contradiction and nothing else.** It is never used for emphasis, never for a
   destructive button, never for a decorative accent. When the user sees red, something disagrees
   with something else.
2. **Draft has no colour at all.** A draft is the *absence* of attestation, so it is drawn as a
   dashed rule in secondary ink. Nothing has been written in ink yet. This is why the draft chip
   and the draft rail are dashed rather than tinted.

The previous accent was forest green. Green reads as "good" and, applied to approval, quietly
implies that more approved records is a better score. Approval here means "you attested to this,"
not "this is good." Indigo says recorded; green says well done. The product does not grade you.

Dark mode keeps every hue role and inverts the ground to a warm near-black, so it is the same
ledger at night rather than a second theme.

## Typography
The Content-Security-Policy is `default-src 'none'` with no `font-src`, so webfonts are impossible
by construction. Three system roles, and the interesting one is the third.

- **Body / UI** — system sans (`ui-sans-serif`, Noto Sans KR/JP). Everything the user reads.
- **Record voice** — system serif (`ui-serif`, Noto Serif KR/JP), used *small and sparingly* for
  headings and record titles. The written, human part of the ledger. Not a 4rem hero.
- **Figure voice** — `ui-monospace` with `tabular-nums`, for every date, period, count, and
  version. This is the ledger's own voice: in a ledger, figures align in a column. It was unused
  before and is the type signature now.

Scale is a 1.2 (minor third) ratio, which is tighter than a display ratio because this is dense
personal data, not a landing page. The old h1 was `clamp(2rem, 5vw, 4.2rem)` — landing-page scale
on a data screen, and it pushed the actual content below the fold.

### CJK correctness
The primary locales are Korean and Japanese, so these are correctness issues, not polish:

- `word-break: keep-all` on body text. The old sheet set `overflow-wrap: anywhere`, which breaks
  Korean mid-word at arbitrary syllable blocks.
- No aggressive negative letter-spacing. The old titles used `-0.045em`, which damages hangul and
  kana legibility. Tracking is applied only where the text is small caps-style Latin labels.
- Body `line-height: 1.7`. CJK needs more leading than Latin at the same size.
- Never `font-style: italic` — Korean and Japanese have no italic face, so browsers synthesise a
  slanted one.

## Grid & Spacing
A 4px base with eight steps, replacing roughly twenty ad-hoc values. Radius collapses from seven
values to two: `2px` for surfaces and `999px` for chips. Weights collapse from four arbitrary
values (650/700/750/800) to three (400/600/700).

Content column is capped at `72rem`; the reading measure for prose is capped at `62ch`.

## Structure over containers
The old sheet gave six semantically different components (`.section-block`, `.next-action`,
`.state-panel`, `.message-panel`, `.recovery-panel`, `.document-card`) the identical treatment:
1px border, rounded corners, raised background. Everything looked equally important, so nothing
was.

Replaced by four surface levels:

- **flat** — no border, separated by space alone. Default for content grouping.
- **ruled** — separated by a hairline. Default for lists and rows.
- **filled** — a tinted background, no border. Groups a form or an aside without drawing a box
  inside the box it already sits in.
- **marked** — a tint in a role colour. Only for the single next action and for messages. This was
  a 3px left rule until the rails came out; a lone coloured edge on an otherwise unruled screen
  read as damage rather than as emphasis, and the brand tint is the only one of its kind here.

## Interaction Language
Quiet and immediate. Hover changes background, never size or shadow. Focus is a 2px `--attest`
ring with a 2px offset, visible on every interactive element in both schemes.

## Motion System
Almost none, deliberately. A 120ms fade on route change and 90ms background transitions on
interactive elements. No scroll animation, no reveals, no parallax. A ledger does not animate, and
motion here would read as a product trying to feel impressive about someone's career anxiety.
`prefers-reduced-motion` reduces both to near-zero.

## Responsive Rules
Desktop-first; the data is dense and the primary use is at a desk. The side rail collapses to a
bottom bar under 900px. The attestation dot is drawn at every size — it is the last thing to be
sacrificed, not the first.

## Accessibility
Every text and chip pair meets WCAG AA in both schemes, verified by computing contrast from
rendered styles rather than by eye. Status is never carried by colour alone: every rail and chip
also carries a text label. Keyboard focus is always visible.

## Things We Explicitly Avoid
- Any chart, sparkline, gauge, meter, or progress ring.
- Any composite score, ranking, percentage of completeness, or hire probability.
- Success-green for approval.
- Vermilion for anything except contradiction.
- Gradients, glassmorphism, decorative blobs, drop shadows on static content.
- Skeuomorphic paper texture or stamp graphics.
- A hero. This is an application screen; the content starts immediately.
