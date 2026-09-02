import React from "react";
import { ActionButton, Callout } from "@seed-design/react";

export const JUDGMENT_CHOICES = ["proceed", "hold", "stop", "unknown"];

/*
 * Human-first decision gate for consequential actions.
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

  const submit = async () => {
    if (!decision || busy) return;
    setBusy(true);
    setFailure(null);
    try {
      await onSubmit({ decision, reasons: reason.trim() ? [reason.trim()] : [] });
      setRevealed(true);
    } catch (error) {
      setFailure(error);
    } finally {
      setBusy(false);
    }
  };

  if (revealed) return children;

  return (
    <section className="record__section" aria-labelledby="judgment-question">
      <h3 id="judgment-question" className="record__section-title">{labels.question}</h3>
      {labels.help ? <p className="muted">{labels.help}</p> : null}

      <div role="radiogroup" aria-label={labels.question} className="choice-grid">
        {JUDGMENT_CHOICES.map((choice) => (
          <ActionButton
            key={choice}
            variant={decision === choice ? "brandSolid" : "neutralWeak"}
            size="medium"
            role="radio"
            aria-checked={decision === choice}
            onClick={() => setDecision(choice)}
            disabled={busy}
          >
            {labels.choices[choice]}
          </ActionButton>
        ))}
      </div>

      <label className="field-label" htmlFor="judgment-reason">{labels.reason}</label>
      <textarea
        id="judgment-reason"
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
  return (
    <Callout.Root tone={diverged ? "informative" : "neutral"}>
      <Callout.Content>
        <Callout.Title>{diverged ? labels.divergedTitle : labels.alignedTitle}</Callout.Title>
        <Callout.Description>
          {labels.human}: {labels.choices[humanDecision]} · {labels.agent}: {labels.choices[agentDecision]}
        </Callout.Description>
      </Callout.Content>
    </Callout.Root>
  );
}
