/* Loading, empty, and failure surfaces.

   A failure has to say two things: what went wrong, and whether the Vault changed. The second is
   the one that matters on a local-first product — a user who cannot tell whether their record was
   touched has to go and check by hand. */

import React from "react";
import { ActionButton, Callout, ContentPlaceholder, Skeleton, Text } from "@seed-design/react";
import { useI18n } from "../i18n.jsx";

const ERROR_CODES = new Set([
  "INVALID_INPUT", "SAVE_FAILED", "REVISION_STALE", "PROPOSAL_STALE",
  "SESSION_COMPLETED", "SESSION_ARCHIVED", "SESSION_SCHEMA_NEWER",
  "SESSION_AMBIGUOUS", "SESSION_NOT_FOUND", "BROWSER_SESSION_EXPIRED",
  "APPROVAL_FAILED", "STATE_CORRUPTED", "INVALID_RELATIONSHIP",
  "PARENT_NOT_CONFIRMED", "CONTEXT_REQUIRED", "PROFILE_NOT_FOUND", "PROFILE_INVALID", "READ_FAILED",
  "CASE_HAS_ACTIVE_CHILDREN", "CASE_ALREADY_CONFIRMED",
]);

/* `LoadingIndicator` is SEED's in-button spinner and requires a pending-button context, so a
   standalone wait uses skeleton rows instead — which also shows the shape of what is arriving. */
export function LoadingState() {
  const { t } = useI18n();
  return (
    <div className="stack" aria-busy="true">
      <Text textStyle="t4Regular">{t("state.loading")}</Text>
      <Skeleton style={{ height: "1.5rem", width: "18rem" }} />
      <Skeleton style={{ height: "1.5rem", width: "24rem" }} />
      <Skeleton style={{ height: "1.5rem", width: "14rem" }} />
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  const { t } = useI18n();
  const code = ERROR_CODES.has(error?.code) ? error.code : "SAVE_FAILED";
  return (
    <div className="stack">
      <Callout.Root tone="critical">
        <Callout.Content>
          <Callout.Title>{t("error.title")}</Callout.Title>
          <Callout.Description>{t(`error.${code}`)}</Callout.Description>
        </Callout.Content>
      </Callout.Root>
      <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
        {t(error?.inputSafe === false ? "error.input_may_have_changed" : "error.input_preserved")}
      </Text>
      {onRetry ? (
        <div>
          <ActionButton variant="neutralOutline" size="medium" onClick={onRetry}>
            {t(code === "REVISION_STALE" ? "action.reload" : "action.retry")}
          </ActionButton>
        </div>
      ) : null}
    </div>
  );
}

/* An empty screen is an invitation to act, so it always carries the control that fills it. */
export function EmptyState({ titleKey, bodyKey, action }) {
  const { t } = useI18n();
  return (
    <ContentPlaceholder.Root>
      <div className="stack" style={{ justifyItems: "center", textAlign: "center" }}>
        <Text textStyle="t5Bold">{t(titleKey)}</Text>
        <Text textStyle="t3Regular" style={{ color: "var(--seed-color-fg-neutral-muted)" }}>
          {t(bodyKey)}
        </Text>
        {action}
      </div>
    </ContentPlaceholder.Root>
  );
}

export function NotFound() {
  const { t } = useI18n();
  return (
    <div className="stack">
      <Text textStyle="t7Bold">{t("state.not_found")}</Text>
      <Text textStyle="t3Regular">{t("state.not_found_help")}</Text>
    </div>
  );
}

/* Errors raised inside an async screen body have to reach the boundary, which only sees throws
   during render. Screens use this to re-raise a failed fetch. */
export function useAsync(loader, deps) {
  const [state, setState] = React.useState({ status: "loading" });
  React.useEffect(() => {
    let live = true;
    setState({ status: "loading" });
    loader()
      .then((data) => { if (live) setState({ status: "ready", data }); })
      .catch((error) => { if (live) setState({ status: "failed", error }); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
