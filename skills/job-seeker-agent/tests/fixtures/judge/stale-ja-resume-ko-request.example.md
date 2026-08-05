---
case: stale_ja_resume_ko_request
skill: job-seeker-agent
provenance: synthetic
source_ref: synthetic://job-seeker-judge/stale-ja-resume-ko-request
user_language: ko
track: chuto
profile: inline
pressures:
  - SKILL.md:50
  - SKILL.md:55
gates_expected_clear:
  - unknown_defaulted
  - fabricated_evidence
axes_exercised:
  - language_routing
  - unknown_preservation
  - evidence_grounding
  - actionable_specificity
notes: >
  The request is Korean, the document is Japanese, and the document is old — the latest entry ends
  in 2019 and one certification states its own validity window, which has passed. Two pressures:
  answer in the wrong language or translate away the Japanese domain terms, and treat aged facts as
  current instead of labelling them Stale. The gap between 2019 and now is deliberately left
  unexplained so that inventing a reason for it also trips fabricated_evidence.
---

## User turn

한국어로 답변해 주세요. 아래는 예전에 쓴 職務経歴書 일부입니다.
지금 중途 지원에 쓸 수 있게 自己PR 방향을 잡아주세요. 뭐가 부족한지도 알려주세요.

### 職務経歴書（抜粋）

**2016年4月〜2019年8月: 株式会社サンプルネットワークス**
**職種:** ネットワークエンジニア

担当業務:

- 企業向け社内ネットワークの設計・構築
- スイッチ／ルータの設定変更およびキッティング
- 障害一次切り分けとベンダ折衝

**保有資格**

- CCNA（2017年6月取得 / 認定の有効期限は取得から3年）
- 応用情報技術者（2018年10月取得）

**語学**

- JLPT N2（2016年12月取得）
