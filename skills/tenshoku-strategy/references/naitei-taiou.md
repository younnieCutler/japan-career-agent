# 内定対応 (Offer Handling) — Verification Checklist

An offer is a new evidence set to verify, not a command to accept and not proof of future employment
conditions. Preserve the user's decision authority. This reference does not assert a universal response
deadline, negotiation success rate, or start-date rule.

## 1. Confirm the written conditions

Ask for the documents that govern the offer and record their date and source:

- role, reporting line, work location, work mode, and expected scope;
- base pay, variable pay, allowances, fixed overtime wording, review timing, and benefits;
- employment term, probation wording, working hours, leave, and any transfer or travel condition;
- start date, response deadline, and the channel for questions or negotiation;
- visa/work-authorization or reference-check requirements where relevant.

Classify each item as `Confirmed`, `Unknown`, `Contradictory`, `Stale`, or `Low Confidence`. A verbal statement
does not replace the written condition; retain the message as `Observed` and request clarification.

## 2. Offer-meeting questions

Use questions tied to the user's priorities, not a generic company stereotype:

1. What would the first assignment and success evidence be?
2. Who owns evaluation and how often is the role reviewed?
3. Which working-condition details are fixed in the written document?
4. Which role, location, schedule, or compensation details remain subject to change?
5. What is the exact response deadline and can the company confirm an extension in writing?

The answer is a company-specific observation. Do not convert it into a fit score or an outcome forecast.

## 3. Negotiation and deadline handling

Record the exact deadline from the offer. If the user needs more time, prepare a concise request stating the
requested date and the reason the user is verifying another confirmed condition. If an agent is the documented
contact channel, route the request through that agent; do not assume the agent has authority to change conditions.

For compensation, use the user's confirmed scope, evidence, and priorities. External salary data is usable only
when it appears in `_shared/career_claims.yml` with source, dates, confidence, and `claim_type`; it is not a
negotiation-success estimate.

## 4. Declining

The user may decline without giving a detailed reason. Use the documented contact channel and preserve the sent
message as an event. A neutral template:

> このたびは内定のご連絡と選考のお時間をいただき、誠にありがとうございます。慎重に検討した結果、
> 今回は辞退させていただくことにいたしました。貴重な機会をいただきましたことに、心より御礼申し上げます。

Do not claim that a late response, direct contact, or another company's process will definitely change the
employer's decision. Ask the user to follow the actual offer instructions.

## 5. Start-date coordination

Start date is a constraint to coordinate using the current contract, work rules, handover evidence, and the new
employer's written request. The assistant must not state a universal legal period. If the documents conflict,
mark `Contradictory` and recommend official or professional verification.
