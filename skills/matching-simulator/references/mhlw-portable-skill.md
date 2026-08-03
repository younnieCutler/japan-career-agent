# MHLW Portable Skill — 29-point allocation & composition distance

Implements 厚生労働省「ポータブルスキル見える化ツール」as published, and nothing beyond it.
Engine: `../../_shared/matching_v3.py`. Reference-data interface: `../../_shared/mhlw_reference.py`.

Source: https://www.mhlw.go.jp/content/11800000/000935264.pdf

## 1. What the official tool does

The candidate distributes **29 points across 9 elements** (持ち味). Both the candidate's
allocation and each standard role profile are normalised to **composition ratios summing
to 1**, and the tool ranks the 114 standard 職務・職位 profiles by **Euclidean distance
between those compositions**.

```
p_i = a_i / Σa        q_i = r_i / Σr        d(p,q) = √( Σ (p_i − q_i)² )
```

That is the whole published method. There is no official conversion of `d` to a 0–100 score,
so this repo does not invent one.

## 2. The 9 elements

| key | 日本語 |
|---|---|
| `current_state_assessment` | 現状の把握 |
| `task_setting` | 課題の設定 |
| `planning` | 計画の立案 |
| `task_execution` | 課題の遂行 |
| `situational_response` | 状況への対応 |
| `internal_coordination` | 社内対応 |
| `external_coordination` | 社外対応 |
| `manager_response` | 上司対応 |
| `subordinate_management` | 部下マネジメント |

## 3. Validation rules (enforced, not advisory)

- every element is an **integer ≥ 1**
- the 9 elements sum to **exactly 29**
- `level: 1–5` is **position-level information**, stored separately and **never** part of the
  distance vector. Changing `level` cannot change any distance — there is a regression test
  for exactly this (`test_level_is_excluded_from_the_distance_vector`).

Anything else raises a validation error. A near-miss allocation is a data-entry problem to
send back to the user, not something to normalise away.

## 4. Collecting the allocation from the user

Ask directly. Do not derive it:

> 9つの持ち味に、合計29点を配分してください。各項目は1点以上、合計はちょうど29点です。
> 現状の把握 / 課題の設定 / 計画の立案 / 課題の遂行 / 状況への対応 /
> 社内対応 / 社外対応 / 上司対応 / 部下マネジメント

**A legacy 1–5 portable-skill rating is not convertible into this allocation.** The old
ratings answer "how strong is this?"; the allocation answers "where does this person's weight
sit?". There is no defensible mapping between them, so the profile keeps both and the user is
asked to allocate 29 points once. Never auto-convert, and never fill the remainder yourself.

## 5. Comparison targets and mapping provenance

The default comparison set is MHLW's 114 standard 職務・職位 profiles.

To compare against a specific posting, `mhlw_mapping` must record **all** of:

```yaml
mhlw_mapping:
  mapped_role_profile_id: "…"       # an id in the reference dataset
  method: manual | rule_based | heuristic_mapping
  confidence: high | medium | low | unknown
  evidence: "why this posting maps to that profile"
```

Without `method` **and** `evidence` the engine returns `status: unmapped` and produces no
distance. A JD ratio that an LLM read off the posting is `heuristic_mapping`; its output is
labelled `official_values: false` and carries a warning. It is never presented as an MHLW value.

## 6. Reference dataset status — **unavailable in this installation**

The 114-profile dataset is **not bundled**. Its redistributable form and licence terms were not
established, and generating the profiles with a language model would fabricate the very
reference the diagnosis is measured against. So:

| capability | status |
|---|---|
| 29-point allocation validation | ✅ implemented |
| composition normalisation + Euclidean distance | ✅ implemented |
| ranking / top-5 / `rank N of M` | ✅ implemented, **runs only when a dataset is installed** |
| reference-data interface, versioning, licence fields | ✅ implemented |
| fixtures and regression tests | ✅ implemented (synthetic fixture, labelled as such) |
| the actual MHLW 114 profiles | ❌ **unavailable** |

With no dataset present, a mapped posting returns `status: unavailable` with the reason, and
the report says so. It does not fall back to a partial ranking or an estimated distance.

**To install a dataset**, write `_shared/mhlw_role_profiles.yml` (or point `$MHLW_ROLE_PROFILES`
at a file) in the format documented at the top of `../../_shared/mhlw_reference.py`. Every profile
allocation is validated by the same 29-point rules. `dataset_version`, `source` and `licence`
are required — an unversioned reference cannot back a reproducible result.

## 7. Prohibited

- computing distance from 1–5 `level` values
- `100 × (1 − distance / max_distance)` or any other 0–100 conversion
- presenting an MHLW distance as company fit, culture fit, or pass probability
- generating the 114 profiles, or a subset, from a language model
