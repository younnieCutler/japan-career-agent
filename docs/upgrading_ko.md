# 호환성과 업그레이드

🌐 [English](upgrading.md) · **한국어** · [日本語](upgrading_ja.md)

## 릴리스 채널

릴리스를 준비하는 동안 저장소의 버전이 stable marketplace 채널보다 앞설 수 있습니다.
stable 채널은 실제로 발행된 최신 immutable `vX.Y.Z` 태그만 가리키며 `main`을 따라가지 않습니다.

지금은 소스 메타데이터가 `3.0.1`인데 stable marketplace ref는 `v2.1.1`입니다. 이 소스에 대한
태그를 릴리스 workflow가 아직 발행하지 않았기 때문이며, 따라서 marketplace로 설치하면 현재는
`2.1.1`이 설치됩니다. 다음 태그가 발행되면 차이가 닫힙니다.

아직 발행되지 않은 소스 버전은 clone으로만 얻을 수 있습니다.

> 위 문단의 두 숫자는 각각을 소유한 파일(`pyproject.toml`,
> `.agents/plugins/marketplace.json`)에서
> [`scripts/check_release_consistency.py`](../scripts/check_release_consistency.py)가 읽어
> 대조합니다. 이 절은 빌드를 실패시키지 않고서는 stale해질 수 없습니다.

## 로컬 fallback

파일을 직접 살펴보거나 실행해야 할 때 저장소를 clone하세요.

```bash
git clone https://github.com/younnieCutler/japan-career-agent.git
```

워크스페이스 상태는 `./data/`(`evidence.yml`, `pipeline.yml`, `applications.yml`, `rules.yml`)에,
생성된 문서는 `./career-docs/`에 저장됩니다. `JAPAN_CAREER_NO_UPDATE_CHECK=1`을 설정하면 24시간 주기
매니페스트 버전 확인을 끌 수 있습니다.
