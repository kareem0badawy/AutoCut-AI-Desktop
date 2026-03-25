"""
video_builder.py
================
Builds the final video by:
  1. Rendering each scene as a temp MP4 (one at a time, no large concatenation).
  2. Using ffmpeg concat-demuxer to join them in EXPLICIT ORDER.
  3. Adding audio with a final ffmpeg call.

This bypasses moviepy's concatenate_videoclips entirely, which eliminates
any ordering bugs caused by lazy evaluation or internal sorting.

Ken Burns motions (6 presets):
  Coords: (x0, y0) = top-left of W×H crop inside rW×rH render buffer.
  1. pan_up          : x-center, y bottom→top
  2. pan_from_left   : y-center, x 0→center
  3. pan_from_right  : y-center, x right→center
  4. zoom_in_center  : x+y both converge to center
  5. pan_up_left     : x 0→center, y bottom→center
  6. pan_up_right    : x right→center, y bottom→center
"""

import json
import difflib
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from moviepy.config import get_setting            # to find ffmpeg executable
from moviepy.editor import AudioFileClip, ImageSequenceClip
from PIL import Image

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
RENDER_SCALE = 1.12   # over-size render buffer — prevents black borders
MOTION_RANGE = 0.05   # max pan = 5 % of dimension (cinematic, not aggressive)


# ─────────────────────────────────────────────────────────────────────────────
# Motion math
# ─────────────────────────────────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float, dur: float) -> float:
    if dur <= 0:
        return b
    p = max(0.0, min(1.0, t / dur))
    return a + (b - a) * p


def _pan_up(t, dur, rW, rH, W, H):
    """Center-x, y bottom→top (limited range)."""
    cx    = (rW - W) / 2
    my    = H * MOTION_RANGE     # max pixels to travel vertically
    cy    = (rH - H) / 2
    y0    = _lerp(cy + my, cy - my, t, dur)
    return int(cx), int(max(0, min(y0, rH - H)))


def _pan_from_left(t, dur, rW, rH, W, H):
    """Center-y, x left→center (limited range)."""
    cy    = (rH - H) / 2
    mx    = W * MOTION_RANGE
    cx    = (rW - W) / 2
    x0    = _lerp(cx - mx, cx, t, dur)
    return int(max(0, x0)), int(cy)


def _pan_from_right(t, dur, rW, rH, W, H):
    """Center-y, x right→center (limited range)."""
    cy    = (rH - H) / 2
    mx    = W * MOTION_RANGE
    cx    = (rW - W) / 2
    x0    = _lerp(cx + mx, cx, t, dur)
    return int(max(0, min(x0, rW - W))), int(cy)


def _zoom_in_center(t, dur, rW, rH, W, H):
    """Start at slight top-left offset, converge to center."""
    cx    = (rW - W) / 2
    cy    = (rH - H) / 2
    mx    = W * MOTION_RANGE
    my    = H * MOTION_RANGE
    x0    = _lerp(cx - mx, cx, t, dur)
    y0    = _lerp(cy - my, cy, t, dur)
    return int(max(0, x0)), int(max(0, y0))


def _pan_up_left(t, dur, rW, rH, W, H):
    """Bottom-left → center."""
    cx    = (rW - W) / 2
    cy    = (rH - H) / 2
    mx    = W * MOTION_RANGE
    my    = H * MOTION_RANGE
    x0    = _lerp(cx - mx, cx, t, dur)
    y0    = _lerp(cy + my, cy, t, dur)
    return int(max(0, x0)), int(max(0, min(y0, rH - H)))


def _pan_up_right(t, dur, rW, rH, W, H):
    """Bottom-right → center."""
    cx    = (rW - W) / 2
    cy    = (rH - H) / 2
    mx    = W * MOTION_RANGE
    my    = H * MOTION_RANGE
    x0    = _lerp(cx + mx, cx, t, dur)
    y0    = _lerp(cy + my, cy, t, dur)
    return int(max(0, min(x0, rW - W))), int(max(0, min(y0, rH - H)))


_PRESETS = [
    _pan_up,
    _pan_from_left,
    _pan_from_right,
    _zoom_in_center,
    _pan_up_left,
    _pan_up_right,
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Image lookup — EXACT match only from mapping.json filename
# ─────────────────────────────────────────────────────────────────────────────

def _find_image(folders: List[Path], name: str) -> Optional[Path]:
    """
    Exact-match lookup: search for `name` (case-insensitive on Windows)
    in each folder. No fuzzy matching — the name comes from mapping.json
    which was built from the actual uploaded filenames.
    """
    name_lower = name.lower()
    for folder in folders:
        if not folder.exists():
            continue
        for f in folder.iterdir():
            if f.is_file() and f.name.lower() == name_lower:
                return f
    return None


def _get_ffmpeg() -> str:
    """Return path to ffmpeg binary from moviepy's config."""
    try:
        return get_setting("FFMPEG_BINARY")
    except Exception:
        return "ffmpeg"


# ─────────────────────────────────────────────────────────────────────────────
# Frame rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_scene_frames(
    img_path: Path,
    duration: float,
    resolution: Tuple[int, int],
    fps: int,
    preset_fn,
) -> List[np.ndarray]:
    """
    Pre-render all frames for one scene as numpy arrays (H×W×3 uint8).
    Each frame is computed at the correct time offset for smooth motion.
    """
    W, H = resolution
    rW   = int(W * RENDER_SCALE)
    rH   = int(H * RENDER_SCALE)
    dur  = max(duration, 0.001)

    pil = Image.open(img_path).convert("RGB").resize((rW, rH), Image.LANCZOS)
    buf = np.array(pil)     # shape: (rH, rW, 3)

    n_frames = max(1, int(round(duration * fps)))
    frames   = []

    for fi in range(n_frames):
        t = fi / fps
        if preset_fn is not None:
            x0, y0 = preset_fn(t, dur, rW, rH, W, H)
            x0 = max(0, min(int(x0), rW - W))
            y0 = max(0, min(int(y0), rH - H))
            frame = buf[y0 : y0 + H, x0 : x0 + W]
        else:
            cx = (rW - W) // 2
            cy = (rH - H) // 2
            frame = buf[cy : cy + H, cx : cx + W]
        frames.append(frame)

    return frames


def _render_black_frames(duration: float, resolution: Tuple[int, int], fps: int) -> List[np.ndarray]:
    W, H     = resolution
    n_frames = max(1, int(round(duration * fps)))
    black    = np.zeros((H, W, 3), dtype=np.uint8)
    return [black] * n_frames


# ─────────────────────────────────────────────────────────────────────────────
# Core builder
# ─────────────────────────────────────────────────────────────────────────────

def build_video(
    config: dict,
    log:      Callable[[str], None] = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path     = Path(config["base_path"])
    resolution    = _parse_resolution(config.get("output_resolution", "1920x1080"))
    fps           = int(config.get("fps", 24))
    fade_duration = float(config.get("transition_duration", 0.5))
    mapping_path  = base_path / "mapping.json"
    ffmpeg        = _get_ffmpeg()

    # ── Audio ─────────────────────────────────────────────────────────────────
    audio_path_str = config.get("audio_path", "")
    if audio_path_str and Path(audio_path_str).exists():
        audio_path = Path(audio_path_str)
    else:
        audio_path = _find_first_audio(base_path / "assets" / "audio")

    # ── Images folders ────────────────────────────────────────────────────────
    images_folder_str = config.get("images_folder", "")
    if images_folder_str and Path(images_folder_str).exists():
        # Explicit uploaded folder — use IT ONLY
        images_folders: List[Path] = [Path(images_folder_str)]
        log(f"images_folder (uploaded): {images_folder_str}")
    else:
        images_folders = [
            base_path / "output" / "images",
            base_path / "assets"  / "images",
        ]
        log(f"images_folder (default): {[str(f) for f in images_folders]}")

    # ── Output ────────────────────────────────────────────────────────────────
    output_folder_str = config.get("output_folder", "")
    output_path = (
        Path(output_folder_str) / "final_video.mp4"
        if output_folder_str
        else base_path / "assets" / "output" / "final_video.mp4"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not mapping_path.exists():
        raise FileNotFoundError("mapping.json not found. Run AI Mapper first.")

    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # ── Sort ASCENDING by scene_number ────────────────────────────────────────
    mapping = sorted(mapping, key=lambda s: int(s.get("scene_number", 0)))

    log(f"Building video: {len(mapping)} scenes | {resolution[0]}x{resolution[1]} | {fps}fps")
    log(f"Scene order: {[int(s.get('scene_number', 0)) for s in mapping]}")
    log(f"Audio: {audio_path.name}")
    log(f"Output: {output_path}")

    # ── Temp directory ────────────────────────────────────────────────────────
    tmpdir = Path(tempfile.mkdtemp(prefix="autocut_"))
    temp_clips: List[Path] = []
    total          = len(mapping)
    n_presets      = len(_PRESETS)
    missing_images = []

    try:
        for i, scene in enumerate(mapping, start=1):
            snum      = int(scene.get("scene_number", i))
            start_s   = _time_to_seconds(scene["start"])
            end_s     = _time_to_seconds(scene["end"])
            dur       = max(1, end_s - start_s)
            images    = scene.get("images", [])
            preset_fn = _PRESETS[(i - 1) % n_presets]

            log(f"  scene {snum:03d} [{i}/{total}] → {dur}s  [{preset_fn.__name__}]")

            # Collect frames for this scene
            all_frames: List[np.ndarray] = []
            if not images:
                log(f"    no image → black clip")
                all_frames = _render_black_frames(dur, resolution, fps)
            else:
                per_image = dur / len(images)
                for img_name in images:
                    img_path = _find_image(images_folders, img_name)
                    if not img_path:
                        log(f"    MISSING '{img_name}' → black clip")
                        missing_images.append(img_name)
                        all_frames += _render_black_frames(per_image, resolution, fps)
                    else:
                        log(f"    {img_path.name}")
                        all_frames += _render_scene_frames(
                            img_path, per_image, resolution, fps, preset_fn
                        )

            # Write this scene to a temp mp4 using ImageSequenceClip
            temp_path = tmpdir / f"scene_{snum:03d}.mp4"
            scene_clip = ImageSequenceClip(all_frames, fps=fps)

            if fade_duration > 0 and dur > fade_duration * 2:
                scene_clip = scene_clip.fadein(fade_duration).fadeout(fade_duration)

            scene_clip.write_videofile(
                str(temp_path),
                fps=fps,
                codec="libx264",
                audio=False,
                threads=2,
                preset="ultrafast",
                logger=None,
            )
            temp_clips.append(temp_path)
            log(f"    ✓ written to {temp_path.name}")

            if progress:
                progress(i, total)

        if not temp_clips:
            raise ValueError("No scene clips rendered.")

        # ── Concat all temp clips in EXPLICIT ORDER via ffmpeg ────────────────
        log("Concatenating scenes with ffmpeg...")
        concat_list = tmpdir / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for p in temp_clips:      # already sorted because we appended in order
                f.write(f"file '{str(p).replace(chr(92), '/')}'\n")

        silent_output = tmpdir / "silent_video.mp4"
        cmd_concat = [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "copy",
            str(silent_output),
        ]
        log(f"ffmpeg concat: {' '.join(cmd_concat)}")
        result = subprocess.run(cmd_concat, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")

        # ── Add audio ─────────────────────────────────────────────────────────
        log("Adding audio...")
        cmd_audio = [
            ffmpeg, "-y",
            "-i", str(silent_output),
            "-i", str(audio_path),
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]
        result = subprocess.run(cmd_audio, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio failed:\n{result.stderr}")

        if missing_images:
            log(f"\nWARNING: {len(missing_images)} images missing (black clips used)")

        log(f"\nVideo saved: {output_path}")
        return str(output_path)

    finally:
        # Clean up temp files
        for p in temp_clips:
            try:
                p.unlink()
            except Exception:
                pass
        for f in [tmpdir / "concat.txt", tmpdir / "silent_video.mp4"]:
            try:
                f.unlink()
            except Exception:
                pass
        try:
            tmpdir.rmdir()
        except Exception:
            pass


def run_video_builder(config: dict, log=print, progress=None):
    build_video(config, log=log, progress=progress)


def _find_first_audio(audio_folder: Path) -> Path:
    if not audio_folder.exists():
        raise FileNotFoundError(f"Audio folder not found: {audio_folder}")
    for f in sorted(audio_folder.iterdir()):
        if f.is_file() and f.suffix.lower() in {".mp3", ".wav", ".m4a"}:
            return f
    raise FileNotFoundError(f"No audio file found in: {audio_folder}")
