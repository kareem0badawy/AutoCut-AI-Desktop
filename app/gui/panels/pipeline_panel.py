import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QPlainTextEdit, QCheckBox,
    QMessageBox, QFileDialog, QApplication,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import make_separator, make_badge, NoScrollSpinBox
from app.core.config_manager import load_config, load_style, validate_config, BASE_DIR
from app.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Background task thread
# ─────────────────────────────────────────────────────────────────────────────

class _TaskThread(QThread):
    log      = Signal(str)
    progress = Signal(int, int)
    done     = Signal(bool, str)

    def __init__(self, task_fn):
        super().__init__()
        self._task_fn = task_fn

    def run(self):
        try:
            self._task_fn(
                log=lambda msg: self.log.emit(str(msg)),
                progress=lambda cur, total: self.progress.emit(cur, total),
            )
            self.done.emit(True, "")
        except Exception as e:
            self.done.emit(False, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


# ─────────────────────────────────────────────────────────────────────────────
# PipelinePanel
# ─────────────────────────────────────────────────────────────────────────────

class PipelinePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._step_cards: list[dict] = []
        self._translatable: dict[str, QLabel | QPushButton | QCheckBox] = {}

        # ── Upload state ──────────────────────────────────────────────────────
        self._uploaded_script: Path | None = None
        self._uploaded_images: list[Path]  = []
        self._uploaded_audio:  Path | None = None

        self._step_progress: dict = {}
        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(28)

        layout.addWidget(self._header_section())
        layout.addWidget(self._preparation_section())   # Section A
        layout.addWidget(self._pipeline_section())      # Section B
        layout.addWidget(self._export_section())
        layout.addWidget(self._log_section())
        layout.addStretch()

        scroll.setWidget(container)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    # ── Header ────────────────────────────────────────────────────────────────

    def _header_section(self) -> QWidget:
        C = get_colors()
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel(t("pipeline_title"))
        title.setObjectName("heading")
        sub = QLabel(t("pipeline_subtitle"))
        sub.setStyleSheet(f"color: {C['text_sec']}; font-size: 14px; background: transparent;")
        sub.setWordWrap(True)
        self._translatable["pipeline_title"]    = title
        self._translatable["pipeline_subtitle"] = sub
        v.addWidget(title)
        v.addWidget(sub)
        return w

    # ── Section A: Preparation (script upload + prompt generation) ────────────

    def _preparation_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        root = QVBoxLayout(card)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # title
        sec_title = QLabel("📝  " + t("prep_title", fallback="الخطوة التحضيرية — توليد المشاهد"))
        sec_title.setStyleSheet(
            f"font-weight: 700; font-size: 16px; color: {C['text']}; background: transparent;"
        )
        sec_desc = QLabel(t(
            "prep_subtitle",
            fallback="ارفع السكريبت، ثم شغّل توليد المشاهد لإنشاء prompts.json"
        ))
        sec_desc.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
        sec_desc.setWordWrap(True)
        root.addWidget(sec_title)
        root.addWidget(sec_desc)
        root.addWidget(make_separator(C))

        # content row: script slot + options + run button
        content_row = QHBoxLayout()
        content_row.setSpacing(16)

        # script upload slot
        self._script_slot = self._make_upload_slot(
            icon="📄",
            title=t("upload_script_title"),
            desc=t("upload_script_desc"),
            btn_text=t("upload_btn"),
            slot_id="script",
            C=C,
        )
        content_row.addWidget(self._script_slot["widget"], 2)

        # options (reset + limit) + run-prompts button
        opts_col = QVBoxLayout()
        opts_col.setSpacing(10)

        # step1 options widget
        opts = self._build_step1_options(C)
        self._step1_opts_widget = opts
        opts_col.addWidget(opts)

        # run prompts button
        self._run_prompts_btn = QPushButton("  ▶  " + t("run_step"))
        self._run_prompts_btn.setObjectName("primary")
        self._run_prompts_btn.setFixedHeight(40)
        self._run_prompts_btn.setEnabled(False)   # gated: needs script
        self._run_prompts_btn.clicked.connect(self._run_step1)

        # progress + status for prompts
        self._pbar_prompts = QProgressBar()
        self._pbar_prompts.setFixedHeight(6)
        self._pbar_prompts.setVisible(False)
        self._pbar_prompts.setRange(0, 100)
        self._status_prompts = QLabel("")
        self._status_prompts.setVisible(False)
        self._status_prompts.setStyleSheet("background: transparent; font-size: 11px;")

        opts_col.addWidget(self._run_prompts_btn)
        opts_col.addWidget(self._pbar_prompts)
        opts_col.addWidget(self._status_prompts)
        opts_col.addStretch()

        content_row.addLayout(opts_col, 3)
        root.addLayout(content_row)
        return card

    # ── Section B: Pipeline (images + audio + mapper + builder) ───────────────

    def _pipeline_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        root = QVBoxLayout(card)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # title
        sec_title = QLabel("🎬  " + t("pipeline_steps_title", fallback="خطوات بناء الفيديو"))
        sec_title.setStyleSheet(
            f"font-weight: 700; font-size: 16px; color: {C['text']}; background: transparent;"
        )
        sec_desc = QLabel(t(
            "pipeline_steps_subtitle",
            fallback="ارفع الصور والصوت، ثم شغّل الخطوات بالترتيب"
        ))
        sec_desc.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
        sec_desc.setWordWrap(True)
        root.addWidget(sec_title)
        root.addWidget(sec_desc)
        root.addWidget(make_separator(C))

        # upload slots row
        slots_row = QHBoxLayout()
        slots_row.setSpacing(12)
        self._images_slot = self._make_upload_slot(
            icon="🖼️",
            title=t("upload_images_title"),
            desc=t("upload_images_desc"),
            btn_text=t("upload_btn_multi"),
            slot_id="images",
            C=C,
        )
        self._audio_slot = self._make_upload_slot(
            icon="🎵",
            title=t("upload_audio_title"),
            desc=t("upload_audio_desc"),
            btn_text=t("upload_btn"),
            slot_id="audio",
            C=C,
        )
        slots_row.addWidget(self._images_slot["widget"], 1)
        slots_row.addWidget(self._audio_slot["widget"],  1)
        root.addLayout(slots_row)

        root.addWidget(make_separator(C))

        # step cards: Mapper → Video Builder
        step_defs = [
            {
                "num":        "1",
                "title_key":  "step3_title",
                "desc_key":   "step3_desc",
                "input_key":  "step3_input",
                "output_key": "step3_output",
                "run_fn":     self._run_step3,
                "color":      "#8b5cf6",
            },
            {
                "num":        "2",
                "title_key":  "step4_title",
                "desc_key":   "step4_desc",
                "input_key":  "step4_input",
                "output_key": "step4_output",
                "run_fn":     self._run_step4,
                "color":      C["success"],
            },
        ]

        self._step_cards = []
        for i, step in enumerate(step_defs):
            cw, refs = self._build_step_card(step, C)
            refs["step_def"] = step
            self._step_cards.append(refs)
            root.addWidget(cw)
            if i < len(step_defs) - 1:
                arr = QLabel("↓")
                arr.setAlignment(Qt.AlignCenter)
                arr.setStyleSheet(
                    f"color: {C['text_dim']}; font-size: 20px; background: transparent;"
                )
                root.addWidget(arr)

        root.addSpacing(8)

        # Run All row
        run_row = QHBoxLayout()
        self._run_all_btn = QPushButton("  ⚡  " + t("run_all"))
        self._run_all_btn.setObjectName("primary")
        self._run_all_btn.setFixedHeight(44)
        self._run_all_btn.setEnabled(False)
        self._run_all_btn.clicked.connect(self._run_all)
        self._run_all_desc = QLabel(t("run_all_desc"))
        self._run_all_desc.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 12px; background: transparent;"
        )
        self._translatable["run_all"]      = self._run_all_btn
        self._translatable["run_all_desc"] = self._run_all_desc
        run_row.addWidget(self._run_all_btn)
        run_row.addSpacing(12)
        run_row.addWidget(self._run_all_desc)
        run_row.addStretch()
        root.addLayout(run_row)

        # initial state
        self._update_pipeline_buttons()
        return card

    # ── Upload slot factory ───────────────────────────────────────────────────

    def _make_upload_slot(self, *, icon, title, desc, btn_text, slot_id, C) -> dict:
        box = QWidget()
        box.setObjectName("card_dark")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 22px; background: transparent;")
        icon_lbl.setFixedWidth(32)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-weight: 700; font-size: 14px; color: {C['text']}; background: transparent;"
        )
        hdr.addWidget(icon_lbl)
        hdr.addWidget(title_lbl, 1)
        lay.addLayout(hdr)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            f"font-size: 11px; color: {C['text_sec']}; background: transparent;"
        )
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)

        status_lbl = QLabel("⬜  " + t("upload_not_done"))
        status_lbl.setStyleSheet(
            f"font-size: 11px; color: {C['text_dim']}; background: transparent; font-weight: 600;"
        )
        lay.addWidget(status_lbl)

        btn = QPushButton(btn_text)
        btn.setObjectName("secondary")
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda _, sid=slot_id: self._on_upload_clicked(sid))
        lay.addWidget(btn)

        return {"widget": box, "status": status_lbl, "btn": btn}

    # ── Step card ─────────────────────────────────────────────────────────────

    def _build_step_card(self, step: dict, C: dict) -> tuple[QWidget, dict]:
        card = QWidget()
        card.setObjectName("step_card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(14)

        num = QLabel(step["num"])
        num.setFixedSize(36, 36)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet(
            f"background: {step['color']}22; color: {step['color']}; "
            f"border: 2px solid {step['color']}; border-radius: 18px; "
            f"font-weight: bold; font-size: 15px;"
        )

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel(t(step["title_key"]))
        title_lbl.setStyleSheet(
            f"font-weight: 700; font-size: 15px; color: {C['text']}; background: transparent;"
        )
        desc_lbl = QLabel(t(step["desc_key"]))
        desc_lbl.setStyleSheet(
            f"font-size: 12px; color: {C['text_sec']}; background: transparent;"
        )
        desc_lbl.setWordWrap(True)
        title_col.addWidget(title_lbl)
        title_col.addWidget(desc_lbl)

        run_btn = QPushButton("  ▶  " + t("run_step"))
        run_btn.setObjectName("primary")
        run_btn.setFixedHeight(34)
        run_btn.setFixedWidth(120)
        run_btn.setEnabled(False)
        run_btn.clicked.connect(step["run_fn"])

        top.addWidget(num)
        top.addLayout(title_col, 1)
        top.addWidget(run_btn)
        lay.addLayout(top)

        lay.addWidget(make_separator(C))

        io_row = QHBoxLayout()
        io_row.setSpacing(20)
        in_lbl = QLabel(t(step["input_key"]))
        in_lbl.setStyleSheet(f"font-size: 11px; color: {C['text_dim']}; background: transparent;")
        in_lbl.setWordWrap(True)
        out_lbl = QLabel(t(step["output_key"]))
        out_lbl.setStyleSheet(
            f"font-size: 11px; color: {step['color']}; font-weight: 600; background: transparent;"
        )
        out_lbl.setWordWrap(True)
        io_row.addWidget(in_lbl, 1)
        io_row.addWidget(QLabel("→"))
        io_row.addWidget(out_lbl, 1)
        lay.addLayout(io_row)

        pbar = QProgressBar()
        pbar.setVisible(False)
        pbar.setFixedHeight(6)
        pbar.setRange(0, 100)
        pbar.setValue(0)
        lay.addWidget(pbar)
        self._step_progress[f"pbar_{step['num']}"] = pbar

        status_lbl = QLabel("")
        status_lbl.setStyleSheet("background: transparent; font-size: 11px;")
        status_lbl.setVisible(False)
        lay.addWidget(status_lbl)

        # Big progress bar for video builder (step 2)
        if step["num"] == "2":
            C2 = C
            scene_lbl = QLabel("")
            scene_lbl.setObjectName("label")
            scene_lbl.setStyleSheet(
                f"font-size: 11px; color: {C2['text_sec']}; background: transparent;"
            )
            scene_lbl.setVisible(False)
            big_pbar = QProgressBar()
            big_pbar.setProperty("big", True)
            big_pbar.setFixedHeight(18)
            big_pbar.setRange(0, 100)
            big_pbar.setValue(0)
            big_pbar.setFormat("%p%")
            big_pbar.setTextVisible(True)
            big_pbar.setVisible(False)
            lay.addWidget(scene_lbl)
            lay.addWidget(big_pbar)
            self._step_progress["scene_label"] = scene_lbl
            self._step_progress["big_pbar_2"] = big_pbar

        refs = {
            "title_lbl": title_lbl,
            "desc_lbl":  desc_lbl,
            "in_lbl":    in_lbl,
            "out_lbl":   out_lbl,
            "run_btn":   run_btn,
            "pbar":      pbar,
            "status_lbl": status_lbl,
        }
        return card, refs

    def _build_step1_options(self, C: dict) -> QWidget:
        grp = QWidget()
        grp.setObjectName("card_dark")
        lay = QVBoxLayout(grp)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        title = QLabel(t("step1_options"))
        title.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {C['text']}; background: transparent;"
        )
        self._translatable["step1_options"] = title
        lay.addWidget(title)

        self._reset_check = QCheckBox(t("reset_option"))
        self._reset_check.setStyleSheet(f"color: {C['text_sec']}; background: transparent;")
        self._translatable["reset_option"] = self._reset_check
        lay.addWidget(self._reset_check)

        limit_row = QHBoxLayout()
        self._limit_check = QCheckBox(t("limit_option"))
        self._limit_check.setStyleSheet(f"color: {C['text_sec']}; background: transparent;")
        self._limit_spin = NoScrollSpinBox()
        self._limit_spin.setRange(1, 999)
        self._limit_spin.setValue(10)
        self._limit_spin.setFixedWidth(70)
        self._limit_spin.setEnabled(False)
        self._limit_check.toggled.connect(self._limit_spin.setEnabled)
        self._translatable["limit_option"] = self._limit_check
        limit_row.addWidget(self._limit_check)
        limit_row.addWidget(self._limit_spin)
        limit_row.addStretch()
        lay.addLayout(limit_row)

        note = QLabel(t("limit_note"))
        note.setStyleSheet(
            f"font-size: 11px; color: {C['text_dim']}; background: transparent;"
        )
        self._translatable["limit_note"] = note
        lay.addWidget(note)
        return grp

    # ── Export + log sections ─────────────────────────────────────────────────

    def _export_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(4)
        title = QLabel("🎬  " + t("export_video"))
        title.setStyleSheet(
            f"font-weight: 700; font-size: 16px; color: {C['text']}; background: transparent;"
        )
        desc = QLabel(t("export_video_desc"))
        desc.setStyleSheet(
            f"font-size: 12px; color: {C['text_sec']}; background: transparent;"
        )
        self._translatable["export_video"]      = title
        self._translatable["export_video_desc"] = desc
        left.addWidget(title)
        left.addWidget(desc)

        self._export_btn = QPushButton(t("open_output_folder"))
        self._export_btn.setObjectName("export_btn")
        self._export_btn.setFixedHeight(48)
        self._export_btn.setFixedWidth(200)
        self._export_btn.clicked.connect(self._open_output)
        self._translatable["open_output_folder"] = self._export_btn

        row.addLayout(left, 1)
        row.addWidget(self._export_btn)
        lay.addLayout(row)
        return card

    def _log_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel(t("logs_title"))
        title.setObjectName("subheading")
        title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {C['text']}; background: transparent;"
        )
        copy_btn = QPushButton(t("copy_logs"))
        copy_btn.setObjectName("secondary")
        copy_btn.setFixedHeight(28)
        copy_btn.clicked.connect(self._copy_logs)
        self._translatable["copy_logs"] = copy_btn

        clear_btn = QPushButton(t("clear_logs"))
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear_logs)
        self._translatable["logs_title"]  = title
        self._translatable["clear_logs"]  = clear_btn

        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(copy_btn)
        hdr.addSpacing(6)
        hdr.addWidget(clear_btn)
        lay.addLayout(hdr)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(200)
        self._log_view.setMaximumHeight(320)
        self._log_view.setStyleSheet(
            f"background: {C['surface2']}; color: {C['text_sec']}; "
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; "
            f"border-radius: 8px; padding: 8px; border: 1px solid {C['border']};"
        )
        lay.addWidget(self._log_view)
        return card

    # ─────────────────────────────────────────────────────────────────────────
    # Upload logic
    # ─────────────────────────────────────────────────────────────────────────

    def _on_upload_clicked(self, slot_id: str):
        C = get_colors()
        if slot_id == "script":
            path, _ = QFileDialog.getOpenFileName(
                self, t("upload_script_title"),
                "", "Script Files (*.py *.txt *.json);;All Files (*)"
            )
            if path:
                self._uploaded_script = Path(path)
                self._update_slot_status(
                    self._script_slot, done=True,
                    text=f"✅  {Path(path).name}", C=C
                )
                logger.info(f"Script uploaded: {path}")
                self._update_prep_button()

        elif slot_id == "images":
            paths, _ = QFileDialog.getOpenFileNames(
                self, t("upload_images_title"),
                "", "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)"
            )
            if paths:
                self._uploaded_images = [Path(p) for p in paths]
                count = len(paths)
                self._update_slot_status(
                    self._images_slot, done=True,
                    text=f"✅  {count} " + t("upload_images_count"), C=C
                )
                logger.info(f"Images uploaded: {count} files")
                self._update_pipeline_buttons()

        elif slot_id == "audio":
            path, _ = QFileDialog.getOpenFileName(
                self, t("upload_audio_title"),
                "", "Audio Files (*.mp3 *.wav *.aac *.ogg *.flac);;All Files (*)"
            )
            if path:
                self._uploaded_audio = Path(path)
                self._update_slot_status(
                    self._audio_slot, done=True,
                    text=f"✅  {Path(path).name}", C=C
                )
                logger.info(f"Audio uploaded: {path}")
                self._update_pipeline_buttons()

    @staticmethod
    def _update_slot_status(slot: dict, *, done: bool, text: str, C: dict):
        lbl: QLabel = slot["status"]
        lbl.setText(text)
        color = C["success"] if done else C["text_dim"]
        lbl.setStyleSheet(
            f"font-size: 11px; color: {color}; background: transparent; font-weight: 600;"
        )

    def _script_ready(self) -> bool:
        return self._uploaded_script is not None

    def _pipeline_ready(self) -> bool:
        return bool(self._uploaded_images and self._uploaded_audio)

    def _update_prep_button(self):
        if hasattr(self, "_run_prompts_btn"):
            self._run_prompts_btn.setEnabled(self._script_ready())

    def _update_pipeline_buttons(self):
        ready = self._pipeline_ready()
        if hasattr(self, "_run_all_btn"):
            self._run_all_btn.setEnabled(ready)
        for refs in self._step_cards:
            if "run_btn" in refs:
                refs["run_btn"].setEnabled(ready)

    # ─────────────────────────────────────────────────────────────────────────
    # Log helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _append_log(self, msg: str):
        self._log_view.appendPlainText(msg)
        self._log_view.verticalScrollBar().setValue(
            self._log_view.verticalScrollBar().maximum()
        )

    def _clear_logs(self):
        self._log_view.clear()

    def _copy_logs(self):
        text = self._log_view.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self._append_log("📋 " + t("copy_logs_done"))

    # ─────────────────────────────────────────────────────────────────────────
    # Running state
    # ─────────────────────────────────────────────────────────────────────────

    def _set_running(self, running: bool, pbar_key: str = None):
        try:
            pipeline_ok = not running and self._pipeline_ready()
            script_ok   = not running and self._script_ready()

            if hasattr(self, "_run_all_btn"):
                self._run_all_btn.setEnabled(pipeline_ok)
            if hasattr(self, "_run_prompts_btn"):
                self._run_prompts_btn.setEnabled(script_ok)
            for refs in self._step_cards:
                if "run_btn" in refs:
                    refs["run_btn"].setEnabled(pipeline_ok)

            if pbar_key:
                pbar = self._step_progress.get(pbar_key)
                if pbar:
                    if running:
                        pbar.setVisible(True)
                        pbar.setRange(0, 0)
                    else:
                        pbar.setRange(0, 100)
                        pbar.setValue(100)

            # prompts pbar
            if pbar_key == "pbar_prompts":
                if running:
                    self._pbar_prompts.setVisible(True)
                    self._pbar_prompts.setRange(0, 0)
                else:
                    self._pbar_prompts.setRange(0, 100)
                    self._pbar_prompts.setValue(100)

            # ── Step 4 (Video Builder): show big progress bar immediately ──────
            if pbar_key == "pbar_2":
                big  = self._step_progress.get("big_pbar_2")
                lbl  = self._step_progress.get("scene_label")
                if big:
                    if running:
                        big.setVisible(True)
                        big.setRange(0, 0)   # indeterminate / pulse
                        big.setFormat("⏳ جارٍ بناء الفيديو...")
                        big.setTextVisible(True)
                    else:
                        big.setRange(0, 100)
                        big.setValue(100)
                        big.setFormat("✅  %p%")
                if lbl:
                    lbl.setVisible(running)
                    if running:
                        lbl.setText("🎬  جارٍ معالجة المشاهد...")

        except Exception as e:
            logger.error(f"_set_running error: {e}\n{traceback.format_exc()}")


    def _on_progress(self, cur: int, total: int, pbar_key: str = "pbar_1"):
        try:
            pbar = self._step_progress.get(pbar_key) or (
                self._pbar_prompts if pbar_key == "pbar_prompts" else None
            )
            if pbar and total > 0:
                pbar.setRange(0, 100)
                pbar.setValue(int(cur / total * 100))

            # Video builder big progress bar (pbar_2 = step 2)
            if pbar_key in ("pbar_2", "pbar_1") and total > 0:
                big = self._step_progress.get("big_pbar_2")
                lbl = self._step_progress.get("scene_label")
                if big:
                    big.setVisible(True)
                    big.setRange(0, 100)
                    big.setValue(int(cur / total * 100))
                if lbl:
                    lbl.setVisible(True)
                    lbl.setText(f"🎬  مشهد {cur} من {total}")
        except Exception as e:
            logger.error(f"_on_progress error: {e}")

    def _on_finished(self, success: bool, err: str, pbar_key: str = "pbar_1", step_idx: int = 0):
        try:
            self._set_running(False, pbar_key)
            C = get_colors()
            if success:
                msg   = t("done_success")
                color = C["success"]
                logger.info(f"Step finished successfully [{pbar_key}]")
            else:
                msg   = t("done_error")
                color = C["error"]
                self._append_log(err)
                logger.error(f"Step failed [{pbar_key}]:\n{err}")

            # Update status label — prompts step or pipeline step
            if pbar_key == "pbar_prompts":
                self._status_prompts.setText(msg)
                self._status_prompts.setStyleSheet(
                    f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;"
                )
                self._status_prompts.setVisible(True)
            elif 0 <= step_idx < len(self._step_cards):
                sl = self._step_cards[step_idx].get("status_lbl")
                if sl:
                    sl.setText(msg)
                    sl.setStyleSheet(
                        f"color: {color}; font-size: 12px; font-weight: 600; background: transparent;"
                    )
                    sl.setVisible(True)

            self._append_log(msg)
        except Exception as e:
            logger.critical(f"_on_finished CRASH: {e}\n{traceback.format_exc()}")

    def _start_task(self, fn, pbar_key: str, step_idx: int, finish_key: str = None):
        fk = finish_key if finish_key is not None else pbar_key
        thread = _TaskThread(fn)
        thread.log.connect(self._append_log)
        thread.progress.connect(
            lambda c, tot, pk=pbar_key: self._on_progress(c, tot, pk)
        )
        thread.done.connect(
            lambda ok, err, pk=fk, si=step_idx: self._on_finished(ok, err, pk, si)
        )
        thread.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        thread.start()

    # ─────────────────────────────────────────────────────────────────────────
    # Validation
    # ─────────────────────────────────────────────────────────────────────────

    def _validate(self) -> list[str]:
        cfg = load_config()
        return validate_config(cfg)

    def _prepare_session_cfg(self, cfg: dict) -> dict:
        """
        Inject uploaded files into cfg so ai_mapper and video_builder
        use EXACTLY the files the user uploaded — not old cached folders.
        """
        import shutil
        cfg = dict(cfg)  # shallow copy — don't mutate the original

        # ── Uploaded images → copy to session/images ──────────────────────────
        if self._uploaded_images:
            base = Path(cfg["base_path"])
            session_dir = base / "session" / "images"
            session_dir.mkdir(parents=True, exist_ok=True)

            # Clear previous session images
            for old in session_dir.iterdir():
                try:
                    old.unlink()
                except Exception:
                    pass

            # Copy uploaded images (preserve original filenames!)
            for img_path in self._uploaded_images:
                dest = session_dir / img_path.name
                shutil.copy2(str(img_path), str(dest))

            cfg["images_folder"] = str(session_dir)
            logger.info(f"Session images folder: {session_dir} ({len(self._uploaded_images)} files)")

        # ── Uploaded audio → inject path directly ─────────────────────────────
        if self._uploaded_audio:
            cfg["audio_path"] = str(self._uploaded_audio)
            logger.info(f"Session audio: {self._uploaded_audio}")

        return cfg

    # ─────────────────────────────────────────────────────────────────────────
    # Step runners
    # ─────────────────────────────────────────────────────────────────────────

    def _run_step1(self):
        """Run prompt generator (Preparation section)."""
        try:
            errors = self._validate()
            if errors:
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return
            cfg   = load_config()
            style = load_style()
            reset = self._reset_check.isChecked()
            limit = self._limit_spin.value() if self._limit_check.isChecked() else None
            logger.info(f"Starting prompt generation — reset={reset}, limit={limit}")
            self._append_log("▶ " + t("step1_title"))
            self._set_running(True, "pbar_prompts")

            def task(log, progress):
                from app.core.prompt_generator import run_prompt_generation
                run_prompt_generation(cfg, style, reset=reset, limit=limit,
                                      log=log, progress=progress)

            self._start_task(task, pbar_key="pbar_prompts", step_idx=-1)
        except Exception as e:
            logger.critical(f"_run_step1 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "pbar_prompts")

    def _run_step3(self):
        """Run AI Mapper (pipeline step 1)."""
        try:
            errors = self._validate()
            if errors:
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return
            cfg = self._prepare_session_cfg(load_config())
            logger.info(f"Starting AI Mapper | images_folder={cfg.get('images_folder')}")
            self._append_log("▶ " + t("step3_title"))
            self._append_log(f"  images_folder: {cfg.get('images_folder', 'default')}")
            self._set_running(True, "pbar_1")

            def task(log, progress):
                from app.core.ai_mapper import run_ai_mapper
                run_ai_mapper(cfg, log=log, progress=progress)

            self._start_task(task, pbar_key="pbar_1", step_idx=0)
        except Exception as e:
            logger.critical(f"_run_step3 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "pbar_1")

    def _run_step4(self):
        """Run Video Builder (pipeline step 2)."""
        try:
            errors = self._validate()
            if errors:
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return
            cfg = self._prepare_session_cfg(load_config())
            logger.info(f"Starting Video Builder | audio={cfg.get('audio_path')}")
            self._append_log("▶ " + t("step4_title"))
            self._append_log(f"  audio_path: {cfg.get('audio_path', 'default')}")
            self._set_running(True, "pbar_2")

            def task(log, progress):
                from app.core.video_builder import run_video_builder
                run_video_builder(cfg, log=log, progress=progress)

            self._start_task(task, pbar_key="pbar_2", step_idx=1)
        except Exception as e:
            logger.critical(f"_run_step4 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "pbar_2")

    def _run_all(self):
        """Run AI Mapper then Video Builder sequentially."""
        try:
            errors = self._validate()
            if errors:
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return
            cfg = self._prepare_session_cfg(load_config())
            logger.info("Starting full pipeline (Mapper + Builder)")
            self._append_log("⚡ " + t("run_all"))
            self._append_log(f"  images_folder: {cfg.get('images_folder', 'default')}")
            self._append_log(f"  audio_path: {cfg.get('audio_path', 'default')}")
            self._set_running(True, "pbar_1")

            def task(log, progress):
                from app.core.ai_mapper    import run_ai_mapper
                from app.core.video_builder import run_video_builder
                log("── AI Mapper ──")
                run_ai_mapper(cfg, log=log, progress=progress)
                log("── Video Builder ──")
                run_video_builder(cfg, log=log, progress=progress)

            self._start_task(task, pbar_key="pbar_1", step_idx=1, finish_key="pbar_2")
        except Exception as e:
            logger.critical(f"_run_all CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "pbar_1")

    # ─────────────────────────────────────────────────────────────────────────
    # Output folder
    # ─────────────────────────────────────────────────────────────────────────

    def _open_output(self):
        cfg    = load_config()
        folder = cfg.get("output_folder", str(Path(BASE_DIR) / "output"))
        path   = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # ─────────────────────────────────────────────────────────────────────────
    # refresh / retranslate
    # ─────────────────────────────────────────────────────────────────────────

    def refresh(self):
        pass

    def retranslate(self):
        for key, widget in self._translatable.items():
            if isinstance(widget, QPushButton):
                if key == "run_all":
                    widget.setText("  ⚡  " + t("run_all"))
                else:
                    widget.setText(t(key))
            elif isinstance(widget, QCheckBox):
                widget.setText(t(key))
            else:
                widget.setText(t(key))

        for refs in self._step_cards:
            step = refs["step_def"]
            refs["title_lbl"].setText(t(step["title_key"]))
            refs["desc_lbl"].setText(t(step["desc_key"]))
            refs["in_lbl"].setText(t(step["input_key"]))
            refs["out_lbl"].setText(t(step["output_key"]))
            if "run_btn" in refs:
                refs["run_btn"].setText("  ▶  " + t("run_step"))
