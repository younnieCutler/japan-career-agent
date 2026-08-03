# Shared Frameworks — evidence first

This file contains public or explicitly labelled working frameworks. It is not a description of a
private recruiter system. All active skills also follow `_shared/decision_philosophy.md`.

## 1. Work-style reflection

The four tendency labels below are a compact reflection vocabulary used by the custom checklist:

| Label | Working meaning |
|---|---|
| `creation` | enjoys making or exploring something new |
| `result` | values visible outcomes and completion |
| `harmony` | seeks workable coordination and mutual respect |
| `order` | prefers clarity, process, and predictable handoffs |

The 12-statement exercise is `SPI3-inspired reflection` only. It is not official SPI3, a diagnosis,
or a validated predictor. Preserve the user's responses and confidence; do not use a label to infer
company culture or determine a company type. Translate a preference into a workplace question.

## 2. Portable skills — resume evidence lens

The nine MHLW Portable Skills elements are:

1. 現状の把握 — current-state assessment
2. 課題の設定 — task setting
3. 計画の立案 — planning
4. 課題の遂行 — task execution
5. 状況への対応 — situational response
6. 社内対応 — internal coordination
7. 社外対応 — external coordination
8. 上司対応 — manager response
9. 部下マネジメント — subordinate management

For resume coaching, cite the user's episode for each element. Do not use a default level. For the
MHLW reference interface, use only a user-confirmed integer allocation of 29 total points with each
element at least 1. `portable_skill_level` is position context and is excluded from the allocation
distance. A legacy 1–5 value is not convertible.

## 3. Skill ontology mapping

Map a JD term to a candidate capability only when the relationship is explicit. Record:

```yaml
candidate_term: "[exact term]"
job_term: "[exact JD term]"
mapping_basis: "synonym | hierarchy | adjacent_transfer | none"
evidence: "[source]"
status: matched | missing | unknown
confidence: high | medium | low | unknown
```

`adjacent_transfer` is a hypothesis for preparation; it does not turn an absent core skill into a
match.

## 4. Career values and conditions

Collect only values the user states as `must_have`, `preferred`, or `avoid`. Compare each with
company evidence. Use `Aligned`, `Tradeoff`, `Conflict`, or `Unknown`. A confirmed must-have or
avoid conflict stays a decision conflict and is never offset by skill evidence.

## 5. Gakuchika and STAR+R

For 新卒 or thin work history, a student episode can be used as supplementary evidence. Keep it
labelled `student-era evidence`; do not present it as work experience. STAR+R means Situation,
Task, Action, Result, and Reflection. The result can be qualitative when no verified number exists.

## 6. Evidence metadata

Important facts should carry:

```yaml
source_type: official_framework | job_posting | company_public_source | user | observed | derived | heuristic | unknown
source_ref: "URL, resume line, note id, or conversation date"
observed_at: "YYYY-MM-DD"
confidence: high | medium | low | unknown
provenance: official_framework | job_posting | company_public_source | user | observed | derived | heuristic | unknown
```

`heuristic` is a question-generating hypothesis, not a fact. The absence of a field remains
`Unknown`.

## 7. Market claims

Time-sensitive salary, platform, service, and labour-market facts belong in
`_shared/career_claims.yml` with a publisher, source URL, publication/observation date, confidence,
and expiry date. A descriptive claim is never transformed into a candidate outcome estimate.
