# Jiko Bunseki — Depth Layer (Phase 3)

Conversational deep-dive that runs AFTER the quantitative report (Phase 2). The quantitative instrument gives a trait snapshot; this layer turns it into a self-portrait by adding what forced-choice scoring cannot reach: what the person refuses to give up, where their strengths turn dangerous, what actually energizes vs drains them, and the narrative that connects it all.

Run this in chat, one block at a time, in the user's language. It is optional — offer it, do not force it. It reuses the Phase 2 output (especially `top_strengths`) as input.

Theoretical basis:
- **Schein Career Anchors** — the one need a person will not sacrifice when forced to choose
- **Hogan/Gallup shadow side** — every strength overused becomes a derailer
- **Values-in-Action energy audit** — "good at" ≠ "wants to do"; a strength you hate using is a trap
- **Savickas Career Construction** — life themes connect past role models to future direction

---

## Block A — Career Anchors (Schein)

Goal: find the 1-2 anchors the person will not trade away. Strengths say what they CAN do; anchors say what they MUST have.

Present the 8 anchors and ask the user to pick the **top 3** they would refuse to give up, then force-rank those 3.

| Anchor | 한 줄 | 충족 안 되면 |
|---|---|---|
| **전문성 (Technical/Functional)** | 특정 분야의 진짜 전문가가 되는 것 | 제너럴리스트로 떠밀리면 의욕 상실 |
| **관리 (General Managerial)** | 사람·자원·조직을 책임지고 키우는 것 | 영향 범위가 좁으면 답답 |
| **자율 (Autonomy)** | 내 방식·내 속도로 일하는 것 | 세세한 통제·승인 체계에 질식 |
| **안정 (Security/Stability)** | 예측 가능하고 안전한 기반 | 불확실성·고용 불안에 소진 |
| **창업/창조 (Entrepreneurial)** | 없던 것을 새로 만드는 것 | 남이 만든 것 운영만 하면 공허 |
| **봉사/헌신 (Service/Dedication)** | 가치 있는 대의에 기여 | 의미 없는 일에 냉소 |
| **순수 도전 (Pure Challenge)** | 어려운 문제를 정복하는 것 | 쉬운 일 반복에 지루함 |
| **라이프스타일 (Lifestyle)** | 일과 삶의 통합·균형 | 일이 삶을 잠식하면 이탈 |

Follow-up after they rank:

- 1순위 앵커가 깨졌던 최근 사건 하나를 말해 주세요.
- 회사가 다른 모든 조건을 다 줘도, 그 앵커가 없으면 떠날 건가요? (앵커 진위 검증)
- 그 앵커와 Phase 2의 top 강점은 같은 방향인가요, 충돌하나요?

**Cross-check rule:** if the anchor conflicts with `preferred_company_type` from Phase 2, surface it. Example: anchor=자율 but preferred_company_type=SIer → built-in tension, name it.

---

## Block B — Derailers (overused strengths)

Goal: every top strength has a shadow. The same trait that wins also sabotages when overused or under stress. Use the person's actual Phase 2 top-5 to generate personalized derailer hypotheses — do not list all 12.

Derailer map (strength → overuse risk):

| 강점 | 과용하면 | 스트레스 시 신호 |
|---|---|---|
| initiative | 마무리 없이 일만 벌림 | 끝낸 것보다 시작한 게 많음 |
| communication | 말이 행동을 앞섬, 과잉설명 | 설명은 많은데 실행 증거가 적음 |
| confidence | 타인 의견 차단, 독단 | "내가 맞아" 후 피드백 무시 |
| execution | 양이 질을 덮음, 멈춰 생각 못함 | 바쁜데 방향이 틀림 |
| discipline | 경직, 변화 저항, 마이크로매니지 | 예외 상황에서 얼어붙음 |
| ownership | 위임 불가, 과부하, 번아웃 | 혼자 다 짊어지고 소진 |
| analysis | 분석 마비, 행동 지연 | 결정 못하고 자료만 모음 |
| learning | 실행 대신 학습으로 도피 | 배우기만 하고 안 씀 |
| strategy | 옵션만 늘고 결정 못함 | 가능성 나열, 선택 회피 |
| empathy | 타인 감정에 휩쓸림, 경계 약함 | 거절 못해 자기 일 밀림 |
| harmony | 갈등 회피, 필요한 대립 못함 | 문제를 덮고 곪게 둠 |
| support | 자기희생, 타인 의존 키움 | 남 챙기다 자기 커리어 정체 |

For each of the user's top-3 strengths:

1. Present the overuse risk as a hypothesis ("가설입니다").
2. Ask for a recent episode where it might have backfired.
3. If confirmed, record a watch-signal they can self-monitor.

This is the highest-value block for interviews — "약점" 질문에 진짜 자기인식 기반 답을 만들어준다.

---

## Block C — Energy Map

Goal: separate "잘하는 일" from "하고 싶은 일". A strength that shows up in the DRAINS column is a career trap — you will be promoted into work that exhausts you.

Ask for concrete recent episodes (not abstractions):

- 최근 한 달, 시간 가는 줄 모르고 몰입했던 업무 장면 2개
- 최근 한 달, 끝나고 진이 빠졌던 업무 장면 2개

Then build:

```
살리는 일 (energizes):
  - [episode] → [underlying driver]
빠는 일 (drains):
  - [episode] → [underlying cost]
```

**Misfit flag rule:** if any Phase 2 top strength appears in the DRAINS column, flag it explicitly. Example: top strength = communication, but "하루 종일 설명·조율" drains them → they are good at it but it costs them. This belongs in `risk_flags` and changes role recommendations.

---

## Block D — Career Theme (Savickas)

Goal: one sentence connecting past → present → future. The numbers describe the person; the theme explains them.

Pick 2-3 prompts:

- 어릴 때 존경했거나 닮고 싶었던 인물은? 그 사람의 어떤 점? (→ 이상적 자아)
- 반복해서 좋아하는 이야기·영화·게임의 공통 주제는? (→ 인생 테마)
- 지금까지 커리어에서 가장 자랑스러운 순간 하나. 왜 그게 자랑스러운가? (→ 핵심 동기)

Synthesize into one line:

> "나는 [과거의 결핍/동기]에서 출발해 [현재 하는 일]을 통해 [미래에 되려는 것]으로 가는 사람이다."

This line becomes the spine of 自己PR and 志望動機.

---

## Integration — Deep Career Portrait

After running the blocks the user opted into, write a short integrated portrait (3-5 sentences, Korean) that ties together:

- Phase 2 강점/스타일 (정량)
- 앵커 (절대 조건)
- 디레일러 (자기인식)
- 에너지 맵 (적합/함정)
- 테마 (스토리)

Extract `career_values.must_have` and `career_values.avoid` only from the user's explicit non-negotiables,
anchor explanation, and energy-map episodes. If the user did not state a value, leave the list empty;
do not convert a generic career cliché into a value.

Before saving, show the exact non-null `career_anchors`, `career_theme`, `energy_map`, and `career_values`
back to the user and ask for one explicit confirmation. Store `career_context_confirmed: true` only after
that confirmation. If the user corrects anything, revise and ask again; if they do not confirm, keep the
draft unconfirmed and downstream skills must ignore it as canonical context.

Then append the optional depth fields to the YAML profile (see SKILL.md Phase 3 output spec). Set any block the user skipped to `null`.

End with the handoff: this portrait feeds `job-seeker-agent` (richer self-PR + 약점 답변), `tenshoku-strategy` (anchor-based 転職理由), and `naked-me` (if a contradiction needs deeper excavation).
