COLORS = {
    "bg": "#0d0d0d",
    "surface": "#141414",
    "surface2": "#1e1e1e",
    "surface3": "#252525",
    "border": "#2a2a2a",
    "accent": "#4fc3f7",
    "accent_dark": "#0288d1",
    "success": "#66bb6a",
    "error": "#ef5350",
    "warning": "#ffa726",
    "text": "#f0f0f0",
    "text_sec": "#888888",
    "text_dim": "#555555",
    "sidebar": "#111111",
    "sidebar_hover": "#1a1a1a",
    "sidebar_active": "#1e2d3d",
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLORS['bg']};
    color: {COLORS['text']};
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
}}

QWidget#sidebar {{
    background-color: {COLORS['sidebar']};
    border-right: 1px solid {COLORS['border']};
}}

QPushButton#nav_btn {{
    background: transparent;
    color: {COLORS['text_sec']};
    border: none;
    text-align: left;
    padding: 10px 20px 10px 20px;
    font-size: 13px;
    border-radius: 0px;
}}
QPushButton#nav_btn:hover {{
    background-color: {COLORS['sidebar_hover']};
    color: {COLORS['text']};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {COLORS['sidebar_active']};
    color: {COLORS['accent']};
    border-left: 3px solid {COLORS['accent']};
}}

QLabel#heading {{
    font-size: 22px;
    font-weight: bold;
    color: {COLORS['text']};
}}
QLabel#subheading {{
    font-size: 15px;
    font-weight: bold;
    color: {COLORS['text']};
}}
QLabel#label {{
    color: {COLORS['text_sec']};
    font-size: 12px;
}}
QLabel#badge_success {{
    background-color: #1b3a1f;
    color: {COLORS['success']};
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}}
QLabel#badge_error {{
    background-color: #3a1b1b;
    color: {COLORS['error']};
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}}
QLabel#badge_warning {{
    background-color: #3a2e1b;
    color: {COLORS['warning']};
    border-radius: 3px;
    padding: 2px 8px;
    font-size: 11px;
}}

QWidget#card {{
    background-color: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
}}
QWidget#card_dark {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {COLORS['surface2']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 5px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: {COLORS['accent_dark']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS['accent']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    color: {COLORS['text']};
    selection-background-color: {COLORS['accent_dark']};
}}

QPushButton#primary {{
    background-color: {COLORS['accent']};
    color: #000000;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton#primary:hover {{
    background-color: #81d4fa;
}}
QPushButton#primary:pressed {{
    background-color: {COLORS['accent_dark']};
}}
QPushButton#primary:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_dim']};
}}

QPushButton#success {{
    background-color: {COLORS['success']};
    color: #000000;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton#success:hover {{
    background-color: #81c784;
}}
QPushButton#success:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_dim']};
}}

QPushButton#danger {{
    background-color: #3a1b1b;
    color: {COLORS['error']};
    border: 1px solid {COLORS['error']};
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
}}
QPushButton#danger:hover {{
    background-color: #4a2020;
}}

QPushButton#secondary {{
    background-color: {COLORS['surface2']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
}}
QPushButton#secondary:hover {{
    background-color: {COLORS['surface3']};
    border-color: {COLORS['accent']};
}}
QPushButton#secondary:disabled {{
    color: {COLORS['text_dim']};
}}

QProgressBar {{
    background-color: {COLORS['surface2']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 4px;
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLORS['surface']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {COLORS['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLORS['text_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {COLORS['surface']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {COLORS['border']};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLORS['text_dim']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QTabWidget::pane {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    background: {COLORS['surface']};
}}
QTabBar::tab {{
    background: {COLORS['surface2']};
    color: {COLORS['text_sec']};
    border: 1px solid {COLORS['border']};
    border-bottom: none;
    padding: 8px 18px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {COLORS['surface']};
    color: {COLORS['accent']};
    border-bottom: 2px solid {COLORS['accent']};
}}
QTabBar::tab:hover {{
    background: {COLORS['surface3']};
    color: {COLORS['text']};
}}

QSplitter::handle {{
    background: {COLORS['border']};
}}

QCheckBox {{
    color: {COLORS['text']};
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid {COLORS['border']};
    background: {COLORS['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 8px;
    color: {COLORS['text_sec']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: {COLORS['text_sec']};
}}

QToolTip {{
    background-color: {COLORS['surface3']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
