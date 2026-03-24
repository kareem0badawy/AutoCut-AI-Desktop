from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QTextEdit, QComboBox, QGroupBox, QMessageBox,
    QSplitter, QPlainTextEdit,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_style, save_style, load_config, BASE_DIR


class StylePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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

        title = QLabel("Style Settings")
        title.setObjectName("heading")
        layout.addWidget(title)

        desc = QLabel(
            "Control the visual identity of your AI-generated images. "
            "Settings are saved to style_config.json."
        )
        desc.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._style_group())
        layout.addWidget(self._template_group())

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Style")
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

    def _style_group(self):
        group = QGroupBox("Visual Style Configuration")
        layout = QVBoxLayout(group)
        layout.setSpacing(16)

        self._style_lock = self._multiline_field(layout, "Style Lock (applied to every scene)",
            "Describe the consistent visual style applied to all generated images")
        self._negative_prompt = self._multiline_field(layout, "Negative Prompt",
            "Elements to exclude from all generated images")
        self._mood = self._single_field(layout, "Mood", "dramatic, historical, documentary, somber")
        self._label_style = self._single_field(layout, "Label Style", "bold rubber stamp uppercase text")

        ar_row = QHBoxLayout()
        ar_label = QLabel("Aspect Ratio")
        ar_label.setObjectName("label")
        ar_label.setFixedWidth(180)
        self._aspect_ratio = QComboBox()
        self._aspect_ratio.addItems(["16:9", "9:16", "1:1", "4:3", "3:4"])
        self._aspect_ratio.setFixedWidth(160)
        ar_row.addWidget(ar_label)
        ar_row.addWidget(self._aspect_ratio)
        ar_row.addStretch()
        layout.addLayout(ar_row)

        return group

    def _template_group(self):
        group = QGroupBox("Prompts Template")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        note = QLabel(
            "This template is sent to the AI to generate scene descriptions. "
            "It uses {placeholders} for dynamic values. Edit carefully."
        )
        note.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._template_edit = QPlainTextEdit()
        self._template_edit.setMinimumHeight(300)
        self._template_edit.setPlaceholderText("Prompts template content...")
        layout.addWidget(self._template_edit)

        row = QHBoxLayout()
        load_btn = QPushButton("Load Template from File")
        load_btn.setObjectName("secondary")
        load_btn.clicked.connect(self._load_template)
        save_tmpl_btn = QPushButton("Save Template to File")
        save_tmpl_btn.setObjectName("secondary")
        save_tmpl_btn.clicked.connect(self._save_template)
        row.addWidget(load_btn)
        row.addWidget(save_tmpl_btn)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _multiline_field(self, layout, label_text, placeholder=""):
        lbl = QLabel(label_text)
        lbl.setObjectName("label")
        layout.addWidget(lbl)
        edit = QTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMaximumHeight(100)
        layout.addWidget(edit)
        return edit

    def _single_field(self, layout, label_text, placeholder=""):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setObjectName("label")
        lbl.setFixedWidth(180)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        row.addWidget(lbl)
        row.addWidget(edit)
        layout.addLayout(row)
        return edit

    def _load(self):
        style = load_style()
        self._style_lock.setPlainText(style.get("style_lock", ""))
        self._negative_prompt.setPlainText(style.get("negative_prompt", ""))
        self._mood.setText(style.get("mood", ""))
        self._label_style.setText(style.get("label_style", ""))
        idx = self._aspect_ratio.findText(style.get("aspect_ratio", "16:9"))
        if idx >= 0:
            self._aspect_ratio.setCurrentIndex(idx)

        tmpl_path = BASE_DIR / "prompts_template.txt"
        if tmpl_path.exists():
            with open(tmpl_path, "r", encoding="utf-8") as f:
                self._template_edit.setPlainText(f.read())

    def _save(self):
        style = {
            "style_lock": self._style_lock.toPlainText().strip(),
            "negative_prompt": self._negative_prompt.toPlainText().strip(),
            "mood": self._mood.text().strip(),
            "label_style": self._label_style.text().strip(),
            "aspect_ratio": self._aspect_ratio.currentText(),
        }
        save_style(style)
        self._save_template()
        QMessageBox.information(self, "Saved", "Style settings saved to style_config.json")

    def _save_template(self):
        tmpl_path = BASE_DIR / "prompts_template.txt"
        with open(tmpl_path, "w", encoding="utf-8") as f:
            f.write(self._template_edit.toPlainText())

    def _load_template(self):
        tmpl_path = BASE_DIR / "prompts_template.txt"
        if tmpl_path.exists():
            with open(tmpl_path, "r", encoding="utf-8") as f:
                self._template_edit.setPlainText(f.read())

    def _reset(self):
        from app.core.config_manager import DEFAULT_STYLE
        reply = QMessageBox.question(self, "Reset Style",
            "Reset all style settings to defaults?",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._style_lock.setPlainText(DEFAULT_STYLE["style_lock"])
            self._negative_prompt.setPlainText(DEFAULT_STYLE["negative_prompt"])
            self._mood.setText(DEFAULT_STYLE["mood"])
            self._label_style.setText(DEFAULT_STYLE["label_style"])

    def refresh(self):
        self._load()
