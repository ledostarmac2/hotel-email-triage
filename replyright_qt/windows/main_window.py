from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.api_client import ApiClient, ApiWorker
from replyright_qt.widgets.admin_panel import AdminPanel
from replyright_qt.widgets.conversation_detail import ConversationDetailWidget
from replyright_qt.widgets.conversation_list import ConversationListWidget
from replyright_qt.widgets.filter_bar import FilterBar
from replyright_qt.widgets.sidebar_nav import SidebarNav
from replyright_qt.windows.kyc_window import KycWindow


class MainWindow(QMainWindow):
    """Primary application window.

    Layout:
        SidebarNav (200 px fixed) | QSplitter
                                      ├── list panel (FilterBar + ConversationListWidget)
                                      └── ConversationDetailWidget
    """

    logged_out = Signal()

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self._client = client
        self._load_worker: ApiWorker | None = None
        self._sync_worker: ApiWorker | None = None
        self._current_queue = "inbox"
        self._current_filters: dict = {}
        self._kyc_window: KycWindow | None = None

        self.setWindowTitle("ReplyRight")
        self.setMinimumSize(1100, 680)
        self.resize(1440, 900)

        self._build_ui()
        self._wire_signals()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = SidebarNav()

        # List panel (left half of splitter)
        list_panel = QWidget()
        list_panel.setObjectName("list-panel")
        list_panel_layout = QVBoxLayout(list_panel)
        list_panel_layout.setContentsMargins(0, 0, 0, 0)
        list_panel_layout.setSpacing(0)

        self._filter_bar = FilterBar()
        self._conv_list = ConversationListWidget()

        list_panel_layout.addWidget(self._filter_bar)
        list_panel_layout.addWidget(self._conv_list)

        # Detail panel (right half of splitter)
        self._detail = ConversationDetailWidget(self._client)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(list_panel)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([380, 760])

        # Admin panel (swapped in when Admin queue is active)
        self._admin_panel = AdminPanel(self._client)

        # Stack: page 0 = email list+detail, page 1 = admin panel
        self._stack = QStackedWidget()
        self._stack.addWidget(splitter)
        self._stack.addWidget(self._admin_panel)

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._stack)

        self.setCentralWidget(root)

    def _wire_signals(self) -> None:
        self._sidebar.queue_changed.connect(self._on_queue_changed)
        self._sidebar.logout_requested.connect(self.logged_out)

        self._filter_bar.filters_changed.connect(self._on_filters_changed)
        self._filter_bar.sync_requested.connect(self._on_sync)

        self._conv_list.conversation_selected.connect(self._detail.load_email)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_user(self, user_data: dict) -> None:
        email = user_data.get("email", "")
        role = user_data.get("role", "user")
        self.setWindowTitle(f"ReplyRight — {email}")
        self._sidebar.set_user(email, role)
        self._load_taxonomy()

    def load_inbox(self) -> None:
        self._load_emails()

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_queue_changed(self, queue: str) -> None:
        self._current_queue = queue
        if queue == "admin":
            self._stack.setCurrentIndex(1)
            self._admin_panel.load()
        elif queue == "kyc":
            # KYC opens as a standalone floating window
            if self._kyc_window is None:
                self._kyc_window = KycWindow(self._client)
            self._kyc_window.activate()
            # Keep the main content area showing the email list
            self._stack.setCurrentIndex(0)
        else:
            self._stack.setCurrentIndex(0)
            self._detail.clear()
            self._load_emails()

    def _on_filters_changed(self, filters: dict) -> None:
        self._current_filters = filters
        self._load_emails()

    def _on_sync(self) -> None:
        self._filter_bar.setEnabled(False)
        self._sync_worker = ApiWorker(self._client.sync_outlook)
        self._sync_worker.success.connect(self._on_sync_done)
        self._sync_worker.failure.connect(self._on_sync_done)
        self._sync_worker.start()

    def _on_sync_done(self, _=None) -> None:
        self._filter_bar.setEnabled(True)
        self._load_emails()

    # ── Data loading ───────────────────────────────────────────────────────────

    def _load_emails(self) -> None:
        self._conv_list.set_loading(True)
        filters = self._current_filters
        self._load_worker = ApiWorker(
            self._client.list_emails,
            self._current_queue,
            filters.get("category", ""),
            filters.get("status", ""),
            filters.get("risk", ""),
            filters.get("q", ""),
        )
        self._load_worker.success.connect(self._on_emails_loaded)
        self._load_worker.failure.connect(self._on_emails_error)
        self._load_worker.start()

    def _on_emails_loaded(self, emails: list) -> None:
        self._conv_list.set_loading(False)
        self._conv_list.populate(emails)

    def _on_emails_error(self, message: str) -> None:
        self._conv_list.set_loading(False)
        self._conv_list.populate([])

    def _load_taxonomy(self) -> None:
        worker = ApiWorker(self._client.get_taxonomy)
        worker.success.connect(self._on_taxonomy_loaded)
        worker.start()
        self._taxonomy_worker = worker

    def _on_taxonomy_loaded(self, taxonomy: dict) -> None:
        categories = taxonomy.get("categories", [])
        if isinstance(categories, list):
            self._filter_bar.populate_categories(categories)
