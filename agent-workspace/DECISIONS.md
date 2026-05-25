# Agent Coordination Decisions

## 2026-05-25 - Repo-Native Coordination

Decision:

- Use `agent-workspace/` markdown files as the mandatory Claude/Codex coordination layer.
- Use `agent-workspace/AGENT_MESSAGES.md` as the direct agent-to-agent message channel.
- Keep the protocol file-based and reviewable in git. Do not build a server, database, chat app, or real-time system.

Rationale:

- File-based coordination is easy to inspect, diff, review, and resume from another machine.
- The project already uses docs and handoff logs successfully.
- The user explicitly requested repo-native coordination, clear gates, and no large coordination app.

Consequences:

- Every agent session must read the coordination files before work.
- Every agent session must write a direct message before ending.
- A session without an `AGENT_MESSAGES.md` entry is incomplete.

