# Target-specific application document routing

Use this reference when the user has a specific company/JD and asks to create or regenerate a 職務経歴書 or resume for that target.

The full workflow remains in `../SKILL.md`:

1. normalize the supplied target posting;
2. map each requirement to confirmed evidence;
3. let the user review the selected primary/supporting evidence;
4. generate the document model and evidence-bounded wording;
5. run the fidelity checks and rendering path.

This route is different from base-document preparation. `job-seeker-agent` may prepare reusable candidate evidence and a base document before any target exists; `career-document` owns the target-specific projection after a concrete posting exists.

The JD changes emphasis, never career facts. Nothing here submits the application.