# Handoff: Codex

Last updated: 2026-05-18

## First: check your rate limit status

If you are still rate-limited, stop here. Come back when the limit has lifted.

## Second: read BLOCKERS.md

Check if BLOCKER-001 (Gemini security verdict) has been resolved.
Do not proceed with the release steps until the verdict is in.

---

## What Codex needs to do (in order)

### Step 1: Check Gemini verdict

Open `docs/coordination/HANDOFF_GEMINI.md` and look for the §Verdict section.

- **If verdict is "CLEAN":** proceed to Step 2.
- **If verdict lists specific issues:** implement the listed fixes (see Step 1a below),
  then return the fixed files to Gemini for re-review before proceeding to Step 2.
- **If no verdict is present yet:** stop and do not tag. Notify the user.

### Step 1a (only if verdict requires fixes)

Implement ONLY the changes Gemini specifies. Do not add unrelated changes.
The files under review are:
- `outlook_dashboard/bundled_secrets.py`
- `installer/replyright_setup.iss`
- `outlook_dashboard/static/credentials_setup.html`
- `installer/sample.env`
- `outlook_dashboard/auth.py` (credential-related functions only)
- `outlook_dashboard/config.py` (write_local_env only)
- `.github/workflows/build.yml`

After implementing fixes: run `py -3.12 -m pytest --timeout=60`, confirm all pass,
commit, and update HANDOFF_GEMINI.md asking for re-review.

### Step 2: Tag v0.1.1 and trigger release

```powershell
# In c:\Users\btarabocchia\Downloads\hotel-email-triage
git tag v0.1.1
git push origin v0.1.1
```

This triggers the GitHub Actions build workflow (`.github/workflows/build.yml`).
Monitor the Actions run for the installer artifact upload.

### Step 3: Download and smoke test the release installer

1. Go to the GitHub release for v0.1.1
2. Download `ReplyRightSetup-v0.1.1.exe`
3. Install on a clean Windows machine with NO pre-existing `.env`
4. Launch from Start Menu shortcut
5. Confirm the app reaches `/credentials-setup` (not a connection error)
6. Enter Supabase credentials → confirm redirect to `/setup`
7. Create first admin → confirm login works
8. Confirm uninstall entry exists in Add/Remove Programs

### Step 4: Update docs/coordination after completion

Update `CURRENT_SITREP.md`, `TASK_BOARD.md`, and `DAILY_LOG.md` with:
- v0.1.1 tagged
- smoke test result
- whether the installer is ready for distribution

---

## Hard constraints for Codex (do not violate)

- Do not tag v0.1.1 without Gemini verdict
- Do not bundle `.env` in the installer
- Do not put `SUPABASE_SERVICE_ROLE_KEY` in `bundled_secrets._SECRETS`
- Do not put `ANTHROPIC_API_KEY` in `bundled_secrets._SECRETS`
- Do not add reply sending
- Do not log raw email bodies
- Do not touch `app/`, `replyright_kernel/`, `replyright_core/`, or `replyright_qt/`
  unless specifically required by the Gemini verdict
- Do not commit real secrets
