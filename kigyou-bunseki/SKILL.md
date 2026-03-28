---
name: kigyou-bunseki
description: >
  日本の求人・企業URLから企業情報を高速で抽出・分析するスキル。
  処理速度を最優先し、まずは対象URLから企業名・職種名を特定後、企業の公式ホームページを直接探索します。
  公式ホームページから「企業理念（Mission/Vision）」と「採用関連情報」を抽出できれば即座に分析を完了します。
  公式情報が不足する場合のみ、他の外部プラットフォームを調査対象とする軽量・高速なワークフローです。

  Use this skill when:
  - User pastes any Japanese job site URL (openwork.jp, doda.jp, wantedly.com, etc.)
  - User says "이 회사 어때?", "この会社どう?", "analyze this company"
  - User pastes 2+ URLs and says "비교해줘", "比較して", "compare these"
  - Keywords: "기업분석", "企業分析", "company analysis", "회사 비교", "company comparison"
  - Keywords: "크롤링", "crawl", "scrape", "이 링크 분석해줘"
  - User sends a URL from any recruitment/review site and expects structured data
  Use this skill proactively whenever a user sends a URL from a known job/review site,
  even without explicitly asking for analysis. If a URL looks like a job posting or
  company review page, activate this skill immediately.
---

# Kigyou Bunseki — Japan Company Analysis & Comparison Agent

## Overview

This skill extracts structured company data from Japanese recruitment and review site URLs,
then produces an objective "企業カルテ" (Company Card) for single-company analysis or
a head-to-head "⚔️ Battlecard" for multi-company comparison.

The output is numbers and facts. There is no "both are great companies."

## How Data Extraction Works (3-Phase Hard Gate)

**RULE: Each phase must fully complete AND fail before the next phase begins. If a phase succeeds, output immediately — do NOT proceed to the next phase.**

---

### PHASE 1 — Input URL Only (MAX 1 fetch)

Fetch the provided URL ONCE to extract **Company Name** and **Job Title**.

```bash
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" "[URL]" | grep -iE "<title>|<meta name=\"description\""
```

**Known blocked sites — skip curl, go straight to search:**
- `jp.indeed.com` — blocks all bots (both `?jk=` and `?vjk=` URL formats). Use `search_web "[URL domain] [job ID from URL]"` to find a cached version or the company name.
- `openwork.jp` — returns 403 for most pages.
- `linkedin.com` — login wall.

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
| Salary range | 年収範囲 | Medium | Official / doda, Indeed |
| Work style | 勤務形態 | Medium | Official / JD |
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
  職種名:     [job title]
  必須スキル: [list]
  歓迎スキル: [list]
  勤務形態:   [remote/hybrid/office]
  年収範囲:   [salary range]
  福利厚生:   [key benefits]

📊 外部評価・口コミ (※公式データで不足した場合のみ取得)
  総合評価:   [X.X / 5.0]
  平均残業:   [hours/month]
  離職率:     [%]
  社風ワード: [extracted culture indicators]

⚠️ データソース: [which sites provided which data - e.g. "公式ホームページ", "Indeed"]
⚠️ 未取得項目:  [dimensions where data was unavailable]
```

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
  (see `references/frameworks.md` for the SPI3 × Company Type table)
- **Well-being Alignment**: match candidate's priorities against company culture signals

When CANDIDATE_PROFILE is available, add these personalized rows to the Battlecard table.
When unavailable, produce the objective comparison only (salary, overtime, scores, etc.).

### Feeding company-battlecard

The output of this skill can feed directly into `company-battlecard` for deeper
SPI3/Well-being analysis. Mention this at the end of the output:
"詳細な文化適合性分析が必要な場合は company-battlecard をご利用ください。"

## Tone & Style

Same anti-sentiment rules as the rest of the skill suite:

- Do not say "どちらも良い会社です" — the data determines the winner.
- If both companies score poorly (e.g., high overtime + low review scores), say so:
  "両社とも総合評価3.0以下、平均残業30h超。他の選択肢の検討を推奨。"
- If data is insufficient to make a judgment, state exactly what's missing
  rather than filling gaps with optimism.
- Numbers first, interpretation second. Every claim must cite its data source.

**Language:**
- Output in Japanese by default.
- If the user writes in Korean, output in Korean.
- If the user writes in English, output in English.
- Technical terms use original script (e.g., 年収, 離職率, リモート).

## Error Handling

| Scenario | Action |
|----------|--------|
| URL returns 403/blocked | Fall through to next tier. If all tiers fail, extract company name from URL and use search_web. |
| URL is behind login wall | Suggest `cookie-import-browser` if gstack available. Otherwise, use search_web. |
| URL is not a recognized site | Try curl → read_url_content → search_web anyway. The pipeline is site-agnostic. |
| Company name can't be determined | Ask the user: "企業名を教えてください" |
| Data is too old | Note the data freshness in the output: "⚠️ データ取得日: [date]" |

## ⚠️ Unsupported Platforms (Crawling Impossible)

The following platforms **cannot be analyzed** by this skill. When a user pastes a URL from these sites, **immediately ask for the company name and job title** — do not attempt any fetch or search.

| Platform | Why Unsupported |
|----------|----------------|
| **jp.indeed.com** | Blocks all bots. `vjk=` and `jk=` URL formats both inaccessible. Sponsored listing URLs (`?vjk=`) are not indexed by search engines. |
| **linkedin.com/jobs/collections/recommended/** | Personalized page requiring login. `currentJobId=` parameter content is invisible without authentication. |
| **linkedin.com** (general) | Full login wall. No meaningful data accessible without session cookies. |

**Action when these URLs are provided:**
```
「このURLはログインが必要なため分析できません。
会社名と職種名を教えていただければ、すぐに分析します。」
```

## Reference Files

- `references/site-patterns.md` — Per-site HTML extraction patterns and selectors
- `references/frameworks.md` — Shared frameworks (SPI3, Well-being Index) — same file used by job-seeker-agent and company-battlecard
