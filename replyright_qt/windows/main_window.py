from __future__ import annotations

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QSplitter,
        QStackedWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - scaffold import guard
    Qt = None

    class _MissingQtBase:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("PySide6 is required to use the native ReplyRight scaffold.")

    QMainWindow = _MissingQtBase
    QWidget = _MissingQtBase
    QHBoxLayout = QLabel = QPushButton = QSplitter = QStackedWidget = QTextEdit = QVBoxLayout = _MissingQtBase

from replyright_core.models.email_models import Conversation, ConversationDetail
from replyright_core.models.user_models import Session
from replyright_qt.widgets.conversation_list import ConversationListWidget
from replyright_qt.widgets.error_display import NotLoggedInWidget
from replyright_qt.windows.login_window import LoginWindow
from replyright_qt.workers import (
    ConversationDetailWorker,
    InboxWorker,
    _run_in_thread,
)


class MainWindow(QMainWindow):
    """Primary native shell — replaces the HTML/CSS/pywebview frontend."""

    def __init__(self, auth_service=None, inbox_service=None) -> None:
        super().__init__()
        self._auth = auth_service
        self._inbox = inbox_service
        self._session: Session | None = None
        self._conversations: list[Conversation] = []
        self._threads: list = []

        self.setWindowTitle("ReplyRight — Inbox")
        self.resize(1280, 800)

        self._stacked = QStackedWidget()
        self.setCentralWidget(self._stacked)

        # Page 0: not-logged-in
        self._not_logged_in = NotLoggedInWidget()
        self._not_logged_in.sign_in_requested.connect(self._show_login_window)
        self._stacked.addWidget(self._not_logged_in)

        # Page 1: inbox
        self._inbox_page = QWidget()
        self._setup_inbox_ui()
        self._stacked.addWidget(self._inbox_page)

        self._stacked.setCurrentWidget(self._not_logged_in)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_inbox_ui(self) -> None:
        root = QVBoxLayout(self._inbox_page)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        # Top bar
        top_bar = QHBoxLayout()
        header = QLabel("Inbox Queue")
        header.setStyleSheet("font-size: 22px; font-weight: bold;")
        top_bar.addWidget(header)
        top_bar.addStretch()

        self._user_label = QLabel("")
        self._user_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        top_bar.addWidget(self._user_label)

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setStyleSheet("padding: 5px 14px;")
        self._refresh_button.clicked.connect(self._refresh_inbox)
        top_bar.addWidget(self._refresh_button)

        self._logout_button = QPushButton("Sign Out")
        self._logout_button.setStyleSheet("padding: 5px 14px; color: #ef4444;")
        self._logout_button.clicked.connect(self._handle_logout)
        top_bar.addWidget(self._logout_button)

        root.addLayout(top_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        root.addWidget(self._status_label)

        # Splitter: conversation list (left) | detail (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        self._conv_list = ConversationListWidget()
        self._conv_list.conversation_selected.connect(self._on_conversation_selected)
        splitter.addWidget(self._conv_list)

        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(8, 0, 0, 0)

        self._detail_subject = QLabel("Select a conversation")
        self._detail_subject.setStyleSheet("font-size: 16px; font-weight: bold;")
        self._detail_subject.setWordWrap(True)
        detail_layout.addWidget(self._detail_subject)

        self._detail_meta = QLabel("")
        self._detail_meta.setStyleSheet("font-size: 12px; color: #6b7280;")
        self._detail_meta.setWordWrap(True)
        detail_layout.addWidget(self._detail_meta)

        self._detail_triage = QLabel("")
        self._detail_triage.setStyleSheet(
            "font-size: 12px; background: #1e293b; color: #93c5fd;"
            " padding: 6px 10px; border-radius: 4px;"
        )
        self._detail_triage.setWordWrap(True)
        self._detail_triage.hide()
        detail_layout.addWidget(self._detail_triage)

        self._detail_summary = QLabel("")
        self._detail_summary.setStyleSheet(
            "font-size: 12px; background: #0f2a1e; color: #86efac;"
            " padding: 6px 10px; border-radius: 4px;"
        )
        self._detail_summary.setWordWrap(True)
        self._detail_summary.hide()
        detail_layout.addWidget(self._detail_summary)

        self._detail_body = QTextEdit()
        self._detail_body.setReadOnly(True)
        self._detail_body.setPlaceholderText("Email content will appear here…")
        detail_layout.addWidget(self._detail_body)

        self._mark_reviewed_button = QPushButton("Mark Reviewed")
        self._mark_reviewed_button.setStyleSheet("padding: 6px 14px;")
        self._mark_reviewed_button.clicked.connect(self._mark_current_reviewed)
        self._mark_reviewed_button.hide()
        detail_layout.addWidget(self._mark_reviewed_button)

        splitter.addWidget(detail_widget)
        splitter.setSizes([360, 880])

    # ------------------------------------------------------------------
    # Auth / login
    # ------------------------------------------------------------------

    def _show_login_window(self) -> None:
        dlg = LoginWindow(auth_service=self._auth, parent=self)
        dlg.login_successful.connect(self._on_login_successful)
        dlg.exec()

    def _on_login_successful(self, session: Session | None) -> None:
        self._session = session
        if session:
            self._user_label.setText(session.user.email)
        self._stacked.setCurrentWidget(self._inbox_page)
        self._refresh_inbox()

    def _handle_logout(self) -> None:
        if self._auth and self._session:
            try:
                self._auth.logout(self._session.access_token)
            except Exception:
                pass
        self._session = None
        self._conversations = []
        self._conv_list.clear()
        self._clear_detail()
        self._stacked.setCurrentWidget(self._not_logged_in)

    # ------------------------------------------------------------------
    # Inbox loading
    # ------------------------------------------------------------------

    def _refresh_inbox(self) -> None:
        if self._inbox is None:
            self._status_label.setText("No inbox service available.")
            return

        self._refresh_button.setEnabled(False)
        self._status_label.setText("Loading…")

        worker = InboxWorker(self._inbox, queue="inbox")
        worker.finished.connect(self._on_inbox_loaded)
        worker.error.connect(self._on_inbox_error)
        _run_in_thread(worker, self._threads)

    def _on_inbox_loaded(self, conversations: list[Conversation]) -> None:
        self._refresh_button.setEnabled(True)
        self._conversations = conversations
        self._conv_list.populate(conversations)
        count = len(conversations)
        self._status_label.setText(
            f"{count} conversation{'s' if count != 1 else ''}" if count else "Inbox is empty."
        )

    def _on_inbox_error(self, message: str) -> None:
        self._refresh_button.setEnabled(True)
        self._status_label.setText(f"Error loading inbox: {message}")

    # ------------------------------------------------------------------
    # Conversation detail
    # ------------------------------------------------------------------

    def _on_conversation_selected(self, conversation_id: str) -> None:
        if not conversation_id or self._inbox is None:
            return
        self._detail_subject.setText("Loading…")
        self._detail_meta.setText("")
        self._detail_triage.hide()
        self._detail_summary.hide()
        self._detail_body.clear()
        self._mark_reviewed_button.hide()

        worker = ConversationDetailWorker(self._inbox, conversation_id)
        worker.finished.connect(self._on_detail_loaded)
        worker.error.connect(self._on_detail_error)
        _run_in_thread(worker, self._threads)

    def _on_detail_loaded(self, detail: ConversationDetail | None) -> None:
        if detail is None:
            self._detail_subject.setText("Conversation not found.")
            return

        conv = detail.conversation
        self._detail_subject.setText(conv.subject)
        meta_parts = [
            f"From: {conv.latest_sender_email}",
            f"Received: {conv.latest_received_at}",
        ]
        if conv.message_count > 1:
            meta_parts.append(f"{conv.message_count} messages in thread")
        meta_parts.append(f"Status: {conv.status}")
        self._detail_meta.setText("  ·  ".join(meta_parts))

        if conv.triage:
            t = conv.triage
            flags = ", ".join(t.risk_flags) if t.risk_flags else "—"
            self._detail_triage.setText(
                f"Category: {t.category}  ·  Urgency: {t.urgency}  ·  "
                f"Sentiment: {t.sentiment}  ·  Risk: {flags}"
            )
            self._detail_triage.show()
        else:
            self._detail_triage.hide()

        if detail.thread_summary:
            self._detail_summary.setText(f"AI Summary: {detail.thread_summary}")
            self._detail_summary.show()
        else:
            self._detail_summary.hide()

        # Render the message thread
        body_lines: list[str] = []
        for i, msg in enumerate(detail.messages, 1):
            sep = "─" * 60
            body_lines.append(
                f"{sep}\nMessage {i} of {len(detail.messages)}\n"
                f"From: {msg.sender_name} <{msg.sender_email}>\n"
                f"Received: {msg.received_at}\n\n"
                f"{msg.body_preview or '(no preview available)'}"
            )

        if conv.triage and conv.triage.ai_draft:
            body_lines.append(
                f"\n{'─' * 60}\n[AI Draft Reply]\n\n{conv.triage.ai_draft}"
            )

        self._detail_body.setPlainText("\n\n".join(body_lines))

        self._mark_reviewed_button.setProperty("conversation_id", conv.conversation_id)
        self._mark_reviewed_button.setVisible(conv.status == "New")

    def _on_detail_error(self, message: str) -> None:
        self._detail_subject.setText("Failed to load conversation.")
        self._detail_meta.setText(message)

    def _clear_detail(self) -> None:
        self._detail_subject.setText("Select a conversation")
        self._detail_meta.setText("")
        self._detail_triage.hide()
        self._detail_summary.hide()
        self._detail_body.clear()
        self._mark_reviewed_button.hide()

    # ------------------------------------------------------------------
    # Mark reviewed
    # ------------------------------------------------------------------

    def _mark_current_reviewed(self) -> None:
        conversation_id = self._mark_reviewed_button.property("conversation_id")
        if not conversation_id or self._inbox is None:
            return
        reviewer = self._session.user.email if self._session else ""
        try:
            self._inbox.mark_reviewed(conversation_id, reviewer)
        except Exception as exc:
            self._status_label.setText(f"Could not mark reviewed: {exc}")
            return
        self._mark_reviewed_button.hide()
        self._status_label.setText("Marked as reviewed.")
        self._refresh_inbox()
