# DO-178C Compliance Test Plan Starter

ReplyRight is not DO-178C certified. This folder starts a compliance-style evidence pattern for future Aerospace & Defense work so requirements, tests, and safety boundaries can be traced from the beginning.

## Current Scope

- Planning and repository evidence only.
- Static guards for high-risk behavior that must stay controlled.
- Traceability metadata in `do178c_traceability.json`.
- Executable pytest checks in `tests/test_do178c_compliance.py`.

## Current Safety Contracts

- Outlook integration stays read-only.
- AI output remains advisory and human-reviewed.
- In-app training remains zero-credit and must not call Claude or other paid AI APIs.
- The active desktop shell remains native PySide6, not a browser/WebView runtime.
- Compliance claims must be explicit: this is a starter suite, not certification evidence accepted by an authority.

## Next Evidence To Add

- Requirements IDs for each regulated workflow.
- Low-level requirement to test-case traceability.
- Tool qualification notes for test and build tools.
- Structural coverage strategy appropriate to the chosen software level.
- Configuration management and change-control evidence.
- Review checklists for requirements, design, code, tests, and verification results.
