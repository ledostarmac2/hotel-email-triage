# Security Gates

Last updated: 2026-05-18

These gates must NEVER be bypassed, downgraded, or removed.
Any agent that lowers a gate is violating DEC-003 in DECISIONS.md.

---

## GATE-S01: No privileged keys in bundled_secrets._SECRETS

**Rule:** `bundled_secrets._SECRETS` must not contain any of:
- `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_AI_API_KEY`
- `GEMINI_API_KEY`
- `MICROSOFT_CLIENT_SECRET`
- Any key matching `*_SECRET` or `*_API_KEY` that is not the Supabase anon key

**Test:** `tests/test_secret_hygiene.py::test_bundled_secrets_contains_no_privileged_key_names`

**Status:** PASSING (ea84602)

---

## GATE-S02: No encoded/obfuscated secret blobs in bundled_secrets.py

**Rule:** No base64, XOR, or other encoding of secret values in source code.
Static checker: `scripts/check_no_bundled_secrets.py`

**Test:** `tests/test_secret_hygiene.py::test_check_no_bundled_secrets_script_passes`

**Status:** PASSING (ea84602)

---

## GATE-S03: .env excluded from installer

**Rule:** `.env` must appear only in the Excludes of `installer/replyright_setup.iss`,
never as a Source. This prevents any local `.env` from shipping in the installer.

**Test:** `tests/test_installer_contract.py::test_inno_installer_bundles_onedir_app_and_excludes_runtime_secrets`

**Status:** PASSING (ea84602)

---

## GATE-S04: credentials_setup.html contains no hardcoded secrets

**Rule:** The credentials setup HTML page must not contain JWT prefixes (`eyJhbGci`),
`sk-ant-`, `sk-proj-`, or any actual API key values in placeholder text or comments.

**Test:** `tests/test_secret_hygiene.py::test_credentials_setup_html_no_hardcoded_secrets`
**Test:** `tests/test_first_run_setup.py::test_credentials_setup_page_renders_no_prefilled_secrets`

**Status:** PASSING (ea84602)

---

## GATE-S05: sample.env contains no real secret values

**Rule:** `installer/sample.env` must have all secret fields empty.
It is safe to ship in the installer only because it contains no values.

**Test:** `tests/test_secret_hygiene.py::test_sample_env_has_no_real_secret_values`

**Status:** PASSING (ea84602)

---

## GATE-S06: Gemini independent security review

**Rule:** An independent agent (Gemini) must review the files listed in
HANDOFF_GEMINI.md and return a written verdict before any release tag.

**Test:** No automated test — requires Gemini action.

**Status:** PENDING — unblocks when Gemini writes verdict to HANDOFF_GEMINI.md §Verdict

---

## GATE-S07: No credentials logged or exposed in tracebacks

**Rule:** `write_local_env()`, `needs_credentials_setup()`, `admin_setup_available()`,
and the `/credentials-setup` route handler must not log or expose credential values
in error messages, debug output, or HTTP responses.

**Test:** `tests/test_secret_hygiene.py` (multiple assertions)

**Status:** PASSING (ea84602)

---

## GATE-S08: Session cookie remains httponly and samesite=lax

**Rule:** The `rr_session` cookie must be set with `httponly=True` and `samesite="lax"`.

**Test:** `tests/test_first_run_setup.py::test_api_first_run_setup_creates_admin_and_sets_session_cookie`

**Status:** PASSING (ea84602)

---

## GATE-S09: No reply sending

**Rule:** No code path in any production module may compose or transmit an email
reply to an Outlook message. Read-only posture must be preserved.

**Status:** PASSING — no send capability exists; enforced by code review on PRs.

---

## GATE-S10: Raw email bodies not logged

**Rule:** No production code may write full email body text to logs or Supabase.
PII, reservation numbers, payment details, and attachments stay off-cloud.

**Status:** PASSING — enforced by redaction.py + code review on PRs.
