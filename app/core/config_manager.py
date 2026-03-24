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
    "style_lock": "vintage documentary collage illustration, scrapbook collage style with torn paper borders, archival documents and financial ledgers layered in background, paper labels and stamps, muted vintage colors with warm amber and brown tones, antique highlights, cinematic lighting, fully colored vintage illustration, hand-colored historical print style, textured parchment paper background, historical documentary style, NOT black and white",
    "negative_prompt": "black and white, monochrome, pure black background, white background, clean border, hyperrealistic skin, photographic face, CGI, anime, flat design, oversaturated, watermark, modern style, digital art, 3D render",
    "label_style": "bold rubber stamp uppercase text",
    "aspect_ratio": "16:9",
    "mood": "dramatic, historical, documentary, somber"
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
