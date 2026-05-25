# scripts/

Utility scripts for the ReplyRight development and operational workflow.
These run outside the app process and require `.env` or env vars to be set.

---

## seal_credentials.py

Reads `.env` and re-encrypts each credential into `outlook_dashboard/bundled_secrets.py`.
Run after updating `.env` if you use the bundled-secrets path for distribution.

```
python scripts/seal_credentials.py
```

---

## seed_prompt_versions.py

Upserts the default Claude Analyze system prompt into the Supabase `prompt_versions` table.
Run once after schema setup, or when you want the hardcoded prompt to be editable from
the admin dashboard without a code deploy.

Requires: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

```
python scripts/seed_prompt_versions.py
```

---

## export_for_labeling.py

Pulls unreviewed training examples from Supabase, formats them as a numbered Markdown
batch for human labeling, and writes to `labeling/exports/`.

```
python scripts/export_for_labeling.py
python scripts/export_for_labeling.py --count 20
python scripts/export_for_labeling.py --output labeling/exports/custom.md
```

Requires: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## import_labels.py

Reconciles Claude + ChatGPT label files from `labeling/Claude/` and `labeling/ChatGPT/`,
applies agreement logic, and updates Supabase `training_examples`.

- 6/6 field match → dual_labeled, human_reviewed=true
- 4–5/6 match → partial, agreed fields written
- <4/6 match → disagreement, flagged for human review

```
python scripts/import_labels.py --date 2026-05-25
```

Requires: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## synthetic_beta.py

Runs 25 deterministic hotel email scenarios through the full triage pipeline and
writes a JSON report to `docs/reports/synthetic_beta_report.json`.
Use to validate classification behavior before a release.

```
python scripts/synthetic_beta.py
```

---

## check_no_bundled_secrets.py

Security audit: scans source, installer, docs, and (if built) `dist/ReplyRight/`
for hardcoded secret values (JWT tokens, API key prefixes, etc.) and non-placeholder
assignments to known secret env var names.

Run in CI or before tagging a release:

```
python scripts/check_no_bundled_secrets.py
```

Exit code 0 = clean. Exit code 1 = potential secrets detected.

---

## apply_labels.py / apply_labels_batch2.py / apply_labels_batch3.py

Offline labeling utilities that were used to apply human-reviewed labels to historical
email batches and upsert them to Supabase.  These are **not** part of the running app.

They accept a JSON label file (usually output from `export_for_labeling.py` → human review)
and patch the corresponding `training_examples` rows in Supabase.

```
python scripts/apply_labels.py --labels labeling/Claude/2026-05-18-labels.json
```

Requires: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`

Note: For new labeling runs, prefer the `import_labels.py` workflow which handles
Claude + ChatGPT dual-label reconciliation automatically.
