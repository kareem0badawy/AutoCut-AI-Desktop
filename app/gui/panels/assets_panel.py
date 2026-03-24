import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QGroupBox, QTabWidget, QPlainTextEdit, QMessageBox,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_config, save_config


class AssetsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Assets Manager")
        title.setObjectName("heading")
        layout.addWidget(title)

        desc = QLabel("View and manage your project assets — script, audio, and images.")
        desc.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        layout.addWidget(desc)

        tabs = QTabWidget()
        tabs.addTab(self._script_tab(), "Script")
        tabs.addTab(self._audio_tab(), "Audio")
        tabs.addTab(self._images_tab(), "Images")
        layout.addWidget(tabs, 1)

    def _script_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        config = load_config()
        script_path = config.get("script_path", "")

        self._script_path_label = QLabel(f"File: {script_path or 'Not set'}")
        self._script_path_label.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        self._script_path_label.setWordWrap(True)

        row = QHBoxLayout()
        change_btn = QPushButton("Change Script File")
        change_btn.setObjectName("secondary")
        change_btn.clicked.connect(self._select_script)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._load_script)
        row.addWidget(change_btn)
        row.addWidget(refresh_btn)
        row.addStretch()

        self._script_view = QPlainTextEdit()
        self._script_view.setReadOnly(True)
        self._script_view.setStyleSheet(
            f"background: #0a0a0a; color: {COLORS['text']}; font-family: monospace; font-size: 12px;"
        )

        layout.addWidget(self._script_path_label)
        layout.addLayout(row)
        layout.addWidget(self._script_view, 1)

        self._load_script()
        return w

    def _audio_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        config = load_config()
        audio_path = config.get("audio_path", "")

        self._audio_info = QLabel()
        self._audio_info.setWordWrap(True)
        self._update_audio_info(audio_path)

        row = QHBoxLayout()
        change_btn = QPushButton("Change Audio File")
        change_btn.setObjectName("secondary")
        change_btn.clicked.connect(self._select_audio)
        row.addWidget(change_btn)
        row.addStretch()

        layout.addWidget(self._audio_info)
        layout.addLayout(row)
        layout.addStretch()

        return w

    def _images_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        row = QHBoxLayout()
        self._images_folder_label = QLabel("Images folder: Not set")
        self._images_folder_label.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        self._images_folder_label.setWordWrap(True)
        change_btn = QPushButton("Change Folder")
        change_btn.setObjectName("secondary")
        change_btn.clicked.connect(self._select_images_folder)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self._load_images)
        row.addWidget(change_btn)
        row.addWidget(refresh_btn)
        row.addStretch()

        self._images_tree = QTreeWidget()
        self._images_tree.setHeaderLabels(["Name", "Size", "Type"])
        self._images_tree.setColumnWidth(0, 400)
        self._images_tree.setColumnWidth(1, 80)
        self._images_tree.setStyleSheet(
            f"background: {COLORS['surface2']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px;"
        )

        self._images_count = QLabel()
        self._images_count.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 11px;")

        layout.addWidget(self._images_folder_label)
        layout.addLayout(row)
        layout.addWidget(self._images_count)
        layout.addWidget(self._images_tree, 1)

        self._load_images()
        return w

    def _load_script(self):
        config = load_config()
        script_path = config.get("script_path", "")
        self._script_path_label.setText(f"File: {script_path or 'Not set'}")
        if script_path and Path(script_path).exists():
            try:
                with open(script_path, "r", encoding="utf-8-sig") as f:
                    self._script_view.setPlainText(f.read())
            except Exception as e:
                self._script_view.setPlainText(f"Error reading file: {e}")
        else:
            self._script_view.setPlainText("Script file not found. Set it in Project Settings.")

    def _update_audio_info(self, audio_path):
        if audio_path and Path(audio_path).exists():
            p = Path(audio_path)
            size_mb = p.stat().st_size / (1024 * 1024)
            text = (
                f"<b>File:</b> {p.name}<br>"
                f"<b>Path:</b> {audio_path}<br>"
                f"<b>Size:</b> {size_mb:.2f} MB<br>"
                f"<b>Format:</b> {p.suffix.upper()[1:]}"
            )
            self._audio_info.setStyleSheet(f"color: {COLORS['success']}; font-size: 13px; padding: 12px;")
        else:
            text = "No audio file selected. Go to Project Settings to set the audio file path."
            self._audio_info.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 13px; padding: 12px;")
        self._audio_info.setText(text)

    def _load_images(self):
        config = load_config()
        base = Path(config.get("base_path", "."))
        images_folder = config.get("images_folder", "")

        folders_to_scan = []
        if images_folder and Path(images_folder).exists():
            folders_to_scan.append(Path(images_folder))
        folders_to_scan.append(base / "output" / "images")
        folders_to_scan.append(base / "assets" / "images")

        primary = folders_to_scan[0] if folders_to_scan else None
        label = str(primary) if primary else "Not set"
        self._images_folder_label.setText(f"Scanning: {label}")

        self._images_tree.clear()
        total = 0
        extensions = {".jpg", ".jpeg", ".png", ".webp"}

        for folder in folders_to_scan:
            if not folder.exists():
                continue
            files = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in extensions)
            if not files:
                continue

            parent = QTreeWidgetItem(self._images_tree, [f"📁 {folder.name}", "", ""])
            parent.setForeground(0, __import__('PySide6.QtGui', fromlist=['QColor']).QColor(COLORS['accent']))

            for f in files:
                size_kb = f.stat().st_size / 1024
                item = QTreeWidgetItem(parent, [f.name, f"{size_kb:.0f} KB", f.suffix.upper()[1:]])
                total += 1

            parent.setExpanded(True)

        self._images_count.setText(f"{total} image(s) found")

    def _select_script(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Script File", str(Path.home()), "Text Files (*.txt)")
        if path:
            config = load_config()
            config["script_path"] = path
            save_config(config)
            self._load_script()

    def _select_audio(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", str(Path.home()),
            "Audio Files (*.mp3 *.wav *.m4a)")
        if path:
            config = load_config()
            config["audio_path"] = path
            save_config(config)
            self._update_audio_info(path)

    def _select_images_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Images Folder", str(Path.home()))
        if path:
            config = load_config()
            config["images_folder"] = path
            save_config(config)
            self._load_images()

    def refresh(self):
        self._load_script()
        self._load_images()
        config = load_config()
        self._update_audio_info(config.get("audio_path", ""))
