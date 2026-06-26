# data/ — Session Memory

This directory stores data between sessions so you don't re-enter your profile every time.

> **Privacy:** This directory is gitignored. Files here are never committed.

---

## Files

| File | Written by | Purpose |
|------|-----------|---------|
| `candidate_profile.yml` | job-seeker-agent (STEP 4) | Your CANDIDATE_PROFILE — loaded automatically by matching-simulator and company-battlecard |
| `match_history.md` | matching-simulator (STEP 4) | Running log of all match simulations |
| `company_profiles/*.yml` | hiring-manager-agent, kigyou-bunseki | One file per company analyzed |

---

## How Skills Use This Directory

**job-seeker-agent:** After STEP 4, saves the full CANDIDATE_PROFILE YAML to `candidate_profile.yml`.
If the file already exists, ask the user: "Overwrite the existing profile, or continue from it?"

**hiring-manager-agent:** After analysis, saves the COMPANY_PROFILE YAML to
`company_profiles/{company-name-slug}.yml` (e.g., `company_profiles/bloom-tech.yml`).

**kigyou-bunseki:** After generating a 企業カルテ, saves the extracted structured data to
`company_profiles/{company-name-slug}.yml`. If a file already exists, merge new data.

**matching-simulator:** After STEP 4, appends a summary entry to `match_history.md`.
Also reads from `candidate_profile.yml` and `company_profiles/` to skip re-entry.

**company-battlecard:** Reads from `candidate_profile.yml` and target `company_profiles/*.yml` files.

---

## Loading Saved Data

When a skill starts, it checks `data/` silently. If relevant data exists:
- Tell the user: "Saved [profile/company data] exists: [name/date]. Use it?"
- If yes: load and skip re-entry steps
- If no: proceed with fresh input
