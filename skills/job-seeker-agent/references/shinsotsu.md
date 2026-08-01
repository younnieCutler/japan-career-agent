# Shinsotsu Workflow (新卒 track guide)

New-graduate (新卒) hiring uses completely different evaluation criteria from mid-career. Candidates are
evaluated on **potential and student-era activities (学チカ)**, not job experience.

### 新卒 STEP 1: Collect 学チカ (Gakuchika)

Collect "the activity you worked hardest on as a student."

Collection points (2–3 questions at a time, then STOP and wait for the answer):
- What activity was it? (club, part-time job, volunteering, academic research, etc.)
- What was your role in it?
- What difficulty arose, and how did you solve it?
- What was the result, or what did you learn?
- Scale: number of people involved, duration, scope of impact

If there are several activities, focus on the 2 most impactful.

### 新卒 STEP 2: SPI3 Quick Assessment

(Same as mid-career) — use the 12 SPI3 statements in `../../../_shared/frameworks.md`.

### 新卒 STEP 3: 学チカ evaluation + potential-based Portable Skills

**学チカ evaluation (see frameworks.md Section 5):**

Refer to the "Gakuchika Evaluation Framework" section in `../../../_shared/frameworks.md`.
Score 4 dimensions (Impact, Goal Achievement, Leadership, Challenger Spirit), each 1–5.

```
📚 学チカ Evaluation
━━━━━━━━━━━━━━━━━━━━━━━━━━
Impact:            ████░ 4/5 — [evidence]
Goal Achievement:  ███░░ 3/5 — [evidence]
Leadership:        ████░ 4/5 — [evidence]
Challenger Spirit: ██░░░ 2/5 — [evidence]
```

**Potential-based Portable Skills:**
Since there is no work experience, score based on the potential shown in 学チカ, part-time work, and academics.
Cap scores in the 1–3 range and state that this is a "student-experience-based evaluation."

After scoring, ask the user:
"Does this evaluation feel accurate? Tell me if there's anything you'd like to adjust."

### 新卒 STEP 4: Comprehensive Report (新卒)

#### 4-1. 自己PR writing

Draft the 自己PR based on the 学チカ + Portable Skills results.

Structure: [one-sentence strength] + [STAR summary of the 学チカ episode] + [link to post-join contribution]

```
Example:
Strength: I'm good at leading a team to results in a changing environment.
Episode: As the club president, I identified a member-attrition problem and reformed how the club was run,
         raising participation by 40% in 6 months.
Link: After joining, I want to take on consulting work, solving client challenges together with a team.
```

**Absolute rule:** Do not write an episode without real experience.
Number estimates are allowed within a reasonable range (scale, frequency, etc.).

#### 4-2. ES (Entry Sheet) optimization

Structure the 学チカ to fit the target company's ES question types:
- 志望動機 (motivation): connect the company's mission/business to your own interests
- 自己PR: use the 4-1 content above
- 学チカ deep-dive questions: prepare answers for "なぜそれをやったのか", "何が一番苦労したか"

#### 4-3. Interview prep

High-probability questions + answer strategy based on SPI3 results and the 学チカ evaluation:
- Strength-appeal question + recommended STAR answer structure
- "Your weakness?" → growth-mindset-based answer strategy
- "Your 5-year career vision" → connect company type based on SPI3 traits

#### 4-4. Target company-type recommendation

Recommend a fit company type based on SPI3 × 学チカ results:
- Platforms to use: OfferBox (scout type), マイナビ・リクナビ (large 新卒 platforms), Wantedly (startups)
- Company size & culture matching

#### 4-5. CANDIDATE_PROFILE output

At the end of STEP 4, output the same YAML block (same format as mid-career, with `track: "shinsotsu"` added):

```yaml
# === CANDIDATE_PROFILE (machine-readable, do not edit) ===
candidate_name: "名前"
track: "shinsotsu"
spi3:
  creation: X
  result: X
  harmony: X
  order: X
  primary_trait: "Creation"
gakuchika:
  impact: X           # 1~5
  goal_achievement: X
  leadership: X
  challenger_spirit: X
portable_skills:  # 9 elements, MHLW official (_shared/frameworks.md §2)
  現状の把握: X  # 1~3 (student experience)
  課題の設定: X
  計画の立案: X
  課題の遂行: X
  状況への対応: X
  社内対応: X
  社外対応: X
  上司対応: X
  部下マネジメント: X
target_role: "営業 / エンジニア / マーケター"
target_company_type: "large enterprise / startup / consulting"
jlpt_level: "N1"
graduation_year: "2026"
# === END CANDIDATE_PROFILE ===
```

#### 4-6. Document save (required)

After the report is complete, always save:

```
Save path: career-docs/profile-[name]-[YYYYMMDD].md
Contents: 学チカ evaluation, SPI3 results, 自己PR draft, interview-prep notes, CANDIDATE_PROFILE YAML
```
