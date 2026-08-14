/* The approval gate.

   This is the one screen the product's promise rests on: nothing becomes Confirmed without the
   user reading what will be written and saying yes. The rules below are carried over unchanged
   from the previous client because they are contracts, not presentation:

   1. The snapshot renders the server's proposal, not the form. What the user approves is what the
      server will write.
   2. "Not entered" and "still unknown" are different answers and get separate boxes. Collapsing
      them would let a field the user deliberately marked unknown read as an oversight, and an
      oversight read as a decision.
   3. Approve is not a close button. A failed approve keeps the dialog open with the error, because
      dismissing on failure is how a user comes to believe something was saved when it was not.
   4. Internal identifiers never reach the screen — HIDDEN_REVIEW_FIELDS — and any key without a
      product label is dropped rather than shown raw. */

import React from "react";
import { ActionButton, Callout, ContentDialog, Divider, Text } from "@seed-design/react";
import { useI18n } from "./i18n.jsx";
import { ErrorState } from "./components/States.jsx";

export function proposalPayload(event) {
  if (event.work_event) return ["experience", { summary: event.claim_summary, ...event.work_event }];
  if (event.experience) return ["experience", { summary: event.claim_summary, ...event.experience }];
  if (event.experience_context) return ["context", event.experience_context];
  if (event.project) return ["project", event.project];
  if (event.career_context) return ["profile", event.career_context];
  return ["experience", {}];
}

export const HIDDEN_REVIEW_FIELDS = new Set([
  "id", "context_id", "primary_project_id", "related_project_ids", "experience_ref",
  "profile_digest", "self_analysis_version", "source_type", "episode_ref", "evidence_episode_refs",
]);

export const FIELD_LABELS = new Set([
  "label", "kind", "title", "role", "scope", "summary", "period", "problem",
  "direct_actions", "individual_contribution", "team_result", "outcome_state", "metrics",
  "improvements", "learning", "work_date", "confidentiality", "contains_confidential",
  "external_use", "candidate_name", "language_preference", "track", "interest_hypotheses",
  "behavior_tendencies", "evidence_episodes", "career_self_efficacy", "perceived_barriers",
  "perceived_supports", "environment_preferences", "value_candidates", "avoid_candidates",
  "preferred_environment_hypothesis", "verification_questions", "recommended_role_clusters",
  "self_pr_seeds", "career_anchors", "derailers", "energy_map", "career_theme", "career_values",
  "career_context_confirmed", "notes", "activity", "response_basis", "confidence", "name",
  "self_report", "experience_type", "situation", "action", "energy_effect", "energy_reason",
  "learning_confidence", "outcome_expectation", "goal", "autonomy", "competence", "relatedness",
  "structure_preference", "speed_preference", "change_tolerance", "collaboration_preference",
  "feedback_frequency", "preference", "hypothesis", "verification_question", "primary",
  "secondary", "will_not_give_up", "strength", "overuse_risk", "watch_signal", "energizes",
  "drains", "misfit_flag", "must_have", "avoid", "seed", "status", "external_label",
]);

const shown = (key) => !HIDDEN_REVIEW_FIELDS.has(key) && FIELD_LABELS.has(key);

/* A value the user never supplied and a value they marked unknown both count here: the point is
   whether the record will carry an answer, not how the blank got there. */
export function containsUnknown(key, value) {
  if (value === null || value === undefined || value === "" || value === "unknown") return true;
  if (Array.isArray(value)) return value.some((item) => containsUnknown(key, item));
  if (!value || typeof value !== "object") return false;
  if (key === "period" && value.current === true) return !value.from;
  return Object.entries(value).some(([childKey, child]) => containsUnknown(childKey, child));
}

function useScalarText() {
  const { t, enumText } = useI18n();
  return React.useCallback((key, value, rootKind = null) => {
    if (value === null || value === undefined || value === "") return t("common.unknown");
    if (typeof value === "boolean") return t(value ? "common.yes" : "common.no");
    if (key === "external_use") return enumText("external_use", value);
    if (key === "outcome_state") return enumText("outcome", value);
    if (key === "kind") return enumText("context_kind", value);
    if (key === "track") return enumText("track", value);
    if (key === "language_preference") return t(`language.${value}`);
    if (key === "confidence") return enumText("confidence", value);
    if (key === "energy_effect") return enumText("energy", value);
    if (key === "status" && rootKind === "project") return enumText("project_status", value);
    if (key === "status" && rootKind === "profile") return enumText("self_analysis_state", value);
    if (key === "status") return t("common.other");
    return String(value);
  }, [t, enumText]);
}

export function Value({ name, value, depth = 0, rootKind = null }) {
  const { t, periodText } = useI18n();
  const scalarText = useScalarText();

  if (Array.isArray(value)) {
    if (!value.length) return <span className="unknown">{t("common.reviewed_empty")}</span>;
    return (
      <ul className={depth ? "nested-list" : "value-list"}>
        {value.map((item, index) => (
          <li key={index}><Value name={name} value={item} depth={depth + 1} rootKind={rootKind} /></li>
        ))}
      </ul>
    );
  }
  if (value && typeof value === "object") {
    if (name === "period") return <span>{periodText(value)}</span>;
    return (
      <dl className="facts">
        {Object.entries(value).filter(([key]) => shown(key)).map(([key, child]) => (
          <React.Fragment key={key}>
            <dt>{t(`field.${key}`)}</dt>
            <dd><Value name={key} value={child} depth={depth + 1} rootKind={rootKind} /></dd>
          </React.Fragment>
        ))}
      </dl>
    );
  }
  const blank = value === null || value === undefined;
  return <span className={blank ? "unknown" : ""}>{scalarText(name, value, rootKind)}</span>;
}

const EXPECTED = {
  experience: ["summary", "work_date", "role", "scope", "problem", "direct_actions",
    "individual_contribution", "team_result", "outcome_state", "metrics", "confidentiality"],
  project: ["title", "role", "scope", "summary", "period"],
  context: ["label", "kind", "role", "summary", "period"],
};

export function SnapshotView({ event }) {
  const { t } = useI18n();
  const [kind, payload] = proposalPayload(event || {});
  const values = Object.entries(payload || {}).filter(([key]) => shown(key));

  let expected = kind === "profile"
    ? Object.keys(payload || {}).filter((key) => FIELD_LABELS.has(key))
    : (EXPECTED[kind] || []);
  // Metrics are only expected where the user said the outcome was measured; asking for them
  // otherwise would report a gap the record does not actually have.
  if (kind === "experience" && payload?.outcome_state !== "quantitative") {
    expected = expected.filter((key) => key !== "metrics");
  }
  const absent = expected.filter((key) => !Object.hasOwn(payload || {}, key));
  const unknown = expected.filter(
    (key) => Object.hasOwn(payload || {}, key) && containsUnknown(key, payload[key]));

  const evidence = (event?.evidence || []).map((item) => (
    item === "user_confirmation" ? t("review.evidence_user_confirmation")
      : String(item).startsWith("private-document:") ? t("review.evidence_private_document")
        : item));

  return (
    <section className="approval-snapshot record__section">
      <h3 className="record__section-title">{t("review.after")}</h3>
      <Text textStyle="t5Bold">{t(`review.snapshot.${kind}`)}</Text>
      <dl className="facts">
        {values.map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{t(`field.${key}`)}</dt>
            <dd><Value name={key} value={value} rootKind={kind} /></dd>
          </React.Fragment>
        ))}
      </dl>

      <div className="unknown-box">
        <h4>{t("review.not_entered_title")}</h4>
        <p>{absent.length
          ? absent.map((key) => t(`field.${key}`)).join(t("common.list_separator"))
          : t("review.not_entered_none")}</p>
      </div>
      <div className="unknown-box">
        <h4>{t("review.unknown_title")}</h4>
        <p>{unknown.length
          ? unknown.map((key) => t(`field.${key}`)).join(t("common.list_separator"))
          : t("review.unknown_none")}</p>
        <p className="muted">{t("review.unknown_help")}</p>
      </div>
      <div className="unknown-box">
        <h4>{t("review.evidence_title")}</h4>
        <p>{kind === "profile" ? t("review.profile_source")
          : evidence.length ? evidence.join(t("common.list_separator")) : t("review.evidence_missing")}</p>
      </div>
    </section>
  );
}

export function ChangesView({ before, event }) {
  const { t } = useI18n();
  const [kind, after] = proposalPayload(event || {});
  const changed = [...new Set([...Object.keys(before || {}), ...Object.keys(after || {})])]
    .filter(shown)
    .filter((key) => JSON.stringify(before?.[key]) !== JSON.stringify(after?.[key]));

  return (
    <section className="before-box record__section">
      <h3 className="record__section-title">{t("review.changes_title")}</h3>
      {changed.length ? (
        <dl className="facts">
          {changed.map((key) => (
            <React.Fragment key={key}>
              <dt>{t(`field.${key}`)}</dt>
              <dd>
                <p className="input-state">{t("review.before")}</p>
                <Value name={key} value={before?.[key]} rootKind={kind} />
                <p className="input-state">{t("review.after")}</p>
                <Value name={key} value={after?.[key]} rootKind={kind} />
              </dd>
            </React.Fragment>
          ))}
        </dl>
      ) : <p>{t("review.no_changes")}</p>}
    </section>
  );
}

/* `onApprove` runs the write. It resolves on success and throws on failure, and this component
   only closes on success — SEED's ContentDialog.Action would close on click, which is exactly the
   behaviour an approval gate must not have. */
export function ApprovalDialog({
  event, before, context = [], titleKey = "review.title", introKey = "review.intro",
  beforeKey = "review.before_new", effectKey = "review.effect_career", onApprove, onApproved, onClose,
}) {
  const { t } = useI18n();
  const [busy, setBusy] = React.useState(false);
  const [failure, setFailure] = React.useState(null);

  const approve = async () => {
    setBusy(true);
    setFailure(null);
    try {
      await onApprove();
      onClose();
      if (onApproved) await onApproved();
    } catch (error) {
      setFailure(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ContentDialog.Root open onOpenChange={(open) => { if (!open && !busy) onClose(); }}>
      <ContentDialog.Backdrop />
      <ContentDialog.Positioner>
        <ContentDialog.Content maxWidth="44rem">
          <ContentDialog.Header>
            <ContentDialog.Title>{t(titleKey)}</ContentDialog.Title>
            <ContentDialog.Description>{t(introKey)}</ContentDialog.Description>
          </ContentDialog.Header>
          <ContentDialog.Body maxHeight="60vh" style={{ overflowY: "auto" }}>
            <div className="stack">
              {context.length ? (
                <p className="context-breadcrumb">
                  <strong>{t("review.context_title")}</strong>{" "}
                  <span>{context.join(t("common.breadcrumb_separator"))}</span>
                </p>
              ) : null}

              {before ? <ChangesView before={before} event={event} /> : (
                <section className="before-box record__section">
                  <h3 className="record__section-title">{t("review.before")}</h3>
                  <p>{t(beforeKey)}</p>
                </section>
              )}

              <Divider />
              <SnapshotView event={event} />
              <Divider />

              <Callout.Root tone="informative">
                <Callout.Content>
                  <Callout.Title>{t("review.effect_title")}</Callout.Title>
                  <Callout.Description>{t(effectKey)}</Callout.Description>
                </Callout.Content>
              </Callout.Root>

              <div aria-live="assertive">
                {failure ? <ErrorState error={failure} /> : null}
              </div>
            </div>
          </ContentDialog.Body>
          <ContentDialog.Footer>
            <ActionButton variant="neutralWeak" size="medium" onClick={onClose} disabled={busy}>
              {t("action.keep_editing")}
            </ActionButton>
            <ActionButton variant="brandSolid" size="medium" onClick={approve} disabled={busy}>
              {t("action.approve")}
            </ActionButton>
          </ContentDialog.Footer>
        </ContentDialog.Content>
      </ContentDialog.Positioner>
    </ContentDialog.Root>
  );
}
