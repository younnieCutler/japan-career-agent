# 문서

🌐 [English](README.md) · **한국어** · [日本語](README_ja.md)

[프로젝트 README](../README_ko.md)에 없는 모든 것. 처음이라면 위에서부터 읽으면 되고, 뒤쪽은
레퍼런스와 기록입니다.

번역이 있는 문서는 언어를 함께 적어 두었습니다. 나머지는 영어 원문 하나만 있습니다.

## 시작하기

| 문서 | 다루는 내용 |
|---|---|
| [`upgrading_ko.md`](upgrading_ko.md) | marketplace가 설치하는 버전, 로컬 fallback, `japan-recruit-ai-agent`였던 2.0.x에서 올라오는 방법 |

## 개념과 계약

| 문서 | 다루는 내용 |
|---|---|
| [`FOUR_SKILL_EVOLUTION_DECISIONS.md`](FOUR_SKILL_EVOLUTION_DECISIONS.md) (영어) | 4-skill 분리의 run identity와 routing 결정 규칙 |
| [`HUMAN_OVERSIGHT.md`](HUMAN_OVERSIGHT.md) (영어) | Judgment와 Approval을 분리하는 이유, L0-L3 영향도 모델, Human-first reveal 계약 |
| [`_shared/decision_philosophy.md`](../_shared/decision_philosophy.md) (영어) | 근거·`Unknown`·확인된 conflict가 그렇게 동작하는 이유 |
| [`_shared/schemas.yml`](../_shared/schemas.yml) | canonical profile·pipeline·rules 스키마 |
| [`_shared/career_claims.yml`](../_shared/career_claims.yml) | 시점에 따라 바뀌는 외부 claim과 만료 |

## 아키텍처

| 문서 | 다루는 내용 |
|---|---|
| [`ARCHITECTURE_BOUNDARIES.md`](ARCHITECTURE_BOUNDARIES.md) (영어) | 스킬, 공유 모듈, 결정적 스크립트의 책임 경계 |
| [`DETERMINISTIC_CORE.md`](DETERMINISTIC_CORE.md) (영어) | Host/LLM 출력은 제안으로 남고 Python이 결정적 상태와 불변식을 소유하는 이유 |

## 메인테이너

- [커리어 지식 유지보수](CAREER_KNOWLEDGE.md) (영어): 출처 검토, 토픽 조회, 후보 승격.
- [일본 커리어 리서치 도시에](research/japan-career-market-2026.md) (영어): 검증된 출처와 남은 리서치.

| 문서 | 다루는 내용 |
|---|---|
| [`MAINTAINER_RUNBOOK.md`](MAINTAINER_RUNBOOK.md) (영어) | 검증, 릴리스, marketplace ref 이동, 실패 복구 |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) (영어) | 저장소를 수정하기 전에 읽어야 할 것 |
| [`CHANGELOG.md`](../CHANGELOG.md) | 릴리스 이력 |

표준 로컬 검증 명령은 다음입니다.

```bash
python scripts/run_all_checks.py
```

릴리스 guard는 [`scripts/check_version_bump.py`](../scripts/check_version_bump.py)입니다. 릴리스
버전은 `pyproject.toml`이 소유하며, plugin manifest와 SBOM에는
[`scripts/sync_version.py`](../scripts/sync_version.py)가 기록합니다. 그 외의 파일을 손으로 고칠
필요는 없습니다. 코드에서 도출할 수 있는 문서 사실은
[`scripts/check_docs_drift.py`](../scripts/check_docs_drift.py)가 고정합니다.

## 기록과 실험

이미 끝난 작업의 기록입니다. 코드에서 되살릴 수 없는 판단 근거를 남기기 위한 것이며, 현재 동작을
설명하지는 않습니다.

| 문서 | 다루는 내용 |
|---|---|
| [`LLM_JUDGE_PILOT.md`](LLM_JUDGE_PILOT.md) (한국어) | `job-seeker-agent` LLM-as-judge 파일럿과 채택하지 않은 이유 |
| [`LLM_JUDGE_V2_AUTORESEARCH.md`](LLM_JUDGE_V2_AUTORESEARCH.md) (한국어) | v2 고정 corpus judge 실험과 잠정 결과 |
