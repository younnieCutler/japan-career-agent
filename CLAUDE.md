# Japan Recruit AI Agent — session entry

Read [`AGENTS.md`](./AGENTS.md) as the contract. At session start load
[`_shared/agent_context/onboarding.md`](./_shared/agent_context/onboarding.md); load routing,
development, persistence, market-flow, or skill references only when the task needs them.

Do not maintain a second routing or decision table here. Keep `Unknown`, approval gates, execution
blockers, trust boundaries, independent matching axes, and legacy read-only compatibility intact.
