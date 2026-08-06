# LLM Judge v2 — autoresearch-style fixed-corpus experiment

**상태:** 6회 완료 — final best `PROVISIONAL KEEP (hard-gate dimensions)`, axis 평가 미확립
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

Frozen hashes:

- corpus SHA-256: `e41cb27f7b95c005ce836b15cd3119fef44e8e3141799de63acbd82ece547a78`
- expected SHA-256: `98eb08464df515ca5cc2b7494edba81266280a729d6bf20e657fae3d4d415af7`
- result schema SHA-256: `9d4e6757a1b80c53170d3bee4cad0f81e4463f5a07d96714594935114044f4ba`

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

### Methodological correction recorded after the six runs

The runner supplied only `judge.md` and `corpus.md` to each Judge and explicitly
forbade inspecting other files.  Although `judge.md` referred to the frozen v1
anchors, it did not contain the complete 0/2/4 anchors for all six axes.  The
frozen v1 rubric was therefore not actually in the Judge input.  The seven
hard-gate definitions were written directly in `judge.md`, so hard-gate
detection, clean hard-gate false positives, and output-quote checks remain
interpretable.  Axis values, the axis-floor comparison, and axis reproducibility
are under-specified and are **not established or measurable from this run**.
The observed `decision_ownership` value changing from 0 to 1 is not attributed
to Judge stochasticity.  No experiment or verification was rerun, and no corpus,
expected label, or v1 record was changed.

For any future run, the frozen input must include and hash the Judge procedure,
fixed corpus, exact frozen v1 rubric, and the required canonical contract
snapshot.  This correction is a record of the wiring fact, not a new experiment.

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

v1의 역사적 결론을 수정하거나 재해석하지 않으며, 제품 파일·CI·runtime 동작은
변경하지 않는다.

## Results

결과는 [`results.tsv`](../skills/job-seeker-agent/tests/judge_v2/results.tsv)에
정확히 6개 행으로 기록했다. baseline은 별도 preflight이며 여섯 실험에 포함하지
않는다. 모든 candidate는 `gpt-5.6-terra`, reasoning `medium`,
`codex exec --ephemeral --ignore-user-config --ignore-rules --sandbox read-only`
로 실행했다. raw output/capture는 저장소 밖
scratch artifact directory에 보존했다.

| 실행 | commit | 결과 | hard detection | clean FP | schema/quote | 비고 |
|---:|---|---|---|---:|---|---|
| 1 | `d17d183` | DISCARD | all expected | 0 | pass | no hard-gate improvement; axis observation is not interpretable after the wiring correction |
| 2 | `47088a6` | DISCARD | all expected | 0 | pass | same hard-gate result as best; longer prompt |
| 3 | `7357417` | DISCARD | all expected | 0 | pass | same hard-gate result as best; longer prompt |
| 4 | `cd2033b` | DISCARD | all expected | 0 | pass | same hard-gate result as best; longer prompt |
| 5 | `9627d27` | DISCARD | all expected | 0 | pass | same hard-gate result as best; longer prompt |
| 6 | `3e6414e` | **PROVISIONAL KEEP (hard-gate dimensions)** | all expected | 0 | pass | same hard-gate result and clean FP with a simpler procedure |

Experiment 3의 첫 호출은 judge 인자에 corpus path를 넣은 wiring typo였고
실험에 세지 않았다. 잘못된 metadata/output은 scratch에 남겼고, 올바른 path로
같은 candidate를 한 번 평가했다. 이 harness 관측은 corpus/expected를 수정하는
근거로 사용하지 않았다.

### Final verification

최종 best `3e6414e`를 fresh session 두 번 더 실행했다(실험 7·8이 아님).
두 번 모두 hard detection 전체, clean FP 0, schema/quote는 유지됐다.
`F_outcome_forecast.decision_ownership`가 experiment 6의 `0`에서 `1`로
변했지만, complete frozen v1 axis anchors가 Judge 입력에 없었으므로 이 값의
변화는 Judge stochasticity나 axis 재현성 실패로 해석할 수 없다. Axis 평가,
axis floor, axis reproducibility는 이번 실행에서 **확립되지 않았고 측정 불가**다.
두 verification 모두 결과를 scratch에 보존했으며 새 candidate·corpus·재채점
루프는 실행하지 않았다.

### Product impact and limitations

- 제품 코드, `SKILL.md`, v1 rubric/judge/fixture/history, `mistakes.md`, CI 및
  runtime은 변경하지 않았다. 이 synthetic corpus에서 새 실제 제품 결함은
  관측하지 않았다.
- defect case의 부수 label(`B: decision_taken`, `G: fabricated_evidence`)은
  결과에 보존했지만 acceptance의 clean false-positive gate와 혼동하지 않았다.
- hard-gate detector는 고정 corpus에서 안정적인 신호를 보였지만, axis rubric
  snapshot을 Judge에게 전달하지 않아 axis 값·floor·재현성은 이번 실행에서
  under-specified이며 measurable하지 않다. 이를 Judge stochasticity의 증거로
  기록하지 않는다.

## Recommendation

**권고: `continue later` (현재 도입하지 않음).** 여섯 candidate 모두
expected hard violation을 탐지하고 clean false positive 0을 유지했으며,
최종 best는 같은 hard-gate 결과를 더 단순하게 달성했다. 따라서 fixed-corpus
hard-gate detector 용도는 향후 고려할 수 있다. 다만 complete frozen v1 axis
anchors가 Judge 입력에서 빠져 axis 평가·floor·재현성은 확립되지 않았고, valid
regression→Judge 운영 경로의 제품 통합 근거도 없다. 이를 근거로 v2 전체를
채택하지 않으며 CI/runtime에도 넣지 않는다. v1 결론은 덮어쓰지 않고, 이
branch/PR의 여섯 결과를 보존한 채 오늘은 6회 후 종료한다.
