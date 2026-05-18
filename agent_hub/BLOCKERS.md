# Active Blockers

Last updated: 2026-05-18

---

## BLOCKER-002: Codex rate-limited

**Status:** MAY HAVE RESOLVED — check before proceeding

**Blocking:** Any implementation work assigned to Codex

**Owner:** Codex (self-resolves when rate limit lifts)

**Resolution path:**
1. Codex checks its rate limit status
2. If resolved: picks up from HANDOFF_CODEX.md
3. If still limited: Claude or Gemini can handle the work if urgent

---

## Resolved blockers (for history)

| Blocker | Resolution | Date |
|---|---|---|
| BLOCKER-001: v0.1.1 tag blocked | Gemini completed review and returned CLEAN verdict | 2026-05-18 |
| bundled_secrets.py contained SUPABASE_SERVICE_ROLE_KEY | Cleaned and verified by tests | 2026-05-18 |
| bundled_secrets.py contained ANTHROPIC_API_KEY | Cleaned and verified by tests | 2026-05-18 |
| No first-run credentials setup path | /credentials-setup implemented | 2026-05-18 |
| Fresh install with no .env would fail at Supabase call | needs_credentials_setup() added | 2026-05-18 |
| FastAPI 0.136.1 rejected HTMLResponse|RedirectResponse union type | response_model=None added | 2026-05-18 |
| test_bundled_secrets.py referenced removed _K/_dec | Rewritten for no-XOR inject() | 2026-05-18 |
