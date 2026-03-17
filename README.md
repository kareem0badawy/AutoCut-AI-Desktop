# 🎬 AutoCut — AI-Powered Video Generator

AutoCut بيحول أي سكريبت صوتي لفيديو كامل أوتوماتيك باستخدام الـ AI.  
بيولد صور، بيربطها بالتايمينج الصح، وبيجمعهم مع الصوت في فيديو نهائي جاهز للنشر.

---

## 🔄 الـ Pipeline

```
script.txt
    ↓
[1] prompt_generator.py   →   output/prompts.json
    ↓
[2] image_generator.py    →   output/images/scene_*.png
    ↓
[3] ai_mapper.py          →   mapping.json
    ↓
[4] video_builder.py      →   assets/output/final_video.mp4
```

---

## 📁 هيكل المشروع

```
AutoCut/
│
├── main.py                  # Entry point (قيد التطوير)
├── prompt_generator.py      # بيولد prompts للصور من السكريبت
├── image_generator.py       # بيولد الصور من الـ prompts عن طريق HuggingFace
├── ai_mapper.py             # بيربط الصور بـ timestamps السكريبت
├── video_builder.py         # بيجمع الصور والصوت في فيديو نهائي
├── check_names.py           # أداة مساعدة لفحص أسماء الصور
│
├── config.json              # إعدادات المشروع والـ API Keys
├── style_config.json        # ستايل وموود الصور المولدة
├── mapping.json             # ناتج ai_mapper (ربط الصور بالـ timestamps)
├── requirements.txt         # المكتبات المطلوبة
│
├── script.txt               # ملف السكريبت الصوتي (أنت بتضيفه)
│
├── assets/
│   ├── audio/               # ملف الصوت (mp3/wav/m4a)
│   ├── images/              # صور جاهزة (بديل عن التوليد)
│   └── output/              # الفيديو النهائي
│
└── output/
    ├── prompts.json         # الـ prompts المولدة
    ├── prompts_output.txt   # نسخة نصية للـ prompts
    └── images/              # الصور المولدة بالـ AI
```

---

## ⚙️ الإعدادات — `config.json`

| المفتاح | الوصف | مثال |
|---|---|---|
| `groq_api_key` | مفتاح Groq API (للـ LLM) | `gsk_...` |
| `hf_api_key` | مفتاح HuggingFace (لتوليد الصور) | `hf_...` |
| `gemini_api_key` | مفتاح Gemini (للاستخدام المستقبلي) | `AIza...` |
| `base_path` | المسار الأساسي للمشروع | `J:/Coding/Desktop/AutoCut` |
| `output_resolution` | دقة الفيديو النهائي | `1920x1080` |
| `fps` | عدد الفريمات في الثانية | `24` |
| `seconds_per_image` | كم ثانية كل صورة | `7` |
| `audio_duration` | مدة الصوت (دقيقة.ثانية) | `4.30` |
| `scenes_per_batch` | عدد المشاهد في كل batch عند توليد الـ prompts | `10` |
| `transition_duration` | مدة الـ fade بين الصور | `0.5` |
| `transition_type` | نوع الانتقال | `fade` |

---

## 🎨 الستايل — `style_config.json`

بيتحكم في شكل الصور المولدة:

| المفتاح | الوصف |
|---|---|
| `style_lock` | الوصف الثابت لستايل الصور (Norman Rockwell vintage) |
| `negative_prompt` | الأشياء اللي مش عايزها في الصور |
| `label_style` | ستايل النصوص على الصور |
| `aspect_ratio` | نسبة أبعاد الصورة `16:9` |
| `mood` | موود الصور: dramatic, historical, documentary |

---

## 🚀 طريقة الاستخدام

### 1. التثبيت

```bash
pip install -r requirements.txt
npm install -g docx
```

### 2. الإعداد

- ضع ملف السكريبت في `script.txt`
- ضع ملف الصوت في `assets/audio/`
- عدّل `config.json` بـ API Keys الخاصة بيك والمسار الصح

### 3. تشغيل الخطوات بالترتيب

```bash
# الخطوة 1: توليد الـ prompts من السكريبت
python prompt_generator.py

# الخطوة 2: توليد الصور من الـ prompts
python image_generator.py

# الخطوة 3: ربط الصور بالـ timestamps
python ai_mapper.py

# الخطوة 4: بناء الفيديو النهائي
python video_builder.py
```

---

## 📦 المكتبات المستخدمة

| المكتبة | الاستخدام |
|---|---|
| `moviepy` | تجميع الفيديو والصوت |
| `Pillow` | معالجة الصور |
| `groq` | التواصل مع Groq API (Llama 3.3 70B) |
| `huggingface_hub` | توليد الصور عن طريق FLUX.1-schnell |
| `pydub` | معالجة الصوت |
| `google-generativeai` | Gemini API (للاستخدام المستقبلي) |

---

## 🤖 الموديلات المستخدمة

| الموديل | الشركة | الاستخدام |
|---|---|---|
| `llama-3.3-70b-versatile` | Groq | توليد الـ prompts وربط الصور بالسكريبت |
| `FLUX.1-schnell` | Black Forest Labs / HuggingFace | توليد الصور |

---

## 🔧 ملاحظات تقنية

- **`TEST_MODE`** في `image_generator.py`: لو `True` بيولد أول 5 صور بس للتجربة، غيّره لـ `False` للتشغيل الكامل
- الصور المولدة بتتحفظ كـ `scene_001.png`, `scene_002.png` ...
- لو صورة موجودة قبل كده بيعملها skip تلقائياً
- الفيديو بيتقلص أو الصوت بيتقص عشان يتطابقوا في المدة

---

## 📌 المتطلبات

- Python 3.8+
- Node.js (للـ docx)
- حساب على Groq (مجاني)
- حساب على HuggingFace (مجاني)
- ملف صوتي mp3 / wav / m4a

---

## 🗺️ خارطة الطريق

- [ ] بناء `main.py` كـ entry point واحد للمشروع كله
- [ ] إضافة واجهة رسومية (GUI) بـ `customtkinter`
- [ ] دعم إضافة نصوص (captions) على الفيديو
- [ ] دعم موسيقى خلفية
- [ ] دعم transitions متعددة (zoom, slide, etc.)

---

## 🖥️ كوماندز التشغيل

### `prompt_generator.py`

```powershell
# تشغيل عادي — بيولد كل المشاهد
python prompt_generator.py

# توليد عدد محدد من المشاهد فقط (للتجربة أو توفير الكوتة)
python prompt_generator.py --limit 5

# مسح الملف القديم والبدء من الأول
python prompt_generator.py --reset

# reset + limit مع بعض
python prompt_generator.py --reset --limit 10
```

> لو الكود اتوقف في النص، شغّله تاني بدون أي flags — هيكمل أوتوماتيك من آخر نقطة.

---

### `image_generator.py`

```powershell
# توليد كل الصور (TEST_MODE = False في الكود)
python image_generator.py
```

> لو عايز تجرب أول 5 صور بس، غيّر `TEST_MODE = True` في الكود.

---

### `ai_mapper.py`

```powershell
# ربط الصور الموجودة بـ timestamps السكريبت
python ai_mapper.py
```

---

### `video_builder.py`

```powershell
# بناء الفيديو النهائي
python video_builder.py
```

---

### تشغيل الـ Pipeline كامل بالترتيب

```powershell
python prompt_generator.py
python image_generator.py
python ai_mapper.py
python video_builder.py
```
