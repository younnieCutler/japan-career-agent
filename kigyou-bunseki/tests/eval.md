# Kigyou Bunseki (Company Analysis) Test Cases

To ensure the extraction pipeline and analysis formatting are working correctly, run these tests when iterating on the `kigyou-bunseki` skill.

## Test Case 1: Single Company (OpenWork)
**Objective**: Verify 3-tier fallback. OpenWork blocks most automated tools, but `extract_url.sh` should grab the title, allowing the agent to use `search_web` to retrieve the hidden evaluations.
- **Input**: `https://www.openwork.jp/a0910000000FrMN/recruit_agent?j=85493d55614c66209a`
- **Criteria**:
  - Script output returns `ブラザー工業` and `データエンジニア`.
  - Final card correctly searches Web to list 総合評価, 平均年収, etc.
  - "未取得項目" lists any data missing gracefully instead of guessing.

## Test Case 2: Multi-Company Battlecard (doda vs Wantedly)
**Objective**: Test comparing two differently structured sites (JD driven vs Culture driven).
- **Inputs**:
  - doda URL: `https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__3010508608/` (example, use any active doda URL)
  - Wantedly URL: `https://www.wantedly.com/projects/1234567` (example, use any active wantedly job URL)
- **Criteria**:
  - Agent creates a side-by-side ⚔️ 企業バトルカード.
  - Salary row for Wantedly is marked as 比較不可 (incomparable) since Wantedly masks pay rates.
  - Winner column correctly highlights the company with superior metrics whenever a row can be compared.

## Test Case 3: Personalized Context (With CANDIDATE_PROFILE)
**Objective**: Test integration with `job-seeker-agent` YAML state block.
- **Input Text**:
```
Please compare these links:
1. https://www.openwork.jp/a0910000000FqjR/recruit_agent?j=effc6cd3ccdc259490
2. https://www.openwork.jp/a0910000000FrMN/recruit_agent?j=85493d55614c66209a

# === CANDIDATE_PROFILE (machine-readable, do not edit) ===
candidate_name: "Test User"
spi3:
  primary_trait: "Creation"
skill_stack:
  - name: "Python"
    level: "advanced"
    capability: "automation scripting"
target_role: "Data Engineer"
target_company_type: "self-developed startup"
jlpt_level: "N3"
# === END CANDIDATE_PROFILE ===
```
- **Criteria**:
  - The Battlecard extracts job demands for BOTH companies.
  - A "Skill Stack Match" row compares Python proficiency with job descriptions.
  - "SPI3 Culture Fit" recommends one of them based on the `target_company_type` alignment.

## Test Case 4: International Sites (LinkedIn / Glassdoor)
**Objective**: Ensure the universal fallback (`search_web` based on `<title>`) triggers when `read_url_content` encounters a heavy login wall.
- **Input**: Any active Glassdoor Japan URL or LinkedIn Job URL.
- **Criteria**:
  - `tier=curl` returns the company name from the Title tag.
  - Instead of failing, the agent automatically executes a query like `search_web "Glassdoor [Company] Japan rating salary reviews"`.
