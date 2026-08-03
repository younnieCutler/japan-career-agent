# Session-start onboarding

Run this check silently using paths relative to the invocation directory (CWD):

1. Does `data/candidate_profile.yml` exist with a non-null `candidate_name`?
2. Does `data/company_profiles/` contain a YAML profile?
3. Does `data/pipeline.yml` contain an active (`closed: false`) company?

If active pipeline entries exist, they take priority. Greet with one line per active company:
name, stage number and label, status, and deadline. Put deadlines within three days first with a
warning marker. Then ask which company to continue with or whether to add a company.

If both candidate profile and company profiles are missing, ask where the user is in the real flow:

- direction/self-analysis → `/jiko-bunseki`
- resume or 職務経歴書 preparation → `/job-seeker-agent`
- company research → `/kigyou-bunseki` and evidence diagnosis
- application/interview execution → `/tenshoku-strategy`
- offer comparison → `/company-battlecard` and `/tenshoku-strategy`
- resignation/onboarding → `/tenshoku-strategy`
- hiring side → `/hiring-manager-agent`

When unsure, recommend direction first and documents second. If a candidate profile exists, tell
the user which file was loaded, ask whether it is current, and route from the user's stated stage.
