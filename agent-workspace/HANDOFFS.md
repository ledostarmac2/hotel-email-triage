# Agent Handoffs

## 2026-05-25 - Codex - Coordination Protocol Bootstrap

Summary:

- Created the `agent-workspace/` coordination layer requested by Brian.
- Made `AGENT_MESSAGES.md` the mandatory direct communication channel between Claude and Codex.
- Added task status gates requiring Claude handoff/review request and Codex `Approved` or `Needs Changes` before work can be marked `Done`.
- Added a lightweight contract test so CI catches missing coordination files or missing mandatory language.

Files changed:

- `agent-workspace/PROJECT_STATE.md`
- `agent-workspace/TASK_BOARD.md`
- `agent-workspace/HANDOFFS.md`
- `agent-workspace/DECISIONS.md`
- `agent-workspace/AGENT_RULES.md`
- `agent-workspace/AGENT_MESSAGES.md`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `tests/test_agent_coordination_contract.py`

Verification:

- `python -m pytest tests/test_agent_coordination_contract.py -q --timeout=60` - 4 passed.
- Codex self-review found the protocol intentionally limited to markdown files plus one pytest contract check; no server, database, dependency, real-time chat, or unrelated app-code edits were added.

Remaining work:

- Claude must adopt the new start/finish protocol and leave future review requests in `agent-workspace/AGENT_MESSAGES.md`.
