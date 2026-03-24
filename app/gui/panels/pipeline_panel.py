import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QProgressBar, QPlainTextEdit, QCheckBox,
    QGroupBox, QSpinBox, QMessageBox,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_config, load_style, validate_config, BASE_DIR


class _Worker(QObject):
    log = Signal(str)
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


class _RunThread(QThread):
    def __init__(self, worker):
        super().__init__()
        self._worker = worker
        self._worker.moveToThread(self)

    def run(self):
        self._worker.run()


class PipelinePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(40, 30, 40, 20)
        top_layout.setSpacing(16)

        title = QLabel("Pipeline Runner")
        title.setObjectName("heading")
        top_layout.addWidget(title)

        desc = QLabel("Run each step individually or run the full pipeline. Logs appear in real time.")
        desc.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
        top_layout.addWidget(desc)

        top_layout.addWidget(self._steps_card())
        top_layout.addWidget(self._options_card())

        layout.addWidget(top)

        logs_container = QWidget()
        logs_container.setObjectName("card_dark")
        logs_layout = QVBoxLayout(logs_container)
        logs_layout.setContentsMargins(20, 16, 20, 16)
        logs_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_label = QLabel("Logs")
        log_label.setObjectName("subheading")
        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("secondary")
        clear_btn.setFixedWidth(70)
        clear_btn.clicked.connect(self._clear_logs)
        log_header.addWidget(log_label)
        log_header.addStretch()
        log_header.addWidget(clear_btn)
        logs_layout.addLayout(log_header)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setTextVisible(False)
        logs_layout.addWidget(self._progress_bar)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMinimumHeight(300)
        self._log_view.setStyleSheet(
            f"background: #0a0a0a; color: {COLORS['success']}; font-family: monospace; font-size: 12px;"
        )
        logs_layout.addWidget(self._log_view)

        layout.addWidget(logs_container, 1)

    def _steps_card(self):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title = QLabel("Pipeline Steps")
        title.setObjectName("subheading")
        layout.addWidget(title)

        self._step_buttons = []

        steps = [
            ("Step 1 — Prompt Generator", "Generate image prompts from script using Groq AI", self._run_step1),
            ("Step 2 — Image Generator", "Generate images via HuggingFace (see instructions below)", self._run_step2),
            ("Step 3 — AI Mapper", "Map generated images to timestamps", self._run_step3),
            ("Step 4 — Video Builder", "Assemble final video from images + audio", self._run_step4),
        ]

        for i, (label, desc, fn) in enumerate(steps):
            row = QHBoxLayout()
            row.setSpacing(12)

            info = QVBoxLayout()
            info.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold;")
            d = QLabel(desc)
            d.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 11px;")
            info.addWidget(lbl)
            info.addWidget(d)

            btn = QPushButton("Run")
            btn.setObjectName("primary")
            btn.setFixedWidth(90)
            btn.clicked.connect(fn)
            self._step_buttons.append(btn)

            row.addLayout(info)
            row.addStretch()
            row.addWidget(btn)
            layout.addLayout(row)

            if i < len(steps) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"color: {COLORS['border']};")
                layout.addWidget(sep)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet(f"color: {COLORS['accent']}44;")
        layout.addWidget(sep2)

        full_row = QHBoxLayout()
        full_info = QVBoxLayout()
        full_info.setSpacing(2)
        fl = QLabel("Full Pipeline")
        fl.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 14px;")
        fd = QLabel("Run all steps sequentially (Step 1 → 3 → 4, skipping Step 2)")
        fd.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 11px;")
        full_info.addWidget(fl)
        full_info.addWidget(fd)

        self._full_btn = QPushButton("Run Full Pipeline")
        self._full_btn.setObjectName("success")
        self._full_btn.setFixedWidth(160)
        self._full_btn.clicked.connect(self._run_full)

        full_row.addLayout(full_info)
        full_row.addStretch()
        full_row.addWidget(self._full_btn)
        layout.addLayout(full_row)

        return card

    def _options_card(self):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        title = QLabel("Step 1 Options")
        title.setObjectName("subheading")
        layout.addWidget(title)

        row1 = QHBoxLayout()
        self._reset_check = QCheckBox("Reset (clear previous prompts and start fresh)")
        self._reset_check.setStyleSheet(f"color: {COLORS['text']};")
        row1.addWidget(self._reset_check)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        limit_check = QCheckBox("Limit scenes:")
        limit_check.setStyleSheet(f"color: {COLORS['text']};")
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(1, 500)
        self._limit_spin.setValue(5)
        self._limit_spin.setFixedWidth(80)
        self._limit_spin.setEnabled(False)
        limit_check.toggled.connect(self._limit_spin.setEnabled)
        self._limit_enabled = limit_check
        row2.addWidget(limit_check)
        row2.addWidget(self._limit_spin)
        row2.addWidget(QLabel("scenes only (useful for testing)"))
        row2.addStretch()
        layout.addLayout(row2)

        note = QLabel(
            "Note: Step 2 (Image Generation) must be done externally using the generated prompts. "
            "See Outputs Viewer → prompts_output.txt for the prompts to use with HuggingFace or any AI image tool."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {COLORS['warning']}; font-size: 11px;")
        layout.addWidget(note)

        return card

    def _log(self, msg):
        self._log_view.appendPlainText(str(msg))
        self._log_view.ensureCursorVisible()

    def _clear_logs(self):
        self._log_view.clear()

    def _update_progress(self, current, total):
        if total > 0:
            self._progress_bar.setMaximum(total)
            self._progress_bar.setValue(current)

    def _set_running(self, running):
        for btn in self._step_buttons:
            btn.setEnabled(not running)
        self._full_btn.setEnabled(not running)
        self._progress_bar.setVisible(running)
        if not running:
            self._progress_bar.setValue(0)

    def _validate(self, require_audio=False, require_images=False, require_mapping=False, require_prompts=False):
        config = load_config()
        errors = []

        if not config.get("groq_api_key") and require_prompts is not False:
            errors.append("Groq API key is missing (go to Project Settings)")

        if require_audio:
            audio = config.get("audio_path", "")
            if not audio or not Path(audio).exists():
                errors.append("Audio file not found (set it in Project Settings)")

        if require_prompts:
            base = Path(config.get("base_path", "."))
            if not (base / "output" / "prompts.json").exists():
                errors.append("prompts.json not found — run Step 1 first")

        if require_images:
            imgs_folder = config.get("images_folder", "")
            base = Path(config.get("base_path", "."))
            has_images = (
                (imgs_folder and Path(imgs_folder).exists() and any(
                    f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
                    for f in Path(imgs_folder).iterdir() if f.is_file()
                )) or
                any(
                    (base / "output" / "images").exists(),
                    (base / "assets" / "images").exists(),
                )
            )

        if require_mapping:
            base = Path(config.get("base_path", "."))
            if not (base / "mapping.json").exists():
                errors.append("mapping.json not found — run Step 3 first")

        script = config.get("script_path", "")
        if not script or not Path(script).exists():
            errors.append("Script file not found (set it in Project Settings)")

        return errors, config

    def _run_task(self, task_fn):
        if self._thread and self._thread.isRunning():
            return

        self._set_running(True)
        self._worker = _Worker(task_fn)
        self._thread = _RunThread(self._worker)
        self._worker.log.connect(self._log)
        self._worker.progress.connect(self._update_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, success, error_msg):
        self._set_running(False)
        if success:
            self._log("\n✓ Step completed successfully!")
        else:
            self._log(f"\n✗ Error:\n{error_msg}")

    def _run_step1(self):
        errors, config = self._validate()
        if errors:
            QMessageBox.critical(self, "Configuration Error", "\n".join(errors))
            return

        self._log("=== Step 1: Prompt Generator ===")

        limit = self._limit_spin.value() if self._limit_enabled.isChecked() else None
        reset = self._reset_check.isChecked()

        def task(log, progress):
            from app.core.prompt_generator import generate_prompts
            style = load_style()
            tmpl_path = BASE_DIR / "prompts_template.txt"
            template = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""
            generate_prompts(config, style, template, limit=limit, reset=reset, log=log, progress=progress)

        self._run_task(task)

    def _run_step2(self):
        self._log(
            "=== Step 2: Image Generation ===\n"
            "Image generation uses HuggingFace FLUX.1-schnell and must be done externally.\n\n"
            "Instructions:\n"
            "1. Go to Outputs Viewer → prompts_output.txt to see all generated prompts.\n"
            "2. Use each prompt with HuggingFace Inference API or any AI image generator.\n"
            "3. Name images as: scene_001.png, scene_002.png, etc.\n"
            "4. Place images in your configured 'AI-Generated Images Folder' (Project Settings).\n"
            "5. Then run Step 3 (AI Mapper) to continue.\n\n"
            "API Code Example (Python):\n"
            '  from huggingface_hub import InferenceClient\n'
            '  client = InferenceClient(token="your_hf_token")\n'
            '  image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")\n'
            '  image.save("output/images/scene_001.png")\n'
        )

    def _run_step3(self):
        self._log("=== Step 3: AI Mapper ===")
        _, config = self._validate()

        def task(log, progress):
            from app.core.ai_mapper import run_ai_mapper
            run_ai_mapper(config, log=log, progress=progress)

        self._run_task(task)

    def _run_step4(self):
        self._log("=== Step 4: Video Builder ===")
        _, config = self._validate(require_audio=True)

        def task(log, progress):
            from app.core.video_builder import build_video
            build_video(config, log=log, progress=progress)

        self._run_task(task)

    def _run_full(self):
        self._log("=== Running Full Pipeline (Step 1 → 3 → 4) ===")
        _, config = self._validate(require_audio=True)
        limit = self._limit_spin.value() if self._limit_enabled.isChecked() else None
        reset = self._reset_check.isChecked()

        def task(log, progress):
            from app.core.prompt_generator import generate_prompts
            from app.core.ai_mapper import run_ai_mapper
            from app.core.video_builder import build_video

            style = load_style()
            tmpl_path = BASE_DIR / "prompts_template.txt"
            template = tmpl_path.read_text(encoding="utf-8") if tmpl_path.exists() else ""

            log("\n--- Step 1: Generating prompts ---")
            generate_prompts(config, style, template, limit=limit, reset=reset, log=log, progress=progress)
            log("\n--- Step 3: Mapping images ---")
            run_ai_mapper(config, log=log, progress=progress)
            log("\n--- Step 4: Building video ---")
            build_video(config, log=log, progress=progress)

        self._run_task(task)

    def refresh(self):
        pass
