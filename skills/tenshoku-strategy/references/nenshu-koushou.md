# 年収交渉: evidence and user-controlled wording

Salary negotiation is a conversation about the written offer, the candidate's confirmed contribution,
and conditions the user chooses to discuss. This guide does not provide a universal market range,
negotiation-success estimate, or leverage formula.

## Before drafting

Collect and label:

- current compensation only if the user chooses to disclose it;
- written offer amount, components, currency, and conditions;
- desired condition and the reason the user wants it;
- confirmed role scope, skills, and contribution evidence;
- competing offer only when the user confirms it;
- route: direct, agent/CA, scout, or referral;
- unknowns and the question to ask HR or the CA.

External salary surveys or platform guidance must be recorded in `_shared/career_claims.yml` with URL,
publisher, publication/observation date, confidence, and expiry. A marketing claim remains a marketing
claim. Never turn it into a candidate benchmark.

## Timing and route

Use the actual process evidence. If the employer has not stated when compensation is discussed, write
`Unknown` and ask. If an agent is involved, confirm with the CA whether the CA should relay the request;
do not claim access to internal grade bands or private agency rules.

## User-reviewed wording

```text
Thank you for explaining the offer. Based on the confirmed scope of [role] and my experience with
[specific evidence], I would like to ask whether [requested condition] can be considered.
If that is not possible, could you explain [grade / review timing / condition] and whether [alternative]
is available? I will review the written conditions carefully.
```

Japanese draft:

```text
オファー内容をご説明いただきありがとうございます。
[職務範囲]と、私の経験である[確認済みの実績・役割]を踏まえ、[希望条件]について
ご相談できるか確認させていただけますでしょうか。
難しい場合は、[等級・評価時期・その他条件]と、[代替案]の可能性をご教示ください。
```

Replace every bracket with a user-confirmed fact. Do not claim a metric, competing offer, urgency,
legal right, or market standard that the user did not provide.

## Decision record

```yaml
condition: "[written offer item]"
candidate_priority: "[user statement]"
evidence: "[resume/JD/offer line]"
state: Confirmed | Unknown | Contradictory | Stale | Low Confidence
source: "[document or conversation]"
observed_at: "YYYY-MM-DD"
confidence: high | medium | low | unknown
tradeoff: "[what changes if accepted or declined]"
next_question: "[question for employer/CA]"
```

The user decides whether to negotiate, accept, defer, or decline. The assistant may prepare language
and show trade-offs but never contacts the employer.
