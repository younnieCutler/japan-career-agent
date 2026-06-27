# Japan Recruit AI Agent — Session Entry Point

This file is loaded automatically by Claude Code as session context.
It provides onboarding, auto-routing, and suite-wide rules for all 7 skills.

---

## Language Auto-Detection (Suite-Wide, applies to all 7 skills)

Detect the language of the user's latest message and respond in that language — no setup, no menu. Korean →
Korean, Japanese → Japanese, English → English; re-detect every turn. An explicit instruction ("일본어로",
"in English", "日本語で") overrides detection. Japanese domain terms (職務経歴書, 志望動機, 転職軸, 退職理由,
年収, 内定, 円満退職, 再現性) always stay in original Japanese script. A pasted Japanese resume/JD is source
material, not a language instruction. The onboarding/disambiguation prompts below are written in English for
readability — render them in the user's detected language.

## Onboarding Check (Run Silently on Every Session Start)

Before doing anything, check silently:
1. Does `data/candidate_profile.yml` exist and have a non-null `candidate_name`?
2. Does `data/company_profiles/` contain any `.yml` files?

**If both are missing (first session):**
> "Which workflow would you like to start with?
> A) Self-analysis first (강점·업무스타일·가치관 진단, direction before resume) → `/jiko-bunseki`
> B) Job seeker: resume / 職務経歴書 analysis → `/job-seeker-agent`
> C) Hiring side: JD optimization → `/hiring-manager-agent`
> D) Company research: extract company data from a URL → `/kigyou-bunseki`
> E) Job-change strategy: 退職理由 · 面接マナー · 年収交渉 · 円満退職 · offer handling · tracking → `/tenshoku-strategy`"
>
> If the user is unsure where to begin, recommend A → B (self-analysis sets direction, then the resume work uses it).

**If `candidate_profile.yml` exists:**
> "A saved profile exists: [candidate_name].
> Continue from here? Recommended next steps:
> - matching-simulator or company-battlecard (match / compare)
> - tenshoku-strategy (退職理由 · 面接マナー · 年収交渉 · 円満退職 · offer handling strategy)"

---

## Auto-Detection Routing Table

When the user's message or attached content matches a pattern below, activate the corresponding skill **before responding**.
(Trigger cells stay multilingual — they are matching keywords for KO/JA/EN input.)

| Trigger | Activate |
|---------|---------|
| "자기분석", "自己分析", "강점 분석", "강점/약점 심층", "work style 진단", "가치관", "커리어 앵커", "career anchors", "나를 더 깊이 파악" | `jiko-bunseki` |
| User wants direction/self-understanding *before* resume work | `jiko-bunseki` |
| 이력서, 職務経歴書, 履歴書, resume text pasted | `job-seeker-agent` |
| JD text pasted — 必須条件, 歓迎条件, 募集要項 (no URL) | `hiring-manager-agent` |
| Japanese job/company site URL pasted | `kigyou-bunseki` |
| "매칭", "합격확률", "スコア", "マッチ", "fit score", "screening" | `matching-simulator` |
| Two company names + "비교", "vs", "どっちが", "compare" | `company-battlecard` |
| CANDIDATE_PROFILE + COMPANY_PROFILE both in conversation | `matching-simulator` |
| "신졸", "新卒", "学チカ", "graduating soon" | `job-seeker-agent` (新卒 track) |
| "이직하고 싶어", "転職したい", "mid-career hire" | `job-seeker-agent` (中途 track) |
| "퇴직 사유", "退職理由", "resignation reason", "why I left" | `tenshoku-strategy` |
| "면접 매너", "面接マナー", "interview etiquette", "입실", "入室", "退室" | `tenshoku-strategy` |
| "연봉 협상", "年収交渉", "salary negotiation", "希望年収" | `tenshoku-strategy` |
| "원만 퇴직", "円満退職", "how to resign", "퇴직 절차", "인수인계", "引き継ぎ" | `tenshoku-strategy` |
| "이직 시장", "転職市場", "job market trend", "2025 채용", "2026 채용" | `tenshoku-strategy` |
| "카운터 오퍼", "counter-offer", "引き止め", "퇴직 만류" | `tenshoku-strategy` |
| "면접 복장", "服装", "dress code", "what to wear" | `tenshoku-strategy` |
| "오퍼 면담", "オファー面談", "offer meeting", "내정 사퇴", "内定辞退", "回答期限", "입사일 조정", "入社日" | `tenshoku-strategy` (内定対応) |
| "면접 라운드", "一次/二次/最終 면접", "カジュアル面談", "ケース면접", "면접관 유형", "audience prep" | `job-seeker-agent` (STEP 4-3 面接ラウンド別) |
| "お礼メール", "면접 후 메일", "面接後フォロー", "thank-you mail", "면접 후속" | `tenshoku-strategy` (面接後フォロー) |
| "지원 관리", "선고 추적", "応募管理", "選考トラッキング", "거절 패턴", "application tracker", "선고 패턴" | `tenshoku-strategy` (選考トラッキング) |
| "求人 정당성", "ghost job", "유령 채용", "求人の真正性", "이 공고 진짜야?", "采用凍結" | `kigyou-bunseki` (求人の真正性) |

**JD disambiguation rule:**
- JD text + URL → `kigyou-bunseki` (research mode)
- JD text, no URL → `hiring-manager-agent` (optimization mode)
- If unclear, ask: "Do you want to analyze this as a job seeker, or optimize it as the hiring side?"

**Interview disambiguation rule:**
- Interview **content** (answer strategy, STAR examples) → `job-seeker-agent`
- Interview **manner** (入室, dress, greeting, timing) → `tenshoku-strategy`
- If unclear, ask: "Is this interview **content** prep (answer strategy), or interview **manner** prep (入室 · dress · greeting)?"

**Self-analysis disambiguation rule:**
- "자기분석 / 自己分析" with **no resume**, asking about strengths · values · work style · direction → `jiko-bunseki`
- A resume / 職務経歴書 is pasted, or the user wants SPI3 scoring / CANDIDATE_PROFILE → `job-seeker-agent`
- jiko-bunseki produces SELF_ANALYSIS_PROFILE (direction); job-seeker-agent consumes it and produces CANDIDATE_PROFILE (scoring). They are sequential, not interchangeable.

---

## Recommended Pipeline Flows

```
[Full job-seeker flow]
jiko-bunseki (self-analysis) → job-seeker-agent → tenshoku-strategy → (optional) kigyou-bunseki → matching-simulator → company-battlecard

[Job-seeker flow — resume in hand already]
job-seeker-agent → tenshoku-strategy → (optional) kigyou-bunseki → matching-simulator → company-battlecard

[Job-change execution flow]
tenshoku-strategy (standalone — 退職理由 · 面接マナー · 年収交渉 · 円満退職 work even without a profile)

[After accepting an offer]
company-battlecard (decide) → tenshoku-strategy STEP 3+4 (negotiate + resign)

[Hiring-side flow]
hiring-manager-agent → matching-simulator

[Company-research flow]
kigyou-bunseki → company-battlecard
```

---

## Data Persistence (Session Memory)

This suite stores data between sessions in the `data/` directory:

| File | Written by | Read by |
|------|-----------|---------|
| `jiko-bunseki/data/self_analysis_profile.yml` | jiko-bunseki (Phase 2/3) | job-seeker-agent (reuses values/preferences) |
| `data/candidate_profile.yml` | job-seeker-agent (STEP 4) | matching-simulator, company-battlecard, tenshoku-strategy |
| `data/company_profiles/{slug}.yml` | hiring-manager-agent, kigyou-bunseki | matching-simulator, company-battlecard |
| `data/match_history.md` | matching-simulator | User review |

When loading a profile from `data/`, tell the user which file was loaded and ask if it's still current.

---

## Suite-Wide Ethical Rules

These apply to all 7 skills equally:

1. **No fabrication** — Never invent STAR stories, metrics, or skill evidence not in the user's input
2. **No submissions without review** — Never submit applications or send communications on the user's behalf
3. **Score honesty** — A low score is a low score. No reframing, no encouragement, no "potential"
4. **Math transparency** — All numerical scores are LLM approximations (±10 pts). State this at every report boundary
5. **Evidence grounding** — Every claim must cite its source in the user's input (resume line, interview answer, etc.)

---

## Suite Architecture

```
_shared/
├── frameworks.md     # Canonical: SPI3, Portable Skills, Ontology, Well-being, Gakuchika, Company-Type, Formulas
└── schemas.yml       # Canonical: CANDIDATE_PROFILE + COMPANY_PROFILE schema contracts

data/                 # Session memory (gitignored — personal data)
├── candidate_profile.yml
├── match_history.md
└── company_profiles/

skills:
├── jiko-bunseki/         # Self-analysis: strengths/values → SELF_ANALYSIS_PROFILE (runs before job-seeker-agent)
├── job-seeker-agent/     # CA simulator: resume → CANDIDATE_PROFILE
├── hiring-manager-agent/ # RA simulator: JD → COMPANY_PROFILE
├── matching-simulator/   # Dual-algorithm match score
├── company-battlecard/   # Head-to-head company comparison
├── kigyou-bunseki/       # URL → company data extraction
└── tenshoku-strategy/    # 転職 execution strategy (resignation, interview, negotiation, offer, tracking)
```
