# Agent Task Board

## Status Rules

Allowed statuses:

- Not Started
- Assigned to Claude
- Waiting for Codex Review
- Needs Claude Changes
- Approved by Codex
- Done
- Blocked

## Done Gate

A task can only move to `Done` when all of these are true:

- Claude has implemented or updated the work.
- Claude has left a handoff or review request for Codex in `agent-workspace/AGENT_MESSAGES.md`.
- Codex has reviewed the work.
- Codex has left `Approved` or `Needs Changes` in `agent-workspace/AGENT_MESSAGES.md`.
- If `Needs Changes`, Claude has addressed the issue or documented why not.

If the user explicitly bypasses Codex review, document that bypass in `agent-workspace/AGENT_MESSAGES.md` and `agent-workspace/HANDOFFS.md`.

## Active Task

| Task | Owner | Status | Next Required Action |
|---|---|---|---|
| Mandatory Claude/Codex coordination protocol | Codex | Approved by Codex | Claude must read the new protocol files and use `AGENT_MESSAGES.md` before implementation work. |

## Backlog

| Task | Owner | Status | Next Required Action |
|---|---|---|---|
| Review remaining unreviewed training examples before another retrain | Claude/Codex | Not Started | Use aggregate/sanitized review only; do not bulk-approve without controlled review. |
| Watch `v0.5.3` release workflow to completion | Codex | Not Started | Confirm lint, build-exe, docker-build, release, and installer asset. |

