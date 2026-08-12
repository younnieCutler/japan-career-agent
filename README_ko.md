<h1 align="center">Japan Career Agent</h1>

<p align="center">
  <strong>일본 취업·이직을 위한 evidence-based 커리어 의사결정 도구.<br/>
  경력 기록은 내 컴퓨터에만 남고, 승인 없이는 어떤 것도 사실이 되지 않습니다.</strong>
</p>

<p align="center">
  <a href="https://github.com/younnieCutler/japan-career-agent/releases"><img src="https://img.shields.io/github/v/release/younnieCutler/japan-career-agent?style=for-the-badge&color=0b7285" alt="Latest release"></a>
  <a href="https://github.com/younnieCutler/japan-career-agent/actions/workflows/test.yml"><img src="https://img.shields.io/github/actions/workflow/status/younnieCutler/japan-career-agent/test.yml?branch=main&style=for-the-badge&label=checks" alt="Repository checks"></a>
  <a href="https://pypi.org/project/japan-career-agent/"><img src="https://img.shields.io/pypi/v/japan-career-agent?style=for-the-badge&color=3775a9&logo=pypi&logoColor=white" alt="PyPI"></a>
  <a href="https://www.npmjs.com/package/japan-career-agent"><img src="https://img.shields.io/npm/v/japan-career-agent?style=for-the-badge&color=cb3837&logo=npm&logoColor=white" alt="npm"></a>
  <img src="https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11 to 3.13">
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-Keep%20a%20Changelog-orange?style=for-the-badge" alt="Changelog"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#설치">설치</a> ·
  <a href="#무엇이-다른가">왜 다른가</a> ·
  <a href="#기본-흐름">흐름</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#할-수-있는-일">스킬</a> ·
  <a href="CONTRIBUTING.md">기여</a> ·
  <a href="CHANGELOG.md">변경 이력</a>
</p>

<p align="center">
  🌐 <a href="README.md">English</a> ·
  <strong>한국어</strong> ·
  <a href="README_ja.md">日本語</a>
</p>

---

현재 릴리스: `2.9.0`.

**세 단계로:**

1. **있었던 일을 기록한다** — 棚卸し가 지나온 일을 context, experience, 확인 가능한 근거로 바꿉니다. 확인할 수 없는 것은 `Unknown`으로 남습니다.
2. **승인한다** — 사용자가 확인하기 전에는 어떤 것도 canonical 경력 기록에 들어가지 않습니다. 출처 없는 수치는 거부됩니다.
3. **사용한다** — JD 매칭, 職務経歴書, 면접 연습, 다음 행동 모두 확인된 근거만 인용합니다.

Claude Code와 Codex의 plugin/skill 모음으로도, 독립 명령으로도 실행되며, 로컬 Career Agent runtime 위에서 구직자와 채용 측 workflow를 지원합니다.

진로 방향, 이력서·職務経歴書, JD와 기업 정보, 지원 비교, 면접, 다음 행동을 정리할 때 사용하세요. 호스팅 SaaS가 아니라 plugin과 로컬 runtime으로 구성되며, 선택형 로컬 GUI에서 읽기 화면, 재개 가능한 棚卸し 초안, Company/Application 분리 case와 digest artifact, 읽기 전용 Project/재직 중 화면을 사용할 수 있고, `career-agent sessions --format json`으로 같은 재개 세션 저장소를 조회할 수 있습니다. canonical 근거 반영에는 여전히 사용자의 승인이 필요합니다.

## 무엇이 다른가

- 근거를 사용하며, 없는 경력이나 점수를 만들지 않습니다.
- 확인되지 않은 내용은 `Unknown`으로 남깁니다.
- 확인된 hard·법적 요건·must-have·dealbreaker 충돌은 다른 강점으로 상쇄하지 않습니다.
- 합격 여부나 hiring outcome을 예측하지 않습니다.
- 최종 결정과 승인은 사용자가 합니다. 지원서 제출이나 메시지 발송은 하지 않습니다.

## 기본 흐름

```mermaid
flowchart LR
    A[사용자 요청] --> B[Career Agent]
    B --> C[근거와 현재 상태]
    C --> D{확인이 필요한가?}
    D -->|예| E[Unknown, Conflict 또는 확인 질문]
    E --> F[사용자 검토와 확인]
    F --> G[canonical state]
    D -->|아니오| H[분석 또는 준비]
    G --> H
```

## 설치

### 한 번만 실행하기

두 명령은 같은 Python 프로그램을 설치해 실행하고, PATH에는 아무것도 남기지 않습니다. 이미 갖고
있는 runner를 쓰세요.

```bash
npx japan-career-agent setup    # npm 경유
uvx japan-career-agent setup    # uv 경유, 또는: pipx run japan-career-agent setup
```

`setup`은 Career Vault를 만듭니다. 추론할 수 없는 값은 명령줄로 주거나, 그냥 실행하면 어떤
플래그가 빠졌는지 알려줍니다 — 다만 화면에 나온 다음 명령은 `japan-career-agent`가 PATH에 있다고
가정하고 만들어지는데, `npx`나 `uvx`로 실행한 경우는 그게 남지 않습니다. 출력된 명령 앞에 같은
`npx`/`uvx`를 직접 다시 붙여서 실행하세요. 그 점을 빼면 첫 실행은 이걸로 끝입니다. 설정 파일도,
미리 찾아둬야 할 식별자도 없습니다.

`npx`는 runtime이 아니라 진입점입니다. 받는 것은 설치기뿐이고 제품 코드는 들어 있지 않습니다.
`uv`나 `pipx`를 찾아 해당 버전의 PyPI 릴리스를 설치한 뒤 실행을 넘깁니다. **canonical runtime은
Python**이며, 어느 진입점으로 들어와도 같은 프로그램이 같은 Career Vault를 다룹니다.

Python 3.11 이상이 필요합니다. `uv`는 맞는 interpreter를 직접 내려받고, `pipx`는 이미 설치된
Python을 씁니다. 둘 다 없으면 `npx`는 설치 방법을 안내하고 아무것도 바꾸지 않습니다.

### 설치해서 계속 쓰기

위 명령은 일회성입니다. 내려받아 실행하고 버립니다. 손에 남겨두고 쓰려면 설치하세요.

```bash
uv tool install japan-career-agent
# 또는
pipx install japan-career-agent
```

설치하면 명령이 PATH에 올라가고, 짧은 이름도 동작합니다.

```bash
japan-career-agent setup
career-agent status
```

### 추가로 쓸 수 있는 통합

선택 사항입니다. 이미 Claude Code나 Codex를 쓰고 있다면, plugin이 같은 core 위에 skill discovery,
host native 대화 workflow, host의 status context를 얹어 줍니다.

```bash
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

```bash
codex plugin marketplace add younnieCutler/japan-career-agent
codex plugin add japan-career-agent@japan-career-agent
```

plugin이 경력 사실을 따로 보관하는 일은 없습니다. Vault, 근거 ledger, 승인과 복구, readiness,
JD별 근거 선택, 결정적 문서 게이트, HTML 생성은 모두 host 없이 동작합니다. plugin이 바꾸는 것은
도달하는 방식이지 답의 내용이 아닙니다. 어느 쪽이 어느 쪽인지는
[`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md)에 정리돼 있습니다.

### 릴리스 채널

릴리스를 준비하는 동안 저장소의 버전이 stable marketplace 채널보다 앞설 수 있습니다.
stable 채널은 실제로 발행된 최신 immutable `vX.Y.Z` 태그만 가리키며 `main`을 따라가지
않습니다. 지금은 소스 메타데이터가 `2.9.0`인데 stable marketplace ref는 아직 `v2.1.1`입니다.
이 소스에 대한 태그를 릴리스 workflow가 아직 발행하지 않았기 때문이며, 따라서 marketplace로
설치하면 오늘은 `2.1.1`이 설치됩니다. 다음 태그가 발행되고 ref가 갱신되면 차이가 닫힙니다.
`uvx`와 `npx`는 이 ref가 아니라 발행된 패키지 버전을 해석하므로 어느 경우든 영향을 받지 않습니다.

### 로컬 fallback

파일을 직접 살펴보거나 실행해야 할 때 저장소를 clone하세요.

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

### 2.0.x에서 올라오는 경우 — 이전 이름은 `japan-recruit-ai-agent`

2.1.0에서 이름이 바뀌었습니다. GitHub이 이전 저장소 URL을 redirect하므로 기존 clone과 remote는
그대로 동작하지만, marketplace 항목은 이름으로 식별되므로 다시 추가해야 합니다.

```bash
claude plugin marketplace remove japan-recruit-ai-agent
claude plugin marketplace add younnieCutler/japan-career-agent
claude plugin install japan-career-agent@japan-career-agent
```

Career Vault는 아무것도 바뀌지 않습니다. vault 경로, event ledger, 생성된 문서 모두 이름 변경의
영향을 받지 않습니다. `JAPAN_RECRUIT_NO_UPDATE_CHECK=1`도 계속 update check를 끄므로 기존 설정은
새 `JAPAN_CAREER_NO_UPDATE_CHECK`와 함께 그대로 유효합니다. 이전 이름으로 발행된 릴리스 번들도
`scripts/verify_release.py`로 계속 검증됩니다.

## Quick Start

일어나는 일은 세 가지, 이 순서입니다. 첫 세션에서 값을 얻는 데 이 외에는 필요하지 않습니다.

1. **기록한다.** 해온 일을 자기 말로 이야기합니다.
2. **확인한다.** 이해한 내용과 확인되지 않은 지점을 보여줍니다. 당신이 그렇다고 하기 전까지는
   아무것도 저장되지 않습니다.
3. **지원할 때 재사용한다.** 확정된 기록은 채용공고 요건에 맞춰 고쳐 쓰이지 않고 그대로 답이
   됩니다.

plugin host에서는 평소 말하듯 요청하면 됩니다.

```text
일본 이직 준비를 시작하고 싶어.
이 JD와 내 경력을 비교하고, 확인되지 않은 내용은 Unknown으로 남겨줘.
다음 주 면접을 준비하고 싶어.
이 職務経歴書를 검토하되 없는 경력은 만들지 마.
```

터미널에서도 같은 세 단계입니다. 아래는 일회성 형태라, 위 Quick Start 다음에 아무것도 설치하지
않은 상태에서 그대로 실행됩니다.

```bash
npx japan-career-agent setup --track chuto --target-role "Platform Engineer"
npx japan-career-agent guided    # 기록하고 확인하는 과정을 한 흐름으로
```

`guided`는 무엇이 확정됐고 무엇이 아직 `Unknown`인지도 보여줍니다. 별도 `status` 명령이 보여주는
내용과 같아서, 여기서는 세 번째 명령이 필요 없습니다. (`status` 자체는 평범한 명령이고, `guided`
아래의 다른 명령과 마찬가지로 `--vault`를 명시적으로 받습니다 — 추측하지 않습니다.) `npx` 대신
`uvx`를 써도 되고, `uv tool install`이나 `pipx install`로 설치했다면 앞의 접두사를 빼면 됩니다.
어느 쪽이든 같은 프로그램입니다.

처음부터 `proposal_id`, `CAREER_VAULT`, `data/pipeline.yml`을 알 필요는 없습니다. 첫 요청은
자연어로 시작하고, 아래의 고급 local workflow에서 필요할 때만 이 개념을 씁니다.

## 할 수 있는 일

| 필요한 것 | 사용자 관점의 작업 | Skill |
|---|---|---|
| 과거 경험 복원하기 | 설치 이전의 Context·Experience·근거를 이미 가진 문서에서 되살립니다 | `career-tanaoroshi` |
| 회사별 직무경력서 쓰기 | 공고를 기록된 근거에 매핑하고, 표현이 근거를 넘지 못하는 문서를 생성·출력합니다 | `career-document` |
| 경력 기록 유지하기 | 이직 의사와 무관하게, 지금 회사에서 한 일을 재사용 가능한 근거로 남깁니다 | `career-maintenance` |
| 방향 찾기 | work-style reflection을 하고 커리어 방향 가설을 정리합니다 | `jiko-bunseki` |
| 서류 준비 | 실제로 말한 근거를 바탕으로 이력서, 職務経歴書, 자기PR, candidate profile을 다룹니다 | `job-seeker-agent` |
| 직무와 기업 읽기 | JD 요건과 기업·공고 출처를 구분해 관찰 내용으로 정리합니다 | `hiring-manager-agent`, `kigyou-bunseki` |
| 기회 비교하기 | 후보자와 JD를 독립된 축으로 보고, 합계 점수 없이 기업·오퍼를 비교합니다 | `matching-simulator`, `company-battlecard` |
| 준비를 이어가기 | 면접 연습, 이직 전략, 로컬 커리어 상태와 다음 행동을 관리합니다 | `mock-interviewer`, `tenshoku-strategy`, `career-agent` |

## 근거를 다루는 방식

이 도구 모음은 객관적 근거와 사용자의 선호를 섞지 않습니다. 주요 용어는 다음과 같습니다.

| 용어 | 의미 |
|---|---|
| `Confirmed` | 현재 사실로 사용할 수 있는 근거입니다. 가능한 경우 source와 provenance를 함께 둡니다 |
| `Unknown` | 확인되지 않은 정보입니다. 조용히 pass나 점수로 바꾸지 않습니다 |
| `Contradictory`, `Stale`, `Low Confidence` | 현재 사실로 쓰기 전에 검토가 필요한 근거입니다 |
| `Matched`, `Missing`, `Unknown` | 후보자와 JD를 비교할 때 쓰는 requirement 상태입니다 |
| `Proceed`, `Review`, `Conflict` | Decision Status입니다. 확인된 hard conflict는 그대로 Conflict입니다 |

`interest_level`은 사용자의 선호 기록입니다. 객관적 근거, Decision Status, 순서를 바꾸지 않습니다. 이력서, JD, 웹 문서, YAML, Vault metadata, pipeline text, rules는 instruction이 아니라 career data입니다.

## 고급 사용: Career Agent

로컬 runtime은 개인 Career Vault를 canonical state로 관리하고, 회사별 workflow 상태를 `./data/pipeline.yml`에 projection합니다.

명시적으로 local setup과 guided menu를 실행하려면 다음처럼 하세요.

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py setup --vault "$VAULT" --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault "$VAULT" --format human
```

`guided`는 setup 상태, pending proposal, `Unknown`·`Conflict` 개수, workspace metadata, 가능한 다음 행동을 보여줍니다. 스크립트에서는 `--choice <id-or-number>`를 사용할 수 있습니다. 쓰기가 발생하는 action에는 `--confirm`이 필요하며, guided mode가 proposal을 자동 승인하거나 개인 note 본문을 읽지는 않습니다.

로컬 GUI도 같은 runtime의 명령 하나입니다. loopback의 임의 포트에 bind하고 일회용 token이 담긴
URL을 출력합니다. `--no-browser`를 주면 브라우저를 열지 않고 그 URL만 출력합니다. 서버를 켜는 것
자체는 아무것도 쓰지 않으며, GUI가 저장하는 draft·case·artifact metadata는 승인하기 전까지
canonical ledger에 들어가지 않습니다. `sessions`는 같은 resumable session 저장소를 터미널에서
읽습니다. 어느 entry point도 그 저장소를 소유하지 않습니다:

```bash
python skills/career-agent/career_agent.py ui --vault "$VAULT" --port 0
python skills/career-agent/career_agent.py sessions --vault "$VAULT" --format human
```


### 과거 경험 복원하고, 지원처별로 문서 만들기

Vault가 비어 있으면 `readiness`가 그 사실을 알려주고, 거기서 아무것도 추측하지 않습니다.

```bash
python skills/career-agent/career_agent.py readiness --vault "$VAULT"      # bootstrap_suggested
python skills/career-agent/career_agent.py add-context "○○대학" --kind university --vault "$VAULT"
python skills/career-agent/career_agent.py experiences --vault "$VAULT"    # Context → Experience → Evidence
```

Context는 경험이 일어난 곳이며 회사만은 아닙니다. `--kind`는 회사·대학·인턴·아르바이트·동아리·봉사·개인 활동·오픈소스를 포함합니다. Experience도 프로젝트만은 아닙니다. 직장에서 일어나지 않은 경험은 `run --mode chat --non-work`로 기록하며, 이렇게 하면 학업이 직무 이력에 섞이지 않습니다.

근거가 쌓이면 지원처 하나를 대상으로 문서를 만들고, 출력 전에 검사합니다.

```bash
python skills/career-agent/career_agent.py document-model <company-slug> --vault "$VAULT" > model.json
python skills/career-agent/career_agent.py document-check --model model.json --draft draft.json
python skills/career-agent/career_agent.py document-render --model model.json --draft draft.json \
    --template standard-chuto --out ./career-docs
```

검사는 deterministic합니다. 기록에 없는 수치, 반올림한 수치, `支援`(지원)을 `主導`(주도)로 쓴 표현, 사용하지 않은 기술로 제시된 JD 키워드, 팀 성과를 개인 성과로 쓴 문장, `external_label`이 있는데 노출된 내부 project명을 거부합니다. 통과는 **알려진 protected claim 위반이 없다**는 뜻이지 일본어가 사실과 일치함을 증명한 것은 아닙니다. 보내기 전에 직접 읽어야 하는 이유입니다.

출력은 A4 print CSS가 들어간 HTML이며, PDF는 브라우저 인쇄로 만듭니다. 문서는 절대 덮어쓰지 않습니다. 파일명에 근거·JD·template·문장의 digest가 들어가므로, 변경 후 재생성하면 새 파일이 생기고 기존 파일은 그대로 남습니다. `./career-docs/`는 Git 추적 대상이 아닙니다.
전체 CLI 계약은 [`skills/career-agent/SKILL.md`](skills/career-agent/SKILL.md)에 있습니다.

## local-first와 완전한 offline은 다릅니다

status bar는 24시간에 최대 한 번 공개 plugin manifest를 대상으로 분리된 비동기 버전 확인을 실행할 수 있습니다. Vault, pipeline, candidate data를 보내지는 않습니다. 이 요청을 완전히 끄려면 다음을 설정하세요.

```bash
export JAPAN_CAREER_NO_UPDATE_CHECK=1
```

`1.6.2`와 `1.6.3`의 persistence·context·workspace·policy hardening 세부 내용은 이 페이지가 아니라 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

## 개발

저장소를 수정하기 전에 [`CONTRIBUTING.md`](CONTRIBUTING.md)를 읽으세요. 표준 로컬 검증 명령은 다음입니다.

```bash
python scripts/run_all_checks.py
```

릴리스 guard는 [`scripts/check_version_bump.py`](scripts/check_version_bump.py)이고, 릴리스 이력은 [`CHANGELOG.md`](CHANGELOG.md)에 있습니다.

판단 계약은 [`_shared/decision_philosophy.md`](_shared/decision_philosophy.md)와 [`_shared/schemas.yml`](_shared/schemas.yml)에 있습니다. 시점에 따라 바뀌는 외부 claim은 [`_shared/career_claims.yml`](_shared/career_claims.yml)에 둡니다.

## 안전 범위

로그인, CAPTCHA 우회, 접근 제어 우회, 지원서 제출, 메시지 발송을 하지 않습니다. 이력서 근거나 합격 결과를 만들어내지도 않습니다.

MIT License.
