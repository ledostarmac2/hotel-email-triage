from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Signal, Qt

class LoginWindow(QDialog):
    """
    Native Login Screen.
    Eventually wired to AuthServiceProtocol for Supabase Auth.
    """
    login_successful = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ReplyRight - Login")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("Sign in to ReplyRight")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("Email Address")
        self.email_input.setStyleSheet("padding: 8px; font-size: 14px;")
        layout.addWidget(self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setStyleSheet("padding: 8px; font-size: 14px;")
        layout.addWidget(self.password_input)

        self.login_button = QPushButton("Login")
        self.login_button.clicked.connect(self._handle_login)
        self.login_button.setStyleSheet("padding: 10px; font-weight: bold; font-size: 14px;")
        layout.addWidget(self.login_button)

    def _handle_login(self):
        # TODO: Inject AuthServiceProtocol to validate via Supabase
        if self.email_input.text() and self.password_input.text():
            self.login_successful.emit()
        else:
            QMessageBox.warning(self, "Login Failed", "Please enter a valid email and password.")