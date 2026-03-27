import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

DEFAULT_CONFIG = {
    "groq_api_key": "",
    "hf_api_key": "",
    "gemini_api_key": "",
    "base_path": str(BASE_DIR),
    "script_path": str(BASE_DIR / "script.txt"),
    "audio_path": "",
    "images_folder": str(BASE_DIR / "output" / "images"),
    "output_folder": str(BASE_DIR / "assets" / "output"),
    "output_resolution": "1920x1080",
    "fps": 24,
    "seconds_per_image": 7,
    "audio_duration": "4.30",
    "scenes_per_batch": 10,
    "transition_duration": 0.5,
    "transition_type": "fade"
}

DEFAULT_STYLE = {
    "style_lock": "cinematic documentary illustration, rich colors, dramatic lighting, detailed composition, high quality, professional look",
    "negative_prompt": "black and white, monochrome, pure black background, white background, watermark, text overlay, CGI, anime, flat design, oversaturated, blurry",
    "label_style": "bold clean text",
    "aspect_ratio": "16:9",
    "mood": "dramatic, cinematic, documentary",
    "template": """You are an AI video director. I will give you a script chunk and you must generate EXACTLY {scenes_in_batch} scene descriptions for a video.

SCRIPT CHUNK (Batch {batch_num}/{total_batches}):
{script_chunk}

VISUAL STYLE: {style_lock}
MOOD: {mood}
NEGATIVE PROMPT (avoid these): {negative_prompt}
SECONDS PER IMAGE: {seconds_per_image}

PREVIOUS SCENES (for continuity):
{previous_scenes}

IMPORTANT RULES:
1. Generate EXACTLY {scenes_in_batch} scenes as a JSON array.
2. The script may be in Arabic or any language — read and understand it fully.
3. "main_prompt" MUST be in English (for image generation AI tools).
4. "label_text" should reflect the key idea from the script in its original language.
5. "scene_description" is a brief English summary of what the scene shows visually.
6. Make each scene visually distinct and cinematically interesting.
7. Return ONLY the JSON array, no explanation text.

Return ONLY this JSON format:
[
  {{
    "scene_number": 1,
    "scene_description": "Brief English description of what this scene shows",
    "main_prompt": "Detailed English image generation prompt with style and mood",
    "label_text": "Short key phrase from the script (in script's language)",
    "secondary_labels": ["tag1", "tag2"],
    "negative_prompt": "{negative_prompt}"
  }}
]"""
}


def get_config_path():
    return BASE_DIR / "config.json"


def get_style_path():
    return BASE_DIR / "style_config.json"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    for key, val in DEFAULT_CONFIG.items():
        data.setdefault(key, val)
    if not data.get("base_path"):
        data["base_path"] = str(BASE_DIR)
    return data


def save_config(config: dict):
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_style() -> dict:
    path = get_style_path()
    if not path.exists():
        save_style(DEFAULT_STYLE)
        return DEFAULT_STYLE.copy()
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    for key, val in DEFAULT_STYLE.items():
        data.setdefault(key, val)
    return data


def save_style(style: dict):
    path = get_style_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2, ensure_ascii=False)


def parse_duration(duration_str: str) -> int:
    parts = str(duration_str).strip().split(".")
    minutes = int(parts[0]) if parts and parts[0] else 0
    seconds = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return minutes * 60 + seconds


def validate_config(config: dict) -> list:
    """Full validation — requires all fields (for Mapper + Video Builder)."""
    errors = []
    if not config.get("groq_api_key"):
        errors.append("Groq API key is missing.")
    if not config.get("hf_api_key"):
        errors.append("HuggingFace API key is missing.")
    script_path = config.get("script_path", "")
    if not script_path or not Path(script_path).exists():
        errors.append(f"Script file not found: {script_path}")
    audio_path = config.get("audio_path", "")
    if not audio_path or not Path(audio_path).exists():
        errors.append(f"Audio file not found: {audio_path}")
    return errors


def validate_config_step1(config: dict) -> list:
    """
    Validation for Step 1 — Prompt Generation.
    Only needs: Groq API key + script file.
    Audio is NOT required at this stage.
    """
    errors = []
    if not config.get("groq_api_key"):
        errors.append("Groq API key is missing.")
    script_path = config.get("script_path", "")
    if not script_path or not Path(script_path).exists():
        errors.append(f"Script file not found: {script_path}")
    return errors


def validate_config_pipeline(config: dict) -> list:
    """
    Validation for pipeline steps (AI Mapper + Video Builder).
    Needs: API keys + audio file.
    Images folder is checked at runtime (uploaded by user).
    """
    errors = []
    if not config.get("groq_api_key"):
        errors.append("Groq API key is missing.")
    if not config.get("hf_api_key"):
        errors.append("HuggingFace API key is missing.")
    audio_path = config.get("audio_path", "")
    if not audio_path or not Path(audio_path).exists():
        errors.append(f"Audio file not found: {audio_path}")
    return errors
