from __future__ import annotations

# Mirrors the CSS design system from outlook_dashboard/static/styles.css.
# Sidebar dark (#131722), content light (#f5f6f8), accent blue (#2d6cdf).

SIDEBAR_BG = "#131722"
SIDEBAR_TEXT = "#c8ccd8"
SIDEBAR_TEXT_ACTIVE = "#ffffff"
SIDEBAR_HOVER = "#1e2435"
SIDEBAR_ACTIVE = "#2d6cdf"

CONTENT_BG = "#f5f6f8"
CONTENT_TEXT = "#1a1d2e"
PANEL_BG = "#ffffff"
BORDER = "#e2e5ee"

ACCENT = "#2d6cdf"
ACCENT_HOVER = "#1a55c0"
DANGER = "#e53e3e"
SUCCESS = "#38a169"
WARNING = "#d69e2e"

# Urgency badge colours (1=low … 5=critical)
URGENCY_COLORS = {
    1: ("#276749", "#c6f6d5"),
    2: ("#285e61", "#b2f5ea"),
    3: ("#744210", "#fefcbf"),
    4: ("#c05621", "#feebc8"),
    5: ("#742a2a", "#fed7d7"),
}

FONT_FAMILY = "Segoe UI, Arial, sans-serif"
FONT_SIZE = "13px"

STYLESHEET = f"""
/* ── Global ──────────────────────────────────── */
QWidget {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
    color: {CONTENT_TEXT};
    background-color: {CONTENT_BG};
}}

QMainWindow {{
    background-color: {CONTENT_BG};
}}

/* ── Sidebar ─────────────────────────────────── */
QWidget#sidebar {{
    background-color: {SIDEBAR_BG};
    border-right: 1px solid #0d1018;
}}

QLabel#brand {{
    color: {SIDEBAR_TEXT_ACTIVE};
    font-size: 16px;
    font-weight: bold;
    padding: 20px 16px 12px 16px;
    background-color: {SIDEBAR_BG};
}}

QPushButton#nav-btn {{
    background-color: transparent;
    color: {SIDEBAR_TEXT};
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
    text-align: left;
    font-size: 13px;
}}

QPushButton#nav-btn:hover {{
    background-color: {SIDEBAR_HOVER};
    color: {SIDEBAR_TEXT_ACTIVE};
}}

QPushButton#nav-btn[active="true"] {{
    background-color: {SIDEBAR_ACTIVE};
    color: {SIDEBAR_TEXT_ACTIVE};
    font-weight: bold;
}}

QPushButton#logout-btn {{
    background-color: transparent;
    color: #fc8181;
    border: none;
    border-radius: 6px;
    padding: 9px 14px;
    text-align: left;
    font-size: 13px;
}}

QPushButton#logout-btn:hover {{
    background-color: #2d1515;
    color: #feb2b2;
}}

QLabel#user-label {{
    color: {SIDEBAR_TEXT};
    font-size: 11px;
    padding: 4px 16px 12px 16px;
    background-color: {SIDEBAR_BG};
}}

/* ── List panel ──────────────────────────────── */
QWidget#list-panel {{
    background-color: {PANEL_BG};
    border-right: 1px solid {BORDER};
}}

QListWidget {{
    background-color: {PANEL_BG};
    border: none;
    outline: none;
}}

QListWidget::item {{
    padding: 0;
    border-bottom: 1px solid {BORDER};
}}

QListWidget::item:selected {{
    background-color: #ebf0fc;
    color: {CONTENT_TEXT};
}}

QListWidget::item:hover:!selected {{
    background-color: #f0f3fa;
}}

/* ── Filter bar ──────────────────────────────── */
QWidget#filter-bar {{
    background-color: {PANEL_BG};
    border-bottom: 1px solid {BORDER};
    padding: 6px 8px;
}}

QWidget#filter-bar QLabel {{
    background-color: transparent;
    color: #718096;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QLineEdit#search-box {{
    background-color: {CONTENT_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 5px 8px;
}}

QLineEdit#search-box:focus {{
    border-color: {ACCENT};
}}

QComboBox {{
    background-color: {CONTENT_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 8px;
    min-width: 100px;
    min-height: 22px;
}}

QComboBox:focus {{
    border-color: {ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}

QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}

QComboBox QAbstractItemView {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 4px;
    selection-background-color: #ebf0fc;
    selection-color: {CONTENT_TEXT};
    padding: 2px;
}}

/* ── Detail panel ────────────────────────────── */
QWidget#detail-panel {{
    background-color: {PANEL_BG};
}}

QTextBrowser {{
    background-color: {PANEL_BG};
    border: none;
    font-size: 13px;
    line-height: 1.5;
}}

/* ── Buttons ─────────────────────────────────── */
QPushButton#primary-btn {{
    background-color: {ACCENT};
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 22px;
}}

QPushButton#primary-btn:hover {{
    background-color: {ACCENT_HOVER};
}}

QPushButton#primary-btn:disabled {{
    background-color: #8da8d8;
}}

QPushButton#secondary-btn {{
    background-color: {CONTENT_BG};
    color: {CONTENT_TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 22px;
}}

QPushButton#secondary-btn:hover {{
    background-color: {BORDER};
}}

QPushButton#secondary-btn:disabled {{
    color: #a0aec0;
    border-color: #d4d8e2;
}}

QPushButton#danger-btn {{
    background-color: {CONTENT_BG};
    color: {DANGER};
    border: 1px solid {DANGER};
    border-radius: 6px;
    padding: 8px 16px;
    min-height: 22px;
}}

QPushButton#danger-btn:hover {{
    background-color: #fff5f5;
}}

QPushButton#danger-btn:disabled {{
    color: #fc8181;
    border-color: #fc8181;
}}

/* ── QGroupBox ───────────────────────────────── */
QGroupBox {{
    font-size: 12px;
    font-weight: 600;
    color: #4a5568;
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 10px;
    padding: 16px 14px 12px 14px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 6px;
    background-color: {CONTENT_BG};
    color: #4a5568;
    font-size: 12px;
    font-weight: 600;
}}

/* ── QSpinBox ────────────────────────────────── */
QSpinBox {{
    background-color: {CONTENT_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px 6px;
    min-height: 22px;
    color: {CONTENT_TEXT};
}}

QSpinBox:focus {{
    border-color: {ACCENT};
}}

QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 16px;
    border-left: 1px solid {BORDER};
    border-bottom: 1px solid {BORDER};
    border-top-right-radius: 5px;
    background-color: {CONTENT_BG};
}}

QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 16px;
    border-left: 1px solid {BORDER};
    border-top: 1px solid {BORDER};
    border-bottom-right-radius: 5px;
    background-color: {CONTENT_BG};
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background-color: {BORDER};
}}

/* ── QTabWidget / QTabBar ────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {PANEL_BG};
    border-radius: 0 0 8px 8px;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background-color: {CONTENT_BG};
    color: #718096;
    border: 1px solid {BORDER};
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 12px;
    min-width: 70px;
}}

QTabBar::tab:selected {{
    background-color: {PANEL_BG};
    color: {CONTENT_TEXT};
    font-weight: 600;
    border-bottom: 2px solid {ACCENT};
}}

QTabBar::tab:hover:!selected {{
    background-color: #ebf0fc;
    color: {CONTENT_TEXT};
}}

/* ── QTableWidget / QHeaderView ──────────────── */
QTableWidget {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 0;
    gridline-color: #edf0f7;
    selection-background-color: #ebf0fc;
}}

QTableWidget::item {{
    padding: 7px 10px;
    border-bottom: 1px solid #edf0f7;
    color: {CONTENT_TEXT};
}}

QTableWidget::item:selected {{
    background-color: #ebf0fc;
    color: {CONTENT_TEXT};
}}

QHeaderView {{
    background-color: {CONTENT_BG};
    border: none;
}}

QHeaderView::section {{
    background-color: {CONTENT_BG};
    border: none;
    border-bottom: 2px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 7px 10px;
    font-size: 11px;
    font-weight: 700;
    color: #718096;
    letter-spacing: 0.3px;
    text-transform: uppercase;
}}

QHeaderView::section:last {{
    border-right: none;
}}

QHeaderView::section:checked {{
    background-color: #ebf0fc;
}}

/* ── QSplitter ───────────────────────────────── */
QSplitter::handle:horizontal {{
    background-color: {BORDER};
    width: 1px;
}}

QSplitter::handle:vertical {{
    background-color: {BORDER};
    height: 1px;
}}

/* ── QCheckBox ───────────────────────────────── */
QCheckBox {{
    spacing: 8px;
    color: {CONTENT_TEXT};
    font-size: {FONT_SIZE};
    background-color: transparent;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid #c1c9d8;
    border-radius: 4px;
    background-color: {PANEL_BG};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QCheckBox::indicator:disabled {{
    background-color: {CONTENT_BG};
    border-color: {BORDER};
}}

/* ── Login window ────────────────────────────── */
QWidget#login-root {{
    background-color: #111723;
}}

QWidget#login-card {{
    background-color: {PANEL_BG};
    border: 1px solid #edf0f5;
    border-radius: 12px;
}}

QWidget#login-card QLabel {{
    background-color: transparent;
}}

QLabel#login-mark {{
    background-color: {ACCENT};
    color: white;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 13px;
    font-weight: 800;
}}

QLabel#login-title {{
    background-color: transparent;
    font-size: 26px;
    font-weight: bold;
    color: #101828;
}}

QLabel#login-subtitle {{
    background-color: transparent;
    font-size: 13px;
    color: #667085;
}}

QLabel#login-field-label {{
    background-color: transparent;
    color: #344054;
    font-size: 12px;
    font-weight: 700;
    padding-top: 4px;
}}

QLineEdit#login-field {{
    background-color: #ffffff;
    border: 1px solid #d0d5dd;
    border-radius: 8px;
    padding: 11px 12px;
    font-size: 14px;
    color: #101828;
    selection-background-color: {ACCENT};
    min-height: 22px;
}}

QLineEdit#login-field:focus {{
    border-color: {ACCENT};
    background-color: #ffffff;
}}

QCheckBox#login-checkbox {{
    background-color: transparent;
    color: #475467;
    font-size: 12px;
    spacing: 7px;
}}

QCheckBox#login-checkbox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid #98a2b3;
    border-radius: 4px;
    background-color: #ffffff;
}}

QCheckBox#login-checkbox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}

QLabel#error-label {{
    background-color: #fff1f3;
    color: #b42318;
    font-size: 12px;
    border: 1px solid #fecdca;
    border-radius: 8px;
    padding: 8px 10px;
}}

QPushButton#link-btn {{
    color: {ACCENT};
    font-size: 12px;
    background: transparent;
    border: none;
    padding: 2px 4px;
    text-decoration: underline;
}}

QPushButton#link-btn:hover {{
    color: {ACCENT_HOVER};
}}

QFrame#login-divider {{
    color: #eaecf0;
    background-color: #eaecf0;
    max-height: 1px;
}}

QLabel#login-footnote {{
    background-color: transparent;
    color: #98a2b3;
    font-size: 11px;
    padding-top: 4px;
}}

/* ── Scroll bars ─────────────────────────────── */
QScrollBar:vertical {{
    background: {CONTENT_BG};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: #c1c9d8;
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: #a0aabb;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {CONTENT_BG};
    height: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal {{
    background: #c1c9d8;
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #a0aabb;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Analysis badges ─────────────────────────── */
QLabel#badge-urgency-1 {{ background-color: #c6f6d5; color: #276749; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-2 {{ background-color: #b2f5ea; color: #285e61; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-3 {{ background-color: #fefcbf; color: #744210; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-4 {{ background-color: #feebc8; color: #c05621; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-5 {{ background-color: #fed7d7; color: #742a2a; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}

QLabel#badge-status {{ background-color: #e2e8f0; color: #4a5568; border-radius: 4px; padding: 2px 7px; font-size: 11px; }}
"""
