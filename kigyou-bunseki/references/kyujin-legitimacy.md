# 求人の真正性 (Posting Legitimacy / Ghost-Job Assessment)

> Judge, by signals, whether a 求人 is real, active, and backed by hiring intent, so the user can prioritize
> where to spend effort. **Present observations only — never accuse.** Every signal has legitimate explanations;
> the judgment is the user's.
>
> Adapted from career-ops (MIT, github/santifer/career-ops): `modes/oferta.md` Block G.
> Localized to the Japanese market (通年採用 · エージェント経由 · 中途採用比率, etc.).

This assessment is output as a supplementary section of the `kigyou-bunseki` 企業カルテ (`🔎 求人の真正性`).
It is a signal — separate from company-data extraction — about "is this 求人 worth your time?"

---

## Signals to analyze (in order)

### 1. 鮮度 (Freshness) — from the page/snapshot
- Date posted / "X日前" label, apply-button state (active / closed / missing / redirects to a generic careers page).
- Has the same 求人 been up for a long time (months)? — but see §edge cases (通年採用).

### 2. 記述の質 (Description Quality) — from the JD text
- Are specific technologies/tools/team size/org context written?
- Are the requirements realistic (years of experience vs the age of the technology, no contradiction)?
- Is the first 6–12 months' scope clear? Is salary mentioned?
- Ratio of role-specific vs boilerplate in the JD. Internal contradictions (junior title + staff requirements, etc.).

### 3. 採用シグナル (Hiring Signals) — 2–3 searches (combine with Block D research)
- `"{company}" リストラ {year}` / `"{company}" 採用凍結 {year}` — date, scale, department.
- If layoffs are found, are they in the same department as this 求人?
- **中途採用比率 (already extracted in the 企業カルテ):** if high (e.g., NEC majority · 日清 78% · NTT East 45%),
  it signals an environment where mid-career hires actually settle and thrive → **positive**.

### 4. 再掲載 detection
- Has the same company + similar role been reposted before under a different URL (frequency, period)?

### 5. 役割の市場文脈 (qualitative, no extra search)
- Is this a common role that typically fills in 4–6 weeks, vs one that inherently takes longer?
- Does this role make sense for this company's business?

---

## Output format (append to the 企業カルテ)

```
🔎 求人の真正性: [信頼度高 / 要注意 / 要確認]

| Signal | Observation | Assessment |
|--------|-------------|------------|
| 鮮度 | "3日前", apply button active | ✅ Positive |
| 記述の質 | tech/team size stated, salary range present | ✅ Positive |
| 採用シグナル | 中途比率 45%, no layoff news | ✅ Positive |
| 再掲載 | no repost in the past 6 months | ◽ Neutral |
| 市場文脈 | DE typically fills in 4–6 weeks | ◽ Neutral |

📝 Context: [legitimate explanations — 通年採用 / niche role / government, if applicable]
```

**Tier definitions:**
- **信頼度高** — multiple signals suggest a real, active opening
- **要注意** — mixed signals, proceed with note
- **要確認** — multiple ghost-job indicators, confirm before investing time

---

## Japan-specific edge cases (adjust thresholds)

| Case | Handling |
|------|----------|
| **通年採用 / ポテンシャル採用** | "随時募集" is not a ghost job = a pipeline role. Do not penalize long postings |
| **Via agent (non-public 求人)** | Freshness signals are unavailable. But **active agent contact is itself a positive signal** |
| **Government / academic** | Long selection (60–90 days) is standard. Relax thresholds |
| **Startup / pre-revenue** | The JD may be vague because the role is genuinely undefined. Weight vagueness less |
| **Large-firm always-open slots** | Mass hiring (e.g., SHIFT 2,500/yr) is normal. Do not misjudge repost frequency as ghost |
| **No date available** | If no other signal is concerning, default to **要注意** (never 要確認 without evidence) |

---

## Ethics & Anti-Fabrication Gate
- **No accusations.** Not "this company is faking the hiring," but "the following signals were observed; the call is yours."
- For layoffs / 採用凍結, cite the **search source and date**. Do not invent them from guesswork.
- If there is no data, write `データなし`. Do not drop to 要確認 when there is no concerning signal.
- Response language follows the SKILL.md Language Auto-Detection rule. Domain terms (求人/中途採用比率/通年採用)
  stay in original Japanese.
