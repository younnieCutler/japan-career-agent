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
that a workflow was chosen and not that anything was verified. An existing Vault that already has a
`stage` keeps its workflow and is never re-onboarded, even if `career_status` is set back to
`onboarding` by hand.

An empty ledger is a fact worth stating: `readiness` reports `bootstrap_suggested` when there is
nothing to quote, independently of `job_search`, and the honest response is to offer
`career-tanaoroshi` rather than to analyse from nothing. Offer it; never start it unasked.

A career-tanaoroshi or career-maintenance request skips the track question entirely: an employed user who is not looking
belongs to no hiring market, so `track` stays `null` and the work event is captured without one.
The question returns the moment a request actually needs a track. An opportunity-review message
counts as a stated intent for the third gate — it names a task as clearly as 面接 does, it just is
not a stage.

`employment_status` and `job_search` are the user's own declaration, default `unknown` and `off`,
and are written only by `set-employment-status` and `set-job-search`. A message such as "재직 중"
or "이직 생각 없어요" is read back as the command that would record it, exactly as a stated
graduation year is. Nothing infers `employed` from "not looking", and no JD review, recruiter
message, approved event, or match run may turn job search on.

The active-pipeline priority above is a separate layer: it is decided by the CWD probe before
`CAREER_VAULT` chat is ever invoked, not by the Vault runtime. `career_agent.py run --mode chat`
takes no `--workspace` and never reads `data/pipeline.yml`, so a pipeline sitting on disk has no
effect on what a chat turn does by itself.
