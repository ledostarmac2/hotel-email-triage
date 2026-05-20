from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker
from replyright_qt.styles.theme import get_stylesheet
from replyright_qt.widgets.admin_panel import AdminPanel
from replyright_qt.widgets.conversation_detail import ConversationDetailWidget
from replyright_qt.widgets.conversation_list import ConversationListWidget
from replyright_qt.widgets.filter_bar import FilterBar
from replyright_qt.widgets.settings_panel import SettingsPanel
from replyright_qt.widgets.sidebar_nav import SidebarNav
from replyright_qt.windows.kyc_reminder_window import KycReminderWindow


class MainWindow(QMainWindow):
    """Primary ReplyRight native application window."""

    logged_out = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._workers: list[ApiWorker] = []
        self._load_worker: ApiWorker | None = None
        self._sync_worker: ApiWorker | None = None
        self._kyc_window: KycReminderWindow | None = None
        self._current_queue = "inbox"
        self._current_filters: dict = {}

        self.setWindowTitle("ReplyRight")
        self.setMinimumSize(1180, 720)
        self.resize(1500, 920)

        self._build_ui()
        self._wire_signals()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = SidebarNav()

        list_panel = QWidget()
        list_panel.setObjectName("list-panel")
        list_panel_layout = QVBoxLayout(list_panel)
        list_panel_layout.setContentsMargins(0, 0, 0, 0)
        list_panel_layout.setSpacing(0)

        self._filter_bar = FilterBar()
        self._conv_list = ConversationListWidget()
        list_panel_layout.addWidget(self._filter_bar)
        list_panel_layout.addWidget(self._conv_list)

        self._detail = ConversationDetailWidget(self._client)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_panel)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([590, 760])

        self._admin_panel = AdminPanel(self._client)
        self._settings_panel = SettingsPanel(self._client)

        self._stack = QStackedWidget()
        self._stack.addWidget(splitter)
        self._stack.addWidget(self._admin_panel)
        self._stack.addWidget(self._settings_panel)

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._stack)
        self.setCentralWidget(root)

    def _wire_signals(self) -> None:
        self._sidebar.queue_changed.connect(self._on_queue_changed)
        self._sidebar.logout_requested.connect(self.logged_out)
        self._filter_bar.filters_changed.connect(self._on_filters_changed)
        self._filter_bar.sync_requested.connect(self._on_sync)
        self._conv_list.conversation_selected.connect(self._detail.load_email)
        self._detail.feedback_submitted.connect(self._load_emails)
        self._detail.status_changed.connect(self._load_emails)
        self._settings_panel.theme_changed.connect(self._on_theme_changed)
        self._settings_panel.profile_image_changed.connect(self._sidebar.set_profile_image)

    def set_user(self, user_data: dict) -> None:
        email = user_data.get("email", "")
        role = user_data.get("role", "user")
        self.setWindowTitle(f"ReplyRight - {email}")
        self._sidebar.set_user(email, role)
        self._settings_panel.set_user(user_data)
        self._load_taxonomy()

    def load_inbox(self) -> None:
        self._load_emails()

    def _on_queue_changed(self, queue: str) -> None:
        previous_queue = self._current_queue
        self._current_queue = queue
        if queue == "admin":
            self._stack.setCurrentIndex(1)
            self._admin_panel.load()
        elif queue == "kyc":
            self._current_queue = previous_queue if previous_queue in {"inbox", "urgent", "vip", "missing"} else "inbox"
            self._sidebar.restore_queue(self._current_queue)
            self._open_kyc_window()
        elif queue == "settings":
            self._stack.setCurrentIndex(2)
        else:
            self._stack.setCurrentIndex(0)
            self._detail.clear()
            self._load_emails()

    def _on_filters_changed(self, filters: dict) -> None:
        self._current_filters = filters
        if self._current_queue in {"inbox", "urgent", "vip", "missing"}:
            self._load_emails()

    def _on_sync(self) -> None:
        self._filter_bar.set_syncing(True)
        self._sync_worker = self._start_worker(
            self._client.sync_outlook,
            success=self._on_sync_done,
            failure=self._on_sync_error,
        )

    def _on_sync_done(self, result: dict | None = None) -> None:
        count = 0
        if isinstance(result, dict):
            count = int(result.get("fetched_count") or result.get("exported_count") or 0)
        self._filter_bar.set_syncing(False, f"Updated {count} messages." if count else "Updated just now.")
        self._load_emails()

    def _on_sync_error(self, message: str) -> None:
        self._filter_bar.set_syncing(False, f"Refresh failed: {message}")
        self._load_emails()

    def _load_emails(self) -> None:
        if self._current_queue not in {"inbox", "urgent", "vip", "missing"}:
            return
        self._conv_list.set_loading(True)
        filters = self._current_filters
        self._load_worker = self._start_worker(
            self._client.list_emails,
            self._current_queue,
            filters.get("category", ""),
            filters.get("status", ""),
            filters.get("risk", ""),
            filters.get("q", ""),
            success=self._on_emails_loaded,
            failure=self._on_emails_error,
        )

    def _on_emails_loaded(self, emails: list) -> None:
        self._conv_list.set_loading(False)
        self._conv_list.populate(emails)
        self._sidebar.set_queue_count(self._current_queue, len(emails))

    def _on_emails_error(self, message: str) -> None:
        self._conv_list.set_loading(False)
        self._conv_list.populate([])
        self._filter_bar.set_syncing(False, f"Load failed: {message}")

    def _load_taxonomy(self) -> None:
        worker = self._start_worker(self._client.get_taxonomy, success=self._on_taxonomy_loaded)
        self._taxonomy_worker = worker

    def _on_taxonomy_loaded(self, taxonomy: dict) -> None:
        categories = taxonomy.get("categories", [])
        if isinstance(categories, list):
            self._filter_bar.populate_categories(categories)

    def _on_theme_changed(self, mode: str) -> None:
        app = QApplication.instance()
        if app:
            app.setStyleSheet(get_stylesheet(mode))

    def _open_kyc_window(self) -> None:
        if self._kyc_window is None:
            self._kyc_window = KycReminderWindow(self)
            self._kyc_window.destroyed.connect(lambda: setattr(self, "_kyc_window", None))
        self._kyc_window.show()
        self._kyc_window.raise_()
        self._kyc_window.activateWindow()

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
