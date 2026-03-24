import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import DropZone, make_separator, make_badge
from app.core.config_manager import load_config, save_config, BASE_DIR


class DashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._zones: dict[str, DropZone] = {}
        self._status_rows: dict[str, tuple] = {}
        self._translatable: dict[str, QLabel | QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(28)

        layout.addWidget(self._hero_section())
        layout.addWidget(self._files_section())
        layout.addWidget(self._status_section())
        layout.addWidget(self._how_section())
        layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _hero_section(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel(t("dashboard_title"))
        title.setObjectName("heading")
        sub = QLabel(t("dashboard_subtitle"))
        sub.setStyleSheet(f"color: {get_colors()['text_sec']}; font-size: 14px; background: transparent;")
        sub.setWordWrap(True)

        self._translatable["dashboard_title"] = title
        self._translatable["dashboard_subtitle"] = sub
        layout.addWidget(title)
        layout.addWidget(sub)
        return w

    def _files_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        icon = QLabel("📂")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("files_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        sub = QLabel(t("files_subtitle"))
        sub.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
        self._translatable["files_section"] = title
        self._translatable["files_subtitle"] = sub

        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(sub)
        layout.addSpacing(4)

        grid = QGridLayout()
        grid.setSpacing(14)

        cfg = load_config()

        self._zones["script"] = DropZone(
            t("drop_script"), t("drop_script_sub"), "📝",
            accept_folders=False,
            file_filter="Text Files (*.txt);;All Files (*)"
        )
        self._zones["audio"] = DropZone(
            t("drop_audio"), t("drop_audio_sub"), "🎵",
            accept_folders=False,
            file_filter="Audio Files (*.mp3 *.wav *.m4a *.aac);;All Files (*)"
        )
        self._zones["images"] = DropZone(
            t("drop_images"), t("drop_images_sub"), "🖼️",
            accept_folders=True
        )
        self._zones["output"] = DropZone(
            t("drop_output"), t("drop_output_sub"), "📤",
            accept_folders=True
        )

        if cfg.get("script_path"):
            self._zones["script"].set_path(cfg["script_path"])
        if cfg.get("audio_path"):
            self._zones["audio"].set_path(cfg["audio_path"])
        if cfg.get("images_folder"):
            self._zones["images"].set_path(cfg["images_folder"])
        if cfg.get("output_folder"):
            self._zones["output"].set_path(cfg["output_folder"])

        for key, zone in self._zones.items():
            zone.file_selected.connect(lambda path, k=key: self._on_file_selected(k, path))

        grid.addWidget(self._zones["script"],  0, 0)
        grid.addWidget(self._zones["audio"],   0, 1)
        grid.addWidget(self._zones["images"],  1, 0)
        grid.addWidget(self._zones["output"],  1, 1)

        layout.addLayout(grid)
        return card

    def _status_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        icon = QLabel("📋")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("status_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["status_section"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(make_separator(C))

        cfg = load_config()
        checks = self._get_checks(cfg)
        self._status_rows = {}
        for key, (label, exists) in checks.items():
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {C['text_sec']}; font-size: 12px; background: transparent;")
            badge = make_badge(t("status_ok") if exists else t("status_missing"),
                               "success" if exists else "error", C)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(badge)
            self._status_rows[key] = (lbl, badge)
            layout.addLayout(row)

        return card

    def _how_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        icon = QLabel("💡")
        icon.setStyleSheet("font-size: 18px; background: transparent;")
        title = QLabel(t("how_section"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {C['text']}; background: transparent;")
        self._translatable["how_section"] = title
        hdr.addWidget(icon)
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)
        layout.addWidget(make_separator(C))

        how_steps = [
            ("how_step1", "how_step1_desc", "1"),
            ("how_step2", "how_step2_desc", "2"),
            ("how_step3", "how_step3_desc", "3"),
            ("how_step4", "how_step4_desc", "4"),
        ]
        self._how_labels = []
        for step_key, desc_key, num in how_steps:
            row = QHBoxLayout()
            row.setSpacing(14)

            num_lbl = QLabel(num)
            num_lbl.setFixedSize(30, 30)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(
                f"background: {C['accent']}; color: white; border-radius: 15px; "
                f"font-weight: bold; font-size: 13px;"
            )

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            step_lbl = QLabel(t(step_key))
            step_lbl.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['text']}; background: transparent;")
            desc_lbl = QLabel(t(desc_key))
            desc_lbl.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
            desc_lbl.setWordWrap(True)
            text_col.addWidget(step_lbl)
            text_col.addWidget(desc_lbl)

            row.addWidget(num_lbl)
            row.addLayout(text_col, 1)
            layout.addLayout(row)
            self._how_labels.append((step_lbl, desc_lbl, step_key, desc_key))

        return card

    def _get_checks(self, cfg) -> dict:
        base = Path(BASE_DIR)
        out = Path(cfg.get("output_folder", base / "output"))
        return {
            "config":   (t("check_config"),  (base / "config.json").exists()),
            "style":    (t("check_style"),   (base / "style_config.json").exists()),
            "script":   (t("check_script"),  cfg.get("script_path", "") != "" and Path(cfg.get("script_path", "x")).exists()),
            "audio":    (t("check_audio"),   cfg.get("audio_path", "") != "" and Path(cfg.get("audio_path", "x")).exists()),
            "prompts":  (t("check_prompts"), (out / "prompts.json").exists()),
            "images":   (t("check_images"),  cfg.get("images_folder", "") != "" and Path(cfg.get("images_folder", "x")).exists()),
            "mapping":  (t("check_mapping"), (out / "mapping.json").exists()),
            "video":    (t("check_video"),   (out / "final_video.mp4").exists()),
        }

    def _on_file_selected(self, key: str, path: str):
        field_map = {
            "script":  "script_path",
            "audio":   "audio_path",
            "images":  "images_folder",
            "output":  "output_folder",
        }
        cfg = load_config()
        cfg[field_map[key]] = path
        save_config(cfg)
        self._refresh_status()

    def _refresh_status(self):
        C = get_colors()
        cfg = load_config()
        checks = self._get_checks(cfg)
        for key, (label, exists) in checks.items():
            if key in self._status_rows:
                lbl, badge = self._status_rows[key]
                lbl.setText(label)
                txt = t("status_ok") if exists else t("status_missing")
                kind = "success" if exists else "error"
                colors = {
                    "success": (C['success_bg'], C['success']),
                    "error":   (C['error_bg'],   C['error']),
                }
                bg, fg = colors[kind]
                badge.setText(txt)
                badge.setStyleSheet(
                    f"background: {bg}; color: {fg}; border-radius: 5px; "
                    f"padding: 2px 8px; font-size: 11px; font-weight: 600;"
                )

    def refresh(self):
        self._refresh_status()
        cfg = load_config()
        if cfg.get("script_path"):
            self._zones["script"].set_path(cfg["script_path"])
        if cfg.get("audio_path"):
            self._zones["audio"].set_path(cfg["audio_path"])
        if cfg.get("images_folder"):
            self._zones["images"].set_path(cfg["images_folder"])
        if cfg.get("output_folder"):
            self._zones["output"].set_path(cfg["output_folder"])

    def retranslate(self):
        C = get_colors()
        for key, widget in self._translatable.items():
            widget.setText(t(key))

        zone_keys = [
            ("script", "drop_script", "drop_script_sub"),
            ("audio",  "drop_audio",  "drop_audio_sub"),
            ("images", "drop_images", "drop_images_sub"),
            ("output", "drop_output", "drop_output_sub"),
        ]
        for k, title_key, sub_key in zone_keys:
            if k in self._zones:
                self._zones[k].retranslate(t(title_key), t(sub_key))

        for step_lbl, desc_lbl, step_key, desc_key in self._how_labels:
            step_lbl.setText(t(step_key))
            desc_lbl.setText(t(desc_key))

        self._refresh_status()
