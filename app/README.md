# ReplyRight App

Initial production app scaffold for the ReplyRight shared mailbox triage system.

## Setup

```bash
npm install
cp .env.example .env
npx prisma generate
npm run dev
```

Local dashboard:

```text
http://localhost:3000
```

## Important

The app is scaffolded for Microsoft Graph application permissions against a shared mailbox. Keep `TRIAGE_DRY_RUN=true` until Graph reads, redaction, classification, and category mappings have been verified.
