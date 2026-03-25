from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame, QApplication,
    QComboBox, QAbstractSpinBox,
)

from app.i18n import lang_manager, t
from app.gui.theme import build_stylesheet, get_colors
from app.gui.panels.dashboard import DashboardPanel
from app.gui.panels.settings_panel import SettingsPanel
from app.gui.panels.style_panel import StylePanel
from app.gui.panels.pipeline_panel import PipelinePanel
from app.gui.panels.outputs_panel import OutputsPanel


NAV_KEYS = [
    "nav_dashboard",
    "nav_settings",
    "nav_style",
    "nav_pipeline",
    "nav_outputs",
]

NAV_ICONS = ["⊞", "⚙", "🎨", "▶", "📊"]


class GlobalScrollBlocker(QObject):
    """
    Application-level event filter that prevents accidental value changes
    when the user scrolls over a ComboBox (dropdown closed) or SpinBox
    (no keyboard focus). Installed once on QApplication — affects ALL widgets.
    """
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Wheel:
            if isinstance(watched, QComboBox):
                # Allow scroll only if the popup list is open
                if not watched.view().isVisible():
                    event.ignore()
                    return True
            elif isinstance(watched, QAbstractSpinBox):
                # Allow scroll only if the widget has keyboard focus
                if not watched.hasFocus():
                    event.ignore()
                    return True
        return super().eventFilter(watched, event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(1100, 700)
        self.resize(1300, 820)
        self._current_index = 0
        self._nav_buttons = []
        self._sidebar_labels = {}

        # Install global scroll blocker on the application
        app = QApplication.instance()
        self._scroll_blocker = GlobalScrollBlocker(app)
        app.installEventFilter(self._scroll_blocker)

        lang_manager.language_changed.connect(self._on_lang_changed)
        lang_manager.theme_changed.connect(self._on_theme_changed)

        self._apply_theme()
        self._build_ui()
        self._set_active(0)

    def _apply_theme(self):
        self.setStyleSheet(build_stylesheet(lang_manager.theme))
        self.setWindowTitle(t("app_name") + " — " + t("tagline"))

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar_widget = self._build_sidebar()
        root_layout.addWidget(self._sidebar_widget)

        self._stack = QStackedWidget()
        self._panels = [
            DashboardPanel(),
            SettingsPanel(),
            StylePanel(),
            PipelinePanel(),
            OutputsPanel(),
        ]
        for panel in self._panels:
            self._stack.addWidget(panel)

        root_layout.addWidget(self._stack, 1)
        self.setCentralWidget(root)

    def _build_sidebar(self):
        C = get_colors()
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(
            f"background: {C['sidebar']}; border-bottom: 1px solid {C['border']};"
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 20, 18, 16)
        header_layout.setSpacing(3)

        logo = QLabel(t("app_name"))
        logo.setStyleSheet(
            f"color: {C['gold']}; font-size: 22px; font-weight: 700; background: transparent; font-family: Cairo, Segoe UI, Arial;"
        )
        tagline = QLabel(t("tagline"))
        tagline.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; background: transparent;"
        )
        tagline.setWordWrap(True)
        header_layout.addWidget(logo)
        header_layout.addWidget(tagline)
        self._sidebar_labels["logo"] = logo
        self._sidebar_labels["tagline"] = tagline
        layout.addWidget(header)

        layout.addSpacing(12)

        section = QLabel("  " + t("menu_label"))
        section.setObjectName("section_title")
        section.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; letter-spacing: 1px; "
            f"padding: 4px 0; background: transparent;"
        )
        self._sidebar_labels["menu"] = section
        layout.addWidget(section)
        layout.addSpacing(4)

        self._nav_buttons = []
        for i, (key, icon) in enumerate(zip(NAV_KEYS, NAV_ICONS)):
            btn = QPushButton(f"  {icon}  {t(key)}")
            btn.setObjectName("nav_btn")
            btn.setFixedHeight(42)
            btn.clicked.connect(lambda checked, idx=i: self._set_active(idx))
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {C['border']};")
        layout.addWidget(sep)

        controls = QWidget()
        controls.setStyleSheet(f"background: {C['sidebar']};")
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setContentsMargins(14, 10, 14, 12)
        ctrl_layout.setSpacing(6)

        self._lang_btn = QPushButton(t("lang_toggle"))
        self._lang_btn.setObjectName("icon_btn")
        self._lang_btn.setFixedHeight(30)
        self._lang_btn.setToolTip("تبديل اللغة / Switch Language")
        self._lang_btn.clicked.connect(self._toggle_lang)

        self._theme_btn = QPushButton(t("theme_dark") if lang_manager.theme == "dark" else t("theme_light"))
        self._theme_btn.setObjectName("icon_btn")
        self._theme_btn.setFixedHeight(30)
        self._theme_btn.setFixedWidth(38)
        self._theme_btn.setToolTip("تبديل المظهر / Toggle Theme")
        self._theme_btn.clicked.connect(self._toggle_theme)

        ctrl_layout.addWidget(self._lang_btn, 1)
        ctrl_layout.addWidget(self._theme_btn)
        layout.addWidget(controls)

        ver = QLabel(f"  {t('version')}")
        ver.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; padding: 0 0 10px 0; background: transparent;")
        self._sidebar_labels["version"] = ver
        layout.addWidget(ver)

        return sidebar

    def _set_active(self, index):
        try:
            for i, btn in enumerate(self._nav_buttons):
                btn.setProperty("active", "true" if i == index else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            self._stack.setCurrentIndex(index)
            self._current_index = index
            panel = self._panels[index]
            if hasattr(panel, "refresh"):
                try:
                    panel.refresh()
                except Exception as e:
                    import traceback
                    print(f"[AutoCut] refresh error on panel {index}: {e}\n{traceback.format_exc()}")
        except Exception as e:
            import traceback
            print(f"[AutoCut] _set_active error: {e}\n{traceback.format_exc()}")

    def _toggle_lang(self):
        try:
            new_lang = "en" if lang_manager.lang == "ar" else "ar"
            lang_manager.set_lang(new_lang)
        except Exception as e:
            print(f"[AutoCut] lang toggle error: {e}")

    def _toggle_theme(self):
        try:
            new_theme = "light" if lang_manager.theme == "dark" else "dark"
            lang_manager.set_theme(new_theme)
        except Exception as e:
            print(f"[AutoCut] theme toggle error: {e}")

    def _on_lang_changed(self, lang: str):
        try:
            app = QApplication.instance()
            if lang == "ar":
                app.setLayoutDirection(Qt.RightToLeft)
            else:
                app.setLayoutDirection(Qt.LeftToRight)
            self._apply_theme()
            self._retranslate_sidebar()
            for panel in self._panels:
                if hasattr(panel, "retranslate"):
                    try:
                        panel.retranslate()
                    except Exception as e:
                        import traceback
                        print(f"[AutoCut] retranslate error: {e}\n{traceback.format_exc()}")
        except Exception as e:
            import traceback
            print(f"[AutoCut] _on_lang_changed error: {e}\n{traceback.format_exc()}")

    def _on_theme_changed(self, theme: str):
        try:
            self._apply_theme()
            icon = t("theme_dark") if theme == "dark" else t("theme_light")
            self._theme_btn.setText(icon)
            for panel in self._panels:
                if hasattr(panel, "retranslate"):
                    try:
                        panel.retranslate()
                    except Exception as e:
                        import traceback
                        print(f"[AutoCut] retranslate error: {e}\n{traceback.format_exc()}")
        except Exception as e:
            import traceback
            print(f"[AutoCut] _on_theme_changed error: {e}\n{traceback.format_exc()}")

    def _retranslate_sidebar(self):
        self._sidebar_labels["logo"].setText(t("app_name"))
        self._sidebar_labels["tagline"].setText(t("tagline"))
        self._sidebar_labels["menu"].setText("  " + t("menu_label"))
        self._sidebar_labels["version"].setText(f"  {t('version')}")
        self._lang_btn.setText(t("lang_toggle"))
        self._theme_btn.setText(t("theme_dark") if lang_manager.theme == "dark" else t("theme_light"))
        for i, (key, icon) in enumerate(zip(NAV_KEYS, NAV_ICONS)):
            self._nav_buttons[i].setText(f"  {icon}  {t(key)}")
        self._set_active(self._current_index)
