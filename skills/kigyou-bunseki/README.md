# Kigyou Bunseki (Company Analysis)

A specialized agent skill for the Japan IT/Marketing sector that analyzes and compares companies based on objective data from Japanese recruitment and review sites (OpenWork, doda, Wantedly, LinkedIn, Indeed, etc.).

## Features
- **URL-driven extraction:** Just paste a URL from any major Japanese job site to get started. No manual data entry required.
- **3-Tier Data Pipeline:** Uses an intelligent fallback mechanism (`curl` → `read_url_content` → `search_web`) to bypass bot protections (like those on OpenWork) and extract the raw facts.
- **Evidence formatting:** Reports salary, overtime, turnover, and third-party review observations only
  when a current source supports each field; it does not turn them into a company total.
- **Single Company Cards (企業カルテ):** Generates a structured breakdown of a single company's metrics.
- **Multi-Company Battlecards (企業バトルカード):** Compares 2+ companies by independent evidence axes and explains trade-offs without a total winner.
- **Personalized Context:** Integrates `CANDIDATE_PROFILE` to compare confirmed skills, values, conditions, constraints, interest, and unknowns. A work-style reflection creates verification questions, not culture fit.

## Usage
Simply send a message with one or more URLs:
> "이 채용공고 어때? https://doda.jp/..."
> "Compare these two companies: [URL1] and [URL2]"
> "오픈워크 링크 3개 줄테니까 연봉이랑 잔업시간 위주로 1등 뽑아줘."

## Architecture
- `SKILL.md`: Core system prompt and output definitions.
- `scripts/extract_url.sh`: Lightweight Bash script for Tier 1 extraction (title, meta, open graph info, raw salary text). Let the agent handle Tier 2/3 fallbacks.
- `references/site-patterns.md`: Knowledge base of Japanese job site DOM structures and query strings for fallbacks.
- `references/frameworks.md`: Source and evidence guidance shared with the other skills.
