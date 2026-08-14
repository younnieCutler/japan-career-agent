/* Applications and documents.

   A company and an application are separate records here, as they are in the Vault: you can be
   researching an employer without having applied. Evidence attached to an application is chosen
   from confirmed experiences and never invented, and an experience whose sharing is blocked cannot
   be picked at all — the checkbox is disabled rather than hidden, so the constraint is legible
   instead of mysterious.

   Documents are shown as a table because that is what the user is doing with them: comparing
   versions across companies. No board, no funnel, no stage progression — the product does not
   model a pipeline and drawing one would invent a process it has no evidence for. */

import React from "react";
import { ActionButton, Callout, Text, TextField } from "@seed-design/react";
import { read, write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { CaseChip } from "../evidence.jsx";
import { EmptyState, ErrorState, LoadingState, useAsync } from "../components/States.jsx";
import { navigate, setSelection, useLocation } from "../App.jsx";
import { Block, CheckBox, Choice, Field, Line } from "../components/Fields.jsx";
import { LifecycleControl } from "./CareerForms.jsx";

const PAGE_SIZE = 25;
const splitLines = (value) => String(value || "")
  .split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

/* A document body is fetched only when asked for. `matches_record: false` means the file on disk
   has been edited outside the app, which the user needs to know before quoting it anywhere. */
function DocumentBody({ artifactRef }) {
  const { t } = useI18n();
  const [state, setState] = React.useState({ status: "idle" });

  const open = async () => {
    setState({ status: "loading" });
    try {
      const payload = await read(`/api/artifact-body?artifact_ref=${encodeURIComponent(artifactRef)}`);
      setState({ status: "ready", payload });
    } catch (error) { setState({ status: "failed", error }); }
  };

  if (state.status === "idle") {
    return (
      <ActionButton variant="neutralOutline" size="xsmall" onClick={open}>
        {t("action.open_document")}
      </ActionButton>
    );
  }
  if (state.status === "loading") return <Text textStyle="t2Regular">{t("state.loading")}</Text>;
  if (state.status === "failed") return <ErrorState error={state.error} onRetry={open} />;
  return (
    <div className="stack">
      {state.payload.matches_record === false ? (
        <Callout.Root tone="warning">
          <Callout.Content>
            <Callout.Description>{t("documents.edited_warning")}</Callout.Description>
          </Callout.Content>
        </Callout.Root>
      ) : null}
      <pre className="document-body">{state.payload.body}</pre>
    </div>
  );
}

export function AddCompany({ companies, existing = null, onDone }) {
  const { t } = useI18n();
  const [label, setLabel] = React.useState(existing?.label || "");
  const [failure, setFailure] = React.useState(null);

  const submit = async (event) => {
    event.preventDefault();
    const name = label.trim();
    if (!name) return;
    const duplicate = companies.find(
      (item) => item.ref !== existing?.ref
        && item.label.trim().toLocaleLowerCase() === name.toLocaleLowerCase());
    if (duplicate && !window.confirm(t("applications.duplicate_company_confirm", { label: duplicate.label }))) return;
    try {
      await write("/api/applications/companies", existing
        ? { case_ref: existing.ref, revision: existing.revision || existing.updated_at, label: name }
        : { label: name });
      if (!existing) setLabel("");
      onDone();
    } catch (error) { setFailure(error); }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <Field label={t("applications.company_name")}>
        <Line value={label} onChange={setLabel} />
      </Field>
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium">{t(existing ? "action.save" : "action.create")}</ActionButton>
      </div>
    </form>
  );
}

function EvidencePicker({ options, chosen, onToggle }) {
  const { t } = useI18n();
  const [query, setQuery] = React.useState("");
  const matches = options.filter((option) => !query
    || `${option.label || ""} ${option.context || ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  return (
    <fieldset className="form-section">
      <legend>{t("applications.select_evidence")}</legend>
      <TextField.Root size="medium">
        <TextField.Input
          placeholder={t("applications.evidence_search")}
          aria-label={t("applications.evidence_search")}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </TextField.Root>
      <p className="result-count" aria-live="polite">
        {t("search.result_count", { shown: Math.min(matches.length, 20), total: matches.length })}
      </p>
      {matches.length ? (
        <ul className="lines">
          {matches.slice(0, 20).map((option) => {
            const value = option.refs.join(",");
            const blocked = option.sharing !== "available";
            return (
              <li className="line" key={value}>
                <CheckBox
                  checked={chosen.has(value)}
                  disabled={blocked}
                  onChange={() => onToggle(value)}
                  label={option.label || t("career.experience")}
                />
                <span className="line__label">
                  {option.contains_confidential ? t("career.confidential_experience")
                    : (option.label || t("career.experience"))}
                </span>
                <span className="line__tag">{option.context || t("common.unknown")}</span>
                {option.work_date ? <span className="figure">{option.work_date}</span> : null}
                {blocked ? (
                  <span className="confidential-note">
                    {t(option.sharing === "blocked"
                      ? "applications.evidence_share_blocked" : "applications.evidence_share_review")}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {options.length ? t("search.no_results") : t("applications.no_evidence")}
        </Text>
      )}
    </fieldset>
  );
}

function AddPosition({ payload, existing = null, onDone }) {
  const { t } = useI18n();
  const active = (payload.companies || []).filter((item) => item.status === "active");
  const [company, setCompany] = React.useState(existing?.parent_ref || active[0]?.ref || "");
  const [label, setLabel] = React.useState(existing?.label || "");
  const [jd, setJd] = React.useState(existing?.jd?.text || "");
  const [chosen, setChosen] = React.useState(() => new Set(existing?.selected_evidence_refs || []));
  const [failure, setFailure] = React.useState(null);

  const toggle = (value) => setChosen((current) => {
    const next = new Set(current);
    if (next.has(value)) next.delete(value); else next.add(value);
    return next;
  });

  if (!active.length) {
    return (
      <Callout.Root tone="warning">
        <Callout.Content>
          <Callout.Description>{t("applications.add_company_first")}</Callout.Description>
        </Callout.Content>
      </Callout.Root>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    if (!label.trim()) return;
    try {
      await write("/api/applications/positions", {
        ...(existing ? { case_ref: existing.ref, revision: existing.updated_at } : { company_ref: company }),
        label: label.trim(),
        jd: jd.trim() ? { text: jd.trim() } : {},
        evidence_refs: [...chosen].flatMap((item) => item.split(",")).filter(Boolean),
        document_kinds: [],
      });
      if (!existing) { setLabel(""); setJd(""); setChosen(new Set()); }
      onDone();
    } catch (error) { setFailure(error); }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <Field label={t("applications.target_company")}>
        <Choice
          value={company}
          onChange={setCompany}
          options={active.map((item) => [item.ref, item.label])}
          label={t("applications.target_company")}
        />
      </Field>
      <Field label={t("applications.position")}><Line value={label} onChange={setLabel} /></Field>
      <Field label={t("applications.jd")} help={t("applications.jd_help")}>
        <Block value={jd} onChange={setJd} />
      </Field>
      <EvidencePicker options={payload.evidence_options || []} chosen={chosen} onToggle={toggle} />
      <p className="field__help">{t("applications.evidence_help")}</p>
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium">
          {t(existing ? "action.save" : "applications.add_position")}
        </ActionButton>
      </div>
    </form>
  );
}

function AddDocument({ position, onDone }) {
  const { t } = useI18n();
  const [type, setType] = React.useState("resume");
  const [body, setBody] = React.useState("");
  const [sources, setSources] = React.useState("");
  const [failure, setFailure] = React.useState(null);

  const kinds = [
    ["resume", t("enum.document.resume")], ["career_history", t("enum.document.career_history")],
    ["self_pr", t("enum.document.self_pr")], ["cover_letter", t("enum.document.cover_letter")],
    ["other", t("enum.document.other")],
  ];

  const submit = async (event) => {
    event.preventDefault();
    if (!body.trim()) return;
    try {
      await write("/api/applications/documents", {
        case_ref: position.ref,
        document_type: type,
        body: body.trim(),
        sources: splitLines(sources),
      });
      setBody(""); setSources("");
      onDone();
    } catch (error) { setFailure(error); }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <Field label={t("applications.document_type")}>
        <Choice
          value={type}
          onChange={setType}
          options={kinds}
          label={t("applications.document_type")}
        />
      </Field>
      <Field label={t("applications.document_body")} help={t("applications.document_body_help")}>
        <Block value={body} onChange={setBody} rows={8} />
      </Field>
      <Field label={t("applications.sources")} help={t("applications.sources_help")}>
        <Block value={sources} onChange={setSources} />
      </Field>
      <p className="field__help">
        {t("applications.document_evidence_help", { count: position.selected_evidence_count || 0 })}
      </p>
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium">{t("action.save")}</ActionButton>
      </div>
    </form>
  );
}

function AddResearch({ position, existing = null, onDone }) {
  const { t } = useI18n();
  const [body, setBody] = React.useState("");
  const [sources, setSources] = React.useState("");
  const [failure, setFailure] = React.useState(null);

  React.useEffect(() => {
    if (!existing?.ref) return;
    read(`/api/artifact-body?artifact_ref=${encodeURIComponent(existing.ref)}`)
      .then((payload) => setBody(payload.body || ""))
      .catch(setFailure);
  }, [existing?.ref]);

  const submit = async (event) => {
    event.preventDefault();
    if (!body.trim()) return;
    try {
      await write("/api/applications/research", existing
        ? { artifact_id: existing.ref, revision: existing.revision, body: body.trim() }
        : { case_ref: position.ref, body: body.trim(), sources: splitLines(sources) });
      if (!existing) { setBody(""); setSources(""); }
      onDone();
    } catch (error) { setFailure(error); }
  };

  return (
    <form className="stack" onSubmit={submit}>
      <Field label={t("applications.research")}><Block value={body} onChange={setBody} /></Field>
      <Field label={t("applications.sources")} help={t("applications.sources_help")}>
        <Block value={sources} onChange={setSources} />
      </Field>
      {failure ? <ErrorState error={failure} /> : null}
      <div>
        <ActionButton type="submit" variant="brandSolid" size="medium">{t("action.save")}</ActionButton>
      </div>
    </form>
  );
}

function PositionRecord({ position, company, payload, onDone }) {
  const { t } = useI18n();
  const documents = position.documents || [];
  return (
    <div className="record">
      <div className="record__head">
        <Text textStyle="t7Bold">{position.label}</Text>
        <CaseChip state={position.status} />
      </div>
      <dl className="facts">
        <dt>{t("applications.target_company")}</dt><dd>{company?.label}</dd>
        <dt>{t("applications.jd")}</dt>
        <dd>{Object.keys(position.jd || {}).length ? t("applications.jd_present") : t("applications.jd_missing")}</dd>
        <dt>{t("applications.select_evidence")}</dt>
        <dd>{t("applications.evidence_selected", { count: position.selected_evidence_count || 0 })}</dd>
      </dl>

      <section className="record__section">
        <h3 className="record__section-title">{t("nav.documents")}</h3>
        {documents.length ? (
          <ul className="lines">
            {documents.map((doc) => (
              <li className="line" key={doc.ref}>
                <span className="line__label">{t(`enum.document.${doc.type}`)}</span>
                <span className="figure">{t("documents.version", { version: doc.version })}</span>
                <span className="line__tag">
                  {t("documents.evidence_count", { count: doc.evidence_count || 0 })}
                </span>
                <DocumentBody artifactRef={doc.ref} />
              </li>
            ))}
          </ul>
        ) : <Text textStyle="t3Regular">{t("documents.empty_body")}</Text>}
      </section>

      {position.status === "active" ? (
        <>
          <details className="record__section">
            <summary>{t("action.edit")}</summary>
            <AddPosition key={position.ref} payload={payload} existing={position} onDone={onDone} />
          </details>
          <details className="record__section">
            <summary>{t("applications.add_research")}</summary>
            <AddResearch position={position} onDone={onDone} />
          </details>
          {position.research ? <details className="record__section">
            <summary>{t("action.edit")}</summary>
            <AddResearch position={position} existing={position.research} onDone={onDone} />
          </details> : null}
          <details className="record__section">
            <summary>{t("applications.add_document")}</summary>
            <AddDocument position={position} onDone={onDone} />
          </details>
        </>
      ) : null}
      <LifecycleControl item={position} onDone={onDone} />
    </div>
  );
}

function CompanyRecord({ company, onSelect, onDone }) {
  const { t } = useI18n();
  const positions = company.positions || [];
  return (
    <div className="record">
      <div className="record__head">
        <Text textStyle="t7Bold">{company.label}</Text>
        <CaseChip state={company.status} />
      </div>
      <section className="record__section">
        <h3 className="record__section-title">{t("applications.position")}</h3>
        {positions.length ? (
          <ul className="lines">
            {positions.map((position) => (
              <li className="line" key={position.ref}>
                <button type="button" className="line__link" onClick={() => onSelect(position.ref)}>
                  {position.label}
                </button>
                <CaseChip state={position.status} />
                <span className="line__tag">
                  {t("applications.evidence_selected", { count: position.selected_evidence_count || 0 })}
                </span>
              </li>
            ))}
          </ul>
        ) : <Text textStyle="t3Regular">{t("applications.no_positions")}</Text>}
      </section>
      {company.status === "active" ? <details className="record__section">
        <summary>{t("action.edit")}</summary>
        <AddCompany key={company.ref} companies={[company]} existing={company} onDone={onDone} />
      </details> : null}
      <LifecycleControl item={company} onDone={onDone} />
    </div>
  );
}

export default function ApplicationsScreen() {
  const { t } = useI18n();
  const [reloads, setReloads] = React.useState(0);
  const state = useAsync(() => read("/api/applications"), [reloads]);
  const { search } = useLocation();
  const selected = new URLSearchParams(search).get("sel");
  const [query, setQuery] = React.useState("");
  const [shown, setShown] = React.useState(PAGE_SIZE);
  const reload = () => setReloads((count) => count + 1);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} onRetry={reload} />;

  const companies = state.data.companies || [];
  const rows = [];
  for (const company of companies) {
    rows.push({ kind: "company", depth: 0, ref: company.ref, label: company.label, node: company });
    for (const position of company.positions || []) {
      rows.push({
        kind: "position", depth: 1, ref: position.ref, label: position.label,
        node: position, parent: company,
      });
    }
  }
  const matches = rows.filter((row) => !query
    || `${row.label} ${row.parent?.label || ""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const current = rows.find((row) => row.ref === selected);

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("applications.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("applications.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("applications.intro")}
        </Text>
      </header>

      <details className="record__section">
        <summary>{t("applications.add_company")}</summary>
        <AddCompany companies={companies} onDone={reload} />
      </details>
      <details className="record__section">
        <summary>{t("applications.add_position")}</summary>
        <AddPosition payload={state.data} onDone={reload} />
      </details>

      <div className="split" data-record-open={current ? "true" : undefined}>
        <div className="split__index">
          <div className="toolbar">
            <TextField.Root size="medium">
              <TextField.Input
                placeholder={t("search.applications_placeholder")}
                aria-label={t("search.applications_placeholder")}
                value={query}
                onChange={(event) => { setQuery(event.target.value); setShown(PAGE_SIZE); }}
              />
            </TextField.Root>
          </div>
          <p className="result-count" aria-live="polite">
            {t("search.result_count", { shown: Math.min(matches.length, shown), total: matches.length })}
          </p>
          {matches.length ? (
            <div>
              {matches.slice(0, shown).map((row) => (
                <button
                  type="button"
                  key={row.ref}
                  className="row"
                  data-depth={row.depth}
                  data-tone={row.node.status === "archived" ? "neutral" : "positive"}
                  data-selected={row.ref === selected ? "true" : undefined}
                  aria-current={row.ref === selected ? "true" : "false"}
                  onClick={() => setSelection(row.ref)}
                >
                  <span className="row__label">{row.label}</span>
                  <span className="row__chips"><CaseChip state={row.node.status} /></span>
                  <span className="row__meta">
                    {row.kind === "company" ? (row.node.positions || []).length : ""}
                  </span>
                </button>
              ))}
              {matches.length > shown ? (
                <ActionButton variant="neutralWeak" size="small" onClick={() => setShown(shown + PAGE_SIZE)}>
                  {t("action.show_more")}
                </ActionButton>
              ) : null}
            </div>
          ) : (
            <EmptyState
              titleKey={query ? "search.no_results" : "applications.empty_title"}
              bodyKey={query ? "search.adjust" : "applications.empty_body"}
            />
          )}
        </div>

        <div className="split__record" aria-live="polite">
          <ActionButton className="back-to-index" variant="ghost" size="small" onClick={() => setSelection(null)}>
            {t("applications.title")}
          </ActionButton>
          {current ? (
            current.kind === "company"
              ? <CompanyRecord company={current.node} onSelect={setSelection} onDone={reload} />
              : <PositionRecord position={current.node} company={current.parent} payload={state.data} onDone={reload} />
          ) : (
            <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
              {t("applications.intro")}
            </Text>
          )}
        </div>
      </div>
    </div>
  );
}

export function DocumentsScreen() {
  const { t, dateTimeText } = useI18n();
  const state = useAsync(() => read("/api/documents"), []);
  const [query, setQuery] = React.useState("");
  const [shown, setShown] = React.useState(PAGE_SIZE);

  if (state.status === "loading") return <LoadingState />;
  if (state.status === "failed") return <ErrorState error={state.error} />;

  const rows = (state.data.documents || []).filter((item) => !query
    || `${item.company} ${item.position} ${t(`enum.document.${item.type}`)}`
      .toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  return (
    <div className="stack">
      <header className="page-header">
        <Text textStyle="t2Bold" style={{ color: "var(--seed-color-fg-neutral-muted)", display: "block" }}>
          {t("documents.eyebrow")}
        </Text>
        <Text textStyle="t8Bold" style={{ display: "block" }}>{t("documents.title")}</Text>
        <Text textStyle="t4Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t("documents.intro")}
        </Text>
      </header>

      <div className="toolbar">
        <TextField.Root size="medium">
          <TextField.Input
            placeholder={t("search.documents_placeholder")}
            aria-label={t("search.documents_placeholder")}
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
          <table className="ledger">
            <thead>
              <tr>
                <th>{t("applications.document_type")}</th>
                <th>{t("applications.position")}</th>
                <th>{t("applications.target_company")}</th>
                <th>{t("documents.version", { version: "" })}</th>
                <th>{t("review.evidence_title")}</th>
                <th>{t("date.when")}</th>
                <th><span className="sr-only">{t("action.open_document")}</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, shown).map((item) => (
                <tr key={item.ref}>
                  <td>{t(`enum.document.${item.type}`)}</td>
                  <td>{item.position}</td>
                  <td>{item.company}</td>
                  <td className="figure">{item.version}</td>
                  <td className="figure">{item.evidence_count || 0}</td>
                  <td className="figure">{dateTimeText(item.updated_at)}</td>
                  <td><DocumentBody artifactRef={item.ref} /></td>
                </tr>
              ))}
            </tbody>
          </table>
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
          titleKey={query ? "search.no_results" : "documents.empty_title"}
          bodyKey={query ? "search.adjust" : "documents.empty_body"}
          action={(
            <ActionButton variant="brandSolid" size="medium" onClick={() => navigate("/applications")}>
              {t("nav.applications")}
            </ActionButton>
          )}
        />
      )}
    </div>
  );
}
