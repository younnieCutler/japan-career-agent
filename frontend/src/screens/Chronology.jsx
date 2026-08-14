/* The two career subviews that are lists rather than records.

   Timeline is the record read in date order — the same evidence the career index holds, sorted by
   when it happened rather than by who it belongs to. In-progress is the opposite: unfinished
   capture sessions, which are not evidence at all yet, kept on their own screen so a draft can
   never be mistaken for a record. */

import React from "react";
import { ActionButton, Text, TextField } from "@seed-design/react";
import { read, write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { StatusChip } from "../evidence.jsx";
import { EmptyState, ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate } from "../App.jsx";
import { Choice } from "../components/Fields.jsx";

const PAGE_SIZE = 30;
const workflowHref = (session) => `/work/${session.session_ref || session.session_id}`;

function Tabs({ current }) {
  const { t } = useI18n();
  const items = [
    ["/career", "career.overview"], ["/career/in-progress", "nav.in_progress"],
    ["/career/timeline", "nav.timeline"],
  ];
  return (
    <nav className="subnav inline" aria-label={t("a11y.career_views")}>
      {items.map(([path, key]) => (
        <ActionButton
          key={path}
          variant={path === current ? "neutralWeak" : "ghost"}
          size="small"
          aria-current={path === current ? "page" : undefined}
          onClick={() => navigate(path)}
        >
          {t(key)}
        </ActionButton>
      ))}
    </nav>
  );
}

export function TimelineScreen() {
  const { t, periodText } = useI18n();
  const state = useAsync(() => read("/api/timeline"), []);
  const [query, setQuery] = React.useState("");
  const [shown, setShown] = React.useState(PAGE_SIZE);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} />;

  const rows = (state.data.sections || []).filter((item) => !query
    || `${item.label || ""} ${periodText(item.period)}`
      .toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("timeline.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("timeline.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("timeline.intro")}
        </Text>
      </header>
      <Tabs current="/career/timeline" />

      <div className="toolbar">
        <TextField.Root size="medium">
          <TextField.Input
            placeholder={t("search.timeline_placeholder")}
            aria-label={t("search.timeline_placeholder")}
            value={query}
            onChange={(event) => { setQuery(event.target.value); setShown(PAGE_SIZE); }}
          />
        </TextField.Root>
      </div>
      <p className="result-count" aria-live="polite">
        {t("search.result_count", { shown: Math.min(rows.length, shown), total: rows.length })}
      </p>

      {rows.length ? (
        <>
          <ol className="chronology">
            {rows.slice(0, shown).map((item, index) => (
              <li className="chronology__row" key={`${item.kind}-${item.label}-${index}`}>
                <span className="figure chronology__when">{periodText(item.period)}</span>
                <span className="line__tag">{t(`timeline.kind.${item.kind}`)}</span>
                <span className="line__label">
                  {item.contains_confidential
                    ? t("career.confidential_experience") : (item.label || t("common.unknown"))}
                </span>
              </li>
            ))}
          </ol>
          {rows.length > shown ? (
            <div>
              <ActionButton variant="neutralWeak" size="small" onClick={() => setShown(shown + PAGE_SIZE)}>
                {t("action.show_more")}
              </ActionButton>
            </div>
          ) : null}
        </>
      ) : (
        <EmptyState
          titleKey={query ? "search.no_results" : "timeline.empty_title"}
          bodyKey={query ? "search.adjust" : "timeline.empty_body"}
        />
      )}
    </div>
  );
}

export function InProgressScreen() {
  const { t, dateTimeText } = useI18n();
  const [reloads, setReloads] = React.useState(0);
  const state = useAsync(() => read("/api/sessions?include_archived=1"), [reloads]);
  const [query, setQuery] = React.useState("");
  const [status, setStatus] = React.useState("all");
  const [shown, setShown] = React.useState(PAGE_SIZE);
  const [failure, setFailure] = React.useState(null);
  const reload = () => setReloads((count) => count + 1);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} onRetry={reload} />;

  const contextOf = (session) => (session.context || session.display_context || [])
    .join(t("common.breadcrumb_separator")) || t(`workflow.type.${session.workflow}`);

  const rows = (state.data.sessions || []).filter((session) => (
    (!query || contextOf(session).toLocaleLowerCase().includes(query.toLocaleLowerCase()))
    && (status === "all" || session.status === status)
  ));

  const choices = [
    ["all", t("filter.all")], ["draft", t("status.draft")],
    ["review_pending", t("status.review_pending")], ["archived", t("status.archived")],
  ];

  const lifecycle = async (session) => {
    const archived = session.status === "archived";
    if (!window.confirm(t(archived ? "work.restore_confirm" : "work.archive_confirm"))) return;
    try {
      await write(`/api/workflows/${archived ? "restore" : "archive"}`, {
        session_ref: session.session_ref, revision: session.revision,
      });
      reload();
    } catch (error) { setFailure(error); }
  };

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("work.in_progress_eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("work.in_progress_title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("work.in_progress_intro")}
        </Text>
      </header>
      <Tabs current="/career/in-progress" />

      {failure ? <ErrorState error={failure} onRetry={reload} /> : null}

      <div className="toolbar">
        <TextField.Root size="medium">
          <TextField.Input
            placeholder={t("search.work_placeholder")}
            aria-label={t("search.work_placeholder")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </TextField.Root>
        <Choice value={status} onChange={setStatus} options={choices} label={t("filter.all")} />
      </div>

      {rows.length ? (
        <ul className="lines">
          {rows.slice(0, shown).map((session) => (
            <li className="line" key={session.session_ref || session.session_id}>
              <span className="line__label">{contextOf(session)}</span>
              <StatusChip state={session.status} />
              <span className="figure">{dateTimeText(session.updated_at)}</span>
              {session.status !== "archived" ? (
                <ActionButton
                  variant="neutralOutline"
                  size="xsmall"
                  onClick={() => navigate(workflowHref(session))}
                >
                  {t(session.status === "review_pending" ? "action.review" : "action.continue")}
                </ActionButton>
              ) : null}
              <ActionButton variant="ghost" size="xsmall" onClick={() => lifecycle(session)}>
                {t(session.status === "archived" ? "action.restore" : "action.archive")}
              </ActionButton>
            </li>
          ))}
          {rows.length > shown ? (
            <li>
              <ActionButton variant="neutralWeak" size="small" onClick={() => setShown(shown + PAGE_SIZE)}>
                {t("action.show_more")}
              </ActionButton>
            </li>
          ) : null}
        </ul>
      ) : (
        <EmptyState
          titleKey={query || status !== "all" ? "search.no_results" : "work.none_title"}
          bodyKey={query || status !== "all" ? "search.adjust" : "work.none_body"}
          action={(
            <ActionButton variant="brandSolid" size="medium" onClick={() => navigate("/career")}>
              {t("career.add_experience")}
            </ActionButton>
          )}
        />
      )}
    </div>
  );
}
