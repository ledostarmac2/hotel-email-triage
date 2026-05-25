from __future__ import annotations

import html
import json
import re
import textwrap

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from outlook_dashboard.taxonomy import CATEGORIES, CONTACT_TYPES, DEPARTMENT_OWNERS, STATUSES
from replyright_qt.api_client import ApiClient, ApiWorker

_ENGINE_DISPLAY = {
    "heuristic": "Heuristic rules",
    "local-classifier": "Local ML classifier",
    "openai": "OpenAI triage",
    "openai-refresh": "OpenAI refresh",
    "anthropic": "Claude AI (single-email)",
    "claude": "Claude AI (single-email)",
    "unknown": "Unknown",
}

_RECOMMENDED_ACTION_DISPLAY = {
    "reply_guest": "Reply to Guest",
    "loop_reservations": "Loop Reservations",
    "loop_front_office": "Loop Front Office",
    "loop_concierge": "Loop Concierge",
    "loop_housekeeping": "Loop Housekeeping",
    "loop_engineering": "Loop Engineering",
    "escalate_manager": "Escalate to Manager",
    "verify_payment_authorization": "Verify Payment Auth",
    "review_folio": "Review Folio",
    "check_reservation": "Check Reservation",
    "request_missing_information": "Request Info",
    "wait_for_guest": "Waiting on Guest",
    "wait_for_internal_team": "Waiting on Team",
    "no_action_likely": "No Action Likely",
}


def _strip_html(text: str) -> str:
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return html.unescape(text).strip()


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if not value:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [part.strip() for part in value.split(",") if part.strip()]
    return [value]


def _urgency_label(priority: int | str | None) -> str:
    try:
        p = int(priority or 0)
    except (ValueError, TypeError):
        return "Unknown"
    return {1: "1 Low", 2: "2 Routine", 3: "3 Moderate", 4: "4 High", 5: "5 Critical"}.get(p, str(p))


def _clean_address(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.startswith("/O=") or "/OU=" in text or "/CN=" in text:
        return ""
    return text if "@" in text else ""


def _sender_label(item: dict) -> str:
    name = str(item.get("sender_name") or "").strip()
    if name.startswith("/O=") or "/OU=" in name or "/CN=" in name:
        name = ""
    email_addr = _clean_address(item.get("sender_email"))
    if name and email_addr:
        return f"{name} <{email_addr}>"
    return name or email_addr or "Unknown sender"


class _Divider(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setFrameShape(QFrame.Shape.HLine)
        self.setObjectName("divider")


class ConversationDetailWidget(QWidget):
    """Right pane: conversation context, analysis, status, AI suggestion, and feedback."""

    feedback_submitted = Signal()
    status_changed = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.setObjectName("detail-panel")
        self._client = client
        self._worker: ApiWorker | None = None
        self._analyze_worker: ApiWorker | None = None
        self._feedback_worker: ApiWorker | None = None
        self._status_worker: ApiWorker | None = None
        self._workers: list[ApiWorker] = []
        self._current_email_id = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._placeholder = QLabel("Select a conversation to review.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #98a2b3; font-size: 15px;")

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.hide()

        content = QWidget()
        content.setObjectName("detail-panel")
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(26, 22, 26, 26)
        self._content_layout.setSpacing(16)
        self._scroll.setWidget(content)

        root.addWidget(self._placeholder)
        root.addWidget(self._scroll)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    child = item.layout().takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

    def load_email(self, email_id: str) -> None:
        if not email_id:
            return
        self._current_email_id = str(email_id)
        self._clear_content()
        self._placeholder.hide()
        self._scroll.show()
        self._content_layout.addWidget(self._muted("Loading conversation..."))

        self._worker = self._start_worker(
            self._client.get_email_detail,
            email_id,
            success=self._on_detail_loaded,
            failure=self._on_detail_error,
        )

    def clear(self) -> None:
        self._clear_content()
        self._scroll.hide()
        self._placeholder.show()
        self._current_email_id = ""

    def _on_detail_loaded(self, data: dict) -> None:
        self._clear_content()
        self._render(data)

    def _on_detail_error(self, message: str) -> None:
        self._clear_content()
        self._content_layout.addWidget(self._error(f"Failed to load conversation: {message}"))

    def _render(self, data: dict) -> None:
        email = data.get("email", data)
        messages = email.get("conversation_messages") or data.get("conversation_messages") or data.get("thread") or [email]

        header_row = QHBoxLayout()
        title = QLabel(email.get("subject") or "(no subject)")
        title.setObjectName("detail-title")
        title.setWordWrap(True)
        close_btn = QPushButton("x")
        close_btn.setObjectName("secondary-btn")
        close_btn.setFixedWidth(34)
        close_btn.clicked.connect(self.clear)
        header_row.addWidget(title, stretch=1)
        header_row.addWidget(close_btn)
        self._content_layout.addLayout(header_row)

        sender_row = QHBoxLayout()
        sender = QLabel(f"<b>{html.escape(_sender_label(email))}</b>")
        sender.setTextFormat(Qt.TextFormat.RichText)
        sender.setWordWrap(True)
        sender.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        received = QLabel((email.get("received_datetime") or "")[:16].replace("T", " "))
        received.setObjectName("muted-label")
        sender_row.addWidget(sender)
        sender_row.addWidget(received)
        self._content_layout.addLayout(sender_row)

        if email.get("needs_review"):
            self._render_needs_review_banner(email)
        self._render_status_row(email)
        self._content_layout.addWidget(_Divider())
        self._render_analysis(email)
        self._content_layout.addWidget(_Divider())
        self._render_thread(messages)
        self._content_layout.addWidget(_Divider())
        self._render_feedback_form(email)
        self._content_layout.addStretch()

    def _render_status_row(self, email: dict) -> None:
        row = QGridLayout()
        row.setHorizontalSpacing(10)
        row.setVerticalSpacing(8)
        self._status_combo = QComboBox()
        self._status_combo.setFixedHeight(30)
        self._status_combo.setMinimumWidth(116)
        current = email.get("status") or "New"
        legacy_statuses = {
            "new": "New",
            "in_progress": "Reviewed",
            "resolved": "Completed",
            "escalated": "Escalated",
        }
        current = legacy_statuses.get(str(current), current)
        for status in STATUSES:
            self._status_combo.addItem(status, status)
        idx = self._status_combo.findData(current)
        if idx >= 0:
            self._status_combo.setCurrentIndex(idx)

        self._status_btn = QPushButton("Update Status")
        self._status_btn.setObjectName("secondary-btn")
        self._status_btn.setFixedHeight(30)
        self._status_btn.setMinimumWidth(110)
        self._status_btn.clicked.connect(self._on_update_status)

        self._action_status = QLabel("")
        self._action_status.setObjectName("muted-label")

        self._owner_combo = QComboBox()
        self._owner_combo.setFixedHeight(30)
        self._owner_combo.setMinimumWidth(116)
        self._owner_combo.addItem("Owner", "")
        for owner in DEPARTMENT_OWNERS:
            self._owner_combo.addItem(owner, owner)
        current_owner = email.get("recommended_department_owner") or ""
        idx2 = self._owner_combo.findData(current_owner)
        if idx2 >= 0:
            self._owner_combo.setCurrentIndex(idx2)

        draft_btn = QPushButton("Draft Reply")
        draft_btn.setObjectName("primary-btn")
        draft_btn.setFixedHeight(30)
        draft_btn.setMinimumWidth(108)
        draft_btn.clicked.connect(self._on_analyze)

        more_btn = QPushButton("More")
        more_btn.setObjectName("secondary-btn")
        more_btn.setFixedHeight(30)

        row.addWidget(QLabel("Status"), 0, 0)
        row.addWidget(self._status_combo, 0, 1)
        row.addWidget(self._status_btn, 0, 2)
        row.addWidget(QLabel("Owner"), 0, 3)
        row.addWidget(self._owner_combo, 0, 4)
        row.addWidget(draft_btn, 1, 1)
        row.addWidget(more_btn, 1, 2)
        row.addWidget(self._action_status, 1, 3, 1, 2)
        row.setColumnStretch(5, 1)
        self._content_layout.addLayout(row)

    def _render_analysis(self, email: dict) -> None:
        hdr_row = QHBoxLayout()
        header = QLabel("Triage Summary")
        header.setObjectName("section-title")
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("link-btn")
        hdr_row.addWidget(header)
        hdr_row.addStretch()
        hdr_row.addWidget(edit_btn)
        self._content_layout.addLayout(hdr_row)

        priority = email.get("urgency_score") or email.get("priority_level")
        try:
            p = int(priority or 0)
        except (TypeError, ValueError):
            p = 0

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        self._add_metric(grid, 0, 0, "Urgency", _urgency_label(priority), f"badge-urgency-{min(max(p, 1), 5)}")
        self._add_metric(grid, 0, 1, "Owner", email.get("recommended_department_owner") or "Unassigned")
        self._add_metric(grid, 1, 0, "Category", email.get("category") or "Uncategorized")
        self._add_metric(grid, 1, 1, "Contact", email.get("contact_type") or "Unknown")
        self._add_metric(grid, 2, 0, "Sentiment", email.get("guest_sentiment") or "Unknown")
        confidence = email.get("confidence_score")
        confidence_text = f"{float(confidence):.0f}%" if isinstance(confidence, (int, float)) else "Not scored"
        self._add_metric(grid, 2, 1, "Confidence", confidence_text)
        engine = str(email.get("analysis_engine") or "unknown")
        engine_display = _ENGINE_DISPLAY.get(engine.lower(), engine.replace("-", " ").title())
        self._add_metric(grid, 3, 0, "Classification Source", engine_display)
        action_key = str(email.get("recommended_action") or "")
        action_display = _RECOMMENDED_ACTION_DISPLAY.get(action_key, action_key.replace("_", " ").title() or "—")
        self._add_metric(grid, 3, 1, "Recommended Action", action_display, "metric-action")
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self._content_layout.addLayout(grid)

        summary = email.get("ai_summary") or email.get("summary")
        if summary:
            summary_lbl = QLabel(html.escape(str(summary)))
            summary_lbl.setWordWrap(True)
            summary_lbl.setObjectName("summary-text")
            self._content_layout.addWidget(summary_lbl)

        self._render_risk_flags(_as_list(email.get("risk_flags")))
        self._render_chip_list("Missing information", _as_list(email.get("missing_information")))
        self._render_steps(_as_list(email.get("internal_next_steps")))

        draft = email.get("suggested_reply_draft")
        if draft:
            draft_box = QTextBrowser()
            draft_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            draft_box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            draft_box.setPlainText(str(draft))
            draft_box.setMinimumHeight(110)
            draft_box.setMaximumHeight(220)
            draft_box.setObjectName("draft-box")
            self._content_layout.addWidget(QLabel("Suggested Reply Draft"))
            self._content_layout.addWidget(draft_box)

    def _add_metric(self, grid: QGridLayout, row: int, col: int, label: str, value: str, object_name: str = "") -> None:
        box = QWidget()
        box.setObjectName("metric-box")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        label_widget = QLabel(label)
        label_widget.setObjectName("metric-label")
        value_widget = QLabel(str(value).replace("_", " ").title())
        value_widget.setWordWrap(True)
        if object_name:
            value_widget.setObjectName(object_name)
        else:
            value_widget.setObjectName("metric-value")
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)
        grid.addWidget(box, row, col)

    def _render_needs_review_banner(self, email: dict) -> None:
        banner = QWidget()
        banner.setObjectName("needs-review-banner")
        row = QHBoxLayout(banner)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)
        icon_lbl = QLabel("! Needs Human Review")
        icon_lbl.setObjectName("needs-review-banner-text")
        row.addWidget(icon_lbl)
        reasons: list[str] = []
        try:
            conf = float(email.get("confidence_score") or 100)
            if conf < 50:
                reasons.append(f"confidence {conf:.0f}%")
        except (TypeError, ValueError):
            pass
        risk_flags = _as_list(email.get("risk_flags"))
        if risk_flags:
            reasons.append(f"risk: {', '.join(str(f) for f in risk_flags[:2])}")
        category = str(email.get("category") or "")
        if category in {"Billing dispute", "Accessibility request"}:
            reasons.append(f"category: {category.lower()}")
        if reasons:
            reason_lbl = QLabel("  |  ".join(reasons))
            reason_lbl.setObjectName("muted-label")
            row.addWidget(reason_lbl)
        row.addStretch()
        self._content_layout.addWidget(banner)

    def _render_chip_list(self, label: str, values: list) -> None:
        if not values:
            return
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        for value in values[:5]:
            chip = QLabel(str(value))
            chip.setObjectName("chip")
            chip.setWordWrap(True)
            row.addWidget(chip)
        row.addStretch()
        self._content_layout.addLayout(row)

    def _render_risk_flags(self, flags: list) -> None:
        if not flags:
            return
        row = QHBoxLayout()
        lbl = QLabel("Risk flags")
        lbl.setObjectName("risk-flags-label")
        row.addWidget(lbl)
        for flag in flags[:5]:
            chip = QLabel(str(flag))
            chip.setObjectName("risk-chip")
            chip.setWordWrap(True)
            row.addWidget(chip)
        row.addStretch()
        self._content_layout.addLayout(row)

    def _render_steps(self, steps: list) -> None:
        if not steps:
            return
        self._content_layout.addWidget(QLabel("Next Steps"))
        for step in steps[:6]:
            item = QLabel(f"✓  {step}")
            item.setWordWrap(True)
            item.setObjectName("summary-text")
            self._content_layout.addWidget(item)

    def _render_thread(self, messages: list[dict]) -> None:
        title = QLabel(f"Conversation Thread ({len(messages)})")
        title.setObjectName("section-title")
        self._content_layout.addWidget(title)
        for message in messages:
            self._render_message(message)

    def _render_message(self, msg: dict) -> None:
        card = QWidget()
        card.setObjectName("message-card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 12)
        card_layout.setSpacing(7)

        sender_row = QHBoxLayout()
        sender = QLabel(f"<b>{html.escape(_sender_label(msg))}</b>")
        sender.setTextFormat(Qt.TextFormat.RichText)
        sender.setWordWrap(True)
        ts = QLabel((msg.get("received_datetime") or "")[:16].replace("T", " "))
        ts.setObjectName("muted-label")
        sender_row.addWidget(sender)
        sender_row.addStretch()
        sender_row.addWidget(ts)

        body_raw = msg.get("body_text") or msg.get("body_content") or msg.get("body") or msg.get("body_preview") or ""
        body_clean = _strip_html(body_raw) if "<" in body_raw else body_raw
        body_clean = textwrap.shorten(body_clean.strip(), width=2500, placeholder="... [truncated]")

        body = QTextBrowser()
        body.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.setPlainText(body_clean or "(No body preview available.)")
        body.setMinimumHeight(90)
        body.setMaximumHeight(320)
        body.setObjectName("message-body")

        card_layout.addLayout(sender_row)
        card_layout.addWidget(body)
        self._content_layout.addWidget(card)

    def _render_feedback_form(self, email: dict) -> None:
        header = QLabel("Correction Feedback")
        header.setObjectName("section-title")
        self._content_layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        self._fb_urgency = self._combo("Urgency", [("No change", ""), *[(f"{i} - {_urgency_label(i).split(' ', 1)[1]}", str(i)) for i in range(1, 6)]])
        self._fb_category = self._combo("Category", [("No change", ""), *[(c, c) for c in CATEGORIES]])
        self._fb_owner = self._combo("Owner", [("No change", ""), *[(o, o) for o in DEPARTMENT_OWNERS]])
        self._fb_contact = self._combo("Contact", [("No change", ""), *[(c, c) for c in CONTACT_TYPES]])
        self._fb_status = self._combo("Status", [("No change", ""), *[(s, s) for s in STATUSES]])
        self._fb_summary_rating = self._combo("Summary", [("Summary rating", ""), *[(str(i), str(i)) for i in range(1, 6)]])
        self._fb_reply_rating = self._combo("Reply", [("Reply rating", ""), *[(str(i), str(i)) for i in range(1, 6)]])

        for i, widget in enumerate(
            (
                self._fb_urgency,
                self._fb_category,
                self._fb_owner,
                self._fb_contact,
                self._fb_status,
                self._fb_summary_rating,
                self._fb_reply_rating,
            )
        ):
            grid.addWidget(widget, i // 3, i % 3)
        self._content_layout.addLayout(grid)

        self._feedback_text = QTextEdit()
        self._feedback_text.setPlaceholderText("What should ReplyRight learn from this correction?")
        self._feedback_text.setFixedHeight(72)
        self._content_layout.addWidget(self._feedback_text)

        row = QHBoxLayout()
        self._submit_fb_btn = QPushButton("Save Feedback")
        self._submit_fb_btn.setObjectName("secondary-btn")
        self._submit_fb_btn.setFixedHeight(32)
        self._submit_fb_btn.clicked.connect(self._on_submit_feedback)
        self._fb_message = QLabel(f"{email.get('feedback_count', 0)} previous correction(s)")
        self._fb_message.setObjectName("muted-label")
        row.addWidget(self._submit_fb_btn)
        row.addWidget(self._fb_message)
        row.addStretch()
        self._content_layout.addLayout(row)

    def _combo(self, _label: str, items: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        combo.setFixedHeight(30)
        for label, value in items:
            combo.addItem(label, value)
        return combo

    def _on_update_status(self) -> None:
        if not self._current_email_id:
            return
        status = self._status_combo.currentData()
        self._status_btn.setEnabled(False)
        self._action_status.setText("Updating status...")
        self._status_worker = self._start_worker(
            self._client.update_email_status,
            self._current_email_id,
            status,
            success=self._on_status_done,
            failure=self._on_status_error,
        )

    def _on_status_done(self, _result: dict) -> None:
        self._status_btn.setEnabled(True)
        self._action_status.setText("Status updated.")
        self.status_changed.emit()

    def _on_status_error(self, message: str) -> None:
        self._status_btn.setEnabled(True)
        self._action_status.setText(f"Status error: {message}")

    def _on_analyze(self) -> None:
        if not self._current_email_id:
            return
        self._action_status.setText("Running AI suggestion...")
        self._analyze_worker = self._start_worker(
            self._client.analyze_email,
            self._current_email_id,
            success=lambda _: self.load_email(self._current_email_id),
            failure=lambda msg: self._action_status.setText(f"AI error: {msg}"),
        )

    def _on_submit_feedback(self) -> None:
        if not self._current_email_id:
            return
        payload: dict = {"feedback_text": self._feedback_text.toPlainText().strip()}
        if not payload["feedback_text"]:
            payload["feedback_text"] = "Correction submitted from the native ReplyRight UI."

        mappings = (
            (self._fb_urgency, "corrected_urgency", int),
            (self._fb_category, "corrected_category", str),
            (self._fb_owner, "corrected_owner", str),
            (self._fb_contact, "corrected_contact_type", str),
            (self._fb_status, "corrected_status", str),
            (self._fb_summary_rating, "summary_quality_rating", int),
            (self._fb_reply_rating, "reply_quality_rating", int),
        )
        changed = False
        for combo, key, caster in mappings:
            value = combo.currentData()
            if value:
                payload[key] = caster(value)
                changed = True
        if not changed and payload["feedback_text"].startswith("Correction submitted"):
            self._fb_message.setText("Choose a correction or add a note.")
            return

        self._submit_fb_btn.setEnabled(False)
        self._fb_message.setText("Saving feedback...")
        self._feedback_worker = self._start_worker(
            self._client.submit_feedback,
            self._current_email_id,
            payload,
            success=self._on_feedback_done,
            failure=self._on_feedback_error,
        )

    def _on_feedback_done(self, _result: dict) -> None:
        self._submit_fb_btn.setEnabled(True)
        self._fb_message.setText("Feedback saved.")
        self.feedback_submitted.emit()
        self.load_email(self._current_email_id)

    def _on_feedback_error(self, message: str) -> None:
        self._submit_fb_btn.setEnabled(True)
        self._fb_message.setText(f"Feedback error: {message}")

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted-label")
        label.setWordWrap(True)
        return label

    def _error(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("error-text")
        label.setWordWrap(True)
        return label

    def _start_worker(self, fn, *args, success=None, failure=None, **kwargs) -> ApiWorker:
        worker = ApiWorker(fn, *args, **kwargs)
        if success is not None:
            worker.success.connect(success)
        if failure is not None:
            worker.failure.connect(failure)
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._workers.append(worker)
        worker.start()
        return worker

    def _cleanup_worker(self, worker: ApiWorker) -> None:
        if worker in self._workers:
            self._workers.remove(worker)
        worker.deleteLater()
