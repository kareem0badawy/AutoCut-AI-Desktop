import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QPlainTextEdit, QCheckBox,
    QSpinBox, QMessageBox,
)

from app.i18n import lang_manager, t
from app.gui.theme import get_colors
from app.gui.widgets import make_separator, make_badge
from app.core.config_manager import load_config, load_style, validate_config, BASE_DIR
from app.logger import logger


class _Worker(QObject):
    log      = Signal(str)
    progress = Signal(int, int)
    finished = Signal(bool, str)

    def __init__(self, task_fn):
        super().__init__()
        self._task_fn = task_fn

    def run(self):
        try:
            self._task_fn(
                log=lambda msg: self.log.emit(str(msg)),
                progress=lambda cur, total: self.progress.emit(cur, total),
            )
            self.finished.emit(True, "")
        except Exception as e:
            self.finished.emit(False, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


class PipelinePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._step_cards: list[dict] = []
        self._translatable: dict[str, QLabel | QPushButton] = {}
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 36, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(self._header_section())
        layout.addWidget(self._steps_section())
        layout.addWidget(self._export_section())
        layout.addWidget(self._log_section())
        layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _header_section(self) -> QWidget:
        C = get_colors()
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel(t("pipeline_title"))
        title.setObjectName("heading")
        sub = QLabel(t("pipeline_subtitle"))
        sub.setStyleSheet(f"color: {C['text_sec']}; font-size: 14px; background: transparent;")

        self._translatable["pipeline_title"] = title
        self._translatable["pipeline_subtitle"] = sub
        layout.addWidget(title)
        layout.addWidget(sub)
        return w

    def _steps_section(self) -> QWidget:
        C = get_colors()
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        step_defs = [
            {
                "num": "1",
                "title_key": "step1_title",
                "desc_key": "step1_desc",
                "input_key": "step1_input",
                "output_key": "step1_output",
                "run_fn": self._run_step1,
                "external": False,
                "color": C["accent"],
            },
            {
                "num": "2",
                "title_key": "step2_title",
                "desc_key": "step2_desc",
                "input_key": "step2_input",
                "output_key": "step2_output",
                "note_key": "step2_note",
                "run_fn": None,
                "external": True,
                "color": C["warning"],
            },
            {
                "num": "3",
                "title_key": "step3_title",
                "desc_key": "step3_desc",
                "input_key": "step3_input",
                "output_key": "step3_output",
                "run_fn": self._run_step3,
                "external": False,
                "color": "#8b5cf6",
            },
            {
                "num": "4",
                "title_key": "step4_title",
                "desc_key": "step4_desc",
                "input_key": "step4_input",
                "output_key": "step4_output",
                "run_fn": self._run_step4,
                "external": False,
                "color": C["success"],
            },
        ]

        self._step_cards = []
        for i, step in enumerate(step_defs):
            card_widget, card_refs = self._build_step_card(step, C)
            card_refs["step_def"] = step
            self._step_cards.append(card_refs)
            layout.addWidget(card_widget)

            if i < len(step_defs) - 1:
                arr = QLabel("↓")
                arr.setAlignment(Qt.AlignCenter)
                arr.setStyleSheet(f"color: {C['text_dim']}; font-size: 20px; background: transparent;")
                layout.addWidget(arr)

        layout.addSpacing(8)

        run_all_row = QHBoxLayout()
        self._run_all_btn = QPushButton("  ⚡  " + t("run_all"))
        self._run_all_btn.setObjectName("primary")
        self._run_all_btn.setFixedHeight(44)
        self._run_all_btn.clicked.connect(self._run_all)

        self._run_all_desc = QLabel(t("run_all_desc"))
        self._run_all_desc.setStyleSheet(f"color: {C['text_dim']}; font-size: 12px; background: transparent;")
        self._translatable["run_all"] = self._run_all_btn
        self._translatable["run_all_desc"] = self._run_all_desc

        run_all_row.addWidget(self._run_all_btn)
        run_all_row.addSpacing(12)
        run_all_row.addWidget(self._run_all_desc)
        run_all_row.addStretch()

        container.layout().addLayout(run_all_row)

        step1_card_refs = self._step_cards[0]
        opts = self._build_step1_options(C)
        self._step1_opts_widget = opts
        container.layout().insertWidget(1, opts)

        return container

    def _build_step_card(self, step: dict, C: dict) -> tuple[QWidget, dict]:
        card = QWidget()
        card.setObjectName("step_card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

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
        title_lbl.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {C['text']}; background: transparent;")
        desc_lbl = QLabel(t(step["desc_key"]))
        desc_lbl.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
        desc_lbl.setWordWrap(True)
        title_col.addWidget(title_lbl)
        title_col.addWidget(desc_lbl)

        top_row.addWidget(num)
        top_row.addLayout(title_col, 1)

        refs: dict = {
            "title_lbl": title_lbl,
            "desc_lbl": desc_lbl,
        }

        if step["external"]:
            ext_badge = make_badge("🔗 " + t("step2_note").split("—")[0].strip(), "warning", C)
            top_row.addWidget(ext_badge)
            refs["ext_badge"] = ext_badge
        else:
            run_btn = QPushButton("  ▶  " + t("run_step"))
            run_btn.setObjectName("primary")
            run_btn.setFixedHeight(34)
            run_btn.setFixedWidth(120)
            run_btn.clicked.connect(step["run_fn"])
            top_row.addWidget(run_btn)
            refs["run_btn"] = run_btn

        layout.addLayout(top_row)
        layout.addWidget(make_separator(C))

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
        layout.addLayout(io_row)

        refs["in_lbl"] = in_lbl
        refs["out_lbl"] = out_lbl

        if step.get("note_key"):
            note = QLabel(t(step["note_key"]))
            note.setStyleSheet(
                f"font-size: 11px; color: {C['warning']}; background: transparent; font-style: italic;"
            )
            note.setWordWrap(True)
            layout.addWidget(note)
            refs["note_lbl"] = note

        self._step_progress = getattr(self, "_step_progress", {})
        pbar = QProgressBar()
        pbar.setVisible(False)
        pbar.setFixedHeight(6)
        pbar.setValue(0)
        pbar.setRange(0, 100)
        layout.addWidget(pbar)
        key = f"pbar_{step['num']}"
        self._step_progress[key] = pbar
        refs["pbar"] = pbar

        status_lbl = QLabel("")
        status_lbl.setStyleSheet("background: transparent; font-size: 11px;")
        status_lbl.setVisible(False)
        layout.addWidget(status_lbl)
        refs["status_lbl"] = status_lbl

        return card, refs

    def _build_step1_options(self, C: dict) -> QWidget:
        grp = QWidget()
        grp.setObjectName("card_dark")
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        title = QLabel(t("step1_options"))
        title.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {C['text']}; background: transparent;")
        self._translatable["step1_options"] = title
        layout.addWidget(title)

        self._reset_check = QCheckBox(t("reset_option"))
        self._reset_check.setStyleSheet(f"color: {C['text_sec']}; background: transparent;")
        self._translatable["reset_option"] = self._reset_check
        layout.addWidget(self._reset_check)

        limit_row = QHBoxLayout()
        self._limit_check = QCheckBox(t("limit_option"))
        self._limit_check.setStyleSheet(f"color: {C['text_sec']}; background: transparent;")
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(1, 999)
        self._limit_spin.setValue(10)
        self._limit_spin.setFixedWidth(70)
        self._limit_spin.setEnabled(False)
        self._limit_check.toggled.connect(self._limit_spin.setEnabled)
        self._translatable["limit_option"] = self._limit_check
        limit_row.addWidget(self._limit_check)
        limit_row.addWidget(self._limit_spin)
        limit_row.addStretch()
        layout.addLayout(limit_row)

        note = QLabel(t("limit_note"))
        note.setStyleSheet(f"font-size: 11px; color: {C['text_dim']}; background: transparent;")
        self._translatable["limit_note"] = note
        layout.addWidget(note)

        return grp

    def _export_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(4)
        title = QLabel("🎬  " + t("export_video"))
        title.setStyleSheet(f"font-weight: 700; font-size: 16px; color: {C['text']}; background: transparent;")
        desc = QLabel(t("export_video_desc"))
        desc.setStyleSheet(f"font-size: 12px; color: {C['text_sec']}; background: transparent;")
        self._translatable["export_video"] = title
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
        layout.addLayout(row)

        return card

    def _log_section(self) -> QWidget:
        C = get_colors()
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        hdr = QHBoxLayout()
        title = QLabel(t("logs_title"))
        title.setObjectName("subheading")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {C['text']}; background: transparent;")
        clear_btn = QPushButton(t("clear_logs"))
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear_logs)
        self._translatable["logs_title"] = title
        self._translatable["clear_logs"] = clear_btn
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(clear_btn)
        layout.addLayout(hdr)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(200)
        self._log_view.setMaximumHeight(300)
        self._log_view.setStyleSheet(
            f"background: {C['surface2']}; color: {C['text_sec']}; "
            f"font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; "
            f"border-radius: 8px; padding: 8px; border: 1px solid {C['border']};"
        )
        layout.addWidget(self._log_view)
        return card

    def _append_log(self, msg: str):
        self._log_view.appendPlainText(msg)
        self._log_view.verticalScrollBar().setValue(
            self._log_view.verticalScrollBar().maximum()
        )

    def _clear_logs(self):
        self._log_view.clear()

    def _set_running(self, running: bool, step_num: str = None):
        try:
            self._run_all_btn.setEnabled(not running)
            for refs in self._step_cards:
                if "run_btn" in refs:
                    refs["run_btn"].setEnabled(not running)
            if step_num:
                key = f"pbar_{step_num}"
                pbar = self._step_progress.get(key)
                if pbar:
                    if running:
                        pbar.setVisible(True)
                        pbar.setRange(0, 0)
                    else:
                        pbar.setRange(0, 100)
                        pbar.setValue(100)
        except Exception as e:
            logger.error(f"_set_running error: {e}\n{traceback.format_exc()}")

    def _on_progress(self, cur: int, total: int, step_num: str = "1"):
        try:
            key = f"pbar_{step_num}"
            pbar = self._step_progress.get(key)
            if pbar and total > 0:
                pbar.setRange(0, 100)
                pbar.setValue(int(cur / total * 100))
        except Exception as e:
            logger.error(f"_on_progress error: {e}")

    def _on_finished(self, success: bool, err: str, step_num: str = "1", step_idx: int = 0):
        try:
            self._set_running(False, step_num)
            if 0 <= step_idx < len(self._step_cards):
                refs = self._step_cards[step_idx]
                status_lbl = refs.get("status_lbl")
            else:
                status_lbl = None
            C = get_colors()
            if success:
                msg = t("done_success")
                color = C["success"]
                logger.info(f"Step {step_num} finished successfully")
            else:
                msg = t("done_error")
                color = C["error"]
                self._append_log(err)
                logger.error(f"Step {step_num} failed:\n{err}")
            if status_lbl:
                status_lbl.setText(msg)
                status_lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600; background: transparent;")
                status_lbl.setVisible(True)
            self._append_log(msg)
        except Exception as e:
            logger.critical(f"_on_finished CRASH: {e}\n{traceback.format_exc()}")

    def _validate(self) -> list[str]:
        cfg = load_config()
        return validate_config(cfg)

    def _start_task(self, fn, step_num: str, step_idx: int,
                    finish_step_num: str = None):
        """
        Proper Qt threading pattern:
          - Worker lives in a QThread; signals are queued across threads.
          - After finished: thread.quit() → deleteLater() on both objects.
          - This prevents the segfault/crash that happens when the C++ QThread
            object is garbage-collected while PySide6 still holds signal connections.

        step_num       : which progress-bar to animate while running
        finish_step_num: which step to mark done in _on_finished (defaults to step_num)
        step_idx       : which step card's status label to update on finish
        """
        fsn = finish_step_num if finish_step_num is not None else step_num

        worker = _Worker(fn)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.log.connect(self._append_log)
        worker.progress.connect(
            lambda c, total, sn=step_num: self._on_progress(c, total, sn)
        )
        worker.finished.connect(
            lambda ok, err, sn=fsn, si=step_idx: self._on_finished(ok, err, sn, si)
        )
        worker.finished.connect(lambda: thread.quit())
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_thread_refs)

        self._thread = thread
        self._worker = worker
        thread.start()

    def _clear_thread_refs(self):
        self._thread = None
        self._worker = None

    def _run_step1(self):
        try:
            errors = self._validate()
            if errors:
                logger.warning(f"Step 1 validation failed: {errors}")
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return

            cfg = load_config()
            style = load_style()
            reset = self._reset_check.isChecked()
            limit = self._limit_spin.value() if self._limit_check.isChecked() else None

            logger.info(f"Starting Step 1 — reset={reset}, limit={limit}")
            self._append_log("▶ " + t("step1_title"))
            self._set_running(True, "1")

            def task(log, progress):
                from app.core.prompt_generator import run_prompt_generation
                run_prompt_generation(cfg, style, reset=reset, limit=limit, log=log, progress=progress)

            self._start_task(task, step_num="1", step_idx=0)
        except Exception as e:
            logger.critical(f"_run_step1 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "1")

    def _run_step3(self):
        try:
            errors = self._validate()
            if errors:
                logger.warning(f"Step 3 validation failed: {errors}")
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return

            cfg = load_config()
            logger.info("Starting Step 3 — AI Mapper")
            self._append_log("▶ " + t("step3_title"))
            self._set_running(True, "3")

            def task(log, progress):
                from app.core.ai_mapper import run_ai_mapper
                run_ai_mapper(cfg, log=log, progress=progress)

            self._start_task(task, step_num="3", step_idx=2)
        except Exception as e:
            logger.critical(f"_run_step3 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "3")

    def _run_step4(self):
        try:
            errors = self._validate()
            if errors:
                logger.warning(f"Step 4 validation failed: {errors}")
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return

            cfg = load_config()
            logger.info("Starting Step 4 — Video Builder")
            self._append_log("▶ " + t("step4_title"))
            self._set_running(True, "4")

            def task(log, progress):
                from app.core.video_builder import run_video_builder
                run_video_builder(cfg, log=log, progress=progress)

            self._start_task(task, step_num="4", step_idx=3)
        except Exception as e:
            logger.critical(f"_run_step4 CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "4")

    def _run_all(self):
        try:
            errors = self._validate()
            if errors:
                logger.warning(f"Run-all validation failed: {errors}")
                QMessageBox.warning(self, t("config_errors"), "\n".join(errors))
                return

            cfg = load_config()
            style = load_style()
            reset = self._reset_check.isChecked()
            limit = self._limit_spin.value() if self._limit_check.isChecked() else None

            logger.info(f"Starting full pipeline — reset={reset}, limit={limit}")
            self._append_log("⚡ " + t("run_all"))
            self._set_running(True, "1")

            def task(log, progress):
                from app.core.prompt_generator import run_prompt_generation
                from app.core.ai_mapper import run_ai_mapper
                from app.core.video_builder import run_video_builder
                log("── Step 1 ──")
                run_prompt_generation(cfg, style, reset=reset, limit=limit, log=log, progress=progress)
                log("── Step 3 ──")
                run_ai_mapper(cfg, log=log, progress=progress)
                log("── Step 4 ──")
                run_video_builder(cfg, log=log, progress=progress)

            self._start_task(task, step_num="1", step_idx=3, finish_step_num="4")
        except Exception as e:
            logger.critical(f"_run_all CRASH: {e}\n{traceback.format_exc()}")
            self._set_running(False, "1")

    def _open_output(self):
        cfg = load_config()
        folder = cfg.get("output_folder", str(Path(BASE_DIR) / "output"))
        path = Path(folder)
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    def refresh(self):
        pass

    def retranslate(self):
        C = get_colors()
        for key, widget in self._translatable.items():
            if isinstance(widget, QPushButton):
                if key == "run_all":
                    widget.setText("  ⚡  " + t("run_all"))
                elif key == "open_output_folder":
                    widget.setText(t(key))
                else:
                    widget.setText(t(key))
            elif isinstance(widget, QCheckBox):
                widget.setText(t(key))
            else:
                widget.setText(t(key))

        for i, refs in enumerate(self._step_cards):
            step = refs["step_def"]
            refs["title_lbl"].setText(t(step["title_key"]))
            refs["desc_lbl"].setText(t(step["desc_key"]))
            refs["in_lbl"].setText(t(step["input_key"]))
            refs["out_lbl"].setText(t(step["output_key"]))
            if "note_lbl" in refs:
                refs["note_lbl"].setText(t(step["note_key"]))
            if "run_btn" in refs:
                refs["run_btn"].setText("  ▶  " + t("run_step"))
