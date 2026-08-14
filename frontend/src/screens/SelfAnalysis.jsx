/* Self-analysis, read-only.

   The profile shown here is a reviewed worksheet, not confirmed evidence: it stays labelled as
   needing review until the user takes it through the approval gate in a capture session. That
   distinction is the whole reason this screen does not offer an edit form. */

import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { read, write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { StatusChip } from "../evidence.jsx";
import { ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate } from "../App.jsx";
import { FIELD_LABELS, HIDDEN_REVIEW_FIELDS, Value } from "../review.jsx";

const workflowHref = (session) => `/work/${session.session_ref || session.session_id}`;

const NOTICE = {
  invalid: { tone: "critical", title: "self_analysis.invalid_title", body: "self_analysis.invalid_body" },
  missing: { tone: "warning", title: "self_analysis.empty_title", body: "self_analysis.empty_body" },
};

function ProfileSections({ profile }) {
  const { t } = useI18n();
  const entries = Object.entries(profile || {})
    .filter(([key]) => !HIDDEN_REVIEW_FIELDS.has(key) && FIELD_LABELS.has(key));
  return (
    <div className="stack">
      {entries.map(([key, value]) => (
        <details
          className="record__section"
          key={key}
          open={["candidate_name", "value_candidates", "avoid_candidates"].includes(key)}
        >
          <summary>{t(`field.${key}`)}</summary>
          <div><Value name={key} value={value} rootKind="profile" /></div>
        </details>
      ))}
    </div>
  );
}

export default function SelfAnalysisScreen() {
  const { t, dateTimeText } = useI18n();
  const [reloads, setReloads] = React.useState(0);
  const state = useAsync(
    () => Promise.all([read("/api/self-analysis"), read("/api/sessions")])
      .then(([profile, sessions]) => ({ profile, sessions })),
    [reloads],
  );
  const [failure, setFailure] = React.useState(null);
  const reload = () => setReloads((count) => count + 1);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} onRetry={reload} />;

  const { profile, sessions } = state.data;
  const open = (sessions.sessions || []).filter((item) => item.workflow === "self_analysis");
  const notice = profile.state === "available" ? null : (NOTICE[profile.state] || NOTICE.missing);

  const start = async () => {
    try {
      const started = await write("/api/workflows/start", {
        workflow: "self_analysis",
        subject: { profile_label: t("self_analysis.title") },
      });
      navigate(workflowHref(started.session));
    } catch (error) { setFailure(error); }
  };

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("self_analysis.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("self_analysis.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("self_analysis.intro")}
        </Text>
      </header>

      {failure ? <ErrorState error={failure} onRetry={reload} /> : null}

      {open.length ? (
        <section className="record__section">
          <h3 className="record__section-title">{t("self_analysis.resume_title")}</h3>
          <ul className="lines">
            {open.map((session) => (
              <li className="line" key={session.session_ref || session.session_id}>
                <span className="line__label">{t("self_analysis.title")}</span>
                <StatusChip state={session.status} />
                <span className="figure">{dateTimeText(session.updated_at)}</span>
                <ActionButton
                  variant="neutralOutline"
                  size="xsmall"
                  onClick={() => navigate(workflowHref(session))}
                >
                  {t(session.status === "review_pending" ? "action.review" : "action.continue")}
                </ActionButton>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {notice ? (
        <Callout.Root tone={notice.tone}>
          <Callout.Content>
            <Callout.Title>{t(notice.title)}</Callout.Title>
            <Callout.Description>{t(notice.body)}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : (
        <section className="record__section">
          <div className="inline">
            <h3 className="record__section-title">{t("self_analysis.reviewed_profile_title")}</h3>
            <span className="input-state">{t("input.needs_review")}</span>
          </div>
          <ProfileSections profile={profile.profile} />
        </section>
      )}

      <div>
        <ActionButton variant="brandSolid" size="medium" onClick={start}>
          {t(open.length ? "action.start_another" : "action.start_new")}
        </ActionButton>
      </div>
    </div>
  );
}
