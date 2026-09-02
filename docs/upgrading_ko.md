# 호환성과 업그레이드

🌐 [English](upgrading.md) · **한국어** · [日本語](upgrading_ja.md)

## 릴리스 채널

릴리스를 준비하는 동안 저장소의 버전이 stable marketplace 채널보다 앞설 수 있습니다.
stable 채널은 실제로 발행된 최신 immutable `vX.Y.Z` 태그만 가리키며 `main`을 따라가지 않습니다.

지금은 소스 메타데이터가 `2.20.0`인데 stable marketplace ref는 `v2.1.1`입니다. 이 소스에 대한
태그를 릴리스 workflow가 아직 발행하지 않았기 때문이며, 따라서 marketplace로 설치하면 오늘은
`2.1.1`이 설치됩니다. 다음 태그가 발행되면 차이가 닫힙니다.

`uvx`와 `npx`는 이 ref를 따르지 않고 PyPI와 npm에 발행된 최신 버전을 해석합니다. 다만 그 버전은
같은 릴리스 workflow가 태그와 함께 발행하는 것이므로, 실제로는 세 채널 모두 가장 최신 `vX.Y.Z`를
가리키며 어느 쪽도 `main`을 따라가지 않습니다. 아직 발행되지 않은 소스 버전은 clone으로만
얻을 수 있습니다.

> 위 문단의 두 숫자는 각각을 소유한 파일(`pyproject.toml`,
> `.agents/plugins/marketplace.json`)에서
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py)가 읽어
> 대조합니다. 이 절은 빌드를 실패시키지 않고서는 stale해질 수 없습니다.

## 로컬 fallback

파일을 직접 살펴보거나 실행해야 할 때 저장소를 clone하세요.

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

## 2.0.x에서 올라오는 경우 — 이전 이름은 `japan-recruit-ai-agent`

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
[`scripts/verify_release.py`](../scripts/verify_release.py)로 계속 검증됩니다.