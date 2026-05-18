# Agent Coordination Decisions

Last updated: 2026-05-18

These decisions govern how the three agents collaborate. They complement the
architectural decisions in docs/DECISIONS.md.

---

## DEC-001: Gemini owns the security verdict for every release

**Decision:** Before any version is tagged, Gemini must review the security-sensitive
files and return a verdict. A verdict of "clean" is required to proceed. A verdict
listing specific issues blocks the tag until those issues are fixed and re-reviewed.

**Rationale:** Claude and Codex share a context and implementation history that can
create blind spots. An independent agent reviewing the actual files provides a
second-opinion gate that is harder to rationalize around.

**Files Gemini reviews:** `bundled_secrets.py`, `installer/replyright_setup.iss`,
`credentials_setup.html`, `installer/sample.env`, `auth.py` (credential functions),
`config.py` (write_local_env), `.github/workflows/build.yml`.

---

## DEC-002: Codex implements, Claude architects

**Decision:** Codex is the implementation agent for features that Claude has
planned and scoped. Claude does not duplicate Codex's implementation work.
Claude does planning, documentation, architecture, test design, and PySide6 migration.

**Rationale:** Avoids parallel conflicting edits to the same files. Each agent
stays in its lane; handoff documents define the boundary.

---

## DEC-003: No agent may lower a security gate

**Decision:** No agent may edit SECURITY_GATES.md or RELEASE_GATES.md to
remove or soften a gate. Gates may only be added or promoted to required status.
If a gate cannot be met, the correct action is to document why in BLOCKERS.md,
not to remove the gate.

**Rationale:** Security gates exist because real secrets were at risk of shipping
in the installer. That incident must not recur.

---

## DEC-004: PySide6 scaffold is additive and non-production until first runnable slice

**Decision:** `replyright_core/` and `replyright_qt/` are scaffold directories.
They must not be imported by `outlook_dashboard/`, `run_desktop.py`, or the
installer build until a runnable native slice exists and has been verified.
Adding PySide6 to production requirements is deferred until the first slice runs.

**Rationale:** Adding a 200 MB+ Qt dependency to the production installer before
any Qt UI is functional would increase bundle size with no user benefit and
introduce a new packaging risk category before the v0.1.1 release.

---

## DEC-005: No QWebEngineView, no pywebview, no Electron, no Tauri in the Qt app

**Decision:** The PySide6 native shell must use only native Qt widgets.
`QWebEngineView` is specifically prohibited as the primary UI surface.
pywebview, Electron, and Tauri are also prohibited.

**Rationale:** The entire point of the PySide6 migration is to eliminate the
browser/WebView failure modes that caused the v0.1.0 release incident. Bringing
a browser engine back in through Qt defeats the purpose.

---

## DEC-006: agent_hub is updated by the agent that last did work

**Decision:** When an agent completes a task, it must update CURRENT_SITREP.md,
TASK_BOARD.md, and DAILY_LOG.md before stopping work. If blocked, it must
update BLOCKERS.md with the blocker, owner, and resolution path.

**Rationale:** Avoids stale state where the next agent starts from incorrect
assumptions about what is done.
