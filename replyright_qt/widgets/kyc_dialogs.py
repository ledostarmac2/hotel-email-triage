from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class KycNotificationDialog(QDialog):
    """Non-blocking notification shown when a KYC run completes or fails.

    In strict mode (strict=True) the dialog cannot be closed via the window
    chrome — the user must click Acknowledge or Snooze.
    """

    acknowledged = Signal()
    snoozed = Signal()

    def __init__(
        self,
        title: str,
        message: str,
        success: bool = True,
        strict: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._strict = strict
        self.setWindowTitle(title)
        self.setMinimumWidth(380)

        if strict:
            self.setWindowFlags(
                self.windowFlags()
                & ~Qt.WindowType.WindowCloseButtonHint
            )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        icon_text = "KYC Inspection" if success else "KYC Inspection Failed"
        header = QLabel(icon_text)
        color = "#38a169" if success else "#e53e3e"
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {color};")
        layout.addWidget(header)

        body = QLabel(message)
        body.setWordWrap(True)
        layout.addWidget(body)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        snooze_btn = QPushButton("Snooze 5 min")
        snooze_btn.setObjectName("secondary-btn")
        snooze_btn.clicked.connect(self._on_snooze)
        btn_row.addWidget(snooze_btn)

        ack_btn = QPushButton("Acknowledge")
        ack_btn.setObjectName("primary-btn")
        ack_btn.clicked.connect(self._on_acknowledge)
        btn_row.addWidget(ack_btn)

        layout.addLayout(btn_row)

    def _on_acknowledge(self) -> None:
        self.acknowledged.emit()
        self.accept()

    def _on_snooze(self) -> None:
        self.snoozed.emit()
        self.accept()

    def closeEvent(self, event) -> None:
        if self._strict:
            event.ignore()
        else:
            super().closeEvent(event)
