# ATS · Scout-Search Keyword Optimization (STEP 4-1b)

> After the 再現性 rewrite (STEP 4-1), verify the document is **findable**. A resume that no CA search,
> scout search, or ATS filter ever surfaces is never read, however well written. This module extracts the
> target JD's keywords, checks resume coverage, and fixes placement — without fabricating experience.
>
> **Relation to matching-simulator STEP 5:** if `matching-simulator` already ran for this JD, its STEP 5
> 職務経歴書 Customization Plan lists 5–8 mirror keywords as a byproduct of the gap analysis. That is a
> quick subset; this module is the full treatment (表記揺れ variants, hit/miss/add coverage table,
> anti-stuffing caps) and should run regardless of whether matching-simulator was used.

**Core Principle:** Keyword optimization = making real experience *searchable*, never claiming unreal
experience. Every added keyword must trace to evidence already scored in STEP 3.

---

## 1. Where keywords actually matter in the Japanese market

Unlike the US pattern (ATS auto-reject scoring), Japanese systems use keywords mainly for **search and
filter** — a human always reads what surfaces. The goal is *hit rate*, not beating a robot:

| Layer | System examples | What is searched |
|-------|----------------|------------------|
| Agent internal DB | Recruit Agent / doda CA search | 職務要約, skill fields, 経験職種 — CAs pull candidate lists by keyword before recommending |
| Scout DB | BizReach, doda X, Green, LinkedIn Recruiter | 職務要約 + skill/経験 fields are the search index; headline quality decides open rate |
| Company ATS | HERP Hire, HRMOS, sonar ATS, ジョブカン採用管理 | Applicant search/filter during screening; keyword tags |

Implication: the **職務要約 (top 3–5 lines) and the skill/経験 summary section carry almost all search
weight**. Body prose matters for reading, not for retrieval.

---

## 2. Extract the JD's keyword set

From the target JD (STEP 0 input), build the canonical keyword list:

1. **必須条件 nouns** — hard skills, tools, 経験職種, years ("Python", "要件定義", "toC マーケ 3年").
2. **歓迎条件 nouns** — secondary keywords; include only those the candidate actually has.
3. **Role-title variants** — the JD's own title + market synonyms (the scout search uses the market term).
4. **Domain nouns** — industry/domain words the JD repeats (SaaS, 医療, 物流, EC) — CAs search these too.

Weight: 必須 > role title > domain > 歓迎.

---

## 3. 表記揺れ (orthographic variants) — the top silent killer

Japanese resumes lose search hits to script variants. Rule: **first occurrence = formal name + common
variant together**, e.g. 「Kubernetes（K8s）」「プロダクトマネージャー（PdM）」. Afterwards either form.

| Canonical | Variants that miss each other in search |
|-----------|------------------------------------------|
| Kubernetes | K8s / クバネティス |
| Google Cloud | GCP / Google Cloud Platform |
| プロダクトマネージャー | PdM / PM / プロダクトマネジメント |
| 機械学習 | ML / マシンラーニング |
| データエンジニア | Data Engineer / DE / データ基盤エンジニア |
| 要件定義 | 要求定義 / requirements definition |
| マネジメント経験 | ピープルマネジメント / 部下育成 / チームリード |
| BtoB | B2B / 法人向け |
| 広告運用 | 運用型広告 / リスティング運用 / パフォーマンスマーケティング |

Match the **JD's own spelling first** (if the JD writes "K8s", make sure "K8s" appears verbatim), then add
the canonical form once.

---

## 4. Placement priority

| Priority | Location | Why |
|----------|----------|-----|
| ① | **職務要約 (top 3–5 lines)** | Highest search weight + the first thing a CA/scout reads. The core-lead-tech and role keywords MUST appear here. |
| ② | **スキル・経験 summary section** | Structured bullet list (skill / years / level) — the cleanest index target. Create this section if the resume lacks one. |
| ③ | **Each 職歴 body** | Keywords woven into 役割/工夫/成果 sentences (natural placement — supports the ① claims with evidence) |
| ④ | Scout-service profile fields (希望職種, 経験職種 tags) | Platform-side dropdown/tags — set them to match the target role, not the past role only |

---

## 5. Coverage Check — output format (mandatory)

```
■ ATS/検索キーワード カバレッジ: 12/15 (必須 7/8 · 職種 2/2 · ドメイン 2/3 · 歓迎 1/2)

| JD keyword | 重み | resume内の表記 | 判定 | 配置 |
|------------|------|----------------|------|------|
| Python     | 必須 | 「Python」職務要約+職歴2 | ✅ hit | ①③ |
| K8s        | 必須 | 「Kubernetes」のみ       | ⚠️ 表記揺れ — 「Kubernetes（K8s）」へ | ② |
| dbt        | 必須 | なし（経験あり: STEP 1で言及） | ✳️ add — 職務要約+スキル欄へ | — |
| Airflow    | 必須 | なし（経験なし）          | ❌ miss — 追加禁止、ギャップとして扱う | — |

■ 修正指示: [concrete edits, per row]
■ ❌ miss items: routed to STEP 0 gap verdict / STEP 4-0b learning plan — NOT added to the resume.
```

Verdicts: `✅ hit` (verbatim or accepted variant present) / `⚠️ 表記揺れ` (experience present, spelling
misses the JD) / `✳️ add` (experience evidenced in STEP 1–3 but absent from the document) / `❌ miss`
(no experience — never added).

---

## 6. Anti-Stuffing Rules (hard)

- **❌ miss keywords are never inserted.** A keyword without experience behind it is fabrication — it fails
  at the interview 深掘り and, at reference-check time, worse (`../../tenshoku-strategy/references/nyusha-teichaku.md` §2).
- **No keyword-salad sentences.** 「Python, SQL, AWS, Docker, K8sを使用」 with no 役割/成果 attached reads
  as padding to the human who opens the hit. Keywords live inside real sentences (STEP 4-1 axes).
- **Touched ≠ skilled:** a tool used once in a tutorial goes in only with an explicit level marker
  (「学習中」「個人開発で使用」) — consistent with the STEP 3 "Learning ≠ Skill" rule.
- Cap: if more than ~30% of proposed edits are keyword insertions with no new evidence, stop and re-run the
  STEP 0 gap analysis — the problem is fit, not findability.
