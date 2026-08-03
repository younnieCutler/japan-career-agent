# Jiko Bunseki — optional depth conversation

The depth conversation turns raw reflection into user-reviewed hypotheses. It does not validate a
personality model or determine company suitability.

## Block A — career anchors

Ask which needs the user will not trade away: expertise, management, autonomy, stability, creation,
service, challenge, or lifestyle. Ask for a concrete episode. Keep the anchor as a hypothesis until
the user confirms it. If two anchors conflict, state the trade-off and ask which condition matters
in which situation.

## Block B — overuse risks

For each selected behavior tendency, phrase an overuse risk as a hypothesis and ask for a recent
episode that confirms or rejects it. A hypothesis without an episode remains Unknown and must not
become a risk fact.

## Block C — energy map

Use the energizing and draining episodes from the v2 checklist as starting material. Ask for two
concrete examples when the pattern is unclear. Keep “good at” separate from “wants to do”. If the
same tendency appears in both episodes, record the tension rather than deciding that the user is
unsuitable for a role.

## Block D — career theme

Ask about a proud decision, a recurring problem the user wants to solve, or a future contribution.
Draft one sentence, show it to the user, and retain it only after correction or confirmation.

## Integration

Extract `career_values.must_have` and `career_values.avoid` only from explicit user statements.
Show the exact proposed values, anchors, energy map, and theme before saving. With a Vault, use
`career-agent propose-context` and `career-agent approve`; without one, save the user-confirmed
profile under the invocation CWD. Unconfirmed hypotheses remain visible as drafts, never as
canonical motivation.
