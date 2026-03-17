from groq import Groq
import json
import os
import math
import time
import argparse
import re

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def load_txt(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().strip()

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_txt(text, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def parse_duration(duration_str):
    parts = str(duration_str).split(".")
    minutes = int(parts[0])
    seconds = int(parts[1]) if len(parts) > 1 else 0
    return (minutes * 60) + seconds

def clean_and_parse_json(raw):
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

def generate_batch(client, script_chunk, style, batch_num, total_batches, scenes_in_batch, seconds_per_image, template):
    prompt = template.format(
        batch_num         = batch_num,
        total_batches     = total_batches,
        scenes_in_batch   = scenes_in_batch,
        seconds_per_image = seconds_per_image,
        script_chunk      = script_chunk,
        style_lock        = style["style_lock"],
        mood              = style["mood"],
        negative_prompt   = style["negative_prompt"],
    )
    max_tokens = min(scenes_in_batch * 500, 8000)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens
            )
            raw = response.choices[0].message.content.strip()
            result = clean_and_parse_json(raw)
            print(f"  ✅ تم parse الـ JSON — {len(result)} مشهد")
            return result
        except json.JSONDecodeError as e:
            print(f"  ⚠️ محاولة {attempt+1}: JSON Error — {e}")
            if attempt < 2:
                print(f"  🔄 بيحاول تاني...")
                time.sleep(3)
            else:
                print(f"  ❌ فشل الـ parse 3 مرات، batch ده هيتعمل skip")
                return []
        except Exception as e:
            print(f"  ⚠️ محاولة {attempt+1}: Error — {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                return []

def generate_prompts(limit=None, reset=False):
    config = load_json(CONFIG_PATH)
    BASE   = config["base_path"]
    style  = load_json(f"{BASE}/style_config.json")
    script = load_txt(f"{BASE}/script.txt")
    template = load_txt(f"{BASE}/prompts_template.txt")

    seconds_per_image = config["seconds_per_image"]
    audio_duration    = parse_duration(config["audio_duration"])
    total_images      = math.ceil(audio_duration / seconds_per_image)

    # لو في limit، نحسب عدد المشاهد منه
    if limit:
        total_images = min(limit, total_images)
        print(f"🎯 Limit مفعّل — هيتولد {total_images} مشهد بس")

    scenes_per_batch  = config["scenes_per_batch"]
    total_batches     = math.ceil(total_images / scenes_per_batch)

    print(f"مدة الصوت: {audio_duration} ثانية")
    print(f"صورة كل: {seconds_per_image} ثواني")
    print(f"إجمالي الصور المطلوبة: {total_images} صورة")
    print(f"عدد الـ batches: {total_batches}")
    print("-" * 40)

    output_path = f"{BASE}/output/prompts.json"
    os.makedirs(f"{BASE}/output", exist_ok=True)

    # Reset — يمسح الملف ويبدأ من الأول
    if reset:
        if os.path.exists(output_path):
            os.remove(output_path)
            print("🗑️  تم مسح الملف القديم — بيبدأ من الأول")
        all_scenes = []
        resume_from = 0
    # Resume — يكمل من آخر نقطة
    elif os.path.exists(output_path):
        all_scenes = load_json(output_path)
        resume_from = len(all_scenes)
        if resume_from >= total_images:
            print(f"✅ الملف مكتمل بالفعل ({resume_from} مشهد) — مفيش حاجة تتعمل")
            return
        print(f"⏩ Resume من مشهد {resume_from + 1}")
    else:
        all_scenes = []
        resume_from = 0

    client = Groq(api_key=config["groq_api_key"])
    words = script.split()
    words_per_batch = math.ceil(len(words) / total_batches)
    scene_counter = resume_from + 1

    for i in range(total_batches):
        batch_start_scene = i * scenes_per_batch

        # Skip الـ batches المكتملة
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
            all_scenes.append(s)
            scene_counter += 1

        # حفظ بعد كل batch
        save_json(all_scenes, output_path)
        print(f"  💾 حُفظ {len(all_scenes)}/{total_images} مشهد")

        if i < total_batches - 1 and (total_images - len(all_scenes)) > 0:
            print("انتظار 4 ثواني...")
            time.sleep(4)

    # حفظ الـ txt
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

    save_txt(txt, f"{BASE}/output/prompts_output.txt")
    print(f"\n✅ تم! عدد المشاهد الفعلي: {len(all_scenes)}")
    print(f"📁 الملفات في: {BASE}/output/")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="عدد المشاهد المطلوبة (بدون limit بيعمل الكل)")
    parser.add_argument("--reset", action="store_true",
                        help="يمسح الملف القديم ويبدأ من الأول")
    args = parser.parse_args()
    generate_prompts(limit=args.limit, reset=args.reset)