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
| Prepare `v0.5.5` release after installer extraction failures | Codex | Assigned to Codex | Purge runtime env files before installer build, keep CCA fix/tests, tag/push `v0.5.5`, and watch release. |
| Adopt mandatory coordination protocol | Claude | Approved by Codex | Protocol acknowledged in `AGENT_MESSAGES.md` at 2026-05-25T20:45:00-04:00. Done pending Codex confirmation. |
| Review/own local triage behavior test file if applicable | Claude | Approved by Codex | Codex reviewed, ran the tests, approved the test file, and took ownership of the CCA false-positive fix. |

## Backlog

| Task | Owner | Status | Next Required Action |
|---|---|---|---|
| Review remaining unreviewed training examples before another retrain | Claude/Codex | Not Started | Use aggregate/sanitized review only; do not bulk-approve without controlled review. |
| Watch follow-up main CI for coordination commit | Codex | Not Started | Confirm the coordination contract test passes in GitHub Actions. |
| Add deterministic `recommended_action` field and operational queue filters | Claude | Assigned to Claude | Follow the coordination protocol, then leave Codex a Review Request before marking complete. |
