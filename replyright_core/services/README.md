# Core Services

Future service modules should expose UI-neutral Python APIs for:

- `auth_service`: login, logout, current user, first-run admin setup
- `inbox_service`: list queues, list conversations, load conversation detail
- `analysis_service`: run deterministic/local/AI-assisted analysis
- `feedback_service`: save corrections and rule-candidate signals
- `training_service`: run training export, train local classifier, inspect model health
- `diagnostics_service`: version, health, update status, platform capabilities

Keep implementations thin at first by delegating to existing `outlook_dashboard` modules.
