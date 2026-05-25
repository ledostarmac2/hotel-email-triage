# Agent Workspace Project State

Last updated: 2026-05-25

## Active Source Of Truth

- Product: ReplyRight hotel reservations email triage desktop app.
- Active app path: `outlook_dashboard/` plus `run_desktop.py`.
- Active desktop UI: PySide6 shell in `replyright_qt/`.
- Release artifact: installer-first `ReplyRightSetup-v{version}.exe`.
- Current coordination channel: `agent-workspace/AGENT_MESSAGES.md`.

## Current Active Task

Prepare the `v0.5.6` release after repeated installer extraction audit failures, while preserving Claude's `recommended_action` work for Codex review.

## Current Release Context

- `v0.5.3` repaired lint/build lanes but failed the release job at `Security Lint (Installer Extraction)`.
- `v0.5.4` (commit `62b0098`, tag pushed) fixed installer `.env` exclusion and the CCA false-positive, but still failed at `Security Lint (Installer Extraction)`.
- `v0.5.5` also failed at `Security Lint (Installer Extraction)`.
- `v0.5.6` is the next release target: payload audit mode scans only the actual release payload locations (`dist\ReplyRight` and extracted `app`) after installer extraction, while source audit remains broad.
- `agent_comms/` retired as of 2026-05-25; `agent-workspace/AGENT_MESSAGES.md` is the active coordination channel.
- Docker CI restored with root `Dockerfile` and `docker-compose.yml`.
- Do not commit local runtime files, `.env`, databases, build outputs, or packaged binaries.

## Safety Boundary

- Preserve read-only Outlook behavior.
- Do not add send/archive/move/category/mark-read behavior without explicit user approval.
- Do not store raw email bodies, credentials, service-role keys, mailbox contents, or large memory dumps in coordination files.
