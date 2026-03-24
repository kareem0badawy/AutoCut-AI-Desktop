import json
import difflib
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from moviepy.editor import AudioFileClip, ColorClip, ImageClip, concatenate_videoclips
from PIL import Image

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def _parse_resolution(value: str) -> Tuple[int, int]:
    text = str(value).lower().strip()
    if "x" not in text:
        return 1920, 1080
    w, h = text.split("x", 1)
    return int(w), int(h)


def _time_to_seconds(t: str) -> int:
    parts = [int(p) for p in t.strip().split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def _list_image_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)


def _find_image_in_folder(folder: Path, name: str) -> Optional[Path]:
    if not folder.exists():
        return None
    files = _list_image_files(folder)
    name_lower = name.lower()
    stem = Path(name).stem.lower()
    for f in files:
        if f.name.lower() == name_lower:
            return f
    for f in files:
        if f.stem.lower() == stem:
            return f
    for f in files:
        if f.stem.lower().startswith(stem) or stem.startswith(f.stem.lower()):
            return f
    stems = [f.stem for f in files]
    close = difflib.get_close_matches(stem, stems, n=1, cutoff=0.35)
    if close:
        for f in files:
            if f.stem == close[0]:
                return f
    return None


def _find_image(folders: List[Path], name: str) -> Optional[Path]:
    for folder in folders:
        result = _find_image_in_folder(folder, name)
        if result:
            return result
    return None


def _make_image_clip(img_path: Path, duration: float, resolution: Tuple[int, int], fade_duration: float):
    img = Image.open(img_path).convert("RGB")
    img = img.resize(resolution, Image.LANCZOS)
    clip = ImageClip(np.array(img), duration=duration)
    if fade_duration > 0 and duration > fade_duration * 2:
        clip = clip.fadein(fade_duration).fadeout(fade_duration)
    return clip


def build_video(
    config: dict,
    log: Callable[[str], None] = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path = Path(config["base_path"])
    resolution = _parse_resolution(config.get("output_resolution", "1920x1080"))
    fps = int(config.get("fps", 24))
    fade_duration = float(config.get("transition_duration", 0.5))

    mapping_path = base_path / "mapping.json"

    audio_path_str = config.get("audio_path", "")
    if audio_path_str and Path(audio_path_str).exists():
        audio_path = Path(audio_path_str)
    else:
        audio_folder = base_path / "assets" / "audio"
        audio_path = _find_first_audio(audio_folder)

    images_folder_str = config.get("images_folder", "")
    images_folders = [
        base_path / "output" / "images",
        base_path / "assets" / "images",
    ]
    if images_folder_str and Path(images_folder_str).exists():
        images_folders.insert(0, Path(images_folder_str))

    output_folder_str = config.get("output_folder", "")
    if output_folder_str:
        output_path = Path(output_folder_str) / "final_video.mp4"
    else:
        output_path = base_path / "assets" / "output" / "final_video.mp4"

    if not mapping_path.exists():
        raise FileNotFoundError("mapping.json not found. Run Step 3 first.")

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    log(f"Building video: {len(mapping)} scenes | {resolution[0]}x{resolution[1]} | {fps}fps")
    log(f"Audio: {audio_path.name}")
    log(f"Output: {output_path}")

    all_clips = []
    missing_images = []
    total = len(mapping)

    for i, scene in enumerate(mapping, start=1):
        start = _time_to_seconds(scene["start"])
        end = _time_to_seconds(scene["end"])
        scene_duration = max(1, end - start)
        images = scene.get("images", [])

        if not images:
            log(f"  scene {i:03d}: no image -> black clip ({scene_duration}s)")
            all_clips.append(ColorClip(size=resolution, color=(10, 10, 10), duration=scene_duration))
        else:
            per_image = scene_duration / len(images)
            for img_name in images:
                img_path = _find_image(images_folders, img_name)
                if not img_path:
                    log(f"  scene {i:03d}: missing '{img_name}' -> black clip")
                    missing_images.append(img_name)
                    all_clips.append(ColorClip(size=resolution, color=(10, 10, 10), duration=per_image))
                else:
                    log(f"  scene {i:03d}: {img_path.name}")
                    all_clips.append(_make_image_clip(img_path, per_image, resolution, fade_duration))

        if progress:
            progress(i, total)

    if not all_clips:
        raise ValueError("No clips built. Check mapping.json and images folders.")

    log("Compositing video...")
    final_video = concatenate_videoclips(all_clips, method="compose")
    audio = AudioFileClip(str(audio_path))

    if audio.duration < final_video.duration:
        final_video = final_video.subclip(0, audio.duration)
    else:
        audio = audio.subclip(0, final_video.duration)

    final = final_video.set_audio(audio)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    log("Writing video file (this may take a while)...")
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast",
        logger=None,
    )

    if missing_images:
        log(f"\nWARNING: {len(missing_images)} images were missing (shown as black clips)")

    log(f"\nVideo saved: {output_path}")
    return str(output_path)


def run_video_builder(config: dict, log=print, progress=None):
    build_video(config, log=log, progress=progress)


def _find_first_audio(audio_folder: Path) -> Path:
    if not audio_folder.exists():
        raise FileNotFoundError(f"Audio folder not found: {audio_folder}")
    for file in sorted(audio_folder.iterdir()):
        if file.is_file() and file.suffix.lower() in {".mp3", ".wav", ".m4a"}:
            return file
    raise FileNotFoundError(f"No audio file found in: {audio_folder}")
