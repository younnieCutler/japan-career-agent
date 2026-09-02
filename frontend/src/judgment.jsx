import React from "react";
import { ActionButton, Callout } from "@seed-design/react";

export const JUDGMENT_CHOICES = ["proceed", "hold", "stop", "unknown"];

/* Human-first decision gate for consequential actions.
 *
 * This component owns no product copy and no persistence. Callers provide localized labels and
 * an async onSubmit callback. Agent analysis is not rendered until the human's initial judgment
 * has been successfully recorded, so a slow or failed write cannot accidentally reveal the answer
 * first and turn the interaction into post-hoc agreement.
 */
export function JudgmentGate({ labels, onSubmit, children }) {
  const [decision, setDecision] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [revealed, setRevealed] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [failure, setFailure] = React.useState(null);
  const submitGuard = React.useRef(false);
  const choiceRefs = React.useRef([]);
  const questionId = React.useId();
  const reasonId = React.useId();

  const selectAndFocus = (index) => {
    const normalized = (index + JUDGMENT_CHOICES.length) % JUDGMENT_CHOICES.length;
    setDecision(JUDGMENT_CHOICES[normalized]);
    choiceRefs.current[normalized]?.focus();
  };

  const onChoiceKeyDown = (event, index) => {
    let next = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = index + 1;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = index - 1;
    if (event.key === "Home") next = 0;
    if (event.key === "End") next = JUDGMENT_CHOICES.length - 1;
    if (next === null) return;
    event.preventDefault();
    selectAndFocus(next);
  };

  const submit = async () => {
    if (!decision || busy || submitGuard.current) return;
    submitGuard.current = true;
    setBusy(true);
    setFailure(null);
    try {
      await onSubmit({ decision, reasons: reason.trim() ? [reason.trim()] : [] });
      setRevealed(true);
    } catch (error) {
      setFailure(error);
    } finally {
      submitGuard.current = false;
      setBusy(false);
    }
  };

  if (revealed) return children;

  return (
    <section className="record__section" aria-labelledby={questionId}>
      <h3 id={questionId} className="record__section-title">{labels.question}</h3>
      {labels.help ? <p className="muted">{labels.help}</p> : null}

      <div role="radiogroup" aria-labelledby={questionId} className="choice-grid">
        {JUDGMENT_CHOICES.map((choice, index) => (
          <ActionButton
            key={choice}
            ref={(node) => { choiceRefs.current[index] = node; }}
            variant={decision === choice ? "brandSolid" : "neutralWeak"}
            size="medium"
            role="radio"
            aria-checked={decision === choice}
            tabIndex={decision === choice || (!decision && index === 0) ? 0 : -1}
            onKeyDown={(event) => onChoiceKeyDown(event, index)}
            onClick={() => setDecision(choice)}
            disabled={busy}
          >
            {labels.choices[choice]}
          </ActionButton>
        ))}
      </div>

      <label className="field-label" htmlFor={reasonId}>{labels.reason}</label>
      <textarea
        id={reasonId}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        disabled={busy}
        rows={3}
      />

      {failure ? (
        <Callout.Root tone="critical">
          <Callout.Content>
            <Callout.Title>{labels.errorTitle}</Callout.Title>
            <Callout.Description>{labels.error}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      <ActionButton variant="brandSolid" size="medium" onClick={submit} disabled={!decision || busy}>
        {labels.continue}
      </ActionButton>
    </section>
  );
}

export function JudgmentDifference({ humanDecision, agentDecision, labels }) {
  const diverged = humanDecision !== agentDecision;
  const human = labels.choices[humanDecision] || labels.choices.unknown;
  const agent = labels.choices[agentDecision] || labels.choices.unknown;
  return (
    <Callout.Root tone={diverged ? "informative" : "neutral"}>
      <Callout.Content>
        <Callout.Title>{diverged ? labels.divergedTitle : labels.alignedTitle}</Callout.Title>
        <Callout.Description>
          {labels.human}: {human} · {labels.agent}: {agent}
        </Callout.Description>
      </Callout.Content>
    </Callout.Root>
  );
}
