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
