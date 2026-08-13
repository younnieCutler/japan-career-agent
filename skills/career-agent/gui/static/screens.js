import { read, write } from "./api.js";
import { dateTimeText, enumText, locale, periodText, statusText, t } from "./i18n.js";

const ERROR_CODES = new Set([
  "INVALID_INPUT", "SAVE_FAILED", "REVISION_STALE", "PROPOSAL_STALE",
  "SESSION_COMPLETED", "SESSION_ARCHIVED", "SESSION_SCHEMA_NEWER",
  "SESSION_AMBIGUOUS", "SESSION_NOT_FOUND", "BROWSER_SESSION_EXPIRED",
  "APPROVAL_FAILED", "STATE_CORRUPTED", "INVALID_RELATIONSHIP",
  "PARENT_NOT_CONFIRMED", "CONTEXT_REQUIRED", "PROFILE_NOT_FOUND", "PROFILE_INVALID", "READ_FAILED",
  "CASE_HAS_ACTIVE_CHILDREN", "CASE_ALREADY_CONFIRMED",
]);

const el = (tag, options = {}, children = []) => {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = String(options.text);
  if (options.id) node.id = options.id;
  if (options.type) node.type = options.type;
  if (options.name) node.name = options.name;
  if (options.value !== undefined) node.value = options.value;
  if (options.placeholder) node.placeholder = options.placeholder;
  if (options.required) node.required = true;
  if (options.checked) node.checked = true;
  if (options.hidden) node.hidden = true;
  for (const [name, value] of Object.entries(options.attrs || {})) node.setAttribute(name, value);
  for (const child of Array.isArray(children) ? children : [children]) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
};

const button = (key, onClick, kind = "secondary") => {
  const node = el("button", { className: `button button--${kind}`, type: "button", text: t(key) });
  node.addEventListener("click", onClick);
  return node;
};

const routeLink = (key, path, kind = "secondary") => {
  const node = el("a", { className: `button button--${kind}`, text: t(key), attrs: { href: `${path}?lang=${locale()}` } });
  node.dataset.route = path;
  return node;
};

const page = (eyebrow, title, intro) => {
  const root = el("div", { className: "page" });
  const header = el("header", { className: "page-header" }, [
    el("p", { className: "eyebrow", text: t(eyebrow) }),
    el("h1", { className: "page-title", text: t(title) }),
    el("p", { className: "page-intro", text: t(intro) }),
  ]);
  root.append(header);
  return root;
};

const badge = (state) => el("span", {
  className: `status-badge status-badge--${state || "draft"}`,
  text: statusText(state),
});

const caseBadge = (state) => el("span", {
  className: `status-badge status-badge--${state || "active"}`,
  text: enumText("case_status", state || "active"),
});

const contextText = (session) => {
  const parts = session.context || session.display_context || [];
  return parts.length ? parts.join(t("common.breadcrumb_separator")) : t(`workflow.type.${session.workflow}`);
};

const workflowHref = (session) => `/work/${session.session_ref || session.session_id}`;

const messagePanel = (kind, titleKey, bodyKey) => el("section", {
  className: `message-panel message-panel--${kind}`,
  attrs: { role: kind === "error" ? "alert" : "status", tabindex: "-1" },
}, [el("h2", { text: t(titleKey) }), el("p", { text: t(bodyKey) })]);

function errorPanel(error, retry) {
  const code = ERROR_CODES.has(error.code) ? error.code : "SAVE_FAILED";
  const panel = el("section", {
    className: "message-panel message-panel--error",
    attrs: { role: "alert", tabindex: "-1" },
  }, [
    el("h2", { text: t("error.title") }),
    el("p", { text: t(`error.${code}`) }),
    el("p", { className: "muted", text: t(error.inputSafe === false ? "error.input_may_have_changed" : "error.input_preserved") }),
  ]);
  if (retry) panel.append(button(code === "REVISION_STALE" ? "action.reload" : "action.retry", retry));
  queueMicrotask(() => panel.focus());
  return panel;
}

const field = (labelKey, control, helpKey = null) => {
  const label = el("label", { className: "field" });
  label.append(el("span", { className: "field__label", text: t(labelKey) }), control);
  if (helpKey) label.append(el("span", { className: "field__help", text: t(helpKey) }));
  return label;
};

const textInput = (name, value = "", type = "text") => el("input", { name, value, type });
const textArea = (name, value = "") => el("textarea", { name, text: value, attrs: { rows: "4" } });

const selectInput = (name, choices, selected) => {
  const select = el("select", { name });
  for (const [value, key] of choices) {
    const option = el("option", { value, text: t(key) });
    option.selected = value === selected;
    select.append(option);
  }
  return select;
};

const splitLines = (value) => String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

const summaryStrip = (summary) => el("dl", { className: "summary-strip" }, [
  ["career.context_count", summary.contexts || 0],
  ["career.project_count", summary.projects || 0],
  ["career.experience_count", summary.experiences || 0],
  ["status.draft", summary.draft || 0],
  ["status.review_pending", summary.review_pending || 0],
  ["status.approved", summary.approved || 0],
].flatMap(([key, value]) => [el("dt", { text: t(key) }), el("dd", { text: value })]));

function sessionCard(session, actions = true) {
  const article = el("article", { className: "work-card" });
  article.append(
    el("div", { className: "work-card__top" }, [badge(session.status || session.lifecycle), el("time", { text: dateTimeText(session.updated_at) })]),
    el("h3", { text: contextText(session) }),
    el("p", { className: "muted", text: t(`workflow.stage.${session.stage}`) }),
  );
  if (session.last_entrypoint && session.last_entrypoint !== "unknown") {
    article.append(el("p", { className: "handoff-note", text: t("workflow.last_entrypoint", { entrypoint: enumText("entrypoint", session.last_entrypoint) }) }));
  }
  if (actions) article.append(routeLink(session.status === "review_pending" ? "action.review" : "action.continue", workflowHref(session), "primary"));
  return article;
}

async function homeScreen() {
  const [sessions, career, applications] = await Promise.all([
    read("/api/sessions"), read("/api/career"), read("/api/applications"),
  ]);
  const root = page("home.eyebrow", "home.title", "home.intro");
  const rows = sessions.sessions || [];
  const review = rows.filter((item) => item.status === "review_pending");
  const draft = rows.filter((item) => item.status === "draft");

  const next = el("section", { className: "next-action" });
  if (review.length) {
    next.append(el("p", { className: "eyebrow", text: t("home.review_title") }), el("h2", { text: contextText(review[0]) }), routeLink("action.review", workflowHref(review[0]), "primary"));
  } else if (draft.length) {
    next.append(el("p", { className: "eyebrow", text: t("home.resume_title") }), el("h2", { text: contextText(draft[0]) }), routeLink("action.continue", workflowHref(draft[0]), "primary"));
  } else if (!(career.summary?.contexts)) {
    next.append(el("p", { className: "eyebrow", text: t("home.first_step") }), el("h2", { text: t("home.empty_title") }), routeLink("career.add_context", "/career", "primary"));
  } else {
    next.append(el("p", { className: "eyebrow", text: t("home.next_step") }), el("h2", { text: t("home.add_experience_title") }), routeLink("career.add_experience", "/career", "primary"));
  }
  root.append(next);

  const overview = el("section", { className: "section-block" }, [
    el("div", { className: "section-heading" }, [el("h2", { text: t("home.known_title") }), routeLink("action.view_all", "/career")]),
    summaryStrip(career.summary || {}),
    el("p", { className: "muted", text: t("home.known_help") }),
  ]);
  root.append(overview);

  if (rows.length > 1) {
    const section = el("section", { className: "section-block" }, [
      el("div", { className: "section-heading" }, [el("h2", { text: t("home.all_work_title") }), routeLink("action.manage", "/career/in-progress")]),
      el("div", { className: "compact-list" }, rows.slice(0, 4).map((item) => sessionCard(item))),
    ]);
    root.append(section);
  }

  const appCount = (applications.companies || []).reduce((count, company) => count + (company.positions || []).length, 0);
  const reuse = el("section", { className: "section-block reuse-callout" }, [
    el("p", { className: "eyebrow", text: t("home.reuse_label") }),
    el("h2", { text: t("home.reuse_title") }),
    el("p", { text: t("home.reuse_count", { count: appCount }) }),
    routeLink("nav.applications", "/applications"),
  ]);
  root.append(reuse);
  return root;
}

function careerToolbar(onChange) {
  const search = textInput("career-search", "", "search");
  search.placeholder = t("search.career_placeholder");
  search.setAttribute("aria-label", t("search.career_placeholder"));
  const status = selectInput("career-status", [
    ["all", "filter.all"], ["draft", "status.draft"],
    ["review_pending", "status.review_pending"], ["approved", "status.approved"],
  ], "all");
  search.addEventListener("input", onChange);
  status.addEventListener("change", onChange);
  return { node: el("div", { className: "toolbar" }, [search, status]), search, status };
}

const searchable = (context) => [
  context.label, context.role, context.summary, periodText(context.period),
  ...(context.projects || []).flatMap((project) => [project.label, project.role, project.summary, periodText(project.period), ...(project.experiences || []).map((item) => item.label)]),
].filter(Boolean).join(" ").toLocaleLowerCase();

function periodPayload(form) {
  const from = form.elements.from?.value || "";
  const to = form.elements.to?.value || "";
  const current = Boolean(form.elements.current?.checked);
  return from || to || current ? { from: from || null, to: to || null, current } : undefined;
}

function createContextForm(contexts, app) {
  const details = el("details", { className: "create-panel" });
  details.append(el("summary", { text: t("career.add_context") }));
  const form = el("form", { className: "form-grid" });
  const relationship = selectInput("relationship", [
    ["employer", "enum.context_kind.company"], ["freelance", "enum.context_kind.freelance"],
    ["internship", "enum.context_kind.internship_organization"],
    ["part_time", "enum.context_kind.part_time_workplace"], ["non_work", "career.non_work"],
  ], "employer");
  const kind = selectInput("context_kind", [
    ["company", "enum.context_kind.company"], ["freelance", "enum.context_kind.freelance"],
    ["internship_organization", "enum.context_kind.internship_organization"],
    ["part_time_workplace", "enum.context_kind.part_time_workplace"],
    ["personal", "enum.context_kind.personal"], ["university", "enum.context_kind.university"],
    ["graduate_school", "enum.context_kind.graduate_school"], ["club", "enum.context_kind.club"],
    ["student_organization", "enum.context_kind.student_organization"],
    ["open_source", "enum.context_kind.open_source"],
    ["volunteer_organization", "enum.context_kind.volunteer_organization"],
    ["other", "enum.context_kind.other"],
  ], "company");
  const label = textInput("label");
  label.required = true;
  const role = textInput("role");
  const summary = textArea("summary");
  const from = textInput("from", "", "month");
  const to = textInput("to", "", "month");
  const current = el("input", { name: "current", type: "checkbox" });
  const workKinds = { employer: "company", freelance: "freelance", internship: "internship_organization", part_time: "part_time_workplace" };
  const syncContextKind = () => {
    const nonWork = relationship.value === "non_work";
    for (const option of kind.options) option.disabled = nonWork && Object.values(workKinds).includes(option.value);
    if (nonWork && Object.values(workKinds).includes(kind.value)) kind.value = "personal";
    if (!nonWork) kind.value = workKinds[relationship.value];
    kind.disabled = !nonWork;
  };
  relationship.addEventListener("change", syncContextKind);
  syncContextKind();
  current.addEventListener("change", () => { to.disabled = current.checked; if (current.checked) to.value = ""; });
  const result = el("div", { className: "form-result", attrs: { "aria-live": "polite" } });
  form.append(
    field("career.relationship", relationship, "career.relationship_help"),
    field("career.context_type", kind), field("career.context_name", label),
    field("career.role_optional", role), field("career.summary_optional", summary),
    field("date.start", from, "date.partial_help"), field("date.end", to, "date.end_help"),
    field("date.current", current),
  );
  const submit = button("action.create_draft", () => {}, "primary");
  submit.type = "submit";
  form.append(submit, result);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const duplicate = contexts.find((item) => String(item.label).trim().toLocaleLowerCase() === label.value.trim().toLocaleLowerCase());
    if (duplicate && !window.confirm(t("career.duplicate_context_confirm", { label: duplicate.label }))) return;
    submit.disabled = true;
    try {
      await write("/api/career/contexts", {
        label: label.value.trim(), relationship: relationship.value === "non_work" ? "non_work" : "employer",
        context_kind: relationship.value === "non_work" ? kind.value : workKinds[relationship.value],
        role: role.value.trim() || null, summary: summary.value.trim() || null,
        period: periodPayload(form),
      });
      await app.refresh();
      app.announce(["success.context_created", "success.context_next"]);
    } catch (error) {
      result.replaceChildren(errorPanel(error));
    } finally { submit.disabled = false; }
  });
  details.append(form);
  return details;
}

function proposalPayload(event) {
  if (event.work_event) return ["experience", { summary: event.claim_summary, ...event.work_event }];
  if (event.experience) return ["experience", { summary: event.claim_summary, ...event.experience }];
  if (event.experience_context) return ["context", event.experience_context];
  if (event.project) return ["project", event.project];
  if (event.career_context) return ["profile", event.career_context];
  return ["experience", {}];
}

const HIDDEN_REVIEW_FIELDS = new Set([
  "id", "context_id", "primary_project_id", "related_project_ids", "experience_ref",
  "profile_digest", "self_analysis_version", "source_type", "episode_ref", "evidence_episode_refs",
]);

const FIELD_LABELS = new Set([
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

function scalarText(key, value, rootKind = null) {
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
}

function valueNode(key, value, depth = 0, rootKind = null) {
  if (Array.isArray(value)) {
    if (!value.length) return el("span", { className: "unknown", text: t("common.reviewed_empty") });
    const list = el("ul", { className: depth ? "nested-list" : "value-list" });
    value.forEach((item) => list.append(el("li", {}, valueNode(key, item, depth + 1, rootKind))));
    return list;
  }
  if (value && typeof value === "object") {
    if (key === "period") return el("span", { text: periodText(value) });
    const list = el("dl", { className: "nested-values" });
    for (const [childKey, child] of Object.entries(value)) {
      if (HIDDEN_REVIEW_FIELDS.has(childKey) || !FIELD_LABELS.has(childKey)) continue;
      list.append(el("dt", { text: t(`field.${childKey}`) }), el("dd", {}, valueNode(childKey, child, depth + 1, rootKind)));
    }
    return list;
  }
  return el("span", { className: value === null || value === undefined ? "unknown" : "", text: scalarText(key, value, rootKind) });
}

function containsUnknown(key, value) {
  if (value === null || value === undefined || value === "" || value === "unknown") return true;
  if (Array.isArray(value)) return value.some((item) => containsUnknown(key, item));
  if (!value || typeof value !== "object") return false;
  if (key === "period" && value.current === true) return !value.from;
  return Object.entries(value).some(([childKey, child]) => containsUnknown(childKey, child));
}

function snapshotView(event) {
  const [kind, payload] = proposalPayload(event || {});
  const section = el("section", { className: "approval-snapshot" });
  section.append(el("p", { className: "eyebrow", text: t("review.after") }), el("h3", { text: t(`review.snapshot.${kind}`) }));
  const values = el("dl", { className: "review-values" });
  for (const [key, value] of Object.entries(payload || {})) {
    if (HIDDEN_REVIEW_FIELDS.has(key) || !FIELD_LABELS.has(key)) continue;
    values.append(el("dt", { text: t(`field.${key}`) }), el("dd", {}, valueNode(key, value, 0, kind)));
  }
  section.append(values);
  let expected = kind === "experience"
    ? ["summary", "work_date", "role", "scope", "problem", "direct_actions", "individual_contribution", "team_result", "outcome_state", "metrics", "confidentiality"]
    : kind === "project" ? ["title", "role", "scope", "summary", "period"]
      : kind === "context" ? ["label", "kind", "role", "summary", "period"]
        : kind === "profile" ? Object.keys(payload || {}).filter((key) => FIELD_LABELS.has(key)) : [];
  if (kind === "experience" && payload?.outcome_state !== "quantitative") {
    expected = expected.filter((key) => key !== "metrics");
  }
  const absent = expected.filter((key) => !Object.hasOwn(payload || {}, key));
  const unknown = expected.filter((key) => Object.hasOwn(payload || {}, key) && containsUnknown(key, payload[key]));
  const notEnteredBox = el("div", { className: "unknown-box" }, [
    el("h4", { text: t("review.not_entered_title") }),
    el("p", { text: absent.length ? absent.map((key) => t(`field.${key}`)).join(t("common.list_separator")) : t("review.not_entered_none") }),
  ]);
  const unknownBox = el("div", { className: "unknown-box" }, [
    el("h4", { text: t("review.unknown_title") }),
    el("p", { text: unknown.length ? unknown.map((key) => t(`field.${key}`)).join(t("common.list_separator")) : t("review.unknown_none") }),
    el("p", { className: "muted", text: t("review.unknown_help") }),
  ]);
  section.append(notEnteredBox, unknownBox);
  const evidence = event?.evidence || [];
  const evidenceText = evidence.map((item) => item === "user_confirmation"
    ? t("review.evidence_user_confirmation")
    : String(item).startsWith("private-document:")
      ? t("review.evidence_private_document")
      : item);
  section.append(el("div", { className: "evidence-box" }, [
    el("h4", { text: t("review.evidence_title") }),
    el("p", { text: kind === "profile" ? t("review.profile_source") : (evidenceText.length ? evidenceText.join(t("common.list_separator")) : t("review.evidence_missing")) }),
  ]));
  return section;
}

function changesView(before, event) {
  const [kind, after] = proposalPayload(event || {});
  const changed = [...new Set([...Object.keys(before || {}), ...Object.keys(after || {})])]
    .filter((key) => !HIDDEN_REVIEW_FIELDS.has(key) && FIELD_LABELS.has(key))
    .filter((key) => JSON.stringify(before?.[key]) !== JSON.stringify(after?.[key]));
  const section = el("section", { className: "before-box" }, [el("h3", { text: t("review.changes_title") })]);
  if (!changed.length) {
    section.append(el("p", { text: t("review.no_changes") }));
    return section;
  }
  const values = el("dl", { className: "review-values review-values--changes" });
  for (const key of changed) {
    values.append(
      el("dt", { text: t(`field.${key}`) }),
      el("dd", {}, [
        el("p", { className: "input-state", text: t("review.before") }), valueNode(key, before?.[key], 0, kind),
        el("p", { className: "input-state", text: t("review.after") }), valueNode(key, after?.[key], 0, kind),
      ]),
    );
  }
  section.append(values);
  return section;
}

function approvalDialog(event, approveAction, options = {}) {
  const dialog = el("dialog", { className: "approval-dialog" });
  const close = button("action.keep_editing", () => dialog.close());
  const approve = button("action.approve", async () => {
    approve.disabled = true;
    try {
      await approveAction();
      dialog.close("approved");
    } catch (error) {
      result.replaceChildren(errorPanel(error));
      approve.disabled = false;
    }
  }, "primary");
  const result = el("div", { className: "dialog-result", attrs: { "aria-live": "assertive" } });
  dialog.append(
    el("p", { className: "eyebrow", text: t("review.eyebrow") }),
    el("h2", { text: t(options.titleKey || "review.title") }),
    el("p", { className: "page-intro", text: t(options.introKey || "review.intro") }),
    options.context?.length ? el("section", { className: "context-breadcrumb" }, [
      el("strong", { text: t("review.context_title") }),
      el("span", { text: options.context.join(t("common.breadcrumb_separator")) }),
    ]) : null,
    options.before ? changesView(options.before, event) : el("section", { className: "before-box" }, [el("h3", { text: t("review.before") }), el("p", { text: t(options.beforeKey || "review.before_new") })]),
    snapshotView(event),
    el("section", { className: "effect-box" }, [el("h3", { text: t("review.effect_title") }), el("p", { text: t(options.effectKey || "review.effect_career") })]),
    result,
    el("div", { className: "dialog-actions" }, [close, approve]),
  );
  dialog.addEventListener("cancel", (event_) => { event_.preventDefault(); dialog.close(); });
  document.body.append(dialog);
  dialog.addEventListener("close", () => { const approved = dialog.returnValue === "approved"; dialog.remove(); if (approved && options.onApproved) options.onApproved(); }, { once: true });
  dialog.showModal();
  return dialog;
}

async function reviewCase(item, app, context = [item.label]) {
  try {
    const review = await write("/api/career/propose", { case_ref: item.ref });
    approvalDialog(review.proposal?.event, async () => {
      await write("/api/career/approve", { case_ref: item.ref, proposal_ref: review.proposal.ref });
    }, {
      onApproved: async () => {
        await app.refresh();
        app.announce(item.relationship
          ? ["success.context_approved", "success.context_approved_next"]
          : ["success.project_approved", "success.project_approved_next"]);
      },
      context,
      effectKey: item.relationship ? "review.effect_context" : "review.effect_project",
    });
  } catch (error) {
    const target = document.querySelector(".page-notices");
    target.replaceChildren(errorPanel(error, app.refresh));
  }
}

function caseLifecycleControls(item, app) {
  const state = item.lifecycle || item.status;
  if (!item.ref || state === "approved" || String(item.ref).startsWith("canonical:")) return null;
  const archived = state === "archived";
  const feedback = el("div", { attrs: { "aria-live": "assertive" } });
  const action = button(archived ? "action.restore" : "action.archive", async () => {
    if (!window.confirm(t(archived ? "case.restore_confirm" : "case.archive_confirm", { label: item.label }))) return;
    action.disabled = true;
    try {
      const endpoint = archived ? "/api/cases/restore" : "/api/cases/archive";
      await write(endpoint, {
        case_id: item.ref,
        updated_at: item.updated_at,
      });
      await app.refresh();
      app.announce(archived ? "success.restored" : "success.archived");
    } catch (error) { feedback.replaceChildren(errorPanel(error, app.refresh)); }
    finally { action.disabled = false; }
  }, "quiet");
  return el("div", { className: "lifecycle-actions" }, [action, feedback]);
}

function createProjectForm(context, app) {
  const details = el("details", { className: "inline-create" });
  details.append(el("summary", { text: t("career.add_project") }));
  const form = el("form", { className: "form-grid form-grid--compact" });
  const label = textInput("label"); label.required = true;
  const role = textInput("role");
  const scope = textArea("scope");
  const from = textInput("from", "", "month");
  const to = textInput("to", "", "month");
  const current = el("input", { name: "current", type: "checkbox" });
  current.addEventListener("change", () => { to.disabled = current.checked; if (current.checked) to.value = ""; });
  const result = el("div", { className: "form-result" });
  form.append(field("career.project_name", label), field("workflow.role", role), field("career.project_scope", scope), field("date.start", from, "date.partial_help"), field("date.end", to, "date.end_help"), field("date.current", current));
  const submit = button("action.create_draft", () => {}, "primary"); submit.type = "submit";
  form.append(submit, result);
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); submit.disabled = true;
    const duplicate = (context.projects || []).find((item) => String(item.label).trim().toLocaleLowerCase() === label.value.trim().toLocaleLowerCase());
    if (duplicate && !window.confirm(t("career.duplicate_project_confirm", { label: duplicate.label }))) { submit.disabled = false; return; }
    try {
      await write("/api/career/projects", { parent_ref: context.ref, label: label.value.trim(), role: role.value.trim() || null, scope: scope.value.trim() || null, period: periodPayload(form) });
      await app.refresh();
      app.announce(["success.project_created", "success.project_next"]);
    } catch (error) { result.replaceChildren(errorPanel(error)); }
    finally { submit.disabled = false; }
  });
  details.append(form);
  return details;
}

function experienceRow(experience) {
  const row = el("li", { className: "experience-row" });
  const label = experience.contains_confidential ? t("career.confidential_experience") : (experience.label || t("career.experience"));
  const details = el("details", { className: "experience-detail" });
  details.append(el("summary", {}, [el("strong", { text: label }), badge("approved")]));
  const body = el("div", { className: "experience-detail__body" });
  body.append(el("p", { className: "muted", text: experience.evidence_state === "present" ? t("evidence.present_count", { count: experience.evidence_count }) : t("evidence.missing_usable") }));
  if (experience.work_date) body.append(el("p", { className: "period", text: formatDate(experience.work_date) }));
  if (experience.contains_confidential) {
    body.append(el("p", { className: "confidential-note", text: t(experience.external_use === "allowed" ? "confidentiality.hidden_allowed" : experience.external_use === "blocked" ? "confidentiality.hidden_blocked" : "confidentiality.hidden_review") }));
  } else {
    const values = el("dl", { className: "review-values experience-values" });
    for (const [key, value] of Object.entries(experience.detail || {})) {
      if (!FIELD_LABELS.has(key)) continue;
      values.append(el("dt", { text: t(`field.${key}`) }), el("dd", {}, valueNode(key, value, 0, "experience")));
    }
    if (values.children.length) body.append(values);
  }
  details.append(body);
  row.append(details);
  return row;
}

function projectTree(project, context, app) {
  const projectLabel = project.label || t("career.project");
  const details = el("details", { className: "project-tree" });
  const heading = el("summary", {}, [el("span", { className: "tree-marker", text: t("career.project") }), el("strong", { text: projectLabel }), badge(project.lifecycle)]);
  details.append(heading);
  const body = el("div", { className: "tree-body" }, [el("p", { className: "period", text: periodText(project.period) })]);
  if (project.summary) body.append(el("p", { text: project.summary }));
  if (project.relationship_conflict) body.append(messagePanel("error", "career.context_conflict_title", "career.context_conflict_body"));
  const work = project.work || [];
  const canStartAnother = () => !work.length || window.confirm(t("career.new_experience_confirm"));
  const actions = el("div", { className: "inline-actions" });
  if (project.lifecycle === "approved" && !String(project.ref).startsWith("canonical:")) {
    actions.append(button("career.add_experience", async () => {
      if (!canStartAnother()) return;
      try {
        const result = await write("/api/workflows/start", { workflow: "career_inventory", case_ref: project.ref });
        await app.navigate(workflowHref(result.session));
      } catch (error) { body.prepend(errorPanel(error)); }
    }, "primary"));
  } else if (project.lifecycle === "approved") {
    actions.append(button("career.organize_project", async () => {
      if (!canStartAnother()) return;
      try {
        const organized = await write("/api/career/organize", { context_ref: context.ref, project_ref: project.ref });
        const result = await write("/api/workflows/start", { workflow: "career_inventory", case_ref: organized.ref });
        await app.navigate(workflowHref(result.session));
      } catch (error) { body.prepend(errorPanel(error)); }
    }, "primary"));
  } else if (project.lifecycle !== "archived") {
    actions.append(button("action.review_to_confirm", () => reviewCase(project, app, [context.label, projectLabel])));
  }
  body.append(actions);
  if (work.length) body.append(el("div", { className: "compact-list" }, work.map((item) => sessionCard(item))));
  const experiences = project.experiences || [];
  if (experiences.length) body.append(el("ul", { className: "experience-list" }, experiences.map(experienceRow)));
  else body.append(el("p", { className: "empty-inline", text: t("career.no_experience_project") }));
  const lifecycle = caseLifecycleControls(project, app);
  if (lifecycle) body.append(lifecycle);
  details.append(body);
  return details;
}

function contextTree(context, app, index) {
  const details = el("details", { className: "context-tree" });
  details.open = index < 3 || context.lifecycle !== "approved";
  details.append(el("summary", {}, [
    el("span", { className: "tree-marker", text: context.kind === "freelance" ? t("career.freelance") : context.relationship === "employer" ? t("career.employer") : t("career.non_work") }),
    el("strong", { text: context.label }), badge(context.lifecycle),
  ]));
  const body = el("div", { className: "tree-body" }, [el("p", { className: "period", text: periodText(context.period) })]);
  if (context.role) body.append(el("p", { text: context.role }));
  if (context.summary) body.append(el("p", { className: "muted", text: context.summary }));
  if (context.lifecycle === "approved" && !String(context.ref).startsWith("canonical:")) body.append(createProjectForm(context, app));
  else if (context.lifecycle === "approved") body.append(button("career.organize_context", async () => {
    try { await write("/api/career/organize", { context_ref: context.ref }); await app.refresh(); }
    catch (error) { body.prepend(errorPanel(error)); }
  }, "primary"));
  else if (context.lifecycle !== "archived") body.append(button("action.review_to_confirm", () => reviewCase(context, app, [context.label]), "primary"));
  const projects = context.projects || [];
  if (projects.length) body.append(el("div", { className: "project-list" }, projects.map((project) => projectTree(project, context, app))));
  else body.append(el("p", { className: "empty-inline", text: context.lifecycle === "approved" ? t("career.no_projects_next") : t("career.confirm_context_first") }));
  if ((context.other_experiences || []).length) body.append(el("ul", { className: "experience-list" }, context.other_experiences.map(experienceRow)));
  const lifecycle = caseLifecycleControls(context, app);
  if (lifecycle) body.append(lifecycle);
  details.append(body);
  return details;
}

function unassignedProjects(payload, refresh) {
  const projects = payload.unassigned_projects || [];
  if (!projects.length) return null;
  const contexts = (payload.contexts || []).filter((item) => item.lifecycle === "approved" && !String(item.ref).startsWith("canonical:"));
  const section = el("section", { className: "recovery-panel" }, [
    el("h2", { text: t("career.unassigned_title") }),
    el("p", { text: t("career.unassigned_body") }),
  ]);
  for (const project of projects) {
    const projectLabel = project.label || t("career.project");
    const select = el("select", { attrs: { "aria-label": t("career.choose_context_for", { project: projectLabel }) } });
    for (const context of contexts) select.append(el("option", { value: context.ref, text: context.label }));
    const result = el("div", { attrs: { "aria-live": "assertive" } });
    const connect = button("career.connect_project", async () => {
      const context = contexts.find((item) => item.ref === select.value);
      if (!context || !window.confirm(t("career.connect_project_confirm", { project: projectLabel, context: context.label }))) return;
      connect.disabled = true;
      try {
        await write("/api/career/assign-project-context", {
          project_ref: project.ref,
          context_ref: context.ref,
          updated_at: project.updated_at,
        });
        await refresh();
      } catch (error) { result.replaceChildren(errorPanel(error, refresh)); }
      finally { connect.disabled = false; }
    }, "primary");
    connect.disabled = !contexts.length;
    section.append(el("article", { className: "recovery-item" }, [
      el("div", {}, [el("strong", { text: projectLabel }), badge(project.lifecycle)]),
      contexts.length ? field("career.correct_context", select, "career.correct_context_help") : el("p", { text: t("career.confirm_context_first") }),
      connect,
      result,
    ]));
  }
  return section;
}

function unassignedWork(payload, app) {
  const sessions = payload.unassigned_work || [];
  if (!sessions.length) return null;
  const choices = (payload.contexts || []).flatMap((context) =>
    (context.projects || [])
      .filter((project) => project.lifecycle === "approved" && !String(project.ref).startsWith("canonical:"))
      .map((project) => ({ ref: project.ref, label: [context.label, project.label].join(t("common.breadcrumb_separator")) }))
  );
  const section = el("section", { className: "recovery-panel" }, [
    el("h2", { text: t("career.unassigned_work_title") }),
    el("p", { text: t("career.unassigned_work_body") }),
  ]);
  for (const session of sessions) {
    const card = sessionCard(session, false);
    const select = el("select", { attrs: { "aria-label": t("career.choose_project_for_draft") } });
    for (const choice of choices) select.append(el("option", { value: choice.ref, text: choice.label }));
    const result = el("div", { attrs: { "aria-live": "assertive" } });
    const connect = button("career.connect_draft", async () => {
      const choice = choices.find((item) => item.ref === select.value);
      if (!choice || !window.confirm(t("career.connect_draft_confirm", { project: choice.label }))) return;
      connect.disabled = true;
      try {
        const assigned = await write("/api/workflows/assign-project", {
          session_ref: session.session_ref,
          case_ref: choice.ref,
          revision: session.revision,
        });
        await app.navigate(workflowHref(assigned.session));
      } catch (error) { result.replaceChildren(errorPanel(error, app.refresh)); }
      finally { connect.disabled = false; }
    }, "primary");
    connect.disabled = !choices.length;
    card.append(choices.length ? field("career.correct_project", select, "career.correct_project_help") : el("p", { text: t("career.confirm_project_first") }), connect, result);
    section.append(card);
  }
  return section;
}

async function careerScreen(app) {
  const payload = await read("/api/career");
  const root = page("career.eyebrow", "career.title", "career.intro");
  const tabs = el("nav", { className: "subnav", attrs: { "aria-label": t("a11y.career_views") } }, [
    routeLink("career.overview", "/career", "quiet"), routeLink("nav.in_progress", "/career/in-progress", "quiet"), routeLink("nav.timeline", "/career/timeline", "quiet"),
  ]);
  tabs.firstElementChild.setAttribute("aria-current", "page");
  root.append(tabs, summaryStrip(payload.summary || {}), el("div", { className: "page-notices" }));
  if ((payload.relationship_conflicts || []).length) root.querySelector(".page-notices").append(messagePanel("error", "career.context_conflict_title", "career.context_conflict_body"));
  root.append(createContextForm(payload.contexts || [], app));
  const toolbar = careerToolbar(render);
  const resultCount = el("p", { className: "result-count", attrs: { "aria-live": "polite" } });
  const list = el("div", { className: "career-tree" });
  const more = button("action.show_more", () => { limit += 8; render(); });
  let limit = 8;
  function render() {
    const query = toolbar.search.value.trim().toLocaleLowerCase();
    const state = toolbar.status.value;
    const matches = (payload.contexts || []).filter((context) => {
      const textMatch = !query || searchable(context).includes(query);
      const states = [context.lifecycle, ...(context.projects || []).map((item) => item.lifecycle), ...(context.projects || []).flatMap((item) => (item.work || []).map((work) => work.lifecycle))];
      return textMatch && (state === "all" || states.includes(state));
    });
    list.replaceChildren(...matches.slice(0, limit).map((context, index) => contextTree(context, app, index)));
    if (!matches.length) list.append(el("section", { className: "state-panel state-panel--empty" }, [el("h2", { text: t(query || state !== "all" ? "search.no_results" : "career.empty_title") }), el("p", { text: t(query || state !== "all" ? "search.adjust" : "career.empty_body") })]));
    resultCount.textContent = t("search.result_count", { shown: Math.min(matches.length, limit), total: matches.length });
    more.hidden = matches.length <= limit;
  }
  root.append(toolbar.node, resultCount, list, more);
  const recovery = unassignedProjects(payload, app.refresh);
  if (recovery) root.append(recovery);
  const draftRecovery = unassignedWork(payload, app);
  if (draftRecovery) root.append(draftRecovery);
  render();
  return root;
}

async function inProgressScreen(app) {
  const payload = await read("/api/sessions?include_archived=1");
  const root = page("work.in_progress_eyebrow", "work.in_progress_title", "work.in_progress_intro");
  const tabs = el("nav", { className: "subnav", attrs: { "aria-label": t("a11y.career_views") } }, [routeLink("career.overview", "/career", "quiet"), routeLink("nav.in_progress", "/career/in-progress", "quiet"), routeLink("nav.timeline", "/career/timeline", "quiet")]);
  tabs.children[1].setAttribute("aria-current", "page");
  root.append(tabs);
  const rows = payload.sessions || [];
  const search = textInput("work-search", "", "search"); search.placeholder = t("search.work_placeholder");
  const filter = selectInput("work-status", [["all", "filter.all"], ["draft", "status.draft"], ["review_pending", "status.review_pending"], ["archived", "status.archived"]], "all");
  const list = el("div", { className: "work-list" });
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const matches = rows.filter((item) => (!query || contextText(item).toLocaleLowerCase().includes(query)) && (filter.value === "all" || item.status === filter.value));
    list.replaceChildren();
    for (const session of matches) {
      const card = sessionCard(session, session.status !== "archived");
      const lifecycle = session.status === "archived" ? "restore" : "archive";
      card.append(button(lifecycle === "archive" ? "action.archive" : "action.restore", async () => {
        const key = lifecycle === "archive" ? "work.archive_confirm" : "work.restore_confirm";
        if (!window.confirm(t(key))) return;
        try {
          await write(`/api/workflows/${lifecycle}`, { session_ref: session.session_ref, revision: session.revision });
          await app.refresh();
        } catch (error) { card.prepend(errorPanel(error, app.refresh)); }
      }, "quiet"));
      list.append(card);
    }
    if (!matches.length) list.append(el("section", { className: "state-panel state-panel--empty" }, [el("h2", { text: t("work.none_title") }), el("p", { text: t("work.none_body") }), routeLink("career.add_experience", "/career", "primary")]));
  };
  search.addEventListener("input", render); filter.addEventListener("change", render);
  root.append(el("div", { className: "toolbar" }, [search, filter]), list); render();
  return root;
}

async function timelineScreen() {
  const payload = await read("/api/timeline");
  const root = page("timeline.eyebrow", "timeline.title", "timeline.intro");
  const tabs = el("nav", { className: "subnav", attrs: { "aria-label": t("a11y.career_views") } }, [routeLink("career.overview", "/career", "quiet"), routeLink("nav.in_progress", "/career/in-progress", "quiet"), routeLink("nav.timeline", "/career/timeline", "quiet")]);
  tabs.children[2].setAttribute("aria-current", "page"); root.append(tabs);
  const search = textInput("timeline-search", "", "search"); search.placeholder = t("search.timeline_placeholder");
  const list = el("ol", { className: "timeline-list" });
  let limit = 30;
  const more = button("action.show_more", () => { limit += 30; render(); });
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const rows = (payload.sections || []).filter((item) => !query || `${item.label || ""} ${periodText(item.period)}`.toLocaleLowerCase().includes(query));
    list.replaceChildren(...rows.slice(0, limit).map((item) => el("li", { className: "timeline-row" }, [
      el("time", { text: periodText(item.period) }),
      el("div", {}, [el("span", { className: "tree-marker", text: t(`timeline.kind.${item.kind}`) }), el("h2", { text: item.contains_confidential ? t("career.confidential_experience") : (item.label || t("common.unknown")) })]),
    ])));
    if (!rows.length) list.append(el("li", { className: "state-panel state-panel--empty" }, [el("h2", { text: t(query ? "search.no_results" : "timeline.empty_title") }), el("p", { text: t(query ? "search.adjust" : "timeline.empty_body") })]));
    more.hidden = rows.length <= limit;
  };
  search.addEventListener("input", render); root.append(el("div", { className: "toolbar" }, search), list, more); render();
  return root;
}

function workBreadcrumb(session) {
  const parts = session.subject || {};
  const labels = [parts.context_label, parts.project_label, parts.experience_label || t("workflow.new_experience")].filter(Boolean);
  return el("nav", { className: "context-breadcrumb", attrs: { "aria-label": t("a11y.current_context") } }, labels.flatMap((label, index) => [index ? el("span", { className: "breadcrumb-separator", text: t("common.breadcrumb_separator"), attrs: { "aria-hidden": "true" } }) : null, el("span", { text: label })]).filter(Boolean));
}

function careerDraftForm(payload, app) {
  const root = page("work.editor_eyebrow", "work.editor_title", "work.editor_intro");
  const session = payload.session;
  let revision = payload.revision;
  let dirty = false;
  let timer = null;
  let saving = null;
  let saveFailed = false;
  let editVersion = 0;
  const unload = (event) => { if (dirty || saving || saveFailed) { event.preventDefault(); event.returnValue = ""; } };
  const cleanup = () => {
    window.clearTimeout(timer);
    window.removeEventListener("beforeunload", unload);
  };
  root.prepend(workBreadcrumb(session));
  const lifecycle = el("div", { className: "lifecycle-strip" }, [badge(session.status), el("span", { text: t("work.not_confirmed") })]);
  root.append(lifecycle);
  const notices = el("div", { className: "page-notices" }); root.append(notices);
  if (payload.write_recovery_required) notices.append(messagePanel("error", "work.recovery_title", "work.recovery_body"));

  const draft = payload.draft || {};
  const form = el("form", { className: "experience-form" });
  const summary = textInput("summary", draft.summary || ""); summary.required = true;
  const workDate = textInput("work_date", draft.work_date || "", "month");
  const role = textInput("role", draft.role || "");
  const scope = textArea("scope", draft.scope || "");
  const problem = textArea("problem", draft.problem || "");
  const actions = textArea("direct_actions", (draft.direct_actions || []).join("\n"));
  const contribution = textArea("individual_contribution", draft.individual_contribution || "");
  const outcomeState = selectInput("outcome_state", [
    ["unknown", "workflow.outcome.unknown"], ["qualitative", "workflow.outcome.qualitative"],
    ["quantitative", "workflow.outcome.quantitative"], ["not_measured", "workflow.outcome.not_measured"],
  ], draft.outcome_state || "unknown");
  const outcome = textArea("team_result", draft.team_result || "");
  const outcomeField = field("workflow.outcome_detail", outcome);
  const metrics = textArea("metrics", (draft.metrics || []).join("\n"));
  const metricsField = field("workflow.metrics", metrics, "workflow.metrics_help");
  const evidence = textArea("evidence", (draft.evidence || []).join("\n"));
  const confidential = el("input", { name: "contains_confidential", type: "checkbox", checked: draft.confidentiality?.contains_confidential });
  const external = selectInput("external_use", [["unknown", "common.unknown"], ["allowed", "external_use.allowed"], ["blocked", "external_use.blocked"]], draft.confidentiality?.external_use || "unknown");
  const updateMetrics = () => {
    const outcomeKnown = ["qualitative", "quantitative"].includes(outcomeState.value);
    outcomeField.hidden = !outcomeKnown;
    metricsField.hidden = outcomeState.value !== "quantitative";
    metrics.required = !metricsField.hidden;
    if (metricsField.hidden) metrics.value = "";
  };
  outcomeState.addEventListener("change", updateMetrics); updateMetrics();
  form.append(
    el("fieldset", { className: "form-section" }, [el("legend", { text: t("work.section.basics") }), field("workflow.summary", summary, "workflow.summary_help"), field("date.when", workDate, "date.partial_help"), field("workflow.role", role), field("workflow.scope", scope)]),
    el("fieldset", { className: "form-section" }, [el("legend", { text: t("work.section.story") }), field("workflow.problem", problem), field("workflow.actions", actions, "workflow.actions_help"), field("workflow.contribution", contribution, "workflow.contribution_help")]),
    el("fieldset", { className: "form-section" }, [el("legend", { text: t("work.section.outcome") }), field("workflow.outcome", outcomeState, "workflow.outcome_help"), outcomeField, metricsField]),
    el("fieldset", { className: "form-section" }, [el("legend", { text: t("work.section.trust") }), field("workflow.evidence", evidence, "workflow.evidence_help"), field("workflow.contains_confidential", confidential, "confidentiality.contains_help"), field("workflow.external_use", external, "confidentiality.external_help")]),
  );

  const serialize = () => {
    const value = {
      summary: summary.value.trim(), outcome_state: outcomeState.value,
      evidence: splitLines(evidence.value),
      confidentiality: { contains_confidential: confidential.checked, external_use: external.value },
    };
    const textValues = {
      work_date: workDate.value, role: role.value.trim(), scope: scope.value.trim(),
      problem: problem.value.trim(), individual_contribution: contribution.value.trim(),
      team_result: ["qualitative", "quantitative"].includes(outcomeState.value) ? outcome.value.trim() : "",
    };
    for (const [key, item] of Object.entries(textValues)) if (item) value[key] = item;
    const direct = splitLines(actions.value);
    if (direct.length) value.direct_actions = direct;
    const measured = splitLines(metrics.value);
    if (outcomeState.value === "quantitative" && measured.length) value.metrics = measured;
    return value;
  };

  const doSave = async () => {
    if (saving) {
      const previousSaved = await saving;
      if (!previousSaved) return false;
      return dirty ? doSave() : true;
    }
    if (!dirty) return true;
    const savingVersion = editVersion;
    app.setSaveState("status.saving");
    saveFailed = false;
    const task = (async () => {
      try {
        const saved = await write("/api/workflows/draft", { session_ref: session.session_ref, revision, draft: serialize() });
        revision = saved.revision;
        notices.replaceChildren();
        if (savingVersion === editVersion) {
          dirty = false;
          app.setSaveState("status.saved");
          app.announce("success.draft_saved");
        } else {
          app.setSaveState("status.saving");
        }
        return true;
      } catch (error) {
        saveFailed = true;
        app.setSaveState("status.save_failed");
        notices.replaceChildren(errorPanel(error, error.code === "REVISION_STALE" ? app.refresh : doSave));
        return false;
      }
    })();
    saving = task;
    const saved = await task;
    if (saving === task) saving = null;
    return saved && dirty ? doSave() : saved;
  };
  const schedule = () => {
    editVersion += 1; dirty = true; saveFailed = false; app.setSaveState("status.saving");
    window.clearTimeout(timer); timer = window.setTimeout(doSave, 650);
  };
  form.addEventListener("input", schedule);
  const leave = async () => {
    window.clearTimeout(timer);
    if (saving) await saving.catch(() => null);
    if (dirty && !(await doSave())) return window.confirm(t("work.leave_failed"));
    return !saveFailed || window.confirm(t("work.leave_failed"));
  };
  app.setLeaveGuard(leave, cleanup);
  window.addEventListener("beforeunload", unload);

  const actionsBar = el("div", { className: "sticky-actions" });
  const save = button("action.save_now", doSave);
  const review = button("action.review_before_confirm", async () => {
    if (!form.reportValidity()) return;
    window.clearTimeout(timer);
    if (!(await doSave())) return;
    review.disabled = true;
    try {
      const proposed = await write("/api/workflows/propose", { session_ref: session.session_ref, revision });
      revision = proposed.revision;
      const proposal = proposed.proposal;
      approvalDialog(proposal.event, async () => {
        const approved = await write("/api/workflows/approve", { session_ref: session.session_ref, proposal_ref: proposal.ref, revision });
        revision = approved.revision;
      }, {
        context: [session.subject.context_label, session.subject.project_label, summary.value.trim()].filter(Boolean),
        onApproved: async () => {
          app.setLeaveGuard(null); app.setSaveState(null);
          const success = messagePanel("success", "success.experience_approved", "success.experience_approved_body");
          root.replaceChildren(success, el("div", { className: "next-actions" }, [routeLink("action.view_career", "/career", "primary"), routeLink("career.add_experience", "/career")]));
          queueMicrotask(() => success.focus());
        },
      });
    } catch (error) { notices.replaceChildren(errorPanel(error, app.refresh)); }
    finally { review.disabled = false; }
  }, "primary");
  const archive = button("action.archive", async () => {
    if (!window.confirm(t("work.archive_confirm"))) return;
    if (!(await leave())) return;
    try { await write("/api/workflows/archive", { session_ref: session.session_ref, revision }); app.setLeaveGuard(null); await app.navigate("/career/in-progress"); }
    catch (error) { notices.replaceChildren(errorPanel(error)); }
  }, "quiet");
  actionsBar.append(save, review, archive);
  root.append(form, actionsBar);
  return root;
}

function profileSummary(profile) {
  const container = el("div", { className: "profile-sections" });
  for (const [key, value] of Object.entries(profile || {})) {
    if (HIDDEN_REVIEW_FIELDS.has(key) || !FIELD_LABELS.has(key)) continue;
    const details = el("details", { className: "profile-section" });
    details.open = ["candidate_name", "value_candidates", "avoid_candidates"].includes(key);
    details.append(el("summary", { text: t(`field.${key}`) }), el("div", { className: "profile-section__body" }, valueNode(key, value, 0, "profile")));
    container.append(details);
  }
  return container;
}

function selfAnalysisWork(payload, app) {
  const root = page("self_analysis.eyebrow", "self_analysis.review_title", "self_analysis.review_intro");
  const session = payload.session;
  let revision = payload.revision;
  root.append(el("div", { className: "lifecycle-strip" }, [badge(session.status), el("span", { text: t("work.not_confirmed") })]));
  const notices = el("div", { className: "page-notices" }); root.append(notices);
  const profile = payload.draft?.profile;
  if (!profile) {
    root.append(messagePanel("warning", "self_analysis.no_profile_title", "self_analysis.no_profile_body"));
    const actions = el("div", { className: "next-actions" });
    if (locale() !== "en") {
      const worksheet = el("a", { className: "button button--secondary", text: t("self_analysis.open_worksheet"), attrs: { href: "/jiko/checklist.html", target: "_blank", rel: "noopener" } });
      actions.append(worksheet);
    }
    actions.append(button("self_analysis.load_reviewed", async () => {
      try { await write("/api/workflows/import-profile", { session_ref: session.session_ref, revision }); await app.refresh(); }
      catch (error) { notices.replaceChildren(errorPanel(error, app.refresh)); }
    }, "primary"), routeLink("action.return_self_analysis", "/self-analysis"));
    root.append(actions, el("p", { className: "handoff-note", text: t("self_analysis.host_handoff") }));
    return root;
  }
  root.append(profileSummary(profile));
  const review = button("action.review_before_confirm", async () => {
    try {
      const proposed = await write("/api/workflows/propose", { session_ref: session.session_ref, revision });
      revision = proposed.revision;
      approvalDialog(proposed.proposal.event, async () => {
        const approved = await write("/api/workflows/approve", { session_ref: session.session_ref, proposal_ref: proposed.proposal.ref, revision });
        revision = approved.revision;
      }, { before: proposed.review_before, effectKey: "review.effect_self_analysis", onApproved: () => {
        const success = messagePanel("success", "success.self_analysis_approved", "success.self_analysis_approved_body");
        root.replaceChildren(success, routeLink("action.return_home", "/", "primary"));
        queueMicrotask(() => success.focus());
      } });
    } catch (error) { notices.replaceChildren(errorPanel(error, app.refresh)); }
  }, "primary");
  root.append(el("div", { className: "sticky-actions" }, [review, routeLink("action.return_self_analysis", "/self-analysis", "quiet")]));
  return root;
}

async function workScreen(path, app) {
  const sessionRef = path.split("/").pop();
  const payload = await read(`/api/work?session_ref=${sessionRef}`);
  if (payload.session.workflow === "self_analysis") return selfAnalysisWork(payload, app);
  if (payload.session.workflow !== "career_inventory") {
    const root = page("work.editor_eyebrow", "work.unsupported_title", "work.unsupported_intro");
    root.append(routeLink("nav.applications", "/applications", "primary"));
    return root;
  }
  return careerDraftForm(payload, app);
}

async function selfAnalysisScreen(app) {
  const [profile, sessionPayload] = await Promise.all([read("/api/self-analysis"), read("/api/sessions")]);
  const root = page("self_analysis.eyebrow", "self_analysis.title", "self_analysis.intro");
  const sessions = (sessionPayload.sessions || []).filter((item) => item.workflow === "self_analysis");
  if (sessions.length) {
    root.append(el("section", { className: "section-block" }, [el("h2", { text: t("self_analysis.resume_title") }), el("div", { className: "compact-list" }, sessions.map((item) => sessionCard(item)))]));
  }
  if (profile.state === "available") {
    root.append(el("section", { className: "section-block" }, [el("div", { className: "section-heading" }, [el("h2", { text: t("self_analysis.reviewed_profile_title") }), el("span", { className: "input-state", text: t("input.needs_review") })]), profileSummary(profile.profile)]));
  } else if (profile.state === "invalid") {
    root.append(messagePanel("error", "self_analysis.invalid_title", "self_analysis.invalid_body"));
  } else {
    root.append(messagePanel("warning", "self_analysis.empty_title", "self_analysis.empty_body"));
  }
  const start = button(sessions.length ? "action.start_another" : "action.start_new", async () => {
    try { const result = await write("/api/workflows/start", { workflow: "self_analysis", subject: { profile_label: t("self_analysis.title") } }); await app.navigate(workflowHref(result.session)); }
    catch (error) { root.prepend(errorPanel(error, app.refresh)); }
  }, "primary");
  root.append(el("div", { className: "next-actions" }, [start]));
  return root;
}

function applicationForms(payload, app) {
  const panel = el("section", { className: "section-block" });
  const companyDetails = el("details", { className: "create-panel" }, el("summary", { text: t("applications.add_company") }));
  const companyForm = el("form", { className: "form-grid form-grid--compact" });
  const companyName = textInput("company"); companyName.required = true;
  const companyResult = el("div", { className: "form-result" });
  const companySubmit = button("action.create", () => {}, "primary"); companySubmit.type = "submit";
  companyForm.append(field("applications.company_name", companyName), companySubmit, companyResult);
  companyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const duplicate = (payload.companies || []).find((item) => item.label.trim().toLocaleLowerCase() === companyName.value.trim().toLocaleLowerCase());
    if (duplicate && !window.confirm(t("applications.duplicate_company_confirm", { label: duplicate.label }))) return;
    try {
      await write("/api/applications/companies", { label: companyName.value.trim() });
      await app.refresh();
      app.announce(["success.company_created", "success.company_next"]);
    }
    catch (error) { companyResult.replaceChildren(errorPanel(error)); }
  });
  companyDetails.append(companyForm);

  const positionDetails = el("details", { className: "create-panel" }, el("summary", { text: t("applications.add_position") }));
  const positionForm = el("form", { className: "form-grid" });
  const company = el("select", { name: "company_ref" });
  const activeCompanies = (payload.companies || []).filter((item) => item.status === "active");
  activeCompanies.forEach((item) => company.append(el("option", { value: item.ref, text: item.label })));
  const position = textInput("position"); position.required = true;
  const jd = textArea("jd");
  const evidenceBox = el("fieldset", { className: "evidence-picker" }, el("legend", { text: t("applications.select_evidence") }));
  const evidenceOptions = payload.evidence_options || [];
  const evidenceSearch = textInput("evidence-search", "", "search");
  evidenceSearch.placeholder = t("applications.evidence_search");
  const evidenceRows = el("div", { className: "evidence-options" });
  const evidenceCount = el("p", { className: "result-count", attrs: { "aria-live": "polite" } });
  const chosenEvidence = new Set();
  const renderEvidence = () => {
    const query = evidenceSearch.value.trim().toLocaleLowerCase();
    const matches = evidenceOptions.filter((option) => !query || `${option.label || ""} ${option.context || ""}`.toLocaleLowerCase().includes(query));
    evidenceRows.replaceChildren();
    matches.slice(0, 20).forEach((option) => {
      const refValue = option.refs.join(",");
      const input = el("input", { type: "checkbox", value: refValue, checked: chosenEvidence.has(refValue) });
      input.disabled = option.sharing !== "available";
      input.addEventListener("change", () => input.checked ? chosenEvidence.add(refValue) : chosenEvidence.delete(refValue));
      evidenceRows.append(el("label", { className: "check-row" }, [input, el("span", {}, [
        el("strong", { text: option.contains_confidential ? t("career.confidential_experience") : (option.label || t("career.experience")) }),
        el("small", { text: option.context || t("common.unknown") }),
        option.work_date ? el("small", { text: formatDate(option.work_date) }) : null,
        option.sharing !== "available" ? el("small", { className: "confidential-note", text: t(option.sharing === "blocked" ? "applications.evidence_share_blocked" : "applications.evidence_share_review") }) : null,
      ])]));
    });
    if (!matches.length) evidenceRows.append(el("p", { className: "muted", text: evidenceOptions.length ? t("search.no_results") : t("applications.no_evidence") }));
    evidenceCount.textContent = t("search.result_count", { shown: Math.min(matches.length, 20), total: matches.length });
  };
  evidenceSearch.addEventListener("input", renderEvidence);
  evidenceBox.append(evidenceSearch, evidenceCount, evidenceRows);
  renderEvidence();
  const positionResult = el("div", { className: "form-result" });
  const positionSubmit = button("applications.add_position", () => {}, "primary"); positionSubmit.type = "submit";
  positionSubmit.disabled = !activeCompanies.length;
  positionForm.append(field("applications.target_company", company), field("applications.position", position), field("applications.jd", jd, "applications.jd_help"), evidenceBox, el("p", { className: "field__help", text: t("applications.evidence_help") }), positionSubmit, positionResult);
  if (!activeCompanies.length) positionResult.append(el("p", { text: t("applications.add_company_first") }));
  positionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const refs = [...chosenEvidence].flatMap((item) => item.split(",")).filter(Boolean);
    try {
      await write("/api/applications/positions", { company_ref: company.value, label: position.value.trim(), jd: jd.value.trim() ? { text: jd.value.trim() } : {}, evidence_refs: refs, document_kinds: [] });
      await app.refresh();
      app.announce(["success.application_created", "success.application_next"]);
    }
    catch (error) { positionResult.replaceChildren(errorPanel(error)); }
  });
  positionDetails.append(positionForm);
  panel.append(companyDetails, positionDetails);
  return panel;
}

function documentOpenControl(document) {
  const details = el("details", { className: "document-open" });
  details.append(el("summary", { text: t("action.open_document") }));
  const content = el("div", { className: "document-open__content" });
  let loaded = false;
  let loading = false;
  details.addEventListener("toggle", async () => {
    if (!details.open || loaded || loading) return;
    loading = true;
    content.replaceChildren(el("p", { className: "muted", text: t("state.loading") }));
    try {
      const payload = await read(`/api/artifact-body?artifact_ref=${encodeURIComponent(document.ref)}`);
      content.replaceChildren(
        payload.matches_record === false ? el("p", { className: "confidential-note", text: t("documents.edited_warning") }) : null,
        el("pre", { className: "document-body", text: payload.body }),
      );
      loaded = true;
    } catch (error) {
      content.replaceChildren(errorPanel(error));
    } finally {
      loading = false;
    }
  });
  details.append(content);
  return details;
}

function applicationDocumentForm(position, app) {
  const details = el("details", { className: "inline-create" }, el("summary", { text: t("applications.add_document") }));
  const form = el("form", { className: "form-grid form-grid--compact" });
  const type = selectInput("document_type", [
    ["resume", "enum.document.resume"], ["career_history", "enum.document.career_history"],
    ["self_pr", "enum.document.self_pr"], ["cover_letter", "enum.document.cover_letter"],
    ["other", "enum.document.other"],
  ], "resume");
  const body = textArea("document_body"); body.required = true;
  const sources = textArea("document_sources");
  const result = el("div", { className: "form-result" });
  const submit = button("action.save", () => {}, "primary"); submit.type = "submit";
  form.append(
    field("applications.document_type", type),
    field("applications.document_body", body, "applications.document_body_help"),
    field("applications.sources", sources, "applications.sources_help"),
    el("p", { className: "field__help", text: t("applications.document_evidence_help", { count: position.selected_evidence_count || 0 }) }),
    submit,
    result,
  );
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); submit.disabled = true;
    try {
      await write("/api/applications/documents", {
        case_ref: position.ref,
        document_type: type.value,
        body: body.value.trim(),
        sources: splitLines(sources.value),
      });
      await app.refresh();
      app.announce(["success.document_saved", "success.document_next"]);
    } catch (error) { result.replaceChildren(errorPanel(error)); }
    finally { submit.disabled = false; }
  });
  details.append(form);
  return details;
}

function positionTree(position, company, app) {
  const details = el("details", { className: "project-tree" });
  details.append(el("summary", {}, [el("span", { className: "tree-marker", text: t("applications.position") }), el("strong", { text: position.label }), caseBadge(position.status)]));
  const body = el("div", { className: "tree-body" });
  body.append(el("p", { text: Object.keys(position.jd || {}).length ? t("applications.jd_present") : t("applications.jd_missing") }), el("p", { text: t("applications.evidence_selected", { count: position.selected_evidence_count || 0 }) }));
  const docs = position.documents || [];
  if (docs.length) body.append(el("ul", { className: "document-list" }, docs.map((doc) => el("li", {}, [
    el("span", { text: enumText("document", doc.type) }),
    el("span", { className: "muted", text: t("documents.version", { version: doc.version }) }),
    el("span", { className: "muted", text: t("documents.evidence_count", { count: doc.evidence_count || 0 }) }),
    documentOpenControl(doc),
  ]))));
  const research = el("details", { className: "inline-create" }, el("summary", { text: t("applications.add_research") }));
  const form = el("form", { className: "form-grid form-grid--compact" });
  const bodyText = textArea("research"); bodyText.required = true;
  const sources = textArea("sources");
  const result = el("div", { className: "form-result" });
  const submit = button("action.save", () => {}, "primary"); submit.type = "submit";
  form.append(field("applications.research", bodyText), field("applications.sources", sources, "applications.sources_help"), submit, result);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await write("/api/applications/research", { case_ref: position.ref, body: bodyText.value.trim(), sources: splitLines(sources.value) });
      await app.refresh();
      app.announce(["success.research_saved", "success.research_next"]);
    }
    catch (error) { result.replaceChildren(errorPanel(error)); }
  });
  research.append(form);
  if (position.status === "active") body.append(research, applicationDocumentForm(position, app));
  const lifecycle = caseLifecycleControls(position, app);
  if (lifecycle) body.append(lifecycle);
  details.append(body); return details;
}

async function applicationsScreen(app) {
  const payload = await read("/api/applications");
  const root = page("applications.eyebrow", "applications.title", "applications.intro");
  root.append(applicationForms(payload, app));
  const search = textInput("application-search", "", "search"); search.placeholder = t("search.applications_placeholder");
  const list = el("div", { className: "career-tree" });
  let limit = 10;
  const more = button("action.show_more", () => { limit += 10; render(); });
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const companies = (payload.companies || []).filter((company) => !query || `${company.label} ${(company.positions || []).map((item) => item.label).join(" ")}`.toLocaleLowerCase().includes(query));
    list.replaceChildren(...companies.slice(0, limit).map((company, index) => {
      const details = el("details", { className: "context-tree" }); details.open = index < 3;
      details.append(el("summary", {}, [el("span", { className: "tree-marker", text: t("applications.target_company") }), el("strong", { text: company.label }), caseBadge(company.status), el("span", { className: "count-pill", text: (company.positions || []).length })]));
      const body = el("div", { className: "tree-body" }, (company.positions || []).map((position) => positionTree(position, company, app)));
      if (!(company.positions || []).length) body.append(el("p", { className: "empty-inline", text: t("applications.no_positions") }));
      const lifecycle = caseLifecycleControls(company, app);
      if (lifecycle) body.append(lifecycle);
      details.append(body); return details;
    }));
    if (!companies.length) list.append(el("section", { className: "state-panel state-panel--empty" }, [el("h2", { text: t(query ? "search.no_results" : "applications.empty_title") }), el("p", { text: t(query ? "search.adjust" : "applications.empty_body") })]));
    more.hidden = companies.length <= limit;
  };
  search.addEventListener("input", render); root.append(el("div", { className: "toolbar" }, search), list, more); render(); return root;
}

async function documentsScreen() {
  const payload = await read("/api/documents");
  const root = page("documents.eyebrow", "documents.title", "documents.intro");
  const search = textInput("document-search", "", "search"); search.placeholder = t("search.documents_placeholder");
  const list = el("div", { className: "document-grid" });
  let limit = 24;
  const more = button("action.show_more", () => { limit += 24; render(); });
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const rows = (payload.documents || []).filter((item) => !query || `${item.company} ${item.position} ${enumText("document", item.type)}`.toLocaleLowerCase().includes(query));
    list.replaceChildren(...rows.slice(0, limit).map((item) => el("article", { className: "document-card" }, [
      el("p", { className: "eyebrow", text: enumText("document", item.type) }),
      el("h2", { text: item.position }),
      el("p", { text: item.company }),
      el("p", { className: "muted", text: t("documents.version", { version: item.version }) }),
      el("p", { className: "muted", text: t("documents.evidence_count", { count: item.evidence_count || 0 }) }),
      el("p", { className: "muted", text: dateTimeText(item.updated_at) }),
      documentOpenControl(item),
    ])));
    if (!rows.length) list.append(el("section", { className: "state-panel state-panel--empty" }, [el("h2", { text: t(query ? "search.no_results" : "documents.empty_title") }), el("p", { text: t(query ? "search.adjust" : "documents.empty_body") }), routeLink("nav.applications", "/applications", "primary")]));
    more.hidden = rows.length <= limit;
  };
  search.addEventListener("input", render); root.append(el("div", { className: "toolbar" }, search), list, more); render(); return root;
}

export async function renderRoute(path, app) {
  if (path === "/") return homeScreen(app);
  if (path === "/career") return careerScreen(app);
  if (path === "/career/in-progress") return inProgressScreen(app);
  if (path === "/career/timeline") return timelineScreen(app);
  if (path === "/self-analysis") return selfAnalysisScreen(app);
  if (path === "/applications") return applicationsScreen(app);
  if (path === "/documents") return documentsScreen(app);
  if (/^\/work\/session-[a-f0-9]{12,64}$/.test(path)) return workScreen(path, app);
  const root = page("state.error_label", "state.not_found", "state.not_found_help");
  root.append(routeLink("action.return_home", "/", "primary"));
  return root;
}
