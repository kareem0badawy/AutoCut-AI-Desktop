# AutoCut — AI-Powered Video Generator

## Architecture

Desktop GUI application built with PySide6 (Qt6). Converts audio scripts into
complete AI-generated videos via a 4-step pipeline.

### Tech Stack
- **GUI**: PySide6 (Qt6) with dark theme QSS stylesheet
- **LLM**: Groq (Llama 3.3 70B) for prompt generation
- **Image Generation**: HuggingFace FLUX.1-schnell (external step)
- **Video**: MoviePy + FFmpeg for final assembly
- **Config**: Dynamic config.json + style_config.json

## Project Structure

```
AutoCut/
├── main.py                 # Entry point with ctypes xcb-cursor preload
├── start.sh                # Shell wrapper (sets LD_LIBRARY_PATH)
├── requirements.txt
├── app/
│   ├── core/
│   │   ├── config_manager.py   # Config read/write + defaults
│   │   ├── prompt_generator.py # Step 1: Groq-based prompt generation
│   │   ├── ai_mapper.py        # Step 3: Image-timestamp mapping
│   │   └── video_builder.py    # Step 4: MoviePy video assembly
│   └── gui/
│       ├── main_window.py      # Main window + sidebar navigation
│       ├── theme.py            # Dark theme (COLORS dict + QSS)
│       └── panels/
│           ├── dashboard.py        # Status overview + how-to guide
│           ├── settings_panel.py   # Project config editor
│           ├── style_panel.py      # Style + prompts template editor
│           ├── pipeline_panel.py   # Step runner with QThread workers
│           ├── assets_panel.py     # File browser for script/audio/images
│           └── outputs_panel.py    # View prompts, mapping, video
├── config.json             # Auto-created, all settings dynamic
├── style_config.json       # Auto-created, image style settings
├── prompts_template.txt    # AI prompt engineering template
└── _archive/               # Archived old files (documented)
```

## Workflow

- **Start application** (VNC): `bash start.sh` → runs `python main.py`
- The app preloads xcb-cursor from Nix store path for Qt xcb platform plugin

## Important Notes

- `main.py` uses `ctypes.CDLL` to preload libxcb-cursor.so.0 before Qt loads
  (required for Qt6.5+ xcb plugin on NixOS)
- `start.sh` additionally sets LD_LIBRARY_PATH and LD_PRELOAD
- All pipeline steps run in `QThread` workers to keep UI responsive
- Config is fully dynamic — all settings editable from UI, saved to JSON

## Archived Files

- `_archive/image_generator.py` — Was a duplicate of ai_mapper.py
- `_archive/check_names.py` — Debug utility absorbed into Assets Manager panel
