# Agent Workspace Project State

Last updated: 2026-05-25

## Active Source Of Truth

- Product: ReplyRight hotel reservations email triage desktop app.
- Active app path: `outlook_dashboard/` plus `run_desktop.py`.
- Active desktop UI: PySide6 shell in `replyright_qt/`.
- Release artifact: installer-first `ReplyRightSetup-v{version}.exe`.
- Current coordination channel: `agent-workspace/AGENT_MESSAGES.md`.

## Current Active Task

Strengthen the repo-native Claude/Codex coordination protocol so both agents read shared state, respond to unresolved messages, update task state and handoffs, and leave a direct message before ending each session.

## Current Release Context

- `v0.5.3` was pushed to repair the `v0.5.2` lint failure and replace forced Node 24 behavior with Node 24-native first-party GitHub Actions.
- Docker CI was restored with a root `Dockerfile` and `docker-compose.yml`.
- Do not commit local runtime files, `.env`, databases, build outputs, or packaged binaries.

## Safety Boundary

- Preserve read-only Outlook behavior.
- Do not add send/archive/move/category/mark-read behavior without explicit user approval.
- Do not store raw email bodies, credentials, service-role keys, mailbox contents, or large memory dumps in coordination files.

