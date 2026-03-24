from app.i18n import lang_manager

DARK = {
    "bg":           "#030712",
    "surface":      "#0f172a",
    "surface2":     "#1e293b",
    "surface3":     "#263348",
    "border":       "#1e293b",
    "border2":      "#334155",
    "accent":       "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_dim":   "#1d4ed8",
    "success":      "#22c55e",
    "success_bg":   "#052e16",
    "error":        "#ef4444",
    "error_bg":     "#2d0a0a",
    "warning":      "#f59e0b",
    "warning_bg":   "#2d1f00",
    "text":         "#f8fafc",
    "text_sec":     "#94a3b8",
    "text_dim":     "#475569",
    "sidebar":      "#020617",
    "sidebar_hover":"#0f172a",
    "sidebar_active":"#1e3a5f",
    "drop_bg":      "#0f172a",
    "drop_border":  "#334155",
    "drop_hover":   "#1e293b",
}

LIGHT = {
    "bg":           "#f8fafc",
    "surface":      "#ffffff",
    "surface2":     "#f1f5f9",
    "surface3":     "#e2e8f0",
    "border":       "#e2e8f0",
    "border2":      "#cbd5e1",
    "accent":       "#2563eb",
    "accent_hover": "#3b82f6",
    "accent_dim":   "#1d4ed8",
    "success":      "#16a34a",
    "success_bg":   "#f0fdf4",
    "error":        "#dc2626",
    "error_bg":     "#fef2f2",
    "warning":      "#d97706",
    "warning_bg":   "#fffbeb",
    "text":         "#0f172a",
    "text_sec":     "#64748b",
    "text_dim":     "#94a3b8",
    "sidebar":      "#1e293b",
    "sidebar_hover":"#334155",
    "sidebar_active":"#1e3a8a",
    "drop_bg":      "#f8fafc",
    "drop_border":  "#94a3b8",
    "drop_hover":   "#eff6ff",
}


def get_colors():
    return DARK if lang_manager.theme == "dark" else LIGHT


def COLORS():
    return get_colors()


def build_stylesheet(theme: str = "dark") -> str:
    C = DARK if theme == "dark" else LIGHT
    return f"""
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: "Segoe UI", "Inter", "Tajawal", "Arial", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QWidget#sidebar {{
    background-color: {C['sidebar']};
    border-right: 1px solid {C['border']};
}}

QPushButton#nav_btn {{
    background: transparent;
    color: {C['text_sec']};
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 11px 18px;
    font-size: 13px;
    border-radius: 0px;
}}
QPushButton#nav_btn:hover {{
    background-color: {C['sidebar_hover']};
    color: {C['text']};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {C['sidebar_active']};
    color: {C['accent_hover']};
    border-left: 3px solid {C['accent']};
    font-weight: bold;
}}

QLabel#heading {{
    font-size: 24px;
    font-weight: bold;
    color: {C['text']};
    background: transparent;
}}
QLabel#subheading {{
    font-size: 15px;
    font-weight: 600;
    color: {C['text']};
    background: transparent;
}}
QLabel#label {{
    color: {C['text_sec']};
    font-size: 12px;
    background: transparent;
}}
QLabel#section_title {{
    font-size: 11px;
    font-weight: bold;
    color: {C['text_dim']};
    letter-spacing: 1px;
    background: transparent;
}}

QWidget#card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QWidget#card_dark {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QWidget#step_card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 14px;
}}
QWidget#step_card_active {{
    background-color: {C['surface']};
    border: 2px solid {C['accent']};
    border-radius: 14px;
}}
QWidget#drop_zone {{
    background-color: {C['drop_bg']};
    border: 2px dashed {C['drop_border']};
    border-radius: 14px;
}}
QWidget#drop_zone_hover {{
    background-color: {C['drop_hover']};
    border: 2px dashed {C['accent']};
    border-radius: 14px;
}}
QWidget#drop_zone_filled {{
    background-color: {C['success_bg']};
    border: 2px solid {C['success']};
    border-radius: 14px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {C['surface2']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    border-radius: 8px;
    padding: 7px 12px;
    font-size: 13px;
    selection-background-color: {C['accent_dim']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {C['accent']};
    background-color: {C['surface3']};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {C['surface3']};
    border: none;
    border-radius: 3px;
    width: 16px;
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
    background: transparent;
}}
QComboBox QAbstractItemView {{
    background-color: {C['surface2']};
    border: 1px solid {C['border2']};
    color: {C['text']};
    selection-background-color: {C['accent_dim']};
    border-radius: 8px;
    padding: 4px;
}}

QPushButton#primary {{
    background-color: {C['accent']};
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#primary:hover {{
    background-color: {C['accent_hover']};
}}
QPushButton#primary:pressed {{
    background-color: {C['accent_dim']};
}}
QPushButton#primary:disabled {{
    background-color: {C['surface3']};
    color: {C['text_dim']};
}}

QPushButton#success_btn {{
    background-color: {C['success']};
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 9px 22px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#success_btn:hover {{
    background-color: #4ade80;
}}
QPushButton#success_btn:disabled {{
    background-color: {C['surface3']};
    color: {C['text_dim']};
}}

QPushButton#export_btn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 #7c3aed);
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 14px 32px;
    font-weight: bold;
    font-size: 15px;
}}
QPushButton#export_btn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent_hover']}, stop:1 #8b5cf6);
}}
QPushButton#export_btn:disabled {{
    background: {C['surface3']};
    color: {C['text_dim']};
}}

QPushButton#secondary {{
    background-color: {C['surface2']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    border-radius: 9px;
    padding: 7px 18px;
    font-size: 12px;
}}
QPushButton#secondary:hover {{
    background-color: {C['surface3']};
    border-color: {C['accent']};
    color: {C['accent_hover']};
}}
QPushButton#secondary:disabled {{
    color: {C['text_dim']};
}}

QPushButton#icon_btn {{
    background-color: {C['surface2']};
    color: {C['text_sec']};
    border: 1px solid {C['border']};
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 14px;
}}
QPushButton#icon_btn:hover {{
    background-color: {C['surface3']};
    color: {C['text']};
}}

QProgressBar {{
    background-color: {C['surface2']};
    border: none;
    border-radius: 5px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {C['accent']};
    border-radius: 5px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C['border2']};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['text_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border2']};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C['text_dim']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    background: {C['surface']};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {C['text_sec']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 18px;
    margin-right: 4px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {C['accent_hover']};
    border-bottom: 2px solid {C['accent']};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    color: {C['text']};
}}

QCheckBox {{
    color: {C['text']};
    spacing: 8px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 5px;
    border: 1.5px solid {C['border2']};
    background: {C['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
}}

QGroupBox {{
    border: 1px solid {C['border']};
    border-radius: 10px;
    margin-top: 16px;
    padding-top: 10px;
    color: {C['text_sec']};
    font-size: 11px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 14px;
    color: {C['text_dim']};
    letter-spacing: 0.5px;
}}

QTreeWidget {{
    background: {C['surface2']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 10px;
    outline: none;
    alternate-background-color: {C['surface']};
}}
QTreeWidget::item {{
    padding: 5px 4px;
    border: none;
}}
QTreeWidget::item:selected {{
    background-color: {C['accent_dim']};
    color: white;
    border-radius: 4px;
}}
QTreeWidget::item:hover {{
    background-color: {C['surface3']};
}}
QHeaderView::section {{
    background-color: {C['surface']};
    color: {C['text_sec']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 6px 8px;
    font-size: 11px;
    font-weight: bold;
}}

QToolTip {{
    background-color: {C['surface3']};
    color: {C['text']};
    border: 1px solid {C['border2']};
    padding: 5px 10px;
    border-radius: 6px;
}}

QSplitter::handle {{
    background: {C['border']};
}}
"""
