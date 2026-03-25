"""
ai_mapper.py
============
Maps prompts.json scenes to uploaded image files, then writes mapping.json.

Image matching strategy:
  PRIMARY (only): match by scene_number extracted from filename.
    e.g. "scene_003_..." → scene_number = 3
  FALLBACK: none — if no image found for a scene_number, images=[] (black clip).

This guarantees that scene_description changes in prompts.json NEVER affect
which image is assigned to which scene.
"""

import json
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _seconds_to_mmss(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def _parse_duration(duration_str: str) -> int:
    parts = str(duration_str).strip().split(".")
    minutes = int(parts[0]) if parts and parts[0] else 0
    seconds = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return minutes * 60 + seconds


def _list_image_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    )


def _extract_scene_number(text: str) -> Optional[int]:
    """Extract leading scene number from a filename like 'scene_003_...'."""
    match = re.search(r"scene[_\-\s]*0*(\d+)", str(text).lower())
    return int(match.group(1)) if match else None


# ─────────────────────────────────────────────────────────────────────────────
# Build a scene_number → [image_path] index from all image folders
# ─────────────────────────────────────────────────────────────────────────────

def _build_image_index(image_folders: List[Path]) -> dict:
    """
    Returns {scene_number: [Path, ...]} for every image found across all folders.
    scene_number is extracted from the filename (e.g. scene_002_... → 2).
    Files whose names don't start with 'scene_N' are ignored.
    """
    index: dict[int, list] = {}
    for folder in image_folders:
        for img in _list_image_files(folder):
            num = _extract_scene_number(img.name)
            if num is not None:
                index.setdefault(num, []).append(img)
    return index


# ─────────────────────────────────────────────────────────────────────────────
# Core mapper
# ─────────────────────────────────────────────────────────────────────────────

def run_ai_mapper(
    config: dict,
    reset: bool = False,
    log: Callable[[str], None] = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path    = Path(config["base_path"])
    prompts_path = base_path / "output" / "prompts.json"
    mapping_path = base_path / "mapping.json"

    images_folder = config.get("images_folder", "")
    if images_folder and Path(images_folder).exists():
        # Explicit upload folder provided — use IT ONLY, ignore defaults
        image_folders: List[Path] = [Path(images_folder)]
        log(f"Using uploaded images folder: {images_folder}")
    else:
        # Fall back to default search paths
        image_folders = [
            base_path / "output" / "images",
            base_path / "assets"  / "images",
        ]
        log(f"No uploaded folder found, searching defaults: {[str(f) for f in image_folders]}")

    seconds_per_image = int(config.get("seconds_per_image", 7))
    audio_duration    = _parse_duration(str(config.get("audio_duration", "4.30")))

    if not prompts_path.exists():
        raise FileNotFoundError("prompts.json not found. Run Step 1 first.")

    if reset and mapping_path.exists():
        mapping_path.unlink()
        log("Reset: deleted old mapping.json")

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    if not prompts:
        raise ValueError("prompts.json is empty. Run Step 1 first.")

    # ── Build scene_number → [image] index ───────────────────────────────────
    image_index = _build_image_index(image_folders)
    total_found = sum(len(v) for v in image_index.values())
    log(f"Image index: {total_found} images across scenes {sorted(image_index.keys())}")

    if total_found == 0:
        raise ValueError(
            "No images found in any folder. "
            "Upload images whose filenames start with 'scene_NNN_...' "
            "then run this step again."
        )

    # ── Sort prompts by scene_number ascending ────────────────────────────────
    prompts = sorted(prompts, key=lambda s: int(s.get("scene_number", 0)))

    mapping  = []
    missing  = []
    current_start = 0
    total    = len(prompts)

    log(f"Mapping {total} scenes | {seconds_per_image}s per image | {audio_duration}s audio")

    for i, scene in enumerate(prompts, start=1):
        if current_start >= audio_duration:
            break

        scene_number = int(scene.get("scene_number", i))
        start_sec    = current_start
        end_sec      = min(current_start + seconds_per_image, audio_duration)

        # ── PRIMARY match: scene_number only ─────────────────────────────────
        matched_images: List[Path] = image_index.get(scene_number, [])

        if matched_images:
            # Use all images for this scene number (sorted by name)
            image_names = [p.name for p in sorted(matched_images)]
            log(f"  scene {scene_number:03d} → {image_names}")
        else:
            image_names = []
            missing.append(scene_number)
            log(f"  scene {scene_number:03d} → [NOT FOUND] (no file named scene_{scene_number:03d}_*)")

        mapping.append({
            "scene_number":    scene_number,
            "start":           _seconds_to_mmss(start_sec),
            "end":             _seconds_to_mmss(end_sec),
            "images":          image_names,
            "scene_description": scene.get("scene_description", ""),
            "label_text":      scene.get("label_text", ""),
        })
        current_start = end_sec

        if progress:
            progress(i, total)

    # ── Write mapping.json (sorted ascending by scene_number) ─────────────────
    mapping = sorted(mapping, key=lambda s: int(s["scene_number"]))

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    log(f"\nMapping saved → {mapping_path}")
    log(f"Scenes mapped: {len(mapping)} | Missing images: {len(missing)}")

    if missing:
        log(f"WARNING: no image found for scenes: {missing}")
    else:
        log("All scenes matched successfully by scene_number ✓")

    return mapping, missing
