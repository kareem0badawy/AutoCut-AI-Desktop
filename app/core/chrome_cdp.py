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
        If Chrome is already running on the port, attach to it.
        """
        if _port_busy(self._port):
            self._log(
                f"Chrome already running on port {self._port} — attaching."
            )
        else:
            Path(self._profile_dir).mkdir(parents=True, exist_ok=True)
            args = [
                self._exe,
                f"--remote-debugging-port={self._port}",
                f"--user-data-dir={self._profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--disable-blink-features=AutomationControlled",
                url,
            ]
            self._log(f"Starting Chrome: {self._exe}")
            self._proc = subprocess.Popen(args)
            # Wait for Chrome to start accepting connections
            for _ in range(20):
                time.sleep(0.5)
                if _port_busy(self._port):
                    break

        self._connect()

    def _connect(self, retries: int = 15) -> None:
        """Establish WebSocket connection to the first available page tab."""
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
                time.sleep(1)

        if not endpoint:
            raise ChromeCDPError(
                f"فشل الاتصال بـ Chrome على المنفذ {self._port}.\n"
                "تأكد أن Chrome يعمل ولم يُفتح من قبل بدون debugging."
            )

        self._ws = websocket.create_connection(endpoint, timeout=15)
        self._log("CDP connected.")

    # ── CDP primitives ────────────────────────────────────────────────────────

    def _send(self, method: str, params: dict | None = None) -> dict:
        """Send one CDP command; return its result."""
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
        """Return True if NOT on a Google accounts/login page."""
        url = self.current_url()
        return "accounts.google.com" not in url and "signin" not in url.lower()

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
        """Click the first element matching selector."""
        js = f"""
        (function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            el.scrollIntoView({{behavior:'smooth', block:'center'}});
            el.click();
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
    ) -> None:
        """
        Type text character-by-character into a field.
        Triggers native React/Vue input events so the framework picks up changes.
        """
        self.focus(selector)
        time.sleep(random.uniform(0.2, 0.5))
        self.clear_field(selector)
        time.sleep(random.uniform(0.1, 0.3))

        for char in text:
            char_json = json.dumps(char)
            js = f"""
            (function() {{
                var el = document.querySelector({json.dumps(selector)});
                if (!el) return;
                var key = {char_json};

                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                    var proto = el.tagName === 'TEXTAREA'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    var setter = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (setter) setter.set.call(el, el.value + key);
                    el.dispatchEvent(new Event('input', {{bubbles:true}}));
                }} else if (el.isContentEditable) {{
                    el.focus();
                    document.execCommand('insertText', false, key);
                }}
            }})()
            """
            self.evaluate(js)
            time.sleep(random.uniform(min_delay, max_delay))
            # Occasional longer pause (like a real typist)
            if random.random() < 0.06:
                time.sleep(random.uniform(0.2, 0.5))

        # Final change event
        self.evaluate(
            f"(function(){{ var el=document.querySelector({json.dumps(selector)});"
            f"if(el)el.dispatchEvent(new Event('change',{{bubbles:true}})); }})()"
        )

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

    def download_blob_image(self, selector: str) -> bytes | None:
        """
        Download an image that might be a blob: URL.
        Uses fetch() inside the page context to convert blob → base64.
        """
        js = f"""
        (async function() {{
            var el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            var src = el.src;
            if (!src) return null;
            try {{
                var resp = await fetch(src);
                var blob = await resp.blob();
                return await new Promise(function(resolve) {{
                    var reader = new FileReader();
                    reader.onloadend = function() {{ resolve(reader.result); }};
                    reader.readAsDataURL(blob);
                }});
            }} catch(e) {{
                return src;  // return raw URL as fallback
            }}
        }})()
        """
        result = self.evaluate(js, await_promise=True)
        if not result:
            return None
        if result.startswith("data:"):
            _, encoded = result.split(",", 1)
            return base64.b64decode(encoded)
        # Regular URL — download via requests
        try:
            import requests
            resp = requests.get(result, timeout=30)
            return resp.content
        except Exception:
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
