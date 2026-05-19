from __future__ import annotations

import html
import textwrap

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker


def _strip_html(text: str) -> str:
    """Very lightweight HTML stripping for email body preview."""
    import re
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html.unescape(text).strip()


def _urgency_label(priority: int | str | None) -> str:
    try:
        p = int(priority or 0)
    except (ValueError, TypeError):
        return "Unknown"
    return {1: "1 – Low", 2: "2 – Routine", 3: "3 – Moderate", 4: "4 – High", 5: "5 – Critical"}.get(p, str(p))


class _Divider(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.HLine)
        self.setStyleSheet("color: #e2e5ee;")


class ConversationDetailWidget(QWidget):
    """Right pane: full email thread + AI analysis + feedback form."""

    feedback_submitted = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.setObjectName("detail-panel")
        self._client = client
        self._worker: ApiWorker | None = None
        self._analyze_worker: ApiWorker | None = None
        self._feedback_worker: ApiWorker | None = None
        self._current_email_id: str = ""
        self._build_ui()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Placeholder shown when nothing is selected
        self._placeholder = QLabel("Select an email to view it.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #a0aec0; font-size: 14px;")

        # Scroll area that holds the actual content
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.hide()

        content = QWidget()
        content.setObjectName("detail-panel")
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(24, 20, 24, 24)
        self._content_layout.setSpacing(16)
        self._scroll.setWidget(content)

        root.addWidget(self._placeholder)
        root.addWidget(self._scroll)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_email(self, email_id: str) -> None:
        if not email_id:
            return
        self._current_email_id = email_id
        self._clear_content()

        loading = QLabel("Loading…")
        loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading.setStyleSheet("color: #a0aec0;")
        self._content_layout.addWidget(loading)

        self._placeholder.hide()
        self._scroll.show()

        self._worker = ApiWorker(self._client.get_email_detail, email_id)
        self._worker.success.connect(self._on_detail_loaded)
        self._worker.failure.connect(self._on_detail_error)
        self._worker.start()

    def clear(self) -> None:
        self._clear_content()
        self._scroll.hide()
        self._placeholder.show()
        self._current_email_id = ""

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_detail_loaded(self, data: dict) -> None:
        self._clear_content()
        self._render(data)

    def _on_detail_error(self, message: str) -> None:
        self._clear_content()
        err = QLabel(f"Failed to load email:\n{message}")
        err.setStyleSheet("color: #e53e3e;")
        err.setWordWrap(True)
        self._content_layout.addWidget(err)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self, data: dict) -> None:
        email = data if "id" in data else data.get("email", data)
        messages = data.get("thread", []) or data.get("messages", [])
        analysis = email.get("analysis") or {}

        # Header
        subject = QLabel(email.get("subject", "(no subject)"))
        subject.setStyleSheet("font-size: 16px; font-weight: bold;")
        subject.setWordWrap(True)
        self._content_layout.addWidget(subject)

        sender_row = QHBoxLayout()
        sender_lbl = QLabel(
            f"<b>{html.escape(email.get('sender_name') or email.get('sender_email',''))}</b>"
            f" &lt;{html.escape(email.get('sender_email',''))}&gt;"
        )
        sender_lbl.setTextFormat(Qt.TextFormat.RichText)
        sender_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        time_lbl = QLabel(email.get("received_datetime", "")[:16].replace("T", " "))
        time_lbl.setStyleSheet("color: #718096; font-size: 12px;")

        sender_row.addWidget(sender_lbl)
        sender_row.addWidget(time_lbl)
        self._content_layout.addLayout(sender_row)

        # Status row
        status_row = QHBoxLayout()
        status = email.get("status", "")
        status_badge = QLabel(status.replace("_", " ").title() if status else "—")
        status_badge.setObjectName("badge-status")
        status_badge.setFixedHeight(22)

        self._status_combo = QComboBox()
        for s in ("new", "in_progress", "resolved", "escalated"):
            self._status_combo.addItem(s.replace("_", " ").title(), s)
        idx = self._status_combo.findData(status)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)

        update_status_btn = QPushButton("Update status")
        update_status_btn.setObjectName("secondary-btn")
        update_status_btn.setFixedHeight(26)
        update_status_btn.clicked.connect(self._on_update_status)

        status_row.addWidget(QLabel("Status:"))
        status_row.addWidget(self._status_combo)
        status_row.addWidget(update_status_btn)
        status_row.addStretch()
        self._content_layout.addLayout(status_row)

        self._content_layout.addWidget(_Divider())

        # AI Analysis section
        if analysis:
            self._render_analysis(analysis)
            self._content_layout.addWidget(_Divider())

        # Email thread
        thread_label = QLabel("Email thread")
        thread_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a5568;")
        self._content_layout.addWidget(thread_label)

        thread_items = messages if messages else [email]
        for msg in thread_items:
            self._render_message(msg)

        # Feedback section
        self._content_layout.addWidget(_Divider())
        self._render_feedback_form()

        # Analyze button (if no analysis yet)
        if not analysis:
            analyze_btn = QPushButton("Run AI analysis")
            analyze_btn.setObjectName("primary-btn")
            analyze_btn.clicked.connect(self._on_analyze)
            self._content_layout.addWidget(analyze_btn)

        self._content_layout.addStretch()

    def _render_analysis(self, analysis: dict) -> None:
        header = QLabel("AI Analysis")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #4a5568;")
        self._content_layout.addWidget(header)

        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(16)

        priority = analysis.get("priority_level") or analysis.get("urgency")
        try:
            p = int(priority or 0)
        except (ValueError, TypeError):
            p = 0

        urgency_badge = QLabel(_urgency_label(priority))
        urgency_badge.setObjectName(f"badge-urgency-{min(max(p, 1), 5)}")
        urgency_badge.setFixedHeight(22)

        category_lbl = QLabel(
            (analysis.get("category") or "—").replace("_", " ").title()
        )
        category_lbl.setStyleSheet("color: #4a5568; font-size: 12px;")

        sentiment_lbl = QLabel(
            f"Sentiment: {analysis.get('guest_sentiment', '—').replace('_', ' ').title()}"
        )
        sentiment_lbl.setStyleSheet("color: #4a5568; font-size: 12px;")

        owner_lbl = QLabel(
            f"Owner: {analysis.get('recommended_department_owner', '—').replace('_', ' ').title()}"
        )
        owner_lbl.setStyleSheet("color: #4a5568; font-size: 12px;")

        grid_layout.addWidget(urgency_badge)
        grid_layout.addWidget(category_lbl)
        grid_layout.addWidget(sentiment_lbl)
        grid_layout.addWidget(owner_lbl)
        grid_layout.addStretch()
        self._content_layout.addWidget(grid)

        summary = analysis.get("ai_summary") or analysis.get("summary", "")
        if summary:
            summary_lbl = QLabel(f"<i>{html.escape(summary)}</i>")
            summary_lbl.setTextFormat(Qt.TextFormat.RichText)
            summary_lbl.setWordWrap(True)
            summary_lbl.setStyleSheet("color: #4a5568; font-size: 13px; padding: 4px 0;")
            self._content_layout.addWidget(summary_lbl)

        risk_flags = analysis.get("risk_flags", [])
        if risk_flags:
            if isinstance(risk_flags, str):
                risk_flags = [risk_flags]
            flags_text = "  ⚠  " + "  ·  ".join(risk_flags)
            flags_lbl = QLabel(flags_text)
            flags_lbl.setStyleSheet("color: #c05621; font-size: 12px;")
            flags_lbl.setWordWrap(True)
            self._content_layout.addWidget(flags_lbl)

    def _render_message(self, msg: dict) -> None:
        card = QWidget()
        card.setStyleSheet(
            "background-color: white; border: 1px solid #e2e5ee; border-radius: 6px;"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 12)
        card_layout.setSpacing(6)

        sender_row = QHBoxLayout()
        sender = QLabel(f"<b>{html.escape(msg.get('sender_name') or msg.get('sender_email',''))}</b>")
        sender.setTextFormat(Qt.TextFormat.RichText)
        ts = QLabel(msg.get("received_datetime", "")[:16].replace("T", " "))
        ts.setStyleSheet("color: #718096; font-size: 11px;")
        sender_row.addWidget(sender)
        sender_row.addStretch()
        sender_row.addWidget(ts)

        body_raw = msg.get("body") or msg.get("body_preview") or ""
        body_clean = _strip_html(body_raw) if "<" in body_raw else body_raw
        body_clean = textwrap.shorten(body_clean, width=2000, placeholder="… [truncated]")

        body = QTextBrowser()
        body.setPlainText(body_clean)
        body.setMinimumHeight(80)
        body.setMaximumHeight(300)
        body.setStyleSheet("border: none; background: transparent; font-size: 13px;")

        card_layout.addLayout(sender_row)
        card_layout.addWidget(body)
        self._content_layout.addWidget(card)

    def _render_feedback_form(self) -> None:
        header = QLabel("Correct triage")
        header.setStyleSheet("font-size: 13px; font-weight: bold; color: #4a5568;")
        self._content_layout.addWidget(header)

        row = QHBoxLayout()

        self._fb_urgency = QComboBox()
        self._fb_urgency.addItem("Urgency…", "")
        for val, label in [("1", "1 – Low"), ("2", "2 – Routine"), ("3", "3 – Moderate"), ("4", "4 – High"), ("5", "5 – Critical")]:
            self._fb_urgency.addItem(label, val)

        self._fb_category = QComboBox()
        self._fb_category.addItem("Category…", "")
        for cat in ("reservation", "complaint", "vip", "maintenance", "billing", "general"):
            self._fb_category.addItem(cat.replace("_", " ").title(), cat)

        submit_fb = QPushButton("Submit feedback")
        submit_fb.setObjectName("secondary-btn")
        submit_fb.setFixedHeight(28)
        submit_fb.clicked.connect(self._on_submit_feedback)

        row.addWidget(self._fb_urgency)
        row.addWidget(self._fb_category)
        row.addWidget(submit_fb)
        row.addStretch()
        self._content_layout.addLayout(row)

        self._fb_status = QLabel("")
        self._fb_status.setStyleSheet("font-size: 12px; color: #38a169;")
        self._content_layout.addWidget(self._fb_status)

    # ── Action handlers ────────────────────────────────────────────────────────

    def _on_update_status(self) -> None:
        if not self._current_email_id:
            return
        status = self._status_combo.currentData()
        self._worker = ApiWorker(self._client.update_email_status, self._current_email_id, status)
        self._worker.success.connect(lambda _: None)
        self._worker.failure.connect(lambda msg: None)
        self._worker.start()

    def _on_analyze(self) -> None:
        if not self._current_email_id:
            return
        self._analyze_worker = ApiWorker(self._client.analyze_email, self._current_email_id)
        self._analyze_worker.success.connect(lambda _: self.load_email(self._current_email_id))
        self._analyze_worker.failure.connect(lambda msg: None)
        self._analyze_worker.start()

    def _on_submit_feedback(self) -> None:
        if not self._current_email_id:
            return
        payload: dict = {}
        urgency = self._fb_urgency.currentData()
        if urgency:
            payload["corrected_urgency"] = int(urgency)
        category = self._fb_category.currentData()
        if category:
            payload["corrected_category"] = category
        if not payload:
            return
        self._feedback_worker = ApiWorker(
            self._client.submit_feedback, self._current_email_id, payload
        )
        self._feedback_worker.success.connect(lambda _: self._fb_status.setText("Feedback saved."))
        self._feedback_worker.failure.connect(lambda msg: self._fb_status.setText(f"Error: {msg}"))
        self._feedback_worker.start()
        self.feedback_submitted.emit()
