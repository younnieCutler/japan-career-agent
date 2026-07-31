# Shared Career Vault Context Contract

All candidate-side skills use the same Career Vault when `CAREER_VAULT` is set.

1. Ask the Career Agent for metadata-only context before analysis:

   ```bash
   python3 "$CAREER_AGENT_RUNTIME" context --vault "$CAREER_VAULT"
   ```

2. Use only the returned profile, current state, and selected note metadata. Do not scan the Vault,
   load archives, or infer facts from old local `data/` files.
3. Treat `00-control/career-profile.toml` and `02-state/career-state.toml` as the shared current state.
   Confirmed facts remain in `02-state/events.jsonl`.
4. Keep skill-specific output as a draft until the user approves evidence through `career-agent approve`.
5. If `CAREER_VAULT` or `CAREER_AGENT_RUNTIME` is missing, ask for the Vault path rather than creating a
   separate career state in the current directory.

`CAREER_AGENT_RUNTIME` should point to the canonical `skills/career-agent/career_agent.py`. On this
machine, Claude Code and Codex install that directory as a symlink to the repository source, so both
frontends call the same runtime.
