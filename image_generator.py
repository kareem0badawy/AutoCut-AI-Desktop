import json
import os
import time
from huggingface_hub import InferenceClient

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

TEST_MODE = True
TEST_COUNT = 5

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def generate_image(client, prompt, width, height, scene_num):
    for attempt in range(3):
        try:
            image = client.text_to_image(
                prompt=prompt,
                model="black-forest-labs/FLUX.1-schnell",
                width=width,
                height=height,
                num_inference_steps=4,
                guidance_scale=0.0
            )
            return image
        except Exception as e:
            err = str(e)
            if "loading" in err.lower() or "503" in err:
                print(f"  الموديل بيتحمل، انتظار 20 ثانية...")
                time.sleep(20)
            elif "429" in err:
                print(f"  Rate limit، انتظار 15 ثانية...")
                time.sleep(15)
            else:
                print(f"  محاولة {attempt+1} فشلت: {err[:100]}")
                time.sleep(5)
    return None

def generate_prompts(limit=None, reset=False):
    config = load_json(CONFIG_PATH)
    BASE   = config["base_path"]
    style  = load_json(f"{BASE}/style_config.json")
    script = load_txt(f"{BASE}/script.txt")
    template = load_txt(f"{BASE}/prompts_template.txt")

    seconds_per_image = config["seconds_per_image"]
    audio_duration    = parse_duration(config["audio_duration"])
    total_images      = math.ceil(audio_duration / seconds_per_image)
    scenes_per_batch  = config["scenes_per_batch"]
    total_batches     = math.ceil(total_images / scenes_per_batch)

    print(f"مدة الصوت: {audio_duration} ثانية")
    print(f"صورة كل: {seconds_per_image} ثواني")
    print(f"إجمالي الصور: {total_images} صورة")
    print(f"عدد الـ batches: {total_batches}")
    print("-" * 40)

    if limit:
        total_images  = min(limit, total_images)
        total_batches = math.ceil(total_images / scenes_per_batch)
        print(f"🎯 Limit مفعّل — هيتولد {total_images} مشهد بس")
        print(f"   عدد الـ batches بعد الـ limit: {total_batches}")
        print("-" * 40)

    # ── Resume من آخر مشهد محفوظ ──
    output_path = f"{BASE}/output/prompts.json"
    os.makedirs(f"{BASE}/output", exist_ok=True)

    if reset and os.path.exists(output_path):
            os.remove(output_path)
            print("🗑️ تم مسح الملف القديم")

    if os.path.exists(output_path):
        try:
            all_scenes  = load_json(output_path)
            resume_from = len(all_scenes)
            print(f"⏩ ملف موجود — Resume من مشهد {resume_from + 1}")
        except (json.JSONDecodeError, ValueError):
            print("⚠️ ملف تالف — هيبدأ من الأول")
            all_scenes  = []
            resume_from = 0
    else:
        all_scenes  = []
        resume_from = 0

    client = Groq(api_key=config["groq_api_key"])

    words           = script.split()
    words_per_batch = math.ceil(len(words) / total_batches)
    scene_counter   = resume_from + 1

    for i in range(total_batches):
        batch_start_scene = i * scenes_per_batch

        if batch_start_scene < resume_from:
            print(f"Batch {i+1}/{total_batches} — ✅ موجود، skip")
            continue

        start_word = i * words_per_batch
        end_word   = min((i + 1) * words_per_batch, len(words))
        chunk      = " ".join(words[start_word:end_word])

        remaining  = total_images - len(all_scenes)
        if remaining <= 0:
            break
        batch_size = min(scenes_per_batch, remaining)

        print(f"Batch {i+1}/{total_batches} — {batch_size} مشاهد...")
        batch = generate_batch(client, chunk, style, i+1, total_batches, batch_size, seconds_per_image, template)

        for s in batch:
            s["scene_number"] = scene_counter
            if "scene_description" in s:
                desc = s["scene_description"]
                desc = re.sub(
                    r'^(This image|This scene|The image|The scene)\s+(shows|represents|depicts|is|captures|features|presents)\s+',
                    '', desc, flags=re.IGNORECASE
                ).strip()
                desc = re.sub(r"[',\.\-\(\)\[\]\"!?;:]", " ", desc)
                desc = re.sub(r"\s+", " ", desc).strip()
                if len(desc) > 100:
                    desc = desc[:100].rsplit(' ', 1)[0].strip()
                if desc:
                    desc = desc[0].upper() + desc[1:]
                s["scene_description"] = desc
            all_scenes.append(s)
            scene_counter += 1

        save_json(all_scenes, output_path)
        print(f"  💾 حُفظ {len(all_scenes)}/{total_images} مشهد")

        if i < total_batches - 1 and remaining - batch_size > 0:
            print("انتظار 4 ثواني...")
            time.sleep(4)

    txt  = "=" * 60 + "\n"
    txt += "AUTOCUT - PROMPTS OUTPUT\n"
    txt += f"Total Scenes: {len(all_scenes)} | Seconds per image: {seconds_per_image}\n"
    txt += "=" * 60 + "\n\n"
    for s in all_scenes:
        txt += f"SCENE {s['scene_number']}\n"
        txt += f"Description: {s['scene_description']}\n"
        txt += "-" * 40 + "\n"
        txt += f"MAIN PROMPT:\n{s['main_prompt']}\n\n"
        txt += f"LABEL TEXT: {s['label_text']}\n"
        txt += f"SECONDARY LABELS: {', '.join(s['secondary_labels'])}\n"
        txt += f"\nNEGATIVE PROMPT:\n{s['negative_prompt']}\n"
        txt += "=" * 60 + "\n\n"

    save_txt(txt, f"{BASE}/output/prompts_output.txt")
    print(f"\n✅ تم! عدد المشاهد الفعلي: {len(all_scenes)}")
    print(f"الملفات في: {BASE}/output/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    generate_prompts(limit=args.limit, reset=args.reset)