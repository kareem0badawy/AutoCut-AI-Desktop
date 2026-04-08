from groq import Groq
import json
import os
import time
import argparse
import re

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCRIPT_PATH  = r"J:\Coding\Desktop\AutoCut\script.txt"
OUTPUT_DIR   = r"J:\Coding\Desktop\AutoCut\thumbnails_output"
# MODEL        = "llama-3.3-70b-versatile"
MODEL        = "llama-3.1-8b-instant"

THUMBNAIL_TEMPLATE = """
You are a thumbnail prompt engineer. Your ONLY job is to replicate the exact style of the reference prompts below.

══════════════════════════════════════════
REFERENCE PROMPTS — STUDY AND REPLICATE EXACTLY
══════════════════════════════════════════

REFERENCE 1:
Editorial collage illustration with a clear focal point. A human hand in watercolor style tightly holding a gold coin, but fine cracks are forming across the coin while being held.
Background is aged parchment with tonal harmony, slightly darker and less saturated, with soft depth. Minimal collage elements.
Soft lighting, gentle shadows, gold slightly richer.
Large bold text "HOLDING WHAT?" in vintage serif font, off-white with dark shadow, placed clearly on a light paper strip.
Clean composition, subtle tension, symbolic meaning about control and loss.

REFERENCE 2:
Editorial collage illustration with a clear focal point. A human hand in watercolor style holding multiple gold coins, but all except one are faded or disappearing, leaving only a single solid coin.
Background is aged brown parchment texture with soft tonal depth, slightly darker and less saturated, with subtle texture and minimal collage elements.
Soft lighting, gentle shadows, the remaining gold coin slightly more vivid to create focus.
A large bold text reading "LAST ONE?" in a heavy vintage serif font, off-white with dark shadow, placed on a light paper strip with a small deep red accent.
Clean composition, emotional tension, strong focus, curiosity-driven.

REFERENCE 3:
Editorial collage illustration with a clear focal point. A human hand in watercolor style trying to hold a stack of gold coins, but several coins are slipping and falling downward.
Background is aged brown parchment texture with soft depth gradient, slightly darker and desaturated, with minimal collage elements.
Soft lighting, smooth shading, gold slightly more saturated for contrast.
A large bold text reading "CAN'T HOLD?" in a heavy vintage serif font, off-white with dark shadow, placed on a light paper strip with a small deep red accent.
Clean composition, motion implied, tension and loss, strong readability.

REFERENCE 4:
Editorial collage illustration with a clear focal point. Two identical gold coins placed side by side, but one coin has subtle cracks and faded details while the other appears solid and intact.
Background is aged brown parchment texture with tonal harmony, slightly darker and softly desaturated, with subtle depth and minimal collage elements.
Soft directional lighting, smooth shading, solid coin slightly richer in tone.
A large bold text reading "WHICH ONE?" in a heavy vintage serif font, off-white with subtle dark shadow, placed clearly on a torn paper strip with a small deep red accent.
Clean composition, subtle contrast, curiosity-driven, strong visual comparison.

REFERENCE 5:
Editorial collage illustration with a clear focal point. A large gold bar in watercolor style appears massive and solid, but a small visible crack runs across it, suggesting weakness.
Background is aged brown parchment texture with tonal harmony, slightly darker and softly desaturated, with a gentle center light and darker edges for depth. Minimal collage elements (faint paper scraps, subtle ink marks).
Soft directional lighting, smooth shading, gold slightly richer than surroundings.
A large bold text reading "TOO BIG?" in a heavy vintage serif font, off-white with subtle dark shadow, placed clearly on a torn paper strip with a small deep red accent.
Clean composition, subtle tension, symbolic fragility, strong readability.

REFERENCE 6:
Editorial collage illustration with a clear focal point. A bag filled with gold coins appears full, but the opening reveals that most coins are only near the surface while inside is empty.
Background is aged brown parchment texture with tonal harmony, slightly darker edges and soft center brightness. Minimal collage elements.
Soft directional lighting, smooth shading, gold slightly richer.
A large bold text reading "FULL?" in a heavy vintage serif font, off-white with subtle shadow, placed clearly on a torn paper strip with a small deep red accent.
Clean composition, illusion of abundance, strong curiosity.

REFERENCE 7:
Editorial collage illustration with a clear focal point. A gold coin in watercolor style breaking into multiple fragments mid-air, with pieces separating but still close together.
Background is aged brown parchment with soft tonal depth, slightly darker and less saturated, with minimal collage elements.
Soft lighting, gentle shadows, gold slightly more saturated for visibility.
A large bold text reading "FALLING?" in a heavy vintage serif font, off-white with dark shadow, placed on a light paper strip with a small deep red accent.
Clean composition, frozen motion, sense of collapse, curiosity-driven.

══════════════════════════════════════════
STYLE DNA — NEVER CHANGE THESE
══════════════════════════════════════════

These are fixed across ALL scripts and ALL prompts:

✓ Style: Editorial collage illustration, watercolor style
✓ Background: Aged brown parchment texture, slightly darker edges, lighter center
✓ Lighting: Soft directional lighting, gentle shadows, smooth shading
✓ Focal subject: Slightly more saturated/vivid than background
✓ Text: Heavy vintage serif font, off-white, dark shadow, on torn/light paper strip
✓ Red accent: Small deep red element near text strip
✓ Composition: Clean, single focal point, minimal collage elements
✓ Contradiction: Every subject must have ONE visual tension built in

✗ NEVER: photorealistic, 3D, CGI, engraving, comic, anime
✗ NEVER: bright colors, clutter, multiple unrelated elements
✗ NEVER: complex scenes, multiple focal points

══════════════════════════════════════════
SUBJECT EXTRACTION — READ SCRIPT FIRST
══════════════════════════════════════════

Before generating prompts, extract from the script:

1. CORE OBJECTS: What physical objects are mentioned or implied?
   → These become your focal subjects
   → Must be concrete and visual (a bulb, a coin, a house, a map, a contract)

2. CORE TENSION: What is the central contradiction or hidden truth?
   → This becomes your visual contradiction (crack, fade, shadow, peel, break)

3. CORE EMOTION: What feeling should the viewer have?
   → Doubt / Curiosity / Fear / Surprise / Warning

Rules for subject selection:
✓ Must be a single concrete object OR hand holding an object OR two identical objects
✓ Must come directly from the script — not invented
✓ Must carry the script's tension visually without explanation
✗ NO abstract concepts as subjects
✗ NO people, faces, or scenes
✗ NO objects not connected to the script

══════════════════════════════════════════
STRUCTURE RULES — MANDATORY
══════════════════════════════════════════

Every prompt MUST follow this exact 5-line structure:

LINE 1 — Subject only:
"Editorial collage illustration with a clear focal point. [subject extracted from script in watercolor style] + [ONE contradiction: crack / fading / slipping / breaking / empty inside / shadow reveals truth / peeling to reveal]."
→ Subject must come from the script
→ NO background here. NO lighting here. NO text here.
→ ONE clean sentence only.

LINE 2 — Background only:
"Background is aged brown parchment texture with [tonal description], [darkness/depth note]. [Collage elements: Minimal collage elements / faint paper scraps, subtle ink marks]."
→ Background description ONLY. Nothing else.

LINE 3 — Lighting and subject tone only:
"[Soft/Directional] lighting, [shadow note], [subject tone note — slightly richer/more vivid than background]."
→ ONE sentence. Lighting and tone ONLY.

LINE 4 — Text element only:
"A large bold text reading \"[2-3 WORD HOOK?]\" in a heavy vintage serif font, off-white with dark shadow, placed clearly on a [light/torn] paper strip with a small deep red accent."
→ Text description ONLY. Nothing else.

LINE 5 — Closing descriptors only:
"Clean composition, [emotional/visual note], [second note], [optional third note]."
→ 2 to 3 short closing descriptors. NO new visual elements here.

══════════════════════════════════════════
SECONDARY ELEMENTS — CONTROLLED
══════════════════════════════════════════

Number of secondary elements to include in LINE 1: {num_elements}

0 → Pure subject, no supporting elements.
1 → ONE secondary element that adds tension.
2 → TWO secondary elements that build the story.
3 → THREE secondary elements maximum.

Rule: Secondary elements stay smaller, less saturated, less defined than the focal subject.
All secondary elements belong in LINE 1 ONLY.

══════════════════════════════════════════
HOOK TEXT RULES
══════════════════════════════════════════

- 2 to 3 words maximum
- Must be a curiosity-gap question
- Must relate directly to the visual contradiction AND the script's core idea
- Short, punchy, creates immediate tension or doubt
- Examples of good hooks: "HOLDING WHAT?", "LAST ONE?", "CAN'T HOLD?", "WHICH ONE?", "TOO BIG?", "FULL?", "FALLING?"

══════════════════════════════════════════
YOUR TASK
══════════════════════════════════════════

Step 1 — Analyze the script:
Extract the core objects, core tension, and core emotion before generating anything.

Step 2 — Generate exactly {num_thumbnails} prompts for this script:
\"\"\"{script}\"\"\"

Rules:
- Each prompt must represent a DIFFERENT core idea from the script
- Follow the 5-line structure exactly — no deviation
- Subjects must come from the script — not invented
- Hook text must be 2-3 words, curiosity-gap question
- No repetition between prompts

Avoid repeating:
{previous_thumbnails}

══════════════════════════════════════════
OUTPUT — JSON ONLY — NO EXTRA TEXT
══════════════════════════════════════════
[
  {{
    "number": 1,
    "script_analysis": {{
      "core_objects": ["object 1", "object 2"],
      "core_tension": "one sentence",
      "core_emotion": "one word"
    }},
    "pattern": "A/B/C/D/E",
    "concept": "one sentence describing the visual contradiction",
    "focal_subject": "the ONE main element — must come from script",
    "secondary_elements": ["element 1", "element 2"],
    "prompt_for_flow": "Editorial collage illustration with a clear focal point. [LINE 1].\\nBackground is aged brown parchment texture with [tonal description], [depth note]. [Collage elements note].\\n[Lighting], [shadow note], [subject tone note].\\nA large bold text reading \\"[2-3 WORD HOOK?]\\" in a heavy vintage serif font, off-white with dark shadow, placed on a light paper strip with a small deep red accent.\\nClean composition, [emotional note], [visual quality note].",
    "negative_prompt": "photorealistic, 3D, CGI, engraving, comic, anime, flat watercolor, low contrast, clutter, tiny subject, empty background, unreadable text, bright colors",
    "suggested_title": "MAX 4 WORDS",
    "hook": "why this thumbnail earns the click"
  }}
]
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_script(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read().strip()

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

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
        try:
            return json.loads(raw)
        except:
            return []

def build_previous_summary(all_thumbnails):
    if not all_thumbnails:
        return "None yet."
    lines = []
    for t in all_thumbnails:
        lines.append(
            f"  #{t.get('number','?')} [{t.get('pattern','')}]: {t.get('concept','')}"
        )
    return "\n".join(lines)

def export_txt(all_thumbnails, path):
    sep = "=" * 60
    lines = [
        sep,
        "THUMBNAIL PROMPTS — READY FOR GOOGLE FLOW",
        f"Total: {len(all_thumbnails)} thumbnails",
        sep, ""
    ]
    for t in all_thumbnails:
        lines += [
            f"IMAGE #{t.get('number','?')} | Pattern: {t.get('pattern','')}",
            f"Title   : {t.get('suggested_title','')}",
            f"Concept : {t.get('concept','')}",
            f"Hook    : {t.get('hook','')}",
            "-" * 40,
            t.get('prompt_for_flow', '').strip('"'),
            sep, ""
        ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def analyze_script(client, script):
    prompt = """
You are a video content analyst. Read this script carefully and extract the most powerful moments that would make high-CTR thumbnails.

For each moment, identify:
- The core tension or contradiction
- Why a viewer would feel compelled to click
- What single visual could represent it

Extract exactly 8 moments, each with a DIFFERENT visual pattern. Distribute evenly:
- Patterns A (hand holding): moments 1, 5, 9, 13, 17
- Patterns B (single object): moments 2, 6, 10, 14, 18
- Patterns C (illusion/bag/safe): moments 3, 7, 11, 15, 19
- Patterns D (two objects comparison): moments 4, 8, 12, 16, 20

Return JSON only:
[
  {{
    "moment": "short description of the scene/idea",
    "tension": "what contradiction or emotion is present",
    "pattern": "A or B or C or D",
    "visual_hint": "MUST match the pattern — A: hand gripping/holding gold object | B: single gold coin or bar with crack/flaw | C: gold bag or chest appearing full but empty inside | D: two gold objects side by side, one solid one damaged"
  }}
]

SCRIPT:
\"\"\"
{script}
\"\"\"
"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt.format(script=script)}],
        temperature=0.4,
        max_tokens=1500,
    )
    raw = resp.choices[0].message.content.strip()
    result = clean_and_parse_json(raw)
    if not result:
        print("  ⚠️ فشل تحليل السكربت")
    return result


def format_moments(moments):
    lines = []
    for i, m in enumerate(moments, 1):
        lines.append(
            f"{i}. Moment: {m.get('moment','')}\n"
            f"   Tension: {m.get('tension','')}\n"
            f"   Visual:  {m.get('visual_hint','')}"
        )
    return "\n\n".join(lines)


def generate_thumbnails(limit=5, reset=False, batch_size=2, num_elements=1):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, "thumbnails.json")
    txt_path  = os.path.join(OUTPUT_DIR, "flow_prompts_ready.txt")

    print(f"📄 تحميل السكربت: {SCRIPT_PATH}")
    script = load_script(SCRIPT_PATH)
    print(f"   {len(script.split())} كلمة")
    print(f"   🎯 عدد العناصر الثانوية: {num_elements}")

    if reset:
        if os.path.exists(json_path):
            os.remove(json_path)
            print("🗑️  تم مسح الملف القديم")
        all_thumbnails = []
    elif os.path.exists(json_path):
        all_thumbnails = load_json(json_path)
        print(f"⏩ Resume — موجود {len(all_thumbnails)} thumbnail")
    else:
        all_thumbnails = []

    remaining = limit - len(all_thumbnails)
    if remaining <= 0:
        print(f"✅ مكتمل بالفعل ({len(all_thumbnails)} thumbnails)")
        return

    # ── Analysis Step ──────────────────────────────────────────
    client = Groq(api_key=GROQ_API_KEY)

    print("\n🔍 بيحلل السكربت...")
    moments = analyze_script(client, script)
    if not moments:
        print("❌ مفيش moments — هيشتغل على السكربت الخام")
        script_input = script[:3500]
    else:
        print(f"   ✅ {len(moments)} moment اتستخلصوا:")
        for m in moments:
            print(f"      • {m.get('moment','')} → {m.get('visual_hint','')}")
        script_input = format_moments(moments)
    # ───────────────────────────────────────────────────────────

    print(f"\n🎯 المطلوب: {limit} | تم: {len(all_thumbnails)} | متبقي: {remaining}")
    print("-" * 40)

    counter = len(all_thumbnails) + 1

    while remaining > 0:
        current_batch = min(batch_size, remaining)
        print(f"🔄 توليد {current_batch} prompt (عناصر ثانوية: {num_elements})...")

        batch = generate_batch(client, script_input, current_batch, num_elements, all_thumbnails)

        for t in batch:
            t["number"] = counter
            all_thumbnails.append(t)
            counter   += 1
            remaining -= 1

        save_json(all_thumbnails, json_path)
        export_txt(all_thumbnails, txt_path)
        print(f"  💾 حُفظ {len(all_thumbnails)}/{limit}")

        if remaining > 0:
            print("  ⏳ 3 ثواني...")
            time.sleep(3)

    print(f"\n{'='*40}")
    print(f"✅ تم! إجمالي: {len(all_thumbnails)} thumbnail")
    print(f"📁 JSON : {json_path}")
    print(f"📄 TXT  : {txt_path}")
    print(f"{'='*40}\n")

    for t in all_thumbnails:
        print(f"  #{t['number']} [{t.get('pattern','')}] — {t.get('suggested_title','')}")
        print(f"      Focal  : {t.get('focal_subject','')}")
        print(f"      Support: {', '.join(t.get('secondary_elements', []))}")
        print(f"      Hook   : {t.get('hook','')}")
        print()


def generate_batch(client, script, num_thumbnails, num_elements, all_thumbnails):
    prompt = THUMBNAIL_TEMPLATE.format(
        script=script,
        num_thumbnails=num_thumbnails,
        num_elements=num_elements,
        previous_thumbnails=build_previous_summary(all_thumbnails),
    )
    # max_tokens = min(num_thumbnails * 800, 8000)
    max_tokens = min(num_thumbnails * 500, 4000)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.55,
                max_tokens=max_tokens,
            )
            raw = resp.choices[0].message.content.strip()
            result = clean_and_parse_json(raw)
            if result:
                print(f"  ✅ {len(result)} prompt تم توليده")
                return result
            else:
                print(f"  ⚠️ محاولة {attempt+1}: JSON فارغ")
        except json.JSONDecodeError as e:
            print(f"  ⚠️ محاولة {attempt+1}: JSON Error — {e}")
        except Exception as e:
            print(f"  ⚠️ محاولة {attempt+1}: {e}")

        if attempt < 2:
            print("  🔄 بيحاول تاني...")
            time.sleep(3)

    print("  ❌ فشل الـ batch بعد 3 محاولات")
    return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Thumbnail Prompt Generator — Editorial Collage Style"
    )
    parser.add_argument("--limit",    type=int, default=5,
                        help="عدد الـ thumbnails (default: 5)")
    parser.add_argument("--reset",    action="store_true",
                        help="يبدأ من الأول")
    parser.add_argument("--batch",    type=int, default=2,
                        help="حجم الـ batch لكل request (default: 2)")
    parser.add_argument("--elements", type=int, default=1, choices=[0, 1, 2, 3],
                        help="عدد العناصر الثانوية (0-3, default: 1)")
    args = parser.parse_args()

    generate_thumbnails(
        limit=args.limit,
        reset=args.reset,
        batch_size=args.batch,
        num_elements=args.elements,
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  أوامر التشغيل:
#
#  python thumbnail_generator.py                              ← 5 thumbnails, 1 عنصر ثانوي
#  python thumbnail_generator.py --elements 0                ← فوكاس نقي
#  python thumbnail_generator.py --elements 2                ← فوكاس + 2 عناصر
#  python thumbnail_generator.py --elements 3                ← فوكاس + 3 عناصر
#  python thumbnail_generator.py --limit 10 --elements 2
#  python thumbnail_generator.py --limit 10 --reset
#  python thumbnail_generator.py --limit 10 --batch 3 --elements 2
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━