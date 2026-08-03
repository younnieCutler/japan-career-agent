# Jiko Bunseki — optional depth conversation

This conversation turns reflection responses into user-reviewed hypotheses. It does not validate a
personality model or determine company suitability.

## Block A — career anchors

Ask which needs the user will not trade away: expertise, management, autonomy, stability,
creation, service, challenge, or lifestyle. Ask for a concrete episode and present the anchor as
`user-confirmed` only after review. If it conflicts with another preference, state the trade-off and
ask which condition matters in which situation.

## Block B — overuse risks

For each selected tendency, phrase an overuse risk as a hypothesis. Ask for a recent episode that
confirms or rejects it. A hypothesis without an episode stays `Unknown` and must not become a risk
fact in a candidate profile.

## Block C — energy map

Ask for two concrete energizing and two draining episodes. Keep “good at” separate from “wants to
do”. If the same tendency appears in both, record the tension rather than deciding that the user
is misfit for a role.

## Block D — career theme

Ask about a proud decision, a recurring problem the user wants to solve, or a future contribution.
Draft one sentence, show it to the user, and retain it only after correction or confirmation.

## Integration

Extract `career_values.must_have` and `career_values.avoid` only from explicit user statements.
Show the exact proposed values, anchors, energy map, and theme before saving. With a Vault, use
`career-agent propose-context` and `career-agent approve`; without one, save the user-confirmed
profile. Unconfirmed hypotheses remain visible as drafts, never as canonical motivation.
