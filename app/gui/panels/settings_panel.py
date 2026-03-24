from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSpinBox, QDoubleSpinBox, QComboBox, QFileDialog,
    QMessageBox, QGroupBox,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import make_separator
from app.core.config_manager import load_config, save_config


class SettingsPanel(QWidget):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields = {}
        self._translatable: dict[str, QLabel | QPushButton | QGroupBox] = {}
        self._build_ui()
        self._load()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)

        C = get_colors()

        title = QLabel(t("settings_title"))
        title.setObjectName("heading")
        self._translatable["settings_title"] = title
        layout.addWidget(title)

        desc = QLabel(t("settings_desc"))
        desc.setStyleSheet(f"color: {C['text_sec']}; font-size: 13px; background: transparent;")
        desc.setWordWrap(True)
        self._translatable["settings_desc"] = desc
        layout.addWidget(desc)

        layout.addWidget(self._api_card())
        layout.addWidget(self._paths_card())
        layout.addWidget(self._video_card())

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton(t("save_settings"))
        self._save_btn.setObjectName("primary")
        self._save_btn.setFixedHeight(40)
        self._save_btn.setFixedWidth(160)
        self._save_btn.clicked.connect(self._save)

        self._reset_btn = QPushButton(t("reset_defaults"))
        self._reset_btn.setObjectName("secondary")
        self._reset_btn.setFixedHeight(40)
        self._reset_btn.clicked.connect(self._reset)

        self._translatable["save_settings"] = self._save_btn
        self._translatable["reset_defaults"] = self._reset_btn

        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _api_card(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        icon = QLabel("🔑")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("api_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["api_section"] = title

        note = QLabel(t("api_note"))
        note.setStyleSheet(
            f"font-size: 11px; color: {C['text_dim']}; background: {C['surface2']}; "
            f"border-radius: 6px; padding: 4px 10px;"
        )
        note.setWordWrap(True)
        self._translatable["api_note"] = note

        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(note)
        layout.addWidget(make_separator(C))

        for key, label_key in [("groq_api_key", "groq_key"), ("hf_api_key", "hf_key"), ("gemini_api_key", "gemini_key")]:
            layout.addLayout(self._api_row(key, label_key, C))

        return card

    def _api_row(self, cfg_key: str, label_key: str, C: dict) -> QHBoxLayout:
        row = QVBoxLayout()
        row.setSpacing(5)

        lbl = QLabel(t(label_key))
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text_sec']}; background: transparent;")
        self._translatable[label_key] = lbl

        line_row = QHBoxLayout()
        field = QLineEdit()
        field.setEchoMode(QLineEdit.Password)
        field.setPlaceholderText("sk-...")
        field.setFixedHeight(36)

        show_btn = QPushButton(t("show"))
        show_btn.setObjectName("secondary")
        show_btn.setFixedHeight(36)
        show_btn.setFixedWidth(72)

        def toggle(checked=False, f=field, b=show_btn):
            if f.echoMode() == QLineEdit.Password:
                f.setEchoMode(QLineEdit.Normal)
                b.setText(t("hide"))
            else:
                f.setEchoMode(QLineEdit.Password)
                b.setText(t("show"))

        show_btn.clicked.connect(toggle)
        self._translatable[f"show_{cfg_key}"] = show_btn

        line_row.addWidget(field, 1)
        line_row.addWidget(show_btn)
        self._fields[cfg_key] = field
        row.addWidget(lbl)
        row.addLayout(line_row)

        wrapper = QWidget()
        wrapper.setLayout(row)
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(wrapper)
        return h

    def _paths_card(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        icon = QLabel("📁")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("paths_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["paths_section"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(make_separator(C))

        paths = [
            ("script_path", "script_path", False),
            ("audio_path", "audio_path", False),
            ("images_folder", "images_folder", True),
            ("output_folder", "output_folder", True),
        ]
        for cfg_key, label_key, is_folder in paths:
            layout.addLayout(self._path_row(cfg_key, label_key, is_folder, C))

        return card

    def _path_row(self, cfg_key: str, label_key: str, is_folder: bool, C: dict) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(5)

        lbl = QLabel(t(label_key))
        lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text_sec']}; background: transparent;")
        self._translatable[label_key] = lbl

        row = QHBoxLayout()
        field = QLineEdit()
        field.setFixedHeight(36)
        field.setPlaceholderText("...")

        browse_btn = QPushButton(t("browse"))
        browse_btn.setObjectName("secondary")
        browse_btn.setFixedHeight(36)
        browse_btn.setFixedWidth(90)

        def pick(checked=False, f=field, folder=is_folder):
            if folder:
                p = QFileDialog.getExistingDirectory(self, "", f.text() or str(Path.home()))
            else:
                p, _ = QFileDialog.getOpenFileName(self, "", f.text() or str(Path.home()))
            if p:
                f.setText(p)

        browse_btn.clicked.connect(pick)
        self._translatable[f"browse_{cfg_key}"] = browse_btn
        self._fields[cfg_key] = field
        row.addWidget(field, 1)
        row.addWidget(browse_btn)
        col.addWidget(lbl)
        col.addLayout(row)
        return col

    def _video_card(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        icon = QLabel("🎬")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("video_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["video_section"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(make_separator(C))

        rows = [
            ("output_resolution", "resolution", "combo", ["1920x1080", "1280x720", "3840x2160", "720x1280"]),
            ("fps", "fps_label", "spin", (1, 120)),
            ("seconds_per_image", "spi_label", "dspin", (0.1, 60.0)),
            ("audio_duration", "duration_label", "line", []),
            ("scenes_per_batch", "batch_label", "spin", (1, 50)),
            ("transition_duration", "transition_label", "dspin", (0.0, 10.0)),
        ]
        for cfg_key, label_key, kind, opts in rows:
            col = QVBoxLayout()
            col.setSpacing(5)
            lbl = QLabel(t(label_key))
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text_sec']}; background: transparent;")
            self._translatable[label_key] = lbl

            if kind == "combo":
                w = QComboBox()
                for o in opts:
                    w.addItem(o)
                w.setFixedHeight(36)
            elif kind == "spin":
                w = QSpinBox()
                w.setRange(opts[0], opts[1])
                w.setFixedHeight(36)
            elif kind == "line":
                w = QLineEdit()
                w.setFixedHeight(36)
            else:
                w = QDoubleSpinBox()
                w.setRange(opts[0], opts[1])
                w.setSingleStep(0.1)
                w.setDecimals(2)
                w.setFixedHeight(36)

            self._fields[cfg_key] = w
            col.addWidget(lbl)
            col.addWidget(w)
            layout.addLayout(col)

        return card

    def _load(self):
        cfg = load_config()
        for key, widget in self._fields.items():
            val = cfg.get(key, "")
            if isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, (QSpinBox,)):
                try:
                    widget.setValue(int(val))
                except Exception:
                    pass
            elif isinstance(widget, QDoubleSpinBox):
                try:
                    widget.setValue(float(val))
                except Exception:
                    pass

    def _save(self):
        cfg = load_config()
        for key, widget in self._fields.items():
            if isinstance(widget, QLineEdit):
                cfg[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                cfg[key] = widget.currentText()
            elif isinstance(widget, (QSpinBox,)):
                cfg[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                cfg[key] = widget.value()
        save_config(cfg)
        QMessageBox.information(self, t("saved_ok"), t("saved_msg"))
        self.settings_saved.emit()

    def _reset(self):
        if QMessageBox.question(self, t("reset_defaults"), t("reset_confirm")) == QMessageBox.Yes:
            from app.core.config_manager import DEFAULT_CONFIG
            for key, widget in self._fields.items():
                val = DEFAULT_CONFIG.get(key, "")
                if isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                elif isinstance(widget, (QSpinBox,)):
                    try:
                        widget.setValue(int(val))
                    except Exception:
                        pass
                elif isinstance(widget, QDoubleSpinBox):
                    try:
                        widget.setValue(float(val))
                    except Exception:
                        pass

    def refresh(self):
        self._load()

    def retranslate(self):
        for key, widget in self._translatable.items():
            if hasattr(widget, "setText"):
                try:
                    widget.setText(t(key))
                except Exception:
                    pass
