import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { write } from "../api.js";
import { navigate } from "../App.jsx";
import { useI18n } from "../i18n.jsx";
import { Choice } from "../components/Fields.jsx";

const DIMENSIONS = [
  "responsibility", "problem_framing", "judgment", "decision_basis", "risk_management",
  "direct_action", "stakeholder_coordination", "organizational_context", "outcome",
  "quantification", "reflection",
];

const listText = (value, separator) => Array.isArray(value) ? value.join(separator) : value;

function DetailFacts({ detail }) {
  const { t } = useI18n();
  const separator = t("common.list_separator");
  const rows = [
    [t("workflow.responsibility"), detail.responsibility],
    [t("workflow.problem"), detail.problem],
    [t("workflow.judgment"), detail.judgment],
    [t("workflow.decision_basis"), detail.decision_basis],
    [t("workflow.risk_management"), detail.risk_management],
    [t("workflow.actions"), listText(detail.direct_actions, separator)],
    [t("workflow.stakeholder_coordination"), listText(detail.stakeholder_coordination, separator)],
    [t("workflow.organizational_context"), detail.organizational_context],
    [t("workflow.contribution"), detail.individual_contribution],
    [t("workflow.outcome_detail"), detail.team_result],
    [t("workflow.metrics"), listText(detail.metrics, separator)],
    [t("workflow.improvements"), listText(detail.improvements, separator)],
    [t("workflow.learning"), listText(detail.learning, separator)],
  ].filter(([, value]) => value !== null && value !== undefined && value !== "");
  if (!rows.length) return <Text textStyle="t3Regular">{t("career.monthly.no_detail")}</Text>;
  return (
    <dl className="facts">
      {rows.map(([label, value]) => (
        <React.Fragment key={label}><dt>{label}</dt><dd>{value}</dd></React.Fragment>
      ))}
    </dl>
  );
}

function DimensionNames({ names }) {
  const { t } = useI18n();
  if (!names?.length) return null;
  return <span>{names.map((name) => t(`career.dimension.${name}`)).join(t("common.list_separator"))}</span>;
}

export default function MonthlyCareerReview({ months = [], onError }) {
  const { t } = useI18n();
  const [selected, setSelected] = React.useState(months[0]?.month || "");
  React.useEffect(() => {
    if (!months.some((month) => month.month === selected)) setSelected(months[0]?.month || "");
  }, [months, selected]);

  const startExperience = async () => {
    try {
      const started = await write("/api/workflows/start", { workflow: "career_inventory" });
      navigate(`/work/${started.session.session_ref || started.session.session_id}`);
    } catch (error) { onError(error); }
  };

  const reviseExperience = async (experience) => {
    try {
      const started = await write("/api/career/experiences/revise", {
        event_id: experience.ref, revision: experience.ref,
      });
      navigate(`/work/${started.session.session_ref}`);
    } catch (error) { onError(error); }
  };

  if (!months.length) {
    return (
      <section className="record monthly-review" data-monthly-career-review="empty">
        <div className="record__head"><Text textStyle="t6Bold">{t("career.monthly.title")}</Text></div>
        <Text textStyle="t3Regular">{t("career.monthly.intro")}</Text>
        <Text textStyle="t3Regular">{t("career.monthly.empty")}</Text>
        <div><ActionButton variant="neutralWeak" size="small" onClick={startExperience}>{t("career.monthly.add")}</ActionButton></div>
      </section>
    );
  }

  const current = months.find((month) => month.month === selected) || months[0];
  const coverage = current.coverage || {};
  const gaps = current.gaps || [];
  const partial = current.partial || [];
  return (
    <section className="record monthly-review" data-monthly-career-review={current.month}>
      <div className="record__head">
        <Text textStyle="t6Bold">{t("career.monthly.title")}</Text>
        <span className="figure">{t("career.monthly.evidence_count", { count: current.evidence_count || 0 })}</span>
      </div>
      <Text textStyle="t3Regular">{t("career.monthly.intro")}</Text>
      <div className="toolbar">
        <Choice value={current.month} onChange={setSelected} options={months.map((month) => [month.month, month.month])} label={t("career.monthly.title")} />
        <ActionButton variant="neutralWeak" size="small" onClick={startExperience}>{t("career.monthly.add")}</ActionButton>
      </div>

      <section className="record__section">
        <h3 className="record__section-title">{t("career.monthly.coverage")}</h3>
        <ul className="lines">
          {DIMENSIONS.map((name) => {
            const row = coverage[name] || { present: 0, total: current.evidence_count || 0 };
            return (
              <li className="line" key={name}>
                <span className="line__label">{t(`career.dimension.${name}`)}</span>
                <span className="figure">{t("career.monthly.coverage_count", row)}</span>
              </li>
            );
          })}
        </ul>
        {gaps.length ? (
          <Callout.Root tone="warning"><Callout.Content><Callout.Title>{t("career.monthly.gaps")}</Callout.Title><Callout.Description><DimensionNames names={gaps} /></Callout.Description></Callout.Content></Callout.Root>
        ) : <Text textStyle="t3Regular">{t("career.monthly.complete")}</Text>}
        {partial.length ? <p><strong>{t("career.monthly.partial")}</strong> · <DimensionNames names={partial} /></p> : null}
      </section>

      <section className="record__section">
        <h3 className="record__section-title">{t("career.monthly.experiences")}</h3>
        <div className="stack">
          {(current.experiences || []).map((experience) => (
            <article className="record" key={experience.ref}>
              <div className="record__head">
                <Text textStyle="t5Bold">{experience.contains_confidential ? t("career.confidential_experience") : experience.label}</Text>
                <span className="figure">{experience.work_date || current.month}</span>
              </div>
              {(experience.context_label || experience.project_label) ? (
                <p className="context-breadcrumb">{[experience.context_label, experience.project_label].filter(Boolean).join(t("common.breadcrumb_separator"))}</p>
              ) : null}
              {experience.contains_confidential ? (
                <Text textStyle="t3Regular">{t("confidentiality.hidden_review")}</Text>
              ) : <DetailFacts detail={experience.detail || {}} />}
              <div><ActionButton variant="ghost" size="small" onClick={() => reviseExperience(experience)}>{t("career.monthly.edit")}</ActionButton></div>
            </article>
          ))}
        </div>
      </section>
    </section>
  );
}

