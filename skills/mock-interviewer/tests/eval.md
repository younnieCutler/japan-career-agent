# Mock Interviewer Test Cases

## Test Case 1: Career value contradiction
**Objective**: Interview practice surfaces contradictions instead of silently rewriting the candidate.
- **Input**: Confirmed `career_context` says autonomy is essential; the candidate answers that they prefer
  strict instructions and no independent decisions.
- **Criteria**:
  - The report quotes both statements and labels `Career Value Contradiction`.
  - The interviewer asks which statement is current.
  - Neither the answer nor the saved context is changed automatically.

## Test Case 2: Missing context stays missing
**Objective**: Mock interview does not invent a value profile.
- **Input**: No `SELF_ANALYSIS_PROFILE`, or `career_context_confirmed: false`.
- **Criteria**:
  - Interview practice continues using only the user's current answers.
  - Career Value Consistency is reported as unavailable; no generic philosophy is added.

## Test Case 3: Adaptive probe selection preserves breadth
**Objective**: A grounded axis is not repeatedly questioned while an unresolved axis remains.
- **Input**: The candidate clearly explains ownership but gives an uncertain metric and no learning point.
- **Criteria**:
  - The next question targets evidence or learning instead of mechanically repeating ownership.
  - The session-local coverage ledger keeps the unresolved axes visible.
  - The interviewer may skip a probe family that is already grounded.

## Test Case 4: Document claims are not auto-confirmed
**Objective**: Resume wording remains a claim to verify, not an established fact.
- **Input**: The resume says the candidate "led" a migration and improved speed "by about 30%".
- **Criteria**:
  - The interviewer distinguishes `document-stated` from `from-user` or `confirmed-context`.
  - Approximation and missing measurement are preserved in the next probe.
  - The answer is not silently rewritten into a stronger interview sentence.

## Test Case 5: Readiness gates assessment, not user exit
**Objective**: Unresolved gaps affect readiness without preventing the user from stopping.
- **Input**: Ownership is clear, but the metric source and trade-off remain unresolved after the question budget.
- **Criteria**:
  - Readiness is reported as `Needs targeted follow-up` or `Not assessable`, not `Ready`.
  - The user can end the session and still receive the assessment.
  - The report names the highest-impact follow-up rather than generating unlimited questions.

## Test Case 6: Defensible Core requires confirmation
**Objective**: The final concise summary is feedback, not an automatic canonical correction.
- **Input**: The interviewer summarizes a narrower ownership claim than the resume wording.
- **Criteria**:
  - The summary preserves the narrower claim and its uncertainty.
  - The user is asked to confirm or correct it.
  - No resume, Vault, or pipeline value is changed automatically.

## Test Case 7: Ambiguous claims get operational and counterexample probes
**Objective**: High-impact wording is clarified and challenged without being declared false.
- **Input**: The candidate says, "I led the migration and improved performance by 30%."
- **Criteria**:
  - The interviewer asks what "led" and "improved" mean in that incident.
  - A high-value probe checks role boundary, baseline, comparison, or an alternative cause.
  - The interviewer treats the probe as a verification question, not as proof that the claim is false.
