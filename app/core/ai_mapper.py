import json
import re
from pathlib import Path
from typing import Callable, List, Optional, Tuple

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


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
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS)


def _normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\.(jpg|jpeg|png|webp)$", "", text)
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_scene_number(text: str) -> Optional[int]:
    match = re.search(r"scene[_\-\s]*0*(\d+)", str(text).lower())
    return int(match.group(1)) if match else None


def _build_requested_names(scene: dict) -> List[str]:
    candidates = []
    for key in ("image", "image_name", "filename"):
        value = scene.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value.strip())
    images = scene.get("images", [])
    if isinstance(images, list):
        for img in images:
            if isinstance(img, str) and img.strip():
                candidates.append(img.strip())
    scene_number = scene.get("scene_number")
    if scene_number is not None:
        candidates.append(f"scene_{int(scene_number):03d}")
        desc = scene.get("scene_description", "")
        if desc:
            candidates.append(f"scene_{int(scene_number):03d}_{desc}")
    return candidates


def _find_image_for_scene(scene: dict, image_folders: List[Path]) -> Tuple[Optional[Path], Optional[str]]:
    scene_number = scene.get("scene_number")
    requested_names = _build_requested_names(scene)
    normalized_candidates = [_normalize_text(x) for x in requested_names if x]

    for folder in image_folders:
        files = _list_image_files(folder)
        if not files:
            continue
        if scene_number is not None:
            for file in files:
                if _extract_scene_number(file.name) == int(scene_number):
                    return file, f"scene_number match in {folder.name}"
        for requested in normalized_candidates:
            if not requested:
                continue
            for file in files:
                file_norm = _normalize_text(file.name)
                if file_norm == requested or file_norm.startswith(requested) or requested in file_norm:
                    return file, f"name match in {folder.name}"
    return None, None


def run_ai_mapper(
    config: dict,
    reset: bool = False,
    log: Callable[[str], None] = print,
    progress: Optional[Callable[[int, int], None]] = None,
):
    base_path = Path(config["base_path"])
    prompts_path = base_path / "output" / "prompts.json"
    mapping_path = base_path / "mapping.json"

    images_folder = config.get("images_folder", "")
    image_folders = [
        base_path / "output" / "images",
        base_path / "assets" / "images",
    ]
    if images_folder and Path(images_folder).exists():
        image_folders.insert(0, Path(images_folder))

    seconds_per_image = int(config.get("seconds_per_image", 7))
    audio_duration = _parse_duration(str(config.get("audio_duration", "4.30")))

    if not prompts_path.exists():
        raise FileNotFoundError(f"prompts.json not found. Run Step 1 first.")

    if reset and mapping_path.exists():
        mapping_path.unlink()
        log("Reset: deleted old mapping.json")

    with open(prompts_path, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    if not prompts:
        raise ValueError("No prompts found. Run Step 1 first.")

    total_images_found = sum(len(_list_image_files(f)) for f in image_folders)
    log(f"Found {total_images_found} images across {len(image_folders)} folders")

    if total_images_found == 0:
        raise ValueError(
            "No images found in any folder. Run Step 2 first or check your images folder."
        )

    mapping = []
    missing = []
    current_start = 0
    total = len(prompts)

    log(f"Mapping {total} scenes | {seconds_per_image}s per image | {audio_duration}s audio")

    for i, scene in enumerate(prompts, start=1):
        if current_start >= audio_duration:
            break

        start_sec = current_start
        end_sec = min(current_start + seconds_per_image, audio_duration)

        image_path, match_reason = _find_image_for_scene(scene, image_folders)

        if image_path:
            images = [image_path.name]
            log(f"  scene {i:03d} -> {image_path.name}")
        else:
            requested = _build_requested_names(scene)
            log(f"  scene {i:03d} -> [NOT FOUND] candidates: {requested[:2]}")
            images = []
            missing.append({"scene_number": scene.get("scene_number", i), "candidates": requested})

        mapping.append({
            "scene_number": scene.get("scene_number", i),
            "start": _seconds_to_mmss(start_sec),
            "end": _seconds_to_mmss(end_sec),
            "images": images,
            "scene_description": scene.get("scene_description", ""),
            "label_text": scene.get("label_text", ""),
        })
        current_start = end_sec

        if progress:
            progress(i, total)

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    log(f"\nMapping saved: {mapping_path}")
    log(f"Total scenes mapped: {len(mapping)}")

    if missing:
        log(f"WARNING: {len(missing)} scenes have no image:")
        for item in missing:
            log(f"  - scene {item['scene_number']}: {item['candidates'][:1]}")
    else:
        log("All scenes mapped successfully!")

    return mapping, missing
