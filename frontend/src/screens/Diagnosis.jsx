/* Six independent answers about the record — never a score.

   The runtime already computes one state per dimension and marks the payload `no_total_by_design`.
   This screen shows those states with the counts behind them, which is what turns "Needs
   rechecking" from a verdict into something the user can check for themselves. */

import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { read } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { ReadinessChip } from "../evidence.jsx";
import { ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate } from "../App.jsx";

/* Which counts stand behind each dimension, and where it can actually be acted on. A state with
   no route to change it is just a scold. */
const DIMENSION_EVIDENCE = {
  recent_work_evidence: ["dated_in_last_year", "dated_work_events", "undated_work_events"],
  project_history: ["projects"],
  individual_contribution: ["confirmed_work_events"],
  metrics_evidence: ["confirmed_work_events"],
  career_contexts: ["career_contexts"],
  experience_coverage: ["experiences"],
};

export default function DiagnosisScreen() {
  const { t, enumText } = useI18n();
  const state = useAsync(() => read("/api/home"), []);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} />;

  const readiness = state.data.readiness || {};
  const counts = readiness.counts || {};
  const dimensions = readiness.dimensions || {};
  const needsReview = counts.external_use_review_required || 0;

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("diagnosis.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("diagnosis.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("diagnosis.intro")}
        </Text>
      </header>

      {readiness.as_of ? (
        <span className="figure">{t("diagnosis.as_of", { date: readiness.as_of })}</span>
      ) : null}

      {/* Nothing to quote is a fact about the Vault, not about the person. */}
      {readiness.bootstrap_suggested ? (
        <Callout.Root tone="warning">
          <Callout.Content>
            <Callout.Title>{t("diagnosis.empty_title")}</Callout.Title>
            <Callout.Description>{t("diagnosis.empty_body")}</Callout.Description>
            <Callout.Link onClick={() => navigate("/career")}>{t("career.add_context")}</Callout.Link>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      <ul className="lines" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {Object.entries(dimensions).map(([name, value]) => {
          const evidence = (DIMENSION_EVIDENCE[name] || [])
            .filter((key) => counts[key] !== undefined)
            .map((key) => t(`diagnosis.counts.${key}`, { count: counts[key] }));
          return (
            <li className="diagnosis-row" key={name}>
              <div className="inline">
                <Text textStyle="t4Bold" style={{ flex: "1 1 12rem" }}>
                  {enumText("readiness_dimension", name)}
                </Text>
                <ReadinessChip state={value} />
              </div>
              {evidence.length ? (
                <span className="figure">
                  {t("diagnosis.evidence_label")}: {evidence.join(t("common.list_separator"))}
                </span>
              ) : null}
              <div>
                <ActionButton variant="ghost" size="xsmall" onClick={() => navigate("/career")}>
                  {t("action.view_all")}
                </ActionButton>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Stated in the interface, not just in the code: this screen refuses to add up. */}
      <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
        {t("diagnosis.no_total")}
      </Text>

      {needsReview ? (
        <section className="record__section">
          <h3 className="record__section-title">{t("diagnosis.review_title")}</h3>
          <Text textStyle="t3Regular">{t("diagnosis.review_body", { count: needsReview })}</Text>
          <div>
            <ActionButton variant="neutralOutline" size="small" onClick={() => navigate("/applications")}>
              {t("nav.applications")}
            </ActionButton>
          </div>
        </section>
      ) : null}
    </div>
  );
}
