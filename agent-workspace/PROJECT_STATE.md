# Agent Workspace Project State

Last updated: 2026-05-28

## Active Source Of Truth

- Product: ReplyRight hotel reservations email triage desktop app.
- Active app path: `outlook_dashboard/` plus `run_desktop.py`.
- Active desktop UI: PySide6 shell in `replyright_qt/`.
- Release artifact: installer-first `ReplyRightSetup-v{version}.exe`.
- Current coordination channel: `agent-workspace/AGENT_MESSAGES.md`.

## Current Active Task

Completed Request classifier training is the current active work. Brian clarified that outside-agent training requires Codex/Claude model-judgment labels on sanitized examples; heuristic-only `run_completed_pipeline()` output is staging data, not completed outside-agent training. Codex has started labeling the 500-row `agent_pending` batch with outside-agent judgment.

## Current Release Context

- 2026-05-28 native PySide6 UI polish pass completed: conversation list/detail labels, empty/loading/error states, and Summary/Action/Risk/Draft section styling were improved without Outlook mutation, sending, new features, or backend triage changes.
- `v0.5.3` repaired lint/build lanes but failed the release job at `Security Lint (Installer Extraction)`.
- `v0.5.4` (commit `62b0098`, tag pushed) fixed installer `.env` exclusion and the CCA false-positive, but still failed at `Security Lint (Installer Extraction)`.
- `v0.5.5` also failed at `Security Lint (Installer Extraction)`.
- `v0.5.6` also failed at `Security Lint (Installer Extraction)`, likely before/during the optional extraction tool path.
- `v0.5.7` also failed at `Security Lint (Installer Extraction)`.
- `v0.5.8` also failed at `Security Lint (Installer Extraction)`.
- `v0.5.9` also failed at `Security Lint (Installer Extraction)`.
- `v0.5.10` still failed at `Security Lint (Installer Extraction)` even after the pre-installer env purge step succeeded.
- `v0.5.11` main run passed, but the tag run wedged in the lint pytest step after build-exe passed; treat as a GitHub runner flake unless logs later prove otherwise.
- `v0.5.12` reached the release job but still failed at `Security Lint (Installer Extraction)` after source lint, EXE build, health smoke, env purge, and installer build passed.
- `v0.5.13` succeeded end-to-end on 2026-05-25/26: lint, docker-build, build-exe, release EXE build, health smoke, staged env purge, installer build, installer payload env-file audit, release smoke gate, and GitHub Release creation all passed.
- Published installer asset: `ReplyRightSetup-v0.5.13.exe`.
- Latest local classifier version after Codex outside-agent retrain: `20260528T141356Z`.
- Current training warning: owner and category CV are `insufficient_data` because the agent-labeled slices introduced rare classes with too few examples for cross-validation.
- Current local Completed Request ledger includes 500 `agent_pending` rows. Codex labeled/uploaded 86 rows from the pending batch, representing 73 unique fingerprints; continue labeling more of this batch before another Completed Request import.
- Training contract update: outside-agent training must include an actual sanitized agent-labeling step; app runtime and training endpoints remain zero-credit.
- `agent_comms/` retired as of 2026-05-25; `agent-workspace/AGENT_MESSAGES.md` is the active coordination channel.
- Docker CI restored with root `Dockerfile` and `docker-compose.yml`.
- Do not commit local runtime files, `.env`, databases, build outputs, or packaged binaries.

## Safety Boundary

- Preserve read-only Outlook behavior.
- Do not add send/archive/move/category/mark-read behavior without explicit user approval.
- Do not store raw email bodies, credentials, service-role keys, mailbox contents, or large memory dumps in coordination files.
