# Task Board

Last updated: 2026-05-18

## Claude

| Task | Status | Notes |
|---|---|---|
| PySide6 migration plan | Done | docs/PYSIDE6_MIGRATION_PLAN.md |
| PySide6 scaffold structure | Done | replyright_core/, replyright_qt/ |
| Agent hub creation | Done | this directory |
| Core service interface definitions | Done | replyright_core/services/ |
| Core model dataclasses | Done | replyright_core/models/ |
| Qt window skeletons | Done | replyright_qt/windows/ |
| Qt viewmodel skeletons | Done | replyright_qt/viewmodels/ |
| Qt widget skeletons | Done | replyright_qt/widgets/ |
| First native login slice | Pending | After v0.1.1 clears |
| PySide6 dependency added to requirements | Blocked | Not until first runnable slice |

## Codex

| Task | Status | Notes |
|---|---|---|
| bundled_secrets.py cleanup | Done (verified) | ea84602 on main |
| /credentials-setup route | Done (verified) | ea84602 on main |
| write_local_env() | Done (verified) | ea84602 on main |
| needs_credentials_setup() | Done (verified) | ea84602 on main |
| test_secret_hygiene.py | Done (verified) | 14 assertions passing |
| v0.1.1 tag and release | Blocked | Pending Gemini verdict + rate limit |
| Any additional security fixes | Blocked | Pending Gemini verdict |
| Rate limit resolved | Unknown | Check before starting |

## Gemini

| Task | Status | Notes |
|---|---|---|
| Security review of bundled_secrets.py | In progress | See HANDOFF_GEMINI.md |
| Security review of credentials_setup.html | In progress | |
| Security review of installer/sample.env | In progress | |
| Security review of auth.py changes | In progress | |
| Security review of config.py changes | In progress | |
| Verdict returned to agent_hub | Pending | Write to HANDOFF_GEMINI.md §Verdict |
