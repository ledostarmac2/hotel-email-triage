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
    padding: 10px 12px;
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
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
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
}}

QPushButton#secondary-btn:hover {{
    background-color: {BORDER};
}}

/* ── Login window ────────────────────────────── */
QWidget#login-root {{
    background-color: {SIDEBAR_BG};
}}

QWidget#login-card {{
    background-color: {PANEL_BG};
    border-radius: 10px;
}}

QLabel#login-title {{
    font-size: 22px;
    font-weight: bold;
    color: {CONTENT_TEXT};
}}

QLabel#login-subtitle {{
    font-size: 13px;
    color: #6b7280;
}}

QLineEdit#login-field {{
    background-color: {CONTENT_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 9px 12px;
    font-size: 14px;
}}

QLineEdit#login-field:focus {{
    border-color: {ACCENT};
}}

QLabel#error-label {{
    color: {DANGER};
    font-size: 12px;
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

/* ── Analysis badges ─────────────────────────── */
QLabel#badge-urgency-1 {{ background-color: #c6f6d5; color: #276749; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-2 {{ background-color: #b2f5ea; color: #285e61; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-3 {{ background-color: #fefcbf; color: #744210; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-4 {{ background-color: #feebc8; color: #c05621; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}
QLabel#badge-urgency-5 {{ background-color: #fed7d7; color: #742a2a; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: bold; }}

QLabel#badge-status {{ background-color: #e2e8f0; color: #4a5568; border-radius: 4px; padding: 2px 7px; font-size: 11px; }}
"""
