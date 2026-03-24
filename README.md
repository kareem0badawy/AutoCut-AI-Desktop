# AutoCut — AI-Powered Video Generator

AutoCut is a desktop application that converts audio scripts into complete AI-generated videos.
It provides a modern dark-themed GUI to manage every step of the pipeline.

---

## How to Run

```bash
bash start.sh
```

Or directly:
```bash
python main.py
```

---

## Pipeline

```
script.txt
    ↓
[1] Prompt Generator    →  output/prompts.json + output/prompts_output.txt
    ↓
[2] Image Generation    →  (external — use HuggingFace or any AI image tool)
    ↓
[3] AI Mapper           →  mapping.json
    ↓
[4] Video Builder       →  {output_folder}/final_video.mp4
```

---

## Project Structure

```
AutoCut/
│
├── main.py                      # App entry point (launches GUI)
├── start.sh                     # Shell wrapper (sets library paths)
├── requirements.txt             # Python dependencies
│
├── app/                         # Main application package
│   ├── core/                    # Backend logic (no UI dependencies)
│   │   ├── config_manager.py    # Reads/writes config.json & style_config.json
│   │   ├── prompt_generator.py  # Step 1: Groq LLM prompt generation
│   │   ├── ai_mapper.py         # Step 3: Image-to-timestamp mapping
│   │   └── video_builder.py     # Step 4: Final video assembly
│   └── gui/                     # PySide6 desktop UI
│       ├── main_window.py       # Main application window & navigation
│       ├── theme.py             # Dark theme stylesheet
│       └── panels/
│           ├── dashboard.py     # Overview & status
│           ├── settings_panel.py # API keys, paths, video config
│           ├── style_panel.py   # Visual style & prompts template
│           ├── pipeline_panel.py # Step runner with live logs
│           ├── assets_panel.py  # Script, audio, images viewer
│           └── outputs_panel.py # Prompts, mapping, video viewer
│
├── config.json                  # Project config (auto-created on first run)
├── style_config.json            # Image style config (auto-created on first run)
├── prompts_template.txt         # AI prompts template
├── mapping.json                 # Image-timestamp mapping (generated)
│
├── assets/
│   ├── audio/                   # Input audio files (mp3/wav/m4a)
│   ├── images/                  # Pre-made images (optional)
│   └── output/                  # Final video output
│
├── output/
│   ├── prompts.json             # Generated scene prompts
│   ├── prompts_output.txt       # Human-readable prompts
│   └── images/                  # AI-generated images
│
└── _archive/                    # Archived/deprecated files
    ├── image_generator.py       # (was duplicate of ai_mapper.py)
    ├── check_names.py           # (absorbed into Assets Manager panel)
    └── README.md                # Archive notes
```

---

## First-Time Setup

### 1. Open the App

Run `bash start.sh`. The GUI will open showing the Dashboard.

### 2. Configure API Keys (Project Settings)

- **Groq API Key** — get it free at [console.groq.com](https://console.groq.com)
- **HuggingFace API Key** — get it at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
- Set your **script file** path (the text script for your video)
- Set your **audio file** path (mp3/wav/m4a)
- Configure **video resolution**, **FPS**, and **timing**

### 3. Configure Style (Style Settings)

- Edit the **Style Lock** — visual identity applied to every image
- Set the **mood** and **negative prompts**
- Optionally edit the **Prompts Template** used by the AI

### 4. Run the Pipeline (Pipeline Runner)

Click each step in order:

| Step | Action |
|------|--------|
| **Step 1** | Generates image descriptions from your script |
| **Step 2** | (External) Generate images with HuggingFace FLUX.1-schnell |
| **Step 3** | Maps generated images to video timestamps |
| **Step 4** | Builds the final video |

Or click **Run Full Pipeline** to run steps 1 → 3 → 4 automatically.

---

## config.json Fields

| Field | Description | Example |
|-------|-------------|---------|
| `groq_api_key` | Groq API key (LLM) | `gsk_...` |
| `hf_api_key` | HuggingFace token | `hf_...` |
| `gemini_api_key` | Gemini key (optional) | `AIza...` |
| `script_path` | Path to your script file | `/path/to/script.txt` |
| `audio_path` | Path to your audio file | `/path/to/audio.mp3` |
| `images_folder` | AI-generated images folder | `/path/to/images/` |
| `output_folder` | Where the video is saved | `/path/to/output/` |
| `output_resolution` | Video resolution | `1920x1080` |
| `fps` | Frames per second | `24` |
| `seconds_per_image` | Duration per image | `7` |
| `audio_duration` | Audio length (min.sec) | `4.30` |
| `scenes_per_batch` | Scenes per LLM batch | `10` |
| `transition_duration` | Fade duration (seconds) | `0.5` |

All fields are editable live in the **Project Settings** panel.

---

## Dependencies

```
PySide6          — Desktop GUI framework
moviepy          — Video assembly
Pillow           — Image processing
pydub            — Audio processing
groq             — Groq API (Llama 3.3 70B)
huggingface_hub  — HuggingFace API
google-generativeai — Gemini (optional, future)
numpy            — Array processing
```

---

## PyInstaller Packaging (exe)

The project is structured for easy packaging:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name AutoCut main.py
```

For full packaging with all assets:
```bash
pyinstaller --onefile --windowed \
  --add-data "prompts_template.txt:." \
  --add-data "style_config.json:." \
  --name AutoCut main.py
```

The modular `app/` structure ensures clean imports and no circular dependencies.

---

## Models Used

| Model | Provider | Use |
|-------|----------|-----|
| `llama-3.3-70b-versatile` | Groq | Prompt generation & scene mapping |
| `FLUX.1-schnell` | Black Forest Labs / HuggingFace | Image generation (external) |
