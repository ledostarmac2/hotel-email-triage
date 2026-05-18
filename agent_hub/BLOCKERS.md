# Active Blockers

Last updated: 2026-05-18

---

## BLOCKER-001: v0.1.1 tag blocked — Gemini security verdict pending

**Status:** ACTIVE

**Blocking:** v0.1.1 tag, GitHub Actions release run, installer distribution

**Owner:** Gemini

**What is needed:**
Gemini must review the files listed in HANDOFF_GEMINI.md and write a verdict
to the §Verdict section of that file. A verdict of "clean" unblocks the tag.
A list of specific issues blocks until those issues are fixed.

**Do not work around this blocker** by tagging without the verdict. The files
under review contain the security path that was previously shipping privileged
secrets in the installer.

**Resolution path:**
1. Gemini completes review and writes verdict
2. If clean: Codex or Claude tags v0.1.1
3. If issues found: Codex implements fixes per verdict, re-submits for review

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
| bundled_secrets.py contained SUPABASE_SERVICE_ROLE_KEY | Cleaned and verified by tests | 2026-05-18 |
| bundled_secrets.py contained ANTHROPIC_API_KEY | Cleaned and verified by tests | 2026-05-18 |
| No first-run credentials setup path | /credentials-setup implemented | 2026-05-18 |
| Fresh install with no .env would fail at Supabase call | needs_credentials_setup() added | 2026-05-18 |
| FastAPI 0.136.1 rejected HTMLResponse|RedirectResponse union type | response_model=None added | 2026-05-18 |
| test_bundled_secrets.py referenced removed _K/_dec | Rewritten for no-XOR inject() | 2026-05-18 |
