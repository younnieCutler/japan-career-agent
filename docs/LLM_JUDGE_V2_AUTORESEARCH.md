# LLM Judge v2 — autoresearch-style fixed-corpus experiment

**상태:** 6회 실험 실행 전 — corpus와 acceptance rule 동결
**브랜치:** `experiment/llm-judge-autoresearch-6`
**기준:** `origin/main` `08b4b8ca70ecc2fbefba07207eb6a5f775ee5c0b`
**구분:** 기존 LLM Judge v1 파일럿(`docs/LLM_JUDGE_PILOT.md`)과 별도 실험

## 목적과 v1과의 차이

v1은 subject 생성의 stochasticity와 Judge 판정을 한 실험에 섞었다. v2는
subject를 호출하지 않는다. 실험 시작 전에 손으로 만든 synthetic output 8개를
고정하고, Judge procedure만 한 번에 하나씩 바꾼다. 기존 제품 계약, `SKILL.md`,
v1 rubric/judge/fixture/history, deterministic checks는 읽기 전용이다.

설계는 [karpathy/autoresearch](https://github.com/karpathy/autoresearch)의
작은 수정 단위, 고정된 평가 조건, 현재 best와의 비교, 개선 시 keep·아니면
discard라는 루프 철학만 참고한다. 이 실험은 모델 학습이나 제품 동작 변경이
아니며, scalar composite score도 만들지 않는다.

## Frozen inputs

| 항목 | 파일 또는 값 |
|---|---|
| fixed corpus | `skills/job-seeker-agent/tests/judge_v2/corpus.md` |
| expected labels | `skills/job-seeker-agent/tests/judge_v2/expected.yml` (Judge prompt에 전달하지 않음) |
| result schema | `skills/job-seeker-agent/tests/judge_v2/output_schema.json` |
| harness | `skills/job-seeker-agent/tests/judge_v2/validate.py`, `run_v2.py` |
| product contract | `AGENTS.md`, `_shared/decision_philosophy.md`, `skills/job-seeker-agent/SKILL.md` |
| v1 contract | `skills/job-seeker-agent/tests/rubric.md`, `judge.md`, 기존 fixture와 history |
| model | subject 없음; Judge `gpt-5.6-terra`, reasoning effort `medium` |
| session | 매 실행 `codex exec --ephemeral`, user config·rules 무시, read-only |

Corpus case set:

`A_clean_hard_conflict`, `B_conflict_regression`, `C_clean_grounded`,
`D_fabricated_evidence`, `E_clean_requirement_risk`, `F_outcome_forecast`,
`G_unknown_defaulted`, `H_clean_unknown`.

`A/C/E/H`는 clean counterpart이고, `B/D/F/G`는 각각 하나의 사전 등록된
hard violation을 포함한다. `B`는 `conflict_offset`와
`requirement_discipline` 축 regression을 함께 확인한다. corpus와 expected
labels는 experiment 1 실행 전에 변경하지 않는다. harness bug가 보이면 결과에
기록하되 dataset을 고치지 않는다.

## Frozen acceptance rule

각 candidate는 corpus 전체를 한 번 평가한다. 다음 순서를 고정한다.

1. expected hard violations를 모두 탐지한다.
2. clean case의 hard-gate false positive가 0이다.
3. 결과 JSON schema와 case/gate/axis 구조가 유효하다.
4. 모든 failed gate와 4 미만 axis 값에 captured output의 원문 quote가 있다.
5. expected axis floor를 충족한다. defect case의 추가 hard label은 부수 관측으로
   기록하고, clean case의 hard-gate false positive만 0 조건으로 막는다.
6. 동률이면 더 짧고 단순한 procedure를 우선한다.

현재 best보다 앞 단계의 조건을 개선하고 뒤 단계의 조건을 악화시키지 않으면
`KEEP`; detection·false positive·schema·인용 계약이 같고 procedure가 명백히
단순해져도 `KEEP`; 그 밖에는 `DISCARD`하고 직전 best 상태로 되돌린다. 이
순서는 lexicographic 비교이며 어떤 weighted average나 overall 점수도 만들지
않는다. 최종 best에는 실험 예산에 포함하지 않는 fresh 2~3 case verification을
추가하되, 6회째 뒤에는 새 아이디어를 실행하지 않는다.

## Exactly six pre-registered experiments

각 행의 변경은 candidate `judge.md`에서 한 개념만 바꾼다. baseline은 별도
기록이며 여섯 실험에 포함하지 않는다.

| Experiment | 단일 아이디어 |
|---:|---|
| 1 | hard gate를 axis 평가보다 먼저 완료하도록 절차 순서를 명시 |
| 2 | requirement state와 candidate fate(outcome forecast)의 경계를 짧은 문장으로 고정 |
| 3 | 각 gate/axis에 `contract rule → captured-output quote → verdict` checklist 적용 |
| 4 | clean counterpart를 먼저 분류해 hard-gate false positive를 억제 |
| 5 | axis 평가 전에 factual claim을 input line에 trace하는 단계 추가 |
| 6 | detection·false positive·schema·quote 결과가 유지되는 최소 procedure로 단순화 |

실제 keep/discard와 commit, corpus/schema 해시는 six-experiment 결과 표에
추가한다. v1의 역사적 결론을 수정하거나 재해석하지 않으며, 제품 파일·CI·runtime
동작은 변경하지 않는다.

## Results

실험 전. 결과는 `skills/job-seeker-agent/tests/judge_v2/results.tsv`에 6개
행으로 기록한다. raw runtime output은 저장소 밖 scratch artifact로 보존하고
tracked 파일에는 넣지 않는다.

## Recommendation

6회와 최종 verification이 끝난 뒤에만 `adopt v2`, `continue later`,
`discard v2` 중 하나를 근거와 함께 기록한다. 7번째 아이디어나 추가 corpus는
실행하지 않는다.
