from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QSizePolicy,
)

from app.gui.theme import COLORS, STYLESHEET
from app.gui.panels.dashboard import DashboardPanel
from app.gui.panels.settings_panel import SettingsPanel
from app.gui.panels.style_panel import StylePanel
from app.gui.panels.pipeline_panel import PipelinePanel
from app.gui.panels.assets_panel import AssetsPanel
from app.gui.panels.outputs_panel import OutputsPanel


NAV_ITEMS = [
    ("Dashboard", "⬛"),
    ("Project Settings", "⚙"),
    ("Style Settings", "🎨"),
    ("Pipeline Runner", "▶"),
    ("Assets Manager", "📁"),
    ("Outputs Viewer", "📊"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoCut — AI-Powered Video Generator")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)
        self._current_index = 0
        self._nav_buttons = []
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = self._build_sidebar()
        root_layout.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._panels = [
            DashboardPanel(),
            SettingsPanel(),
            StylePanel(),
            PipelinePanel(),
            AssetsPanel(),
            OutputsPanel(),
        ]

        for panel in self._panels:
            self._stack.addWidget(panel)

        root_layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)
        self._set_active(0)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background: {COLORS['sidebar']}; border-bottom: 1px solid {COLORS['border']};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 20, 20, 16)
        header_layout.setSpacing(4)

        logo = QLabel("AutoCut")
        logo.setStyleSheet(f"color: {COLORS['accent']}; font-size: 18px; font-weight: bold;")
        tagline = QLabel("AI Video Generator")
        tagline.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        header_layout.addWidget(logo)
        header_layout.addWidget(tagline)
        layout.addWidget(header)

        layout.addSpacing(8)

        section_label = QLabel("  MENU")
        section_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; letter-spacing: 1px; padding: 4px 0;")
        layout.addWidget(section_label)

        for i, (name, icon) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {icon}  {name}")
            btn.setObjectName("nav_btn")
            btn.setFixedHeight(40)
            btn.clicked.connect(lambda checked, idx=i: self._set_active(idx))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(sep)

        version = QLabel("  v1.0.0")
        version.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px; padding: 8px 0;")
        layout.addWidget(version)

        return sidebar

    def _set_active(self, index):
        for i, btn in enumerate(self._nav_buttons):
            btn.setProperty("active", "true" if i == index else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._stack.setCurrentIndex(index)
        self._current_index = index

        panel = self._panels[index]
        if hasattr(panel, "refresh"):
            panel.refresh()
