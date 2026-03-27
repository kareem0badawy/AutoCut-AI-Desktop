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

import random
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.core.chrome_cdp import ChromeCDP, ChromeCDPError, find_chrome
from app.logger import logger


# ─────────────────────────────────────────────────────────────────────────────
# Google Flow URLs & selectors
# ─────────────────────────────────────────────────────────────────────────────

FLOW_URL         = "https://labs.google/fx/ar/tools/flow"
FLOW_ABOUT_URL   = "https://labs.google/flow/about"
GOOGLE_LOGIN_URL = "https://accounts.google.com"


# Multiple fallback selectors for each UI element.
# Flow's UI uses a mixture of material-web components and standard HTML.
# We try selectors from most-specific to least-specific.

PROMPT_SELECTORS = [
    # Most likely — material textarea or role-based input
    "textarea[aria-label]",
    "textarea[placeholder]",
    "textarea",
    "div[contenteditable='true'][aria-label]",
    "div[contenteditable='true']",
    "[role='textbox']",
    "input[type='text'][aria-label]",
    "input[type='text']",
]

GENERATE_BTN_SELECTORS = [
    # Prefer aria-label matches
    "button[aria-label*='Generate' i]",
    "button[aria-label*='Create' i]",
    "button[aria-label*='Generat' i]",
    # data-testid patterns
    "[data-testid*='generate' i]",
    "[data-testid*='submit' i]",
    # Icon buttons (Material) with specific structure
    "button[type='submit']",
    # Last resort: any primary/action button near the prompt
    "form button:last-of-type",
    "button.primary",
]

IMAGE_RESULT_SELECTORS = [
    # Generated image containers
    "[data-testid*='result' i] img",
    "[data-testid*='output' i] img",
    "[data-testid*='generated' i] img",
    "img[src*='labs.google']",
    "img[src^='blob:']",
    ".generated-image img",
    ".output img",
    "img[alt*='Generated' i]",
]

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

        # ── Step 1: Launch Chrome ─────────────────────────────────────────────
        self.log.emit("🚀  تشغيل Chrome...")
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
        self.log.emit("🌐  الانتقال إلى Flow...")
        self._ensure_on_flow()
        self._check_stop()

        # ── Step 4: Process each scene ────────────────────────────────────────
        failed_count = 0
        for idx, scene in enumerate(self._scenes):
            if self._stop_flag:
                self.log.emit("⛔  تم الإيقاف بواسطة المستخدم.")
                self.fallback.emit("أوقفه المستخدم")
                return

            self.progress.emit(idx, total)
            scene_prompt = self._build_scene_prompt(scene)
            self.log.emit(f"\n🎬  مشهد {idx + 1}/{total}: {scene_prompt[:60]}...")

            img_path = self._process_one_scene(idx, scene_prompt)
            if img_path:
                self.scene_done.emit(idx, img_path)
                self.log.emit(f"✅  صورة مشهد {idx + 1} محفوظة: {img_path}")
            else:
                failed_count += 1
                self.scene_done.emit(idx, "")
                self.log.emit(f"⚠️  فشل مشهد {idx + 1} — الانتقال لليدوي إذا فشل 3 متتالية")
                if failed_count >= 3:
                    self.fallback.emit(f"فشل {failed_count} مشاهد متتالية — التحويل لـ Manual")
                    return

        self.progress.emit(total, total)
        self.log.emit(f"\n🎉  اكتمل! {total - failed_count}/{total} مشهد ناجح.")
        self.finished_ok.emit()

    # ─────────────────────────────────────────────────────────────────────────
    # Login handling
    # ─────────────────────────────────────────────────────────────────────────

    def _wait_for_login(self) -> bool:
        """
        Check if user is logged in.
        If not, emit login_needed and wait up to TIMEOUT_LOGIN_WAIT seconds.
        Returns True when logged in, False on timeout or stop.
        """
        if self._cdp.is_logged_in():
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
        """Navigate to the Flow image creation interface."""
        url = self._cdp.current_url()
        if "labs.google/flow" not in url:
            self._cdp.navigate(FLOW_URL, settle=3.0)

        # If we land on the about/landing page, click through to the app
        url = self._cdp.current_url()
        if "about" in url or url.rstrip("/") == FLOW_URL.rstrip("/"):
            self.log.emit("🔘  النقر على 'Create' للدخول إلى التطبيق...")
            btn = self._cdp.wait_for_any(CREATE_BTN_SELECTORS, timeout=10)
            if btn:
                try:
                    self._cdp.click(btn)
                    time.sleep(2.5)
                except ChromeCDPError:
                    pass
            # Also try navigating directly to the create URL
            url = self._cdp.current_url()
            if "about" in url:
                self._cdp.navigate(FLOW_URL, settle=3.0)

        self.log.emit(f"📍  الصفحة الحالية: {self._cdp.current_url()}")

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

    def _process_one_scene(self, idx: int, prompt: str) -> str | None:
        """
        Run one full generate cycle for a scene.
        Returns saved image path on success, None on failure.
        """
        try:
            # Subtle human warmup
            self._cdp.subtle_mouse_wander(steps=3)
            time.sleep(random.uniform(0.5, 1.2))

            # ── Find prompt input ─────────────────────────────────────────────
            prompt_sel = self._cdp.wait_for_any(PROMPT_SELECTORS, timeout=TIMEOUT_PROMPT_FIND)
            if not prompt_sel:
                self.log.emit(f"  ❌  لم يُعثر على حقل الـ prompt لمشهد {idx + 1}")
                return None

            self.log.emit(f"  ✏️  كتابة الـ prompt ({len(prompt)} حرف)...")
            self._cdp.type_into(prompt_sel, prompt)
            time.sleep(random.uniform(0.4, 0.9))
            self._cdp.subtle_mouse_wander(steps=2)

            # ── Click Generate ────────────────────────────────────────────────
            gen_sel = self._cdp.wait_for_any(GENERATE_BTN_SELECTORS, timeout=10)
            if not gen_sel:
                self.log.emit(f"  ❌  لم يُعثر على زر Generate لمشهد {idx + 1}")
                return None

            self.log.emit("  🖱️  ضغط Generate...")
            time.sleep(random.uniform(0.3, 0.7))
            self._cdp.click(gen_sel)

            # ── Wait for generated image ──────────────────────────────────────
            self.log.emit("  ⏳  انتظار توليد الصورة...")
            img_sel = self._cdp.wait_for_any(IMAGE_RESULT_SELECTORS, timeout=TIMEOUT_IMAGE_GEN)
            if not img_sel:
                self.log.emit(f"  ⚠️  لم تظهر الصورة خلال {TIMEOUT_IMAGE_GEN}s")
                return None

            time.sleep(1.5)  # settle after image appears

            # ── Download & save ───────────────────────────────────────────────
            img_data = self._cdp.download_blob_image(img_sel)
            if not img_data:
                # Fallback: take a screenshot of the result area
                self.log.emit("  📸  تعذّر تحميل الصورة — أخذ screenshot...")
                img_data = self._cdp.screenshot()

            filename = f"scene_{idx + 1:03d}.png"
            save_path = self._output_dir / filename
            with open(save_path, "wb") as f:
                f.write(img_data)
            return str(save_path)

        except ChromeCDPError as e:
            self.log.emit(f"  ❌  CDP error لمشهد {idx + 1}: {e}")
            return None
        except Exception as e:
            self.log.emit(f"  ❌  خطأ لمشهد {idx + 1}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _check_stop(self) -> None:
        """Raise if stop was requested."""
        if self._stop_flag:
            raise RuntimeError("أوقفه المستخدم")
