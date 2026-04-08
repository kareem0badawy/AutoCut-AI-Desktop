import json
import math
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from groq import Groq


# ─────────────────────────────────────────────
# JSON helpers
# ─────────────────────────────────────────────

def _clean_and_parse_json(raw: str) -> list:
    raw = re.sub(r"```json", "", raw)
    raw = re.sub(r"```", "", raw)
    raw = raw.strip()
    match = re.search(r'\[.*\]', raw, re.DOTALL)
    if match:
        raw = match.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raw = re.sub(r',\s*\{[^}]*$', '', raw)
        raw = re.sub(r',\s*$', '', raw)
        if not raw.endswith(']'):
            raw += ']'
        return json.loads(raw)


# ─────────────────────────────────────────────
# Whisper transcription
# ─────────────────────────────────────────────

def _transcribe_audio(audio_path: str, model_size: str = "base", log=print):
    """
    يشغّل Whisper على الصوت ويرجع:
      segments : [{"text": str, "start": float, "end": float}, ...]
      duration : float  (مدة الصوت بالثواني)
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper مش مثبت. شغّل: pip install faster-whisper"
        )

    log(f"Loading Whisper model ({model_size})...")
    model = WhisperModel(model_size, compute_type="int8")

    log(f"Transcribing: {audio_path}")
    segments_iter, info = model.transcribe(audio_path, language="en")

    segments = []
    for seg in segments_iter:
        segments.append({
            "text":  seg.text.strip(),
            "start": round(seg.start, 2),
            "end":   round(seg.end,   2),
        })

    log(f"Transcription done: {len(segments)} segments | duration={info.duration:.1f}s")
    return segments, info.duration


# ─────────────────────────────────────────────
# Group Whisper segments into scene chunks
# ─────────────────────────────────────────────

def _group_segments_into_scenes(segments: list, seconds_per_image: int) -> list:
    """
    يجمع الـ Whisper segments في groups.
    كل group بيغطي seconds_per_image تقريباً.

    Output:
    [
      {"scene_index": 0, "start": 0.0, "end": 7.4, "text": "..."},
      ...
    ]
    """
    if not segments:
        return []

    scenes        = []
    current_text  = []
    current_start = segments[0]["start"]
    scene_index   = 0

    for seg in segments:
        current_text.append(seg["text"])
        elapsed = seg["end"] - current_start

        if elapsed >= seconds_per_image:
            scenes.append({
                "scene_index": scene_index,
                "start":       current_start,
                "end":         seg["end"],
                "text":        " ".join(current_text).strip(),
            })
            scene_index  += 1
            current_text  = []
            current_start = seg["end"]

    # آخر group لو في كلام متبقي
    if current_text:
        scenes.append({
            "scene_index": scene_index,
            "start":       current_start,
            "end":         segments[-1]["end"],
            "text":        " ".join(current_text).strip(),
        })

    return scenes


# ─────────────────────────────────────────────
# Scene prompt fixer
# ─────────────────────────────────────────────

REQUIRED_OPENING = (
    "Editorial collage illustration. "
    "A hand-drawn watercolor subject with clear visual focus, "
    "richly illustrated with relevant details subtly sketched. "
    "Background is aged parchment paper, dark brown stained, "
    "heavily textured with natural grain, slightly darker at edges."
)
REQUIRED_STYLE_TAGS = (
    " Minimal clutter, strong focal composition, "
    "vintage documentary feel, aged documentary mixed media illustration."
)

FIXED_NEGATIVE = (
    "white background, white margins, blank areas, empty space, "
    "white corners, white edges, photographic realism, photograph, "
    "3D render, anime, neon, modern digital art, glossy, black and white, "
    "monochrome, grayscale, washed out, blurry, futuristic"
)


def _fix_scene(scene: dict) -> dict:
    prompt = scene.get("main_prompt", "")
    if not prompt.startswith("Editorial collage illustration."):
        prompt = REQUIRED_OPENING + " " + prompt
    if "vintage documentary feel" not in prompt.lower():
        prompt = prompt.rstrip(".") + "." + REQUIRED_STYLE_TAGS
    scene["main_prompt"] = prompt
    scene["negative_prompt"] = FIXED_NEGATIVE
    return scene


# ─────────────────────────────────────────────
# Previous scenes summary (for variety)
# ─────────────────────────────────────────────

def _build_previous_summary(all_scenes: list, last_n: int = 5) -> str:
    if not all_scenes:
        return "No previous scenes yet."
    lines = []
    for s in all_scenes[-last_n:]:
        lines.append(
            f"- Scene {s.get('scene_number', '?')}: "
            f"[{s.get('label_text', '')}] {s.get('scene_description', '')}"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────
# LLM batch generation
# ─────────────────────────────────────────────

def _generate_batch(
    client:           Groq,
    scene_chunks:     list,
    style:            dict,
    batch_num:        int,
    total_batches:    int,
    template:         str,
    all_scenes:       list,
    seconds_per_image: int,
    log:              Callable[[str], None],
) -> list:

    scenes_in_batch = len(scene_chunks)

    # الـ script_chunk يحتوي على النص الفعلي من الصوت لكل scene
    script_chunk = "\n".join(
        f"[Scene {sc['scene_index'] + 1} | {sc['start']:.1f}s–{sc['end']:.1f}s]: {sc['text']}"
        for sc in scene_chunks
    )

    previous_summary = _build_previous_summary(all_scenes)

    prompt = template.format(
        batch_num         = batch_num,
        total_batches     = total_batches,
        scenes_in_batch   = scenes_in_batch,
        seconds_per_image = seconds_per_image,
        script_chunk      = script_chunk,
        style_lock        = style["style_lock"],
        mood              = style["mood"],
        negative_prompt   = style["negative_prompt"],
        previous_scenes   = previous_summary,
    )

    max_tokens = min(scenes_in_batch * 500, 8000)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content.strip()
            log(f"  RAW (first 400): {raw[:400]}")
            result = _clean_and_parse_json(raw)
            log(f"  Batch {batch_num}: parsed {len(result)} scenes")
            return result

        except json.JSONDecodeError as e:
            log(f"  Attempt {attempt + 1}: JSON error — {e}")
            if attempt < 2:
                time.sleep(3)
            else:
                log("  Failed after 3 attempts, skipping batch.")
                return []
        except Exception as e:
            log(f"  Attempt {attempt + 1}: Error — {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                return []
    return []


# ─────────────────────────────────────────────
# Main generate function
# ─────────────────────────────────────────────

def generate_prompts(
    config:   dict,
    style:    dict,
    template: str,
    limit:    Optional[int]                        = None,
    reset:    bool                                 = False,
    log:      Callable[[str], None]                = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path   = Path(config["base_path"])
    audio_path  = config.get("audio_path", str(base_path / "assets/audio/audio.mp3"))
    output_path     = base_path / "output" / "prompts.json"
    output_txt_path = base_path / "output" / "prompts_output.txt"
    whisper_cache   = base_path / "output" / "whisper_segments.json"

    seconds_per_image = int(config.get("seconds_per_image", 7))
    scenes_per_batch  = int(config.get("scenes_per_batch",  10))
    whisper_model     = config.get("whisper_model", "base")

    os.makedirs(output_path.parent, exist_ok=True)

    # ── Step 1: Transcribe (أو load من الـ cache) ──
    if whisper_cache.exists() and not reset:
        log("Loading cached Whisper segments...")
        with open(whisper_cache, "r", encoding="utf-8") as f:
            cached = json.load(f)
        segments       = cached["segments"]
        audio_duration = cached["duration"]
    else:
        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        segments, audio_duration = _transcribe_audio(audio_path, whisper_model, log)
        with open(whisper_cache, "w", encoding="utf-8") as f:
            json.dump(
                {"segments": segments, "duration": audio_duration},
                f, indent=2, ensure_ascii=False
            )
        log(f"Whisper segments cached → {whisper_cache}")

    # ── Step 2: Group segments into scenes ──
    all_scene_chunks = _group_segments_into_scenes(segments, seconds_per_image)
    total_images     = len(all_scene_chunks)

    if limit:
        total_images     = min(limit, total_images)
        all_scene_chunks = all_scene_chunks[:total_images]
        log(f"Limit active — generating {total_images} scenes only")

    total_batches = math.ceil(total_images / scenes_per_batch)

    log(
        f"Audio: {audio_duration:.1f}s | {seconds_per_image}s/image | "
        f"{total_images} scenes | {total_batches} batches"
    )

    # ── Step 3: Resume logic ──
    if reset and output_path.exists():
        output_path.unlink()
        log("Reset: deleted old prompts file")
        all_scenes, resume_from = [], 0
    elif output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            all_scenes = json.load(f)
        resume_from = len(all_scenes)
        if resume_from >= total_images:
            log(f"Already complete ({resume_from} scenes). Nothing to do.")
            return
        log(f"Resuming from scene {resume_from + 1}")
    else:
        all_scenes, resume_from = [], 0

    log(
        f"DEBUG: resume_from={resume_from} | total_images={total_images} | "
        f"whisper_segments={len(segments)}"
    )

    if not config.get("groq_api_key"):
        raise ValueError("Groq API key is missing in settings.")

    client        = Groq(api_key=config["groq_api_key"])
    scene_counter = resume_from + 1

    # ── Step 4: Generate batches ──
    for i in range(total_batches):
        batch_start = i * scenes_per_batch
        batch_end   = min(batch_start + scenes_per_batch, total_images)

        if batch_start < resume_from:
            log(f"Batch {i + 1}/{total_batches} — already done, skipping")
            continue

        batch_chunks = all_scene_chunks[batch_start:batch_end]
        remaining    = total_images - len(all_scenes)
        if remaining <= 0:
            break

        log(
            f"Batch {i + 1}/{total_batches} — {len(batch_chunks)} scenes "
            f"({batch_chunks[0]['start']:.1f}s → {batch_chunks[-1]['end']:.1f}s)..."
        )

        batch = _generate_batch(
            client            = client,
            scene_chunks      = batch_chunks,
            style             = style,
            batch_num         = i + 1,
            total_batches     = total_batches,
            template          = template,
            all_scenes        = all_scenes,
            seconds_per_image = seconds_per_image,
            log               = log,
        )

        for j, s in enumerate(batch):
            s["scene_number"] = scene_counter
            # نضيف timestamps الحقيقية من Whisper في كل scene
            if j < len(batch_chunks):
                s["start_time"] = batch_chunks[j]["start"]
                s["end_time"]   = batch_chunks[j]["end"]
                s["audio_text"] = batch_chunks[j]["text"]
            s = _fix_scene(s)
            all_scenes.append(s)
            scene_counter += 1

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_scenes, f, indent=2, ensure_ascii=False)

        log(f"  Saved {len(all_scenes)}/{total_images} scenes")
        if progress:
            progress(len(all_scenes), total_images)

        if i < total_batches - 1 and (total_images - len(all_scenes)) > 0:
            log("Waiting 4 seconds...")
            time.sleep(4)

    # ── Step 5: Save readable txt ──
    txt  = "=" * 60 + "\n"
    txt += "AUTOCUT - PROMPTS OUTPUT\n"
    txt += f"Total Scenes: {len(all_scenes)} | {seconds_per_image}s/image\n"
    txt += "=" * 60 + "\n\n"

    for s in all_scenes:
        txt += f"SCENE {s['scene_number']}"
        if "start_time" in s:
            txt += f"  [{s['start_time']:.1f}s – {s['end_time']:.1f}s]"
        txt += "\n"
        if "audio_text" in s:
            txt += f"Audio: {s['audio_text']}\n"
        txt += f"Description: {s.get('scene_description', '')}\n"
        txt += "-" * 40 + "\n"
        txt += f"MAIN PROMPT:\n{s['main_prompt']}\n\n"
        txt += f"LABEL TEXT: {s['label_text']}\n"
        txt += f"SECONDARY LABELS: {', '.join(s.get('secondary_labels', []))}\n"
        txt += f"\nNEGATIVE PROMPT:\n{s.get('negative_prompt', '')}\n"
        txt += "=" * 60 + "\n\n"

    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(txt)

    log(f"\nDone! Total scenes: {len(all_scenes)}")
    log(f"Output saved to: {output_path.parent}/")


# ─────────────────────────────────────────────
# Public entry point (called from GUI)
# ─────────────────────────────────────────────

def run_prompt_generation(
    config:   dict,
    style:    dict,
    reset:    bool             = False,
    limit:    Optional[int]    = None,
    log:      Callable         = print,
    progress: Optional[Callable] = None,
):
    base_path     = Path(config["base_path"])
    template_path = base_path / "prompts_template.txt"

    if template_path.exists():
        with open(template_path, "r", encoding="utf-8-sig") as f:
            template = f.read().strip()
    else:
        template = style.get("template", "")

    generate_prompts(
        config, style, template,
        limit=limit, reset=reset,
        log=log, progress=progress,
    )