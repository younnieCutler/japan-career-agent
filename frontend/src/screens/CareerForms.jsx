/* Creating a context or a project, reviewing one, and reconnecting records that lost their parent.

   Everything here creates a *draft*. Confirmation happens later, through the review dialog, and
   the copy says so ("create draft") rather than "add" — a record that appears the moment you
   press a button is a record nobody attested to.

   The recovery panels matter more than their size suggests. A project whose context was archived,
   or a capture session whose project went away, is unreachable from the index: it belongs to
   nothing, so nothing lists it. Without these panels that work is stranded in the Vault with no
   way back. */

import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { StatusChip } from "../evidence.jsx";
import { ErrorState } from "../components/States.jsx";
import { Block, CheckBox, Choice, Field, Line } from "../components/Fields.jsx";
import { navigate } from "../App.jsx";
import { ApprovalDialog } from "../review.jsx";

const isCanonical = (ref) => String(ref || "").startsWith("canonical:");
const trimmed = (value) => value.trim() || null;

/* A period is omitted entirely when nothing was said about it. Sending `{from: null, to: null}`
   would record "no dates" as an answer rather than as a gap. */
const periodOf = (form) => (
  form.from || form.to || form.current
    ? { from: form.from || null, to: form.to || null, current: form.current }
    : undefined
);

function PeriodFields({ form, onChange }) {
  const { t } = useI18n();
  return (
    <>
      <Field label={t("date.start")} help={t("date.partial_help")}>
        <Line type="month" value={form.from} onChange={(from) => onChange({ from })} />
      </Field>
      {!form.current ? (
        <Field label={t("date.end")} help={t("date.end_help")}>
          <Line type="month" value={form.to} onChange={(to) => onChange({ to })} />
        </Field>
      ) : null}
      <Field label={t("date.current")}>
        <CheckBox
          checked={form.current}
          onChange={(current) => onChange({ current, to: current ? "" : form.to })}
          label={t("date.current")}
        />
      </Field>
    </>
  );
}

/* Relationship and context kind are two questions, not one, and the pairing is constrained: a
   non-work context cannot be a company. Deriving the kind for work relationships keeps the two
   from contradicting each other. */
const WORK_KINDS = {
  employer: "company", freelance: "freelance",
  internship: "internship_organization", part_time: "part_time_workplace",
};

const NON_WORK_KINDS = [
  "personal", "university", "graduate_school", "club", "student_organization",
  "open_source", "volunteer_organization", "other",
];

export function AddContext({ contexts, existing = null, onDone }) {
  const { t } = useI18n();
  const [form, setForm] = React.useState(() => ({
    relationship: existing?.relationship || "employer", kind: existing?.kind || "company",
    label: existing?.label || "", role: existing?.role || "", summary: existing?.summary || "",
    from: existing?.period?.from || "", to: existing?.period?.to || "", current: existing?.period?.current === true,
  }));
  const [detailsOpen, setDetailsOpen] = React.useState(Boolean(existing));
  const [review, setReview] = React.useState(null);
  const [failure, setFailure] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const edit = (patch) => setForm((current) => ({ ...current, ...patch }));
  const nonWork = form.relationship === "non_work";

  const relationships = [
    ["employer", t("enum.context_kind.company")], ["freelance", t("enum.context_kind.freelance")],
    ["internship", t("enum.context_kind.internship_organization")],
    ["part_time", t("enum.context_kind.part_time_workplace")], ["non_work", t("career.non_work")],
  ];

  const submit = async (event) => {
    event.preventDefault();
    const label = form.label.trim();
    if (!label) return;
    const duplicate = contexts.find(
      (item) => item.ref !== existing?.ref
        && String(item.label).trim().toLocaleLowerCase() === label.toLocaleLowerCase());
    if (duplicate && !window.confirm(t("career.duplicate_context_confirm", { label: duplicate.label }))) return;
    setBusy(true);
    try {
      const result = await write("/api/career/contexts", {
        label,
        relationship: nonWork ? "non_work" : "employer",
        context_kind: nonWork ? form.kind : WORK_KINDS[form.relationship],
        role: trimmed(form.role),
        summary: trimmed(form.summary),
        period: periodOf(form),
        ...(existing ? {
          context_id: existing.context_id, case_ref: existing.ref, revision: existing.revision,
        } : {}),
      });
      if (existing) setReview(result);
      else onDone();
    } catch (error) { setFailure(error); }
    finally { setBusy(false); }
  };

  return (
    <>
    <form className="stack" onSubmit={submit}>
      <Field label={t("career.relationship")} help={t("career.relationship_help")}>
        <Choice
          value={form.relationship}
          onChange={(relationship) => edit({
            relationship,
            kind: relationship === "non_work" ? "personal" : WORK_KINDS[relationship],
          })}
          options={relationships}
          label={t("career.relationship")}
        />
      </Field>
      {nonWork ? (
        <Field label={t("career.context_type")}>
          <Choice
            value={form.kind}
            onChange={(kind) => edit({ kind })}
            options={NON_WORK_KINDS.map((kind) => [kind, t(`enum.context_kind.${kind}`)])}
            label={t("career.context_type")}
          />
        </Field>
      ) : null}
      <Field label={t("career.context_name")}>
        <Line value={form.label} onChange={(label) => edit({ label })} />
      </Field>
      {!detailsOpen ? (
        <div>
          <ActionButton type="button" variant="neutralWeak" size="small" onClick={() => setDetailsOpen(true)}>
            {t("action.show_more")}
          </ActionButton>
        </div>
      ) : null}
      {detailsOpen ? (
        <>
          <Field label={t("career.role_optional")}>
            <Line value={form.role} onChange={(role) => edit({ role })} />
          </Field>
          <Field label={t("career.summary_optional")}>
            <Block value={form.summary} onChange={(summary) => edit({ summary })} />
          </Field>
          <PeriodFields form={form} onChange={edit} />
        </>
      ) : null}
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium" disabled={busy}>
          {t(existing ? "action.review_before_confirm" : "action.create_draft")}
        </ActionButton>
      </div>
    </form>
    {review ? <ConfirmRecord
      key={review.proposal.ref}
      item={existing}
      initialReview={review}
      onDone={onDone}
      onClose={() => setReview(null)}
    /> : null}
    </>
  );
}

export function AddProject({ context, existing = null, onDone }) {
  const { t } = useI18n();
  const [form, setForm] = React.useState(() => ({
    label: existing?.label || "", role: existing?.role || "", scope: existing?.scope || "",
    from: existing?.period?.from || "", to: existing?.period?.to || "", current: existing?.period?.current === true,
  }));
  const [detailsOpen, setDetailsOpen] = React.useState(Boolean(existing));
  const [review, setReview] = React.useState(null);
  const [failure, setFailure] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const edit = (patch) => setForm((current) => ({ ...current, ...patch }));

  const submit = async (event) => {
    event.preventDefault();
    const label = form.label.trim();
    if (!label) return;
    const duplicate = (context.projects || []).find(
      (item) => item.ref !== existing?.ref
        && String(item.label).trim().toLocaleLowerCase() === label.toLocaleLowerCase());
    if (duplicate && !window.confirm(t("career.duplicate_project_confirm", { label: duplicate.label }))) return;
    setBusy(true);
    try {
      const result = await write("/api/career/projects", {
        ...(existing ? {
          project_id: existing.project_id, case_ref: existing.ref, revision: existing.revision,
        } : { parent_ref: context.ref }),
        label,
        role: trimmed(form.role),
        scope: trimmed(form.scope),
        period: periodOf(form),
      });
      if (existing) setReview(result);
      else onDone();
    } catch (error) { setFailure(error); }
    finally { setBusy(false); }
  };

  return (
    <>
    <form className="stack" onSubmit={submit}>
      <Field label={t("career.project_name")}>
        <Line value={form.label} onChange={(label) => edit({ label })} />
      </Field>
      {!detailsOpen ? (
        <div>
          <ActionButton type="button" variant="neutralWeak" size="small" onClick={() => setDetailsOpen(true)}>
            {t("action.show_more")}
          </ActionButton>
        </div>
      ) : null}
      {detailsOpen ? (
        <>
          <Field label={t("workflow.role")}>
            <Line value={form.role} onChange={(role) => edit({ role })} />
          </Field>
          <Field label={t("career.project_scope")}>
            <Block value={form.scope} onChange={(scope) => edit({ scope })} />
          </Field>
          <PeriodFields form={form} onChange={edit} />
        </>
      ) : null}
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium" disabled={busy}>
          {t(existing ? "action.review_before_confirm" : "action.create_draft")}
        </ActionButton>
      </div>
    </form>
    {review ? <ConfirmRecord
      key={review.proposal.ref}
      item={existing}
      initialReview={review}
      context={[context.label, existing.label].filter(Boolean)}
      onDone={onDone}
      onClose={() => setReview(null)}
    /> : null}
    </>
  );
}

/* Confirming a drafted context or project: propose, show the user exactly what will be written,
   then approve. The two calls are separate on purpose — the proposal is what the dialog renders,
   so the user approves the server's version rather than the screen's. */
export function ConfirmRecord({ item, context = [], initialReview = null, onDone, onClose }) {
  const { t } = useI18n();
  const [review, setReview] = React.useState(initialReview);
  const [failure, setFailure] = React.useState(null);

  const propose = async () => {
    setFailure(null);
    try {
      setReview(await write("/api/career/propose", { case_ref: item.ref, revision: item.revision }));
    } catch (error) { setFailure(error); }
  };

  return (
    <div className="stack">
      {!initialReview ? <div>
        <ActionButton variant="brandSolid" size="medium" onClick={propose}>
          {t("action.review_before_confirm")}
        </ActionButton>
      </div> : null}
      {failure ? <ErrorState error={failure} /> : null}
      {review ? (
        <ApprovalDialog
          event={review.proposal.event}
          before={review.before}
          context={context}
          effectKey={item.relationship ? "review.effect_context" : "review.effect_project"}
          onApprove={() => write("/api/career/approve", {
            case_ref: item.ref, proposal_ref: review.proposal.ref, revision: review.revision,
          })}
          onApproved={onDone}
          onClose={() => { setReview(null); onClose?.(); }}
        />
      ) : null}
    </div>
  );
}

/* Archive and restore, never delete: work the user stops pursuing still happened. */
export function LifecycleControl({ item, onDone }) {
  const { t } = useI18n();
  const [failure, setFailure] = React.useState(null);
  const state = item.lifecycle || item.status;
  if (!item.ref || state === "approved" || isCanonical(item.ref)) return null;
  const archived = state === "archived";

  const run = async () => {
    if (!window.confirm(t(archived ? "case.restore_confirm" : "case.archive_confirm", { label: item.label }))) return;
    try {
      await write(archived ? "/api/cases/restore" : "/api/cases/archive", {
        case_id: item.ref, updated_at: item.updated_at,
      });
      onDone();
    } catch (error) { setFailure(error); }
  };

  return (
    <div className="stack">
      <div>
        <ActionButton variant="ghost" size="small" onClick={run}>
          {t(archived ? "action.restore" : "action.archive")}
        </ActionButton>
      </div>
      <div aria-live="assertive">{failure ? <ErrorState error={failure} /> : null}</div>
    </div>
  );
}

function Reconnect({ title, choices, emptyKey, confirmKey, confirmValues, actionKey, onConnect }) {
  const { t } = useI18n();
  const [choice, setChoice] = React.useState(choices[0]?.ref || "");
  const [failure, setFailure] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  const run = async () => {
    const target = choices.find((item) => item.ref === choice);
    if (!target) return;
    if (!window.confirm(t(confirmKey, { ...confirmValues, context: target.label, project: target.label }))) return;
    setBusy(true);
    try { await onConnect(target); }
    catch (error) { setFailure(error); }
    finally { setBusy(false); }
  };

  return (
    <article className="recovery-item">
      {title}
      {choices.length ? (
        <>
          <Field label={t("career.correct_context")} help={t("career.correct_context_help")}>
            <Choice
              value={choice}
              onChange={setChoice}
              options={choices.map((item) => [item.ref, item.label])}
              label={t("career.correct_context")}
            />
          </Field>
          <div>
            <ActionButton variant="brandSolid" size="small" onClick={run} disabled={busy}>
              {t(actionKey)}
            </ActionButton>
          </div>
        </>
      ) : <Text textStyle="t3Regular">{t(emptyKey)}</Text>}
      <div aria-live="assertive">{failure ? <ErrorState error={failure} /> : null}</div>
    </article>
  );
}

export function UnassignedProjects({ payload, onDone }) {
  const { t } = useI18n();
  const projects = payload.unassigned_projects || [];
  if (!projects.length) return null;
  const contexts = (payload.contexts || [])
    .filter((item) => item.lifecycle === "approved" && !isCanonical(item.ref))
    .map((item) => ({ ref: item.ref, label: item.label }));

  return (
    <Callout.Root tone="warning">
      <Callout.Content>
        <Callout.Title>{t("career.unassigned_title")}</Callout.Title>
        <Callout.Description>{t("career.unassigned_body")}</Callout.Description>
        {projects.map((project) => (
          <Reconnect
            key={project.ref}
            title={(
              <div className="inline">
                <Text textStyle="t4Bold">{project.label || t("career.project")}</Text>
                <StatusChip state={project.lifecycle} />
              </div>
            )}
            choices={contexts}
            emptyKey="career.confirm_context_first"
            confirmKey="career.connect_project_confirm"
            confirmValues={{ project: project.label || t("career.project") }}
            actionKey="career.connect_project"
            onConnect={async (target) => {
              await write("/api/career/assign-project-context", {
                project_ref: project.ref,
                context_ref: target.ref,
                updated_at: project.updated_at,
              });
              onDone();
            }}
          />
        ))}
      </Callout.Content>
    </Callout.Root>
  );
}

export function UnassignedWork({ payload }) {
  const { t, dateTimeText } = useI18n();
  const sessions = payload.unassigned_work || [];
  if (!sessions.length) return null;
  const projects = (payload.contexts || []).flatMap((context) =>
    (context.projects || [])
      .filter((project) => project.lifecycle === "approved" && !isCanonical(project.ref))
      .map((project) => ({
        ref: project.ref,
        label: [context.label, project.label].join(t("common.breadcrumb_separator")),
      })));

  return (
    <Callout.Root tone="warning">
      <Callout.Content>
        <Callout.Title>{t("career.unassigned_work_title")}</Callout.Title>
        <Callout.Description>{t("career.unassigned_work_body")}</Callout.Description>
        {sessions.map((session) => (
          <Reconnect
            key={session.session_ref || session.session_id}
            title={(
              <div className="inline">
                <Text textStyle="t4Bold">{t(`workflow.type.${session.workflow}`)}</Text>
                <StatusChip state={session.status} />
                <span className="figure">{dateTimeText(session.updated_at)}</span>
              </div>
            )}
            choices={projects}
            emptyKey="career.confirm_project_first"
            confirmKey="career.connect_draft_confirm"
            confirmValues={{}}
            actionKey="career.connect_draft"
            onConnect={async (target) => {
              const assigned = await write("/api/workflows/assign-project", {
                session_ref: session.session_ref,
                case_ref: target.ref,
                revision: session.revision,
              });
              navigate(`/work/${assigned.session.session_ref || assigned.session.session_id}`);
            }}
          />
        ))}
      </Callout.Content>
    </Callout.Root>
  );
}
