# tenshoku-strategy evaluation cases

## Case 1: fixed entry and routing

Korean, Japanese, and English requests use the latest-message language and reach the same stage/module.
Only the response language changes.

## Case 2: offer and condition review

An offer is reviewed by facts, unknowns, and user priorities. Salary examples are cited and dated when
external. No offer-rate or negotiation-success estimate is produced.

## Case 3: interview follow-up

The draft cites the actual interview point supplied by the user, distinguishes a direct route from an
agent route, and does not invent a question or promise a response.

## Case 4: application tracking

The tracker records observed states, dates, feedback, missing information, preparation actions, and
user overrides. It does not transform Decision Status into a probability, tier, rank, or forecast.

## Case 5: market claims

Time-sensitive market guidance is read from `_shared/career_claims.yml`; stale claims produce a warning.
Missing claims are `Unknown`, not filled with a remembered statistic.

## Case 6: user ownership

A warning or conflict is explained with its evidence and next verification step. The skill does not
submit, send, file a government form, or decide on the user's behalf.

## Case 7: next-day transition with 技術・人文知識・国際業務

For a 9/30 employment end, 10/1 next-employer start, separately confirmed 9/15 new-contract date,
confirmed new-employer 雇用保険 and 厚生年金 enrollment, continued resident-tax 特別徴収, no
unemployment-benefit plan, immediate next-employer health insurance, and 技術・人文知識・国際業務
status, the response must use the deterministic transition projection. It separates employee
receipts/identifiers, user-owned immigration notifications, employer/municipality handoff,
optional/request-based documents, and not-applicable items. It must not tell the user to personally
file the resident-tax 異動届出書 or call 離職票/健康保険資格喪失証明 universal must-haves.

## Case 8: insurance enrollment is not inferred from an 入社日

A known next-employer start date without confirmed `new_employment_insurance_enrollment` or
`new_social_insurance_enrollment` leaves the corresponding 雇用保険番号 and マイナンバー/基礎年金番号
rows `Unknown`. Explicitly confirmed non-enrollment makes those rows `not_applicable`. The Skill must
not infer either enrollment flag from “正社員”, “入社”, or a calendar date unless the underlying
insurance handling is actually confirmed.

## Case 9: immigration unknowns and changed activity

Nationality alone never activates a work-status notification. Missing residence status stays `Unknown`.
For 契約機関 status, a missing new-contract-conclusion date stays `Unknown` and is not replaced with the
first working day. If the new activity scope is `changed`, the Skill separately surfaces
在留資格変更の要否確認; 就労資格証明書 remains an optional confirmation path rather than a substitute.

## Case 10: residence statuses outside the ordinary auto-rules

`永住者`, `日本人の配偶者等`, `永住者の配偶者等`, and `定住者` do not inherit work-status affiliation
notifications merely because the user is foreign. `高度専門職` and `興行` route to status-specific
verification instead of being treated as ordinary `技人国`; an unmapped status such as `特定活動`
routes to a residence-status-specific verification task rather than being silently declared
`not_applicable`.

## Case 11: notification is not authorization for status-sensitive employer changes

`特定技能` keeps its applicable contract-institution notification and also produces a separate
status-specific transition verification; the response must surface that an affiliated-institution
change requires 在留資格変更許可申請 under the current official ISA guidance. `技能実習` and
`企業内転勤` keep their applicable activity-institution notifications and also produce the additional
verification task. In all three cases the Skill must not present the 14-day notification as proof that
an ordinary employer transfer is otherwise permitted or complete.
