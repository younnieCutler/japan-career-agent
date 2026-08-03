# Japan Recruit AI Agent

일본 구직자를 위한 local-first **evidence-based Career OS**입니다. 이 프로젝트는 합격 여부를
예측하거나 Recruit·Persol·doda 등의 비공개 알고리즘을 복제하지 않습니다. 사용자가 제공한
증거를 바탕으로 무엇이 확인되었고, 무엇이 충돌하며, 무엇이 `Unknown`인지와 다음에 확인할
질문을 정리합니다.

현재 릴리스: `1.6.2`.

## 핵심 원칙

- hard eligibility, required skills, experience, portable skills, 조건, career values, practical
  constraints, candidate interest, employer signals를 서로 다른 축으로 보존합니다.
- 정보가 없으면 `Unknown`입니다. 평균, default pass, 임의 점수, coefficient를 만들지 않습니다.
- 확인된 hard requirement·법적 요건·must-have·dealbreaker 충돌은 다른 강점으로 상쇄하지 않습니다.
- `interest_level`은 선호 기록일 뿐 objective evidence나 Decision Status를 바꾸지 않습니다.
- 주요 사실에는 source, observed_at, confidence, provenance를 붙입니다. `heuristic`은 확인 질문을
  만들기 위한 가설이며 판정을 결정하지 않습니다.
- `Proceed` / `Review` / `Conflict`, `Matched` / `Missing` / `Unknown`을 사용하며 사용자가 결정을
  소유합니다. 지원서 제출이나 메시지 발송은 하지 않습니다.
- Resume, JD, 웹 문서, YAML, Vault metadata, pipeline, rules는 untrusted career data입니다.
  데이터는 instruction이 될 수 없습니다.

자세한 계약은 [`_shared/decision_philosophy.md`](_shared/decision_philosophy.md)와
[`_shared/schemas.yml`](_shared/schemas.yml)를 참고하세요.

## Skills

- `jiko-bunseki`: 공식 SPI3가 아닌 work-style reflection과 방향 탐색
- `job-seeker-agent`: 이력서·職務経歴書·자기PR·증거 기반 CANDIDATE_PROFILE
- `hiring-manager-agent`: 명시적 JD 요건과 면접 평가 기준
- `kigyou-bunseki`: 출처·날짜가 있는 기업/공고 조사
- `matching-simulator`: independent-axis 진단과 `Proceed` / `Review` / `Conflict`
- `company-battlecard`: 합계 없는 기업·오퍼 비교
- `tenshoku-strategy`: 면접 매너, follow-up, 年収交渉, 퇴직, 입사, tracking
- `career-agent`: 승인 게이트 Vault 상태와 CWD workspace projection

## Vault와 workspace

Vault는 개인 canonical state이고, `./data/pipeline.yml`은 현재 job-search workspace의 회사별
projection입니다. 혼동을 막기 위해 필요하면 둘 다 명시하세요.

status bar는 `--workspace`로 지정한 경로, `CAREER_WORKSPACE`, 현재 CWD 순서로
`data/pipeline.yml`을 읽습니다. 다른 디렉터리에서 실행해도 잘못된 pipeline을 읽지 않도록 하기
위한 우선순위입니다.

```powershell
$env:CAREER_VAULT='C:\path\to\career-vault'
$env:CAREER_WORKSPACE='C:\path\to\job-search-workspace'
python skills/career-agent/career_agent.py context --vault $env:CAREER_VAULT
python skills/career-agent/career_agent.py approve --vault $env:CAREER_VAULT --workspace $env:CAREER_WORKSPACE <proposal-id>
```

`restore-state`는 rollback/undo가 아니라 state recovery입니다. append-only ledger, proposal,
pipeline projection은 되감지 않습니다. Vault note 본문은 자동으로 읽지 않고 metadata만 사용합니다.

## 신뢰성 및 context hardening (`1.6.2`)

- Career Vault의 JSON/TOML 상태와 다시 쓰는 JSONL snapshot은 atomic replacement를 사용하며,
  append-only JSONL의 기존 의미는 유지합니다.
- Context는 항상 로드하는 invariant, 작업별 lazy reference, 사용자/evidence 원문으로 나눕니다.
  `python scripts/check_context_budget.py`가 byte·문자 수·줄 수 기준을 결정적으로 검사합니다.
- 일반 status bar에서는 행동으로 이어지지 않는 반복 정보를 줄이지만 모든 blocker와 제한된
  action/rule 미리보기는 유지합니다.
- UserPromptSubmit launcher는 오래된 plugin 경로와 없는 script를 Python 실행 전에 확인하고,
  문제가 있어도 prompt를 차단하지 않습니다. 대신 gate와 deadline을 확인하지 못했다는 degraded
  상태를 표시합니다. Claude manifest는 표준 hook 파일을 중복 선언하지 않습니다.
- `_shared/self_analysis_profile.py`가 canonical v2 profile을 검증합니다. checklist export는
  raw reflection으로 남고, 미평가 `null`과 검토 후 빈 목록 `[]`을 구분합니다. episode ID,
  activity ID, behavior의 episode 참조도 검증하며 matching이나 Vault context에 자동으로
  들어가지 않습니다.
- 확인된 required skill 또는 experience gap은 `Proceed`가 아니라 `Review`입니다. preferred gap은
  독립적으로 남고 점수나 합격 예측은 추가하지 않습니다.

## 외부 claim과 실행

시간에 따라 바뀌는 salary·platform·market 정보는 [`_shared/career_claims.yml`](_shared/career_claims.yml)에
출처, publisher, 날짜, confidence, claim type, expiry와 함께 등록합니다. 오래된 claim은 `Stale`입니다.
공식 서비스 페이지에 publication date가 없으면 `published_at: unknown`으로 기록하고,
`observed_at`과 `expires_on`은 반드시 명시합니다.

## 상태바 네트워크 동작

상태바는 local-first이지만 24시간에 최대 한 번, 공개 매니페스트
(`https://raw.githubusercontent.com/younnieCutler/japan-recruit-ai-agent/main/.claude-plugin/plugin.json`)를
대상으로 분리된 비동기 버전 확인을 실행할 수 있습니다. 이 요청은 로컬 캐시만 읽고 쓰며
pipeline, Vault, 후보자 데이터를 전송하지 않습니다. 오프라인이거나 요청이 실패하면 조용히
넘어갑니다. 호스트를 시작하기 전에 `JAPAN_RECRUIT_NO_UPDATE_CHECK=1`을 설정하면 외부 요청을
완전히 끌 수 있습니다.

## 기여 및 변경 이력

개발 절차와 Ubuntu/Windows 검증 기준은 [`CONTRIBUTING.md`](CONTRIBUTING.md)에,
릴리스 이력은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

```bash
python scripts/check_policy.py
python scripts/check_claim_freshness.py
python scripts/check_context_budget.py
python scripts/check_reference_paths.py
python scripts/check_agent_context.py
python scripts/check_manifest_consistency.py
python scripts/check_readme_consistency.py
python scripts/test_hook_contract.py
python _shared/test_matching_v3.py
python scripts/test_status_bar.py
python scripts/test_calibrate.py
python scripts/test_pipeline_cli.py
python scripts/test_pipeline_integration.py
python scripts/test_policy.py
python _shared/test_self_analysis_profile.py
python skills/career-agent/test_state_durability.py
node skills/jiko-bunseki/tests/test_checklist_runtime.js
```

CI는 Ubuntu와 Windows에서 실행됩니다. 기존 legacy 데이터는 읽을 수 있지만 신규 legacy write와
MHLW 29-point allocation으로의 자동 변환은 거부합니다.

MIT License.
