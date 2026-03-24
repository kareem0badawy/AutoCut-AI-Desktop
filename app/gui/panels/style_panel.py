from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QFrame, QTextEdit, QComboBox, QMessageBox, QPlainTextEdit,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import make_separator
from app.core.config_manager import load_style, save_style, load_config, BASE_DIR


class StylePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fields = {}
        self._translatable: dict[str, QLabel | QPushButton] = {}
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

        title = QLabel(t("style_title"))
        title.setObjectName("heading")
        self._translatable["style_title"] = title
        layout.addWidget(title)

        desc = QLabel(t("style_desc"))
        desc.setStyleSheet(f"color: {C['text_sec']}; font-size: 13px; background: transparent;")
        desc.setWordWrap(True)
        self._translatable["style_desc"] = desc
        layout.addWidget(desc)

        layout.addWidget(self._style_card())
        layout.addWidget(self._template_card())

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton(t("save_style"))
        self._save_btn.setObjectName("primary")
        self._save_btn.setFixedHeight(40)
        self._save_btn.setFixedWidth(160)
        self._save_btn.clicked.connect(self._save)
        self._reset_btn = QPushButton(t("reset_defaults"))
        self._reset_btn.setObjectName("secondary")
        self._reset_btn.setFixedHeight(40)
        self._reset_btn.clicked.connect(self._reset)
        self._translatable["save_style"] = self._save_btn
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

    def _style_card(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        icon = QLabel("🎨")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("style_lock"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["style_lock"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(make_separator(C))

        fields = [
            ("style_lock", "style_lock_val", "line"),
            ("negative_prompt", "neg_prompt", "line"),
            ("mood", "mood", "line"),
            ("label_style", "label_style", "combo", ["Arabic white text", "English white text", "No label"]),
            ("aspect_ratio", "aspect_ratio", "combo", ["16:9", "9:16", "1:1", "4:3"]),
        ]
        for row in fields:
            cfg_key = row[0]
            label_key = row[1]
            kind = row[2]
            opts = row[3] if len(row) > 3 else []

            col = QVBoxLayout()
            col.setSpacing(5)
            lbl = QLabel(t(label_key))
            lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text_sec']}; background: transparent;")
            self._translatable[label_key] = lbl

            if kind == "line":
                w = QLineEdit()
                w.setFixedHeight(36)
            else:
                w = QComboBox()
                for o in opts:
                    w.addItem(o)
                w.setFixedHeight(36)

            self._fields[cfg_key] = w
            col.addWidget(lbl)
            col.addWidget(w)
            layout.addLayout(col)

        return card

    def _template_card(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        hdr = QHBoxLayout()
        icon = QLabel("📝")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("template_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["template_section"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()

        self._load_tmpl_btn = QPushButton(t("load_template"))
        self._load_tmpl_btn.setObjectName("secondary")
        self._load_tmpl_btn.setFixedHeight(30)
        self._load_tmpl_btn.clicked.connect(self._load_template_file)
        self._translatable["load_template"] = self._load_tmpl_btn
        hdr.addWidget(self._load_tmpl_btn)

        layout.addLayout(hdr)

        note = QLabel(t("template_note"))
        note.setStyleSheet(f"font-size: 11px; color: {C['text_dim']}; background: transparent; font-style: italic;")
        note.setWordWrap(True)
        self._translatable["template_note"] = note
        layout.addWidget(note)

        self._template_edit = QPlainTextEdit()
        self._template_edit.setMinimumHeight(200)
        self._template_edit.setStyleSheet(
            f"background: {C['surface2']}; color: {C['text_sec']}; "
            f"font-family: 'Consolas', monospace; font-size: 12px; "
            f"border-radius: 8px; border: 1px solid {C['border']};"
        )
        self._fields["template"] = self._template_edit
        layout.addWidget(self._template_edit)

        return card

    def _load(self):
        style = load_style()
        for key, widget in self._fields.items():
            if key == "template":
                widget.setPlainText(style.get("template", ""))
                continue
            val = style.get(key, "")
            if isinstance(widget, QLineEdit):
                widget.setText(str(val))
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)

    def _load_template_file(self):
        from PySide6.QtWidgets import QFileDialog
        from pathlib import Path
        path, _ = QFileDialog.getOpenFileName(self, t("load_template"), str(Path.home()), "Text Files (*.txt *.md);;All (*)")
        if path:
            try:
                self._template_edit.setPlainText(Path(path).read_text(encoding="utf-8"))
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _save(self):
        style = load_style()
        for key, widget in self._fields.items():
            if key == "template":
                style[key] = widget.toPlainText()
            elif isinstance(widget, QLineEdit):
                style[key] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                style[key] = widget.currentText()
        save_style(style)
        QMessageBox.information(self, t("saved_ok"), t("style_saved"))

    def _reset(self):
        if QMessageBox.question(self, t("reset_defaults"), t("reset_confirm")) == QMessageBox.Yes:
            from app.core.config_manager import DEFAULT_STYLE
            for key, widget in self._fields.items():
                if key == "template":
                    widget.setPlainText(DEFAULT_STYLE.get("template", ""))
                    continue
                val = DEFAULT_STYLE.get(key, "")
                if isinstance(widget, QLineEdit):
                    widget.setText(str(val))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)

    def refresh(self):
        self._load()

    def retranslate(self):
        for key, widget in self._translatable.items():
            if hasattr(widget, "setText"):
                widget.setText(t(key))
