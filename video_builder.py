import json
import difflib
from pathlib import Path
from typing import Optional, List, Tuple

import numpy as np
from moviepy.editor import AudioFileClip, ColorClip, ImageClip, concatenate_videoclips
from PIL import Image

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def parse_resolution(value: str):
    text = str(value).lower().strip()
    if "x" not in text:
        return 1920, 1080
    width, height = text.split("x", 1)
    return int(width), int(height)


def time_to_seconds(t: str) -> int:
    parts = [int(p) for p in t.strip().split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def list_image_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        [
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
        ]
    )


def find_first_audio(audio_folder: Path) -> Path:
    if not audio_folder.exists():
        raise FileNotFoundError(f"Audio folder not found: {audio_folder}")

    for file in sorted(audio_folder.iterdir()):
        if file.is_file() and file.suffix.lower() in {".mp3", ".wav", ".m4a"}:
            return file

    raise FileNotFoundError(f"No audio file found in: {audio_folder}")


def make_image_clip(img_path: Path, duration: float, resolution=(1920, 1080), fade_duration=0.5):
    img = Image.open(img_path).convert("RGB")
    img = img.resize(resolution, Image.LANCZOS)
    clip = ImageClip(np.array(img), duration=duration)
    if fade_duration > 0 and duration > fade_duration * 2:
        clip = clip.fadein(fade_duration).fadeout(fade_duration)
    return clip


def get_close_matches(requested_name: str, files: List[Path], limit: int = 5) -> List[str]:
    file_names = [f.name for f in files]
    requested_stem = Path(requested_name).stem
    file_stems = [f.stem for f in files]

    matches_by_name = difflib.get_close_matches(requested_name, file_names, n=limit, cutoff=0.35)
    matches_by_stem = difflib.get_close_matches(requested_stem, file_stems, n=limit, cutoff=0.35)

    merged = []
    seen = set()

    for item in matches_by_name:
        if item not in seen:
            seen.add(item)
            merged.append(item)

    for stem in matches_by_stem:
        for f in files:
            if f.stem == stem and f.name not in seen:
                seen.add(f.name)
                merged.append(f.name)
                break

    return merged[:limit]


def find_matching_image_in_folder(images_folder: Path, requested_name: str, verbose: bool = False) -> Optional[Path]:
    if not images_folder.exists():
        if verbose:
            print(f"      [DEBUG] folder not found: {images_folder}")
        return None

    files = list_image_files(images_folder)

    if verbose:
        print(f"      [DEBUG] searching in: {images_folder}")
        print(f"      [DEBUG] image files count: {len(files)}")

    direct = images_folder / requested_name
    if direct.exists():
        if verbose:
            print(f"      [MATCH] direct name match: {direct.name}")
        return direct

    requested_lower = requested_name.lower()
    requested_stem = Path(requested_name).stem.lower()

    for file in files:
        if file.name.lower() == requested_lower:
            if verbose:
                print(f"      [MATCH] case-insensitive file name match: {file.name}")
            return file

    for file in files:
        if file.stem.lower() == requested_stem:
            if verbose:
                print(f"      [MATCH] stem match: {file.name}")
            return file

    for file in files:
        if requested_stem and file.stem.lower().startswith(requested_stem):
            if verbose:
                print(f"      [MATCH] file stem startswith requested stem: {file.name}")
            return file

    for file in files:
        if requested_stem and requested_stem.startswith(file.stem.lower()):
            if verbose:
                print(f"      [MATCH] requested stem startswith file stem: {file.name}")
            return file

    close_matches = get_close_matches(requested_name, files, limit=5)
    if verbose:
        print(f"      [MISS] no exact/stem match for: {requested_name}")
        if close_matches:
            print("      [DEBUG] closest candidates:")
            for candidate in close_matches:
                print(f"         - {candidate}")
        else:
            print("      [DEBUG] no close candidates found")

    return None


def find_matching_image(images_folders: List[Path], requested_name: str, verbose: bool = False) -> Tuple[Optional[Path], Optional[Path]]:
    for folder in images_folders:
        found = find_matching_image_in_folder(folder, requested_name, verbose=verbose)
        if found:
            return found, folder
    return None, None


def debug_print_environment(mapping_path: Path, audio_folder: Path, images_folders: List[Path], output_path: Path):
    print("\n========== DEBUG ENV ==========")
    print(f"[DEBUG] mapping path : {mapping_path} | exists={mapping_path.exists()}")
    print(f"[DEBUG] audio folder : {audio_folder} | exists={audio_folder.exists()}")
    print(f"[DEBUG] output path  : {output_path}")

    for folder in images_folders:
        exists = folder.exists()
        files = list_image_files(folder) if exists else []
        print(f"[DEBUG] images folder: {folder} | exists={exists} | image_count={len(files)}")
        if files:
            preview = ", ".join(f.name for f in files[:5])
            print(f"         preview: {preview}")

    print("===============================\n")


def build_video(
    mapping_path: Path,
    audio_path: Path,
    images_folders: List[Path],
    output_path: Path,
    resolution=(1920, 1080),
    fps=24,
    fade_duration=0.5,
):
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    all_clips = []
    missing_images = []

    print("🎬 building video clips...")
    print(f"[DEBUG] loaded scenes from mapping: {len(mapping)}")
    print(f"[DEBUG] using audio: {audio_path}")

    for i, scene in enumerate(mapping, start=1):
        start = time_to_seconds(scene["start"])
        end = time_to_seconds(scene["end"])
        scene_duration = max(1, end - start)
        images = scene.get("images", [])

        if not images:
            print(f"⚠️ scene {i} has no images, using black clip | duration: {scene_duration}s")
            clip = ColorClip(size=resolution, color=(10, 10, 10), duration=scene_duration)
            all_clips.append(clip)
            continue

        per_image = scene_duration / len(images)
        print(f"\n  • scene {i}: {len(images)} image(s) | duration: {scene_duration}s | per_image={per_image:.2f}s")

        for img_name in images:
            print(f"    [REQUESTED] {img_name}")
            img_path, matched_folder = find_matching_image(images_folders, img_name, verbose=True)

            if not img_path:
                print(f"    ⚠️ missing image after searching all folders: {img_name}")
                missing_images.append(img_name)
                clip = ColorClip(size=resolution, color=(10, 10, 10), duration=per_image)
            else:
                print(f"    ✅ resolved to: {img_path.name}")
                print(f"       folder: {matched_folder}")
                clip = make_image_clip(img_path, per_image, resolution, fade_duration)

            all_clips.append(clip)

    if not all_clips:
        raise ValueError("No clips were built. Check mapping.json and images folders.")

    final_video = concatenate_videoclips(all_clips, method="compose")
    audio = AudioFileClip(str(audio_path))

    if audio.duration < final_video.duration:
        final_video = final_video.subclip(0, audio.duration)
    else:
        audio = audio.subclip(0, final_video.duration)

    final = final_video.set_audio(audio)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n🎧 audio: {audio_path.name}")
    print(f"💾 writing final video: {output_path}")
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast",
    )

    if missing_images:
        print("\n⚠️ missing images used as black clips:")
        for name in missing_images:
            print(f" - {name}")

    print("✅ final video created successfully")


def main():
    config = load_config()
    base_path = Path(config["base_path"])
    resolution = parse_resolution(config.get("output_resolution", "1920x1080"))
    fps = int(config.get("fps", 24))
    fade_duration = float(config.get("transition_duration", 0.5))

    mapping_path = base_path / "mapping.json"
    audio_folder = base_path / "assets" / "audio"
    images_folders = [
        base_path / "source" / "images",
        base_path / "output" / "images",
        base_path / "assets" / "images",
    ]
    output_path = base_path / "assets" / "output" / "final_video.mp4"

    debug_print_environment(mapping_path, audio_folder, images_folders, output_path)

    audio_path = find_first_audio(audio_folder)
    build_video(
        mapping_path=mapping_path,
        audio_path=audio_path,
        images_folders=images_folders,
        output_path=output_path,
        resolution=resolution,
        fps=fps,
        fade_duration=fade_duration,
    )


if __name__ == "__main__":
    main()
    print("\n✅ done")