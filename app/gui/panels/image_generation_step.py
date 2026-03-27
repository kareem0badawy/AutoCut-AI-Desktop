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
import shutil
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QButtonGroup, QProgressBar,
    QPlainTextEdit, QLineEdit, QApplication, QFileDialog, QDialog,
    QGridLayout, QCheckBox, QStackedWidget,
)
from PySide6.QtGui import QPixmap, QFont

from app.gui.theme import get_colors
from app.gui.widgets import make_separator
from app.core.config_manager import BASE_DIR
from app.logger import logger
from app.core.flow_automation import SESSION_STATE_FILE

# ── Flow images source dir ────────────────────────────────────────────────────
FLOW_DIR = Path.home() / "Downloads" / "AutoCut" / "Flow"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _list_flow_images() -> list[Path]:
    """Return all image files inside FLOW_DIR, sorted by name."""
    if not FLOW_DIR.exists():
        return []
    return sorted(
        p for p in FLOW_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


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

# ─────────────────────────────────────────────────────────────────────────────
# Image Picker Dialog
# ─────────────────────────────────────────────────────────────────────────────

class _ImagePickerDialog(QDialog):
    """
    Shows all images found in FLOW_DIR as a thumbnail grid.
    User clicks one to select it.
    """
    def __init__(self, images: list[Path], current: Path | None, C: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("اختر صورة للمشهد")
        self.setMinimumSize(720, 500)
        self.setStyleSheet(
            f"background:{C['surface']};color:{C['text']};"
        )
        self._selected: Path | None = current

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Info bar
        info = QLabel(f"📁  {FLOW_DIR}   —   {len(images)} صورة")
        info.setStyleSheet(f"font-size:11px;color:{C['text_sec']};background:transparent;")
        root.addWidget(info)

        # Grid scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(8)
        cols = 4
        self._thumb_btns: list[QPushButton] = []
        for i, img_path in enumerate(images):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setChecked(img_path == current)
            btn.setFixedSize(150, 130)
            btn.setToolTip(img_path.name)
            px = QPixmap(str(img_path))
            if not px.isNull():
                btn.setIcon(px.scaled(130, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                btn.setIconSize(px.scaled(130, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation).size())
            btn.setText(f"\n{img_path.name[:18]}" if px.isNull() else "")
            border = C['accent'] if img_path == current else C['border']
            btn.setStyleSheet(
                f"background:{C['surface2']};border:2px solid {border};"
                f"border-radius:8px;color:{C['text_sec']};font-size:9px;"
                f"text-align:bottom center;"
            )
            btn.clicked.connect(lambda checked, p=img_path: self._on_pick(p))
            grid.addWidget(btn, i // cols, i % cols)
            self._thumb_btns.append(btn)
        self._images = images
        scroll.setWidget(grid_w)
        root.addWidget(scroll, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("إلغاء")
        cancel_btn.setObjectName("secondary")
        cancel_btn.setFixedHeight(34)
        cancel_btn.clicked.connect(self.reject)
        clear_btn = QPushButton("🗑  إزالة الاختيار")
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedHeight(34)
        clear_btn.clicked.connect(self._on_clear)
        self._ok_btn = QPushButton("✅  تأكيد")
        self._ok_btn.setObjectName("primary")
        self._ok_btn.setFixedHeight(34)
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ok_btn)
        root.addLayout(btn_row)

    def _on_pick(self, path: Path):
        self._selected = path
        C = get_colors()
        for i, btn in enumerate(self._thumb_btns):
            is_sel = (self._images[i] == path)
            border = C['accent'] if is_sel else C['border']
            btn.setStyleSheet(
                f"background:{C['surface2']};border:2px solid {border};"
                f"border-radius:8px;color:{C['text_sec']};font-size:9px;"
                f"text-align:bottom center;"
            )
            btn.setChecked(is_sel)

    def _on_clear(self):
        self._selected = None
        C = get_colors()
        for btn in self._thumb_btns:
            btn.setChecked(False)
            btn.setStyleSheet(
                f"background:{C['surface2']};border:2px solid {C['border']};"
                f"border-radius:8px;color:{C['text_sec']};font-size:9px;"
                f"text-align:bottom center;"
            )

    def result_path(self) -> Path | None:
        return self._selected


# ─────────────────────────────────────────────────────────────────────────────
# Scene Card widget
# ─────────────────────────────────────────────────────────────────────────────

class _SceneCard(QWidget):
    """One row: badge + title/prompt + Copy button + image thumbnail."""

    def __init__(self, index: int, scene_data: dict, C: dict,
                 flow_images: list[Path], parent=None):
        super().__init__(parent)
        self.setObjectName("step_card")
        self._prompt = (
            scene_data.get("main_prompt")
            or scene_data.get("prompt")
            or scene_data.get("description")
            or ""
        )
        self._scene_data = scene_data
        self._flow_images = flow_images   # shared list reference
        self._selected_image: Path | None = None

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

        # Status icon
        self._status_lbl = QLabel("⬜")
        self._status_lbl.setFixedWidth(22)
        self._status_lbl.setStyleSheet("background:transparent;font-size:14px;")

        # Thumbnail label
        self._thumb_lbl = QLabel()
        self._thumb_lbl.setFixedSize(64, 48)
        self._thumb_lbl.setAlignment(Qt.AlignCenter)
        self._thumb_lbl.setStyleSheet(
            f"background:{C['surface2']};border:1px solid {C['border']};"
            f"border-radius:4px;font-size:9px;color:{C['text_dim']};"
        )
        self._thumb_lbl.setText("لا توجد\nصورة")

        # Pick button
        self._pick_btn = QPushButton("🖼  اختر")
        self._pick_btn.setObjectName("secondary")
        self._pick_btn.setFixedHeight(28)
        self._pick_btn.setFixedWidth(80)
        self._pick_btn.setToolTip("اختر صورة من مجلد Flow")
        self._pick_btn.clicked.connect(self._on_pick)

        # Copy prompt button
        copy_btn = QPushButton("📋  Prompt")
        copy_btn.setObjectName("secondary")
        copy_btn.setFixedHeight(28)
        copy_btn.setFixedWidth(90)
        copy_btn.setToolTip("نسخ الـ main_prompt كاملاً للـ clipboard")
        copy_btn.clicked.connect(self._copy)

        lay.addWidget(badge)
        lay.addLayout(info, 1)
        lay.addWidget(self._thumb_lbl)
        lay.addWidget(self._status_lbl)
        lay.addWidget(self._pick_btn)
        lay.addWidget(copy_btn)

    def _copy(self):
        QApplication.clipboard().setText(self._prompt)

    def _on_pick(self):
        dlg = _ImagePickerDialog(
            self._flow_images, self._selected_image,
            get_colors(), parent=self
        )
        if dlg.exec() == QDialog.Accepted:
            self.set_image(dlg.result_path())

    def set_image(self, path: Path | None):
        """Assign an image to this scene card and update thumbnail."""
        self._selected_image = path
        C = get_colors()
        if path and path.exists():
            px = QPixmap(str(path)).scaled(
                64, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._thumb_lbl.setPixmap(px)
            self._thumb_lbl.setToolTip(path.name)
            self._thumb_lbl.setStyleSheet(
                f"background:{C['surface2']};border:2px solid {C['accent']};"
                f"border-radius:4px;"
            )
            self._status_lbl.setText("✅")
        else:
            self._thumb_lbl.clear()
            self._thumb_lbl.setText("لا توجد\nصورة")
            self._thumb_lbl.setStyleSheet(
                f"background:{C['surface2']};border:1px solid {C['border']};"
                f"border-radius:4px;font-size:9px;color:{C['text_dim']};"
            )
            self._status_lbl.setText("⬜")

    def update_flow_images(self, images: list[Path]):
        """Refresh the shared image list (after scan)."""
        self._flow_images = images

    @property
    def selected_image(self) -> Path | None:
        return self._selected_image

    @property
    def scene_number(self) -> int:
        return int(self._scene_data.get("scene_number", 0))

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
    • Scenes list with per-scene Copy buttons + image pickers
    • Image Intake: scan Flow dir, auto-assign or manual-pick
    • Handoff: rename to scene_{N}.ext and expose to Step 3
    • Auto panel:  Chrome path · output dir · progress · log · Stop btn
    • Login banner: shown when Chrome is waiting for Google login
    """

    # Emitted when user clicks "Next" with the session images folder path
    images_ready = Signal(str)   # str = session/images/ path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene_cards: list[_SceneCard] = []
        self._scenes_data: list[dict] = []
        self._main_prompt_text: str = ""
        self._worker = None          # FlowWorker instance
        self._flow_images: list[Path] = []   # images found in FLOW_DIR
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
        root.addWidget(self._build_image_intake_panel(C))  # NEW
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
            # Check if there's a saved session to resume
            self._check_resume_available()
        else:
            self._action_btn.setText("🔗  فتح Flow في المتصفح")
            self._action_btn.setObjectName("secondary")
            self._action_btn.setEnabled(True)
            if hasattr(self, "_resume_btn"):
                self._resume_btn.setVisible(False)
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

    # ── Image Intake panel ────────────────────────────────────────────────────

    def _build_image_intake_panel(self, C: dict) -> QWidget:
        """
        Panel for:
          1. Scanning FLOW_DIR for images
          2. Auto-assigning images to scenes by order
          3. Showing scan status + per-scene counts
          4. 'Next' handoff button
        """
        self._intake_panel = QWidget()
        self._intake_panel.setObjectName("card_dark")
        v = QVBoxLayout(self._intake_panel)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        # Title row
        title_row = QHBoxLayout()
        title_lbl = QLabel("🗂  استقبال الصور — Image Intake")
        title_lbl.setStyleSheet(
            f"font-weight:700;font-size:13px;color:{C['text']};background:transparent;"
        )
        title_row.addWidget(title_lbl)
        title_row.addStretch()

        # Flow dir label
        dir_lbl = QLabel(f"📁  {FLOW_DIR}")
        dir_lbl.setStyleSheet(
            f"font-size:10px;color:{C['text_dim']};background:transparent;"
        )
        dir_lbl.setToolTip(str(FLOW_DIR))
        title_row.addWidget(dir_lbl)
        v.addLayout(title_row)

        # Scan row
        scan_row = QHBoxLayout()
        scan_row.setSpacing(10)

        self._scan_btn = QPushButton("🔍  مسح مجلد Flow")
        self._scan_btn.setObjectName("secondary")
        self._scan_btn.setFixedHeight(32)
        self._scan_btn.clicked.connect(self._scan_flow_images)

        self._scan_status_lbl = QLabel("اضغط 'مسح' لتحميل الصور من مجلد Flow")
        self._scan_status_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_dim']};background:transparent;"
        )

        # Auto-assign toggle
        self._auto_assign_check = QCheckBox("تعيين تلقائي بالترتيب")
        self._auto_assign_check.setChecked(True)
        self._auto_assign_check.setStyleSheet(
            f"color:{C['text_sec']};background:transparent;font-size:11px;"
        )
        self._auto_assign_check.setToolTip(
            "عند المسح، يتم تعيين الصورة الأولى للمشهد الأول وهكذا تلقائياً"
        )

        scan_row.addWidget(self._scan_btn)
        scan_row.addWidget(self._auto_assign_check)
        scan_row.addWidget(self._scan_status_lbl, 1)
        v.addLayout(scan_row)

        # Handoff row
        handoff_row = QHBoxLayout()
        handoff_row.setSpacing(10)

        self._next_btn = QPushButton("✅  تسليم للخطوة 3")
        self._next_btn.setObjectName("primary")
        self._next_btn.setFixedHeight(36)
        self._next_btn.setMinimumWidth(180)
        self._next_btn.setEnabled(False)
        self._next_btn.setToolTip(
            "ينسخ الصور المحددة إلى session/images/ بأسماء scene_N.ext "
            "ليتعرف عليها AI Mapper تلقائياً"
        )
        self._next_btn.clicked.connect(self._on_next_clicked)

        self._next_status_lbl = QLabel("")
        self._next_status_lbl.setStyleSheet(
            f"font-size:11px;color:{C['text_dim']};background:transparent;"
        )

        handoff_row.addWidget(self._next_btn)
        handoff_row.addWidget(self._next_status_lbl, 1)
        v.addLayout(handoff_row)

        return self._intake_panel

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

        self._resume_btn = QPushButton("▶️  استئناف")
        self._resume_btn.setObjectName("secondary")
        self._resume_btn.setFixedHeight(40)
        self._resume_btn.setFixedWidth(120)
        self._resume_btn.setVisible(False)
        self._resume_btn.setToolTip("استئناف التوليد من حيث توقف")
        self._resume_btn.clicked.connect(self._on_resume_clicked)

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
        row.addWidget(self._resume_btn)
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
            sc = _SceneCard(idx, scene, C,
                            flow_images=self._flow_images,
                            parent=self._scenes_container)
            self._scenes_layout.insertWidget(insert_pos, sc)
            self._scene_cards.append(sc)
            insert_pos += 1

        self._update_action_btn_state()
        # Re-apply any existing scan so thumbnails show up immediately
        if self._flow_images:
            self._apply_scan_to_cards()

    def _update_action_btn_state(self):
        if not self._auto_btn.isChecked():
            return
        self._action_btn.setEnabled(bool(self._scenes_data))

    def _update_next_btn_state(self):
        """Enable Next button when at least one scene has a selected image."""
        has_any = any(sc.selected_image is not None for sc in self._scene_cards)
        if hasattr(self, "_next_btn"):
            self._next_btn.setEnabled(has_any)

    # ─────────────────────────────────────────────────────────────────────────
    # Image Intake logic
    # ─────────────────────────────────────────────────────────────────────────

    def _scan_flow_images(self):
        """Scan FLOW_DIR and refresh image list."""
        C = get_colors()
        images = _list_flow_images()
        self._flow_images = images

        # Push updated list to all cards
        for sc in self._scene_cards:
            sc.update_flow_images(images)

        count = len(images)
        if count == 0:
            self._scan_status_lbl.setText(
                f"⚠️  لا توجد صور في {FLOW_DIR}"
            )
            self._scan_status_lbl.setStyleSheet(
                f"font-size:11px;color:{get_colors()['warning']};background:transparent;"
            )
            return

        self._scan_status_lbl.setText(
            f"✅  {count} صورة — اضغط على كل مشهد لاختيار صورته"
        )
        self._scan_status_lbl.setStyleSheet(
            f"font-size:11px;color:{C['success']};background:transparent;"
        )
        logger.info(f"[ImageIntake] Scanned {count} images from {FLOW_DIR}")

        if self._auto_assign_check.isChecked():
            self._apply_scan_to_cards()

    def _apply_scan_to_cards(self):
        """Auto-assign images to scene cards by sequential order."""
        images = self._flow_images
        for i, sc in enumerate(self._scene_cards):
            if i < len(images):
                sc.set_image(images[i])
            else:
                sc.set_image(None)
        self._update_next_btn_state()

    # ─────────────────────────────────────────────────────────────────────────
    # Handoff: copy renamed images to session/images/
    # ─────────────────────────────────────────────────────────────────────────

    def _on_next_clicked(self):
        """
        For each scene card that has a selected image:
          1. Copy the image to <base_path>/session/images/
          2. Rename it to scene_{scene_number}{ext}
        Then emit images_ready(session_dir) so PipelinePanel can pick it up.
        """
        from app.core.config_manager import load_config, BASE_DIR
        C = get_colors()
        cfg = load_config()
        session_dir = Path(cfg.get("base_path", str(BASE_DIR))) / "session" / "images"
        try:
            session_dir.mkdir(parents=True, exist_ok=True)

            # Clear previous session images
            for old in session_dir.iterdir():
                try:
                    old.unlink()
                except Exception:
                    pass

            copied = 0
            missing = []
            for sc in self._scene_cards:
                img = sc.selected_image
                if img and img.exists():
                    dest_name = f"scene_{sc.scene_number}{img.suffix.lower()}"
                    dest = session_dir / dest_name
                    shutil.copy2(str(img), str(dest))
                    copied += 1
                    logger.info(f"[Handoff] {img.name} → {dest_name}")
                else:
                    missing.append(sc.scene_number)

            msg = f"✅  تم نقل {copied} صورة إلى session/images/"
            if missing:
                msg += f"  |  ⚠️ مشاهد بدون صورة: {missing}"

            self._next_status_lbl.setText(msg)
            self._next_status_lbl.setStyleSheet(
                f"font-size:11px;color:{C['success']};background:transparent;"
            )
            logger.info(f"[Handoff] Done — {copied} images → {session_dir}")

            # Emit for PipelinePanel
            self.images_ready.emit(str(session_dir))

        except Exception as e:
            self._next_status_lbl.setText(f"❌  خطأ: {e}")
            self._next_status_lbl.setStyleSheet(
                f"font-size:11px;color:{C['error']};background:transparent;"
            )
            logger.error(f"[Handoff] Error: {e}")

    # ── Public API for PipelinePanel ──────────────────────────────────────────

    def get_selected_images_folder(self) -> str | None:
        """
        Returns the session/images/ path if handoff was done,
        otherwise None.
        """
        from app.core.config_manager import load_config, BASE_DIR as _BD
        cfg = load_config()
        p = Path(cfg.get("base_path", str(_BD))) / "session" / "images"
        return str(p) if p.exists() and any(p.iterdir()) else None

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
            # --- Check if we already have generated images before starting ---
            existing = self._find_existing_images()
            if existing:
                self._log_auto(
                    f"ℹ️  وُجدت {sum(len(v) for v in existing.values())} صورة من جلسة سابقة — عرضها للاختيار..."
                )
                self._show_auto_log(True)
                self._show_completion_gallery(existing)
            else:
                self._start_auto_mode()
        else:
            self._open_flow_browser()

    def _open_flow_browser(self):
        """Manual mode: open Flow in default browser."""
        import subprocess, sys
        # Also ensure FLOW_DIR exists so user knows where to save
        FLOW_DIR.mkdir(parents=True, exist_ok=True)
        url = "https://labs.google/fx/ar/tools/flow/"
        self._set_action_status(
            f"تم فتح Flow — احفظ الصور داخل:  {FLOW_DIR}"
        )
        if sys.platform == "win32":
            subprocess.Popen(["start", url], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])

    def _on_stop_clicked(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()

    def _on_resume_clicked(self):
        """Launch FlowWorker with resume=True to continue from saved state."""
        if not self._scenes_data:
            self._set_action_status("⚠️  لا توجد مشاهد — أعد تحميل الصفحة", error=True)
            return
        self._start_auto_mode(resume=True)

    def _find_existing_images(self) -> dict | None:
        """
        Scan output_dir for images saved by a previous auto-mode run.
        Returns dict {scene_idx: [path1, path2, ...]} if enough images
        are found (at least 50% of scenes), else None.
        """
        import re
        output_dir = Path(
            self._output_dir_edit.text().strip() or _default_output_dir()
        )
        if not output_dir.exists() or not self._scenes_data:
            return None

        images_by_scene: dict[int, list] = {}
        for f in sorted(output_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                m = re.match(r'scene_(\d+)', f.name, re.IGNORECASE)
                if m:
                    snum = int(m.group(1))
                    images_by_scene.setdefault(snum, []).append(f)

        if not images_by_scene:
            return None

        # Need images for at least 50% of scenes
        needed = max(1, len(self._scenes_data) // 2)
        if len(images_by_scene) >= needed:
            return images_by_scene
        return None

    def _show_completion_gallery(self, images_by_scene: dict):
        """
        Show a modal where each scene displays its generated image options.
        User checks exactly one image per scene (or skips), then confirms.
        images_by_scene: dict  scene_number(int) -> list[Path]
        """
        C = get_colors()
        dlg = QDialog(self)
        dlg.setWindowTitle("🎉  اختر صورة لكل مشهد")
        dlg.setMinimumSize(920, 640)
        dlg.setStyleSheet(
            f"background:{C['surface']};color:{C['text']};"
            f"font-family:'Segoe UI', Arial, sans-serif;"
        )

        root = QVBoxLayout(dlg)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # --- Title ---
        total_scenes = len(self._scenes_data) if self._scenes_data else len(images_by_scene)
        title = QLabel(f"✅  تم توليد الصور — اختر صورة واحدة لكل مشهد")
        title.setStyleSheet(
            f"font-size:17px;font-weight:700;color:{C['accent']};background:transparent;"
        )
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        # --- Counter label ---
        counter_lbl = QLabel(f"0 / {total_scenes} مشهد مختار")
        counter_lbl.setStyleSheet(
            f"font-size:12px;color:{C['text_sec']};background:transparent;"
        )
        counter_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(counter_lbl)

        # --- Scroll grid ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(
            f"background:{C['surface2']};border-radius:10px;"
        )

        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(16)
        grid.setContentsMargins(12, 12, 12, 12)

        # Track selection: scene_number -> selected Path | None
        selected: dict[int, object] = {}
        # btn_groups: scene_number -> list[(btn, path)]
        btn_groups: dict[int, list] = {}

        def update_counter():
            chosen = sum(1 for v in selected.values() if v is not None)
            counter_lbl.setText(f"{chosen} / {total_scenes} مشهد مختار")
            ok_btn.setEnabled(chosen > 0)

        # Build a sorted list of (scene_number, paths)
        sorted_scenes = sorted(images_by_scene.items())
        col = 0
        row = 0
        max_cols = 4   # image options per scene in one row

        for s_idx, (scene_num, paths) in enumerate(sorted_scenes):
            selected[scene_num] = None
            btn_groups[scene_num] = []

            # Scene label row
            scene_name = f"مشهد {scene_num}"
            if self._scene_cards and (scene_num - 1) < len(self._scene_cards):
                sc_data = self._scene_cards[scene_num - 1]._scene_data
                scene_name = (
                    sc_data.get("label_text")
                    or sc_data.get("scene_title")
                    or sc_data.get("title")
                    or scene_name
                )

            # Each scene occupies its own block cell
            block = QWidget()
            block.setStyleSheet(
                f"background:{C['surface']};border:2px solid {C['border']};"
                f"border-radius:10px;padding:4px;"
            )
            block_v = QVBoxLayout(block)
            block_v.setSpacing(6)
            block_v.setContentsMargins(8, 8, 8, 8)

            # Scene title
            slbl = QLabel(f"#{scene_num}  {str(scene_name)[:30]}")
            slbl.setStyleSheet(
                f"font-size:11px;font-weight:700;color:{C['text_sec']};background:transparent;"
            )
            slbl.setAlignment(Qt.AlignCenter)
            block_v.addWidget(slbl)

            # Image options in a horizontal row
            opts_row = QHBoxLayout()
            opts_row.setSpacing(8)

            for opt_i, img_path in enumerate(paths):
                opt_w = QWidget()
                opt_w.setStyleSheet("background:transparent;")
                opt_v = QVBoxLayout(opt_w)
                opt_v.setSpacing(4)
                opt_v.setContentsMargins(0, 0, 0, 0)

                # Thumbnail button (acts as radio)
                thumb_btn = QPushButton()
                thumb_btn.setCheckable(True)
                thumb_btn.setFixedSize(140, 105)
                px = QPixmap(str(img_path))
                if not px.isNull():
                    thumb_btn.setIcon(px.scaled(128, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    thumb_btn.setIconSize(px.size().scaled(128, 96, Qt.KeepAspectRatio))
                else:
                    thumb_btn.setText("❌")
                thumb_btn.setStyleSheet(
                    f"background:{C['surface2']};border:2px solid {C['border']};"
                    f"border-radius:8px;"
                )
                thumb_btn.setToolTip(img_path.name)

                opt_lbl = QLabel(f"خيار {opt_i + 1}")
                opt_lbl.setStyleSheet(
                    f"font-size:9px;color:{C['text_dim']};background:transparent;"
                )
                opt_lbl.setAlignment(Qt.AlignCenter)

                opt_v.addWidget(thumb_btn, alignment=Qt.AlignCenter)
                opt_v.addWidget(opt_lbl)
                opts_row.addWidget(opt_w)

                btn_groups[scene_num].append((thumb_btn, img_path))

                def make_picker(snum, path, btn):
                    def on_click(checked):
                        # Deselect all in same scene, select this
                        for b, _ in btn_groups[snum]:
                            is_this = (b is btn)
                            b.setChecked(is_this)
                            b.setStyleSheet(
                                f"background:{C['surface2']};border:2px solid "
                                + (f"{C['accent']}" if is_this else f"{C['border']}")
                                + ";border-radius:8px;"
                            )
                        selected[snum] = path if checked else None
                        update_counter()
                    return on_click

                thumb_btn.clicked.connect(make_picker(scene_num, img_path, thumb_btn))

            block_v.addLayout(opts_row)
            grid.addWidget(block, s_idx // 3, s_idx % 3)

        scroll.setWidget(grid_w)
        root.addWidget(scroll, 1)

        # --- Buttons row ---
        btn_row = QHBoxLayout()

        cancel_btn2 = QPushButton("❌  إلغاء")
        cancel_btn2.setObjectName("secondary")
        cancel_btn2.setFixedHeight(36)
        cancel_btn2.clicked.connect(dlg.reject)

        select_all_btn = QPushButton("✅  تحديد الأولى للكل")
        select_all_btn.setObjectName("secondary")
        select_all_btn.setFixedHeight(36)
        def auto_select_first():
            for snum, pairs in btn_groups.items():
                if pairs:
                    btn, path = pairs[0]
                    for b, _ in pairs:
                        b.setChecked(False)
                        b.setStyleSheet(
                            f"background:{C['surface2']};border:2px solid {C['border']};border-radius:8px;"
                        )
                    btn.setChecked(True)
                    btn.setStyleSheet(
                        f"background:{C['surface2']};border:2px solid {C['accent']};border-radius:8px;"
                    )
                    selected[snum] = path
            update_counter()
        select_all_btn.clicked.connect(auto_select_first)

        ok_btn = QPushButton("✅  تأكيد الاختيار وتسليم للخطوة 3")
        ok_btn.setObjectName("primary")
        ok_btn.setFixedHeight(38)
        ok_btn.setMinimumWidth(220)
        ok_btn.setEnabled(False)

        btn_row.addWidget(cancel_btn2)
        btn_row.addWidget(select_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(ok_btn)
        root.addLayout(btn_row)

        def on_confirm():
            # Assign chosen images to scene cards & do handoff
            for i, sc in enumerate(self._scene_cards):
                snum = sc.scene_number
                chosen_path = selected.get(snum)
                if chosen_path:
                    sc.set_image(Path(chosen_path))
            dlg.accept()
            self._update_next_btn_state()
            self._on_next_clicked()   # auto-handoff

        ok_btn.clicked.connect(on_confirm)

        # Auto-select first option for every scene by default
        auto_select_first()

        dlg.exec()

    def _on_continue_after_login(self):
        """
        User clicked 'Continue' after logging in.
        The FlowWorker polls current_url() automatically — just hide the banner.
        """
        self._login_banner.setVisible(False)
        self._log_auto("ℹ️  متابعة — سيتحقق النظام من تسجيل الدخول...")



    # ── WebSocket / CDP error friendly display ────────────────────────────────
    def _handle_ws_error(self, msg: str):
        """
        Show a friendly message when WebSocket 403 is detected
        (Chrome not started with --remote-debugging-port).
        """
        if "403" in msg or "Forbidden" in msg or "WebSocket" in msg:
            self._set_action_status(
                "❌  Chrome غير متصل — شغّل Chrome بخيار --remote-debugging-port=9222",
                error=True
            )
            self._log_auto(
                "⚠️  خطأ في الاتصال بـ Chrome DevTools:\n"
                "  الحل: شغّل Chrome من الـ Terminal بهذا الأمر:\n"
                '  chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\\AutoCutProfile\n'
                "  أو استخدم Manual Mode بدلاً من Auto."
            )
            self._show_auto_log(True)
            self._worker.stop() if self._worker else None

    # ─────────────────────────────────────────────────────────────────────────
    # Auto Mode
    # ─────────────────────────────────────────────────────────────────────────

    def _start_auto_mode(self, resume: bool = False):
        """Validate inputs and launch FlowWorker. If resume=True, continues from saved state."""
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
            resume=resume,
            parent=self,
        )

        # Connect signals
        self._worker.log.connect(self._log_auto)
        self._worker.log.connect(self._handle_ws_error)
        self._worker.progress.connect(self._on_auto_progress)
        self._worker.scene_done.connect(self._on_scene_done)
        self._worker.fallback.connect(self._on_auto_fallback)
        self._worker.finished_ok.connect(self._on_auto_finished)
        self._worker.all_images_done.connect(self._on_all_images_done)  # NEW
        self._worker.login_needed.connect(self._on_login_needed)
        self._worker.login_done.connect(lambda: self._login_banner.setVisible(False))
        self._worker.finished.connect(self._on_worker_finished)

        # UI state
        self._set_running_ui(True)
        self._show_auto_log(True)
        self._auto_pbar.setVisible(True)
        self._auto_pbar.setRange(0, 0)   # indeterminate
        if resume:
            self._log_auto("▶️  استئناف Auto Mode من حيث توقف...")
            self._set_action_status("جارٍ الاستئناف...")
        else:
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
            sc = self._scene_cards[idx]
            if img_path:
                sc.set_status("done")
                # Auto-assign the generated image to the scene card
                p = Path(img_path)
                if p.exists():
                    sc.set_image(p)
                    self._update_next_btn_state()
            else:
                sc.set_status("error")

    def _on_auto_fallback(self, reason: str):
        self._log_auto(f"⚠️  Fallback → Manual Mode\nالسبب: {reason}")
        self._set_action_status(f"تحويل لـ Manual: {reason}", error=True)
        # Switch to Manual mode
        self._manual_btn.setChecked(True)
        # Show resume button if there's a session state
        self._check_resume_available()

    def _check_resume_available(self):
        """
        Show/hide the Resume button based on whether a session state file exists.
        Only relevant in Auto mode.
        """
        # Guard: auto panel may not be built yet during initial _set_mode call
        if not hasattr(self, "_output_dir_edit") or not hasattr(self, "_resume_btn"):
            return
        if not self._auto_btn.isChecked():
            self._resume_btn.setVisible(False)
            return
        output_dir = Path(self._output_dir_edit.text().strip() or _default_output_dir())
        state_file = output_dir / SESSION_STATE_FILE
        has_state = state_file.exists()
        self._resume_btn.setVisible(has_state)
        if has_state:
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                done = len(data.get("completed", []))
                total = data.get("total", 0)
                self._resume_btn.setToolTip(
                    f"استئناف — تم {done}/{total} مشهد — اضغط للمتابعة"
                )
                self._set_action_status(
                    f"ℹ️  توجد جلسة محفوظة ({done}/{total} مشهد) — اضغط 'استئناف' للمتابعة"
                )
            except Exception:
                pass

    def _on_auto_finished(self):
        self._log_auto("🎉  اكتمل التوليد التلقائي!")
        self._auto_pbar.setRange(0, 100)
        self._auto_pbar.setValue(100)
        self._set_action_status("✅  اكتمل بنجاح")
        self._resume_btn.setVisible(False)
        # Gallery is shown by _on_all_images_done via all_images_done signal

    def _on_all_images_done(self, images_by_scene: dict):
        """
        Called via FlowWorker.all_images_done signal.
        images_by_scene: {scene_idx(int): [path_str, ...]}
        Convert to {scene_number: [Path, ...]} and show gallery.
        """
        # Convert scene_idx (0-based) to scene_number (1-based) and Path objects
        converted: dict[int, list] = {}
        for idx, paths in images_by_scene.items():
            snum = idx + 1
            converted[snum] = [Path(p) for p in paths if Path(p).exists()]

        converted = {k: v for k, v in converted.items() if v}  # drop empties

        if converted:
            self._show_completion_gallery(converted)
        else:
            # Fallback: scan output dir
            output_dir = Path(
                self._output_dir_edit.text().strip() or _default_output_dir()
            )
            existing = self._find_existing_images()
            if existing:
                self._show_completion_gallery(existing)
            else:
                self._log_auto("⚠️  لم تُعثر على صور محفوظة.")

    def _on_worker_finished(self):
        self._set_running_ui(False)
        # After any stop (user-initiated or error), check if we can resume
        if self._auto_btn.isChecked():
            self._check_resume_available()


    # ─────────────────────────────────────────────────────────────────────────
    # UI state helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _set_running_ui(self, running: bool):
        self._action_btn.setEnabled(not running)
        self._stop_btn.setVisible(running)
        self._resume_btn.setVisible(False)  # hide while running
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
        # Also auto-scan if FLOW_DIR already has images
        if FLOW_DIR.exists() and any(
            p.suffix.lower() in IMAGE_EXTS for p in FLOW_DIR.iterdir() if p.is_file()
        ):
            self._scan_flow_images()
