import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QPlainTextEdit, QTreeWidget, QTreeWidgetItem,
    QScrollArea, QMessageBox,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_config, BASE_DIR


class OutputsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        title = QLabel("Outputs Viewer")
        title.setObjectName("heading")
        layout.addWidget(title)

        desc = QLabel("View generated prompts, scene mapping, and video output.")
        desc.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        layout.addWidget(desc)

        header_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh All")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self.refresh)
        header_row.addStretch()
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        tabs = QTabWidget()
        tabs.addTab(self._prompts_tab(), "Prompts")
        tabs.addTab(self._mapping_tab(), "Mapping")
        tabs.addTab(self._video_tab(), "Final Video")
        layout.addWidget(tabs, 1)

    def _prompts_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self._prompts_status = QLabel()
        row.addWidget(self._prompts_status)
        row.addStretch()
        open_btn = QPushButton("Open prompts_output.txt")
        open_btn.setObjectName("secondary")
        open_btn.clicked.connect(self._open_prompts_txt)
        row.addWidget(open_btn)
        layout.addLayout(row)

        self._prompts_view = QPlainTextEdit()
        self._prompts_view.setReadOnly(True)
        self._prompts_view.setStyleSheet(
            f"background: #0a0a0a; color: {COLORS['text']}; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self._prompts_view, 1)

        self._load_prompts()
        return w

    def _mapping_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)

        row = QHBoxLayout()
        self._mapping_status = QLabel()
        row.addWidget(self._mapping_status)
        row.addStretch()
        layout.addLayout(row)

        self._mapping_tree = QTreeWidget()
        self._mapping_tree.setHeaderLabels(["Scene", "Start", "End", "Image", "Label"])
        self._mapping_tree.setColumnWidth(0, 60)
        self._mapping_tree.setColumnWidth(1, 60)
        self._mapping_tree.setColumnWidth(2, 60)
        self._mapping_tree.setColumnWidth(3, 350)
        self._mapping_tree.setStyleSheet(
            f"background: {COLORS['surface2']}; color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px;"
        )
        layout.addWidget(self._mapping_tree, 1)

        self._load_mapping()
        return w

    def _video_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.setSpacing(16)

        self._video_info = QLabel()
        self._video_info.setWordWrap(True)
        self._video_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._video_info)

        row = QHBoxLayout()
        open_folder_btn = QPushButton("Open Output Folder")
        open_folder_btn.setObjectName("secondary")
        open_folder_btn.clicked.connect(self._open_output_folder)
        row.addWidget(open_folder_btn)
        row.addStretch()
        layout.addLayout(row)

        layout.addStretch()

        self._load_video_info()
        return w

    def _load_prompts(self):
        config = load_config()
        base = Path(config.get("base_path", "."))

        txt_path = base / "output" / "prompts_output.txt"
        json_path = base / "output" / "prompts.json"

        if txt_path.exists():
            try:
                with open(txt_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self._prompts_view.setPlainText(content)
                scene_count = 0
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    scene_count = len(data)
                self._prompts_status.setText(f"{scene_count} scenes generated")
                self._prompts_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")
            except Exception as e:
                self._prompts_view.setPlainText(f"Error reading file: {e}")
                self._prompts_status.setText("Error reading file")
                self._prompts_status.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")
        else:
            self._prompts_view.setPlainText("No prompts generated yet.\nRun Step 1 in the Pipeline Runner.")
            self._prompts_status.setText("Not generated")
            self._prompts_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")

    def _load_mapping(self):
        config = load_config()
        base = Path(config.get("base_path", "."))
        mapping_path = base / "mapping.json"
        self._mapping_tree.clear()

        if not mapping_path.exists():
            self._mapping_status.setText("mapping.json not found — run Step 3 first")
            self._mapping_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
            return

        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)

            self._mapping_status.setText(f"{len(mapping)} scenes mapped")
            self._mapping_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px;")

            for scene in mapping:
                images = scene.get("images", [])
                img_str = images[0] if images else "[no image]"
                img_color = COLORS['text'] if images else COLORS['error']

                item = QTreeWidgetItem([
                    str(scene.get("scene_number", "?")),
                    scene.get("start", ""),
                    scene.get("end", ""),
                    img_str,
                    scene.get("label_text", ""),
                ])
                if not images:
                    for col in range(5):
                        item.setForeground(col, __import__('PySide6.QtGui', fromlist=['QColor']).QColor(COLORS['error']))
                self._mapping_tree.addTopLevelItem(item)

        except Exception as e:
            self._mapping_status.setText(f"Error: {e}")
            self._mapping_status.setStyleSheet(f"color: {COLORS['error']}; font-size: 12px;")

    def _load_video_info(self):
        config = load_config()
        output_folder = config.get("output_folder", "")
        base = Path(config.get("base_path", "."))

        if output_folder:
            video_path = Path(output_folder) / "final_video.mp4"
        else:
            video_path = base / "assets" / "output" / "final_video.mp4"

        if video_path.exists():
            size_mb = video_path.stat().st_size / (1024 * 1024)
            self._video_info.setText(
                f"<b style='color:{COLORS['success']}; font-size:16px;'>✓ Video Ready</b><br><br>"
                f"<span style='color:{COLORS['text_sec']};'>File: {video_path.name}</span><br>"
                f"<span style='color:{COLORS['text_sec']};'>Path: {video_path}</span><br>"
                f"<span style='color:{COLORS['text_sec']};'>Size: {size_mb:.1f} MB</span>"
            )
        else:
            self._video_info.setText(
                f"<b style='color:{COLORS['text_sec']}; font-size:14px;'>No video generated yet</b><br><br>"
                f"<span style='color:{COLORS['text_dim']};'>Run Step 4 (Video Builder) in the Pipeline Runner.</span><br>"
                f"<span style='color:{COLORS['text_dim']};'>Expected path: {video_path}</span>"
            )

    def _open_prompts_txt(self):
        config = load_config()
        base = Path(config.get("base_path", "."))
        txt_path = base / "output" / "prompts_output.txt"
        if txt_path.exists():
            import subprocess, sys
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", str(txt_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(txt_path)])
            else:
                subprocess.Popen(["notepad", str(txt_path)])
        else:
            QMessageBox.warning(self, "Not Found", "prompts_output.txt not found. Run Step 1 first.")

    def _open_output_folder(self):
        config = load_config()
        output_folder = config.get("output_folder", "")
        base = Path(config.get("base_path", "."))
        folder = Path(output_folder) if output_folder else base / "assets" / "output"
        folder.mkdir(parents=True, exist_ok=True)

        import subprocess, sys
        if sys.platform == "linux":
            subprocess.Popen(["xdg-open", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["explorer", str(folder)])

    def refresh(self):
        self._load_prompts()
        self._load_mapping()
        self._load_video_info()
