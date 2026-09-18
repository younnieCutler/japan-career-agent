# 適性検査 preparation

Use this reference only when the user has an aptitude-test invitation or explicitly asks to prepare for one. It stays inside `job-seeker-agent`; no new Skill is introduced.

## First identify the actual test

Do not treat every assessment as SPI3. Ask for or read the employer/recruiter invitation and preserve the stated test name, provider, deadline, delivery method, and allowed environment.

If the test is not identified, keep the provider/type `Unknown` and give only provider-neutral preparation advice. Do not infer SPI3 from a Japanese employer, job level, or URL shape.

## SPI3 boundary

For an explicitly identified SPI3 assessment, current official Recruit material distinguishes aptitude content such as basic-ability and personality assessment and supports multiple delivery methods, including test-center, in-house computer, web, and paper variants. Use the actual invitation for the candidate's required format and timing; do not generalize one format to all SPI3 uses.

Official source:
- https://www.spi.recruit.co.jp/
- https://www.spi.recruit.co.jp/t_99/

Do not reproduce leaked or proprietary test questions. Public example questions or user-owned practice material may be used only as practice material, never as a claim about the user's actual test form.

## Workflow

1. Record the assessment name/provider exactly as stated, or `Unknown`.
2. Record deadline, delivery method, required device/location, identity requirements, and any employer instructions from the invitation.
3. Separate preparation into:
   - logistics: deadline, environment, connection/device, test-center reservation when applicable;
   - ability practice: only for the identified test family and only from legitimate public/user-supplied material;
   - personality section: answer as the candidate, not as a fabricated 'ideal employee'. Do not coach deception or consistency gaming.
4. If the user shares practice results, treat them as practice observations only. Do not convert them into intelligence, personality, job-fit, or hiring-probability claims.
5. Before the real test, show remaining logistics and Unknowns. The user performs the assessment themselves.

## Handoff

Assessment completion is part of the active selection loop. Record the actual application stage/status through `tenshoku-strategy` tracking when the user asks to update it. A score or pass/fail reason not supplied by the employer remains `Unknown`.