# ReplyRight Agent Guide

This repository is the ReplyRight hotel reservations email triage app. Future agents should keep the project easy to resume from another computer and preserve the current read-only Outlook safety posture unless the user explicitly approves a broader workflow.

## Required First Reads

Before making changes, read these files in order:

1. `AGENTS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/CURRENT_STATE.md`
4. `docs/HANDOFF.md`

Use `docs/CURRENT_STATE.md` as the latest truth. Treat older root-level planning docs as historical unless the current docs say otherwise.

For broad architecture, adaptive learning, Supabase, staged AI pipeline, shared feedback, or admin dashboard work, also read:

5. `docs/FUTURE_ROADMAP_SUPABASE_ADAPTIVE_LEARNING.md`

## Handoff Protocol

After meaningful work:

- Update `docs/CURRENT_STATE.md` with the latest status, risks, and next steps.
- Append a concise entry to `docs/HANDOFF.md` with date, summary, files changed, verification, and remaining work.
- Update `docs/DECISIONS.md` when architecture, runtime, data flow, security posture, or integration strategy changes.
- Update `docs/CHANGELOG_AI.md` for meaningful AI-assisted changes.
- Keep docs and code in sync. Do not leave stale setup, build, or workflow instructions behind.
- Do not store chain-of-thought, private reasoning, credentials, mailbox contents, or large memory dumps in docs.

## Working Rules

- Preserve read-only Outlook behavior. The app may read/import messages and update local SQLite status, but it must not send, delete, archive, move, mark read, or mutate Outlook messages without explicit new approval.
- Do not commit `.env`, local SQLite databases, exported `.msg` files, build folders, virtual environments, vendored dependencies, or startup logs.
- Keep `outlook_dashboard/` as the current runnable app unless the user explicitly asks to migrate to the Next.js scaffold in `app/`.
- Prefer small, focused changes. Avoid broad refactors while launch/build/debugging work is still active.
- Keep the VBA macro portable. It should not hardcode one workstation path.
- Target workflow: Refresh Inbox should use the OpenAI API to assign triage metadata for imported emails, choosing the best currently available free-tier or lowest-cost suitable OpenAI model after checking current official OpenAI model/pricing docs. Keep local deterministic triage as a fallback and for tests. Reserve Claude Opus for explicit user actions such as `AI Suggestion`.
- Redact payment-like data before any AI call.

## Main Commands

```powershell
python -m pip install -r requirements.txt
python -m unittest tests.test_ai_and_database
python run_desktop.py
.\build_exe.ps1
```

The Windows executable builds to `dist\ReplyRight.exe`. Runtime data and logs are local and ignored by git.
