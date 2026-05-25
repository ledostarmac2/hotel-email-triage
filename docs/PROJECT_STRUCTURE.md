# Project Structure

Last updated: 2026-05-25

ReplyRight is expected to keep growing, so the repository root should stay boring and predictable.

## Root Contract

Root-level files should be limited to:

- Project entry points: `run_desktop.py`, `build_exe.ps1`, `setup.ps1`, `run.bat`, `run.sh`
- Dependency and tooling files: `requirements*.txt`, `pyproject.toml`, `pytest.ini`, `Dockerfile`, `docker-compose.yml`
- Primary human entry docs: `README.md`, `AGENTS.md`, `CHANGELOG.md`
- Agent coordination folder (active): `agent-workspace/`
- Coordination folders (historical/retired): `agent_comms/`, `docs/coordination/`
- Active source folders: `outlook_dashboard/`, `replyright_qt/`, `replyright_core/`, `replyright_kernel/`
- Active support folders: `.github/`, `docs/`, `installer/`, `labeling/`, `scripts/`, `tests/`, `build_support/`

## Active App Paths

- `outlook_dashboard/`: production FastAPI backend and currently served dashboard assets.
- `run_desktop.py`: production desktop launcher.
- `replyright_qt/`: native PySide6 migration/dev path.
- `replyright_core/`: future native UI shared core.
- `replyright_kernel/`: experimental/additive Semantic Kernel layer.

## Inactive Or Historical Paths

- `app/`: inactive Next.js scaffold. Keep intact unless Brian explicitly asks for a migration.
- `docs/archive/`: retired planning notes, old reviews, migration notes, and historical one-off documents.
- `docs/coordination/`: previous multi-agent coordination docs — historical/archived, not current agent instructions.
- `agent_comms/`: retired Claude↔Codex direct-message channel (2026-05-19 to 2026-05-25). Preserved as archive. Use `agent-workspace/AGENT_MESSAGES.md` instead.
- `.external/`: ignored local holding area for dropped source bundles or external apps, such as the original KYC Auto folder and historical reference repos. Files here are preserved locally but not committed.

## Generated Or Local-Only Paths

These should not be committed:

- `data/`
- `build/`
- `dist/`
- `installer/output/`
- `.vendor/`
- `.venv/`
- `.build-*`
- `.pytest_cache/`
- `__pycache__/`
- local `.env` files

## Cleanup Policy

- Archive historical docs under `docs/archive/` instead of leaving them at root.
- Keep generated EXEs and installers out of git.
- Keep dropped third-party or standalone app folders under ignored `.external/` unless their code is intentionally integrated into active source.
- Prefer adding a short README or docs note before introducing a new top-level folder.
