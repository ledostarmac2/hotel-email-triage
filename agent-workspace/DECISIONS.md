# Agent Coordination Decisions

## 2026-05-28 - Agent-Assisted Training Requires Agent Labels

Decision:

- When Brian explicitly asks Codex or Claude to "train the model" or "train the classifier," the outside agent must label sanitized Completed Request examples using its own model judgment before training the local classifier.
- `run_completed_pipeline()` and `heuristic_analysis()` remain valid zero-credit in-app/staging tools, but they are not the final labeler for Brian's outside-agent training request.
- App runtime and FastAPI/admin training endpoints must remain zero-credit and must not call Claude, OpenAI, Google AI, or any other external model.

Rationale:

- Brian wants Codex/Claude to contribute model judgment during explicit outside-agent training while preserving the app's no-credit runtime training posture.
- Treating deterministic heuristic labels as agent-reviewed labels weakens the classifier training signal and misrepresents what was done.

Consequences:

- Future training handoffs must state whether labels came from outside-agent judgment or from deterministic heuristics.
- If a workflow only runs `run_completed_pipeline()` plus classifier `train()`, it is not complete for an outside-agent training request unless a separate agent-labeling step occurred.
- Safe inputs, sanitized storage, raw-body purge, read-only Outlook behavior, and duplicate-prevention metadata remain mandatory.

## 2026-05-25 - Retire agent_comms/ Channel

Decision:

- `agent_comms/from_claude.md` and `agent_comms/from_codex.md` are retired as active communication channels.
- Both files have been marked with deprecation notices pointing to `agent-workspace/AGENT_MESSAGES.md`.
- `agent_comms/` is preserved in git as a historical archive. Do not append new coordination messages there.

Rationale:

- The `agent-workspace/` layer supersedes the ad-hoc file-per-agent pattern.
- Duplicate channels create ambiguity about which is authoritative.

## 2026-05-25 - Repo-Native Coordination

Decision:

- Use `agent-workspace/` markdown files as the mandatory Claude/Codex coordination layer.
- Use `agent-workspace/AGENT_MESSAGES.md` as the direct agent-to-agent message channel.
- Keep the protocol file-based and reviewable in git. Do not build a server, database, chat app, or real-time system.

Rationale:

- File-based coordination is easy to inspect, diff, review, and resume from another machine.
- The project already uses docs and handoff logs successfully.
- The user explicitly requested repo-native coordination, clear gates, and no large coordination app.

Consequences:

- Every agent session must read the coordination files before work.
- Every agent session must write a direct message before ending.
- A session without an `AGENT_MESSAGES.md` entry is incomplete.
