"""
flow_automation.py
──────────────────
Auto Mode engine for Google Labs Flow (https://labs.google/fx/ar/tools/flow/).

Architecture:
  FlowWorker (QThread)
    └─ runs _automation_loop()
         ├─ launches / attaches to Chrome via ChromeCDP
         ├─ checks Google login → waits for user if needed
         ├─ navigates to Flow image creation page
         ├─ for each scene:
         │    ├─ types prompt (human-like)
         │    ├─ clicks Generate
         │    ├─ waits for generated image
         │    └─ downloads and saves image
         └─ emits signals back to the UI thread

Fallback → emits fallback(reason) signal which the UI uses to switch
           back to Manual mode.

The module purposely contains NO PySide6 UI code — only signals + logic.
"""

import datetime
import json
import random
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.chrome_cdp import ChromeCDP, ChromeCDPError, find_chrome, _port_busy
from app.logger import logger

# ─────────────────────────────────────────────────────────────────────────────
# Session state file (for resume support)
# ─────────────────────────────────────────────────────────────────────────────
SESSION_STATE_FILE = "autocut_session_state.json"  # stored in output_dir


# ─────────────────────────────────────────────────────────────────────────────
# Google Flow URLs & selectors
# ─────────────────────────────────────────────────────────────────────────────

FLOW_URL         = "https://labs.google/fx/ar/tools/flow"
FLOW_ABOUT_URL   = "https://labs.google/flow/about"
GOOGLE_LOGIN_URL = "https://accounts.google.com"


# Multiple fallback selectors for the prompt field.
# Flow uses a Slate.js editor: <div role='textbox' contenteditable='true'>
# Confirmed from live HTML inspection (March 2026).
PROMPT_SELECTORS = [
    # PRIMARY: Slate.js editor pattern (confirmed from real HTML)
    "[role='textbox'][contenteditable='true']",
    "[role='textbox'][contenteditable]",
    # Fallback: generic contenteditable
    "div[contenteditable='true']",
    "div[contenteditable]",
    # Slate editor class patterns
    ".sc-cc6342e-0",        # matches iTYalL class observed in HTML
    ".sc-84e494b2-5",       # matches gVobbe class observed in HTML
    # Last resort: any textarea
    "textarea[aria-label]",
    "textarea[placeholder]",
    "textarea",
]

# Generate button — the "إنشاء" (Create/Generate) button in Flow.
# Confirmed from live HTML:
#   CORRECT ✅: <button class="...sc-84e494b2-4..."><i>arrow_forward</i><span>إنشاء</span></button>
#   WRONG   ❌: <button aria-haspopup="menu"><i>more_vert</i><span>إنشاء المزيد</span></button>
#
# KEY RULES:
#   - MUST have aria-forward icon OR exact span text 'إنشاء'
#   - MUST NOT have aria-haspopup (that's the wrong menu button)
GENERATE_BTN_SELECTORS = [
    # Exact class from confirmed HTML (most specific)
    ".sc-84e494b2-4",
    # arrow_forward icon button that is NOT a menu trigger
    "button:not([aria-haspopup]):has(i.google-symbols)",
]

IMAGE_RESULT_SELECTORS = [
    # Extension-verified: the alt text Flow uses on generated images
    "img[alt='صورة تم إنشاؤها']",          # Arabic
    "img[alt='Generated image']",            # English
    "img[src*='getMediaUrlRedirect']",        # Flow CDN URL pattern
    # Generic generated image containers
    "[data-testid*='result' i] img",
    "[data-testid*='output' i] img",
    "[data-testid*='generated' i] img",
    "img[src*='labs.google']",
    "img[src^='blob:']",
    ".generated-image img",
    ".output img",
    "img[alt*='Generated' i]",
    "[data-tile-id] img",                    # Flow tile grid
]

# JS that detects Flow's server error state (HTTP 500) and clicks the retry button.
# Flow shows an error card: "تعذّر إكمال المعالجة. حدث خطأ." with a refresh icon button.
_ERROR_RETRY_JS = """
(function() {
    var allText = document.body.innerText || document.body.textContent || '';
    var hasError = allText.includes('\u062a\u0639\u0630\u0651\u0631 \u0625\u0643\u0645\u0627\u0644 \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629')
                || allText.includes('\u062d\u062f\u062b\u062a \u0645\u0634\u0643\u0644\u0629')
                || allText.includes('Something went wrong')
                || allText.includes('حدثت خطأ')
                || allText.includes('\u062d\u062f\u062b \u062e\u0637\u0623');
    if (!hasError) return 'none';

    // Find the retry/refresh button inside the error card
    var btns = Array.from(document.querySelectorAll('button'));
    var retryBtn = btns.find(function(b) {
        var icons = Array.from(b.querySelectorAll('i'));
        return icons.some(function(i) {
            var t = (i.innerText || i.textContent || '').trim();
            return t === 'refresh' || t === 'autorenew' || t === 'replay' || t === 'restart_alt';
        });
    });
    if (retryBtn) {
        retryBtn.scrollIntoView({block:'center'});
        var opts = {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1};
        retryBtn.dispatchEvent(new PointerEvent('pointerdown', opts));
        retryBtn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
        retryBtn.dispatchEvent(new PointerEvent('pointerup',
            {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:0}));
        retryBtn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
        retryBtn.dispatchEvent(new MouseEvent('click',   {bubbles:true}));
        return 'retried';
    }
    return 'error_no_btn';
})()
"""

CREATE_BTN_SELECTORS = [
    # Landing page "Create" / "Start" / "Try" buttons
    "a[href*='/flow'][aria-label*='Create' i]",
    "button[aria-label*='Create' i]",
    "a[href*='/flow/create']",
    "a[href*='/flow/project']",
    "[data-testid*='create' i]",
    "a.cta",
    "button.cta",
]

# "+ New Project" / "+ مشروع جديد" button shown after login on Flow home screen.
# Confirmed from live HTML (March 2026):
#   <button class="sc-a38764c7-0 ...">
#     <i class="google-symbols ...">add_2</i>
#     مشروع جديد
#   </button>
NEW_PROJECT_SELECTORS = [
    # Exact class from confirmed HTML
    ".sc-a38764c7-0",
    # Icon-based: button containing add_2 icon (google-symbols)
    "button:has(i.google-symbols)",
    # aria-label fallbacks
    "button[aria-label*='new project' i]",
    "button[aria-label*='مشروع جديد' i]",
    "[data-testid*='new-project' i]",
    "[data-testid*='create-project' i]",
]

# Project name input — shown right after clicking "New Project".
# Confirmed from live HTML:
#   <input type="text" aria-label="نص قابل للتعديل" value="Mar 27, 07:15 AM">
PROJECT_NAME_SELECTORS = [
    "input[aria-label='نص قابل للتعديل']",
    "input[aria-label*='قابل للتعديل']",
    "input[aria-label*='editable' i]",
    ".sc-68b42f2-2",          # confirmed class gemGik
    "input[type='text'][size]",
    "input[type='text']",
]

# ─────────────────────────────────────────────────────────────────────────────
# Timeouts (seconds)
# ─────────────────────────────────────────────────────────────────────────────

TIMEOUT_LOGIN_WAIT  = 300   # 5 min for user to log in
TIMEOUT_PAGE_LOAD   = 30
TIMEOUT_PROMPT_FIND = 20
TIMEOUT_IMAGE_GEN   = 90    # Flow image gen can take a while
TIMEOUT_LOGIN_POLL  = 1.0   # poll interval while waiting for login


# ─────────────────────────────────────────────────────────────────────────────
# FlowWorker
# ─────────────────────────────────────────────────────────────────────────────


class FlowWorker(QThread):
    """
    Background thread that drives automation of Google Labs Flow.

    Signals
    -------
    log(str)             — log message for the UI
    progress(int, int)   — current scene index, total scenes
    scene_done(int, str) — scene index (0-based), saved image path (or "")
    fallback(str)        — reason string → UI switches to Manual mode
    finished_ok()        — all scenes processed successfully
    login_needed()       — Chrome is on the login page; user must log in
    login_done()         — login completed; continuing automation
    """

    log         = Signal(str)
    progress    = Signal(int, int)    # scene_idx, total
    scene_done  = Signal(int, str)    # scene_idx, image_path
    fallback    = Signal(str)         # reason
    finished_ok = Signal()
    login_needed = Signal()
    login_done   = Signal()

    def __init__(
        self,
        scenes: list[dict],
        main_prompt: str,
        output_dir: str,
        chrome_exe: str | None = None,
        chrome_profile: str | None = None,
        cdp_port: int = 9222,
        resume: bool = False,   # NEW: resume from last saved state
        parent=None,
    ):
        super().__init__(parent)
        self._scenes        = scenes
        self._main_prompt   = main_prompt
        self._output_dir    = Path(output_dir)
        self._chrome_exe    = chrome_exe
        self._chrome_profile = chrome_profile
        self._cdp_port      = cdp_port
        self._stop_flag     = False
        self._cdp: ChromeCDP | None = None
        self._resume        = resume   # if True, load saved state to skip done scenes

    def stop(self) -> None:
        """Request graceful stop."""
        self._stop_flag = True
        self.log.emit("⛔  إيقاف مطلوب...")

    def run(self) -> None:
        """Entry point — called by QThread.start()."""
        try:
            self._automation_loop()
        except ChromeCDPError as e:
            self.log.emit(f"❌  Chrome Error: {e}")
            self.fallback.emit(str(e))
        except Exception as e:
            err = traceback.format_exc()
            self.log.emit(f"❌  خطأ غير متوقع: {e}\n{err}")
            self.fallback.emit(str(e))
        finally:
            if self._cdp:
                try:
                    self._cdp.close()
                except Exception:
                    pass

    # ─────────────────────────────────────────────────────────────────────────
    # Main automation loop
    # ─────────────────────────────────────────────────────────────────────────

    def _automation_loop(self) -> None:
        total = len(self._scenes)
        if total == 0:
            self.log.emit("⚠️  لا توجد مشاهد للمعالجة.")
            self.fallback.emit("لا توجد مشاهد في prompts.json")
            return

        self._output_dir.mkdir(parents=True, exist_ok=True)

        # ── Step 1: Attach to existing Chrome OR launch new ─────────────────
        if _port_busy(self._cdp_port):
            self.log.emit(
                f"🔗  Chrome يعمل على المنفذ {self._cdp_port} — الاتصال بالجلسة الحالية (بدون فتح نافذة جديدة)..."
            )
        else:
            self.log.emit(
                "⚠️  لم يُعثر على Chrome مفتوح.\n"
                "   الرجاء فتح Chrome يدوياً مع تشغيله بـ --remote-debugging-port=9222\n"
                "   أو تفعيل الخيار في الإعدادات لتشغيل Chrome تلقائياً."
            )
            self.log.emit("🚀  محاولة تشغيل Chrome مع جلسة ثابتة...")

        self._cdp = ChromeCDP(
            chrome_exe=self._chrome_exe,
            profile_dir=self._chrome_profile,
            port=self._cdp_port,
            log_fn=self.log.emit,
        )
        self._cdp.launch(FLOW_URL)
        self._check_stop()

        # ── Step 2: Handle login ──────────────────────────────────────────────
        if not self._wait_for_login():
            self.fallback.emit("انتهت مهلة انتظار تسجيل الدخول")
            return
        self._check_stop()

        # ── Step 3: Navigate to Flow image creation ───────────────────────────
        self.log.emit("🌐  التحقق من صفحة Flow...")
        self._ensure_on_flow()
        self._check_stop()

        # ── Step 4: Load saved state to support resume ────────────────────────
        completed_indices = set()
        if self._resume:
            completed_indices = self._load_progress()
            if completed_indices:
                self.log.emit(
                    f"🔄  استئناف — تم إيجاد {len(completed_indices)} مشهد منجز مسبقاً: "
                    f"{sorted(completed_indices)}"
                )
            else:
                self.log.emit("ℹ️  لا توجد جلسة محفوظة — البدء من الأول.")

        # ── Step 5: Process each scene (sequential, one at a time) ────────────
        failed_count = 0
        for idx, scene in enumerate(self._scenes):
            if self._stop_flag:
                self.log.emit("⛔  تم الإيقاف بواسطة المستخدم.")
                self.fallback.emit("أوقفه المستخدم")
                return

            # Skip already completed scenes when resuming
            if idx in completed_indices:
                self.log.emit(f"⏭️  تخطي مشهد {idx + 1} (تم إنجازه مسبقاً).")
                # Emit progress so UI stays in sync
                existing = self._output_dir / f"scene_{idx + 1:03d}.png"
                self.scene_done.emit(idx, str(existing) if existing.exists() else "")
                self.progress.emit(idx + 1, total)
                continue

            self.progress.emit(idx, total)
            scene_prompt = self._build_scene_prompt(scene)
            self.log.emit(f"\n🎬  مشهد {idx + 1}/{total}: {scene_prompt[:60]}...")

            try:
                img_path = self._process_one_scene(idx, scene_prompt)
                if img_path:
                    self.scene_done.emit(idx, img_path)
                    self.log.emit(f"✅  صورة مشهد {idx + 1} محفوظة: {img_path}")
                    failed_count = 0  # reset on success
                    # Save progress so we can resume later
                    completed_indices.add(idx)
                    self._save_progress(completed_indices)
                else:
                    failed_count += 1
                    self.scene_done.emit(idx, "")
                    self.log.emit(f"⚠️  فشل مشهد {idx + 1}")
                    if failed_count >= 3:
                        self.fallback.emit(f"فشل {failed_count} مشاهد متتالية — التحويل لـ Manual")
                        return
            except ChromeCDPError as e:
                # Critical failure — don't continue silently
                self.log.emit(f"❌  خطأ حرج في مشهد {idx + 1}: {e}")
                self.fallback.emit(str(e))
                return

        self.progress.emit(total, total)
        done_count = len(completed_indices)
        self.log.emit(f"\n🎉  اكتمل! {done_count}/{total} مشهد ناجح.")
        # Clear session state on full completion
        self._clear_progress()
        self.finished_ok.emit()

    # ─────────────────────────────────────────────────────────────────────────
    # Login handling
    # ─────────────────────────────────────────────────────────────────────────

    def _wait_for_login(self) -> bool:
        """
        Check if user is logged in.
        If already logged in (persistent session), return True immediately.
        If not, emit login_needed and wait up to TIMEOUT_LOGIN_WAIT seconds.
        Returns True when logged in, False on timeout or stop.
        """
        # Give the page 2 seconds to load before checking
        time.sleep(2.0)
        if self._cdp.is_logged_in():
            self.log.emit("✅  جلسة نشطة — لا حاجة لتسجيل دخول.")
            return True

        self.log.emit(
            "🔑  يحتاج تسجيل دخول Google.\n"
            "   سجّل دخولك في نافذة Chrome ثم اضغط 'متابعة' في التطبيق."
        )
        self.login_needed.emit()

        deadline = time.time() + TIMEOUT_LOGIN_WAIT
        while time.time() < deadline:
            if self._stop_flag:
                return False
            time.sleep(TIMEOUT_LOGIN_POLL)
            try:
                if self._cdp.is_logged_in():
                    self.login_done.emit()
                    self.log.emit("✅  تم تسجيل الدخول بنجاح.")
                    return True
            except Exception:
                pass

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Navigation
    # ─────────────────────────────────────────────────────────────────────────

    def _ensure_on_flow(self) -> None:
        """Navigate into an open Flow project ready for prompt injection."""

        # ── Fast path: already inside an open project ─────────────────────────
        if self._cdp.is_on_flow_project():
            self.log.emit("✅  بالفعل داخل مشروع Flow — جاهز.")
            return

        # ── Make sure we are on the Flow gallery page ─────────────────────────
        url = self._cdp.current_url()
        if "labs.google" not in url or "/project/" in url:
            # Either not on Flow at all, or on a stale project — go to gallery
            self.log.emit("🌐  الانتقال إلى صفحة مشاريع Flow...")
            self._cdp.navigate(FLOW_URL, settle=4.0)

        # Wait for gallery page to fully load
        time.sleep(1.5)
        url = self._cdp.current_url()
        self.log.emit(f"📍  الصفحة الحالية: {url}")

        # ── Click "مشروع جديد" ────────────────────────────────────────────────
        self.log.emit("🔘  البحث عن زر 'مشروع جديد' والنقر عليه...")
        if not self._click_new_project():
            raise ChromeCDPError(
                "❌ لم يُعثر على زر 'مشروع جديد'.\n"
                "تأكد أن Chrome مفتوح على صفحة Flow وأنت مسجّل دخولك."
            )

        # ── Wait for browser to navigate to /project/xxxxxxxx ────────────────
        self.log.emit("⏳  انتظار فتح المشروع (الانتقال إلى /project/)...")
        if not self._cdp.wait_for_project_url(timeout=20):
            raise ChromeCDPError(
                "❌ انتهت المهلة — لم ينتقل Chrome إلى صفحة المشروع.\n"
                "جرّب تشغيل Chrome يدوياً على صفحة المشاريع ثم أعد المحاولة."
            )

        project_url = self._cdp.current_url()
        self.log.emit(f"✅  تم فتح المشروع: {project_url}")

        # ── Set project name ───────────────────────────────────────────────────
        self._set_project_name()

        # ── Verify prompt field is ready ──────────────────────────────────────
        time.sleep(1.5)
        if not self._cdp.is_on_flow_project():
            raise ChromeCDPError(
                "❌ المشروع مفتوح لكن حقل الـ prompt غير موجود.\n"
                "قد تكون الصفحة لم تكتمل — انتظر ثم أعد المحاولة."
            )
        self.log.emit("✅  حقل الـ prompt جاهز — بدء حقن المشاهد.")

    # ─────────────────────────────────────────────────────────────────────────
    # New project helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _click_new_project(self) -> bool:
        """
        Click the "مشروع جديد" (New Project) button on the Flow home/gallery page.

        Strategy (most-reliable first):
        1. JS: find button whose icon innerText == 'add_2' (confirmed from HTML)
        2. JS: find button whose text includes 'مشروع جديد' / 'new project'
        3. CSS selector list fallback

        Returns True if the button was found and clicked.
        """
        # Strategy 1: icon-based (most reliable — icon text is 'add_2')
        clicked = self._cdp.evaluate("""
        (function() {
            var btns = Array.from(document.querySelectorAll('button'));
            var target = btns.find(function(b) {
                var icons = Array.from(b.querySelectorAll('i'));
                return icons.some(function(i) {
                    return (i.innerText || i.textContent || '').trim() === 'add_2';
                });
            });
            if (target) {
                target.scrollIntoView({block:'center'});
                var opts = {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1};
                target.dispatchEvent(new PointerEvent('pointerdown', opts));
                target.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                target.dispatchEvent(new PointerEvent('pointerup',
                    {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:0}));
                target.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                target.dispatchEvent(new MouseEvent('click',   {bubbles:true}));
                return true;
            }
            return false;
        })()
        """)
        if clicked:
            self.log.emit("✅  تم النقر على 'مشروع جديد' (add_2 icon).")
            time.sleep(2.5)
            return True

        # Strategy 2: text-based
        clicked = self._cdp.evaluate("""
        (function() {
            var btns = Array.from(document.querySelectorAll('button'));
            var target = btns.find(function(b) {
                var t = (b.innerText || b.textContent || '').toLowerCase().trim();
                return t.includes('\u0645\u0634\u0631\u0648\u0639 \u062c\u062f\u064a\u062f') || t.includes('new project');
            });
            if (target) {
                target.scrollIntoView({block:'center'});
                var opts = {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1};
                target.dispatchEvent(new PointerEvent('pointerdown', opts));
                target.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
                target.dispatchEvent(new PointerEvent('pointerup',
                    {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:0}));
                target.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
                target.dispatchEvent(new MouseEvent('click',   {bubbles:true}));
                return true;
            }
            return false;
        })()
        """)
        if clicked:
            self.log.emit("✅  تم النقر على 'مشروع جديد' (text match).")
            time.sleep(2.5)
            return True

        # Strategy 3: CSS selector fallback
        sel = self._cdp.wait_for_any(NEW_PROJECT_SELECTORS, timeout=5)
        if sel:
            try:
                self._cdp.click(sel)
                self.log.emit(f"✅  تم النقر على 'مشروع جديد' (selector: {sel}).")
                time.sleep(2.5)
                return True
            except ChromeCDPError:
                pass

        return False

    def _set_project_name(self) -> None:
        """
        After clicking 'مشروع جديد', Flow shows a project name input field.
        Confirmed HTML: <input type='text' aria-label='نص قابل للتعديل' value='Mar 27, ...'>

        We:
        1. Wait for the input to appear (short timeout — it may not always show)
        2. Clear the default date/time value
        3. Type a unique auto-generated name: AutoCut_YYYYMMDD_HHMM
        """
        # Generate a unique name based on current timestamp
        now = datetime.datetime.now()
        project_name = f"AutoCut_{now.strftime('%Y%m%d_%H%M')}"

        # Wait up to 4 seconds for the name field to appear
        name_sel = self._cdp.wait_for_any(PROJECT_NAME_SELECTORS, timeout=4)
        if not name_sel:
            self.log.emit("ℹ️  حقل اسم المشروع لم يظهر — سيُستخدم الاسم الافتراضي.")
            return

        self.log.emit(f"✏️  تعيين اسم المشروع: {project_name}")
        try:
            # Use JS to clear + set value on the input (it's a plain <input type='text'>)
            escaped_name = json.dumps(project_name)
            escaped_sel  = json.dumps(name_sel)
            js = f"""
            (function() {{
                var el = document.querySelector({escaped_sel});
                if (!el) return false;
                el.focus();
                // Select all and replace
                el.select();
                var proto = window.HTMLInputElement.prototype;
                var setter = Object.getOwnPropertyDescriptor(proto, 'value');
                if (setter) setter.set.call(el, {escaped_name});
                el.dispatchEvent(new Event('input',  {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                // Press Enter to confirm the name
                el.dispatchEvent(new KeyboardEvent('keydown', {{bubbles:true, key:'Enter', code:'Enter', keyCode:13}}));
                el.dispatchEvent(new KeyboardEvent('keyup',   {{bubbles:true, key:'Enter', code:'Enter', keyCode:13}}));
                return true;
            }})()
            """
            result = self._cdp.evaluate(js)
            if result:
                self.log.emit(f"✅  اسم المشروع تم تعيينه: {project_name}")
            else:
                self.log.emit("⚠️  لم يتم تعيين اسم المشروع — الحقل غير موجود.")
        except Exception as e:
            self.log.emit(f"⚠️  خطأ في تعيين اسم المشروع: {e}")

        time.sleep(0.8)  # give the UI time to process the name

    # ─────────────────────────────────────────────────────────────────────────
    # Scene processing
    # ─────────────────────────────────────────────────────────────────────────

    def _build_scene_prompt(self, scene: dict) -> str:
        """
        Combine main_prompt with scene-specific details.
        scene keys: prompt, main_prompt, description, etc.
        """
        scene_text = (
            scene.get("prompt")
            or scene.get("description")
            or scene.get("main_prompt")
            or ""
        )
        if self._main_prompt and scene_text:
            return f"{self._main_prompt}. {scene_text}"
        return scene_text or self._main_prompt

    # ─────────────────────────────────────────────────────────────────────────
    # Generate button helpers
    # ─────────────────────────────────────────────────────────────────────────

    # ─── Reusable JS that fires the full Pointer+Mouse event chain ────────────
    # Mirrors the extension's clickElement() — required for Radix UI buttons.
    _CLICK_ELEMENT_JS = """
    function _acClick(el) {
        el.scrollIntoView({block:'center'});
        var opts = {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1};
        el.dispatchEvent(new PointerEvent('pointerdown', opts));
        el.dispatchEvent(new MouseEvent('mousedown',  {bubbles:true}));
        el.dispatchEvent(new PointerEvent('pointerup',  {bubbles:true, cancelable:true,
            pointerId:1, isPrimary:true, button:0, buttons:0}));
        el.dispatchEvent(new MouseEvent('mouseup',    {bubbles:true}));
        el.dispatchEvent(new MouseEvent('click',      {bubbles:true}));
    }
    """

    # JS that finds AND (optionally) clicks the Generate (إنشاء) button.
    #
    # Confirmed from live HTML (March 2026):
    #   CORRECT ✅: <button class="...sc-84e494b2-4..."><i>arrow_forward</i><span>إنشاء</span></button>
    #   WRONG   ❌: <button aria-haspopup="menu"><i>more_vert</i><span>إنشاء المزيد</span></button>
    #
    # Strategy (3 priorities, stops at first match):
    #   1. Exact CSS class .sc-84e494b2-4
    #   2. Non-menu button (no aria-haspopup) with EXACT icon text 'arrow_forward'
    #   3. Non-menu button with span whose TRIMMED text is exactly 'إنشاء'
    #
    # CRITICAL: skip any button with aria-haspopup (إنشاء المزيد menu button)
    _GENERATE_JS = """
    (function(doClick) {
        function radixClick(el) {
            el.scrollIntoView({block:'center'});
            var opts = {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1};
            el.dispatchEvent(new PointerEvent('pointerdown', opts));
            el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
            el.dispatchEvent(new PointerEvent('pointerup',
                {bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:0}));
            el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
            el.dispatchEvent(new MouseEvent('click',   {bubbles:true}));
        }

        // Priority 1: exact CSS class (most reliable)
        var byClass = document.querySelector('.sc-84e494b2-4');
        if (byClass && !byClass.disabled) {
            if (doClick) radixClick(byClass);
            return true;
        }

        // Exclude ALL menu-trigger buttons (aria-haspopup present)
        var btns = Array.from(document.querySelectorAll('button')).filter(function(b) {
            return !b.disabled && !b.getAttribute('aria-haspopup');
        });

        // Priority 2: non-menu button with EXACT icon text 'arrow_forward'
        var byIcon = btns.find(function(b) {
            return Array.from(b.querySelectorAll('i')).some(function(i) {
                return (i.innerText || i.textContent || '').trim() === 'arrow_forward';
            });
        });
        if (byIcon) {
            if (doClick) radixClick(byIcon);
            return true;
        }

        // Priority 3: non-menu button whose span text is EXACTLY 'إنشاء'
        var bySpan = btns.find(function(b) {
            return Array.from(b.querySelectorAll('span')).some(function(s) {
                return (s.innerText || s.textContent || '').trim() === '\u0625\u0646\u0634\u0627\u0621';
            });
        });
        if (bySpan) {
            if (doClick) radixClick(bySpan);
            return true;
        }

        return false;
    })
    """

    def _find_generate_btn(self) -> bool:
        """Return True if the Generate button is found on page."""
        try:
            # 1. JS text search (most reliable)
            if self._cdp.evaluate(self._GENERATE_JS + "(false)"):
                return True
            # 2. CSS selector fallback
            return bool(self._cdp.wait_for_any(GENERATE_BTN_SELECTORS, timeout=5))
        except Exception:
            return False

    def _click_generate_btn(self) -> None:
        """Click the Generate button (text-based → CSS fallback)."""
        # Try text-based click first
        clicked = self._cdp.evaluate(self._GENERATE_JS + "(true)")
        if not clicked:
            # CSS fallback
            sel = self._cdp.wait_for_any(GENERATE_BTN_SELECTORS, timeout=5)
            if sel:
                self._cdp.click(sel)

    def _process_one_scene(self, idx: int, prompt: str) -> str | None:
        """
        Run one full generate cycle for a scene.
        Returns saved image path on success, None on failure.
        Raises explicit errors on critical failures — does NOT continue silently.
        """
        try:
            # Subtle human warmup
            self._cdp.subtle_mouse_wander(steps=3)
            time.sleep(random.uniform(0.5, 1.2))

            # ── Find prompt input ─────────────────────────────────────────────
            self.log.emit(f"  🔍  البحث عن حقل الـ prompt (مشهد {idx + 1})...")
            prompt_sel = self._cdp.wait_for_any(PROMPT_SELECTORS, timeout=TIMEOUT_PROMPT_FIND)
            if not prompt_sel:
                # Last-chance JS search
                found_sel = self._cdp.evaluate(
                    """
                    (function() {
                        var el = document.querySelector('[role="textbox"][contenteditable]')
                            || document.querySelector('div[contenteditable="true"]')
                            || document.querySelector('textarea');
                        if (!el) return null;
                        // Build a unique selector
                        if (el.id) return '#' + el.id;
                        if (el.getAttribute('role')) return '[role="' + el.getAttribute('role') + '"]';
                        return el.tagName.toLowerCase();
                    })()
                    """
                )
                if found_sel:
                    prompt_sel = found_sel
                    self.log.emit(f"  ✅  حقل الـ prompt وُجد بـ JS: {prompt_sel}")
                else:
                    raise ChromeCDPError(
                        f"❌ لم يُعثر على حقل الـ prompt لمشهد {idx + 1}.\n"
                        "تأكد أنك داخل مشروع Flow جاهز للاستخدام."
                    )

            self.log.emit(f"  ✏️  حقن الـ prompt في: {prompt_sel} ({len(prompt)} حرف)...")
            # type_into now raises on failure — no silent skip
            self._cdp.type_into(prompt_sel, prompt)
            self.log.emit(f"  ✅  تم حقن الـ prompt بنجاح.")
            time.sleep(random.uniform(0.5, 1.0))
            self._cdp.subtle_mouse_wander(steps=2)

            # ── Find & Click Generate ─────────────────────────────────────────
            self.log.emit("  🔍  البحث عن زر Generate...")
            if not self._find_generate_btn():
                time.sleep(3.0)  # wait for UI to settle then retry
                if not self._find_generate_btn():
                    raise ChromeCDPError(
                        f"❌ لم يُعثر على زر Generate لمشهد {idx + 1}.\n"
                        "تحقق من الصفحة — قد تكون في حالة خطأ."
                    )

            # ── Count images BEFORE clicking Generate (baseline) ──────────────
            before_count = self._count_result_images()
            self.log.emit(f"  📊  صور موجودة قبل التوليد: {before_count}")

            self.log.emit("  🖱️  ضغط Generate...")
            time.sleep(random.uniform(0.3, 0.7))
            self._click_generate_btn()
            self.log.emit("  ✅  تم الضغط على Generate.")

            # ── Wait for generated image (with error detection + retry) ───────
            # We pass before_count so we only detect NEW images (not old ones)
            self.log.emit("  ⏳  انتظار توليد الصورة الجديدة...")
            img_sel = self._wait_for_image_with_retry(idx, before_count=before_count)

            self.log.emit(f"  🖼️  صورة ظهرت: {img_sel}")
            time.sleep(1.5)  # settle after image appears

            # ── Download & save ───────────────────────────────────────────────
            img_data = self._cdp.download_blob_image(img_sel)
            if not img_data:
                self.log.emit("  📸  تعذّر تحميل الصورة — أخذ screenshot...")
                img_data = self._cdp.screenshot()

            filename = f"scene_{idx + 1:03d}.png"
            save_path = self._output_dir / filename
            with open(save_path, "wb") as f:
                f.write(img_data)
            self.log.emit(f"  💾  صورة محفوظة: {save_path}")
            return str(save_path)

        except ChromeCDPError as e:
            self.log.emit(f"  ❌  CDP error لمشهد {idx + 1}: {e}")
            raise  # re-raise so _automation_loop can handle it
        except Exception as e:
            self.log.emit(f"  ❌  خطأ لمشهد {idx + 1}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Image wait helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _count_result_images(self) -> int:
        """
        Count how many result images are currently visible on the page.
        Used as a baseline before clicking Generate so we know when a NEW
        image appears (count increases), avoiding false positives from
        previously generated images.
        """
        total = 0
        for sel in IMAGE_RESULT_SELECTORS:
            try:
                count = self._cdp.evaluate(
                    f"document.querySelectorAll({json.dumps(sel)}).length"
                )
                if count and int(count) > 0:
                    total = max(total, int(count))
            except Exception:
                pass
        return total

    def _wait_for_image_with_retry(
        self,
        idx: int,
        before_count: int = 0,
        max_retries: int = 2,
    ) -> str | None:
        """
        Wait for a NEW generated image to appear (count > before_count).
        If Flow's 500-error card appears, automatically click Retry and resume.

        before_count: number of result images visible BEFORE clicking Generate.
        Returns the matched selector string, or None on permanent failure.
        """
        attempt = 0
        while attempt <= max_retries:
            self._check_stop()
            result = self._wait_for_image_smart(before_count=before_count)

            if result == "image":      # success—selector is stored, return it
                return self._last_image_sel

            if result == "retried":    # error caught, retry button clicked
                attempt += 1
                self.log.emit(
                    f"  🔄  خطأ 500 — جربنا Retry ({attempt}/{max_retries})..."
                )
                time.sleep(random.uniform(3.0, 6.0))  # wait before next attempt
                continue

            if result == "error_no_btn":
                self.log.emit("  ⚠️  خطأ ولم يُعثر على زر Retry.")
                return None

            # timeout
            self.log.emit(
                f"  ⚠️  لم تظهر الصورة خلال {TIMEOUT_IMAGE_GEN}s"
            )
            return None

        self.log.emit(f"  ❌  فشل {max_retries} محاولات Retry لمشهد {idx + 1}.")
        return None

    def _wait_for_image_smart(self, before_count: int = 0) -> str:
        """
        Poll until EITHER:
          - a NEW result image appears (count > before_count)
            → returns 'image' (selector in self._last_image_sel)
          - Flow's error card appears → tries to click Retry,
            returns 'retried' or 'error_no_btn'
          - timeout → returns 'timeout'

        Polls every 3 seconds for up to TIMEOUT_IMAGE_GEN seconds.
        The 'before_count' parameter prevents false positives from images
        generated in previous scenes that are still visible in the page.
        """
        self._last_image_sel = None
        deadline = time.time() + TIMEOUT_IMAGE_GEN
        poll_interval = 3.0
        poll_num = 0

        while time.time() < deadline:
            self._check_stop()
            poll_num += 1

            # ── Check if a NEW image appeared (count > before_count) ──────────
            for sel in IMAGE_RESULT_SELECTORS:
                try:
                    current_count = self._cdp.evaluate(
                        f"document.querySelectorAll({json.dumps(sel)}).length"
                    )
                    if current_count and int(current_count) > before_count:
                        self._last_image_sel = sel
                        self.log.emit(
                            f"  📊  صور قبل: {before_count} | بعد: {current_count} "
                            f"— ظهرت صورة جديدة! ({sel})"
                        )
                        return "image"
                except Exception:
                    pass

            if poll_num % 5 == 0:  # log progress every 15s
                elapsed = int(time.time() - (deadline - TIMEOUT_IMAGE_GEN))
                self.log.emit(
                    f"  ⏳  انتظار الصورة... ({elapsed}s) "
                    f"[صور موجودة: {before_count}]"
                )

            # ── Check for error card + click retry ───────────────────────────
            try:
                err_result = self._cdp.evaluate(_ERROR_RETRY_JS)
                if err_result and err_result != "none":
                    return err_result   # 'retried' or 'error_no_btn'
            except Exception:
                pass

            time.sleep(poll_interval)

        return "timeout"

    # ─────────────────────────────────────────────────────────────────────────
    # Session state (resume support)
    # ─────────────────────────────────────────────────────────────────────────

    def _state_file(self) -> Path:
        return self._output_dir / SESSION_STATE_FILE

    def _save_progress(self, completed: set) -> None:
        """Persist the set of completed scene indices to disk."""
        try:
            data = {
                "completed": sorted(completed),
                "total": len(self._scenes),
                "timestamp": datetime.datetime.now().isoformat(),
            }
            with open(self._state_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log.emit(f"⚠️  لم يتم حفظ الحالة: {e}")

    def _load_progress(self) -> set:
        """
        Load previously saved progress.  Returns set of completed indices.
        Returns empty set if no state file or incompatible state.
        """
        try:
            sf = self._state_file()
            if not sf.exists():
                return set()
            with open(sf, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Validate: same number of scenes
            if data.get("total") != len(self._scenes):
                self.log.emit(
                    "⚠️  الحالة المحفوظة لعدد مشاهد مختلف — البدء من الأول."
                )
                return set()
            return set(data.get("completed", []))
        except Exception as e:
            self.log.emit(f"⚠️  فشل تحميل الحالة: {e}")
            return set()

    def _clear_progress(self) -> None:
        """Remove the session state file after successful completion."""
        try:
            sf = self._state_file()
            if sf.exists():
                sf.unlink()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _check_stop(self) -> None:
        """Raise if stop was requested."""
        if self._stop_flag:
            raise RuntimeError("أوقفه المستخدم")

