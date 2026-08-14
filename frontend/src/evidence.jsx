/* Evidence state, expressed in SEED's vocabulary.

   SEED documents what each tone means, and those meanings line up with this product's states
   almost exactly — so the mapping below is a translation, not a decoration:

     positive  "완료, 적용됨, 승인됨, 발행됨, 저장 성공, 검토 통과"   -> approved
     warning   "만료 임박, 제출 누락, 필수 정보 부족"                 -> waiting on the user
     critical  "검수 거절, 제재 상태, 편집 불가, 유효성 검증 실패"     -> contradiction
     neutral   "상태가 특별히 없거나, 상태값이 명확하지 않은 초기 상태" -> draft, unknown

   Two rules survive from the previous system and are not SEED's to relax:
   1. Conflict is not a lifecycle state. It rides alongside the lifecycle chip, never replaces it,
      so a contradicted-but-approved record still reads as both.
   2. A draft is the absence of attestation, so it is drawn (outline) rather than filled. */

import React from "react";
import { Badge } from "@seed-design/react";
import { useI18n } from "./i18n.jsx";

const LIFECYCLE_TONE = {
  approved: "positive",
  completed: "positive",
  active: "positive",
  review_pending: "warning",
  draft: "neutral",
  archived: "neutral",
};

export const toneOf = (state) => LIFECYCLE_TONE[state] || "neutral";

export function StatusChip({ state }) {
  const { statusText } = useI18n();
  const tone = toneOf(state);
  return (
    <Badge tone={tone} variant={state === "draft" ? "outline" : "weak"} size="medium">
      {statusText(state)}
    </Badge>
  );
}

export function ConflictChip() {
  const { t } = useI18n();
  // Solid, because a contradiction is the one state that must win a glance.
  return <Badge tone="critical" variant="solid" size="medium">{t("status.conflict")}</Badge>;
}

export function CaseChip({ state }) {
  const { enumText } = useI18n();
  return (
    <Badge tone={toneOf(state || "active")} variant="weak" size="medium">
      {enumText("case_status", state || "active")}
    </Badge>
  );
}

/* Readiness reports one state per dimension and never a total. `Partial` deliberately shares
   `warning` with `Stale` rather than getting a tone of its own between neutral and positive:
   a graded ramp is what invites the eye to average six independent answers into a score. */
const READINESS_TONE = {
  Confirmed: "positive",
  Partial: "warning",
  Stale: "warning",
  Unknown: "neutral",
};

export function ReadinessChip({ state }) {
  const { enumText } = useI18n();
  return (
    <Badge tone={READINESS_TONE[state] || "neutral"} variant="weak" size="medium">
      {enumText("readiness", state)}
    </Badge>
  );
}
