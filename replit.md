# AutoCut — مولّد الفيديو بالذكاء الاصطناعي

## Architecture

Desktop GUI application built with PySide6 (Qt6). Converts audio scripts into
complete AI-generated videos via a 4-step pipeline.

### Tech Stack
- **GUI**: PySide6 (Qt6) with full i18n (Arabic default / English), dark + light mode
- **Styling**: Tailwind-inspired design (rounded cards, clean hierarchy, color system)
- **LLM**: Groq (Llama 3.3 70B) for prompt generation
- **Image Generation**: HuggingFace FLUX.1-schnell (external step)
- **Video**: MoviePy + FFmpeg for final assembly
- **Config**: Dynamic config.json + style_config.json

## Project Structure

```
AutoCut/
├── main.py                 # Entry point — cross-platform (Windows: direct, Linux: xcb preload)
├── start.sh                # Linux/Replit launcher (sets LD_PRELOAD for xcb-cursor)
├── start.bat               # Windows launcher (double-click to run)
├── requirements.txt
├── app/
│   ├── i18n.py             # Full Arabic/English translation system + LangManager (signals)
│   ├── core/
│   │   ├── config_manager.py   # Config read/write + defaults + validation
│   │   ├── prompt_generator.py # Step 1: Groq-based prompt generation
│   │   ├── ai_mapper.py        # Step 3: Image-timestamp mapping
│   │   └── video_builder.py    # Step 4: MoviePy video assembly
│   └── gui/
│       ├── main_window.py      # Main window + sidebar + lang/theme toggle buttons
│       ├── theme.py            # Dark + Light themes (Tailwind-inspired color system)
│       ├── widgets.py          # DropZone (drag&drop), make_badge, make_separator
│       └── panels/
│           ├── dashboard.py    # Upload zone (all 4 files), status, how-to guide
│           ├── settings_panel.py # API keys, file paths, video settings
│           ├── style_panel.py  # Style lock, negative prompt, template editor
│           ├── pipeline_panel.py # Visual step cards (1→2→3→4) with run buttons
│           └── outputs_panel.py  # Tabs: prompts / mapping table / video export
```

## Key Features

- **Arabic-first UI**: Default Arabic with RTL layout (setLayoutDirection), toggle to English
- **Dark + Light mode**: Toggle button in sidebar. Darker dark mode (Tailwind slate-950)
- **Drag & Drop uploads**: DropZone widget with dashed border, hover highlight, fill state
- **All files in one place**: Dashboard has 4 large drop zones (script, audio, images, output)
- **Clear pipeline**: Numbered step cards (1→4) with input/output labels and run buttons
- **Export button**: Prominent gradient button to open output folder after Step 4

## Running the App

### Windows
```
python main.py
```
Or double-click `start.bat`

### Linux / Replit
```
bash start.sh
```
(Sets LD_PRELOAD for xcb-cursor Qt plugin)

## Pipeline Steps

1. **Prompt Generator** — Reads script → generates scene descriptions via Groq AI
2. **Image Generation** — External step: use HuggingFace/Midjourney with the prompts
3. **AI Mapper** — Maps each image to the correct video timestamp
4. **Video Builder** — Combines images + audio into final_video.mp4

## i18n System

`app/i18n.py` exports:
- `lang_manager` — QObject with `language_changed` and `theme_changed` signals
- `t(key)` — Returns translated string for current language
- `lang_manager.set_lang("ar"|"en")` — Triggers signal → all panels call `retranslate()`
- `lang_manager.set_theme("dark"|"light")` — Triggers signal → rebuild stylesheet
