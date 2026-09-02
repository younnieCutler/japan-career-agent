import React from "react";
import { ActionButton, Badge, Text } from "@seed-design/react";

import { useAsync } from "./components/States.jsx";
import { read, write } from "./api.js";
import { useI18n } from "./i18n.jsx";
import { JudgmentDifference, JudgmentGate } from "./judgment.jsx";


const DECISIONS = ["proceed", "hold", "stop", "unknown"];

function decisionLabels(t) {
  return Object.fromEntries(DECISIONS.map((value) => [value, t(`judgment.choice.${value}`)]));
}

function differenceLabels(t) {
  return {
    choices: decisionLabels(t),
    human: t("judgment.initial_title"),
    agent: t("judgment.agent_title"),
    divergedTitle: t("judgment.diverged"),
    alignedTitle: t("judgment.aligned"),
  };
}

function gateLabels(t) {
  return {
    question: t("judgment.question"),
    help: t("judgment.help"),
    reason: t("judgment.reason"),
    continue: t("judgment.submit_initial"),
    errorTitle: t("judgment.save_failed"),
    error: t("error.SAVE_FAILED"),
    choices: decisionLabels(t),
  };
}

function DecisionForm({ title, intro, reasonLabel, submitLabel, onSubmit }) {
  const { t } = useI18n();
  const [decision, setDecision] = React.useState("unknown");
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const requestPending = React.useRef(false);
  const groupName = React.useId();

  const submit = async (event) => {
    event.preventDefault();
    if (requestPending.current) return;
    requestPending.current = true;
    setBusy(true);
    setError("");
    try {
      await onSubmit({ decision, reason: reason.trim() });
    } catch (nextError) {
      setError(nextError?.message || "SAVE_FAILED");
    } finally {
      requestPending.current = false;
      setBusy(false);
    }
  };

  return (
    <form className="form-stack" onSubmit={submit}>
      <div className="stack tight">
        <Text textStyle="t5Bold">{title}</Text>
        <Text color="palette.fg.neutralSubtle">{intro}</Text>
      </div>
      <fieldset className="choice-grid" disabled={busy}>
        <legend className="sr-only">{title}</legend>
        {DECISIONS.map((value) => (
          <label className="choice" key={value}>
            <input
              type="radio"
              name={groupName}
              value={value}
              checked={decision === value}
              onChange={() => setDecision(value)}
            />
            <span>{t(`judgment.choice.${value}`)}</span>
          </label>
        ))}
      </fieldset>
      <label className="field">
        <span>{reasonLabel}</span>
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} disabled={busy} />
      </label>
      {error ? <Text color="palette.fg.critical">{t("error.SAVE_FAILED")}</Text> : null}
      <ActionButton type="submit" variant="brandSolid" disabled={busy}>
        {submitLabel}
      </ActionButton>
    </form>
  );
}

function HumanInitial({ value }) {
  const { t } = useI18n();
  return (
    <div className="stack tight">
      <Text textStyle="t5Bold">{t("judgment.initial_title")}</Text>
      <Badge variant="neutralWeak">{t(`judgment.choice.${value.decision}`)}</Badge>
      {value.reasons?.length ? <Text color="palette.fg.neutralSubtle">{value.reasons.join(" · ")}</Text> : null}
    </div>
  );
}

function AgentAssessment({ value }) {
  const { t, enumText } = useI18n();
  return (
    <div className="stack tight">
      <Text textStyle="t5Bold">{t("judgment.agent_title")}</Text>
      <div className="facts compact-facts">
        <span>{t(`judgment.choice.${value.recommendation}`)}</span>
        <span>{t("judgment.confidence")}: {enumText("confidence", value.confidence)}</span>
      </div>
      <Text textStyle="t6Bold">{t("judgment.reasons")}</Text>
      <Text color="palette.fg.neutralSubtle">
        {value.reasons?.length ? value.reasons.join(" · ") : t("judgment.no_reasons")}
      </Text>
      <Text textStyle="t6Bold">{t("judgment.unknowns")}</Text>
      <Text color="palette.fg.neutralSubtle">
        {value.unknowns?.length ? value.unknowns.join(" · ") : t("judgment.no_unknowns")}
      </Text>
      {value.evidence_ref_count ? (
        <Text color="palette.fg.neutralSubtle">{t("judgment.evidence_count", { count: value.evidence_ref_count })}</Text>
      ) : null}
    </div>
  );
}

function WaitingForAgent({ initial }) {
  const { t } = useI18n();
  return (
    <div className="notice stack tight">
      {initial ? <HumanInitial value={initial} /> : null}
      <Text textStyle="t5Bold">{t("judgment.waiting_title")}</Text>
      <Text color="palette.fg.neutralSubtle">{t("judgment.waiting_body")}</Text>
    </div>
  );
}

function CompletedJudgment({ judgment, refresh }) {
  const { t } = useI18n();
  const [newRound, setNewRound] = React.useState(false);
  if (newRound) {
    return <InitialGate positionRef={judgment.target_ref} refresh={refresh} />;
  }
  return (
    <div className="stack tight">
      <HumanInitial value={judgment.human_initial} />
      <AgentAssessment value={judgment.agent_assessment} />
      <JudgmentDifference
        humanDecision={judgment.human_initial.decision}
        agentDecision={judgment.agent_assessment.recommendation}
        labels={differenceLabels(t)}
      />
      <div className="stack tight">
        <Text textStyle="t5Bold">{t("judgment.final_title")}</Text>
        <Badge variant="neutralWeak">{t(`judgment.choice.${judgment.human_final.decision}`)}</Badge>
        {judgment.human_final.reasons?.length ? (
          <Text color="palette.fg.neutralSubtle">{judgment.human_final.reasons.join(" · ")}</Text>
        ) : null}
      </div>
      {judgment.outcome ? (
        <div className="stack tight">
          <Text textStyle="t5Bold">{t("judgment.outcome_title")}</Text>
          <Badge variant="neutralWeak">{t(`judgment.choice.${judgment.outcome.value}`)}</Badge>
          {judgment.outcome.notes ? <Text color="palette.fg.neutralSubtle">{judgment.outcome.notes}</Text> : null}
        </div>
      ) : (
        <DecisionForm
          title={t("judgment.outcome_title")}
          intro={t("judgment.outcome_intro")}
          reasonLabel={t("judgment.outcome_reason")}
          submitLabel={t("judgment.submit_outcome")}
          onSubmit={async ({ decision, reason }) => {
            await write("/api/judgments/outcome", {
              judgment_id: judgment.judgment_id,
              outcome: decision,
              notes: reason || undefined,
            });
            refresh();
          }}
        />
      )}
      {judgment.outcome ? (
        <ActionButton type="button" variant="neutralWeak" onClick={() => setNewRound(true)}>
          {t("judgment.new_round")}
        </ActionButton>
      ) : null}
    </div>
  );
}

function InitialGate({ positionRef, refresh }) {
  const { t } = useI18n();
  return (
    <JudgmentGate
      labels={gateLabels(t)}
      onSubmit={async ({ decision, reasons }) => {
        await write("/api/judgments/initial", {
          subject: "application",
          target_ref: positionRef,
          decision,
          reasons,
        });
        refresh();
      }}
    >
      <WaitingForAgent />
    </JudgmentGate>
  );
}

export function ApplicationJudgment({ positionRef }) {
  const { t } = useI18n();
  const [reloadKey, setReloadKey] = React.useState(0);
  const refresh = React.useCallback(() => setReloadKey((value) => value + 1), []);
  const { data, loading, error } = useAsync(
    () => read(`/api/judgments?target_ref=${encodeURIComponent(positionRef)}`),
    [positionRef, reloadKey],
  );

  const latest = data?.judgments?.[0] || null;

  return (
    <section className="record stack" aria-label={t("judgment.title")}>
      <div className="stack tight">
        <Text textStyle="t4Bold">{t("judgment.title")}</Text>
        <Text color="palette.fg.neutralSubtle">{t("judgment.intro")}</Text>
      </div>
      {loading ? <Text color="palette.fg.neutralSubtle">{t("state.loading")}</Text> : null}
      {error ? <Text color="palette.fg.critical">{t("error.READ_FAILED")}</Text> : null}
      {!loading && !error && !latest ? <InitialGate positionRef={positionRef} refresh={refresh} /> : null}
      {!loading && !error && latest && !latest.agent_assessment ? (
        <WaitingForAgent initial={latest.human_initial} />
      ) : null}
      {!loading && !error && latest?.agent_assessment && !latest.human_final ? (
        <div className="stack">
          <HumanInitial value={latest.human_initial} />
          <AgentAssessment value={latest.agent_assessment} />
          <JudgmentDifference
            humanDecision={latest.human_initial.decision}
            agentDecision={latest.agent_assessment.recommendation}
            labels={differenceLabels(t)}
          />
          <DecisionForm
            title={t("judgment.final_title")}
            intro={t("judgment.final_intro")}
            reasonLabel={t("judgment.final_reason")}
            submitLabel={t("judgment.submit_final")}
            onSubmit={async ({ decision, reason }) => {
              await write("/api/judgments/final", {
                judgment_id: latest.judgment_id,
                decision,
                reasons: reason ? [reason] : [],
              });
              refresh();
            }}
          />
        </div>
      ) : null}
      {!loading && !error && latest?.human_final ? (
        <CompletedJudgment judgment={latest} refresh={refresh} />
      ) : null}
    </section>
  );
}
