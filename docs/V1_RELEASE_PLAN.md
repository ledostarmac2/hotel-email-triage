# ReplyRight v1.0.0 Release Plan

Last updated: 2026-05-25

## Current Position

ReplyRight is at `0.5.0` and is best treated as late internal alpha / early beta.

The active application is:

```text
run_desktop.py
  -> FastAPI backend in outlook_dashboard/
  -> native PySide6 shell in replyright_qt/
  -> local SQLite runtime data
  -> optional Supabase, Outlook COM, OpenAI, Google AI, Claude
```

The local Windows EXE builds at:

```text
dist\ReplyRight\ReplyRight.exe
```

User-facing releases must remain installer-first:

```text
installer\output\ReplyRightSetup-v{version}.exe
```

## Canonical Docs

Use these as the source of truth:

- `docs/CURRENT_STATE.md` - latest project status.
- `docs/ARCHITECTURE.md` - active architecture and boundaries.
- `docs/TRAINING_PIPELINE.md` - current in-app training contract.
- `docs/CLASSIFIER.md` - local classifier behavior and gaps.
- `docs/SECURITY_AND_PRIVACY.md` - safety, Outlook, PII, and AI rules.
- `docs/DEPLOYMENT.md` - installer and runtime deployment.
- `docs/OPERATIONS_GUIDE.md` - operator workflow.
- `docs/V1_RELEASE_PLAN.md` - v1 gates and current checklist.

Historical or supporting docs:

- `docs/archive/**` - historical planning and migration records. Each Markdown file is bannered as historical.
- `docs/coordination/**` - previous multi-agent coordination, not current product state. `docs/coordination/README.md` is bannered as historical.
- `docs/PROPERTY_KNOWLEDGE.md` - generated/historical property knowledge artifact.
- `docs/TRAINING_WORKFLOW.md` - agent-facing training runbook (import→label→upload→purge).
- `docs/LABELING_PROMPTS.md` - optional external human/agent labeling runbook, outside the running app.

## v1.0.0 Gates

### Gate 1 - Build And Install Reliability

Required:

- `python -m pytest tests/ -x --timeout=60` passes.
- `.\build_exe.ps1` builds `dist\ReplyRight\ReplyRight.exe`.
- `dist\ReplyRight\ReplyRight.exe --health-smoke` passes.
- `.\installer\build_installer.ps1` builds `ReplyRightSetup-v{version}.exe`.
- Clean Windows install launches without a localhost/refused-to-connect page.
- Diagnostics report version, build, database, Outlook, Supabase, AI, and classifier status without secrets.

Current status:

- Source EXE build and packaged health smoke are working.
- Installer-first release path exists.
- Fresh-machine install validation still needs a manual pass before v1.

### Gate 2 - Outlook And Security Boundary

Required:

- Outlook remains read-only.
- No send, delete, archive, move, categorize, mark read/unread, or other Outlook mutation.
- AI drafts stay suggestions only.
- No secrets, raw mailbox content, raw email bodies, session cookies, or service-role keys in logs, docs, installer payloads, or test fixtures.
- Training exports store only redacted bodies, sender domains, subject tokens, fingerprints, and labels.

Current status:

- Read-only design is documented and covered by starter tests.
- Additional guardrail tests are being expanded for the v1 push.

### Gate 3 - Training And Classifier Readiness

Required:

- In-app training endpoints are zero-credit by default and do not call Claude/Anthropic, OpenAI, or Google AI.
- Completed Requests import produces sanitized training examples.
- Human-reviewed or externally reviewed examples can train the local classifier.
- Classifier status clearly shows example counts, trained targets, version, metrics, and gaps.
- Candidate model promotion/rollback is explicit or the limitation is documented.

Current status:

- `training_pipeline.py` and `completed_training_pipeline.py` use existing analysis/heuristics and report `external_ai_used=false`.
- The local classifier trains `urgency`, `owner`, and `category`.
- Bootstrap/local examples exist, but real human-reviewed beta examples are not yet sufficient for v1 confidence.
- Rollback/admin model comparison remains a v1 hardening item.

### Gate 4 - Safety And Review UX

Required:

- Low-confidence and risky messages are visible.
- Billing, chargeback/refund, ADA/accessibility, medical, legal, discrimination, VIP/consortia, same-day arrival, serious complaint, and safety/security cases trigger review/risk indicators.
- Detail view explains classification source, signals, risk flags, owner, category, urgency, and confidence.
- AI draft UI clearly preserves human review.

Current status:

- Core risk flags and confidence exist.
- The v1 work remaining is polish and making review states hard to miss.

### Gate 5 - Internal Beta Evidence

Required:

- 500 to 1,000 real emails reviewed by Brian or a trusted beta user.
- Correction rates tracked for urgency, owner, category, contact type, risk, summary quality, and reply quality.
- Failure categories documented.
- Classifier retrained on reviewed corrections.
- No major packaging, privacy, Outlook, or auth incident remains open.

Current status:

- This is the biggest v1 blocker. Synthetic tests can reduce risk, but real beta evidence is still required.

## Current v1 Work Split

Codex lane:

1. Source-of-truth doc consolidation.
2. Version/release hygiene and consistency tests.
3. Training pipeline contract reconciliation.
4. Core guardrail tests for versioning/training/docs.

Claude lane:

4. Additional automated safety tests.
5. Classifier/admin hardening.
6. Synthetic beta simulation.
7. UI safety polish.
8. Installer and diagnostics hardening.

## Release Candidate Checklist

Before tagging a v1 release candidate:

- Version values match in `outlook_dashboard/__init__.py`, `pyproject.toml`, FastAPI metadata, installer fallback, updater fallback metadata, and build metadata generation.
- `docs/CURRENT_STATE.md`, `docs/HANDOFF.md`, and this plan are updated.
- Canonical training docs reflect the actual code path.
- Full test suite passes.
- EXE build and health smoke pass.
- Installer build passes.
- Generated EXE/installer, databases, logs, `.env`, and mailbox exports are not staged.
- Manual launch/sign-in/Refresh Inbox/Admin/KYC smoke is complete.
- Any unresolved beta risks are listed in `docs/CURRENT_STATE.md`.
