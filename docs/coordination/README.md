# ReplyRight Agent Coordination Hub

> Historical coordination archive. Do not treat this directory as current project
> state. Use `docs/CURRENT_STATE.md`, `docs/HANDOFF.md`, and
> `docs/V1_RELEASE_PLAN.md` for active status and release planning.

This directory records previous multi-agent work coordination.

## Files

| File | Purpose |
|---|---|
| CURRENT_SITREP.md | Ground truth — what is done, what is blocked, what is next |
| TASK_BOARD.md | Who owns what, current status per agent |
| DECISIONS.md | Architecture and process decisions made during multi-agent work |
| BLOCKERS.md | Active blockers with owner and resolution path |
| HANDOFF_CLAUDE.md | Claude's active work and context |
| HANDOFF_CODEX.md | Exact work for Codex when rate limit returns |
| HANDOFF_GEMINI.md | Exact ask for Gemini; where to write the security verdict |
| RELEASE_GATES.md | Gates that must all be green before tagging a release |
| SECURITY_GATES.md | Security-specific gates — never bypass these |
| PYSIDE6_MIGRATION.md | PySide6 migration summary and current scaffold status |
| DAILY_LOG.md | Chronological log of decisions and changes |

## Usage protocol

- Before starting work, read CURRENT_SITREP.md and BLOCKERS.md.
- After completing work, update CURRENT_SITREP.md, TASK_BOARD.md, and DAILY_LOG.md.
- When handing off to another agent, update the relevant HANDOFF_*.md file.
- Never edit SECURITY_GATES.md or RELEASE_GATES.md to lower the bar — only raise it.
- BLOCKERS.md entries must be resolved by the owning agent, not worked around.

## Agent roles

| Agent | Primary responsibility |
|---|---|
| Claude | Architecture, planning, PySide6 migration, documentation |
| Codex | Implementation of planned features; security fix execution |
| Gemini | Independent security audit; release verification |
