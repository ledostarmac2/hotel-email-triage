from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

QUEUES = [
    ("inbox", "Inbox"),
    ("urgent", "Urgent"),
    ("vip", "VIP"),
    ("missing", "Missing Info"),
    ("admin", "Admin"),
]


class SidebarNav(QWidget):
    """Left navigation panel. Dark background, queue buttons, logout."""

    queue_changed = Signal(str)
    logout_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(200)
        self._buttons: dict[str, QPushButton] = {}
        self._active_queue = "inbox"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 12)
        layout.setSpacing(2)

        brand = QLabel("ReplyRight")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(brand)

        self._user_label = QLabel("")
        self._user_label.setObjectName("user-label")
        self._user_label.setWordWrap(True)
        layout.addWidget(self._user_label)

        layout.addSpacing(4)

        for queue_key, queue_label in QUEUES:
            btn = QPushButton(queue_label)
            btn.setObjectName("nav-btn")
            btn.setCheckable(False)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda checked, k=queue_key: self._select(k))
            self._buttons[queue_key] = btn
            layout.addWidget(btn)

        layout.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )

        logout_btn = QPushButton("Sign out")
        logout_btn.setObjectName("logout-btn")
        logout_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        logout_btn.setFixedHeight(36)
        logout_btn.clicked.connect(self.logout_requested)
        layout.addWidget(logout_btn)

        self._select("inbox")

    def _select(self, queue_key: str) -> None:
        for key, btn in self._buttons.items():
            btn.setProperty("active", "true" if key == queue_key else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._active_queue = queue_key
        self.queue_changed.emit(queue_key)

    def set_user(self, email: str, role: str) -> None:
        display = email
        if role and role != "user":
            display = f"{email}\n{role.title()}"
        self._user_label.setText(display)

        # Show Admin nav only if user is admin
        admin_btn = self._buttons.get("admin")
        if admin_btn:
            admin_btn.setVisible(role == "admin")

    def active_queue(self) -> str:
        return self._active_queue
