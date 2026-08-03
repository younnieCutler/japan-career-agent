# Japan Recruit AI Agent — Session Entry Point

For full system architecture, fast code maps, token-saving navigation guides, and agent execution guidelines, please refer to:
👉 **[AGENTS.md](./AGENTS.md)**

---

## Onboarding Check (Run Silently on Every Session Start)

Before doing anything, load the full checklist and greeting/menu procedure from
[`_shared/agent_context/onboarding.md`](./_shared/agent_context/onboarding.md). It is authoritative;
do not keep a shorter duplicate in this entry point.

---

## Auto-Detection Routing Table

When the user's message matches a pattern below, load the authoritative multilingual routing and
disambiguation table from [`_shared/agent_context/routing.md`](./_shared/agent_context/routing.md)
before responding. Do not keep a second routing table here.
