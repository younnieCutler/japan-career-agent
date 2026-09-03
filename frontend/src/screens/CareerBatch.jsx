import React from "react";
import { ActionButton, Callout, Text } from "@seed-design/react";
import { write } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { ErrorState } from "../components/States.jsx";
import { SnapshotView } from "../review.jsx";

const isCanonical = (ref) => String(ref || "").startsWith("canonical:");

function pendingDrafts(payload) {
  const rows = [];
  for (const context of payload.contexts || []) {
    if (context.lifecycle !== "approved" && context.lifecycle !== "archived" && !isCanonical(context.ref)) {
      rows.push(context);
    }
    for (const project of context.projects || []) {
      if (project.lifecycle !== "approved" && project.lifecycle !== "archived" && !isCanonical(project.ref)) {
        rows.push(project);
      }
    }
  }
  return rows;
}

/* This is deliberately a UI batch, not a new backend transaction. Every item gets its ordinary
   server proposal first, all proposal snapshots are shown, and one user action then applies those
   already-reviewed proposals in order. A failure stops immediately and is never presented as all
   confirmed. */
export default function CareerBatch({ payload, onDone }) {
  const { t } = useI18n();
  const items = pendingDrafts(payload);
  const [reviews, setReviews] = React.useState(null);
  const [failure, setFailure] = React.useState(null);
  const [busy, setBusy] = React.useState(false);

  if (!items.length) return null;

  const prepare = async () => {
    setBusy(true);
    setFailure(null);
    try {
      const prepared = [];
      for (const item of items) {
        const review = await write("/api/career/propose", { case_ref: item.ref, revision: item.revision });
        prepared.push({ item, review });
      }
      setReviews(prepared);
    } catch (error) { setFailure(error); }
    finally { setBusy(false); }
  };

  const approve = async () => {
    setBusy(true);
    setFailure(null);
    let applied = 0;
    try {
      for (const entry of reviews || []) {
        await write("/api/career/approve", {
          case_ref: entry.item.ref,
          proposal_ref: entry.review.proposal.ref,
          revision: entry.review.revision,
        });
        applied += 1;
      }
      setReviews(null);
      onDone();
    } catch (error) {
      setFailure(error);
      if (applied) onDone();
    } finally { setBusy(false); }
  };

  return (
    <section className="record__section stack">
      <div className="inline">
        <Text textStyle="t5Bold">{t("review.title")}</Text>
        <span className="figure">{items.length}</span>
      </div>
      {!reviews ? (
        <div>
          <ActionButton variant="neutralWeak" size="medium" onClick={prepare} disabled={busy}>
            {t("action.review_before_confirm")}
          </ActionButton>
        </div>
      ) : (
        <>
          {reviews.map(({ item, review }) => (
            <article className="record" key={item.ref}>
              <Text textStyle="t4Bold">{item.label}</Text>
              <SnapshotView event={review.proposal.event} />
            </article>
          ))}
          <Callout.Root tone="informative">
            <Callout.Content>
              <Callout.Description>{t("review.effect_career")}</Callout.Description>
            </Callout.Content>
          </Callout.Root>
          <div className="inline">
            <ActionButton variant="neutralWeak" size="medium" onClick={() => setReviews(null)} disabled={busy}>
              {t("action.keep_editing")}
            </ActionButton>
            <ActionButton variant="brandSolid" size="medium" onClick={approve} disabled={busy}>
              {t("action.approve")}
            </ActionButton>
          </div>
        </>
      )}
      {failure ? <ErrorState error={failure} /> : null}
    </section>
  );
}
