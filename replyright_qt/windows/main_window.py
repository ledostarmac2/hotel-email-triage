from __future__ import annotations

# PySide6 is not yet in production requirements.
# This scaffold compiles and imports without PySide6 installed.
try:
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QWidget
    _PYSIDE6 = True
except ImportError:
    QMainWindow = object  # type: ignore[assignment,misc]
    _PYSIDE6 = False


class MainWindow(QMainWindow):  # type: ignore[misc]
    """Native main window — scaffold only, not yet wired to any service.

    Future layout:
      Left panel:  queue tabs (Inbox / Urgent / VIP / Missing Info)
      Centre:      conversation list (ConversationListWidget)
      Right panel: conversation detail pane
    """

    def __init__(self) -> None:
        if not _PYSIDE6:
            raise RuntimeError(
                "MainWindow requires PySide6. "
                "Add PySide6 to requirements when the native slice is ready."
            )
        super().__init__()
        self.setWindowTitle("ReplyRight")
        self.setMinimumSize(1024, 640)
        self._build_ui()

    def _build_ui(self) -> None:
        placeholder = QWidget()  # type: ignore[call-arg]
        layout = QHBoxLayout(placeholder)  # type: ignore[call-arg]
        layout.addWidget(QLabel("Inbox — native shell not yet implemented"))  # type: ignore[call-arg]
        self.setCentralWidget(placeholder)  # type: ignore[attr-defined]

    def set_user_info(self, email: str, role: str) -> None:
        self.setWindowTitle(f"ReplyRight — {email}")  # type: ignore[attr-defined]
