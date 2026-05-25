# Agent Coordination Rules

These rules apply to Claude and Codex. They supplement `AGENTS.md` and `CLAUDE.md`.

## Mandatory Start Protocol

- Read coordination files.
- Identify the other agent's latest message.
- Respond to any unresolved message first.
- Confirm the Active Task.
- Work only on that task.

## Mandatory Finish Protocol

- Update `agent-workspace/HANDOFFS.md`.
- Update `agent-workspace/TASK_BOARD.md` if task status changed.
- Leave a direct message to the other agent in `agent-workspace/AGENT_MESSAGES.md`.
- Include tests/checks run.
- Include next required action.

If you complete a session without writing to AGENT_MESSAGES.md, the session is incomplete.

## Message Resolution

- Questions, blockers, handoffs, review requests, and requested changes remain unresolved until the addressed agent replies in `AGENT_MESSAGES.md`.
- Do not start unrelated implementation work while there is an unresolved message addressed to you unless the user explicitly redirects the task.
- Approval must be explicit: use `Status: Approved`.
- Required fixes must be explicit: use `Status: Needs Changes`.

## Privacy

- Do not include chain-of-thought, secrets, raw mailbox data, raw email bodies, full sender emails, full subjects, session cookies, service-role keys, or local database dumps in coordination files.

