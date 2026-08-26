# CLI 레퍼런스

🌐 [English](cli-reference.md) · **한국어** · [日本語](cli-reference_ja.md)

로컬 runtime은 개인 Career Vault를 canonical state로 관리하고, 회사별 workflow 상태를
`./data/pipeline.yml`에 projection합니다.

이 페이지의 모든 내용은 plugin과 `npx`/`uvx` 진입점이 실행하는 것과 같은 프로그램입니다. host는
필요하지 않습니다.

## setup과 guided menu

명시적으로 local setup과 guided menu를 실행하려면 다음처럼 하세요.

```bash
VAULT=/path/to/career-agent-vault
python skills/career-agent/career_agent.py setup --vault "$VAULT" --track chuto --target-role "Platform Engineer"
python skills/career-agent/career_agent.py guided --vault "$VAULT" --format human
```

`guided`는 setup 상태, pending proposal, `Unknown`·`Conflict` 개수, workspace metadata, 가능한 다음
행동을 보여줍니다. 스크립트에서는 `--choice <id-or-number>`를 사용할 수 있습니다. 쓰기가 발생하는
action에는 `--confirm`이 필요하며, guided mode가 proposal을 자동 승인하거나 개인 note 본문을 읽지는
않습니다.

## 과거 경험 복원하고, 지원처별로 문서 만들기

Vault가 비어 있으면 `readiness`가 그 사실을 알려주고, 거기서 아무것도 추측하지 않습니다.

```bash
python skills/career-agent/career_agent.py readiness --vault "$VAULT"      # bootstrap_suggested
python skills/career-agent/career_agent.py add-context "○○대학" --kind university --vault "$VAULT"
python skills/career-agent/career_agent.py experiences --vault "$VAULT"    # Context → Experience → Evidence
```

Context는 경험이 일어난 곳이며 회사만은 아닙니다. `--kind`는 회사·대학·인턴·아르바이트·동아리·
봉사·개인 활동·오픈소스를 포함합니다. Experience도 프로젝트만은 아닙니다. 직장에서 일어나지 않은
경험은 `run --mode chat --non-work`로 기록하며, 이렇게 하면 학업이 직무 이력에 섞이지 않습니다.

근거가 쌓이면 지원처 하나를 대상으로 문서를 만들고, 출력 전에 검사합니다.

```bash
python skills/career-agent/career_agent.py document-model <company-slug> --vault "$VAULT" > model.json
python skills/career-agent/career_agent.py document-check --model model.json --draft draft.json
python skills/career-agent/career_agent.py document-render --model model.json --draft draft.json \
    --template standard-chuto --out ./career-docs
```

검사는 deterministic합니다. 기록에 없는 수치, 반올림한 수치, `支援`(지원)을 `主導`(주도)로 쓴 표현,
사용하지 않은 기술로 제시된 JD 키워드, 팀 성과를 개인 성과로 쓴 문장, `external_label`이 있는데
노출된 내부 project명을 거부합니다. 통과는 **알려진 protected claim 위반이 없다**는 뜻이지 일본어가
사실과 일치함을 증명한 것은 아닙니다. 보내기 전에 직접 읽어야 하는 이유입니다.

출력은 A4 print CSS가 들어간 HTML이며, PDF는 브라우저 인쇄로 만듭니다. 문서는 절대 덮어쓰지
않습니다. 파일명에 근거·JD·template·문장의 digest가 들어가므로, 변경 후 재생성하면 새 파일이 생기고
기존 파일은 그대로 남습니다. `./career-docs/`는 Git 추적 대상이 아닙니다.

## 로컬 GUI 실행하기

GUI도 같은 runtime의 명령 하나입니다. loopback의 임의 포트에 bind하고 일회용 token이 담긴 URL을
출력합니다. `--no-browser`를 주면 브라우저를 열지 않고 그 URL만 출력합니다.

```bash
python skills/career-agent/career_agent.py ui --vault "$VAULT" --port 0
python skills/career-agent/career_agent.py sessions --vault "$VAULT" --format human
```

서버를 켜는 것 자체는 아무것도 쓰지 않습니다. GUI가 저장하는 draft·case·artifact metadata는
승인하기 전까지 canonical ledger에 들어가지 않습니다. `sessions`는 같은 resumable session 저장소를
터미널에서 읽습니다. 어느 entry point도 그 저장소를 소유하지 않습니다.

설계 결정과 UI 구현 계약은 [`GUI_DESIGN_DECISIONS.md`](GUI_DESIGN_DECISIONS.md)에 있습니다.

## Skill 실행 기록

Skill을 선택하는 것과 실제로 실행하는 것은 다릅니다. `run --mode chat`과 `skills`는 이번 요청이
어떤 Skill을 쓸지 알려줄 뿐이고, 실제로 실행했다는 기록은 `skill-open`과 `skill-report`로 host가
남깁니다. host가 필요한 Skill인데 쓸 수 있는 host가 없으면, 실행한 것처럼 답하는 대신
`unsupported`를 반환합니다.

## 전체 계약

이 페이지는 자주 쓰는 명령을 다룹니다. 모든 subcommand·플래그·exit code·출력 형태를 포함한 전체
CLI 계약은 [`skills/career-agent/SKILL.md`](../skills/career-agent/SKILL.md)에 있습니다.
