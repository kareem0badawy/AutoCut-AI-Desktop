# AutoCut — AI-Powered Video Generator

## Overview

AutoCut converts an audio script into a complete AI-generated video by:
1. Generating image prompts from a script using Groq (Llama 3.3 70B)
2. Generating images via HuggingFace (FLUX.1-schnell)
3. Mapping images to audio timestamps with AI
4. Assembling the final video with MoviePy

## Project Structure

```
AutoCut/
├── main.py                  # Entry point — runs full pipeline
├── prompt_generator.py      # Step 1: Generate prompts from script
├── image_generator.py       # Step 2: Generate images from prompts
├── ai_mapper.py             # Step 3: Map images to timestamps
├── video_builder.py         # Step 4: Build final video
├── check_names.py           # Helper: check image filenames
│
├── config.json              # API keys and video settings (user must create)
├── style_config.json        # Image style/mood configuration
├── mapping.json             # Output of ai_mapper (image-timestamp mapping)
├── requirements.txt         # Python dependencies
├── script.txt               # Your audio script (user must provide)
│
├── assets/
│   ├── audio/               # Input audio files (mp3/wav/m4a)
│   ├── images/              # Pre-made images (alternative to AI generation)
│   └── output/              # Final video output
│
└── output/
    ├── prompts.json         # Generated prompts
    ├── prompts_output.txt   # Text version of prompts
    └── images/              # AI-generated images
```

## Setup

### 1. Create `config.json` with your API keys:
```json
{
  "groq_api_key": "gsk_...",
  "hf_api_key": "hf_...",
  "gemini_api_key": "AIza...",
  "base_path": "/home/runner/workspace",
  "output_resolution": "1920x1080",
  "fps": 24,
  "seconds_per_image": 7,
  "audio_duration": "4.30",
  "scenes_per_batch": 10,
  "transition_duration": 0.5,
  "transition_type": "fade"
}
```

### 2. Place your audio file in `assets/audio/`
### 3. Place your script in `script.txt`

## Running

The workflow runs `python main.py` which executes all 4 steps in sequence.
You can also run individual steps:
```bash
python prompt_generator.py
python image_generator.py
python ai_mapper.py
python video_builder.py
```

## Dependencies

- **Python 3.12** (Replit module)
- **moviepy** — video assembly
- **Pillow** — image processing
- **pydub** — audio processing
- **groq** — Groq API client (Llama 3.3 70B)
- **huggingface_hub** — HuggingFace API (FLUX.1-schnell)
- **google-generativeai** — Gemini API (future use)
- **ffmpeg** — system dependency for audio/video processing

## Workflow

- **Start application** (console): `python main.py` — runs the full pipeline
