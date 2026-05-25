# Agent Task Board

## Status Rules

Allowed statuses:

- Not Started
- Assigned to Codex
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
| Watch `v0.5.3` release workflow to completion | Codex | Assigned to Codex | Codex is actively watching; docker-build is green, lint/build-exe still running at last check. |
| Adopt mandatory coordination protocol | Claude | Assigned to Claude | Claude must acknowledge the protocol in `AGENT_MESSAGES.md` before implementation work. |
| Review/own local triage behavior test file if applicable | Claude | Assigned to Claude | If `tests/test_email_triage_behavior.py` is Claude's work, Claude must leave a Review Request in `AGENT_MESSAGES.md` before Codex reviews or commits it. |

## Backlog

| Task | Owner | Status | Next Required Action |
|---|---|---|---|
| Review remaining unreviewed training examples before another retrain | Claude/Codex | Not Started | Use aggregate/sanitized review only; do not bulk-approve without controlled review. |
| Watch follow-up main CI for coordination commit | Codex | Not Started | Confirm the coordination contract test passes in GitHub Actions. |
