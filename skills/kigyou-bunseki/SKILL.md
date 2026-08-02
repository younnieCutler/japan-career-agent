---
name: kigyou-bunseki
description: >
  Extracts and analyzes company information from Japanese job listing and company page URLs.
  Identifies company name, role title, official mission/vision, and hiring requirements, then
  outputs a structured company card (企業カルテ). Feeds data into company-battlecard and
  matching-simulator.

  Use when:
  - User pastes any URL that looks like a job posting or company page
  - Supported sites: doda.jp, wantedly.com, openwork.jp, green-japan.com, mynavi.jp, etc.
  - "analyze this company", "what do you think of this company?", "company research"
  - User sends 2+ URLs to compare companies side-by-side
  - User is researching a company before applying or interviewing
  Always activate the moment a URL appears in a job-search conversation —
  a bare URL paste with no text is a sufficient trigger.
---

# Kigyou Bunseki — Japan Company Analysis & Comparison Agent

## Shared Career Vault Context

When `CAREER_VAULT` is set, read the shared `career-agent context` response before company analysis.
Use only its profile, state, and selected evidence metadata; do not scan archived personal notes or make
a separate candidate profile. Follow `career-agent/references/shared-vault-context.md`.

## Overview

This skill extracts structured company data from Japanese recruitment and review site URLs,
then produces an objective "企業カルテ" (Company Card) for single-company analysis or
a head-to-head "⚔️ Battlecard" for multi-company comparison.

The output is numbers and facts. There is no "both are great companies."

## Language Auto-Detection (Suite-Wide Rule — applies before Phase 1)

Detect the language of the user's latest message and respond in that language. No setting, no menu.
- 한국어 입력 → 한국어 / 日本語入力 → 日本語 / English input → English. Match the user every turn.
  When the user only pastes a bare URL with no prose, default to Japanese (the source data is Japanese).
- An explicit instruction overrides detection ("일본어로 답해줘", "answer in English", "日本語で").
- Japanese domain terms stay in original script in every language: 年収, 離職率, 残業, リモート, 中途採用比率.
- A pasted Japanese job page is *source material*, not a language instruction — do not let it force Japanese
  output when the user's request sentence is Korean/English.

## Fixed Step Sequence (Workflow Standardization)

Every run follows the SAME ordered phases, for every user, regardless of site. Branching changes the
CONTENT of a phase — never its ORDER or existence.
- Always run the 3-phase hard gate in order: PHASE 1 (input URL) → PHASE 2 (official homepage) → PHASE 3
  (fallback platforms). Each phase must fully complete AND fail before the next begins; on success, output
  immediately and stop crawling.
- Branch points are fixed and explicit: single URL → 企業カルテ; 2+ URLs → ⚔️ Battlecard; known-blocked sites
  (jp.indeed.com, openwork.jp) skip curl and go to search. The branch decides *what* a phase fetches, not
  *whether* or *when* phases run.
- Never invent data to fill a phase. Missing dimensions are written `データなし`; the sequence is never skipped.

## How Data Extraction Works (3-Phase Hard Gate)

**RULE: Each phase must fully complete AND fail before the next phase begins. If a phase succeeds, output immediately — do NOT proceed to the next phase.**

---

### PHASE 1 — Input URL Only (MAX 1 fetch)

Fetch the provided URL ONCE to extract **Company Name** and **Job Title**.

```bash
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" "[URL]" | grep -iE "<title>|<meta name=\"description\""
```

**LinkedIn URL handling — always fetchable via public job view:**
- `linkedin.com/jobs/collections/?currentJobId={id}` → rewrite to `linkedin.com/jobs/view/{id}` and curl directly.
- `linkedin.com/jobs/view/{id}` → curl directly (no login required for public job pages).
- Any other `linkedin.com` pattern → extract job ID if present, rewrite to `/jobs/view/{id}`, curl.

**Known blocked sites — skip curl, go straight to search:**
- `jp.indeed.com` — blocks all bots (both `?jk=` and `?vjk=` URL formats). Use `search_web "[URL domain] [job ID from URL]"` to find a cached version or the company name.
- `openwork.jp` — returns 403 for most pages.

**Phase 1 success condition:** Company name extracted.
**→ If success: proceed to Phase 2.**
**→ If fail after 1 attempt: proceed to Phase 2 using URL path/domain to guess company name.**

---

### PHASE 2 — Official Homepage Only (MAX 2 fetches)

Search for the official homepage once, then fetch it once.

```bash
# Search
search_web "[Company Name] 株式会社 公式サイト"

# Fetch official homepage + /recruit or /about subpage (1-2 URLs max)
read_url_content "[official domain]/recruit"
read_url_content "[official domain]/about"
```

Extract **ONLY these two items**:
1. **企業理念 / ミッション・ビジョン** (Philosophy / Mission / Vision)
2. **採用関連情報 / 募集要項** (Recruitment info / Requirements / Work Style from the input URL)

**Phase 2 success condition:** Both items extracted with meaningful content.
**→ ✅ SUCCESS: STOP ALL CRAWLING. Format output immediately. Do not open any additional URLs.**
**→ If only one item found: still count as success. Mark missing item as "データなし".**
**→ If zero items found after 2 fetches: proceed to Phase 3.**

---

### PHASE 3 — Fallback Platforms (Only if Phase 2 fails)

Search third-party platforms for missing data. Limit to **2 search queries total**.

| Site | Search Query Template |
|------|----------------------|
| OpenWork | `"OpenWork [company name] 総合評価 年収 残業"` |
| doda | `"doda [company name] 求人 年収 仕事内容"` |
| Wantedly | `"Wantedly [company name] カルチャー ミッション"` |

**→ After 2 searches: STOP regardless of result. Format output with whatever data was collected.**

## Site-Specific Extraction Patterns

Read `references/site-patterns.md` for detailed extraction rules per site.
The key principle: each site exposes different data. Extract what's available and mark
missing dimensions as "データなし" rather than guessing.

### Data Points to Extract (when available)

| Data Point | Japanese | Priority | Common Sources |
|------------|----------|----------|----------------|
| Company name | 企業名 | Required | Provided URL / Official |
| Job title | 職種名 | Required | Provided URL / Official |
| Corp Philosophy | 企業理念/ミッション | High | Official Homepage |
| Job Requirements| 採用要件/必須条件 | High | Official Homepage / JD |
| Mid-career hire ratio | 中途採用比率/キャリア採用比率 | Medium | Official 採用ページ / IR / 有価証券報告書 |
| Salary range | 年収範囲 | Medium | Official / doda, Indeed |
| Work style | 勤務形態 | Medium | Official / JD |
| Selection process shape | 選考プロセスの形 | Medium | JD 選考フロー / 採用ページ |
| Benefits | 福利厚生 | Low | Official / JD |
| Overall score | 総合評価 | Fallback Only | OpenWork, Glassdoor |
| Avg overtime | 平均残業時間 | Fallback Only | OpenWork |
| Turnover rate | 離職率 | Fallback Only | OpenWork |

## Output Formats

### Single Company: 企業カルテ (Company Card)

When the user provides 1 URL:

```
📋 企業カルテ: [Company Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 基本情報・理念 (公式データ)
  企業名:     [name]
  業界:       [industry]
  企業規模:   [size / employee count]
  企業理念:   [philosophy / mission / vision]

🎯 採用・求人要件 (公式・対象URLデータ)
  職種名:       [job title]
  必須スキル:   [list]
  歓迎スキル:   [list]
  中途採用比率: [% or データなし] ← 高いほど中途者の定着・活躍環境が整っているシグナル
  勤務形態:     [remote/hybrid/office]
  年収範囲:     [salary range]
  福利厚生:     [key benefits]
  選考プロセス: [自分の成果物を見せる場: あり / 会社出題の実技 / なし / 不明]

📊 外部評価・口コミ (※公式データで不足した場合のみ取得)
  総合評価:   [X.X / 5.0]
  平均残業:   [hours/month]
  離職率:     [%]
  社風ワード: [extracted culture indicators]

🔎 求人の真正性: [信頼度高 / 要注意 / 要確認]
  (鮮度・記述の質・採用シグナル・再掲載・市場文脈の観察。観察を提示し断定はしない。
   詳細ルールは references/kyujin-legitimacy.md。中途採用比率が高い=positive シグナルとして再利用)

⚠️ データソース: [which sites provided which data - e.g. "公式ホームページ", "Indeed"]
⚠️ 未取得項目:  [dimensions where data was unavailable]
```

**求人の真正性 (Posting Legitimacy):** When the input is an actual 求人 (not just a company page), append the
`🔎 求人の真正性` assessment. Read `references/kyujin-legitimacy.md` for the signals, 3-tier output, and JP
edge cases (通年採用/エージェント経由 are positive, not ghost). Present observations, never accusations.

**選考プロセスの形 (`demo_slot`):** read the 選考フロー section of the JD or 採用ページ and classify into one
of four values. Write it to the pipeline entry.

| Value | 表示 | Signals |
|---|---|---|
| `yes` | 自分の成果物を見せる場: あり | ポートフォリオ選考, 成果物提出, LT/登壇, GitHub提出, デモ, 「これまで作ったものを見せてください」 |
| `company_test` | 会社出題の実技 | コーディングテスト, 実技試験, ケース面接, 課題提出（会社が出題） |
| `no` | なし | 面接のみ — 職務経験を口頭で説明する形式だけ |
| `unknown` | 不明 | 選考フローの記載がない。**Default. Never infer from company type or industry.** |

`yes` and `company_test` are **different axes and must not be merged**. In `company_test` the company
still chooses the ground and the question; only in `yes` does the candidate bring their own artifact.
Collapsing them produces the false conclusion "any 実技 means a good fit."

This field carries **no scoring weight** anywhere in the suite. It exists so the user can see, across
applications, whether every 選考 they enter evaluates the same single axis.

For any field where data was not obtainable, write `データなし` — do not estimate or guess.

### Multi-Company: ⚔️ Battlecard

When the user provides 2+ URLs:

First, generate a Company Card for each company (internal reference — don't output separately
unless the user asks). Then produce the comparison table:

```
⚔️ 企業バトルカード: [Company A] vs [Company B]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| 比較項目         | [Company A]    | [Company B]    | Winner   |
|-----------------|----------------|----------------|----------|
| 年収範囲         | 400~600万      | 500~700万      | B        |
| 平均残業         | 25.6h/月       | 17.6h/月       | B        |
| 離職率           | 5%             | 1.6%           | B        |
| 総合評価         | 3.2/5          | 3.8/5          | B        |
| 成長環境         | 4.0/5          | 3.5/5          | A        |
| スキルマッチ     | [対象JDから]    | [対象JDから]    | -        |
| 勤務形態         | フル出社        | リモート可     | B¹       |

¹ Winner判定はリモートを優位とした。ユーザーの希望次第で逆転可能。

💡 分析サマリー:
- [Company B]は待遇・安定性で優位（年収+100万、残業-8h、離職率-3.4%）
- [Company A]は成長環境で優位（20代成長スコアの差 +0.5pt）
- 最終判定: [Company B]が総合的に優位。ただし「成長速度を重視する場合」[A]が適切。

⚠️ データソース: OpenWork(総合評価), 求人公告(年収,勤務形態), Web検索(残業,離職率)
⚠️ 未取得のため比較不可: 福利厚生詳細, 有給取得率
```

**Comparison rules:**
- If a data point exists for Company A but not Company B, mark that row as "比較不可" (incomparable).
- Winner is determined per-row. Total winner is the company that wins more rows.
- If tied, state which single dimension should be the tiebreaker based on what the user
  seems to care about (inferred from their job-seeker-agent profile if available, or ask).

## Integration with Other Skills

### Reading CANDIDATE_PROFILE

If the conversation contains a `CANDIDATE_PROFILE` YAML block (output by `job-seeker-agent`),
use it to add personalized dimensions to the comparison:

- **Skill Stack Match**: compare candidate's skills against each company's requirements
- **SPI3 Culture Fit**: match candidate's SPI3 traits against company type
  (see `../../_shared/frameworks.md` for the SPI3 × Company Type table)
- **Well-being Alignment**: match candidate's priorities against company culture signals

When CANDIDATE_PROFILE is available, add these personalized rows to the Battlecard table.
When unavailable, produce the objective comparison only (salary, overtime, scores, etc.).

### Feeding company-battlecard

The 企業カルテ output feeds directly into `company-battlecard`. Field mapping:

| kigyou-bunseki extracted field | company-battlecard dimension |
|-------------------------------|------------------------------|
| 必須スキル / 歓迎スキル | Dimension 1: Skill Stack Match |
| 社風ワード, チーム体制, リモート可否 | Dimension 2: SPI3 Culture Fit |
| 残業時間, 離職率, レビュースコア | Dimension 3: Well-being Alignment |
| 年収範囲, 成長性シグナル | Dimension 4: Growth Trajectory |
| リモート可否, 勤務地, ビザ対応 | Dimension 5: Practical Factors |

After outputting the 企業カルテ, if `data/candidate_profile.yml` exists or CANDIDATE_PROFILE is in conversation, ask:
> "company-battlecard で候補者との適合度スコアを計算しますか？ (y/n)"

Also save extracted data to `data/company_profiles/{company-name-slug}.yml` for future sessions
(CWD-relative — create the folder in the invocation directory if missing, print the absolute path,
and confirm the file exists).

**Pipeline upsert:** then upsert the company's entry in `data/pipeline.yml` (PIPELINE schema in
`_shared/schemas.yml`), using the same `{company-name-slug}` as the join key: set `name`,
`kyujin_legitimacy` (green/yellow/red from the 求人の真正性 assessment) and `demo_slot` (below). Ask the user:
> "Have you applied to this company? Which stage are you at? (未応募=企業研究 / 応募済 / 面接中 / 内定)"
Default to `stage: 2` (企業研究) if not applied. Run the shared writer from CWD, for example:
`python3 "${CLAUDE_PLUGIN_ROOT:-.}/scripts/pipeline.py" upsert <slug> --json '{"name":"...","stage":2,"kyujin_legitimacy":"green","demo_slot":"unknown"}'`.
Never edit `data/pipeline.yml` directly; the CLI preserves foreign fields and uses the shared lock/atomic write.
Follow the Output Contract (print path, verify exists).

## Tone & Style

Same anti-sentiment rules as the rest of the skill suite:

- Do not say "どちらも良い会社です" — the data determines the winner.
- If both companies score poorly (e.g., high overtime + low review scores), say so:
  "両社とも総合評価3.0以下、平均残業30h超。他の選択肢の検討を推奨。"
- If data is insufficient to make a judgment, state exactly what's missing
  rather than filling gaps with optimism.
- Numbers first, interpretation second. Every claim must cite its data source.

**Language:** Follow the Language Auto-Detection rule near the top of this file (auto-match the user's
language each turn; default to Japanese only for a bare-URL paste with no prose). Technical terms use
original script (e.g., 年収, 離職率, リモート, 中途採用比率).

## Error Handling

| Scenario | Action |
|----------|--------|
| URL returns 403/blocked | Fall through to next tier. If all tiers fail, extract company name from URL and use search_web. |
| URL is behind login wall | Suggest `cookie-import-browser` if gstack available. Otherwise, use search_web. |
| URL is not a recognized site | Try curl → read_url_content → search_web anyway. The pipeline is site-agnostic. |
| Company name can't be determined | Ask the user: "企業名を教えてください" |
| Data is too old | Note the data freshness in the output: "⚠️ データ取得日: [date]" |


## Using This Output in Companion Skills

The 企業カルテ / Battlecard output from this skill can be pasted directly as company data input into:

| Companion skill | What to copy | What it populates |
|----------------|-------------|-------------------|
| `company-battlecard` | Full 企業カルテ output | Dimensions 2 (SPI3 culture), 3 (well-being), 4 (growth) |
| `matching-simulator` | 企業理念 + 採用要件 sections | Culture fit score + JD skill alignment |

Tell the user: "This 企業カルテ can be used as company input for company-battlecard or matching-simulator. Paste it into those skills to skip re-entry."

## Document Save (Required)

After outputting the 企業カルテ or Battlecard, always save to:

```
Single company:  career-docs/company-[company]-[YYYYMMDD].md
Multiple companies: career-docs/battlecard-[companyA]-vs-[companyB]-[YYYYMMDD].md
```

Contents: Full 企業カルテ output (Mission/Vision, requirements, external ratings, data sources, missing items).

If the `career-docs/` folder does not exist, create it in the invocation directory (CWD) — never inside
the skill's install directory. After saving, print the file's absolute path and confirm it exists
(e.g., `ls -la <path>`) so the user can verify the output on disk.

## Reference Files

- `references/site-patterns.md` — Per-site HTML extraction patterns and selectors
- `references/kyujin-legitimacy.md` — 求人の真正性 (ghost-job) assessment: signals, 3 tiers, JP edge cases
- `../../_shared/frameworks.md` — Shared frameworks (SPI3, Well-being Index) — same file used by job-seeker-agent and company-battlecard
