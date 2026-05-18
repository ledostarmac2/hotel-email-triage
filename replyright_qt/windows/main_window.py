from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QTextEdit, QPushButton, QSplitter, QStackedWidget
)
from PySide6.QtCore import Qt

from replyright_qt.widgets.conversation_list import ConversationListWidget
from replyright_qt.widgets.error_display import NotLoggedInWidget
from replyright_qt.windows.login_window import LoginWindow

class MainWindow(QMainWindow):
    """
    Primary Native Shell.
    Replaces the HTML/CSS Next.js scaffold.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ReplyRight - Inbox")
        self.resize(1280, 800)

        # Use a stacked widget to switch between "Logged Out" and "Inbox" views
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # 1. Logged Out View
        self.not_logged_in_widget = NotLoggedInWidget()
        self.not_logged_in_widget.sign_in_requested.connect(self._show_login_window)
        self.stacked_widget.addWidget(self.not_logged_in_widget)
        
        # 2. Main Inbox View
        self.inbox_widget = QWidget()
        self._setup_inbox_ui()
        self.stacked_widget.addWidget(self.inbox_widget)
        
        # Default to not logged in
        self.stacked_widget.setCurrentWidget(self.not_logged_in_widget)

    def _setup_inbox_ui(self):
        main_layout = QVBoxLayout(self.inbox_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top Toolbar
        top_bar = QHBoxLayout()
        header = QLabel("Inbox Queue")
        header.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.refresh_button = QPushButton("Refresh Inbox")
        self.refresh_button.setStyleSheet("padding: 5px 15px;")
        self.refresh_button.clicked.connect(self._refresh_inbox)
        
        top_bar.addWidget(header)
        top_bar.addStretch()
        top_bar.addWidget(self.refresh_button)
        main_layout.addLayout(top_bar)

        # Splitter for Queue (Left) and Detail (Right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel: Conversation List
        self.conversation_list = ConversationListWidget()
        self.conversation_list.add_scaffold_items([
            "[Urgency 5] High Priority VIP Request",
            "[Urgency 3] Routine Booking Inquiry",
            "[Urgency 1] Spam/Newsletter"
        ])
        self.conversation_list.conversation_selected.connect(self._on_conversation_selected)
        splitter.addWidget(self.conversation_list)

        # Right panel: Conversation Detail
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_header = QLabel("Select a conversation to view details")
        self.detail_header.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        detail_layout.addWidget(self.detail_header)

        self.email_body = QTextEdit()
        self.email_body.setReadOnly(True)
        self.email_body.setPlaceholderText("Email content will appear here...")
        detail_layout.addWidget(self.email_body)

        splitter.addWidget(detail_widget)
        splitter.setSizes([350, 850])

    def _show_login_window(self):
        """Shows the login dialog and transitions to inbox on success."""
        self.login_window = LoginWindow(self)
        self.login_window.login_successful.connect(self._on_login_successful)
        self.login_window.exec()

    def _on_login_successful(self):
        self.login_window.accept()
        self.stacked_widget.setCurrentWidget(self.inbox_widget)

    def _refresh_inbox(self):
        """Placeholder for refreshing the inbox queue."""
        # TODO: Implement actual inbox refresh logic
        pass

    def _on_conversation_selected(self, conversation_text: str):
        """Updates the detail view when a conversation is selected."""
        self.detail_header.setText(conversation_text)
        self.email_body.setText(f"Details for {conversation_text}...\n\n(Simulated content)")