---
name: kigyou-bunseki
description: >
  日本の求人サイト（OpenWork, LinkedIn, Indeed, doda, Wantedly, en転職, マイナビ転職,
  Green, キャリアトレック, Glassdoor Japan etc.）の求人URL・企業ページURLを受け取り、
  企業情報を抽出して構造化分析を行うスキル。1社の単独分析も、2社以上のURL比較も対応。
  OpenWorkの社員クチコミ・評点、dodaの求人要件、Wantedlyのカルチャー情報など、
  サイトごとに異なるデータを統合して「企業カルテ」として出力する。

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

## How Data Extraction Works

Every URL goes through a 3-tier extraction pipeline. Each tier is a fallback for the previous one.
Try them in order — move to the next tier only when the current one fails.

### Tier 1: curl (fastest, ~1 second)

Use curl with a browser User-Agent to fetch the raw HTML. This works for most sites
that render on the server (SSR). Extract data from `<title>`, `<meta>`, and visible text.

```bash
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" "[URL]"
```

**What to extract from raw HTML:**
- `<title>` tag → company name, job title, sometimes salary range
- `<meta name="description">` → job summary, key requirements
- `<meta property="og:title">` and `og:description` → structured preview data
- Visible text patterns → salary ranges (年収XXX万), work style (リモート, フレックス), requirements

If the response contains meaningful company/job data, parse it and proceed to the Scoring step.
If the response is empty, a login wall, or 403/captcha, move to Tier 2.

### Tier 2: read_url_content (medium speed, ~3 seconds)

Use the `read_url_content` tool to fetch and convert the page to markdown.
This handles JavaScript-rendered pages better than raw curl.

If this also fails (empty response, login required, blocked), move to Tier 3.

### Tier 3: search_web (always works)

Use `search_web` to find the company data indirectly. This is the universal fallback
that works regardless of any site's security measures.

**Search strategy by site:**

| Site | Search Query Template |
|------|----------------------|
| OpenWork | `"OpenWork [company name] 総合評価 年収 残業"` |
| doda | `"doda [company name] 求人 年収 仕事内容"` |
| Wantedly | `"Wantedly [company name] カルチャー ミッション"` |
| LinkedIn | `"LinkedIn [company name] Japan employees reviews"` |
| Indeed | `"Indeed Japan [company name] 年収 口コミ"` |
| en転職 | `"en転職 [company name] 年収 口コミ 評判"` |
| Green | `"Green [company name] 求人 エンジニア"` |
| Glassdoor | `"Glassdoor [company name] Japan rating salary"` |
| Generic | `"[company name] 評判 年収 残業 口コミ"` |

The company name is extracted from the URL using Tier 1 (`<title>` tag) before searching.
If the title tag itself is blocked, extract the company ID from the URL path and search for it.

### Tier 3.5: gstack browser (optional, when available)

If the `$B` (gstack browse) tool is available, it can be used as an additional option
between Tier 2 and Tier 3. It runs a real headless browser that can handle
JavaScript-rendered content.

```bash
$B goto "[URL]"
$B text
```

If blocked (403, captcha), use `cookie-import-browser` to import the user's real browser session:
```bash
$B cookie-import-browser chrome --domain .[site-domain]
```

Only suggest this if the user has gstack installed and explicitly wants deeper crawling.
Do not make gstack a hard dependency — the 3-tier pipeline above handles 95% of cases.

## Site-Specific Extraction Patterns

Read `references/site-patterns.md` for detailed extraction rules per site.
The key principle: each site exposes different data. Extract what's available and mark
missing dimensions as "データなし" rather than guessing.

### Data Points to Extract (when available)

| Data Point | Japanese | Priority | Common Sources |
|------------|----------|----------|----------------|
| Company name | 企業名 | Required | All sites |
| Job title | 職種名 | Required | Job posting URLs |
| Salary range | 年収範囲 | High | OpenWork, doda, Indeed, en転職 |
| Overall score | 総合評価 | High | OpenWork, Glassdoor |
| Avg overtime | 平均残業時間 | High | OpenWork |
| Turnover rate | 離職率 | High | OpenWork, job postings |
| Work style | 勤務形態 | Medium | All job postings |
| Required skills | 必須スキル | Medium | Job posting URLs |
| Company size | 企業規模 | Medium | Most sites |
| Industry | 業界 | Medium | Most sites |
| Culture keywords | 社風キーワード | Medium | OpenWork, Wantedly |
| Benefits | 福利厚生 | Low | Job postings, OpenWork |
| Founded year | 設立年 | Low | Company pages |

## Output Formats

### Single Company: 企業カルテ (Company Card)

When the user provides 1 URL:

```
📋 企業カルテ: [Company Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏢 基本情報
  企業名:     [name]
  業界:       [industry]
  企業規模:   [size / employee count]
  設立:       [year]
  上場:       [listed / unlisted]

💰 待遇・環境
  年収範囲:   [salary range]
  平均残業:   [hours/month]
  離職率:     [%]
  勤務形態:   [remote/hybrid/office]
  福利厚生:   [key benefits]

📊 評価 (OpenWork系データ)
  総合評価:   [X.X / 5.0]
  待遇満足度: [X.X]
  社員の士気: [X.X]
  風通し:     [X.X]
  20代成長:   [X.X]
  人材育成:   [X.X]
  法令順守:   [X.X]
  人事評価:   [X.X]

🎯 求人要件 (JDデータ)
  必須スキル: [list]
  歓迎スキル: [list]
  経験年数:   [required years]

🏷️ 社風キーワード: [extracted culture indicators]

⚠️ データソース: [which sites provided which data]
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

## Reference Files

- `references/site-patterns.md` — Per-site HTML extraction patterns and selectors
- `references/frameworks.md` — Shared frameworks (SPI3, Well-being Index) — same file used by job-seeker-agent and company-battlecard
