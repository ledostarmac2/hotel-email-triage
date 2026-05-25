from __future__ import annotations

FONT_FAMILY = "Segoe UI, Arial, sans-serif"
FONT_SIZE = "13px"

LIGHT = {
    "sidebar_bg": "#071833",
    "sidebar_bg_2": "#0b244a",
    "sidebar_text": "#d8e3f5",
    "sidebar_muted": "#8fa6c8",
    "sidebar_hover": "#0e315f",
    "sidebar_active": "#155dfc",
    "content_bg": "#f6f8fc",
    "content_text": "#111827",
    "panel_bg": "#ffffff",
    "panel_alt": "#f8fafc",
    "border": "#d8deea",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "danger": "#dc2626",
    "success": "#059669",
    "warning": "#d97706",
}

DARK = {
    "sidebar_bg": "#050b18",
    "sidebar_bg_2": "#08142a",
    "sidebar_text": "#e5edf9",
    "sidebar_muted": "#8fa6c8",
    "sidebar_hover": "#10233f",
    "sidebar_active": "#3b82f6",
    "content_bg": "#0b1220",
    "content_text": "#e5e7eb",
    "panel_bg": "#111827",
    "panel_alt": "#172033",
    "border": "#263347",
    "accent": "#60a5fa",
    "accent_hover": "#3b82f6",
    "danger": "#f87171",
    "success": "#34d399",
    "warning": "#fbbf24",
}


def get_stylesheet(mode: str = "light") -> str:
    c = DARK if mode == "dark" else LIGHT
    muted = "#9aa7bd" if mode == "light" else "#a7b2c5"
    selected_bg = "#edf4ff" if mode == "light" else "#12233d"
    selected_border = "#2563eb" if mode == "light" else "#3b82f6"
    hover_bg = "#f7f9fd" if mode == "light" else "#101c31"
    input_bg = "#ffffff" if mode == "light" else "#0f172a"
    login_card = "#ffffff" if mode == "light" else "#0f172a"
    login_root = "#0b1220" if mode == "light" else "#030712"
    field_border = "#cbd5e1" if mode == "light" else "#334155"
    return f"""
QWidget {{
    font-family: {FONT_FAMILY};
    font-size: {FONT_SIZE};
    color: {c["content_text"]};
    background-color: {c["content_bg"]};
}}

QWidget#sidebar {{
    background-color: {c["sidebar_bg"]};
    border-right: 1px solid #061025;
}}

QLabel#brand {{
    color: #ffffff;
    font-size: 20px;
    font-weight: 800;
    padding: 16px 10px 10px 10px;
    background-color: transparent;
}}

QLabel#brand-subtitle {{
    color: {c["sidebar_muted"]};
    font-size: 10px;
    padding: 0 10px 14px 10px;
    background-color: transparent;
}}

QWidget#user-card {{
    background-color: {c["sidebar_bg_2"]};
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 8px;
}}

QLabel#user-name-lbl {{
    background-color: transparent;
    color: #ffffff;
    font-size: 13px;
    font-weight: 800;
}}

QLabel#user-role-lbl {{
    background-color: transparent;
    color: {c["sidebar_muted"]};
    font-size: 11px;
}}

QWidget#nav-item {{
    background-color: transparent;
    border-radius: 8px;
}}

QWidget#nav-item:hover {{
    background-color: {c["sidebar_hover"]};
}}

QWidget#nav-item[active="true"] {{
    background-color: {c["sidebar_active"]};
}}

QLabel#nav-icon {{
    background-color: transparent;
    color: #c7d2fe;
    font-size: 11px;
    font-weight: 900;
}}

QLabel#nav-label {{
    background-color: transparent;
    color: {c["sidebar_text"]};
    font-size: 14px;
    font-weight: 650;
}}

QLabel#nav-count {{
    background-color: rgba(255,255,255,0.15);
    color: white;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 800;
    padding: 1px 7px;
}}

QLabel#sidebar-section-header {{
    color: {c["sidebar_muted"]};
    background-color: transparent;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0px;
    padding: 8px 8px 4px 8px;
}}

QLabel#waldorf-label {{
    background-color: transparent;
    color: #d8e3f5;
    font-size: 9px;
    font-weight: 800;
    padding-top: 4px;
}}

QLabel#waldorf-mark {{
    background-color: transparent;
    color: #ffffff;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 24px;
    font-weight: 500;
}}

QLabel#waldorf-sub {{
    background-color: transparent;
    color: {c["sidebar_muted"]};
    font-size: 9px;
}}

QLabel#sidebar-footnote {{
    background-color: rgba(255,255,255,0.06);
    color: {c["sidebar_text"]};
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 8px;
    padding: 9px 12px;
    font-size: 12px;
}}

QPushButton#nav-btn {{
    background-color: transparent;
    color: {c["sidebar_text"]};
    border: none;
    border-radius: 8px;
    padding: 9px 13px;
    text-align: left;
    font-size: 14px;
}}

QPushButton#nav-btn:hover {{
    background-color: {c["sidebar_hover"]};
    color: #ffffff;
}}

QPushButton#nav-btn[active="true"] {{
    background-color: {c["sidebar_active"]};
    color: #ffffff;
    font-weight: 700;
}}

QPushButton#logout-btn {{
    background-color: transparent;
    color: #fecaca;
    border: none;
    border-radius: 8px;
    padding: 9px 13px;
    text-align: left;
    font-size: 13px;
}}

QPushButton#logout-btn:hover {{
    background-color: #3f1111;
    color: #ffffff;
}}

QLabel#user-label {{
    color: {c["sidebar_muted"]};
    font-size: 11px;
    padding: 2px 10px 12px 10px;
    background-color: transparent;
}}

QWidget#list-panel {{
    background-color: {c["panel_bg"]};
    border-right: 1px solid {c["border"]};
}}

QListWidget {{
    background-color: {c["panel_bg"]};
    border: none;
    outline: none;
}}

QListWidget::item {{
    padding: 0;
    border-bottom: 1px solid {c["border"]};
    background-color: {c["panel_bg"]};
}}

QListWidget::item:selected {{
    background-color: transparent;
    color: {c["content_text"]};
    border: none;
}}

QListWidget::item:hover:!selected {{
    background-color: {hover_bg};
}}

QWidget#conversation-row {{
    background-color: transparent;
}}

QWidget#conversation-row:hover {{
    background-color: {hover_bg};
}}

QWidget#conversation-row[selected="true"] {{
    background-color: {selected_bg};
    border-left: 2px solid {selected_border};
}}

QWidget#conversation-row QLabel {{
    background-color: transparent;
}}

QLabel#avatar {{
    background-color: {"#64748b" if mode == "light" else "#475569"};
    color: #ffffff;
    border-radius: 17px;
    font-size: 11px;
    font-weight: 800;
}}

QLabel#row-subject {{
    color: {c["content_text"]};
    font-size: 12px;
    font-weight: 700;
}}

QLabel#row-meta, QLabel#row-preview {{
    color: {muted};
    font-size: 11px;
}}

QLabel#list-count {{
    color: {c["content_text"]};
    font-size: 12px;
    font-weight: 800;
}}

QWidget#filter-bar {{
    background-color: {c["panel_bg"]};
    border-bottom: 1px solid {c["border"]};
    padding: 0;
}}

QLineEdit, QTextEdit, QTextBrowser, QComboBox {{
    background-color: {input_bg};
    color: {c["content_text"]};
    border: 1px solid {field_border};
    border-radius: 7px;
    padding: 5px 8px;
}}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {c["accent"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QWidget#detail-panel {{
    background-color: {c["panel_bg"]};
}}

QLabel#detail-title {{
    color: {c["content_text"]};
    font-size: 22px;
    font-weight: 800;
}}

QLabel#section-title {{
    color: {c["content_text"]};
    font-size: 14px;
    font-weight: 800;
}}

QLabel#muted-label {{
    color: {muted};
    font-size: 12px;
}}

QLabel#error-text, QLabel#error-label {{
    color: #991b1b;
    background-color: #fee2e2;
    border: 1px solid #fecaca;
    border-radius: 8px;
    padding: 8px 10px;
}}

QFrame#divider {{
    color: {c["border"]};
    background-color: {c["border"]};
    max-height: 1px;
}}

QWidget#metric-box, QWidget#message-card, QWidget#settings-card, QWidget#kyc-card {{
    background-color: {c["panel_alt"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
}}

QLabel#metric-label {{
    color: {muted};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#metric-value, QLabel#settings-title {{
    color: {c["content_text"]};
    font-size: 13px;
    font-weight: 800;
}}

QLabel#summary-text {{
    color: {c["content_text"]};
    font-size: 13px;
}}

QLabel#chip {{
    background-color: {"#dbeafe" if mode == "light" else "#1e3a5f"};
    color: {"#1d4ed8" if mode == "light" else "#bfdbfe"};
    border: 1px solid {"#bfdbfe" if mode == "light" else "#2f5f9f"};
    border-radius: 5px;
    padding: 3px 7px;
    font-size: 11px;
    font-weight: 700;
}}

QTextBrowser#message-body, QTextBrowser#draft-box {{
    background-color: {input_bg};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 8px;
}}

QPushButton#primary-btn {{
    background-color: {c["accent"]};
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 800;
}}

QPushButton#primary-btn:hover {{
    background-color: {c["accent_hover"]};
}}

QPushButton#primary-btn:disabled {{
    background-color: #8da8d8;
}}

QPushButton#secondary-btn {{
    background-color: {input_bg};
    color: {c["content_text"]};
    border: 1px solid {c["border"]};
    border-radius: 8px;
    padding: 8px 16px;
}}

QPushButton#secondary-btn:hover {{
    background-color: {hover_bg};
}}

QPushButton#danger-btn {{
    background-color: {input_bg};
    color: {c["danger"]};
    border: 1px solid {c["danger"]};
    border-radius: 8px;
    padding: 8px 16px;
}}

QWidget#login-root {{
    background-color: {login_root};
}}

QWidget#login-card {{
    background-color: {login_card};
    border: 1px solid {c["border"]};
    border-radius: 14px;
}}

QWidget#login-logo-panel {{
    background-color: #071833;
    border-radius: 10px;
}}

QLabel#login-logo {{
    background-color: transparent;
    min-width: 138px;
    max-width: 138px;
    min-height: 40px;
    max-height: 40px;
}}

QLabel#login-logo-tagline {{
    background-color: transparent;
    color: #8fa6c8;
    font-size: 9px;
}}

QLabel#login-title {{
    background-color: transparent;
    font-size: 27px;
    font-weight: 800;
    color: {c["content_text"]};
}}

QLabel#login-subtitle, QLabel#login-footnote {{
    background-color: transparent;
    font-size: 13px;
    color: {muted};
}}

QLabel#login-field-label {{
    background-color: transparent;
    color: {c["content_text"]};
    font-size: 12px;
    font-weight: 800;
    padding-top: 4px;
}}

QLineEdit#login-field {{
    background-color: {input_bg};
    border: 1px solid {field_border};
    border-radius: 9px;
    padding: 11px 12px;
    font-size: 14px;
    color: {c["content_text"]};
    min-height: 22px;
}}

QCheckBox {{
    background-color: transparent;
    color: {c["content_text"]};
    spacing: 7px;
}}

QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {field_border};
    border-radius: 4px;
    background-color: {input_bg};
}}

QCheckBox::indicator:checked {{
    background-color: {c["accent"]};
    border-color: {c["accent"]};
}}

QPushButton#link-btn {{
    color: {c["accent"]};
    font-size: 12px;
    background: transparent;
    border: none;
    padding: 2px 4px;
    text-decoration: underline;
}}

QFrame#login-divider {{
    color: {c["border"]};
    background-color: {c["border"]};
    max-height: 1px;
}}

QScrollBar:vertical {{
    background: {c["content_bg"]};
    width: 9px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {"#c2cad8" if mode == "light" else "#334155"};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QLabel#badge-urgency-1 {{ background-color: #dcfce7; color: #166534; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 800; }}
QLabel#badge-urgency-2 {{ background-color: #ccfbf1; color: #0f766e; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 800; }}
QLabel#badge-urgency-3 {{ background-color: #fef3c7; color: #92400e; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 800; }}
QLabel#badge-urgency-4 {{ background-color: #ffedd5; color: #c2410c; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 800; }}
QLabel#badge-urgency-5 {{ background-color: #fee2e2; color: #b91c1c; border-radius: 5px; padding: 2px 7px; font-size: 11px; font-weight: 800; }}
QLabel#badge-status {{ background-color: {selected_bg}; color: {c["content_text"]}; border-radius: 5px; padding: 2px 7px; font-size: 11px; }}
QLabel#badge-needs-review {{ background-color: #dc2626; color: #ffffff; border-radius: 5px; padding: 2px 6px; font-size: 10px; font-weight: 800; }}

/* ── Needs Review banner (detail panel) ── */
QWidget#needs-review-banner {{ background-color: {"#fef2f2" if mode == "light" else "#3f1212"}; border: 1px solid {"#fecaca" if mode == "light" else "#7f1d1d"}; border-radius: 8px; }}
QWidget#needs-review-banner QLabel {{ background-color: transparent; }}
QLabel#needs-review-banner-text {{ color: {"#991b1b" if mode == "light" else "#fca5a5"}; font-size: 13px; font-weight: 800; background: transparent; }}

/* ── Risk flag chips (high-risk, red) ── */
QLabel#risk-chip {{ background-color: {"#fee2e2" if mode == "light" else "#3f1212"}; color: {"#991b1b" if mode == "light" else "#fca5a5"}; border: 1px solid {"#fecaca" if mode == "light" else "#7f1d1d"}; border-radius: 5px; padding: 3px 7px; font-size: 11px; font-weight: 800; }}
QLabel#risk-flags-label {{ color: {"#991b1b" if mode == "light" else "#fca5a5"}; font-size: 12px; font-weight: 700; background: transparent; }}

/* ── Sidebar custom nav items ── */
QWidget#nav-item {{ background-color: transparent; border-radius: 8px; }}
QWidget#nav-item:hover {{ background-color: {c["sidebar_hover"]}; }}
QWidget#nav-item[active="true"] {{ background-color: {c["sidebar_active"]}; }}
QLabel#nav-icon {{ color: {c["sidebar_muted"]}; background: transparent; font-size: 14px; }}
QLabel#nav-label {{ color: {c["sidebar_text"]}; background: transparent; font-size: 13px; }}
QLabel#nav-count {{ background-color: rgba(255,255,255,0.15); color: #ffffff; border-radius: 10px; font-size: 10px; font-weight: 800; padding: 1px 7px; min-width: 22px; }}
QLabel#sidebar-section-header {{ color: {c["sidebar_muted"]}; font-size: 10px; font-weight: 800; letter-spacing: 1px; padding: 10px 12px 3px 12px; background: transparent; }}
QLabel#sidebar-footnote {{ color: {c["sidebar_muted"]}; font-size: 11px; padding: 3px 12px; background: transparent; }}
QLabel#user-name-lbl {{ color: #ffffff; font-size: 12px; font-weight: 700; background: transparent; }}
QLabel#user-role-lbl {{ color: {c["sidebar_muted"]}; font-size: 11px; background: transparent; }}
QLabel#waldorf-label {{ color: {c["sidebar_muted"]}; font-size: 9px; font-weight: 800; letter-spacing: 2px; background: transparent; padding-bottom: 1px; }}
QLabel#waldorf-mark {{ color: #ffffff; font-family: Georgia, 'Times New Roman', serif; font-size: 24px; font-weight: 500; background: transparent; padding: 2px 0; }}
QLabel#waldorf-sub {{ color: {c["sidebar_muted"]}; font-size: 8px; letter-spacing: 1px; background: transparent; }}

/* ── Conversation list rows ── */
QWidget#conversation-row QLabel {{ background-color: transparent; }}
QWidget#conversation-row[selected="true"] {{ background-color: {selected_bg}; border-left: 2px solid {selected_border}; }}
QLabel#row-sender {{ font-weight: 700; font-size: 13px; color: {c["content_text"]}; background: transparent; }}
QLabel#row-subject {{ font-size: 12px; font-weight: 600; color: {c["content_text"]}; background: transparent; }}
QLabel#row-meta, QLabel#row-preview {{ color: {muted}; font-size: 11px; background: transparent; }}
QLabel#row-time {{ color: {muted}; font-size: 11px; background: transparent; }}
QLabel#row-chip {{ background-color: {"#eef2ff" if mode == "light" else "#1e2d4e"}; color: {"#4f46e5" if mode == "light" else "#a5b4fc"}; border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: 700; }}
QLabel#unread-dot {{ background-color: {c["accent"]}; border-radius: 5px; min-width: 10px; max-width: 10px; min-height: 10px; max-height: 10px; }}
QWidget#list-header {{ background-color: {c["panel_bg"]}; border-bottom: 1px solid {c["border"]}; }}
QLabel#list-count-lbl {{ font-size: 12px; font-weight: 700; color: {c["content_text"]}; background: transparent; }}
QComboBox#sort-combo {{ font-size: 12px; border-radius: 5px; padding: 2px 6px; }}

/* ── Filter bar ── */
QLabel#sync-status-lbl {{ color: {muted}; font-size: 10px; background: transparent; padding-right: 4px; }}

/* KYC Auto popup */
QWidget#kyc-window {{
    background-color: #07101f;
}}

QLabel#kyc-title {{
    background-color: transparent;
    color: #f8fafc;
    font-size: 22px;
    font-weight: 850;
}}

QLabel#kyc-subtitle, QLabel#kyc-body, QLabel#kyc-field-label {{
    background-color: transparent;
    color: #d8e3f5;
    font-size: 13px;
}}

QGroupBox#kyc-card {{
    background-color: #0b1425;
    color: #f8fafc;
    border: 1px solid #24324a;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 800;
}}

QGroupBox#kyc-card::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #f8fafc;
    background-color: #07101f;
}}

QLabel#kyc-state {{
    background-color: transparent;
    color: #cbd5e1;
    font-size: 13px;
    font-weight: 900;
}}

QLabel#kyc-state[state="overdue"] {{
    color: #f87171;
}}

QLabel#kyc-state[state="running"] {{
    color: #34d399;
}}

QLabel#kyc-body[tone="success"] {{
    color: #34d399;
}}

QLabel#kyc-body[tone="danger"] {{
    color: #f87171;
}}

QLabel#kyc-body[tone="neutral"] {{
    color: #bfdbfe;
}}

QSpinBox {{
    background-color: {input_bg};
    color: {c["content_text"]};
    border: 1px solid {field_border};
    border-radius: 7px;
    padding: 5px 8px;
}}

QTableWidget {{
    background-color: #08111f;
    color: #e5edf9;
    border: 1px solid #24324a;
    gridline-color: #24324a;
    alternate-background-color: #08111f;
    selection-background-color: #10233f;
}}

QHeaderView::section {{
    background-color: #111827;
    color: #e5edf9;
    border: none;
    border-right: 1px solid #24324a;
    padding: 5px 7px;
    font-weight: 700;
}}
"""


STYLESHEET = get_stylesheet("light")
