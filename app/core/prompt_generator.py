import json
import math
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from groq import Groq


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


def _build_previous_summary(all_scenes: list, last_n: int = 5) -> str:
    if not all_scenes:
        return "No previous scenes yet."
    last = all_scenes[-last_n:]
    lines = []
    for s in last:
        desc = s.get("scene_description", "")
        label = s.get("label_text", "")
        lines.append(f"- Scene {s.get('scene_number', '?')}: [{label}] {desc}")
    return "\n".join(lines)


def _generate_batch(
    client: Groq,
    script_chunk: str,
    style: dict,
    batch_num: int,
    total_batches: int,
    scenes_in_batch: int,
    seconds_per_image: int,
    template: str,
    all_scenes: list,
    log: Callable[[str], None],
) -> list:
    previous_summary = _build_previous_summary(all_scenes)
    prompt = template.format(
        batch_num=batch_num,
        total_batches=total_batches,
        scenes_in_batch=scenes_in_batch,
        seconds_per_image=seconds_per_image,
        script_chunk=script_chunk,
        style_lock=style["style_lock"],
        mood=style["mood"],
        negative_prompt=style["negative_prompt"],
        previous_scenes=previous_summary,
    )
    max_tokens = min(scenes_in_batch * 500, 8000)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )
            raw = response.choices[0].message.content.strip()
            result = _clean_and_parse_json(raw)
            log(f"  Batch {batch_num}: parsed {len(result)} scenes")
            return result
        except json.JSONDecodeError as e:
            log(f"  Attempt {attempt + 1}: JSON parse error — {e}")
            if attempt < 2:
                time.sleep(3)
            else:
                log(f"  Failed after 3 attempts, skipping batch.")
                return []
        except Exception as e:
            log(f"  Attempt {attempt + 1}: Error — {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                return []
    return []


def generate_prompts(
    config: dict,
    style: dict,
    template: str,
    limit: Optional[int] = None,
    reset: bool = False,
    log: Callable[[str], None] = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path = Path(config["base_path"])
    script_path = Path(config.get("script_path", base_path / "script.txt"))
    output_path = base_path / "output" / "prompts.json"
    output_txt_path = base_path / "output" / "prompts_output.txt"

    if not script_path.exists():
        raise FileNotFoundError(f"Script file not found: {script_path}")

    with open(script_path, "r", encoding="utf-8-sig") as f:
        script = f.read().strip()

    seconds_per_image = int(config.get("seconds_per_image", 7))
    audio_duration = _parse_duration(str(config.get("audio_duration", "4.30")))
    total_images = math.ceil(audio_duration / seconds_per_image)

    if limit:
        total_images = min(limit, total_images)
        log(f"Limit active — generating {total_images} scenes only")

    scenes_per_batch = int(config.get("scenes_per_batch", 10))
    total_batches = math.ceil(total_images / scenes_per_batch)

    log(f"Audio duration: {audio_duration}s | {seconds_per_image}s per image | {total_images} total scenes | {total_batches} batches")

    os.makedirs(output_path.parent, exist_ok=True)

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

    if not config.get("groq_api_key"):
        raise ValueError("Groq API key is missing in settings.")

    client = Groq(api_key=config["groq_api_key"])
    words = script.split()
    words_per_batch = math.ceil(len(words) / total_batches)
    scene_counter = resume_from + 1

    for i in range(total_batches):
        batch_start_scene = i * scenes_per_batch
        if batch_start_scene < resume_from:
            log(f"Batch {i + 1}/{total_batches} — already done, skipping")
            continue

        start_word = i * words_per_batch
        end_word = min((i + 1) * words_per_batch, len(words))
        chunk = " ".join(words[start_word:end_word])

        remaining = total_images - len(all_scenes)
        if remaining <= 0:
            break
        batch_size = min(scenes_per_batch, remaining)

        log(f"Batch {i + 1}/{total_batches} — {batch_size} scenes...")

        batch = _generate_batch(
            client, chunk, style,
            batch_num=i + 1,
            total_batches=total_batches,
            scenes_in_batch=batch_size,
            seconds_per_image=seconds_per_image,
            template=template,
            all_scenes=all_scenes,
            log=log,
        )

        for s in batch:
            s["scene_number"] = scene_counter
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

    txt = "=" * 60 + "\n"
    txt += "AUTOCUT - PROMPTS OUTPUT\n"
    txt += f"Total Scenes: {len(all_scenes)} | Seconds per image: {seconds_per_image}\n"
    txt += "=" * 60 + "\n\n"
    for s in all_scenes:
        txt += f"SCENE {s['scene_number']}\n"
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


def _parse_duration(duration_str: str) -> int:
    parts = str(duration_str).strip().split(".")
    minutes = int(parts[0]) if parts and parts[0] else 0
    seconds = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return minutes * 60 + seconds
