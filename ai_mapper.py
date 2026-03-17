from groq import Groq
import json
import os

def load_config():
    with open("J:/Coding/Desktop/AutoCut/config.json", "r", encoding="utf-8-sig") as f:
        return json.load(f)

def get_image_list(images_folder):
    extensions = ('.jpg', '.jpeg', '.png', '.webp')
    images = [f for f in os.listdir(images_folder) if f.lower().endswith(extensions)]
    return images

def map_images_to_script(script_text, images_folder):
    config = load_config()
    client = Groq(api_key=config["groq_api_key"])
    
    images = get_image_list(images_folder)
    images_list_str = "\n".join([f"- {img}" for img in images])

    prompt = f"""
You are a video editor assistant. 
I have a voiceover script with timestamps and a list of images.
Your job is to map each image to the most suitable timestamp range in the script based on the image filename description.

SCRIPT:
{script_text}

AVAILABLE IMAGES:
{images_list_str}

RULES:
1. Return ONLY a valid JSON array, no explanation, no markdown, no extra text.
2. Cover the entire script from start to finish with no gaps.
3. Each scene must have at least 1 image, you can use the same image in multiple scenes if needed.
4. Distribute images logically based on their filename meaning vs script content.
5. Use this exact format:

[
  {{
    "start": "00:00",
    "end": "00:36",
    "images": ["image1.jpg", "image2.jpg"]
  }},
  {{
    "start": "00:36",
    "end": "01:19",
    "images": ["image3.jpg"]
  }}
]
"""

    print("🤖 Groq + Llama بيحلل السكريبت والصور...")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    
    raw = response.choices[0].message.content.strip()
    
    if raw.startswith("`"):
        raw = raw.split("`")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    
    result = json.loads(raw)
    
    output_path = "J:/Coding/Desktop/AutoCut/mapping.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"✅ تم عمل الـ mapping وحفظه في: {output_path}")
    print(f"📊 عدد المشاهد: {len(result)}")
    return result

if __name__ == "__main__":
    script = """
(00:00) in nineteen twenty three a german banker named friedrich hecker watched his life savings buy less than a cup of coffee he'd spent thirty years building a respectable fortune government bonds a pension a savings account at a reputable berlin bank all denominated in marks all worthless by november meanwhile a wheat farmer forty miles outside the city a man with no education no financial sophistication no connections was richer than he'd ever been his grain was worth more every single day people were trading pianos
(00:36) fur coats and family silver for bags of flour same crisis same country same year completely opposite outcomes and the thing that separated them wasn't luck or timing or intelligence it was what they held this is a story about the things that survive when money dies and if you think it's ancient history that it couldn't happen today consider this every single fiat currency ever created has either collapsed or lost the vast majority of its value everyone the dollar has lost over ninety six percent of its purchasing power since nineteen thirteen
(01:19) we're not outside this pattern we're inside it this pattern specific types of assets surviving while everything else burns isn't unique to germany it shows up in every major currency crisis every hyperinflation every financial collapse across four thousand years of recorded history the assets change their names they never change their nature so what are they and why do they keep working when nothing else does the first asset that survives every crisis is the most ancient one land not land is a line item on a portfolio spreadsheet
(01:57) productive land the kind that grows food holds minerals or sits on water when currencies collapse the economy doesn't stop people still eat they still need shelter fuel raw materials and whoever controls the source of those things holds real power regardless of what's happening to the money in weimar germany farmers who owned their land outright became the new aristocracy almost overnight they could demand payment in gold in foreign currency or in goods a pig farmer could trade a single hog for a grand piano
(02:38) that once cost a banker three months salary that's not an exaggeration that's from the historical record in zimbabwe's collapse in two thousand eight the same pattern played out farmers with productive land and livestock had something people would trade anything for urban workers with savings accounts denominated in zimbabwean dollars had nothing the reason is simple land produces things that have value independent of any currency a bushel of wheat feeds a family whether the dollar is worth a hundred cents or half a cent
(03:14) that independence from the monetary system is what makes land the oldest crisis proof asset in human history the second asset is gold and before you roll your eyes this isn't about gold bugs or conspiracy theories this is about math and human behavior when a currency fails an entire society needs something to use as money not eventually immediately and for thousands of years the thing humans default to is gold not because it's magical because it's recognizable divisible portable and critically no government can print more of it
(03:53) during the french revolution the government issued paper currency called assignats they were backed by seized church lands and for a while people trusted them then the government printed more and more within five years assignats had lost over ninety nine percent of their value people who had converted their paper into gold early preserved everything people who waited lost everything the same dynamic played out in argentina in the nineteen eighties in russia in the nineteen nineties in venezuela in the twenty tens
"""
    
    images_folder = "J:/Coding/Desktop/AutoCut/assets/images"
    map_images_to_script(script, images_folder)
