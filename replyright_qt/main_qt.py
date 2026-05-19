from __future__ import annotations

import sys


def main() -> None:
    """Native PySide6 entry point for ReplyRight (v0.2.0 native shell)."""
    raise RuntimeError(
        "replyright_qt is a future native-ui scaffold and is not the default "
        "runnable entry point yet. Use run_desktop.py or the packaged "
        "ReplyRight.exe for v0.1.x."
    )


def _run_native_app() -> None:
    from PySide6.QtWidgets import QApplication

    from replyright_qt.adapters.auth_adapter import SupabaseAuthAdapter
    from replyright_qt.adapters.inbox_adapter import SqliteInboxAdapter
    from replyright_qt.windows.main_window import MainWindow

    # Load settings (triggers .env / bundled-secrets injection)
    from outlook_dashboard.config import get_settings
    from outlook_dashboard.database import initialize_database

    settings = get_settings()
    initialize_database(settings.database_path)

    auth_service = SupabaseAuthAdapter()
    inbox_service = SqliteInboxAdapter(settings.database_path)

    app = QApplication(sys.argv)
    app.setApplicationName("ReplyRight")
    app.setApplicationDisplayName("ReplyRight")

    window = MainWindow(auth_service=auth_service, inbox_service=inbox_service)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
