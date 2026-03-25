from app.i18n import lang_manager

# ─── Brand Identity Palette ───────────────────────────────────────────────────
# Primary blues: #133B61 → #236192 → #007ACC → #5A9BD5 → #9CDAF1 → #D8EAF8
# Gold accent:   #d4a329 (primary), #abc406 (light)
# ─────────────────────────────────────────────────────────────────────────────

DARK = {
    "bg":            "#030d1c",
    "surface":       "#071828",
    "surface2":      "#0c2035",
    "surface3":      "#112a45",
    "border":        "#1a3a5c",
    "border2":       "#1e4a72",
    "accent":        "#007ACC",
    "accent_hover":  "#5A9BD5",
    "accent_dim":    "#236192",
    "success":       "#22c55e",
    "success_bg":    "#052e16",
    "error":         "#ef4444",
    "error_bg":      "#2d0a0a",
    "warning":       "#d4a329",
    "warning_bg":    "#2d2000",
    "text":          "#EAF4FF",
    "text_sec":      "#9CDAF1",
    "text_dim":      "#236192",
    "sidebar":       "#020c18",
    "sidebar_hover": "#071828",
    "sidebar_active":"#0c2d50",
    "drop_bg":       "#071828",
    "drop_border":   "#1e4a72",
    "drop_hover":    "#0c2035",
    "gold":          "#d4a329",
    "gold_light":    "#efc84a",
}

LIGHT = {
    "bg":           "#EBF5FF",
    "surface":      "#ffffff",
    "surface2":     "#D8EAF8",
    "surface3":     "#c2daf0",
    "border":       "#9CDAF1",
    "border2":      "#5A9BD5",
    "accent":       "#007ACC",
    "accent_hover": "#236192",
    "accent_dim":   "#133B61",
    "success":      "#16a34a",
    "success_bg":   "#f0fdf4",
    "error":        "#dc2626",
    "error_bg":     "#fef2f2",
    "warning":      "#d4a329",
    "warning_bg":   "#fffbeb",
    "text":         "#133B61",
    "text_sec":     "#236192",
    "text_dim":     "#5A9BD5",
    "sidebar":      "#133B61",
    "sidebar_hover":"#1a4a78",
    "sidebar_active":"#007ACC",
    "drop_bg":      "#EBF5FF",
    "drop_border":  "#9CDAF1",
    "drop_hover":   "#D8EAF8",
    "gold":         "#d4a329",
    "gold_light":   "#efc84a",
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
    font-family: "Cairo", "Segoe UI", "Tajawal", "Arial", sans-serif;
    font-size: 14px;
    font-weight: 700;
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
    padding: 12px 18px;
    font-size: 13px;
    font-weight: 700;
    border-radius: 0px;
}}
QPushButton#nav_btn:hover {{
    background-color: {C['sidebar_hover']};
    color: {C['text']};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {C['sidebar_active']};
    color: {C['accent_hover']};
    border-left: 3px solid {C['gold']};
    font-weight: 700;
}}

QLabel#heading {{
    font-size: 26px;
    font-weight: 700;
    color: {C['text']};
    background: transparent;
}}
QLabel#subheading {{
    font-size: 16px;
    font-weight: 700;
    color: {C['text']};
    background: transparent;
}}
QLabel#label {{
    color: {C['text_sec']};
    font-size: 13px;
    background: transparent;
}}
QLabel#section_title {{
    font-size: 11px;
    font-weight: 700;
    color: {C['text_dim']};
    letter-spacing: 1px;
    background: transparent;
}}

QWidget#card {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 16px;
}}
QWidget#card_dark {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 12px;
}}
QWidget#step_card {{
    background-color: {C['surface']};
    border: 1px solid {C['border2']};
    border-radius: 16px;
}}
QWidget#step_card_active {{
    background-color: {C['surface']};
    border: 2px solid {C['accent']};
    border-radius: 16px;
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
    font-weight: 700;
    selection-background-color: {C['accent_dim']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1.5px solid {C['accent']};
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
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent_hover']});
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-weight: 700;
    font-size: 14px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent_hover']}, stop:1 #9CDAF1);
}}
QPushButton#primary:pressed {{
    background-color: {C['accent_dim']};
}}
QPushButton#primary:disabled {{
    background: {C['surface2']};
    color: {C['text_dim']};
    border: 1px solid {C['border']};
}}

QPushButton#success_btn {{
    background-color: {C['success']};
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 10px 24px;
    font-weight: 700;
    font-size: 14px;
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
        stop:0 {C['gold']}, stop:1 {C['gold_light']});
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 14px 32px;
    font-weight: 700;
    font-size: 15px;
}}
QPushButton#export_btn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['gold_light']}, stop:1 #f5d876);
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
    font-size: 13px;
    font-weight: 700;
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
    font-weight: 700;
}}
QPushButton#icon_btn:hover {{
    background-color: {C['surface3']};
    color: {C['text']};
}}

QProgressBar {{
    background-color: {C['surface2']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent']}, stop:1 {C['accent_hover']});
    border-radius: 6px;
}}
QProgressBar[big="true"] {{
    height: 20px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
}}
QProgressBar[big="true"]::chunk {{
    border-radius: 10px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {C['accent_dim']}, stop:0.4 {C['accent']},
        stop:0.8 {C['accent_hover']}, stop:1 {C['gold']});
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
    background: {C['accent']};
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
    background: {C['accent']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 12px;
    background: {C['surface']};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {C['text_sec']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 20px;
    margin-right: 4px;
    font-size: 13px;
    font-weight: 700;
}}
QTabBar::tab:selected {{
    color: {C['accent_hover']};
    border-bottom: 2px solid {C['gold']};
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{
    color: {C['text']};
}}

QCheckBox {{
    color: {C['text']};
    spacing: 8px;
    background: transparent;
    font-weight: 700;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
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
    border-radius: 12px;
    margin-top: 16px;
    padding-top: 10px;
    color: {C['text_sec']};
    font-size: 11px;
    font-weight: 700;
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
    border-radius: 12px;
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
    font-weight: 700;
}}

QToolTip {{
    background-color: {C['accent_dim']};
    color: #EAF4FF;
    border: 1px solid {C['accent']};
    padding: 5px 10px;
    border-radius: 6px;
    font-weight: 700;
}}

QSplitter::handle {{
    background: {C['border']};
}}
"""
