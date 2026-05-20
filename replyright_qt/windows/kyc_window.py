from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow

from replyright_qt.api_client import ApiClient
from replyright_qt.widgets.kyc_panel import KycPanel


class KycWindow(QMainWindow):
    """Standalone KYC Inspection Reminder window.

    Opens as an independent floating window so it can stay visible alongside
    the main ReplyRight window — matching the original program's behavior.
    """

    def __init__(self, client: ApiClient) -> None:
        super().__init__(parent=None)
        self.setWindowTitle("KYC Inspection Reminder")
        self.setMinimumSize(680, 600)
        self.resize(780, 740)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )

        self._panel = KycPanel(client)
        self.setCentralWidget(self._panel)

    def activate(self) -> None:
        """Show, bring to front, and refresh KYC data."""
        self._panel.activate()
        if not self.isVisible():
            self.show()
        self.raise_()
        self.activateWindow()
