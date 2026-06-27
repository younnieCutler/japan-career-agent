---
name: jiko-bunseki
description: >
  Conduct Japan job-hunting self-analysis for both shinsotsu and chuto candidates. Identify
  work strengths, work style, wellbeing priorities, preferred company environment, and self-PR
  seeds, then save a SELF_ANALYSIS_PROFILE YAML for downstream use by job-seeker-agent. Includes an
  optional Phase 3 depth layer adding career anchors (Schein), derailers, energy map, and career
  theme for a far deeper individual portrait. Use when the user asks for 자기분석, 自己分析, strengths
  analysis, work style diagnosis, values clarification, company-type fit, career anchors, 강점/약점
  심층 분석, "나를 더 깊이 파악", or wants to start the Japan job-search workflow before resume
  analysis.
---

# Jiko Bunseki

## Overview

Run this skill before `job-seeker-agent` when the user needs direction before resume analysis.

This skill is for:

- clarifying work strengths in a job-hunting context
- understanding preferred company environment and manager style
- generating self-PR seeds for later resume / interview work
- creating a reusable profile that reduces repeated questioning downstream

This skill is not:

- an official Gallup assessment
- an official SPI3 assessment
- a psychometrically validated replacement for either

## Depth model

This skill has two depths. **Phase 1–2** is a quantitative snapshot (forced-choice strengths + Likert style/wellbeing → scored profile). **Phase 3** is an optional conversational deep-dive that turns the snapshot into a self-portrait.

The quantitative instrument measures what a person *can* do. It cannot reach four things that decide a real career fit, which Phase 3 adds:

- **Career anchors** (Schein) — the one need they refuse to give up
- **Derailers** (Hogan/Gallup shadow side) — where each top strength turns dangerous when overused
- **Energy map** — "good at" vs "wants to do"; a strength they hate using is a trap
- **Career theme** (Savickas) — the narrative that connects past to future

For excavating a single motive that stays contradictory even after Phase 3, hand off to `naked-me`, which runs a stricter one-question-at-a-time interrogation.

## Language Rule

Write this skill in English internally, but run the user session in the user's selected language.

## Files To Load

- Phase 2: `references/questions.md` — pair-to-strength mapping and interpretation rules
- Phase 2: `../../_shared/frameworks.md` — wellbeing axis names and wording consistency
- Phase 3: `references/depth-layer.md` — career anchors, derailers, energy map, career theme protocol

---

## Workflow

This skill runs in **two required phases plus an optional third**. Phase 1 hands off the checklist; Phase 2 scores it and produces the profile; Phase 3 is an optional conversational deep-dive offered after Phase 2. Do not proceed past Phase 1 until the user submits the checklist JSON.

---

### PHASE 1 — Checklist Handoff

**Trigger:** The skill is invoked and the conversation contains no `jiko_bunseki_submission` JSON.

Run these steps in order, then stop and wait for the user.

#### Step 1 — Existing Profile Check

Silently check `data/self_analysis_profile.yml`.

- If a saved profile exists, tell the user what was found and ask whether to **reuse**, **update**, or **replace** it.
  - Reuse → summarize the existing result and skip to Downstream Handoff.
  - Update → proceed to Phase 1 Step 2; explain that answers will overwrite the saved file.
  - Replace → proceed to Phase 1 Step 2.
- If no profile exists, proceed to Step 2 silently.

#### Step 2 — Language Confirmation

Ask the user which language to use for this session:

```
A. 한국어
B. 日本語
```

Store the answer as `language_preference`. Use that language for all remaining output.

#### Step 3 — Checklist Handoff

Tell the user to open the pre-built HTML checklist. Resolve `{SKILL_DIR}` to the absolute path of
the folder this `SKILL.md` loaded from (e.g. `~/.claude/skills/jiko-bunseki`), then substitute it into
the `open` command below. Never hardcode another user's path.

**Korean session:**
```
자기분석 체크시트를 준비했습니다.

아래 파일을 브라우저에서 열어주세요:

  open {SKILL_DIR}/checklist.html

모든 항목(강점 24쌍 + 업무스타일 6개 + 웰빙 4개)을 입력한 뒤
[제출 및 JSON 복사] 버튼을 클릭하세요.
표시된 JSON 텍스트를 이 대화창에 붙여넣으면 분석을 시작합니다.
```

**Japanese session:**
```
自己分析チェックシートを用意しました。

以下のファイルをブラウザで開いてください：

  open {SKILL_DIR}/checklist.html

全項目（強み24ペア＋仕事スタイル6項目＋ウェルビーイング4項目）を入力後、
[提出してJSONをコピー] ボタンをクリックしてください。
表示されたJSONテキストをこの会話に貼り付けると分析を開始します。
```

**Stop here.** Do not ask further questions. Do not begin analysis. Wait for the user's next message.

---

### PHASE 2 — Analysis

**Trigger:** The user's message contains a JSON block with `"jiko_bunseki_submission": true`,
or contains a `"strength_pairs"` array with 24 items.

Read `references/questions.md` now. It contains the pair-to-strength mapping needed for scoring.

#### Step 1 — Parse Submission

Extract from the JSON:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Candidate name |
| `language` | `"ko"` \| `"ja"` | Session language |
| `track` | `"shinsotsu"` \| `"chuto"` | Track |
| `strength_pairs` | array[24] | Values: `SL` `L` `N` `R` `SR` |
| `work_style` | array[6] | 1–5 scale; order: autonomy → structure_preference → speed_preference → change_tolerance → collaboration_preference → feedback_frequency |
| `wellbeing` | array[4] | 1–5 scale; order: autonomy → social_contribution → management_quality → mutual_respect |

If any required field is missing or malformed, ask the user to re-paste the JSON from the checklist.

#### Step 2 — Strength Scoring

Apply the 5-point forced-choice scoring rule per pair:

| Answer | Left strength | Right strength |
|--------|--------------|----------------|
| SL     | +4           | +0             |
| L      | +3           | +1             |
| N      | +2           | +2             |
| R      | +1           | +3             |
| SR     | +0           | +4             |

Use the pair-to-strength mapping from `references/questions.md` Section 1.

After scoring all 24 pairs:

- Calculate raw scores for all 12 strengths (max 16 each)
- Rank to find top 5 strengths
- Calculate 4 cluster raw scores (3 strengths × max 16 = 48 per cluster)
- Normalize: `round(raw_cluster_score / 48 * 100)`

Tie-breaking: if two strengths share the same raw score, the one with more SL/SR extreme answers ranks higher.

#### Step 3 — Work Style and Wellbeing

Map `work_style` array positions to field names:

```
[0] autonomy
[1] structure_preference
[2] speed_preference
[3] change_tolerance
[4] collaboration_preference
[5] feedback_frequency
```

Map `wellbeing` array positions to field names:

```
[0] autonomy
[1] social_contribution
[2] management_quality
[3] mutual_respect
```

Store raw 1–5 values directly. Do not reinterpret into SPI3.

#### Step 4 — Interpretation

Use the derivation rules in `references/questions.md` Section 3 to generate:

1. **Top 5 strengths** with scores
2. **Cluster distribution** (normalized scores)
3. **Work style summary** in plain language
4. **Preferred company type** using these defaults:
   - high `structure_preference` (≥4) AND low `change_tolerance` (≤3) → `SIer`
   - high `autonomy` (≥4) AND high `change_tolerance` (≥4) → `self-developed startup`
   - balanced → `large enterprise`
5. **Recommended role clusters** (2–4)
6. **Self-PR seeds** (2–4 short phrases reusable in self-introduction, self-PR, and interviews)
7. **Risk flags** (evidence-based only; omit if none apply)

For shinsotsu track: express role directions in broad terms; do not assume prior industry experience.

#### Step 5 — Output and Persistence

Present the full self-analysis report in the user's language.

Append the machine-readable YAML block at the end:

```yaml
# === SELF_ANALYSIS_PROFILE (machine-readable, do not edit) ===
candidate_name: "Name"
language_preference: "ko"
track: "chuto"
top_strengths:
  - name: "analysis"
    score: 14
    cluster: "strategic_thinking"
strength_clusters:
  executing: 58
  strategic_thinking: 79
  relationship_building: 50
  influencing: 46
work_style:
  autonomy: 4
  structure_preference: 2
  speed_preference: 4
  change_tolerance: 5
  collaboration_preference: 3
  feedback_frequency: 4
wellbeing_priorities:
  autonomy: 5
  social_contribution: 4
  management_quality: 4
  mutual_respect: 5
preferred_company_type: "self-developed startup"
preferred_role_environment:
  - "high-autonomy"
  - "fast-feedback"
recommended_role_clusters:
  - "product / service planning"
  - "growth / digital marketing"
risk_flags:
  - "may dislike rigid approval chains"
self_pr_seeds:
  - "turns ambiguity into a practical next step"
  - "prefers ownership with clear outcome responsibility"
# --- Phase 3 depth layer (null until Phase 3 is run) ---
career_anchors:
  primary: "autonomy"
  secondary: ["pure_challenge"]
  will_not_give_up: "내 방식·속도를 통제당하면 떠난다"
derailers:
  - strength: "ownership"
    overuse_risk: "위임 불가 → 과부하/번아웃"
    watch_signal: "혼자 다 짊어지고 있다고 느낄 때"
energy_map:
  energizes: ["새 문제를 처음부터 설계할 때"]
  drains: ["하루 종일 조율·승인 대기"]
  misfit_flag: null
career_theme: "통제받던 환경에서 출발해, 자율적으로 만들어내는 사람이 되려 한다"
notes:
  - "Custom self-analysis only; not an official aptitude test"
# === END SELF_ANALYSIS_PROFILE ===
```

If a field was not assessed, set it to `null`. The Phase 3 block stays `null` until the depth-dive is run.

Then:

- Save the YAML to `data/self_analysis_profile.yml`. If the file already exists, ask before overwriting.
- Save the human-readable summary:
  - CWD가 /Documents/Jeongyun 이면: `{CWD}/04-areas/Career/Matching/self-analysis-[name]-[YYYYMMDD].md`
  - 그 외: `{CWD}/Matching/self-analysis-[name]-[YYYYMMDD].md`

After saving, offer Phase 3:

> 정량 분석은 끝났습니다. 더 깊이 들어가면 정량 점수가 못 잡는 4가지 — 절대 포기 못하는 조건(커리어 앵커), 강점이 독이 되는 지점(디레일러), 살리는 일 vs 빠는 일(에너지 맵), 과거-미래를 잇는 테마 — 를 파악할 수 있습니다. 진행할까요?

If the user declines, go to Downstream Handoff. If yes, run Phase 3.

---

### PHASE 3 — Depth Layer (optional)

**Trigger:** Phase 2 is complete and the user opts in.

Read `references/depth-layer.md` now. It contains the full protocol for four blocks:

- **Block A — Career Anchors** (Schein): the 1-2 needs they refuse to give up
- **Block B — Derailers**: where each Phase 2 top strength turns dangerous when overused
- **Block C — Energy Map**: "good at" vs "wants to do"; flag strengths that drain
- **Block D — Career Theme** (Savickas): one line connecting past to future

Run conversationally, one block at a time, in the user's language. This is not a checklist — it reuses the Phase 2 `top_strengths` as input and probes with concrete episodes. Let the user skip any block.

After the opted-in blocks finish:

1. Write a 3-5 sentence **Deep Career Portrait** (Korean) integrating quant + anchor + derailer + energy + theme.
2. Update the YAML `career_anchors`, `derailers`, `energy_map`, `career_theme` fields. Set skipped blocks to `null`.
3. Re-save both the YAML and the human-readable summary, appending a `## Phase 3 — 심층 분석` section.

**Cross-check obligation:** if Phase 3 surfaces a conflict with Phase 2 (e.g., anchor=자율 vs preferred_company_type=SIer, or a top strength sitting in the DRAINS column), state it plainly. These contradictions are the most valuable output — they explain why a "high-fit" job on paper still feels wrong.

---

## Downstream Handoff

After Phase 2 (or Phase 3) completes, recommend `job-seeker-agent` as the default next step.

Explain the handoff clearly:

- `jiko-bunseki` = self-understanding and direction setting (Phase 3 adds anchors, derailers, theme)
- `job-seeker-agent` = resume, self-PR, SPI3, portable skills, and candidate profile generation
- `matching-simulator` = job-specific fit scoring after the candidate profile exists
- `naked-me` = stricter single-motive excavation when a Phase 3 contradiction stays unresolved

Phase 3 outputs feed directly downstream: derailers become evidence-based 약점 answers, the career theme becomes the spine of 自己PR and 志望動機, and anchors give `tenshoku-strategy` an honest 転職理由.

Do not claim that `job-seeker-agent` can skip SPI3 because of this profile.
It may reuse values and preferences, but it still owns candidate scoring.
