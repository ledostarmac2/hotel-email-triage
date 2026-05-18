from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

class ErrorDisplayWidget(QWidget):
    """
    Native PySide6 implementation of the ErrorDisplay React component.
    """
    def __init__(self, error_message=None, support_email="support@example.com", parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(10)
        
        # Alert Icon (Using a basic unicode icon; can be replaced with QSvgWidget)
        self.icon_label = QLabel("⚠️")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 48px; color: #ef4444;")
        layout.addWidget(self.icon_label)
        
        # Title
        self.title_label = QLabel("There was an error")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title_label)
        
        # Description
        self.desc_label = QLabel()
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        
        if error_message:
            self.desc_label.setText(error_message)
        else:
            self.desc_label.setText(f"Please refresh or contact support at {support_email}\nif the error persists.")
            
        layout.addWidget(self.desc_label)

class NotLoggedInWidget(QWidget):
    """
    Native PySide6 implementation of the NotLoggedIn React component.
    """
    sign_in_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        
        self.msg_label = QLabel("You are not signed in 😞")
        self.msg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg_label.setStyleSheet("font-size: 18px; color: #374151;")
        layout.addWidget(self.msg_label)
        
        self.sign_in_button = QPushButton("Sign in")
        self.sign_in_button.clicked.connect(self.sign_in_requested.emit)
        self.sign_in_button.setStyleSheet("padding: 8px 16px; font-size: 14px;")
        layout.addWidget(self.sign_in_button)