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
| Prepare `v0.5.13` release with concrete payload env-file gate only | Codex | Done | Release published with `ReplyRightSetup-v0.5.13.exe`; Brian should installer-test. |
| Fix native sidebar asset clipping and rebuild local EXE | Codex | Done | Sidebar nav now scrolls instead of squeezing logo/profile/footer assets; local EXE rebuilt and health-smoked. |
| Fix native PySide label background highlights and rebuild local EXE | Codex | Done | Default `QLabel` backgrounds are transparent, regression test passed, local `dist\ReplyRight\ReplyRight.exe` rebuilt and health-smoked. |
| Adopt mandatory coordination protocol | Claude | Approved by Codex | Protocol acknowledged in `AGENT_MESSAGES.md` at 2026-05-25T20:45:00-04:00. Done pending Codex confirmation. |
| Review/own local triage behavior test file if applicable | Claude | Approved by Codex | Codex reviewed, ran the tests, approved the test file, and took ownership of the CCA false-positive fix. |
| Codify outside-agent classifier training contract | Codex | Done | Docs, helper script, and contract tests updated so agent-assisted training requires sanitized agent labels, not heuristic-only pipeline output. |

## Backlog

| Task | Owner | Status | Next Required Action |
|---|---|---|---|
| Review remaining unreviewed training examples before another retrain | Claude/Codex | Not Started | Use aggregate/sanitized review only; do not bulk-approve without controlled review. |
| Resolve 500-entry `agent_pending` Completed Request batch | Codex | Assigned to Codex | Codex labeled/uploaded 86 rows (73 unique fingerprints) and retrained; continue with more sanitized agent-labeling before another import. |
| Continue controlled sanitized review of Completed Request training queue | Claude/Codex | Assigned to Claude | Review unreviewed examples in small batches only; leave a review request before any broad approval or retrain. |
| Installer/manual smoke test for `v0.5.13` | Brian/Codex | Not Started | Install `ReplyRightSetup-v0.5.13.exe`, sign in, refresh inbox, verify KYC popup, auto-refresh, queues, and AI suggestion gating. |
| Watch follow-up main CI for coordination commit | Codex | Not Started | Confirm the coordination contract test passes in GitHub Actions. |
| Add deterministic `recommended_action` field and operational queue filters | Claude/Codex | Approved by Codex | Codex reviewed, found and repaired stale action routing after classifier/AI/rule overrides, and approved with the Codex follow-up fix. |
