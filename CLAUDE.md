# Claude Agent Guide

Claude is the implementation/support agent for ReplyRight. Follow `AGENTS.md`, preserve the read-only Outlook safety posture, and use the repo-native coordination layer before and after every task.

## Required First Reads

Before doing work, read these files:

1. `AGENTS.md`
2. `agent-workspace/PROJECT_STATE.md`
3. `agent-workspace/TASK_BOARD.md`
4. `agent-workspace/HANDOFFS.md`
5. `agent-workspace/DECISIONS.md`
6. `agent-workspace/AGENT_RULES.md`
7. `agent-workspace/AGENT_MESSAGES.md`
8. `docs/ARCHITECTURE.md`
9. `docs/CURRENT_STATE.md`
10. `docs/HANDOFF.md`

## Mandatory Coordination

Claude must:

- Check the latest Codex message before starting implementation.
- Respond to unresolved Codex review comments, blockers, questions, or requested changes before starting unrelated work.
- Work only on the Active Task unless the user explicitly says otherwise.
- Leave Codex a review request in `agent-workspace/AGENT_MESSAGES.md` after implementation.
- Update `agent-workspace/HANDOFFS.md` after meaningful work.
- Update `agent-workspace/TASK_BOARD.md` if task status changes.
- Treat the session as incomplete if it does not write to `agent-workspace/AGENT_MESSAGES.md`.
- Not mark work `Done` unless Codex has reviewed it or the user explicitly bypasses review.

## Finish Checklist

Before ending a session:

- Update handoff notes with summary, files changed, verification, and remaining work.
- Update task status if it changed.
- Add a direct message to Codex in `agent-workspace/AGENT_MESSAGES.md`.
- Include tests/checks run and the next required action.
- Run the Mandatory Consistency Checklist in `agent-workspace/AGENT_RULES.md` and update any affected files.

## Coordination Channel

Use `agent-workspace/AGENT_MESSAGES.md` for all direct Codex messages.
Do not use `agent_comms/from_claude.md`; that channel is retired as of 2026-05-25.

## Training the Classifier

When Brian asks Claude to "train the model" or "train the classifier," follow `docs/TRAINING_WORKFLOW.md`.

Critical distinction:

- In-app training endpoints stay zero-credit and must not call Claude/OpenAI/Google.
- Outside-agent training requires Claude to label sanitized Completed Request examples using Claude's own model judgment before training the local classifier.

Do not claim training is complete by only running `run_completed_pipeline()`, `heuristic_analysis()`, or an app training endpoint. Those are deterministic/staging paths. For Brian's outside-agent request, sanitized examples must be labeled by the outside agent, only sanitized labeled examples may be stored, raw imported bodies must be purged, and duplicate-prevention metadata must be preserved.
