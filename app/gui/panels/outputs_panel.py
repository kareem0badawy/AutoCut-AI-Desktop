import json
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTabWidget, QPlainTextEdit, QTreeWidget, QTreeWidgetItem,
    QScrollArea,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import make_separator, make_badge
from app.core.config_manager import load_config, BASE_DIR


class OutputsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._translatable: dict[str, QLabel | QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        C = get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(20)

        hdr_row = QHBoxLayout()
        title = QLabel(t("outputs_title"))
        title.setObjectName("heading")
        self._translatable["outputs_title"] = title

        self._refresh_btn = QPushButton(t("refresh_all"))
        self._refresh_btn.setObjectName("secondary")
        self._refresh_btn.setFixedHeight(34)
        self._refresh_btn.clicked.connect(self.refresh)
        self._translatable["refresh_all"] = self._refresh_btn

        hdr_row.addWidget(title)
        hdr_row.addStretch()
        hdr_row.addWidget(self._refresh_btn)
        layout.addLayout(hdr_row)

        desc = QLabel(t("outputs_desc"))
        desc.setStyleSheet(f"color: {C['text_sec']}; font-size: 13px; background: transparent;")
        self._translatable["outputs_desc"] = desc
        layout.addWidget(desc)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)

        self._tab_prompts = self._build_prompts_tab()
        self._tab_mapping = self._build_mapping_tab()
        self._tab_video = self._build_video_tab()

        self._tabs.addTab(self._tab_prompts, t("tab_prompts"))
        self._tabs.addTab(self._tab_mapping, t("tab_mapping"))
        self._tabs.addTab(self._tab_video,   t("tab_video"))

        layout.addWidget(self._tabs, 1)

    def _build_prompts_tab(self) -> QWidget:
        C = get_colors()
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        self._prompts_badge = QLabel(t("not_generated"))
        self._prompts_badge.setStyleSheet(
            f"color: {C['text_sec']}; font-size: 12px; background: transparent;"
        )
        self._open_txt_btn = QPushButton(t("open_txt"))
        self._open_txt_btn.setObjectName("secondary")
        self._open_txt_btn.setFixedHeight(30)
        self._open_txt_btn.clicked.connect(self._open_prompts_txt)
        self._translatable["open_txt"] = self._open_txt_btn
        hdr.addWidget(self._prompts_badge)
        hdr.addStretch()
        hdr.addWidget(self._open_txt_btn)
        layout.addLayout(hdr)

        self._prompts_view = QPlainTextEdit()
        self._prompts_view.setReadOnly(True)
        self._prompts_view.setStyleSheet(
            f"background: {C['surface2']}; color: {C['text_sec']}; "
            f"font-family: 'Consolas', monospace; font-size: 12px; "
            f"border-radius: 8px; border: 1px solid {C['border']};"
        )
        layout.addWidget(self._prompts_view)
        return w

    def _build_mapping_tab(self) -> QWidget:
        C = get_colors()
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._mapping_badge = QLabel(t("mapping_not_found"))
        self._mapping_badge.setStyleSheet(
            f"color: {C['text_sec']}; font-size: 12px; background: transparent;"
        )
        layout.addWidget(self._mapping_badge)

        self._mapping_tree = QTreeWidget()
        self._mapping_tree.setColumnCount(5)
        self._mapping_tree.setHeaderLabels([
            t("col_scene"), t("col_start"), t("col_end"), t("col_image"), t("col_label")
        ])
        self._mapping_tree.setAlternatingRowColors(True)
        self._mapping_tree.setRootIsDecorated(False)
        layout.addWidget(self._mapping_tree)
        return w

    def _build_video_tab(self) -> QWidget:
        C = get_colors()
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignTop)

        self._video_status_lbl = QLabel(t("video_not_ready"))
        self._video_status_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {C['text']}; background: transparent;"
        )
        self._video_hint_lbl = QLabel(t("video_run_step4"))
        self._video_hint_lbl.setStyleSheet(
            f"font-size: 13px; color: {C['text_sec']}; background: transparent;"
        )

        self._video_size_lbl = QLabel("")
        self._video_size_lbl.setStyleSheet(
            f"font-size: 12px; color: {C['text_dim']}; background: transparent;"
        )
        self._video_path_lbl = QLabel("")
        self._video_path_lbl.setStyleSheet(
            f"font-size: 12px; color: {C['text_dim']}; background: transparent;"
        )
        self._video_path_lbl.setWordWrap(True)

        self._open_folder_btn = QPushButton(t("open_folder"))
        self._open_folder_btn.setObjectName("export_btn")
        self._open_folder_btn.setFixedHeight(48)
        self._open_folder_btn.setFixedWidth(220)
        self._open_folder_btn.setEnabled(False)
        self._open_folder_btn.clicked.connect(self._open_output_folder)
        self._translatable["open_folder"] = self._open_folder_btn

        layout.addWidget(self._video_status_lbl)
        layout.addWidget(self._video_hint_lbl)
        layout.addSpacing(8)
        layout.addWidget(self._video_size_lbl)
        layout.addWidget(self._video_path_lbl)
        layout.addSpacing(16)
        layout.addWidget(self._open_folder_btn)
        return w

    def refresh(self):
        C = get_colors()
        cfg = load_config()
        base = Path(BASE_DIR)
        out = Path(cfg.get("output_folder", base / "output"))

        prompts_json = out / "prompts.json"
        if prompts_json.exists():
            try:
                data = json.loads(prompts_json.read_text(encoding="utf-8"))
                n = len(data) if isinstance(data, list) else len(data.get("scenes", []))
                self._prompts_badge.setText(t("scenes_count", n=n))
                self._prompts_view.setPlainText(
                    json.dumps(data, ensure_ascii=False, indent=2)
                )
            except Exception as e:
                self._prompts_badge.setText(str(e))
        else:
            self._prompts_badge.setText(t("not_generated"))
            self._prompts_view.setPlainText("")

        mapping_json = out / "mapping.json"
        self._mapping_tree.clear()
        if mapping_json.exists():
            try:
                data = json.loads(mapping_json.read_text(encoding="utf-8"))
                scenes = data if isinstance(data, list) else data.get("scenes", [])
                self._mapping_badge.setText(t("scenes_mapped", n=len(scenes)))
                self._mapping_tree.setHeaderLabels([
                    t("col_scene"), t("col_start"), t("col_end"), t("col_image"), t("col_label")
                ])
                for i, scene in enumerate(scenes):
                    item = QTreeWidgetItem([
                        str(i + 1),
                        str(scene.get("start", "")),
                        str(scene.get("end", "")),
                        str(Path(scene.get("image_path", scene.get("image", ""))).name),
                        str(scene.get("label", scene.get("text", ""))),
                    ])
                    self._mapping_tree.addTopLevelItem(item)
                for col in range(5):
                    self._mapping_tree.resizeColumnToContents(col)
            except Exception as e:
                self._mapping_badge.setText(str(e))
        else:
            self._mapping_badge.setText(t("mapping_not_found"))

        video_path = out / "final_video.mp4"
        if video_path.exists():
            size_mb = video_path.stat().st_size / 1_048_576
            self._video_status_lbl.setText(t("video_ready"))
            self._video_status_lbl.setStyleSheet(
                f"font-size: 18px; font-weight: 700; color: {C['success']}; background: transparent;"
            )
            self._video_hint_lbl.setText("")
            self._video_size_lbl.setText(f"{t('video_size')}: {size_mb:.1f} MB")
            self._video_path_lbl.setText(f"{t('video_path')}: {video_path}")
            self._open_folder_btn.setEnabled(True)
        else:
            self._video_status_lbl.setText(t("video_not_ready"))
            self._video_status_lbl.setStyleSheet(
                f"font-size: 18px; font-weight: 700; color: {C['text']}; background: transparent;"
            )
            self._video_hint_lbl.setText(t("video_run_step4"))
            self._video_size_lbl.setText("")
            self._video_path_lbl.setText("")
            self._open_folder_btn.setEnabled(False)

    def _open_prompts_txt(self):
        cfg = load_config()
        out = Path(cfg.get("output_folder", Path(BASE_DIR) / "output"))
        txt = out / "prompts_output.txt"
        if txt.exists():
            if sys.platform == "win32":
                subprocess.Popen(["notepad", str(txt)])
            else:
                subprocess.Popen(["xdg-open", str(txt)])

    def _open_output_folder(self):
        cfg = load_config()
        folder = cfg.get("output_folder", str(Path(BASE_DIR) / "output"))
        p = Path(folder)
        p.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(p)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])

    def retranslate(self):
        for key, widget in self._translatable.items():
            widget.setText(t(key))
        self._tabs.setTabText(0, t("tab_prompts"))
        self._tabs.setTabText(1, t("tab_mapping"))
        self._tabs.setTabText(2, t("tab_video"))
        self._mapping_tree.setHeaderLabels([
            t("col_scene"), t("col_start"), t("col_end"), t("col_image"), t("col_label")
        ])
        self.refresh()
