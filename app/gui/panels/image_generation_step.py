"""
image_generation_step.py
────────────────────────
Step 2 — Image Generation

Modes:
  Manual  — user copies prompts and generates images by hand.
  Auto    — FlowWorker opens Chrome, navigates to labs.google/flow,
            handles Google login (persistent session), types each scene
            prompt, clicks Generate, and downloads the result.

Login flow:
  1. First run: Chrome opens labs.google/flow.
     If not logged in → login_needed signal → banner shown → user logs in.
  2. Session is saved in ~/.autocut/chrome_profile/
  3. Subsequent runs start directly in Flow (no login needed again).
"""

import json
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QButtonGroup, QProgressBar,
    QPlainTextEdit, QLineEdit, QApplication, QFileDialog,
)

from app.gui.theme import get_colors
from app.gui.widgets import make_separator
from app.core.config_manager import BASE_DIR
from app.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_prompts() -> tuple[list[dict], str]:
    """
    Read prompts.json and return (scenes_list, main_prompt_text).

    Handles two formats:
      • list  → [{scene_number, main_prompt, ...}, ...]   ← actual format
      • dict  → {main_prompt: str, scenes: [...]}         ← legacy format
    """
    candidates = [
        Path(BASE_DIR) / "output" / "prompts.json",
        Path(BASE_DIR) / "prompts.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # ── List format (actual) ──────────────────────────────────
                if isinstance(data, list):
                    # Use first scene's main_prompt as the global preview
                    first_prompt = data[0].get("main_prompt", "") if data else ""
                    # Trim style boilerplate: keep first sentence only
                    short = first_prompt.split(",")[0] if first_prompt else ""
                    return data, short
                # ── Dict format (legacy) ─────────────────────────────────
                if isinstance(data, dict):
                    scenes = data.get("scenes", [])
                    main   = data.get("main_prompt", "")
                    return scenes, main
            except Exception:
                pass
    return [], ""


def _default_output_dir() -> str:
    return str(Path(BASE_DIR) / "output" / "generated_images")


def _default_profile_dir() -> str:
    return str(Path.home() / ".autocut" / "chrome_profile")


# ─────────────────────────────────────────────────────────────────────────────
# Scene Card widget
# ─────────────────────────────────────────────────────────────────────────────

class _SceneCard(QWidget):
    """One row: badge + title/prompt + Copy button."""

    def __init__(self, index: int, scene_data: dict, C: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("step_card")
        # main_prompt is the image-generation prompt in the actual format
        self._prompt = (
            scene_data.get("main_prompt")
            or scene_data.get("prompt")
            or scene_data.get("description")
            or ""
        )
        self._scene_data = scene_data

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Badge
        badge = QLabel(str(index))
        badge.setFixedSize(30, 30)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{C['accent']}22;color:{C['accent']};"
            f"border:2px solid {C['accent']};border-radius:15px;"
            f"font-weight:bold;font-size:12px;"
        )

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)
        # Use label_text as scene title, fallback to scene_number
        scene_name = (
            scene_data.get("label_text")
            or scene_data.get("scene_title")
            or scene_data.get("title")
            or f"Scene {index}"
        )
        scene_num = scene_data.get("scene_number", index)
        title_lbl = QLabel(f"#{scene_num}  {scene_name}")
        title_lbl.setStyleSheet(
            f"font-weight:700;font-size:13px;color:{C['text']};background:transparent;"
        )
        # Show scene_description (readable) not the long main_prompt
        display_text = (
            scene_data.get("scene_description")
            or self._prompt[:120] + "..." if len(self._prompt) > 120 else self._prompt
        ) or "—"
        prompt_lbl = QLabel(display_text)
        prompt_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_sec']};background:transparent;"
        )
        prompt_lbl.setWordWrap(True)
        prompt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info.addWidget(title_lbl)
        info.addWidget(prompt_lbl)

        # Status icon (updated during auto mode)
        self._status_lbl = QLabel("⬜")
        self._status_lbl.setFixedWidth(22)
        self._status_lbl.setStyleSheet("background:transparent;font-size:14px;")

        # Copy — copies the full main_prompt (for image gen tools)
        copy_btn = QPushButton("📋  Prompt")
        copy_btn.setObjectName("secondary")
        copy_btn.setFixedHeight(28)
        copy_btn.setFixedWidth(90)
        copy_btn.setToolTip("نسخ الـ main_prompt كاملاً للـ clipboard")
        copy_btn.clicked.connect(self._copy)

        lay.addWidget(badge)
        lay.addLayout(info, 1)
        lay.addWidget(self._status_lbl)
        lay.addWidget(copy_btn)

    def _copy(self):
        QApplication.clipboard().setText(self._prompt)

    def set_status(self, status: str):
        """status: 'pending' | 'done' | 'error'"""
        icons = {"pending": "⏳", "done": "✅", "error": "❌"}
        self._status_lbl.setText(icons.get(status, "⬜"))


# ─────────────────────────────────────────────────────────────────────────────
# ImageGenerationStep
# ─────────────────────────────────────────────────────────────────────────────

class ImageGenerationStep(QWidget):
    """
    Step 2 — Image Generation

    Contains:
    • Mode toggle (Manual / Auto)
    • Main prompt display
    • Scenes list with per-scene Copy buttons
    • Auto panel:  Chrome path · output dir · progress · log · Stop btn
    • Login banner: shown when Chrome is waiting for Google login
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_cards: list[_SceneCard] = []
        self._scenes_data: list[dict] = []
        self._main_prompt_text: str = ""
        self._worker = None          # FlowWorker instance
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        root = QVBoxLayout(card)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        root.addWidget(self._build_header(C))
        root.addWidget(make_separator(C))
        root.addWidget(self._build_mode_row(C))
        root.addWidget(make_separator(C))
        root.addWidget(self._build_login_banner(C))   # hidden by default
        root.addWidget(self._build_main_prompt_bar(C))
        root.addWidget(self._build_scenes_panel(C), 1)
        root.addWidget(make_separator(C))
        root.addWidget(self._build_auto_panel(C))     # hidden in Manual
        root.addLayout(self._build_action_row(C))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)

        # Start in Manual mode
        self._set_mode("manual")

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self, C: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        icon = QLabel("🖼️")
        icon.setStyleSheet("font-size:22px;background:transparent;")
        icon.setFixedWidth(32)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("الخطوة 2 — توليد الصور  ·  Step 2: Image Generation")
        title.setStyleSheet(
            f"font-weight:700;font-size:16px;color:{C['text']};background:transparent;"
        )
        desc = QLabel(
            "✋ Manual: انسخ الـ prompt من كل مشهد وأدخله يدوياً في Flow لتوليد الصورة.\n"
            "⚡ Auto: Chrome يفتح Flow تلقائياً، يكتب الـ prompt ويضغط Generate لكل مشهد."
        )
        desc.setStyleSheet(f"font-size:12px;color:{C['text_sec']};background:transparent;")
        desc.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(desc)

        lay.addWidget(icon)
        lay.addLayout(col, 1)
        return w

    # ── Mode toggle ───────────────────────────────────────────────────────────

    def _build_mode_row(self, C: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        lbl = QLabel("وضع التوليد:")
        lbl.setStyleSheet(f"font-weight:700;font-size:13px;color:{C['text']};background:transparent;")

        # Toggle pill
        pill = QWidget()
        pill.setObjectName("card_dark")
        pill.setFixedHeight(36)
        pill_lay = QHBoxLayout(pill)
        pill_lay.setContentsMargins(4, 4, 4, 4)
        pill_lay.setSpacing(4)

        self._manual_btn = QPushButton("✋  Manual")
        self._manual_btn.setCheckable(True)
        self._manual_btn.setChecked(True)
        self._manual_btn.setFixedHeight(28)
        self._manual_btn.setFixedWidth(110)

        self._auto_btn = QPushButton("⚡  Auto")
        self._auto_btn.setCheckable(True)
        self._auto_btn.setFixedHeight(28)
        self._auto_btn.setFixedWidth(110)

        grp = QButtonGroup(self)
        grp.addButton(self._manual_btn)
        grp.addButton(self._auto_btn)
        grp.setExclusive(True)
        self._mode_grp = grp

        self._manual_btn.toggled.connect(self._on_mode_toggled)

        pill_lay.addWidget(self._manual_btn)
        pill_lay.addWidget(self._auto_btn)
        pill.setFixedWidth(232)

        lay.addWidget(lbl)
        lay.addWidget(pill)
        lay.addStretch()
        self._update_toggle_styles(C, manual=True)
        return w

    def _update_toggle_styles(self, C: dict, manual: bool):
        active   = (f"background:{C['accent']};color:#ffffff;border:none;"
                    f"border-radius:6px;font-weight:700;font-size:12px;")
        inactive = (f"background:transparent;color:{C['text_dim']};border:none;"
                    f"border-radius:6px;font-weight:700;font-size:12px;")
        self._manual_btn.setStyleSheet(active   if manual else inactive)
        self._auto_btn.setStyleSheet(inactive if manual else active)

    def _on_mode_toggled(self, manual_checked: bool):
        C = get_colors()
        self._update_toggle_styles(C, manual=manual_checked)
        self._set_mode("manual" if manual_checked else "auto")

    def _set_mode(self, mode: str):
        is_auto = (mode == "auto")
        self._auto_panel.setVisible(is_auto)
        # Update action row button text
        if is_auto:
            self._action_btn.setText("⚡  بدء التوليد التلقائي")
            self._action_btn.setObjectName("primary")
            self._action_btn.setEnabled(bool(self._scenes_data))
        else:
            self._action_btn.setText("🔗  فتح Flow في المتصفح")
            self._action_btn.setObjectName("secondary")
            self._action_btn.setEnabled(True)
        # Re-polish button
        self._action_btn.style().unpolish(self._action_btn)
        self._action_btn.style().polish(self._action_btn)

    # ── Login banner (shown when waiting for Google login) ────────────────────

    def _build_login_banner(self, C: dict) -> QWidget:
        self._login_banner = QWidget()
        self._login_banner.setObjectName("card_dark")
        self._login_banner.setVisible(False)
        lay = QHBoxLayout(self._login_banner)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        icon = QLabel("🔑")
        icon.setStyleSheet("font-size:20px;background:transparent;")
        icon.setFixedWidth(28)

        msg = QLabel(
            "Chrome يحتاج تسجيل دخول Google.\n"
            "افتح نافذة Chrome وسجّل دخولك، ثم اضغط 'متابعة'."
        )
        msg.setStyleSheet(f"font-size:12px;color:{C['warning']};background:transparent;")
        msg.setWordWrap(True)

        continue_btn = QPushButton("✅  متابعة")
        continue_btn.setObjectName("primary")
        continue_btn.setFixedHeight(32)
        continue_btn.setFixedWidth(120)
        continue_btn.clicked.connect(self._on_continue_after_login)
        self._continue_login_btn = continue_btn

        lay.addWidget(icon)
        lay.addWidget(msg, 1)
        lay.addWidget(continue_btn)
        return self._login_banner

    # ── Main prompt bar ───────────────────────────────────────────────────────

    def _build_main_prompt_bar(self, C: dict) -> QWidget:
        w = QWidget()
        w.setObjectName("card_dark")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        prefix = QLabel("🎨  Style Preview:")
        prefix.setStyleSheet(
            f"font-weight:700;font-size:12px;color:{C['text_sec']};background:transparent;"
        )
        prefix.setFixedWidth(110)

        self._main_prompt_lbl = QLabel("—  لم يتم تحميل prompts.json بعد")
        self._main_prompt_lbl.setStyleSheet(
            f"font-size:12px;color:{C['text_dim']};background:transparent;"
        )
        self._main_prompt_lbl.setWordWrap(True)
        self._main_prompt_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._main_prompt_lbl.setToolTip(
            "معاينة أول جزء من style الـ prompt — كل مشهد له prompt كامل خاص بيه"
        )

        copy_btn = QPushButton("📋  نسخ")
        copy_btn.setObjectName("secondary")
        copy_btn.setFixedHeight(28)
        copy_btn.setFixedWidth(80)
        copy_btn.clicked.connect(
            lambda: QApplication.clipboard().setText(self._main_prompt_text)
        )

        lay.addWidget(prefix)
        lay.addWidget(self._main_prompt_lbl, 1)
        lay.addWidget(copy_btn)
        return w

    # ── Scenes panel ──────────────────────────────────────────────────────────

    def _build_scenes_panel(self, C: dict) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet("background:transparent;")
        v = QVBoxLayout(outer)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        # Sub-header row
        hdr = QHBoxLayout()
        scenes_lbl = QLabel("📋  المشاهد")
        scenes_lbl.setStyleSheet(
            f"font-weight:700;font-size:13px;color:{C['text']};background:transparent;"
        )
        self._count_lbl = QLabel("(0 مشهد)")
        self._count_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_dim']};background:transparent;"
        )
        refresh_btn = QPushButton("🔄  تحديث")
        refresh_btn.setObjectName("secondary")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self.reload_scenes)
        hdr.addWidget(scenes_lbl)
        hdr.addWidget(self._count_lbl)
        hdr.addStretch()
        hdr.addWidget(refresh_btn)
        v.addLayout(hdr)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumHeight(200)
        scroll.setMaximumHeight(420)

        self._scenes_container = QWidget()
        self._scenes_container.setStyleSheet("background:transparent;")
        self._scenes_layout = QVBoxLayout(self._scenes_container)
        self._scenes_layout.setContentsMargins(0, 0, 0, 0)
        self._scenes_layout.setSpacing(6)

        self._empty_lbl = QLabel(
            "⚠️  لا توجد مشاهد.\n"
            "شغّل الخطوة التحضيرية لتوليد prompts.json"
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:13px;background:transparent;padding:32px;"
        )
        self._scenes_layout.addWidget(self._empty_lbl)
        self._scenes_layout.addStretch()

        scroll.setWidget(self._scenes_container)
        v.addWidget(scroll)
        return outer

    # ── Auto panel (Chrome settings + progress + log) ─────────────────────────

    def _build_auto_panel(self, C: dict) -> QWidget:
        self._auto_panel = QWidget()
        self._auto_panel.setObjectName("card_dark")
        self._auto_panel.setVisible(False)
        v = QVBoxLayout(self._auto_panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        # Title
        title = QLabel("⚙️  إعدادات Auto Mode")
        title.setStyleSheet(
            f"font-weight:700;font-size:13px;color:{C['text']};background:transparent;"
        )
        v.addWidget(title)

        # Chrome path row
        chrome_row = QHBoxLayout()
        chrome_row.setSpacing(8)
        chrome_lbl = QLabel("Chrome:")
        chrome_lbl.setFixedWidth(70)
        chrome_lbl.setStyleSheet(f"color:{C['text_sec']};background:transparent;font-size:12px;")
        self._chrome_path_edit = QLineEdit()
        self._chrome_path_edit.setPlaceholderText("مسار chrome.exe (اتركه فارغاً للكشف التلقائي)")
        self._chrome_path_edit.setFixedHeight(30)
        self._chrome_path_edit.setStyleSheet(
            f"background:{C['surface2']};color:{C['text']};border:1px solid {C['border2']};"
            f"border-radius:6px;padding:4px 8px;font-size:12px;"
        )
        browse_chrome_btn = QPushButton("...")
        browse_chrome_btn.setObjectName("secondary")
        browse_chrome_btn.setFixedSize(36, 30)
        browse_chrome_btn.clicked.connect(self._browse_chrome)
        chrome_row.addWidget(chrome_lbl)
        chrome_row.addWidget(self._chrome_path_edit, 1)
        chrome_row.addWidget(browse_chrome_btn)
        v.addLayout(chrome_row)

        # Output dir row
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        out_lbl = QLabel("حفظ الصور:")
        out_lbl.setFixedWidth(70)
        out_lbl.setStyleSheet(f"color:{C['text_sec']};background:transparent;font-size:12px;")
        self._output_dir_edit = QLineEdit(_default_output_dir())
        self._output_dir_edit.setFixedHeight(30)
        self._output_dir_edit.setStyleSheet(
            f"background:{C['surface2']};color:{C['text']};border:1px solid {C['border2']};"
            f"border-radius:6px;padding:4px 8px;font-size:12px;"
        )
        browse_out_btn = QPushButton("...")
        browse_out_btn.setObjectName("secondary")
        browse_out_btn.setFixedSize(36, 30)
        browse_out_btn.clicked.connect(self._browse_output_dir)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self._output_dir_edit, 1)
        out_row.addWidget(browse_out_btn)
        v.addLayout(out_row)

        # Progress bar
        self._auto_pbar = QProgressBar()
        self._auto_pbar.setRange(0, 100)
        self._auto_pbar.setValue(0)
        self._auto_pbar.setFixedHeight(8)
        self._auto_pbar.setVisible(False)
        v.addWidget(self._auto_pbar)

        # Status label
        self._auto_status_lbl = QLabel("")
        self._auto_status_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_sec']};background:transparent;"
        )
        self._auto_status_lbl.setVisible(False)
        v.addWidget(self._auto_status_lbl)

        # Mini log
        self._auto_log = QPlainTextEdit()
        self._auto_log.setReadOnly(True)
        self._auto_log.setMaximumHeight(130)
        self._auto_log.setVisible(False)
        self._auto_log.setStyleSheet(
            f"background:{C['surface2']};color:{C['text_sec']};"
            f"font-family:'Consolas','Courier New',monospace;font-size:11px;"
            f"border-radius:6px;padding:6px;border:1px solid {C['border']};"
        )
        v.addWidget(self._auto_log)

        return self._auto_panel

    # ── Action row ────────────────────────────────────────────────────────────

    def _build_action_row(self, C: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._action_btn = QPushButton("🔗  فتح Flow في المتصفح")
        self._action_btn.setObjectName("secondary")
        self._action_btn.setFixedHeight(40)
        self._action_btn.setMinimumWidth(200)
        self._action_btn.clicked.connect(self._on_action_clicked)

        self._stop_btn = QPushButton("⛔  إيقاف")
        self._stop_btn.setObjectName("secondary")
        self._stop_btn.setFixedHeight(40)
        self._stop_btn.setFixedWidth(110)
        self._stop_btn.setVisible(False)
        self._stop_btn.clicked.connect(self._on_stop_clicked)

        self._action_status_lbl = QLabel("")
        self._action_status_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_dim']};background:transparent;"
        )

        row.addWidget(self._action_btn)
        row.addWidget(self._stop_btn)
        row.addWidget(self._action_status_lbl, 1)
        row.addStretch()
        return row

    # ─────────────────────────────────────────────────────────────────────────
    # Data
    # ─────────────────────────────────────────────────────────────────────────

    def reload_scenes(self):
        """Read prompts.json and rebuild scene cards."""
        C = get_colors()
        scenes, style_preview = _load_prompts()   # always returns (list, str)

        # Style preview bar
        self._main_prompt_text = style_preview
        if style_preview:
            self._main_prompt_lbl.setText(style_preview)
            self._main_prompt_lbl.setStyleSheet(
                f"font-size:12px;color:{C['text']};background:transparent;"
            )
        else:
            self._main_prompt_lbl.setText(
                "—  لم يُعثر على prompts.json — شغّل الخطوة التحضيرية أولاً"
            )
            self._main_prompt_lbl.setStyleSheet(
                f"font-size:12px;color:{C['text_dim']};background:transparent;"
            )

        # Clear old cards
        for sc in self._scene_cards:
            sc.setParent(None)
            sc.deleteLater()
        self._scene_cards.clear()
        self._scenes_data = []
        self._empty_lbl.setVisible(False)

        if not scenes:
            self._empty_lbl.setVisible(True)
            self._count_lbl.setText("(0 مشهد)")
            self._update_action_btn_state()
            return

        self._scenes_data = scenes
        self._count_lbl.setText(f"({len(scenes)} مشهد)")
        insert_pos = self._scenes_layout.count() - 1
        if insert_pos < 0:
            insert_pos = 0

        for idx, scene in enumerate(scenes, start=1):
            sc = _SceneCard(idx, scene, C, parent=self._scenes_container)
            self._scenes_layout.insertWidget(insert_pos, sc)
            self._scene_cards.append(sc)
            insert_pos += 1

        self._update_action_btn_state()

    def _update_action_btn_state(self):
        if not self._auto_btn.isChecked():
            return
        self._action_btn.setEnabled(bool(self._scenes_data))

    # ─────────────────────────────────────────────────────────────────────────
    # Browse dialogs
    # ─────────────────────────────────────────────────────────────────────────

    def _browse_chrome(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر Chrome", "", "Chrome (chrome.exe);;All Files (*)"
        )
        if path:
            self._chrome_path_edit.setText(path)

    def _browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "مجلد حفظ الصور", self._output_dir_edit.text()
        )
        if d:
            self._output_dir_edit.setText(d)

    # ─────────────────────────────────────────────────────────────────────────
    # Action handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_action_clicked(self):
        if self._auto_btn.isChecked():
            self._start_auto_mode()
        else:
            self._open_flow_browser()

    def _open_flow_browser(self):
        """Manual mode: open Flow in default browser."""
        import subprocess, sys
        url = "https://labs.google/fx/ar/tools/flow/"
        if sys.platform == "win32":
            subprocess.Popen(["start", url], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])

    def _on_stop_clicked(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def _on_continue_after_login(self):
        """
        User clicked 'Continue' after logging in.
        The FlowWorker polls current_url() automatically — just hide the banner.
        """
        self._login_banner.setVisible(False)
        self._log_auto("ℹ️  متابعة — سيتحقق النظام من تسجيل الدخول...")

    # ─────────────────────────────────────────────────────────────────────────
    # Auto Mode
    # ─────────────────────────────────────────────────────────────────────────

    def _start_auto_mode(self):
        """Validate inputs and launch FlowWorker."""
        if not self._scenes_data:
            self._set_action_status("⚠️  لا توجد مشاهد — شغّل الخطوة التحضيرية أولاً", error=True)
            return

        # Check websocket-client availability before launching thread
        try:
            import websocket  # noqa
        except ImportError:
            self._set_action_status(
                "❌  يحتاج: pip install websocket-client", error=True
            )
            self._log_auto(
                "لتفعيل Auto Mode شغّل في الـ Terminal:\n"
                "    pip install websocket-client\n"
                "ثم أعد تشغيل التطبيق."
            )
            self._show_auto_log(True)
            return

        from app.core.flow_automation import FlowWorker

        chrome_exe = self._chrome_path_edit.text().strip() or None
        output_dir = self._output_dir_edit.text().strip() or _default_output_dir()
        profile_dir = _default_profile_dir()

        self._worker = FlowWorker(
            scenes=self._scenes_data,
            main_prompt=self._main_prompt_text,
            output_dir=output_dir,
            chrome_exe=chrome_exe,
            chrome_profile=profile_dir,
            parent=self,
        )

        # Connect signals
        self._worker.log.connect(self._log_auto)
        self._worker.progress.connect(self._on_auto_progress)
        self._worker.scene_done.connect(self._on_scene_done)
        self._worker.fallback.connect(self._on_auto_fallback)
        self._worker.finished_ok.connect(self._on_auto_finished)
        self._worker.login_needed.connect(self._on_login_needed)
        self._worker.login_done.connect(lambda: self._login_banner.setVisible(False))
        self._worker.finished.connect(self._on_worker_finished)

        # UI state
        self._set_running_ui(True)
        self._show_auto_log(True)
        self._auto_pbar.setVisible(True)
        self._auto_pbar.setRange(0, 0)   # indeterminate
        self._log_auto("🚀  بدء Auto Mode...")
        self._set_action_status("جارٍ التوليد...")

        self._worker.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Worker signal handlers
    # ─────────────────────────────────────────────────────────────────────────

    def _on_login_needed(self):
        """Show login banner when Chrome is on the Google login page."""
        self._login_banner.setVisible(True)

    def _on_auto_progress(self, current: int, total: int):
        if total > 0:
            self._auto_pbar.setRange(0, 100)
            self._auto_pbar.setValue(int(current / total * 100))
        pct = f"{current}/{total}"
        self._auto_status_lbl.setText(f"مشهد {pct}")
        self._auto_status_lbl.setVisible(True)

    def _on_scene_done(self, idx: int, img_path: str):
        if 0 <= idx < len(self._scene_cards):
            self._scene_cards[idx].set_status("done" if img_path else "error")

    def _on_auto_fallback(self, reason: str):
        self._log_auto(f"⚠️  Fallback → Manual Mode\nالسبب: {reason}")
        self._set_action_status(f"تحويل لـ Manual: {reason}", error=True)
        # Switch to Manual mode
        self._manual_btn.setChecked(True)

    def _on_auto_finished(self):
        self._log_auto("🎉  اكتمل التوليد التلقائي!")
        self._auto_pbar.setRange(0, 100)
        self._auto_pbar.setValue(100)
        self._set_action_status("✅  اكتمل بنجاح")

    def _on_worker_finished(self):
        self._set_running_ui(False)

    # ─────────────────────────────────────────────────────────────────────────
    # UI state helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _set_running_ui(self, running: bool):
        self._action_btn.setEnabled(not running)
        self._stop_btn.setVisible(running)
        self._manual_btn.setEnabled(not running)
        self._auto_btn.setEnabled(not running)

    def _show_auto_log(self, visible: bool):
        self._auto_log.setVisible(visible)
        self._auto_status_lbl.setVisible(visible)

    def _log_auto(self, msg: str):
        self._auto_log.appendPlainText(msg)
        self._auto_log.verticalScrollBar().setValue(
            self._auto_log.verticalScrollBar().maximum()
        )
        logger.info(f"[AutoFlow] {msg}")

    def _set_action_status(self, msg: str, error: bool = False):
        C = get_colors()
        color = C["error"] if error else C["text_dim"]
        self._action_status_lbl.setText(msg)
        self._action_status_lbl.setStyleSheet(
            f"font-size:11px;color:{color};background:transparent;"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def refresh(self):
        """Called by PipelinePanel.refresh()."""
        self.reload_scenes()
