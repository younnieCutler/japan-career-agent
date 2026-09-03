/* Career records: a dense index you scan, a record you read.

   The hierarchy is still the Vault's — context, project, experience — but it is shown as indented
   rows rather than nested disclosure widgets, so no record hides another. See UI-SPEC.md. */

import React from "react";
import { ActionButton, Callout, Divider, Text, TextField } from "@seed-design/react";
import { read, write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { ConflictChip, StatusChip, toneOf } from "../evidence.jsx";
import { EmptyState, ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate, setSelection, useLocation } from "../App.jsx";
import { Block, Choice, Field } from "../components/Fields.jsx";
import {
  AddContext, AddProject, ConfirmRecord, LifecycleControl, UnassignedProjects, UnassignedWork,
} from "./CareerForms.jsx";
import CareerBatch from "./CareerBatch.jsx";

const PAGE_SIZE = 25;
const isCanonical = (ref) => String(ref || "").startsWith("canonical:");

/* One flat index built from the nested payload. Depth is presentational only. */
function indexRows(payload, labels) {
  const rows = [];
  for (const context of payload.contexts || []) {
    const conflicted = (context.projects || []).some((p) => p.relationship_conflict);
    rows.push({ kind: "context", depth: 0, ref: context.ref, label: context.label, node: context, conflicted });
    for (const project of context.projects || []) {
      rows.push({
        kind: "project", depth: 1, ref: project.ref, label: project.label || labels.project,
        node: project, parent: context, conflicted: Boolean(project.relationship_conflict),
      });
      for (const experience of project.experiences || []) {
        rows.push({
          kind: "experience", depth: 2, ref: experience.experience_ref || experience.ref,
          label: experienceLabel(experience, labels), node: experience, parent: project, grandparent: context,
        });
      }
    }
    for (const experience of context.other_experiences || []) {
      rows.push({
        kind: "experience", depth: 1, ref: experience.experience_ref || experience.ref,
        label: experienceLabel(experience, labels), node: experience, grandparent: context,
      });
    }
  }
  return rows;
}

const experienceLabel = (experience, labels) => (
  experience.contains_confidential ? labels.confidential : (experience.label || labels.experience)
);

const rowState = (row) => (row.kind === "experience" ? "approved" : row.node.lifecycle);

function IndexRow({ row, meta, selected, onSelect }) {
  return (
    <button
      type="button"
      className="row"
      data-depth={row.depth}
      data-tone={toneOf(rowState(row))}
      data-conflict={row.conflicted ? "true" : undefined}
      data-selected={selected ? "true" : undefined}
      aria-current={selected ? "true" : "false"}
      onClick={onSelect}
    >
      <span className="row__label">{row.label}</span>
      <span className="row__chips">
        <StatusChip state={rowState(row)} />
        {row.conflicted ? <ConflictChip /> : null}
      </span>
      <span className="row__meta">{meta}</span>
    </button>
  );
}

/* Every experience recorded against this company, whichever project it sits under, plus the ones
   the Vault holds directly against the context. The project becomes a trailing label rather than
   a level the user has to walk through. */
function companyExperiences(context) {
  const fromProjects = (context.projects || []).flatMap((project) =>
    (project.experiences || []).map((experience) => ({ experience, project })));
  const direct = (context.other_experiences || []).map((experience) => ({ experience, project: null }));
  return [...fromProjects, ...direct];
}

function Facts({ rows }) {
  const visible = rows.filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!visible.length) return null;
  return (
    <dl className="facts">
      {visible.map(([label, value]) => (
        <React.Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function ExperienceLines({ items, labels }) {
  const { t } = useI18n();
  if (!items.length) return <Text textStyle="t3Regular">{t("career.no_experience_project")}</Text>;
  return (
    <ul className="lines">
      {items.map(({ experience, project }, index) => (
        <li className="line" key={experience.experience_ref || experience.ref || index}>
          <span className="line__label">{experienceLabel(experience, labels)}</span>
          <StatusChip state="approved" />
          {experience.work_date ? <span className="figure">{experience.work_date}</span> : null}
          {project ? <span className="line__tag">{project.label || labels.project}</span> : null}
        </li>
      ))}
    </ul>
  );
}

/* Existing material is useful before the user has recreated our hierarchy. Keep the pasted text
   as an unassigned workflow draft; nothing is inferred or written to the canonical ledger. */
function ExistingHistoryCapture({ onError }) {
  const { t } = useI18n();
  const [body, setBody] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const text = body.trim();
    if (!text) return;
    setBusy(true);
    try {
      const started = await write("/api/workflows/start", { workflow: "career_inventory" });
      const sessionRef = started.session.session_ref || started.session.session_id;
      const saved = await write("/api/workflows/draft", {
        session_ref: sessionRef,
        revision: started.revision ?? started.session.revision ?? 0,
        draft: { evidence: [text] },
      });
      navigate(`/work/${saved.session?.session_ref || sessionRef}`);
    } catch (error) { onError(error); }
    finally { setBusy(false); }
  };

  return (
    <section className="record__section next-action">
      <h3 className="record__section-title">{t("workflow.type.career_inventory")}</h3>
      <Text textStyle="t4Regular">{t("home.empty_title")}</Text>
      <form className="stack" onSubmit={submit}>
        <Field label={t("applications.document_body")}>
          <Block value={body} onChange={setBody} rows={8} />
        </Field>
        <div>
          <ActionButton type="submit" variant="brandSolid" size="medium" disabled={busy || !body.trim()}>
            {t("action.continue")}
          </ActionButton>
        </div>
      </form>
    </section>
  );
}

/* Starting capture must not require the user to model a project first. When a confirmed project is
   available we keep using it; otherwise the existing unassigned-work path holds the draft until the
   user connects the right location before approval. No project is invented on the user's behalf. */
function AddExperience({ context, onError }) {
  const { t } = useI18n();
  const usable = (context.projects || []).filter(
    (p) => p.lifecycle === "approved" && !isCanonical(p.ref));
  const [choice, setChoice] = React.useState(usable[0]?.ref || "");
  const [choosing, setChoosing] = React.useState(false);

  const launch = async (ref = null) => {
    const project = ref ? usable.find((p) => p.ref === ref) : null;
    if (project && (project.work || []).length && !window.confirm(t("career.new_experience_confirm"))) return;
    try {
      const started = await write("/api/workflows/start", {
        workflow: "career_inventory",
        ...(project ? { case_ref: project.ref } : {}),
      });
      navigate(`/work/${started.session.session_ref || started.session.session_id}`);
    } catch (error) { onError(error); }
  };

  if (usable.length > 1 && choosing) {
    return (
      <div className="stack">
        <Choice
          value={choice}
          onChange={setChoice}
          options={usable.map((p) => [p.ref, p.label])}
          label={t("career.correct_project")}
        />
        <div><ActionButton variant="brandSolid" size="medium" onClick={() => launch(choice)}>
          {t("career.add_experience")}
        </ActionButton></div>
      </div>
    );
  }
  return (
    <div>
      <ActionButton
        variant="brandSolid"
        size="medium"
        onClick={() => (usable.length > 1 ? setChoosing(true) : launch(usable[0]?.ref || null))}
      >
        {t("career.add_experience")}
      </ActionButton>
    </div>
  );
}

function ContextRecord({ context, labels, onSelect, onError, onReload }) {
  const { t, periodText } = useI18n();
  const conflicted = (context.projects || []).some((p) => p.relationship_conflict);
  const experiences = companyExperiences(context);
  return (
    <div className="record">
      <div className="record__head">
        <Text textStyle="t7Bold">{context.label}</Text>
        <StatusChip state={context.lifecycle} />
        {conflicted ? <ConflictChip /> : null}
      </div>
      <span className="figure">{periodText(context.period)}</span>

      {conflicted ? (
        <Callout.Root tone="critical">
          <Callout.Content>
            <Callout.Title>{t("career.context_conflict_title")}</Callout.Title>
            <Callout.Description>{t("career.context_conflict_body")}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      <Facts rows={[
        [t("workflow.role"), context.role],
        [t("career.summary_optional"), context.summary],
      ]} />

      {context.lifecycle === "approved" ? (
        <details className="record__section">
          <summary>{t("action.edit")}</summary>
          <AddContext key={context.ref} contexts={[context]} existing={context} onDone={onReload} />
        </details>
      ) : null}

      <Divider />
      <section className="record__section">
        <h3 className="record__section-title">{t("career.project_count")}</h3>
        {(context.projects || []).length ? (
          <ul className="lines">
            {context.projects.map((project) => (
              <li className="line" key={project.ref}>
                <button
                  type="button"
                  className="line__label"
                  style={{
                    border: 0, background: "transparent", cursor: "pointer", font: "inherit",
                    color: "var(--seed-color-fg-brand)", textAlign: "left", padding: 0,
                  }}
                  onClick={() => onSelect(project.ref)}
                >
                  {project.label || labels.project}
                </button>
                <StatusChip state={project.lifecycle} />
                <span className="figure">{periodText(project.period)}</span>
              </li>
            ))}
          </ul>
        ) : <Text textStyle="t3Regular">{t("career.no_projects_next")}</Text>}
        {context.lifecycle === "approved" && !isCanonical(context.ref) ? (
          <details>
            <summary>{t("career.add_project")}</summary>
            <AddProject context={context} onDone={onReload} />
          </details>
        ) : null}
      </section>

      <section className="record__section">
        <h3 className="record__section-title">{t("career.experience_count")}</h3>
        <ExperienceLines items={experiences} labels={labels} />
        {context.lifecycle === "approved" && !isCanonical(context.ref)
          ? <AddExperience context={context} onError={onError} />
          : null}
      </section>

      {context.lifecycle !== "approved" && !isCanonical(context.ref) ? (
        <ConfirmRecord item={context} context={[context.label]} onDone={onReload} />
      ) : null}
      <LifecycleControl item={context} onDone={onReload} />
    </div>
  );
}

function ProjectRecord({ row, labels, onReload }) {
  const { t, periodText } = useI18n();
  const project = row.node;
  return (
    <div className="record">
      <div className="record__head">
        <Text textStyle="t7Bold">{project.label || labels.project}</Text>
        <StatusChip state={project.lifecycle} />
        {project.relationship_conflict ? <ConflictChip /> : null}
      </div>
      <span className="figure">{periodText(project.period)}</span>
      <Facts rows={[
        [t("career.context_name"), row.parent?.label],
        [t("workflow.role"), project.role],
        [t("career.project_scope"), project.scope],
      ]} />
      {project.lifecycle === "approved" ? (
        <details className="record__section">
          <summary>{t("action.edit")}</summary>
          <AddProject key={project.ref} context={row.parent} existing={project} onDone={onReload} />
        </details>
      ) : null}
      <Divider />
      <section className="record__section">
        <h3 className="record__section-title">{t("career.experience_count")}</h3>
        <ExperienceLines
          items={(project.experiences || []).map((experience) => ({ experience, project: null }))}
          labels={labels}
        />
      </section>

      {project.lifecycle !== "approved" && !isCanonical(project.ref) ? (
        <ConfirmRecord
          item={project}
          context={[row.parent?.label, project.label].filter(Boolean)}
          onDone={onReload}
        />
      ) : null}
      <LifecycleControl item={project} onDone={onReload} />
    </div>
  );
}

export function ExperienceRevisionControl({ experience, onError }) {
  const { t } = useI18n();
  const revise = async () => {
    try {
      const started = await write("/api/career/experiences/revise", {
        event_id: experience.ref, revision: experience.ref,
      });
      navigate(`/work/${started.session.session_ref}`);
    } catch (error) { onError(error); }
  };
  return <ActionButton variant="neutralWeak" size="small" onClick={revise}>{t("action.edit")}</ActionButton>;
}

function ExperienceRecord({ row, labels, onError }) {
  const { t } = useI18n();
  const experience = row.node;
  return (
    <div className="record">
      <div className="record__head">
        <Text textStyle="t7Bold">{experienceLabel(experience, labels)}</Text>
        <StatusChip state="approved" />
      </div>
      {experience.work_date ? <span className="figure">{experience.work_date}</span> : null}
      <Facts rows={[
        [t("career.context_name"), row.grandparent?.label],
        [t("career.project"), row.parent?.label],
        [t("review.evidence_title"), experience.evidence_state === "present"
          ? t("evidence.present_count", { count: experience.evidence_count })
          : t("evidence.missing_usable")],
      ]} />
      <div className="inline"><ExperienceRevisionControl experience={experience} onError={onError} /></div>
      {experience.contains_confidential ? (
        <Callout.Root tone="warning">
          <Callout.Content>
            <Callout.Description>
              {t(experience.external_use === "allowed" ? "confidentiality.hidden_allowed"
                : experience.external_use === "blocked" ? "confidentiality.hidden_blocked"
                  : "confidentiality.hidden_review")}
            </Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}
    </div>
  );
}

export default function CareerScreen() {
  const { t, periodText } = useI18n();
  const [reloads, setReloads] = React.useState(0);
  const state = useAsync(() => read("/api/career"), [reloads]);
  const reload = () => setReloads((count) => count + 1);
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  const selected = params.get("sel");
  const capture = params.get("capture") === "1";
  const [query, setQuery] = React.useState("");
  const [status, setStatus] = React.useState("all");
  const [shown, setShown] = React.useState(PAGE_SIZE);
  const [failure, setFailure] = React.useState(null);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} />;

  const labels = {
    project: t("career.project"),
    experience: t("career.experience"),
    confidential: t("career.confidential_experience"),
  };
  const rows = indexRows(state.data, labels);
  const metaOf = (row) => (row.kind === "experience" ? (row.node.work_date || "") : periodText(row.node.period));
  const matches = rows.filter((row) => {
    const haystack = [row.label, row.node.role, row.node.scope, row.node.summary, row.parent?.label, row.grandparent?.label]
      .filter(Boolean).join(" ").toLocaleLowerCase();
    return (!query || haystack.includes(query.toLocaleLowerCase()))
      && (status === "all" || rowState(row) === status);
  });
  const current = rows.find((row) => row.ref === selected);

  const statusChoices = [
    ["all", t("filter.all")], ["draft", t("status.draft")],
    ["review_pending", t("status.review_pending")], ["approved", t("status.approved")],
  ];

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("career.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("career.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("career.intro")}
        </Text>
      </header>

      {(state.data.relationship_conflicts || []).length ? (
        <Callout.Root tone="critical">
          <Callout.Content>
            <Callout.Title>{t("career.context_conflict_title")}</Callout.Title>
            <Callout.Description>{t("career.context_conflict_body")}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      {failure ? <ErrorState error={failure} onRetry={() => setFailure(null)} /> : null}

      <UnassignedProjects payload={state.data} onDone={reload} />
      <UnassignedWork payload={state.data} />
      <CareerBatch payload={state.data} onDone={reload} />

      {capture || !rows.length ? <ExistingHistoryCapture onError={setFailure} /> : null}

      <details className="record__section">
        <summary>{t("career.add_context")}</summary>
        <AddContext contexts={state.data.contexts || []} onDone={reload} />
      </details>

      <div className="split" data-record-open={current ? "true" : undefined}>
        <div className="split__index">
          <div className="toolbar">
            <TextField.Root size="medium">
              <TextField.Input
                placeholder={t("search.career_placeholder")}
                aria-label={t("search.career_placeholder")}
                value={query}
                onChange={(event) => { setQuery(event.target.value); setShown(PAGE_SIZE); }}
              />
            </TextField.Root>
            <Choice
              value={status}
              onChange={(next) => { setStatus(next); setShown(PAGE_SIZE); }}
              options={statusChoices}
              label={t("filter.all")}
            />
          </div>
          <p className="result-count" aria-live="polite">
            {t("search.result_count", { shown: Math.min(matches.length, shown), total: matches.length })}
          </p>
          {matches.length ? (
            <div>
              {matches.slice(0, shown).map((row) => (
                <IndexRow
                  key={row.ref}
                  row={row}
                  meta={metaOf(row)}
                  selected={row.ref === selected}
                  onSelect={() => setSelection(row.ref)}
                />
              ))}
              {matches.length > shown ? (
                <ActionButton variant="neutralWeak" size="small" onClick={() => setShown(shown + PAGE_SIZE)}>
                  {t("action.show_more")}
                </ActionButton>
              ) : null}
            </div>
          ) : (
            <EmptyState
              titleKey={query || status !== "all" ? "search.no_results" : "career.empty_title"}
              bodyKey={query || status !== "all" ? "search.adjust" : "career.empty_body"}
            />
          )}
        </div>

        <div className="split__record" aria-live="polite">
          <ActionButton
            className="back-to-index"
            variant="ghost"
            size="small"
            onClick={() => setSelection(null)}
          >
            {t("career.overview")}
          </ActionButton>
          {current ? (
            current.kind === "context"
              ? (
                <ContextRecord
                  context={current.node}
                  labels={labels}
                  onSelect={setSelection}
                  onError={setFailure}
                  onReload={reload}
                />
              )
              : current.kind === "project"
                ? <ProjectRecord row={current} labels={labels} onReload={reload} />
                : <ExperienceRecord row={current} labels={labels} onError={setFailure} />
          ) : (
            <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
              {t("career.intro")}
            </Text>
          )}
        </div>
      </div>
    </div>
  );
}
