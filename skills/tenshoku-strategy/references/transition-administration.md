# Transition Administration — 退職時の必要書類 + 外国人転職手続き

Use this reference when the user asks what to receive, submit, confirm, or report while moving from
one employer to another in Japan. The source of truth for procedural applicability is
`_shared/transition_admin.yml`; deterministic projection is owned by `_shared/transition_admin.py`.
This reference explains how the Skill consumes that projection. It is not a second legal-rule copy.

## Scope

V1 covers the narrow transition slice around employment end and the next employment:

- 給与所得の源泉徴収票;
- 雇用保険被保険者証 / 被保険者番号 when the new job is confirmed to enroll the user in 雇用保険;
- 退職証明書;
- 個人住民税の特別徴収継続 handoff;
- 雇用保険被保険者離職票-1・2 when unemployment-benefit handling is relevant;
- 健康保険資格喪失証明等 when 国民健康保険 transition makes it relevant;
- マイナンバー / 基礎年金番号 confirmation when the new job is confirmed to enroll the user in 厚生年金;
- applicable 出入国在留管理庁 affiliation/institution notifications for the bounded residence-status groups in the registry;
- status-specific immigration verification when a general rule would overstate what is known;
- 就労資格証明書 as an optional confirmation path for the supported contract-institution group, never a universal transfer requirement;
- 在留資格変更の要否確認 when the new activity may differ from the currently permitted activity.

It does **not** calculate tax, insurance premiums, unemployment benefits, pension exemptions, or
immigration eligibility. It does not submit any form. V1 is deliberately not a complete matrix of all
在留資格; a status outside the bounded groups becomes an explicit verification task rather than a
silent assumption that no procedure applies.

## Facts to collect

Ask only for facts needed by the projection. Preserve an omitted item as `Unknown`.

```yaml
employment_end_date: YYYY-MM-DD | null
new_employment_start_date: YYYY-MM-DD | null
new_contract_conclusion_date: YYYY-MM-DD | null
new_employment_insurance_enrollment: true | false | null
new_social_insurance_enrollment: true | false | null
unemployment_benefit_planned: true | false | null
resident_tax_mode: continue_special_collection | other | null
health_insurance_after_exit: new_employer_immediate | national_health_insurance | other | null
residence_status: "在留資格の正式名称" | null
new_activity_scope: same | changed | unknown | null
```

`new_employment_insurance_enrollment` and `new_social_insurance_enrollment` must be based on the
actual employment/insurance handling or confirmation from the new employer. Do not derive either
from the mere existence of a start date or from an assumed full-time employment pattern.

Do not infer `new_contract_conclusion_date` from the first working day. Do not use nationality as a
proxy for residence status. A user who says only “外国人です” still has `residence_status: null`.

## Deterministic projection

Create a temporary JSON/YAML scenario outside the Skill installation and run:

```bash
python scripts/transition_admin.py <scenario.yml>
```

When operating from an installed package rather than the repository, use the host/runtime path to
`_shared/transition_admin.py` directly or apply the same registry projection; do not replace it with
remembered legal guidance.

Every projected row has one of these states:

- `required`: the supplied facts make this action applicable;
- `conditional`: applicable only because the user selected the condition that activates it;
- `recommended`: useful/request-based, but not a universal legal must-have;
- `not_applicable`: supplied facts establish that this V1 rule does not apply;
- `unknown`: a required input is missing or a procedural source is stale.

## Output groups

Never collapse all rows into “退職時にもらう書類”. Separate at least these groups:

1. **本人が受け取る / 確認するもの**
2. **本人が行う届出・確認**
3. **旧勤務先・新勤務先・自治体の handoff を確認するもの**
4. **条件付き / 今回は対象外**
5. **Unknown — 追加確認が必要**

For every material row show:

```text
What: [task/document]
State: required | conditional | recommended | not_applicable | unknown
Owner: [user / former employer / new employer / both employers / authority]
Your action: [receive / confirm / notify / verify]
Trigger: [known event, if any]
Deadline: [projected date, if source and trigger are current]
Why: [registry guidance]
Official source: [authority + URL]
```

## Critical domain boundaries

### 雇用保険番号 / 基礎年金番号

Do not mark either identifier as required merely because a new employment start date exists.

For 雇用保険, V1 waits for `new_employment_insurance_enrollment`. The official rule has eligibility
conditions, including the ordinary 週20時間以上 and 31日以上雇用見込み criteria, so the Skill does
not infer enrollment from a generic “入社する” statement.

For 厚生年金, V1 waits for `new_social_insurance_enrollment`. The new employer handles enrollment
when the job is covered; only then does this slice require confirmation of マイナンバー or
基礎年金番号. `null` stays `Unknown`, and an explicitly confirmed `false` becomes `not_applicable`.

### 給与所得者異動届出書

When the user continues resident-tax 特別徴収, do not describe the 異動届出書 as a universal document
the employee personally receives and files. The projection treats it as an employer-to-employer /
municipality workflow that the user should confirm. Municipality-specific forms and deadlines must be
verified against the applicable local authority.

### 離職票

Do not turn 離職票 into a universal “must receive before starting the next company” item. V1 activates
it when the user says unemployment-benefit handling is planned. If another reason makes it necessary,
record that reason and verify the current official source before changing the projection.

### 健康保険資格喪失証明等

Do not require it merely because employment ended. V1 activates it for a stated 国民健康保険
transition. An immediate next-employer insurance start does not by itself activate this document.

### 外国人の届出

The user-owned notification depends on the actual residence status, not nationality. For the bounded
契約機関 group, contract termination and a new contract are separate events. Do not silently use the
new employment start date as the contract-conclusion date. For the bounded 活動機関 group, use the
applicable leave/transfer event from the registry.

Known unrestricted-work statuses in the registry (`永住者`, `日本人の配偶者等`,
`永住者の配偶者等`, `定住者`) do not inherit those work-status affiliation notifications merely
because the user is foreign.

Do **not** generalize the ordinary contract/activity rules to every other residence status:

- `高度専門職` is routed to `在留資格固有の転職手続確認`. A change of the designated institution can
  raise an additional status-change requirement, so V1 must not treat it as ordinary `技人国`.
- `興行` is also routed to status-specific verification because the contract-institution notification
  rule depends on the form of the activity/contract; the bare status name is insufficient for a safe
  automatic verdict.
- `特定技能` keeps the applicable affiliation notification **and** also produces
  `在留資格固有の追加転職手続確認`; the ISA explicitly states that changing the affiliated institution
  requires a 在留資格変更許可申請. The 14-day notification is therefore not the whole transition.
- `技能実習` and `企業内転勤` also keep their applicable activity-institution notification while
  separately producing the additional verification task. V1 does not claim that the notification
  alone authorizes an ordinary employer change.
- an unmapped status such as `特定活動` is routed to `在留資格別の転職手続確認`. It is **not** rendered
  as `not_applicable`; V1 says that the current procedure must be checked for that status.
- if the residence status itself is missing, show `Unknown` and ask for the exact status name.

### 就労資格証明書 vs 在留資格変更

`就労資格証明書` is an optional way to obtain official confirmation of permitted paid activity; it
is not a universal job-change requirement. V1 only auto-surfaces it for the bounded contract-institution
group where that question is relevant to this slice. If the new activity may differ from what the current
status permits, surface `在留資格変更の要否確認` separately. Never say that obtaining a
就労資格証明書 automatically resolves a changed-activity case.

## Source freshness

Before relying on this procedural registry in repository work, run:

```bash
python scripts/check_transition_admin.py
```

A stale procedural source is not silently treated as current. The projection returns `unknown` for a
row whose cited source passed `review_by`, and the repository checker fails until the source is
reverified.

## Example acceptance scenario

For:

```yaml
employment_end_date: 2026-09-30
new_employment_start_date: 2026-10-01
new_contract_conclusion_date: 2026-09-15
new_employment_insurance_enrollment: true
new_social_insurance_enrollment: true
unemployment_benefit_planned: false
resident_tax_mode: continue_special_collection
health_insurance_after_exit: new_employer_immediate
residence_status: 技術・人文知識・国際業務
new_activity_scope: same
```

expect the projection to distinguish at minimum:

- 源泉徴収票: required, former employer owns issuance;
- 雇用保険番号: required only because new-employment enrollment is confirmed;
- マイナンバー / 基礎年金番号: required only because new 厚生年金 enrollment is confirmed;
- 退職証明書: recommended/request-based, not universal automatic issuance;
- resident-tax continuation: employer handoff confirmation, not a universal employee filing;
- 離職票: not applicable under the stated unemployment-benefit condition;
- 健康保険資格喪失証明等: not applicable under the stated immediate next-employer-insurance condition;
- 契約終了 and 新たな契約 immigration notifications: separate required user actions;
- 就労資格証明書: recommended/optional;
- 在留資格変更の要否確認: not applicable while `new_activity_scope: same`;
- status-specific, additional-transition, and unmapped-status verification tasks: not applicable for this confirmed `技人国` case.
