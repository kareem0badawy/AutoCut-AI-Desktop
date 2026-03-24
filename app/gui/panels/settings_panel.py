from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QSpinBox, QDoubleSpinBox, QComboBox, QFileDialog,
    QMessageBox, QGroupBox,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_config, save_config


class SettingsPanel(QWidget):
    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields = {}
        self._build_ui()
        self._load()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        title = QLabel("Project Settings")
        title.setObjectName("heading")
        layout.addWidget(title)

        desc = QLabel("Configure your API keys, file paths, and video parameters. All settings are saved to config.json.")
        desc.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._api_group())
        layout.addWidget(self._paths_group())
        layout.addWidget(self._video_group())

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("secondary")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _api_group(self):
        group = QGroupBox("API Keys")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        note = QLabel("Your API keys are stored locally in config.json and never shared.")
        note.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")
        layout.addWidget(note)

        self._fields["groq_api_key"] = self._field_row(layout, "Groq API Key", "gsk_...", password=True,
            tooltip="Get your free API key at console.groq.com")
        self._fields["hf_api_key"] = self._field_row(layout, "HuggingFace API Key", "hf_...", password=True,
            tooltip="Get your token at huggingface.co/settings/tokens")
        self._fields["gemini_api_key"] = self._field_row(layout, "Gemini API Key (optional)", "AIza...", password=True,
            tooltip="Optional — for future Gemini features")
        return group

    def _paths_group(self):
        group = QGroupBox("File Paths")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        self._fields["script_path"] = self._file_row(layout, "Script File (.txt)", "Select script file",
            filter="Text Files (*.txt)")
        self._fields["audio_path"] = self._file_row(layout, "Audio File", "Select audio file",
            filter="Audio Files (*.mp3 *.wav *.m4a)")
        self._fields["images_folder"] = self._folder_row(layout, "AI-Generated Images Folder",
            "Folder containing generated scene images")
        self._fields["output_folder"] = self._folder_row(layout, "Output Folder",
            "Where the final video will be saved")
        return group

    def _video_group(self):
        group = QGroupBox("Video Parameters")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        res_layout = QHBoxLayout()
        res_label = QLabel("Output Resolution")
        res_label.setObjectName("label")
        res_combo = QComboBox()
        res_combo.addItems(["1920x1080", "1280x720", "3840x2160", "1080x1920"])
        res_combo.setFixedWidth(200)
        self._fields["output_resolution"] = res_combo
        res_layout.addWidget(res_label)
        res_layout.addWidget(res_combo)
        res_layout.addStretch()
        layout.addLayout(res_layout)

        fps_layout = QHBoxLayout()
        fps_label = QLabel("FPS (Frames per second)")
        fps_label.setObjectName("label")
        fps_spin = QSpinBox()
        fps_spin.setRange(1, 60)
        fps_spin.setValue(24)
        fps_spin.setFixedWidth(100)
        self._fields["fps"] = fps_spin
        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(fps_spin)
        fps_layout.addStretch()
        layout.addLayout(fps_layout)

        spi_layout = QHBoxLayout()
        spi_label = QLabel("Seconds per Image")
        spi_label.setObjectName("label")
        spi_spin = QSpinBox()
        spi_spin.setRange(1, 60)
        spi_spin.setValue(7)
        spi_spin.setFixedWidth(100)
        self._fields["seconds_per_image"] = spi_spin
        spi_layout.addWidget(spi_label)
        spi_layout.addWidget(spi_spin)
        spi_layout.addStretch()
        layout.addLayout(spi_layout)

        dur_layout = QHBoxLayout()
        dur_label = QLabel("Audio Duration (minutes.seconds  e.g. 4.30)")
        dur_label.setObjectName("label")
        dur_edit = QLineEdit()
        dur_edit.setPlaceholderText("4.30")
        dur_edit.setFixedWidth(120)
        self._fields["audio_duration"] = dur_edit
        dur_layout.addWidget(dur_label)
        dur_layout.addWidget(dur_edit)
        dur_layout.addStretch()
        layout.addLayout(dur_layout)

        batch_layout = QHBoxLayout()
        batch_label = QLabel("Scenes per Batch")
        batch_label.setObjectName("label")
        batch_spin = QSpinBox()
        batch_spin.setRange(1, 50)
        batch_spin.setValue(10)
        batch_spin.setFixedWidth(100)
        self._fields["scenes_per_batch"] = batch_spin
        batch_layout.addWidget(batch_label)
        batch_layout.addWidget(batch_spin)
        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        trans_layout = QHBoxLayout()
        trans_label = QLabel("Transition Duration (seconds)")
        trans_label.setObjectName("label")
        trans_spin = QDoubleSpinBox()
        trans_spin.setRange(0.0, 3.0)
        trans_spin.setSingleStep(0.1)
        trans_spin.setValue(0.5)
        trans_spin.setFixedWidth(100)
        self._fields["transition_duration"] = trans_spin
        trans_layout.addWidget(trans_label)
        trans_layout.addWidget(trans_spin)
        trans_layout.addStretch()
        layout.addLayout(trans_layout)

        return group

    def _field_row(self, layout, label_text, placeholder="", password=False, tooltip=""):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("label")
        label.setFixedWidth(200)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if password:
            edit.setEchoMode(QLineEdit.Password)
        if tooltip:
            edit.setToolTip(tooltip)

        toggle = None
        if password:
            toggle = QPushButton("Show")
            toggle.setObjectName("secondary")
            toggle.setFixedWidth(60)
            toggle.setFixedHeight(32)
            toggle.clicked.connect(lambda checked, e=edit, b=toggle: self._toggle_password(e, b))

        row.addWidget(label)
        row.addWidget(edit)
        if toggle:
            row.addWidget(toggle)
        layout.addLayout(row)
        return edit

    def _toggle_password(self, edit, btn):
        if edit.echoMode() == QLineEdit.Password:
            edit.setEchoMode(QLineEdit.Normal)
            btn.setText("Hide")
        else:
            edit.setEchoMode(QLineEdit.Password)
            btn.setText("Show")

    def _file_row(self, layout, label_text, placeholder="", filter="All Files (*)"):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("label")
        label.setFixedWidth(200)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        browse = QPushButton("Browse")
        browse.setObjectName("secondary")
        browse.setFixedWidth(80)
        browse.clicked.connect(lambda: self._browse_file(edit, filter))
        row.addWidget(label)
        row.addWidget(edit)
        row.addWidget(browse)
        layout.addLayout(row)
        return edit

    def _folder_row(self, layout, label_text, placeholder=""):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("label")
        label.setFixedWidth(200)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        browse = QPushButton("Browse")
        browse.setObjectName("secondary")
        browse.setFixedWidth(80)
        browse.clicked.connect(lambda: self._browse_folder(edit))
        row.addWidget(label)
        row.addWidget(edit)
        row.addWidget(browse)
        layout.addLayout(row)
        return edit

    def _browse_file(self, edit, filter):
        path, _ = QFileDialog.getOpenFileName(self, "Select File", str(Path.home()), filter)
        if path:
            edit.setText(path)

    def _browse_folder(self, edit):
        path = QFileDialog.getExistingDirectory(self, "Select Folder", str(Path.home()))
        if path:
            edit.setText(path)

    def _get_field_value(self, key, widget):
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        elif isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return widget.value()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        return ""

    def _set_field_value(self, key, widget, value):
        if isinstance(widget, QLineEdit):
            widget.setText(str(value) if value else "")
        elif isinstance(widget, QSpinBox):
            try:
                widget.setValue(int(value))
            except (ValueError, TypeError):
                pass
        elif isinstance(widget, QDoubleSpinBox):
            try:
                widget.setValue(float(value))
            except (ValueError, TypeError):
                pass
        elif isinstance(widget, QComboBox):
            idx = widget.findText(str(value))
            if idx >= 0:
                widget.setCurrentIndex(idx)

    def _load(self):
        config = load_config()
        for key, widget in self._fields.items():
            self._set_field_value(key, widget, config.get(key, ""))

    def _save(self):
        config = load_config()
        for key, widget in self._fields.items():
            config[key] = self._get_field_value(key, widget)
        base = Path(__file__).resolve().parent.parent.parent.parent
        config["base_path"] = str(base)
        save_config(config)
        QMessageBox.information(self, "Saved", "Settings saved to config.json")
        self.settings_saved.emit()

    def _reset(self):
        from app.core.config_manager import DEFAULT_CONFIG
        reply = QMessageBox.question(self, "Reset Settings",
            "Reset all settings to defaults? (API keys will be cleared)",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for key, widget in self._fields.items():
                self._set_field_value(key, widget, DEFAULT_CONFIG.get(key, ""))

    def refresh(self):
        self._load()
