"""
chrome_cdp.py
─────────────
Minimal Chrome DevTools Protocol (CDP) helper.

Responsibilities:
  • Find Chrome executable on Windows / Mac / Linux
  • Launch Chrome with --remote-debugging-port and a persistent profile dir
  • Connect via WebSocket (uses 'requests' + stdlib 'websocket' shim via
    websocket-client package; added to requirements.txt)
  • Provide high-level helpers: evaluate JS, click, type, wait_for_selector

Dependencies added to requirements.txt:
  websocket-client
"""

import base64
import json
import os
import platform
import random
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from app.logger import logger

# ─────────────────────────────────────────────────────────────────────────────
# websocket-client import guard
# ─────────────────────────────────────────────────────────────────────────────

try:
    import websocket  # websocket-client package

    _WS_OK = True
except ImportError:
    _WS_OK = False


# ─────────────────────────────────────────────────────────────────────────────
# Chrome discovery
# ─────────────────────────────────────────────────────────────────────────────

_WIN_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
]
_MAC_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
_LNX_PATHS = [
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/snap/bin/chromium",
]


def find_chrome() -> str | None:
    """Return path to Chrome executable, or None if not found."""
    system = platform.system()
    if system == "Windows":
        candidates = _WIN_PATHS
    elif system == "Darwin":
        candidates = _MAC_PATHS
    else:
        candidates = _LNX_PATHS
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────


class ChromeCDPError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# ChromeCDP
# ─────────────────────────────────────────────────────────────────────────────


class ChromeCDP:
    """
    Manages a Chrome instance and communicates via CDP.

    Usage::

        cdp = ChromeCDP(profile_dir="path/to/profile")
        cdp.launch("https://labs.google/fx/ar/tools/flow")
        cdp.wait_for_selector("textarea")
        cdp.type_into("textarea", "a sunrise over mountains")
        cdp.click("button[aria-label='Generate']")
    """

    DEFAULT_PORT = 9222

    def __init__(
        self,
        chrome_exe: str | None = None,
        profile_dir: str | None = None,
        port: int = DEFAULT_PORT,
        log_fn=None,
    ):
        if not _WS_OK:
            raise ChromeCDPError(
                "websocket-client غير مثبّت.\n"
                "شغّل في Terminal:\n"
                "    pip install websocket-client"
            )
        self._exe = chrome_exe or find_chrome()
        if not self._exe:
            raise ChromeCDPError(
                "لم يُعثر على Google Chrome.\n"
                "حدّد مساره في الإعدادات أو ثبّت Chrome."
            )
        self._profile_dir = profile_dir or str(
            Path.home() / ".autocut" / "chrome_profile"
        )
        self._port = port
        self._proc: subprocess.Popen | None = None
        self._ws: "websocket.WebSocket | None" = None
        self._msg_id = 0
        self._log = log_fn or (lambda m: logger.info(m))

    # ── Launch ────────────────────────────────────────────────────────────────

    def launch(self, url: str = "about:blank") -> None:
        """
        Start Chrome with remote debugging enabled.
        If Chrome is already running on the port, attach to it
        WITHOUT opening a new window (preserves session + avoids login).
        """
        if _port_busy(self._port):
            self._log(
                f"🔗  Chrome يعمل على المنفذ {self._port} — الاتصال بالجلسة الحالية..."
            )
            self._connect()
            # Only navigate if the current tab isn't already on Flow
            try:
                current = self.current_url()
                if url != "about:blank" and "labs.google" not in current:
                    self._log(f"🌐  الانتقال إلى: {url}")
                    self.navigate(url, settle=3.0)
            except Exception:
                pass
            return

        # Chrome not running — launch with debugging enabled
        Path(self._profile_dir).mkdir(parents=True, exist_ok=True)
        args = [
            self._exe,
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={self._profile_dir}",
            # ── Fix WebSocket 403 ─────────────────────────────────────────
            "--remote-allow-origins=*",
            # ─────────────────────────────────────────────────────────────
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-popup-blocking",
            # NOTE: --disable-blink-features=AutomationControlled breaks React
            # hydration on Flow (errors #418/#423). Do NOT add it.
            url,
        ]
        self._log(f"🚀  تشغيل Chrome: {self._exe}")
        self._proc = subprocess.Popen(args)
        # Wait for Chrome to start accepting connections
        for _ in range(30):
            time.sleep(0.5)
            if _port_busy(self._port):
                break
        self._connect()

    def _connect(self, retries: int = 20) -> None:
        """
        Establish WebSocket connection to the first available page tab.
        Uses suppress_origin=True to avoid the 403 Forbidden Origin error.
        """
        endpoint = None
        for attempt in range(retries):
            try:
                raw = urllib.request.urlopen(
                    f"http://localhost:{self._port}/json", timeout=3
                ).read()
                tabs = json.loads(raw)
                for tab in tabs:
                    if tab.get("type") == "page":
                        endpoint = tab["webSocketDebuggerUrl"]
                        break
                if endpoint:
                    break
            except Exception:
                time.sleep(0.8)

        if not endpoint:
            raise ChromeCDPError(
                f"فشل الاتصال بـ Chrome على المنفذ {self._port}.\n"
                "تأكد أن Chrome يعمل ولم يُفتح من قبل بدون --remote-debugging-port."
            )

        # ── Fix WebSocket 403: send no Origin header ──────────────────────────
        # Chrome refuses connections from http://localhost:{port} origin.
        # Solution 1: --remote-allow-origins=* on launch (already set above).
        # Solution 2: pass an empty header list so websocket-client omits Origin.
        # Both together = bulletproof.
        self._ws = websocket.create_connection(
            endpoint,
            timeout=15,
            header=[],    # suppresses the Origin header that causes 403
        )
        self._log("✅  CDP متصل بنجاح.")

    # ── CDP primitives ────────────────────────────────────────────────────────

    def _send(self, method: str, params: dict | None = None) -> dict:
        """Send one CDP command; return its result. Auto-reconnects once on dropped connections."""
        for attempt in range(2):   # try twice: once normally, once after reconnect
            try:
                self._msg_id += 1
                payload = {"id": self._msg_id, "method": method, "params": params or {}}
                self._ws.send(json.dumps(payload))
                # Drain messages until we get the response for our id
                while True:
                    raw = self._ws.recv()
                    data = json.loads(raw)
                    if data.get("id") == self._msg_id:
                        if "error" in data:
                            raise ChromeCDPError(
                                f"CDP error [{method}]: {data['error'].get('message', data['error'])}"
                            )
                        return data.get("result", {})
            except ChromeCDPError:
                raise   # don't retry on logic errors
            except Exception as e:
                if attempt == 0:
                    # Connection dropped (e.g. WinError 10053) — try to reconnect once
                    self._log(f"⚠️  انقطع الاتصال بـ CDP ({type(e).__name__}) — إعادة الاتصال...")
                    try:
                        if self._ws:
                            try:
                                self._ws.close()
                            except Exception:
                                pass
                        self._ws = None
                        time.sleep(1.0)
                        self._connect()
                        continue  # retry the send after reconnect
                    except Exception as re:
                        raise ChromeCDPError(f"فشلت إعادة الاتصال: {re}") from e
                raise ChromeCDPError(f"CDP send فشل بعد إعادة المحاولة: {e}") from e
        raise ChromeCDPError(f"CDP send فشل بعد كل المحاولات")

    def evaluate(self, js: str, await_promise: bool = False) -> Any:
        """Execute JavaScript in the page context and return the value."""
        result = self._send(
            "Runtime.evaluate",
            {
                "expression": js,
                "returnByValue": True,
                "awaitPromise": await_promise,
                "timeout": 8000,
            },
        )
        if result.get("exceptionDetails"):
            msg = result["exceptionDetails"].get("text", str(result["exceptionDetails"]))
            raise ChromeCDPError(f"JS exception: {msg}")
        val = result.get("result", {})
        return val.get("value")

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate(self, url: str, settle: float = 2.5) -> None:
        """Navigate to a URL and wait for it to settle."""
        self._send("Page.navigate", {"url": url})
        time.sleep(settle)

    def current_url(self) -> str:
        return self.evaluate("window.location.href") or ""

    def is_logged_in(self) -> bool:
        """
        Return True when the user has an active Google session on Flow.

        Checks (in order):
        1. URL → not redirected to accounts.google.com / servicelogin
        2. Positive signal → prompt textarea/textbox is present on page
           (the real indicator that we are inside Flow and logged in)
        3. Negative signal → a "Sign in" or Google login button is visible
        """
        url = self.current_url()
        # Hard redirect to Google auth
        if (
            "accounts.google.com" in url
            or "signin" in url.lower()
            or "servicelogin" in url.lower()
        ):
            return False
        # Positive signal: Flow's Slate editor or any input is present
        # This is the most reliable logged-in indicator.
        try:
            has_prompt = self.evaluate(
                """
                (function() {
                    return !!(
                        document.querySelector('[role="textbox"][contenteditable]') ||
                        document.querySelector('div[contenteditable="true"]') ||
                        document.querySelector('textarea')
                    );
                })()
                """
            )
            if has_prompt:
                return True
        except Exception:
            pass
        # Negative signal: visible Google sign-in button
        try:
            has_signin_btn = self.evaluate(
                """
                (function() {
                    var btns = Array.from(document.querySelectorAll('button, a'));
                    return btns.some(function(el) {
                        var t = (el.innerText || el.textContent || '').trim().toLowerCase();
                        return t === 'sign in' || t === '\u062a\u0633\u062c\u064a\u0644 \u0627\u0644\u062f\u062e\u0648\u0644'
                            || t === 'log in' || t === 'get started'
                            || t === 'continue with google';
                    });
                })()
                """
            )
            if has_signin_btn:
                return False
        except Exception:
            pass
        # Default: if on labs.google/flow and no hard login signal, assume ok
        return "labs.google" in url and "flow" in url.lower()

    def is_on_flow_project(self) -> bool:
        """
        Return True ONLY when we are inside an open Flow project:
        - URL must contain '/project/' (e.g. /flow/project/8745370c-...)
        - AND the Slate.js prompt field must be visible

        The home page at /flow and /fx/ar/tools/flow is NOT a project page
        even if it contains a textarea somewhere.
        """
        try:
            url = self.current_url()
            # MUST have /project/ in the URL — home page is excluded
            if "/project/" not in url:
                return False
            if "labs.google" not in url:
                return False
            # Primary: Slate editor or any contenteditable prompt
            has_input = bool(self.evaluate(
                """
                !!(document.querySelector('[role="textbox"][contenteditable]') ||
                   document.querySelector('div[contenteditable="true"]') ||
                   document.querySelector('textarea'))
                """
            ))
            return has_input
        except Exception:
            return False

    def wait_for_project_url(self, timeout: float = 15.0) -> bool:
        """
        Poll until the browser URL contains '/project/' (meaning Flow
        has opened / created a project page).
        Returns True when navigated, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if "/project/" in self.current_url():
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    # ── DOM helpers ───────────────────────────────────────────────────────────

    def wait_for_selector(
        self,
        selector: str,
        timeout: float = 20.0,
        poll: float = 0.6,
    ) -> bool:
        """Poll until the CSS selector matches an element."""
        deadline = time.time() + timeout
        js = f"!!document.querySelector({json.dumps(selector)})"
        while time.time() < deadline:
            try:
                if self.evaluate(js):
                    return True
            except Exception:
                pass
            time.sleep(poll)
        return False

    def wait_for_any(
        self,
        selectors: list[str],
        timeout: float = 20.0,
    ) -> str | None:
        """Return the first selector that appears within timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            for sel in selectors:
                try:
                    if self.evaluate(f"!!document.querySelector({json.dumps(sel)})"):
                        return sel
                except Exception:
                    pass
            time.sleep(0.6)
        return None

    def get_attribute(self, selector: str, attr: str) -> str:
        js = f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            return el ? (el.getAttribute({json.dumps(attr)}) || el[{json.dumps(attr)}] || '') : '';
        }})()
        """
        return self.evaluate(js) or ""

    def click(self, selector: str) -> None:
        """
        Click the first element matching selector.
        Dispatches the full pointer-event chain (pointerdown → mousedown →
        pointerup → mouseup → click) so that Radix UI / React components
        respond correctly — mirrors the extension's clickElement() helper.
        """
        js = f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            el.scrollIntoView({{behavior:'smooth', block:'center'}});
            var opts = {{bubbles:true, cancelable:true, pointerId:1, isPrimary:true, button:0, buttons:1}};
            el.dispatchEvent(new PointerEvent('pointerdown', opts));
            el.dispatchEvent(new MouseEvent('mousedown',  {{bubbles:true}}));
            el.dispatchEvent(new PointerEvent('pointerup',  {{...opts, buttons:0}}));
            el.dispatchEvent(new MouseEvent('mouseup',    {{bubbles:true}}));
            el.dispatchEvent(new MouseEvent('click',      {{bubbles:true}}));
            return true;
        }})()
        """
        if not self.evaluate(js):
            raise ChromeCDPError(f"Element not found for click: {selector}")

    def focus(self, selector: str) -> None:
        self.evaluate(
            f"(function(){{ var el=document.querySelector({json.dumps(selector)});if(el)el.focus(); }})()"
        )

    def clear_field(self, selector: str) -> None:
        """Clear a textarea, input, or contenteditable field."""
        js = f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return;
            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                var nativeInputSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ) || Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                );
                if (nativeInputSetter) nativeInputSetter.set.call(el, '');
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
            }} else if (el.isContentEditable) {{
                el.innerHTML = '';
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
            }}
        }})()
        """
        self.evaluate(js)

    # ── Human-like typing ─────────────────────────────────────────────────────

    def type_into(
        self,
        selector: str,
        text: str,
        min_delay: float = 0.04,
        max_delay: float = 0.13,
    ) -> bool:
        """
        Inject text into a field. Returns True on success, raises ChromeCDPError on failure.

        For Slate.js (used by Google Flow):
        - JS execCommand / innerHTML does NOT work — it changes the DOM but Slate's
          internal JSON state stays empty ⇒ the send button rejects the input.
        - The ONLY reliable method is:
          1. Real CDP mouse click  → gives Slate actual browser focus
          2. Ctrl+A via CDP key events  → selects any existing text
          3. CDP Input.insertText  → fires native beforeinput/input events that
             Slate's mutation observer actually catches and updates its state
        """
        # Verify element exists
        exists = self.evaluate(f"!!document.querySelector({json.dumps(selector)})")
        if not exists:
            raise ChromeCDPError(f"حقل الـ prompt غير موجود: {selector}")

        # ── Step 1: Real browser click to give Slate proper focus ───────────────
        self._real_focus_click(selector)
        time.sleep(random.uniform(0.3, 0.5))

        # ── Step 2: Ctrl+A to select all existing content ─────────────────────
        self._select_all_kbd()
        time.sleep(0.1)

        # ── Step 3: Insert text via native CDP Input.insertText ────────────────
        # This fires the browser's native 'beforeinput' + 'input' events with
        # inputType='insertText', which is exactly what Slate.js listens for.
        self._send("Input.insertText", {"text": text})
        time.sleep(random.uniform(0.4, 0.7))

        # ── Step 4: Verify Slate actually registered the text ──────────────────
        injected = self.evaluate(f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return '';
            return el.value || el.innerText || el.textContent || '';
        }})()
        """) or ""
        if not injected.strip():
            raise ChromeCDPError(
                f"الـ prompt لم يُحقن في Slate.js (الحقل لا يزال فارغاً): {selector}"
            )
        return True

    def _real_focus_click(self, selector: str) -> None:
        """
        Click an element using REAL CDP mouse events (Input.dispatchMouseEvent),
        not JS-dispatched synthetic events.

        This is required for Slate.js editors: JS el.focus() does not properly
        initialise Slate's internal selection state, but a real mouse click does.
        """
        # Get element center coordinates via JS
        coords = self.evaluate(f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            el.scrollIntoView({{block: 'center'}});
            var r = el.getBoundingClientRect();
            return {{x: Math.round(r.left + r.width  / 2),
                     y: Math.round(r.top  + r.height / 2)}};
        }})()
        """)
        if not coords:
            # Fall back to JS-based focus if we can't get coordinates
            self.evaluate(
                f"(function(){{ var el=document.querySelector({json.dumps(selector)});"
                f"if(el)el.focus(); }})()"
            )
            return

        x, y = coords["x"], coords["y"]
        # Real mouse press + release
        self._send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "buttons": 1, "clickCount": 1,
        })
        time.sleep(0.05)
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "buttons": 0, "clickCount": 1,
        })

    def _select_all_kbd(self) -> None:
        """
        Send Ctrl+A via CDP key events to select all content in the focused element.
        Works correctly with Slate.js (real keyboard events, not JS-dispatched).
        """
        ctrl_a = {
            "modifiers": 2,          # Ctrl
            "key": "a",
            "code": "KeyA",
            "windowsVirtualKeyCode": 65,
            "nativeVirtualKeyCode":  65,
        }
        self._send("Input.dispatchKeyEvent", {"type": "keyDown", **ctrl_a})
        self._send("Input.dispatchKeyEvent", {"type": "keyUp",   **ctrl_a})

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mouse_move(self, x: int, y: int) -> None:
        self._send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y, "button": "none",
        })

    def subtle_mouse_wander(self, steps: int = 4) -> None:
        """Move mouse naturally to avoid bot detection."""
        for _ in range(steps):
            self.mouse_move(random.randint(200, 800), random.randint(150, 500))
            time.sleep(random.uniform(0.05, 0.18))

    # ── Screenshot ────────────────────────────────────────────────────────────

    def screenshot(self, save_path: str | None = None) -> bytes:
        """Capture a PNG screenshot of the current page."""
        result = self._send("Page.captureScreenshot", {"format": "png"})
        png = base64.b64decode(result.get("data", ""))
        if save_path:
            with open(save_path, "wb") as f:
                f.write(png)
        return png

    # ── Image download ────────────────────────────────────────────────────────

    def get_image_src(self, selector: str) -> str:
        """Return the src attribute of an image element (could be blob: or https:)."""
        return self.get_attribute(selector, "src")

    def get_result_image_count(self, selector: str) -> int:
        """Return how many elements match selector (used to track before/after counts)."""
        try:
            cnt = self.evaluate(f"document.querySelectorAll({json.dumps(selector)}).length")
            return int(cnt) if cnt else 0
        except Exception:
            return 0

    def screenshot_element(self, selector: str) -> bytes:
        """
        Capture a screenshot cropped to just the bounding box of the first
        element matching selector.  Falls back to full-page screenshot if
        the element is not found or has zero size.
        """
        coords = self.evaluate(f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            el.scrollIntoView({{block: 'center'}});
            var r = el.getBoundingClientRect();
            var s = window.devicePixelRatio || 1;
            return {{x: r.left, y: r.top, width: r.width, height: r.height, scale: s}};
        }})()
        """)
        if not coords or not coords.get("width") or not coords.get("height"):
            return self.screenshot()
        result = self._send("Page.captureScreenshot", {
            "format": "png",
            "clip": {
                "x":      max(0.0, float(coords["x"])),
                "y":      max(0.0, float(coords["y"])),
                "width":  max(1.0, float(coords["width"])),
                "height": max(1.0, float(coords["height"])),
                "scale":  float(coords.get("scale", 1.0)),
            },
        })
        return base64.b64decode(result.get("data", ""))

    def screenshot_element_at_index(self, selector: str, index: int) -> bytes:
        """
        Capture a screenshot cropped to just the bounding box of element at
        position `index` within querySelectorAll(selector).  Falls back to
        full-page screenshot if element is not found.
        """
        coords = self.evaluate(f"""
        (function() {{
            var els = document.querySelectorAll({json.dumps(selector)});
            var el  = els[{index}];
            if (!el) return null;
            el.scrollIntoView({{block: 'center'}});
            var r = el.getBoundingClientRect();
            var s = window.devicePixelRatio || 1;
            return {{x: r.left, y: r.top, width: r.width, height: r.height, scale: s}};
        }})()
        """)
        if not coords or not coords.get("width") or not coords.get("height"):
            return self.screenshot()
        result = self._send("Page.captureScreenshot", {
            "format": "png",
            "clip": {
                "x":      max(0.0, float(coords["x"])),
                "y":      max(0.0, float(coords["y"])),
                "width":  max(1.0, float(coords["width"])),
                "height": max(1.0, float(coords["height"])),
                "scale":  float(coords.get("scale", 1.0)),
            },
        })
        return base64.b64decode(result.get("data", ""))

    def download_image_at_index(self, selector: str, index: int) -> bytes | None:
        js = f"""
        (async function() {{
            var els = document.querySelectorAll({json.dumps(selector)});
            var el  = els[{index}];
            if (!el || el.tagName !== 'IMG') return null;

            // Scroll into view and wait for load
            el.scrollIntoView({{block: 'center'}});
            await new Promise(function(resolve) {{ setTimeout(resolve, 800); }});

            if (!el.complete || el.naturalWidth === 0) {{
                await new Promise(function(resolve) {{
                    el.addEventListener('load',  resolve, {{once: true}});
                    el.addEventListener('error', resolve, {{once: true}});
                    setTimeout(resolve, 5000);
                }});
            }}

            var src = el.src || el.getAttribute('src') || '';
            if (!src) return null;

            // Strategy 1: fetch directly (works for CDN URLs with credentials)
            try {{
                var resp = await fetch(src, {{credentials: 'include', cache: 'force-cache'}});
                if (resp.ok) {{
                    var blob = await resp.blob();
                    return await new Promise(function(resolve) {{
                        var reader = new FileReader();
                        reader.onloadend = function() {{ resolve(reader.result); }};
                        reader.readAsDataURL(blob);
                    }});
                }}
            }} catch(e1) {{}}

            // Strategy 2: canvas drawImage (fallback — may fail for cross-origin)
            try {{
                var nw = el.naturalWidth  || el.width  || 512;
                var nh = el.naturalHeight || el.height || 512;
                if (nw > 0 && nh > 0) {{
                    var canvas = document.createElement('canvas');
                    canvas.width  = nw;
                    canvas.height = nh;
                    var ctx = canvas.getContext('2d');
                    ctx.drawImage(el, 0, 0, nw, nh);
                    var data = canvas.toDataURL('image/png');
                    if (data && data.length > 200) return data;
                }}
            }} catch(e2) {{}}

            return null;
        }})()
        """
        try:
            result = self.evaluate(js, await_promise=True)
        except Exception:
            result = None

        if result and isinstance(result, str) and result.startswith("data:"):
            _, encoded = result.split(",", 1)
            return base64.b64decode(encoded)
        return None

    def download_blob_image(self, selector: str) -> bytes | None:
        """
        Download the first image matching selector.
        Wrapper around download_image_at_index(selector, 0)
        kept for backward compatibility.
        """
        result = self.download_image_at_index(selector, 0)
        if result:
            return result
        # Legacy fetch fallback
        js = f"""
        (async function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            var src = el.src;
            if (!src) return null;
            try {{
                var resp = await fetch(src, {{credentials: 'include'}});
                var blob = await resp.blob();
                return await new Promise(function(resolve) {{
                    var reader = new FileReader();
                    reader.onloadend = function() {{ resolve(reader.result); }};
                    reader.readAsDataURL(blob);
                }});
            }} catch(e) {{ return null; }}
        }})()
        """
        try:
            r = self.evaluate(js, await_promise=True)
            if r and r.startswith("data:"):
                _, enc = r.split(",", 1)
                return base64.b64decode(enc)
        except Exception:
            pass
        return None

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the WebSocket. Does NOT kill Chrome (preserves session)."""
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
