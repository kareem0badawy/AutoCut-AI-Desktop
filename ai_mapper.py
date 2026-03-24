import json
import math
import re
from pathlib import Path
from typing import List, Optional, Tuple

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def parse_duration(duration_str: str) -> int:
    parts = str(duration_str).strip().split(".")
    minutes = int(parts[0]) if parts and parts[0] else 0
    seconds = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    return minutes * 60 + seconds


def seconds_to_mmss(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def list_image_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        [
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
    )


def normalize_text(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"\.(jpg|jpeg|png|webp)$", "", text)
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_scene_number(text: str) -> Optional[int]:
    if not text:
        return None
    match = re.search(r"scene[_\-\s]*0*(\d+)", str(text).lower())
    if match:
        return int(match.group(1))
    return None


def build_requested_names(scene: dict) -> List[str]:
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
    if scene_number is not None and desc:
        candidates.append(f"scene_{int(scene_number):03d}_{desc}")

    return candidates


def debug_print_folders(image_folders: List[Path]):
    print("\n========== AI MAPPER DEBUG ==========")
    for folder in image_folders:
        files = list_image_files(folder)
        print(f"[DEBUG] folder: {folder} | exists={folder.exists()} | image_count={len(files)}")
        if files:
            preview = ", ".join(f.name for f in files[:5])
            print(f"        preview: {preview}")
    print("=====================================\n")


def find_image_for_scene(scene: dict, image_folders: List[Path]) -> Tuple[Optional[Path], Optional[str]]:
    scene_number = scene.get("scene_number")
    requested_names = build_requested_names(scene)
    normalized_candidates = [normalize_text(x) for x in requested_names if x]

    for folder in image_folders:
        files = list_image_files(folder)
        if not files:
            continue

        # 1) scene number match first
        if scene_number is not None:
            for file in files:
                file_scene_num = extract_scene_number(file.name)
                if file_scene_num == int(scene_number):
                    return file, f"scene_number match in {folder}"

        # 2) exact / contains normalized name
        for requested in normalized_candidates:
            if not requested:
                continue
            for file in files:
                file_norm = normalize_text(file.name)
                if file_norm == requested:
                    return file, f"normalized exact match in {folder}"
                if requested and file_norm.startswith(requested):
                    return file, f"normalized startswith match in {folder}"
                if requested and requested in file_norm:
                    return file, f"normalized contains match in {folder}"

    return None, None


def build_mapping(prompts: List[dict], seconds_per_image: int, audio_duration: int, image_folders: List[Path]):
    mapping = []
    current_start = 0
    missing = []

    total_scenes = len(prompts)
    print(f"[DEBUG] total prompts loaded: {total_scenes}")
    print(f"[DEBUG] seconds_per_image from config: {seconds_per_image}")
    print(f"[DEBUG] audio_duration from config: {audio_duration}s")

    for i, scene in enumerate(prompts, start=1):
        if current_start >= audio_duration:
            print(f"[DEBUG] stopping at scene {i} because timeline reached audio duration")
            break

        start_sec = current_start
        end_sec = min(current_start + seconds_per_image, audio_duration)

        image_path, match_reason = find_image_for_scene(scene, image_folders)

        if image_path:
            images = [image_path.name]
            print(f"✅ scene {i:03d} -> {image_path.name}")
            print(f"   [MATCH] {match_reason}")
        else:
            scene_num = scene.get("scene_number", i)
            requested = build_requested_names(scene)
            print(f"⚠️ scene {i:03d} image not found")
            print(f"   requested candidates: {requested}")
            images = []
            missing.append(
                {
                    "scene_number": scene_num,
                    "requested_candidates": requested,
                }
            )

        mapping.append(
            {
                "scene_number": scene.get("scene_number", i),
                "start": seconds_to_mmss(start_sec),
                "end": seconds_to_mmss(end_sec),
                "images": images,
                "scene_description": scene.get("scene_description", ""),
                "label_text": scene.get("label_text", ""),
            }
        )

        current_start = end_sec

    return mapping, missing


def main():
    config = load_json(CONFIG_PATH)
    base_path = Path(config["base_path"])

    prompts_path = base_path / "output" / "prompts.json"
    mapping_path = base_path / "mapping.json"

    image_folders = [
        base_path / "source" / "images",
        base_path / "output" / "images",
        base_path / "assets" / "images",
    ]

    seconds_per_image = int(config.get("seconds_per_image", 10))
    audio_duration = parse_duration(config.get("audio_duration", "1.00"))

    if not prompts_path.exists():
        raise FileNotFoundError(f"prompts.json not found: {prompts_path}")

    debug_print_folders(image_folders)

    prompts = load_json(prompts_path)
    if not prompts:
        raise ValueError(f"No prompts found in {prompts_path}")

    total_images_found = sum(len(list_image_files(folder)) for folder in image_folders)
    if total_images_found == 0:
        raise ValueError(
            "No images found in any configured folder:\n"
            + "\n".join(str(folder) for folder in image_folders)
        )

    mapping, missing = build_mapping(
        prompts=prompts,
        seconds_per_image=seconds_per_image,
        audio_duration=audio_duration,
        image_folders=image_folders,
    )

    save_json(mapping, mapping_path)

    print(f"\n💾 mapping saved to: {mapping_path}")
    print(f"✅ total mapped scenes: {len(mapping)}")

    if missing:
        print("\n⚠️ scenes with missing images:")
        for item in missing:
            print(f" - scene {item['scene_number']}: {item['requested_candidates']}")
    else:
        print("\n✅ all scenes mapped successfully")


if __name__ == "__main__":
    main()