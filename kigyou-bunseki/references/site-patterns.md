# Site-Specific Extraction Patterns

Per-site reference for extracting structured data from Japanese recruitment and review sites.
Each section documents: what data is available, where it lives in the HTML, and known access restrictions.

---

## 1. OpenWork (openwork.jp / vorkers.com)

**Data richness: ★★★★★** — Richest source for company culture and employee sentiment data.

### Available Data
- 総合評価 (overall score, X.X / 5.0)
- 8つの評価項目 (8 category scores)
- 平均年収 (average salary)
- 平均残業時間 (average overtime hours/month)
- 有給消化率 (paid leave usage rate)
- 社員クチコミ (employee reviews — text)
- 企業概要 (company overview)

### URL Patterns
- Company page: `openwork.jp/a09XXXXXXXXXX`
- Job posting: `openwork.jp/a09XXXXXXXXXX/recruit_agent?j=XXXX`
- Reviews: `openwork.jp/a09XXXXXXXXXX/answer`

### Access Restrictions
- **403 on headless browsers** — OpenWork has aggressive bot detection.
- **Login required** for full review text.
- **Title tag accessible via curl** — contains company name + job title.
- The `<title>` tag format:
  `[CompanyName]／[JobTitle]（[JobID]） [teaser text] 求人情報と社員クチコミ OpenWork [jobHash]`

### Extraction Strategy
1. `curl` with User-Agent → extract `<title>` for company name and job title
2. `search_web "OpenWork [company name] 総合評価 年収 残業"` → get scores and salary data
3. If user has gstack + cookies: `$B cookie-import-browser chrome --domain .openwork.jp` → full access

### 8 Category Score Names (for search queries)
1. 待遇面の満足度
2. 社員の士気
3. 風通しの良さ
4. 社員の相互尊重
5. 20代成長環境
6. 人材の長期育成
7. 法令順守意識
8. 人事評価の適正感

---

## 2. doda (doda.jp)

**Data richness: ★★★★☆** — Strong for job requirements and salary data.

### Available Data
- 求人タイトル (job title)
- 年収範囲 (salary range, often specific)
- 仕事内容 (job description)
- 必須条件 / 歓迎条件 (required / preferred qualifications)
- 勤務地 (location)
- 勤務形態 (work style: remote/hybrid/office)
- 企業規模 (company size)
- 業界 (industry)

### URL Patterns
- Job posting: `doda.jp/DodaFront/View/JobSearchDetail/j_jid__XXXXXXXX/`
- Company page: `doda.jp/DodaFront/View/CompanyInfo/j_id__XXXXXXXX/`

### Access Restrictions
- **Mostly accessible via curl** — doda renders server-side.
- Some job listings require login for full details.
- Meta tags (`og:title`, `og:description`) contain job summary.

### Extraction Strategy
1. `curl` → extract title, meta description, and visible salary/requirements
2. `read_url_content` → converts HTML to markdown with good structure
3. `search_web "doda [company name] [job title] 年収"` as fallback

---

## 3. Wantedly (wantedly.com)

**Data richness: ★★★☆☆** — Best for culture/mission data, weak on salary.

### Available Data
- 企業ミッション (company mission)
- カルチャー (culture description)
- メンバー紹介 (team member profiles)
- 求人タイトル (job title)
- 仕事内容 (job description)
- **No salary data** — Wantedly intentionally hides salary information.

### URL Patterns
- Company page: `wantedly.com/companies/[company-slug]`
- Job posting: `wantedly.com/projects/[project-id]`
- Stories: `wantedly.com/companies/[slug]/post_articles/[id]`

### Access Restrictions
- **Accessible via curl and read_url_content** — relatively open.
- Full job descriptions may require login.
- Rich `og:` meta tags with good summaries.

### Extraction Strategy
1. `curl` or `read_url_content` → extract mission, culture, job description
2. `search_web "Wantedly [company name] カルチャー ミッション"` as fallback
3. Note in output: "⚠️ Wantedlyは年収データを公開していません"

---

## 4. LinkedIn (linkedin.com)

**Data richness: ★★★☆☆** — Good for company size, employee count, international presence.

### Available Data
- Company overview
- Employee count
- Industry
- Headquarters location
- Recent posts/updates
- Job postings (title, location, requirements)

### URL Patterns
- Company page: `linkedin.com/company/[company-slug]/`
- Job posting: `linkedin.com/jobs/view/[job-id]/`

### Access Restrictions
- **Heavy login wall** — most content requires authentication.
- `curl` gets minimal data (basic company name from title).
- `search_web` is the most reliable approach.

### Extraction Strategy
1. `curl` → extract `<title>` for company name
2. `search_web "LinkedIn [company name] Japan employees company size"` → company data
3. If gstack available: `$B cookie-import-browser chrome --domain .linkedin.com`

---

## 5. Indeed Japan (jp.indeed.com)

**Data richness: ★★★★☆** — Good for salary and job requirements.
**⚠️ Bot blocking: SEVERE** — curl and read_url_content both fail. Skip direct fetch entirely.

### URL Patterns
- Standard job posting: `jp.indeed.com/viewjob?jk=XXXXXXXXXXXX`
- Sponsored/featured listing: `jp.indeed.com/?vjk=XXXXXXXXXXXX&advn=XXXXXXXXXXXXX`
  → `vjk` (view job key) is the job ID in sponsored listings — extract for search queries.
- Company reviews: `jp.indeed.com/cmp/[company-name]/reviews`

### Access Restrictions
- **ALL direct fetch methods fail**: curl returns bot-detection page, read_url_content gets blocked.
- This applies to both `?jk=` and `?vjk=` URL formats.
- Do NOT attempt curl or read_url_content for jp.indeed.com URLs.

### Extraction Strategy (Indeed-specific)
1. Extract job ID from URL: `jk=XXXX` or `vjk=XXXX`
2. Extract any readable slug/company hint from the URL path or `advn=` parameter
3. `search_web "Indeed Japan [job ID] [any company hint from URL]"` → may surface cached job title
4. If company name not found: `search_web` using the job ID as the query string
5. Once company name is known → proceed to Phase 2 (official homepage) immediately

### Available Data (via search only)
- 求人タイトル (job title) — from search result snippets
- 年収/給与 (salary) — sometimes in search snippet
- 企業名 (company name) — from search result title

---

## 6. en転職 (employment.en-japan.com)

**Data richness: ★★★★☆** — Strong salary data and detailed job descriptions.

### Available Data
- Detailed job description
- 年収 (salary — often specific ranges)
- 勤務地・勤務時間 (location, hours)
- 必要な経験・スキル (required experience)
- 社員クチコミ (via en Lighthouse integration)

### URL Patterns
- Job posting: `employment.en-japan.com/desc_XXXXXXXX/`

### Access Restrictions
- **Accessible via curl** — server-side rendered.
- Good meta tag data.

### Extraction Strategy
1. `curl` or `read_url_content` → full job details
2. `search_web "en転職 [company name] 年収 口コミ"` as fallback

---

## 7. Green (green-japan.com)

**Data richness: ★★★☆☆** — IT/Web engineer focused, good tech stack data.

### Available Data
- Job title and description
- Required tech stack (often detailed)
- Salary range
- Company info (size, industry, funding)

### URL Patterns
- Job posting: `green-japan.com/job/[job-id]`
- Company: `green-japan.com/company/[company-id]`

### Access Restrictions
- **Accessible via read_url_content** — relatively open.

### Extraction Strategy
1. `read_url_content` → tech stack and requirements
2. `search_web "Green [company name] エンジニア 求人"` as fallback

---

## 8. マイナビ転職 (tenshoku.mynavi.jp)

**Data richness: ★★★★☆** — Comprehensive job postings with detailed requirements.

### Available Data
- Detailed job description
- Salary range
- Benefits
- Work style
- Required qualifications

### URL Patterns
- Job posting: `tenshoku.mynavi.jp/jobinfo-XXXX/`

### Access Restrictions
- **Accessible via curl/read_url_content**.

### Extraction Strategy
1. `curl` or `read_url_content` → full job details
2. `search_web` as fallback

---

## 9. Glassdoor Japan (glassdoor.com)

**Data richness: ★★★★☆** — Strong for salary data and employee ratings (international companies).

### Available Data
- Overall rating (X.X / 5.0)
- Salary data (detailed by role)
- Interview experience
- Pros/Cons reviews
- CEO approval rating

### URL Patterns
- Company: `glassdoor.com/Reviews/[company]-Reviews-EXXXXXXX.htm`
- Salaries: `glassdoor.com/Salary/[company]-Salaries-EXXXXXXX.htm`

### Access Restrictions
- **Login wall after a few page views**.
- `search_web` is the most reliable approach.

### Extraction Strategy
1. `search_web "Glassdoor [company name] Japan rating salary reviews"` → aggregated data
2. `read_url_content` may work for initial page load

---

## Universal Fallback Pattern

For any URL not matching the above patterns:

1. Extract domain name from URL
2. `curl` with browser UA → parse `<title>` and `<meta>` tags
3. `read_url_content` → attempt full page parse
4. `search_web "[company name from title] 評判 年収 口コミ"` → universal search
5. If company name can't be determined from any tier → ask the user
