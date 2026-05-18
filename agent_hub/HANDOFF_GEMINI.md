# Handoff: Gemini

Last updated: 2026-05-18

## Your task: security review for v0.1.1

ReplyRight v0.1.1 fixes a critical security issue: privileged secrets were
previously shipped in the compiled installer via XOR-obfuscated values in
`bundled_secrets.py`. Those secrets have been removed and a proper first-run
credentials setup UI has been added. You need to verify this fix is complete.

---

## Files to review

### 1. `outlook_dashboard/bundled_secrets.py`
Verify:
- `_SECRETS` dict is empty or contains NO privileged keys
- No `SUPABASE_SERVICE_ROLE_KEY` value or name present
- No `ANTHROPIC_API_KEY` value or name present
- No `OPENAI_API_KEY` value or name present
- No encoded/obfuscated blobs (base64, XOR, etc.) that decode to secret values
- The `inject()` function only copies `_SECRETS` into env if not already set

### 2. `installer/replyright_setup.iss`
Verify:
- `.env` appears in the `[Files]` section **only as an Excludes flag**, never as a Source
- `*.sqlite3` is excluded
- `*.log` is excluded
- `sample.env` is sourced (safe — it contains no real values)
- `SUPABASE_SERVICE_ROLE_KEY` does not appear anywhere in the file
- No pre-filled credential values in any `Source` directive

### 3. `outlook_dashboard/static/credentials_setup.html`
Verify:
- No hardcoded API keys or secret values in the HTML source
- No JWT-prefix patterns (`eyJhbGci`) in placeholder text
- No `sk-ant-`, `sk-proj-`, or `sk-` patterns in placeholder text
- Form POSTs to `/credentials-setup` (local server only — no external submission)
- No inline JavaScript that transmits credentials to a third party
- No `autocomplete` enabled on secret fields

### 4. `installer/sample.env`
Verify:
- All secret fields are empty (no real values)
- `SUPABASE_SERVICE_ROLE_KEY=` is present but empty (or absent)
- No `ANTHROPIC_API_KEY` with a real value
- Safe to ship in the installer without credentials exposure

### 5. `outlook_dashboard/auth.py` — `needs_credentials_setup()` and `write_local_env()` area
Verify:
- `needs_credentials_setup()` returns True when Supabase config is absent
- No credentials are logged (no `_log.info/debug` that includes secret values)
- `admin_setup_available()` still returns False when service key is absent

### 6. `outlook_dashboard/config.py` — `write_local_env()`
Verify:
- Written values are not logged
- File write is atomic (temp file + os.replace)
- No values are exposed in error messages or tracebacks
- Only writes to `ROOT_DIR / ".env"` (not a user-accessible web path)

### 7. `.github/workflows/build.yml`
Verify:
- No secrets are echoed or logged in build steps
- The workflow uploads only the Inno Setup installer, not `dist/ReplyRight.exe` directly
- No `.env` file is committed or included in the build artifact

---

## How to write your verdict

Find the §Verdict section below and fill it in. Codex will read this file
before proceeding with the v0.1.1 tag.

---

## §Verdict

**Status:** PENDING — Gemini has not yet completed review.

**Date reviewed:** (fill in)

**Verdict:** [ CLEAN | ISSUES FOUND ]

**Issues (if any):**
(list specific file, line number, and required fix for each issue)

**Summary:**
(one paragraph)

---

## Context: what the original problem was

`bundled_secrets.py` previously contained:
```python
_K = b"WaldorfAstoriaNYCWA"
_SECRETS = {
    "SUPABASE_SERVICE_ROLE_KEY": "<base64-XOR-encoded value>",
    "ANTHROPIC_API_KEY": "<base64-XOR-encoded value>",
}
def _dec(encoded: str) -> str:
    raw = base64.b64decode(encoded)
    return bytes(char ^ _K[index % len(_K)] for index, char in enumerate(raw)).decode("utf-8")
def inject() -> None:
    for name, encoded in _SECRETS.items():
        if not os.environ.get(name):
            os.environ[name] = _dec(encoded)
```

The XOR encoding is trivially reversible — any user who decompiles the PyInstaller
bundle gets the service-role key and Anthropic key in plaintext. These values
were shipping in every copy of `ReplyRightSetup-v0.1.0.exe`. The fix removes
them entirely and replaces the flow with a local credentials setup screen.
