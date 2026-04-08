# app\core\video_builder.py
"""
video_builder.py
================
Builds the final video by:
  1. Rendering each scene as a temp MP4 (one at a time, no large concatenation).
  2. Using ffmpeg concat-demuxer to join them in EXPLICIT ORDER.
  3. Adding audio with a final ffmpeg call.

moviepy is NOT used anymore — all encoding is done via ffmpeg stdin pipe.
This avoids moviepy v1/v2 API incompatibilities.

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
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
RENDER_SCALE = 1.10   # over-size render buffer — prevents black borders
MOTION_RANGE = 0.04   # max pan = 4 % of dimension (cinematic, not aggressive)


# ─────────────────────────────────────────────────────────────────────────────
# Motion math (Ken Burns)
# ─────────────────────────────────────────────────────────────────────────────

def _lerp(a: float, b: float, t: float, dur: float) -> float:
    """Linear interpolation with ease-out-quad to eliminate start-lag."""
    if dur <= 0:
        return b
    # Use ease-out-quad so motion starts immediately at full speed and decelerates
    p = max(0.0, min(1.0, t / dur))
    p = 1.0 - (1.0 - p) ** 2   # ease-out-quad: fast start, smooth end
    return a + (b - a) * p


def _pan_up(t, dur, rW, rH, W, H):
    """Center-x, y bottom→top (limited range)."""
    cx  = (rW - W) / 2
    my  = H * MOTION_RANGE
    cy  = (rH - H) / 2
    y0  = _lerp(cy + my, cy - my, t, dur)
    return int(cx), int(max(0, min(y0, rH - H)))


def _pan_from_left(t, dur, rW, rH, W, H):
    """Center-y, x left→center (limited range)."""
    cy  = (rH - H) / 2
    mx  = W * MOTION_RANGE
    cx  = (rW - W) / 2
    x0  = _lerp(cx - mx, cx, t, dur)
    return int(max(0, x0)), int(cy)


def _pan_from_right(t, dur, rW, rH, W, H):
    """Center-y, x right→center (limited range)."""
    cy  = (rH - H) / 2
    mx  = W * MOTION_RANGE
    cx  = (rW - W) / 2
    x0  = _lerp(cx + mx, cx, t, dur)
    return int(max(0, min(x0, rW - W))), int(cy)


def _zoom_in_center(t, dur, rW, rH, W, H):
    """Start at slight top-left offset, converge to center."""
    cx  = (rW - W) / 2
    cy  = (rH - H) / 2
    mx  = W * MOTION_RANGE
    my  = H * MOTION_RANGE
    x0  = _lerp(cx - mx, cx, t, dur)
    y0  = _lerp(cy - my, cy, t, dur)
    return int(max(0, x0)), int(max(0, y0))


def _pan_up_left(t, dur, rW, rH, W, H):
    """Bottom-left → center."""
    cx  = (rW - W) / 2
    cy  = (rH - H) / 2
    mx  = W * MOTION_RANGE
    my  = H * MOTION_RANGE
    x0  = _lerp(cx - mx, cx, t, dur)
    y0  = _lerp(cy + my, cy, t, dur)
    return int(max(0, x0)), int(max(0, min(y0, rH - H)))


def _pan_up_right(t, dur, rW, rH, W, H):
    """Bottom-right → center."""
    cx  = (rW - W) / 2
    cy  = (rH - H) / 2
    mx  = W * MOTION_RANGE
    my  = H * MOTION_RANGE
    x0  = _lerp(cx + mx, cx, t, dur)
    y0  = _lerp(cy + my, cy, t, dur)
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
    """
    Find ffmpeg binary.
    Order: imageio_ffmpeg → shutil.which → moviepy v1 config → common paths → "ffmpeg".
    """
    # 0. imageio_ffmpeg — bundled with the package (highest priority, always works)
    try:
        import imageio_ffmpeg                           # type: ignore
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # 1. shutil.which — covers any PATH installation
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. moviepy v1 config API (not available in v2, so wrapped in try/except)
    try:
        from moviepy.config import get_setting          # type: ignore
        path = get_setting("FFMPEG_BINARY")
        if path and os.path.exists(path):
            return path
    except Exception:
        pass

    # 3. Common explicit paths (Windows + Unix)
    common = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
    ]
    for p in common:
        if os.path.exists(p):
            return p

    return "ffmpeg"  # last resort: assume it is in PATH


# ─────────────────────────────────────────────────────────────────────────────
# Fade helper
# ─────────────────────────────────────────────────────────────────────────────

def _apply_fades(
    frames: List[np.ndarray],
    fps: int,
    fade_duration: float,
) -> List[np.ndarray]:
    """
    Apply linear fade-in (from black) and fade-out (to black) to a frame list.
    Replaces moviepy's .fadein() / .fadeout().
    """
    n = len(frames)
    if n == 0 or fade_duration <= 0:
        return frames

    fade_n = min(max(1, int(fade_duration * fps)), n // 2)
    result = [f.copy() for f in frames]

    # Fade in: frames 0..fade_n-1
    for i in range(fade_n):
        alpha = i / fade_n
        result[i] = (frames[i].astype(np.float32) * alpha).astype(np.uint8)

    # Fade out: frames n-fade_n..n-1
    for i in range(fade_n):
        alpha = (fade_n - 1 - i) / fade_n
        result[n - fade_n + i] = (
            frames[n - fade_n + i].astype(np.float32) * alpha
        ).astype(np.uint8)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# ffmpeg pipe encoder — replaces moviepy.ImageSequenceClip
# ─────────────────────────────────────────────────────────────────────────────

def _frames_to_mp4(
    frames: List[np.ndarray],
    fps: int,
    output_path: Path,
    ffmpeg: str,
    fade_duration: float = 0.0,
    duration: float = 0.0,
) -> None:
    """
    Encode a list of HxWx3 uint8 numpy frames to H.264 mp4
    by piping raw RGB24 data to ffmpeg stdin.

    This replaces moviepy.ImageSequenceClip + write_videofile entirely,
    keeping Ken Burns motion intact (motion is baked into the frames).
    """
    if not frames:
        return

    # Apply fades if duration is long enough to accommodate both ends
    if fade_duration > 0 and duration > fade_duration * 2:
        frames = _apply_fades(frames, fps, fade_duration)

    h, w = frames[0].shape[:2]

    cmd = [
        ffmpeg, "-y",
        "-f",       "rawvideo",
        "-vcodec",  "rawvideo",
        "-s",       f"{w}x{h}",
        "-pix_fmt", "rgb24",
        "-r",       str(fps),
        "-i",       "pipe:0",
        "-c:v",     "libx264",
        "-preset",  "ultrafast",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait()
    except Exception as exc:
        try:
            proc.kill()
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg pipe error: {exc}") from exc

    if proc.returncode != 0:
        err_txt = b""
        try:
            err_txt = proc.stderr.read()
        except Exception:
            pass
        raise RuntimeError(
            f"ffmpeg encoding failed (exit {proc.returncode}):\n"
            f"{err_txt.decode(errors='replace')}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Frame rendering (Ken Burns)
# ─────────────────────────────────────────────────────────────────────────────

def _cover_resize(pil_img: "Image.Image", target_w: int, target_h: int) -> "Image.Image":
    """
    Resize image to COVER target_w × target_h completely (no black bars).
    Scales by the LARGER ratio so the image always fills the entire frame,
    then center-crops to the exact target size.
    """
    src_w, src_h = pil_img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(target_w, int(round(src_w * scale)))
    new_h = max(target_h, int(round(src_h * scale)))
    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    return pil_img.crop((left, top, left + target_w, top + target_h))


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

    Image is cover-resized into the render buffer (rW × rH) so it always
    fills the frame completely — zero black bars regardless of aspect ratio.
    Ken Burns motion is then applied by cropping the W×H viewport from the
    slightly larger render buffer, giving parallax/zoom effects.
    """
    W, H = resolution
    rW   = int(W * RENDER_SCALE)
    rH   = int(H * RENDER_SCALE)
    dur  = max(duration, 0.001)

    # Cover-fill: image fills rW×rH completely (no letterbox / pillarbox)
    pil = _cover_resize(Image.open(img_path).convert("RGB"), rW, rH)
    buf = np.array(pil)     # shape: (rH, rW, 3)

    n_frames = max(1, int(round(duration * fps)))
    frames   = []

    for fi in range(n_frames):
        # t uses fps-accurate time; first frame t=0 → start position instantly
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
        frames.append(frame.copy())   # .copy() prevents aliasing when buf is large

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
    log(f"ffmpeg: {ffmpeg}")

    # ── Audio ─────────────────────────────────────────────────────────────────
    audio_path_str = config.get("audio_path", "")
    if audio_path_str and Path(audio_path_str).exists():
        audio_path = Path(audio_path_str)
    else:
        audio_path = _find_first_audio(base_path / "assets" / "audio")

    if not audio_path or not audio_path.exists():
        raise FileNotFoundError(
            f"Audio file not found.\n"
            f"Tried: {audio_path_str!r}\n"
            f"Please upload an audio file in Step 3."
        )

    # ── Images folders ────────────────────────────────────────────────────────
    images_folder_str = config.get("images_folder", "")
    if images_folder_str and Path(images_folder_str).exists():
        images_folders: List[Path] = [Path(images_folder_str)]
        log(f"Using uploaded images folder: {images_folder_str}")
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
            snum    = int(scene.get("scene_number", i))
            start_s = _time_to_seconds(scene["start"])
            end_s   = _time_to_seconds(scene["end"])
            dur     = max(1, end_s - start_s)
            images  = scene.get("images", [])
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

            # Encode this scene to a temp mp4 using ffmpeg pipe (no moviepy)
            temp_path = tmpdir / f"scene_{snum:03d}.mp4"
            _frames_to_mp4(all_frames, fps, temp_path, ffmpeg, fade_duration, dur)
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


def _find_first_audio(audio_folder: Path) -> Optional[Path]:
    if not audio_folder.exists():
        return None
    for f in sorted(audio_folder.iterdir()):
        if f.is_file() and f.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg"}:
            return f
    return None
