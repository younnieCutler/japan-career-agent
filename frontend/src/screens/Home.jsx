/* Home answers "what do I do next", not "how am I doing".

   It reads `/api/home`, which is the runtime's own view of where the record stands — it already
   counts conflicts and pending approvals, so nothing here recomputes them. Record counts live on
   the career overview, where they describe that screen's own contents; repeated here they were a
   metrics row on a screen whose job is the next action. */

import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { read } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { StatusChip } from "../evidence.jsx";
import { ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate } from "../App.jsx";

const workflowHref = (session) => `/work/${session.session_ref || session.session_id}`;

function SessionCard({ session }) {
  const { t, dateTimeText, enumText } = useI18n();
  const context = (session.context || session.display_context || []);
  const title = context.length
    ? context.join(t("common.breadcrumb_separator"))
    : t(`workflow.type.${session.workflow}`);
  return (
    <li className="line">
      <span className="line__label">{title}</span>
      <StatusChip state={session.status || session.lifecycle} />
      <span className="figure">{dateTimeText(session.updated_at)}</span>
      <ActionButton variant="neutralOutline" size="xsmall" onClick={() => navigate(workflowHref(session))}>
        {t(session.status === "review_pending" ? "action.review" : "action.continue")}
      </ActionButton>
      {session.last_entrypoint && session.last_entrypoint !== "unknown" ? (
        <span className="line__tag">
          {t("workflow.last_entrypoint", { entrypoint: enumText("entrypoint", session.last_entrypoint) })}
        </span>
      ) : null}
    </li>
  );
}

/* States the runtime already counted, listed rather than summed.

   A single "readiness" number would be the one thing this product refuses to produce: these are
   different questions, and averaging them tells the user nothing they can act on. Each row is a
   count and a destination — the point is to reach the list, not to read the figure. */
function Attention({ rows }) {
  const { t } = useI18n();
  const visible = rows.filter((row) => row.count > 0);
  if (!visible.length) return null;
  return (
    <section className="record__section">
      <h3 className="record__section-title">{t("home.attention_title")}</h3>
      <ul className="lines">
        {visible.map((row) => (
          <li className="line" key={row.key}>
            <span className="figure">{row.count}</span>
            <span className="line__label">{t(row.key)}</span>
            <ActionButton variant="neutralOutline" size="xsmall" onClick={() => navigate(row.target)}>
              {t("action.review")}
            </ActionButton>
          </li>
        ))}
      </ul>
      <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
        {t("home.attention_help")}
      </Text>
    </section>
  );
}

function Queue({ titleKey, items }) {
  const { t } = useI18n();
  if (!items.length) return null;
  return (
    <section className="record__section">
      <div className="inline">
        <h3 className="record__section-title">{t(titleKey)}</h3>
        <span className="figure">{items.length}</span>
        <ActionButton variant="ghost" size="xsmall" onClick={() => navigate("/career")}>
          {t("action.manage")}
        </ActionButton>
      </div>
      <ul className="lines">
        {items.slice(0, 4).map((session) => (
          <SessionCard key={session.session_ref || session.session_id} session={session} />
        ))}
      </ul>
    </section>
  );
}

export default function HomeScreen() {
  const { t } = useI18n();
  const state = useAsync(
    () => Promise.all([read("/api/home"), read("/api/sessions")]).then(([home, sessions]) => ({ home, sessions })),
    [],
  );

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} />;

  const { home, sessions } = state.data;
  const rows = sessions.sessions || [];
  const review = rows.filter((item) => item.status === "review_pending");
  const draft = rows.filter((item) => item.status === "draft");

  const next = review.length
    ? { eyebrow: "home.review_title", action: "action.review", target: workflowHref(review[0]), session: review[0] }
    : draft.length
      ? { eyebrow: "home.resume_title", action: "action.continue", target: workflowHref(draft[0]), session: draft[0] }
      : home.readiness?.bootstrap_suggested
        ? { eyebrow: "home.first_step", action: "career.add_context", target: "/career", title: t("home.empty_title") }
        : { eyebrow: "home.next_step", action: "career.add_experience", target: "/career", title: t("home.add_experience_title") };

  const nextTitle = next.title || (next.session.context || next.session.display_context || [])
    .join(t("common.breadcrumb_separator")) || t(`workflow.type.${next.session.workflow}`);

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("home.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("home.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("home.intro")}
        </Text>
      </header>

      <section
        className="record__section"
        style={{
          padding: "var(--seed-dimension-x5)",
          borderLeft: "3px solid var(--seed-color-bg-brand-solid)",
          background: "var(--seed-color-bg-layer-default)",
          border: "1px solid var(--seed-color-stroke-neutral-muted)",
        }}
      >
        <h3 className="record__section-title">{t(next.eyebrow)}</h3>
        <Text textStyle="t6Bold">{nextTitle}</Text>
        <div>
          <ActionButton variant="brandSolid" size="medium" onClick={() => navigate(next.target)}>
            {t(next.action)}
          </ActionButton>
        </div>
      </section>

      {/* An unresolved contradiction outranks any queue. The count is the runtime's. */}
      {(home.conflicts?.count || 0) > 0 ? (
        <Callout.Root tone="critical">
          <Callout.Content>
            <Callout.Title>{t("career.context_conflict_title")}</Callout.Title>
            <Callout.Description>{t("career.context_conflict_body")}</Callout.Description>
            <Callout.Link onClick={() => navigate("/career")}>{t("action.view_all")}</Callout.Link>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      {/* Conflicts keep the callout above rather than a row here: a contradiction is not one more
          item in a queue, and demoting it into this list would be a downgrade. */}
      <Attention
        rows={[
          {
            key: "home.attention_pending",
            count: home.pending_approval?.count || 0,
            target: "/career",
          },
          {
            key: "home.attention_unknown",
            count: (home.unknown?.dimensions || []).length,
            target: "/diagnosis",
          },
        ]}
      />

      <Queue titleKey="home.review_title" items={review} />
      <Queue titleKey="home.resume_title" items={draft} />
    </div>
  );
}
