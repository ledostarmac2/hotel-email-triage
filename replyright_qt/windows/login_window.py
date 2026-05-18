from __future__ import annotations

# PySide6 is not yet in production requirements.
# This scaffold compiles and imports without PySide6 installed.
try:
    from PySide6.QtWidgets import (
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    _PYSIDE6 = True
except ImportError:
    QWidget = object  # type: ignore[assignment,misc]
    _PYSIDE6 = False


class LoginWindow(QWidget):  # type: ignore[misc]
    """Native login window — scaffold only, not yet wired to any service."""

    def __init__(self) -> None:
        if not _PYSIDE6:
            raise RuntimeError(
                "LoginWindow requires PySide6. "
                "Add PySide6 to requirements when the native slice is ready."
            )
        super().__init__()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)  # type: ignore[call-arg]
        layout.addWidget(QLabel("ReplyRight"))  # type: ignore[call-arg]
        self._email = QLineEdit()  # type: ignore[call-arg]
        self._email.setPlaceholderText("Email")
        layout.addWidget(self._email)
        self._password = QLineEdit()  # type: ignore[call-arg]
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)  # type: ignore[attr-defined]
        layout.addWidget(self._password)
        self._submit = QPushButton("Sign in")  # type: ignore[call-arg]
        layout.addWidget(self._submit)
        self._error = QLabel("")  # type: ignore[call-arg]
        layout.addWidget(self._error)

    def show_error(self, message: str) -> None:
        self._error.setText(message)  # type: ignore[attr-defined]

    def clear_error(self) -> None:
        self._error.setText("")  # type: ignore[attr-defined]
