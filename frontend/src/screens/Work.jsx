/* 棚卸し capture — the one screen that writes.

   A capture session is a draft, not a record. Everything here says so: the lifecycle strip, the
   save state, and the fact that the only way out of draft is the review dialog. The autosave
   contract is carried over unchanged, including the parts that look fussy:

   - A save in flight is awaited rather than raced, so two keystrokes cannot write out of order.
   - `editVersion` is checked after the write returns: if the user typed while it was in flight,
     the state stays "saving" rather than claiming saved work that is already behind.
   - `REVISION_STALE` offers reload, never retry. Retrying a stale write is how one browser tab
     silently overwrites another.
   - Leaving with a failed save asks first. Losing typed work quietly is the failure mode a
     local-first product cannot afford. */

import React from "react";
import { ActionButton, Callout, Divider, Text } from "@seed-design/react";
import { read, write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { StatusChip } from "../evidence.jsx";
import { ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate, setLeaveGuard } from "../App.jsx";
import { ApprovalDialog, FIELD_LABELS, HIDDEN_REVIEW_FIELDS, Value } from "../review.jsx";
import { Block, CheckBox, Choice, Field, Line } from "../components/Fields.jsx";

const splitLines = (value) => String(value || "")
  .split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

const SAVE_DEBOUNCE_MS = 650;

function Breadcrumb({ session }) {
  const { t } = useI18n();
  const parts = session.subject || {};
  const labels = [parts.context_label, parts.project_label,
    parts.experience_label || t("workflow.new_experience")].filter(Boolean);
  return (
    <nav className="context-breadcrumb" aria-label={t("a11y.current_context")}>
      {labels.map((label, index) => (
        <React.Fragment key={index}>
          {index ? <span aria-hidden="true"> {t("common.breadcrumb_separator")} </span> : null}
          <span>{label}</span>
        </React.Fragment>
      ))}
    </nav>
  );
}

const EMPTY = {
  summary: "", work_date: "", role: "", scope: "", problem: "", direct_actions: "",
  individual_contribution: "", outcome_state: "unknown", team_result: "", metrics: "",
  evidence: "", contains_confidential: false, external_use: "unknown",
};

const fromDraft = (draft = {}) => ({
  ...EMPTY,
  summary: draft.summary || "",
  work_date: draft.work_date || "",
  role: draft.role || "",
  scope: draft.scope || "",
  problem: draft.problem || "",
  direct_actions: (draft.direct_actions || []).join("\n"),
  individual_contribution: draft.individual_contribution || "",
  outcome_state: draft.outcome_state || "unknown",
  team_result: draft.team_result || "",
  metrics: (draft.metrics || []).join("\n"),
  evidence: (draft.evidence || []).join("\n"),
  contains_confidential: Boolean(draft.confidentiality?.contains_confidential),
  external_use: draft.confidentiality?.external_use || "unknown",
});

/* Only fields the user actually filled are sent. An empty string written into the Vault is a
   claim that the answer is empty; omitting the key leaves it unanswered, which is the truth. */
function serialize(form) {
  const measured = ["qualitative", "quantitative"].includes(form.outcome_state);
  const value = {
    summary: form.summary.trim(),
    outcome_state: form.outcome_state,
    evidence: splitLines(form.evidence),
    confidentiality: {
      contains_confidential: form.contains_confidential,
      external_use: form.external_use,
    },
  };
  const text = {
    work_date: form.work_date,
    role: form.role.trim(),
    scope: form.scope.trim(),
    problem: form.problem.trim(),
    individual_contribution: form.individual_contribution.trim(),
    team_result: measured ? form.team_result.trim() : "",
  };
  for (const [key, item] of Object.entries(text)) if (item) value[key] = item;
  const direct = splitLines(form.direct_actions);
  if (direct.length) value.direct_actions = direct;
  const metrics = splitLines(form.metrics);
  if (form.outcome_state === "quantitative" && metrics.length) value.metrics = metrics;
  return value;
}

/* What is entered so far, in the same shape and vocabulary the approval dialog will use. Shown
   beside the form so the review holds no surprises — not a completeness score, which would turn
   an evidence record into a game. */
function LivePreview({ form }) {
  const { t } = useI18n();
  const payload = serialize(form);
  const entries = Object.entries(payload).filter(
    ([key]) => !HIDDEN_REVIEW_FIELDS.has(key) && FIELD_LABELS.has(key));
  return (
    <aside className="record">
      <h3 className="record__section-title">{t("review.after")}</h3>
      <dl className="facts">
        {entries.map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{t(`field.${key}`)}</dt>
            <dd><Value name={key} value={value} rootKind="experience" /></dd>
          </React.Fragment>
        ))}
      </dl>
    </aside>
  );
}

function CaptureForm({ payload, onReload }) {
  const { t } = useI18n();
  const session = payload.session;
  const [form, setForm] = React.useState(() => fromDraft(payload.draft));
  const [saveState, setSaveState] = React.useState(null);
  const [failure, setFailure] = React.useState(null);
  const [review, setReview] = React.useState(null);
  const [done, setDone] = React.useState(false);

  // Mutable so the debounce timer and the leave guard read the live values rather than the ones
  // captured when they were created.
  const box = React.useRef({
    revision: payload.revision, dirty: false, saving: null, saveFailed: false, editVersion: 0,
    form, timer: null,
  });
  box.current.form = form;

  const doSave = React.useCallback(async function save() {
    const state = box.current;
    if (state.saving) {
      const previous = await state.saving;
      if (!previous) return false;
      return state.dirty ? save() : true;
    }
    if (!state.dirty) return true;
    const version = state.editVersion;
    setSaveState("status.saving");
    state.saveFailed = false;
    const task = (async () => {
      try {
        const saved = await write("/api/workflows/draft", {
          session_ref: session.session_ref,
          revision: state.revision,
          draft: serialize(state.form),
        });
        state.revision = saved.revision;
        setFailure(null);
        if (version === state.editVersion) {
          state.dirty = false;
          setSaveState("status.saved");
        } else {
          setSaveState("status.saving");
        }
        return true;
      } catch (error) {
        state.saveFailed = true;
        setSaveState("status.save_failed");
        setFailure(error);
        return false;
      }
    })();
    state.saving = task;
    const ok = await task;
    if (state.saving === task) state.saving = null;
    return ok && state.dirty ? save() : ok;
  }, [session.session_ref]);

  const edit = (patch) => {
    const state = box.current;
    state.editVersion += 1;
    state.dirty = true;
    state.saveFailed = false;
    setSaveState("status.saving");
    setForm((current) => ({ ...current, ...patch }));
    window.clearTimeout(state.timer);
    state.timer = window.setTimeout(doSave, SAVE_DEBOUNCE_MS);
  };

  const leave = React.useCallback(async () => {
    const state = box.current;
    window.clearTimeout(state.timer);
    if (state.saving) await state.saving.catch(() => null);
    if (state.dirty && !(await doSave())) return window.confirm(t("work.leave_failed"));
    return !state.saveFailed || window.confirm(t("work.leave_failed"));
  }, [doSave, t]);

  React.useEffect(() => {
    if (done) return undefined;
    setLeaveGuard(leave);
    const unload = (event) => {
      const state = box.current;
      if (state.dirty || state.saving || state.saveFailed) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", unload);
    return () => {
      window.clearTimeout(box.current.timer);
      window.removeEventListener("beforeunload", unload);
      setLeaveGuard(null);
    };
  }, [leave, done]);

  const openReview = async () => {
    if (!form.summary.trim()) { setFailure({ code: "INVALID_INPUT" }); return; }
    if (form.outcome_state === "quantitative" && !splitLines(form.metrics).length) {
      setFailure({ code: "INVALID_INPUT" });
      return;
    }
    window.clearTimeout(box.current.timer);
    if (!(await doSave())) return;
    try {
      const proposed = await write("/api/workflows/propose", {
        session_ref: session.session_ref, revision: box.current.revision,
      });
      box.current.revision = proposed.revision;
      setReview(proposed.proposal);
    } catch (error) { setFailure(error); }
  };

  const archive = async () => {
    if (!window.confirm(t("work.archive_confirm"))) return;
    if (!(await leave())) return;
    try {
      await write("/api/workflows/archive", {
        session_ref: session.session_ref, revision: box.current.revision,
      });
      setLeaveGuard(null);
      navigate("/career/in-progress");
    } catch (error) { setFailure(error); }
  };

  if (done) {
    return (
      <div className="stack">
        <Callout.Root tone="positive">
          <Callout.Content>
            <Callout.Title>{t("success.experience_approved")}</Callout.Title>
            <Callout.Description>{t("success.experience_approved_body")}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
        <div className="inline">
          <ActionButton variant="brandSolid" size="medium" onClick={() => navigate("/career")}>
            {t("action.view_career")}
          </ActionButton>
        </div>
      </div>
    );
  }

  const measured = ["qualitative", "quantitative"].includes(form.outcome_state);
  const outcomes = [
    ["unknown", t("workflow.outcome.unknown")], ["qualitative", t("workflow.outcome.qualitative")],
    ["quantitative", t("workflow.outcome.quantitative")], ["not_measured", t("workflow.outcome.not_measured")],
  ];
  const externalUse = [
    ["unknown", t("common.unknown")], ["allowed", t("external_use.allowed")],
    ["blocked", t("external_use.blocked")],
  ];

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("work.editor_eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("work.editor_title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("work.editor_intro")}
        </Text>
      </header>

      <Breadcrumb session={session} />
      <div className="inline">
        <StatusChip state={session.status} />
        <Text textStyle="t3Regular">{t("work.not_confirmed")}</Text>
        <span className="figure" role="status">{saveState ? t(saveState) : ""}</span>
      </div>

      {payload.write_recovery_required ? (
        <Callout.Root tone="critical">
          <Callout.Content>
            <Callout.Title>{t("work.recovery_title")}</Callout.Title>
            <Callout.Description>{t("work.recovery_body")}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}

      {failure ? (
        <ErrorState
          error={failure}
          onRetry={failure.code === "REVISION_STALE" ? onReload : doSave}
        />
      ) : null}

      <div className="split split--capture">
        <div className="split__record">
          <fieldset className="form-section">
            <legend>{t("work.section.basics")}</legend>
            <Field label={t("workflow.summary")} help={t("workflow.summary_help")}>
              <Line value={form.summary} onChange={(v) => edit({ summary: v })} />
            </Field>
            <Field label={t("date.when")} help={t("date.partial_help")}>
              <Line type="month" value={form.work_date} onChange={(v) => edit({ work_date: v })} />
            </Field>
            <Field label={t("workflow.role")}>
              <Line value={form.role} onChange={(v) => edit({ role: v })} />
            </Field>
            <Field label={t("workflow.scope")}>
              <Block value={form.scope} onChange={(v) => edit({ scope: v })} />
            </Field>
          </fieldset>

          <fieldset className="form-section">
            <legend>{t("work.section.story")}</legend>
            <Field label={t("workflow.problem")}>
              <Block value={form.problem} onChange={(v) => edit({ problem: v })} />
            </Field>
            <Field label={t("workflow.actions")} help={t("workflow.actions_help")}>
              <Block value={form.direct_actions} onChange={(v) => edit({ direct_actions: v })} />
            </Field>
            <Field label={t("workflow.contribution")} help={t("workflow.contribution_help")}>
              <Block
                value={form.individual_contribution}
                onChange={(v) => edit({ individual_contribution: v })}
              />
            </Field>
          </fieldset>

          <fieldset className="form-section">
            <legend>{t("work.section.outcome")}</legend>
            <Field label={t("workflow.outcome")} help={t("workflow.outcome_help")}>
              <Choice
                value={form.outcome_state}
                options={outcomes}
                onChange={(v) => edit({ outcome_state: v, metrics: v === "quantitative" ? form.metrics : "" })}
              />
            </Field>
            {measured ? (
              <Field label={t("workflow.outcome_detail")}>
                <Block value={form.team_result} onChange={(v) => edit({ team_result: v })} />
              </Field>
            ) : null}
            {form.outcome_state === "quantitative" ? (
              <Field label={t("workflow.metrics")} help={t("workflow.metrics_help")}>
                <Block value={form.metrics} onChange={(v) => edit({ metrics: v })} />
              </Field>
            ) : null}
          </fieldset>

          <fieldset className="form-section">
            <legend>{t("work.section.trust")}</legend>
            <Field label={t("workflow.evidence")} help={t("workflow.evidence_help")}>
              <Block value={form.evidence} onChange={(v) => edit({ evidence: v })} />
            </Field>
            <Field label={t("workflow.contains_confidential")} help={t("confidentiality.contains_help")}>
              <CheckBox
                checked={form.contains_confidential}
                onChange={(checked) => edit({ contains_confidential: checked })}
              />
            </Field>
            <Field label={t("workflow.external_use")} help={t("confidentiality.external_help")}>
              <Choice value={form.external_use} options={externalUse} onChange={(v) => edit({ external_use: v })} />
            </Field>
          </fieldset>

          <Divider />
          <div className="inline">
            <ActionButton variant="neutralWeak" size="medium" onClick={doSave}>
              {t("action.save_now")}
            </ActionButton>
            <ActionButton variant="brandSolid" size="medium" onClick={openReview}>
              {t("action.review_before_confirm")}
            </ActionButton>
            <ActionButton variant="ghost" size="medium" onClick={archive}>
              {t("action.archive")}
            </ActionButton>
          </div>
        </div>

        <div className="split__index"><LivePreview form={form} /></div>
      </div>

      {review ? (
        <ApprovalDialog
          event={review.event}
          context={[session.subject?.context_label, session.subject?.project_label, form.summary.trim()]
            .filter(Boolean)}
          onApprove={async () => {
            const approved = await write("/api/workflows/approve", {
              session_ref: session.session_ref,
              proposal_ref: review.ref,
              revision: box.current.revision,
            });
            box.current.revision = approved.revision;
          }}
          onApproved={() => { setLeaveGuard(null); setSaveState(null); setDone(true); }}
          onClose={() => setReview(null)}
        />
      ) : null}
    </div>
  );
}

function ProfileSummary({ profile }) {
  const { t } = useI18n();
  return (
    <dl className="facts">
      {Object.entries(profile || {})
        .filter(([key]) => !HIDDEN_REVIEW_FIELDS.has(key) && FIELD_LABELS.has(key))
        .map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{t(`field.${key}`)}</dt>
            <dd><Value name={key} value={value} rootKind="profile" /></dd>
          </React.Fragment>
        ))}
    </dl>
  );
}

/* The self-analysis worksheet is `jiko-bunseki`'s, and a profile is only valid with every required
   field present — so this screen imports a reviewed profile rather than offering a partial form
   the validator would reject. */
function SelfAnalysisWork({ payload, onReload }) {
  const { t, language } = useI18n();
  const session = payload.session;
  const revision = React.useRef(payload.revision);
  const [failure, setFailure] = React.useState(null);
  const [review, setReview] = React.useState(null);
  const [done, setDone] = React.useState(false);
  const profile = payload.draft?.profile;

  if (done) {
    return (
      <Callout.Root tone="positive">
        <Callout.Content>
          <Callout.Title>{t("success.self_analysis_approved")}</Callout.Title>
          <Callout.Description>{t("success.self_analysis_approved_body")}</Callout.Description>
        </Callout.Content>
      </Callout.Root>
    );
  }

  const importProfile = async () => {
    try {
      await write("/api/workflows/import-profile", {
        session_ref: session.session_ref, revision: revision.current,
      });
      onReload();
    } catch (error) { setFailure(error); }
  };

  const openReview = async () => {
    try {
      const proposed = await write("/api/workflows/propose", {
        session_ref: session.session_ref, revision: revision.current,
      });
      revision.current = proposed.revision;
      setReview(proposed);
    } catch (error) { setFailure(error); }
  };

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("self_analysis.review_title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("self_analysis.review_intro")}
        </Text>
      </header>
      <div className="inline">
        <StatusChip state={session.status} />
        <Text textStyle="t3Regular">{t("work.not_confirmed")}</Text>
      </div>
      {failure ? <ErrorState error={failure} onRetry={onReload} /> : null}

      {profile ? (
        <>
          <ProfileSummary profile={profile} />
          <div className="inline">
            <ActionButton variant="brandSolid" size="medium" onClick={openReview}>
              {t("action.review_before_confirm")}
            </ActionButton>
            <ActionButton variant="ghost" size="medium" onClick={() => navigate("/self-analysis")}>
              {t("action.return_self_analysis")}
            </ActionButton>
          </div>
        </>
      ) : (
        <>
          <Callout.Root tone="warning">
            <Callout.Content>
              <Callout.Title>{t("self_analysis.no_profile_title")}</Callout.Title>
              <Callout.Description>{t("self_analysis.no_profile_body")}</Callout.Description>
            </Callout.Content>
          </Callout.Root>
          <div className="inline">
            {language !== "en" ? (
              <a className="worksheet-link" href="/jiko/checklist.html" target="_blank" rel="noopener">
                {t("self_analysis.open_worksheet")}
              </a>
            ) : null}
            <ActionButton variant="brandSolid" size="medium" onClick={importProfile}>
              {t("self_analysis.load_reviewed")}
            </ActionButton>
          </div>
          <Text textStyle="t2Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
            {t("self_analysis.host_handoff")}
          </Text>
        </>
      )}

      {review ? (
        <ApprovalDialog
          event={review.proposal.event}
          before={review.review_before}
          effectKey="review.effect_self_analysis"
          onApprove={async () => {
            const approved = await write("/api/workflows/approve", {
              session_ref: session.session_ref,
              proposal_ref: review.proposal.ref,
              revision: revision.current,
            });
            revision.current = approved.revision;
          }}
          onApproved={() => setDone(true)}
          onClose={() => setReview(null)}
        />
      ) : null}
    </div>
  );
}

export default function WorkScreen({ path }) {
  const { t } = useI18n();
  const sessionRef = path.split("/").pop();
  const [reloads, setReloads] = React.useState(0);
  const state = useAsync(() => read(`/api/work?session_ref=${sessionRef}`), [sessionRef, reloads]);
  const reload = () => setReloads((count) => count + 1);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} onRetry={reload} />;

  const workflow = state.data.session?.workflow;
  if (workflow === "self_analysis") return <SelfAnalysisWork payload={state.data} onReload={reload} />;
  if (workflow !== "career_inventory") {
    return (
      <div className="stack">
        <Text textStyle="t8Bold">{t("work.unsupported_title")}</Text>
        <Text textStyle="t3Regular">{t("work.unsupported_intro")}</Text>
      </div>
    );
  }
  // Remounting on reload resets the draft state to whatever the server now holds, which is the
  // only safe response to a stale revision.
  return <CaptureForm key={reloads} payload={state.data} onReload={reload} />;
}
