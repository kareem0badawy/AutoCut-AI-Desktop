from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QFrame,
)

from app.gui.theme import COLORS
from app.core.config_manager import load_config


class DashboardPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)

        title = QLabel("AutoCut")
        title.setObjectName("heading")
        sub = QLabel("AI-Powered Video Generator")
        sub.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 14px;")

        layout.addWidget(title)
        layout.addWidget(sub)
        layout.addSpacing(10)

        layout.addWidget(self._pipeline_card())
        layout.addWidget(self._status_card())
        layout.addWidget(self._how_to_use_card())
        layout.addStretch()

        scroll.setWidget(container)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _pipeline_card(self):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("Pipeline Overview")
        title.setObjectName("subheading")
        layout.addWidget(title)

        steps = [
            ("1", "Prompt Generator", "Converts your script into detailed AI image prompts using Groq LLM", COLORS['accent']),
            ("2", "Image Generator", "Generates images from prompts via HuggingFace FLUX.1-schnell", "#ab47bc"),
            ("3", "AI Mapper", "Maps generated images to correct timestamps in the script", COLORS['warning']),
            ("4", "Video Builder", "Assembles images + audio into the final video with transitions", COLORS['success']),
        ]

        for num, name, desc, color in steps:
            row = QHBoxLayout()
            row.setSpacing(14)

            badge = QLabel(num)
            badge.setFixedSize(32, 32)
            badge.setAlignment(Qt.AlignCenter)
            badge.setStyleSheet(
                f"background-color: {color}22; color: {color}; border: 1px solid {color}55;"
                f"border-radius: 16px; font-weight: bold; font-size: 13px;"
            )

            info = QVBoxLayout()
            info.setSpacing(2)
            n = QLabel(name)
            n.setStyleSheet(f"color: {COLORS['text']}; font-weight: bold; font-size: 13px;")
            d = QLabel(desc)
            d.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px;")
            info.addWidget(n)
            info.addWidget(d)

            row.addWidget(badge, 0, Qt.AlignTop)
            row.addLayout(info)
            layout.addLayout(row)

        return card

    def _status_card(self):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Project Status")
        title.setObjectName("subheading")
        layout.addWidget(title)

        config = load_config()
        base = Path(config.get("base_path", "."))

        checks = [
            ("config.json", (base / "config.json").exists()),
            ("style_config.json", (base / "style_config.json").exists()),
            ("script.txt", Path(config.get("script_path", "")).exists()),
            ("Audio file", Path(config.get("audio_path", "")).exists()),
            ("prompts.json", (base / "output" / "prompts.json").exists()),
            ("Images folder", Path(config.get("images_folder", "")).exists()),
            ("mapping.json", (base / "mapping.json").exists()),
            ("final_video.mp4", (Path(config.get("output_folder", base / "assets" / "output")) / "final_video.mp4").exists()),
        ]

        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(8)

        col1 = QVBoxLayout()
        col2 = QVBoxLayout()
        col1.setSpacing(6)
        col2.setSpacing(6)

        for i, (name, status) in enumerate(checks):
            icon = "✓" if status else "○"
            color = COLORS['success'] if status else COLORS['text_dim']
            label = QLabel(f"{icon}  {name}")
            label.setStyleSheet(f"color: {color}; font-size: 12px;")
            if i % 2 == 0:
                col1.addWidget(label)
            else:
                col2.addWidget(label)

        grid_layout.addLayout(col1)
        grid_layout.addLayout(col2)
        grid_layout.addStretch()
        layout.addWidget(grid)

        return card

    def _how_to_use_card(self):
        card = QWidget()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel("How to Use AutoCut")
        title.setObjectName("subheading")
        layout.addWidget(title)

        steps = [
            ("Step 1 — Configure Settings",
             "Go to Project Settings → enter your Groq and HuggingFace API keys, set your video resolution, FPS, and timing. "
             "Select your script file and audio file."),
            ("Step 2 — Set Visual Style",
             "Go to Style Settings → customize the image style, mood, and negative prompts. "
             "The prompts template controls how the AI generates image descriptions."),
            ("Step 3 — Generate Prompts",
             "Go to Pipeline Runner → click Run Step 1. The app will read your script and use "
             "Groq AI to generate detailed image prompts for each scene."),
            ("Step 4 — Generate Images (External)",
             "Use the generated prompts from output/prompts_output.txt to generate images with "
             "HuggingFace or any AI image tool. Place the images in the configured images folder."),
            ("Step 5 — Map & Build",
             "Click Run Step 3 to map your images to timestamps, then Run Step 4 to build "
             "the final video. You can also use Run Full Pipeline to run all steps at once."),
            ("Step 6 — View Output",
             "Go to Outputs Viewer to preview prompts, mapping, and the final video path."),
        ]

        for i, (title_text, desc) in enumerate(steps, 1):
            row = QVBoxLayout()
            row.setSpacing(2)
            t = QLabel(title_text)
            t.setStyleSheet(f"color: {COLORS['accent']}; font-weight: bold; font-size: 12px;")
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet(f"color: {COLORS['text_sec']}; font-size: 12px; padding-left: 8px;")
            row.addWidget(t)
            row.addWidget(d)
            layout.addLayout(row)
            if i < len(steps):
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet(f"color: {COLORS['border']};")
                layout.addWidget(sep)

        return card

    def refresh(self):
        pass
