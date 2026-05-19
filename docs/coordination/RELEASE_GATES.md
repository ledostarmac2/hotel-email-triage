# Release Gates

Last updated: 2026-05-18

All gates must be green before any version tag is created.

---

## v0.1.1 gates

| Gate | Status | Owner | Notes |
|---|---|---|---|
| All security gates pass (see SECURITY_GATES.md) | PASS | Codex/Claude | ea84602 |
| Gemini security verdict: CLEAN | PASS | Gemini | Verdict written to HANDOFF_GEMINI.md |
| `py -3.12 -m pytest --timeout=60` passes (zero failures) | PASS | Claude | 471 passed |
| `build_exe.ps1` runs without error | UNKNOWN | Codex | Not yet re-run post ea84602 |
| `installer/build_installer.ps1` runs without error | UNKNOWN | Codex | Not yet re-run |
| Installer `ReplyRightSetup-v0.1.1.exe` produced | UNKNOWN | Codex | |
| Smoke test: fresh Windows install, no `.env`, app reaches `/credentials-setup` | UNKNOWN | Codex | |
| Smoke test: credentials entry → `/setup` redirect | UNKNOWN | Codex | |
| Smoke test: first admin creation + login | UNKNOWN | Codex | |
| Smoke test: uninstall entry in Add/Remove Programs | UNKNOWN | Codex | |
| GitHub Actions release run uploads installer only (not raw EXE) | UNKNOWN | Codex | |

---

## Standing rules for all releases

1. `SUPABASE_SERVICE_ROLE_KEY` must never appear in `bundled_secrets._SECRETS`
2. `ANTHROPIC_API_KEY` must never appear in `bundled_secrets._SECRETS`
3. `.env` must never be in the installer's `[Files]` Source lines (only in Excludes)
4. All tests must pass before tagging
5. Gemini must have reviewed security-sensitive files and returned a clean verdict
6. The release artifact is always the Inno Setup installer, never the raw PyInstaller output
7. No real secrets in test fixtures, HTML source, or documentation
