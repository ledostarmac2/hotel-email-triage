# ReplyRight

Read-only Outlook email intelligence dashboard for a luxury hotel shared inbox.

This version primarily reads classic Outlook for Windows through local read-only `pywin32` COM import, imports emails into local SQLite, summarizes and classifies them, identifies follow-up work, flags risk, and prepares suggested luxury-hospitality reply drafts for human review. Microsoft Graph remains available as an optional read-only path when tenant credentials are configured.

It does not send, delete, archive, move, mark read, categorize, or otherwise modify Outlook messages.

## Current App

The Python/FastAPI app lives in:

```text
outlook_dashboard/
```

It serves a simple browser dashboard from FastAPI, so there is no separate React build required for this first executable-friendly version.

## Features

- Direct read-only classic Outlook import from `NYCWA_Reservations > Inbox`
- Optional Microsoft Graph OAuth sign-in with Microsoft Entra ID
- Personal mailbox mode: `GET /me/messages`
- Shared mailbox mode: `GET /users/{SHARED_MAILBOX_EMAIL}/mailFolders/Inbox/messages`
- Graph field selection limited to:
  - `id`
  - `subject`
  - `sender`
  - `from`
  - `receivedDateTime`
  - `bodyPreview`
  - `body`
  - `conversationId`
  - `importance`
  - `hasAttachments`
- SQLite email storage with duplicate prevention by Graph message ID
- Local triage summary, category, urgency score 1-5, sentiment, next steps, missing information, risk flags, and owner
- Conversation-level adaptive feedback for urgency and labeling corrections
- Dashboard filters for category, status, and risk flag
- On-demand AI recommended response modal for the selected email only
- Local-only workflow status: `New`, `Reviewed`, `Drafted`, `Completed`, `Escalated`

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Update `.env` with your Microsoft and OpenAI values:

```env
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT_ID=
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/callback
SHARED_MAILBOX_EMAIL=
OPENAI_API_KEY=
```

Run the app:

```powershell
python run_desktop.py
```

Dashboard:

```text
http://127.0.0.1:8000
```

The app does not seed mock/demo messages in the active dashboard path. Refresh Inbox treats Outlook as the source of truth and removes local email rows not present in the current Outlook import.

## Microsoft Entra App Registration

1. Open Microsoft Entra admin center.
2. Go to `Identity` -> `Applications` -> `App registrations`.
3. Create a new app registration.
4. Set the redirect URI as:

```text
http://localhost:8000/auth/callback
```

5. Copy the application client ID into `MICROSOFT_CLIENT_ID`.
6. Copy the directory tenant ID into `MICROSOFT_TENANT_ID`.
7. Create a client secret under `Certificates & secrets`.
8. Copy the secret value into `MICROSOFT_CLIENT_SECRET`.
9. Add Microsoft Graph delegated permissions:
   - `Mail.Read`
   - `Mail.Read.Shared`
10. Grant admin consent if your tenant requires it.

For shared mailbox sync, the signed-in Microsoft 365 user must have access to the shared mailbox configured in `SHARED_MAILBOX_EMAIL`.

## Outlook Sync

The primary desktop workflow uses classic Outlook for Windows through direct read-only `pywin32` COM import. The local VBA macro remains a fallback only if the direct import path is unavailable:

```text
outlook_dashboard/static/outlook_refresh_macro.bas
```

Paste that macro into Outlook VBA with the name:

```text
ExportNYCWAReservationsInboxOnly
```

The dashboard `Refresh Inbox` button reads only:

```text
NYCWA_Reservations > Inbox
```

It saves local `.msg` copies under `data/outlook_exports`, imports the inbox data to local SQLite, deletes stale local rows that are no longer in Outlook, and performs fast local triage without calling OpenAI.

Microsoft Graph sync is still available if credentials are configured. Use `Connect Microsoft` first, then call the Graph sync route:

The sync route is:

```text
POST /api/sync/outlook?mode=shared&top=25&analyze=true
```

Personal mailbox mode is also available:

```text
POST /api/sync/outlook?mode=personal&top=25&analyze=true
```

Both modes are read-only and use Graph `GET` requests only.

## AI Processing

Inbox refresh and queue ranking use deterministic local triage for speed. If `OPENAI_API_KEY` is configured, OpenAI is called only when the user clicks `AI Response` for a selected email. If the key is missing or the API call fails, the app falls back to a deterministic local hotel-triage draft so the dashboard remains usable.

Sensitive payment-like text is redacted before AI calls:

- Luhn-valid card numbers
- CVV/security code phrases
- Expiration date phrases

## API Routes

```text
GET  /
GET  /api/health
GET  /api/config
GET  /api/taxonomy
GET  /auth/login?mode=shared
GET  /auth/callback
POST /api/outlook-desktop/export-inbox
POST /api/outlook-desktop/import-json
POST /api/sync/outlook?mode=shared&top=25&analyze=true
POST /api/ai/process-pending?limit=25
GET  /api/emails
GET  /api/emails/{email_id}
POST /api/emails/{email_id}/analyze
POST /api/emails/{email_id}/feedback
PATCH /api/emails/{email_id}/status
```

`PATCH /api/emails/{email_id}/status` updates only the local SQLite review status. It does not modify Outlook.

## Build The Windows EXE

From the repository root:

```powershell
.\build_exe.ps1
```

Output:

```text
dist\ReplyRight.exe
```

The executable starts the local FastAPI server inside a standalone desktop window. It does not open the default browser.

## Notes Before Live Use

- Keep this version read-only until the mailbox workflow is reviewed.
- Do not add send, delete, archive, move, category, or mark-read actions until a separate approval flow is designed.
- Use a dedicated Entra app registration for the hotel shared inbox workflow.
- Store `.env` securely and do not commit it.
- Review AI drafts before using them with guests or colleagues.
