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

## Career Agent Vault side

When `CAREER_VAULT` is set, the Vault runs the same routing as a progressive sequence instead of a
questionnaire. A new Vault starts at `career_status = "onboarding"`, and `chat` confirms only:

1. track (`shinsotsu` or `chuto`) when the message does not state it,
2. `graduation_year` when the track is `shinsotsu`,
3. the task the user wants to start, when the message names none.

Each missing one is a question, never an inferred value. A stated `27卒` is read back for the user
to confirm with `setup --graduation-year 2027`; it is not written for them. `target_role` is not a
blocker and stays `Unknown`. Reaching a real stage moves `career_status` to `active`, which records
that a workflow was chosen and not that anything was verified. An existing Vault with a stage or an
active pipeline keeps its workflow and is never re-onboarded, matching the CWD priority rule above.
