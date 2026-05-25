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

## Mandatory Consistency Checklist

After every meaningful change, each agent must check whether the change affects any of the files below and update them if the existing content becomes stale. Do not edit every file on every pass — only update a file if its content is now incorrect or missing key information.

### Coordination files

- [ ] `agent-workspace/PROJECT_STATE.md` — current release target, active app path, safety boundary
- [ ] `agent-workspace/TASK_BOARD.md` — task status, owner, next required action
- [ ] `agent-workspace/HANDOFFS.md` — session summary, files changed, verification, remaining work
- [ ] `agent-workspace/AGENT_MESSAGES.md` — direct message to the other agent (required every session)
- [ ] `agent-workspace/DECISIONS.md` — architecture, runtime, data-flow, security posture, or integration changes

### Docs

- [ ] `docs/CURRENT_STATE.md` — release status, known risks, recommended next steps
- [ ] `docs/ARCHITECTURE.md` — active modules, data flow, intelligence layers, build/packaging
- [ ] `docs/ROADMAP.md` — phase completion, active vs. inactive directions
- [ ] `docs/V1_RELEASE_PLAN.md` — gate status, current position, canonical doc pointers
- [ ] `docs/SECURITY_AND_PRIVACY.md` — Outlook boundary, PII rules, logging rules, redaction coverage
- [ ] `docs/TESTING.md` — test file table, what is/is not tested, phase 7 considerations
- [ ] `docs/OPERATIONS_GUIDE.md` — operator workflow, queue views, feedback, triage actions
- [ ] `docs/HANDOFF.md` — cumulative handoff log (append, do not replace)

### Root docs

- [ ] `README.md` — if install/usage instructions, version, or feature set change
- [ ] `AGENTS.md` — if agent rules, AI usage rules, or training contract change
- [ ] `CLAUDE.md` — if Claude-specific required first reads or coordination protocol change

### Code and tests

- [ ] `tests/` — add or update tests for any new or changed behavior
- [ ] Packaging/build scripts (`build_exe.ps1`, `installer/replyright_setup.iss`) — if bundled files, version, or startup behavior change
- [ ] `docs/CHANGELOG_AI.md` or release notes — for meaningful AI-assisted behavior changes

