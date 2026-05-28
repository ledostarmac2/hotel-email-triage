from __future__ import annotations

import hashlib
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from replyright_qt.display_labels import display_role

QUEUES: list[tuple[str, str]] = [
    ("inbox", "Inbox"),
    ("review", "Needs Human Review"),
    ("urgent", "Urgent"),
    ("vip", "VIP"),
    ("missing", "Missing Information"),
    ("immediate", "Immediate"),
    ("today", "Today"),
    ("waiting_guest", "Waiting on Guest"),
    ("waiting_internal", "Waiting on Internal Team"),
    ("billing_risk", "Billing Risk"),
    ("vip_travel", "VIP / Travel Advisor"),
    ("complaints", "Complaints"),
    ("low_confidence", "Low Confidence"),
    ("no_action", "No Action Likely"),
    ("kyc", "KYC Auto"),
    ("settings", "Settings"),
    ("admin", "Admin"),
]

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_ICON_DIR = os.path.join(_ROOT_DIR, "replyright_qt", "resources", "icons")

_QUEUE_GROUPS: list[tuple[str, list[tuple[str, str, str]]]] = [
    (
        "INBOX",
        [
            ("inbox", "inbox", "Inbox"),
            ("review", "review", "Needs Human Review"),
            ("urgent", "urgent", "Urgent"),
            ("vip", "vip", "VIP"),
            ("missing", "missing", "Missing Information"),
            ("kyc", "kyc", "KYC Auto"),
        ],
    ),
    (
        "HOTEL OPS",
        [
            ("immediate", "immediate", "Immediate"),
            ("today", "today", "Today"),
            ("waiting_guest", "waiting_guest", "Waiting on Guest"),
            ("waiting_internal", "waiting_internal", "Waiting on Internal Team"),
            ("billing_risk", "billing_risk", "Billing Risk"),
            ("vip_travel", "vip_travel", "VIP / Travel Advisor"),
            ("complaints", "complaints", "Complaints"),
            ("low_confidence", "low_confidence", "Low Confidence"),
            ("no_action", "no_action", "No Action Likely"),
        ],
    ),
    ("ADMIN", [("settings", "settings", "Settings"), ("admin", "admin", "Admin")]),
]

_AVATAR_COLORS = [
    "#0e7a71",
    "#7c3aed",
    "#c05621",
    "#2563eb",
    "#b45309",
    "#0891b2",
    "#15803d",
    "#be185d",
]


def _avatar_color(seed: str) -> str:
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(_AVATAR_COLORS)
    return _AVATAR_COLORS[idx]


class _SidebarItem(QWidget):
    clicked = Signal(str)

    def __init__(self, icon: str, key: str, label: str) -> None:
        super().__init__()
        self._key = key
        self.setObjectName("nav-item")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(9)

        self._icon = _NavIcon(icon)

        name_lbl = QLabel(label)
        name_lbl.setObjectName("nav-label")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._count_lbl = QLabel("")
        self._count_lbl.setObjectName("nav-count")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_lbl.setFixedHeight(20)
        self._count_lbl.setMinimumWidth(24)
        self._count_lbl.hide()

        row.addWidget(self._icon)
        row.addWidget(name_lbl)
        row.addWidget(self._count_lbl)

    def set_count(self, count: int) -> None:
        if count > 0:
            self._count_lbl.setText(str(count))
            self._count_lbl.show()
        else:
            self._count_lbl.hide()

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self._icon.set_active(active)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._key)
        super().mousePressEvent(event)


class _NavIcon(QLabel):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.setObjectName("nav-icon")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(28, 28)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._normal = self._load_pixmap(24)
        self._active = self._load_pixmap(26)
        self.setPixmap(self._normal)

    def set_active(self, active: bool) -> None:
        self.setPixmap(self._active if active else self._normal)

    def _load_pixmap(self, size: int) -> QPixmap:
        path = os.path.join(_ICON_DIR, f"{self._name}.png")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


class _UserCard(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("user-card")
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        self._avatar = QLabel("RR")
        self._avatar.setObjectName("sidebar-avatar")
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setFixedSize(36, 36)

        info_col = QVBoxLayout()
        info_col.setSpacing(1)
        info_col.setContentsMargins(0, 0, 0, 0)

        self._name_lbl = QLabel("Signed in")
        self._name_lbl.setObjectName("user-name-lbl")

        self._role_lbl = QLabel("")
        self._role_lbl.setObjectName("user-role-lbl")

        info_col.addWidget(self._name_lbl)
        info_col.addWidget(self._role_lbl)
        row.addWidget(self._avatar)
        row.addLayout(info_col)

    def update_user(self, email: str, role: str, profile_image: str = "") -> None:
        local = (email or "ReplyRight").split("@")[0]
        parts = local.replace(".", " ").replace("_", " ").split()
        initials = "".join(part[:1] for part in parts[:2]).upper() or "RR"
        color = _avatar_color(email or "ReplyRight")
        if profile_image and os.path.exists(profile_image):
            pixmap = _rounded_pixmap(profile_image, 36)
            if pixmap and not pixmap.isNull():
                self._avatar.setPixmap(pixmap)
                self._avatar.setText("")
                self._avatar.setStyleSheet(
                    "background-color: transparent;"
                    "min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;"
                )
            else:
                self._set_initials(initials, color)
        else:
            self._set_initials(initials, color)
        self._name_lbl.setText(" ".join(part.title() for part in parts) or "Signed in")
        self._role_lbl.setText(display_role(role))

    def _set_initials(self, initials: str, color: str) -> None:
        self._avatar.setPixmap(QPixmap())
        self._avatar.setText(initials)
        self._avatar.setStyleSheet(
            f"background-color: {color}; border-radius: 18px; color: white;"
            "font-size: 12px; font-weight: 800;"
            "min-width: 36px; max-width: 36px; min-height: 36px; max-height: 36px;"
        )


def _rounded_pixmap(path: str, size: int) -> QPixmap:
    source = QPixmap(path)
    if source.isNull():
        return QPixmap()
    scaled = source.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)
    output = QPixmap(size, size)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path_obj = QPainterPath()
    path_obj.addEllipse(0, 0, size, size)
    painter.setClipPath(path_obj)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return output


class SidebarNav(QWidget):
    queue_changed = Signal(str)
    logout_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._items: dict[str, _SidebarItem] = {}
        self._active_queue = "inbox"
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(0)

        logo = QLabel("ReplyRight")
        logo.setObjectName("brand")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(48)
        logo.setMaximumHeight(58)
        logo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        logo_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "outlook_dashboard",
            "static",
            "replyright-logo.png",
        )
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                logo.setPixmap(pixmap.scaledToWidth(168, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo)

        tagline = QLabel("The right response, every time.")
        tagline.setObjectName("brand-subtitle")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)
        layout.addSpacing(12)

        self._user_card = _UserCard()
        layout.addWidget(self._user_card)
        layout.addSpacing(12)

        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("sidebar-scroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        nav_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        nav_body = QWidget()
        nav_body.setObjectName("sidebar-scroll-body")
        nav_layout = QVBoxLayout(nav_body)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(0)

        for group_name, items in _QUEUE_GROUPS:
            header = QLabel(group_name)
            header.setObjectName("sidebar-section-header")
            nav_layout.addWidget(header)
            nav_layout.addSpacing(3)
            for icon, key, label in items:
                item = _SidebarItem(icon, key, label)
                item.clicked.connect(self._select)
                self._items[key] = item
                nav_layout.addWidget(item)
            nav_layout.addSpacing(9)

        nav_layout.addStretch()
        nav_scroll.setWidget(nav_body)
        layout.addWidget(nav_scroll)

        wa_label = QLabel("WALDORF ASTORIA")
        wa_label.setObjectName("waldorf-label")
        wa_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wa_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(wa_label)

        wa_mark = QLabel("WA")
        wa_mark.setObjectName("waldorf-mark")
        wa_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wa_mark.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(wa_mark)

        wa_sub = QLabel("HOTELS & RESORTS")
        wa_sub.setObjectName("waldorf-sub")
        wa_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wa_sub.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(wa_sub)
        layout.addSpacing(10)

        footnote = QLabel("Read-only Outlook mode")
        footnote.setObjectName("sidebar-footnote")
        footnote.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footnote)
        layout.addSpacing(8)

        logout_btn = QPushButton("Sign out")
        logout_btn.setObjectName("logout-btn")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFixedHeight(38)
        logout_btn.clicked.connect(self.logout_requested)
        layout.addWidget(logout_btn)

        self._select("inbox")

    def _select(self, queue_key: str) -> None:
        for key, item in self._items.items():
            item.set_active(key == queue_key)
        self._active_queue = queue_key
        self.queue_changed.emit(queue_key)

    def restore_queue(self, queue_key: str) -> None:
        for key, item in self._items.items():
            item.set_active(key == queue_key)
        self._active_queue = queue_key

    def set_user(self, email: str, role: str) -> None:
        self._user_email = email
        self._user_role = role
        self._user_card.update_user(email, role, getattr(self, "_profile_image", ""))
        admin_item = self._items.get("admin")
        if admin_item:
            admin_item.setVisible(role == "admin")

    def set_profile_image(self, image_path: str) -> None:
        self._profile_image = image_path
        self._user_card.update_user(
            getattr(self, "_user_email", ""),
            getattr(self, "_user_role", "user"),
            image_path,
        )

    def set_queue_count(self, queue_key: str, count: int) -> None:
        item = self._items.get(queue_key)
        if item:
            item.set_count(count)

    def active_queue(self) -> str:
        return self._active_queue
