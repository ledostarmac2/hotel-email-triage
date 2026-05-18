# Core Adapters

Adapters should isolate external systems from the future native UI:

- SQLite/local repository adapter
- Outlook COM read-only adapter
- Supabase Auth and training adapter
- Optional AI provider adapter
- GitHub release/update adapter

Adapters must preserve ReplyRight's read-only Outlook posture and privacy rules.
