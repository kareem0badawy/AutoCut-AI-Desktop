from moviepy.editor import *
from PIL import Image
import json
import os
import numpy as np

def load_config():
    with open("J:/Coding/Desktop/AutoCut/config.json", "r", encoding="utf-8-sig") as f:
        return json.load(f)

def time_to_seconds(t):
    parts = t.strip().split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0

def make_image_clip(img_path, duration, resolution=(1920, 1080)):
    img = Image.open(img_path).convert("RGB")
    img = img.resize(resolution, Image.LANCZOS)
    clip = ImageClip(np.array(img), duration=duration)
    clip = clip.fadein(0.5).fadeout(0.5)
    return clip

def build_video(mapping_path, audio_path, images_folder, output_path, resolution=(1920, 1080)):
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    all_clips = []
    print("???? ???? ???????...")

    for i, scene in enumerate(mapping):
        start = time_to_seconds(scene["start"])
        end = time_to_seconds(scene["end"])
        scene_duration = end - start
        images = scene["images"]
        per_image = scene_duration / len(images)

        print(f"  ???? {i+1}: {len(images)} ???? | ?????: {scene_duration} ?????")

        for img_name in images:
            img_path = os.path.join(images_folder, img_name)
            if not os.path.exists(img_path):
                print(f"  ???? ?? ??????: {img_name}")
                clip = ColorClip(size=resolution, color=(10,10,10), duration=per_image)
            else:
                clip = make_image_clip(img_path, per_image, resolution)
            all_clips.append(clip)

    print("???? ??? ????????...")
    final_video = concatenate_videoclips(all_clips, method="compose")

    print("???? ????? ?????...")
    audio = AudioFileClip(audio_path)

    if audio.duration < final_video.duration:
        final_video = final_video.subclip(0, audio.duration)
    else:
        audio = audio.subclip(0, final_video.duration)

    final = final_video.set_audio(audio)

    print(f"???? ????? ???????: {output_path}")
    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="ultrafast"
    )
    print("?? ???? ??????? ?????!")

if __name__ == "__main__":
    images_folder = "J:/Coding/Desktop/AutoCut/assets/images"

    audio_files = [f for f in os.listdir("J:/Coding/Desktop/AutoCut/assets/audio")
                   if f.lower().endswith(('.mp3', '.MP3', '.wav', '.WAV', '.m4a', '.M4A'))]

    if not audio_files:
        print("???? ??? ??? ?? ????? audio!")
    else:
        audio_path = f"J:/Coding/Desktop/AutoCut/assets/audio/{audio_files[0]}"
        print(f"?????: {audio_files[0]}")

        build_video(
            mapping_path="J:/Coding/Desktop/AutoCut/mapping.json",
            audio_path=audio_path,
            images_folder=images_folder,
            output_path="J:/Coding/Desktop/AutoCut/assets/output/final_video.mp4"
        )
