# Dependency Evaluation

Last updated: 2026-05-29

This is a practical risk review for optional local-intelligence and privacy
tooling. ReplyRight remains local-first, read-only against Outlook, and usable
without paid AI services.

| Package | Purpose | License | Maintenance | Install / Build Risk | PyInstaller Risk | Benefit | Recommendation |
|---|---|---|---|---|---|---|---|
| `rapidfuzz` | Local fuzzy subject/follow-up scoring | MIT | Active; current Windows wheels available | Low; pinned wheel import smoke passed on Windows | Low to moderate because it ships compiled extensions, but wheels are available | Better explainable duplicate/follow-up scoring without AI | Integrate now as optional helper with deterministic fallback |
| `presidio-analyzer` / `presidio-anonymizer` | Optional second-pass PII detection | MIT | Active Microsoft project | Medium to high; useful text analysis typically requires an NLP engine such as spaCy, transformers, or stanza | High until model packaging is proven | Strong general PII detector, especially names/entities | Defer as required dependency; add disabled optional hook only |
| `small-text` | Active-learning candidate selection | MIT | Maintained; sklearn path exists | Medium; adds an abstraction layer and optional ML integrations not needed now | Medium because packaging must cover active-learning internals | Useful for larger annotation loops | Defer; use deterministic local ranking from sanitized examples |
| PySide6 theme packages (`qt-material`, `QDarkStyle`, `pyqtdarktheme`) | Native UI styling | MIT/BSD depending on package | Mixed; several maintained options | Medium; can override existing object-name styling and brand details | Medium; stylesheet/resource bundling needs validation | Faster generic visual polish | Defer; continue improving existing `replyright_qt/styles/theme.py` |
| `structlog` | Structured logging | MIT or Apache-2.0 | Mature and maintained | Low | Low | Rich structured logging API | Defer; stdlib helper is enough for scrubbed diagnostic events |

## Current Decision

Only `rapidfuzz==3.14.5` is added in this pass, after a local import/package
smoke check. All other candidates are documented deferrals. Presidio remains
an optional disabled hook and is not listed in `requirements.txt`.
