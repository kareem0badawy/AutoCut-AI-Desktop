# generate_smart_mapping.py
from faster_whisper import WhisperModel
import json
from pathlib import Path

# ===== CONFIG =====
AUDIO_PATH = "assets/audio/audio.mp3"
PROMPTS_PATH = "output/prompts.json"
OUTPUT_MAPPING = "mapping.json"
MODEL_SIZE = "base"  # ممكن تخليه small أو medium لو عايز دقة أعلى

# ==================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def seconds_to_mmss(s):
    m = int(s) // 60
    s = int(s) % 60
    return f"{m:02d}:{s:02d}"

print("🎧 Loading Whisper model...")
model = WhisperModel(MODEL_SIZE, compute_type="int8")

print("🎙 Transcribing audio...")
segments, _ = model.transcribe(AUDIO_PATH)

transcript = []
for seg in segments:
    transcript.append({
        "text": seg.text.strip(),
        "start": seg.start,
        "end": seg.end
    })

print(f"✅ extracted {len(transcript)} segments")

prompts = load_json(PROMPTS_PATH)

# ===== Mapping Logic =====

mapping = []

def get_segment_for_scene(i):
    # تقسيم بسيط: كل scene ياخد segment بنفس الترتيب
    if i < len(transcript):
        return transcript[i]
    return transcript[-1]

for i, scene in enumerate(prompts):
    seg = get_segment_for_scene(i)

    mapping.append({
        "scene_number": scene.get("scene_number", i + 1),
        "start": seconds_to_mmss(seg["start"]),
        "end": seconds_to_mmss(seg["end"]),
        "images": [f"scene_{i+1:03d}.jpg"],
        "scene_description": scene.get("scene_description", ""),
        "label_text": scene.get("label_text", "")
    })

save_json(mapping, OUTPUT_MAPPING)

print("🔥 Smart mapping generated!")