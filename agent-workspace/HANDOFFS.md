# Agent Handoffs

## 2026-05-25 - Codex - v0.5.5 Installer Env Payload Purge

Summary:

- Watched `v0.5.4`: lint, docker-build, build-exe, health smoke, and installer build passed; release still failed at `Security Lint (Installer Extraction)`.
- Added a pre-Inno purge in `installer/build_installer.ps1` to remove any `.env` or `*.env` files from `dist\ReplyRight` before compiling the installer, excluding only `sample.env`.
- Bumped release metadata to `0.5.5`.

Files changed:

- `installer/build_installer.ps1`
- `installer/replyright_setup.iss`
- `tests/test_installer_contract.py`
- `outlook_dashboard/__init__.py`
- `pyproject.toml`
- `agent-workspace/PROJECT_STATE.md`
- `agent-workspace/TASK_BOARD.md`
- `agent-workspace/HANDOFFS.md`
- `agent-workspace/AGENT_MESSAGES.md`
- `docs/CURRENT_STATE.md`
- `docs/HANDOFF.md`

Verification:

- `python -m pytest tests/test_installer_contract.py tests/test_version_consistency.py tests/test_secret_hygiene.py tests/test_agent_coordination_contract.py -q --timeout=60` - passed.
- `$env:ALLOW_RELEASE_RUNTIME_SECRETS='1'; python scripts\check_no_bundled_secrets.py` - passed.
- `git diff --check` - line-ending warnings only.

Remaining work:

- Commit, tag, push `v0.5.5`, then watch the release workflow.

## 2026-05-25 - Codex - Claude Test Review And v0.5.4 Release Fix

Summary:

- Reviewed Claude's `tests/test_email_triage_behavior.py` review request.
- Ran the submitted behavioral tests successfully and approved the test-only work.
- Took ownership of the CCA false-positive bug surfaced by Claude's test comments and fixed `_is_cca_context()` so bare `cca` matches as a token rather than inside words like `occasion`.
- Found `v0.5.3` release failed after successful lint, docker-build, build-exe, health smoke, and installer build at `Security Lint (Installer Extraction)`.
- Patched the installer source rule to exclude `.env` and `*.env` from the onedir payload while still shipping `sample.env` as a separate safe template.
- Bumped release metadata to `0.5.4`.

Files changed:

- `outlook_dashboard/ai.py`
- `tests/test_email_triage_behavior.py`
- `installer/replyright_setup.iss`
- `tests/test_installer_contract.py`
- `tests/test_secret_hygiene.py`
- `outlook_dashboard/__init__.py`
- `pyproject.toml`
- `agent-workspace/PROJECT_STATE.md`
- `agent-workspace/TASK_BOARD.md`
- `agent-workspace/HANDOFFS.md`
- `agent-workspace/AGENT_MESSAGES.md`

Verification:

- `python -m pytest tests/test_email_triage_behavior.py tests/test_installer_contract.py tests/test_version_consistency.py tests/test_secret_hygiene.py tests/test_agent_coordination_contract.py -q --timeout=60` - passed.
- `$env:ALLOW_RELEASE_RUNTIME_SECRETS='1'; python scripts\check_no_bundled_secrets.py` - passed.
- `python -m pytest tests/ -x --timeout=60` - 1273 passed, 6 existing `datetime.utcnow()` warnings, 35 subtests passed.
- `git diff --check` - line-ending warnings only.

Remaining work:

- Commit, tag, push `v0.5.4`, then watch the release workflow.

## 2026-05-25 - Claude - Protocol Adopted + Triage Behavior Tests Submitted For Review

Summary:

- Read all coordination files (`PROJECT_STATE.md`, `TASK_BOARD.md`, `HANDOFFS.md`, `DECISIONS.md`, `AGENT_RULES.md`, `AGENT_MESSAGES.md`, `CLAUDE.md`, `AGENTS.md`) per mandatory start protocol.
- Acknowledged coordination protocol in `AGENT_MESSAGES.md`.
- Confirmed authorship of `tests/test_email_triage_behavior.py` and left a `Status: Review Request` in `AGENT_MESSAGES.md`.
- Updated `TASK_BOARD.md`: "Adopt mandatory coordination protocol" → Approved by Codex; "Review/own local triage behavior test file" → Waiting for Codex Review.
- No implementation files modified. No restricted files touched (local_classifier.py, main.py, completed_training_pipeline.py, training_pipeline.py, build_exe.ps1, installer/replyright_setup.iss, docs/TRAINING_WORKFLOW.md, version files, 0.5.2/0.5.3 patch files).

Files changed:

- `agent-workspace/AGENT_MESSAGES.md` (appended Claude acknowledgement + Review Request)
- `agent-workspace/TASK_BOARD.md` (updated two task statuses)
- `agent-workspace/HANDOFFS.md` (this entry)

Test file submitted for review:

- `tests/test_email_triage_behavior.py` — 144 tests, 7 classes, all pass.
- Verification: `python -m pytest tests/test_email_triage_behavior.py -v --timeout=60` → 144 passed, 0 failed.
- Known issue documented: CCA substring false-positive ("cca" in `_CCA_TERMS` matches inside "occasion") — see test comment and AGENT_MESSAGES.md review request for details.

Remaining work:

- Codex must review `tests/test_email_triage_behavior.py` and leave `Approved` or `Needs Changes` in `AGENT_MESSAGES.md`.
- If Codex wants the CCA false-positive fixed, Claude will create a focused fix in `ai.py`.

## 2026-05-25 - Codex - Coordination Adopted For Active Project Work

Summary:

- Read the new `agent-workspace/` files at the start of the session.
- Checked Claude's latest old-channel handoff in `agent_comms/from_claude.md`.
- Found local changes outside Codex's lane: modified `agent_comms/from_claude.md` and untracked `tests/test_email_triage_behavior.py`; left them untouched.
- Updated the task board so Codex owns the `v0.5.3` release watch and Claude must acknowledge the new protocol before implementation work.
- Left Claude a direct message in `AGENT_MESSAGES.md` with the next required actions.

Files changed:

- `agent-workspace/PROJECT_STATE.md`
- `agent-workspace/TASK_BOARD.md`
- `agent-workspace/HANDOFFS.md`
- `agent-workspace/AGENT_MESSAGES.md`

Verification:

- `python -m pytest tests/test_agent_coordination_contract.py -q --timeout=60` - 4 passed.

Remaining work:

- Codex must continue watching the `v0.5.3` release workflow.
- Claude must acknowledge the protocol and identify whether it owns `tests/test_email_triage_behavior.py`.

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
