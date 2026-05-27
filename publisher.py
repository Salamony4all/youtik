"""
publisher.py – Unified Social-Media Publishing Engine
=====================================================
Handles browser-based uploads to TikTok, YouTube Shorts, Instagram Reels
and X/Twitter using Playwright stealth wrappers and the tiktokautouploader
pip package.

First-time use per platform opens a *visible* browser window for manual
login.  Session cookies are persisted locally so subsequent uploads can
run headless.
"""

import asyncio
import base64
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SESSIONS_DIR = Path("./sessions")
GOOGLE_PROFILE_DIR = SESSIONS_DIR / "google_profile"
PLATFORMS = {
    "tiktok":    {"icon": "🎵", "name": "TikTok"},
    "youtube":   {"icon": "▶️",  "name": "YouTube Shorts"},
    "instagram": {"icon": "📸", "name": "Instagram Reels"},
    "twitter":   {"icon": "🐦", "name": "X / Twitter"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_session_dirs():
    """Create the sessions/ directory tree if it doesn't exist."""
    for platform in PLATFORMS:
        (SESSIONS_DIR / platform).mkdir(parents=True, exist_ok=True)


def _cookies_path(platform: str, account: str = "default") -> Path:
    return SESSIONS_DIR / platform / account / "cookies.json"


def _has_real_session(platform: str, account: str = "default") -> bool:
    """Check if the platform has a real, authenticated login session (not just a mock master trigger)."""
    cookie_file = _cookies_path(platform, account)
    if not cookie_file.is_file():
        return False
    try:
        data = json.loads(cookie_file.read_text())
        if isinstance(data, dict):
            # TikTok autouploader session or other custom format
            return data.get("source") == "tiktokautouploader" or len(data) > 1
        elif isinstance(data, list):
            # Playwright cookies list
            real_cookies = [c for c in data if c.get("name") != "google_master_session"]
            return len(real_cookies) > 0
        return False
    except Exception:
        return False


def _has_google_profile() -> bool:
    """Check if a real Google browser profile exists (user signed in via browser)."""
    try:
        return GOOGLE_PROFILE_DIR.exists() and any(GOOGLE_PROFILE_DIR.iterdir())
    except Exception:
        return False


def get_authenticated_accounts() -> list[dict]:
    """Return a list of platforms that already have saved sessions."""
    _ensure_session_dirs()
    accounts = []
    for platform, meta in PLATFORMS.items():
        platform_dir = SESSIONS_DIR / platform
        if platform_dir.exists():
            for acct_dir in platform_dir.iterdir():
                if acct_dir.is_dir() and (acct_dir / "cookies.json").exists():
                    accounts.append({
                        "platform": platform,
                        "account": acct_dir.name,
                        "icon": meta["icon"],
                        "name": meta["name"],
                    })
    return accounts


# ---------------------------------------------------------------------------
# Publish jobs (in-memory store, keyed by job_id)
# ---------------------------------------------------------------------------
publish_jobs: dict[str, dict] = {}
login_jobs: dict[str, dict] = {}


def _set_status(job_id: str, status: str, detail: str = ""):
    if job_id in publish_jobs:
        publish_jobs[job_id]["status"] = status
        publish_jobs[job_id]["detail"] = detail
        publish_jobs[job_id]["updated_at"] = time.time()


def _is_headless_server() -> bool:
    """Detect if running on a headless cloud server (Railway, Render, Docker)."""
    return (
        os.environ.get("RENDER") is not None
        or os.environ.get("DOCKER_CONTAINER") is not None
        or os.environ.get("RAILWAY_ENVIRONMENT") is not None
    )


# ---------------------------------------------------------------------------
# Virtual Display Manager (Xvfb + x11vnc + websockify)
# ---------------------------------------------------------------------------

class VirtualDisplay:
    """
    Manages a virtual display stack for live browser streaming:
      Xvfb (:99) → x11vnc (VNC :5900) → websockify (WebSocket :6080)

    The user connects to websockify via noVNC in their browser to watch
    and interact with the Playwright browser in real time.
    """

    _instance = None  # Singleton — one display per server process
    _lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

    def __init__(self):
        self.display = ":99"
        self.vnc_port = 5900
        self.ws_port = 6080
        self.xvfb_proc = None
        self.vnc_proc = None
        self.ws_proc = None
        self._running = False
        self._active_sessions = 0

    @classmethod
    async def get_instance(cls):
        """Get or create the singleton VirtualDisplay."""
        if cls._instance is None:
            cls._instance = VirtualDisplay()
        if not cls._instance._running:
            await cls._instance.start()
        cls._instance._active_sessions += 1
        return cls._instance

    async def start(self):
        """Start Xvfb, x11vnc, and websockify."""
        if self._running:
            return

        print("[VNC] Starting virtual display stack…")

        # 1. Start Xvfb (virtual framebuffer)
        try:
            self.xvfb_proc = subprocess.Popen(
                ["Xvfb", self.display, "-screen", "0", "1920x1080x24", "-ac", "-nolisten", "tcp"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await asyncio.sleep(0.5)  # Give Xvfb time to start
            print(f"[VNC] Xvfb started on display {self.display} (PID: {self.xvfb_proc.pid})")
        except FileNotFoundError:
            print("[VNC] WARNING: Xvfb not found — falling back to headless mode")
            return
        except Exception as e:
            print(f"[VNC] WARNING: Failed to start Xvfb: {e}")
            return

        # 2. Start x11vnc (captures the virtual display as VNC)
        try:
            self.vnc_proc = subprocess.Popen(
                [
                    "x11vnc",
                    "-display", self.display,
                    "-nopw",           # No password (internal-only)
                    "-forever",        # Don't exit after first disconnect
                    "-shared",         # Allow multiple connections
                    "-rfbport", str(self.vnc_port),
                    "-xkb",            # Use X keyboard
                    "-noxrecord",
                    "-noxfixes",
                    "-noxdamage",
                    "-wait", "5",      # 5ms poll interval (fast updates)
                ]
            )
            await asyncio.sleep(0.3)
            print(f"[VNC] x11vnc started on port {self.vnc_port} (PID: {self.vnc_proc.pid})")
        except FileNotFoundError:
            print("[VNC] WARNING: x11vnc not found — display started but no VNC")
        except Exception as e:
            print(f"[VNC] WARNING: Failed to start x11vnc: {e}")

        # 3. Start websockify (proxies VNC over WebSocket for noVNC)
        try:
            # noVNC static files location on Debian/Ubuntu
            novnc_path = "/usr/share/novnc"
            self.ws_proc = subprocess.Popen(
                [
                    "websockify",
                    "--web", novnc_path,
                    str(self.ws_port),
                    f"127.0.0.1:{self.vnc_port}",
                ]
            )
            await asyncio.sleep(0.3)
            print(f"[VNC] websockify started on port {self.ws_port} → VNC:{self.vnc_port} (PID: {self.ws_proc.pid})")
        except FileNotFoundError:
            print("[VNC] WARNING: websockify not found — VNC running but no WebSocket proxy")
        except Exception as e:
            print(f"[VNC] WARNING: Failed to start websockify: {e}")

        self._running = True
        os.environ["DISPLAY"] = self.display
        print("[VNC] Virtual display stack ready ✓")

    @property
    def is_vnc_ready(self):
        """Check if websockify is actually running and proxying VNC."""
        return self._running and self.ws_proc is not None and self.ws_proc.poll() is None

    async def release(self):
        """Decrement active session count; stop stack if no sessions remain."""
        self._active_sessions = max(0, self._active_sessions - 1)
        if self._active_sessions == 0:
            await self.stop()

    async def stop(self):
        """Tear down the virtual display stack."""
        if not self._running:
            return
        print("[VNC] Stopping virtual display stack…")
        for name, proc in [("websockify", self.ws_proc), ("x11vnc", self.vnc_proc), ("Xvfb", self.xvfb_proc)]:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                    print(f"[VNC] {name} stopped.")
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        self.xvfb_proc = self.vnc_proc = self.ws_proc = None
        self._running = False

    @property
    def is_running(self):
        return self._running

    async def take_screenshot(self) -> Optional[str]:
        """Capture a screenshot of the virtual display as base64 PNG."""
        if not self._running:
            return None
        screenshot_path = "/tmp/vnc_screenshot.png"
        try:
            proc = await asyncio.create_subprocess_exec(
                "xdotool", "getactivewindow", "--",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass
        try:
            import_proc = await asyncio.create_subprocess_exec(
                "import", "-display", self.display, "-window", "root", screenshot_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(import_proc.wait(), timeout=5)
            if os.path.isfile(screenshot_path):
                with open(screenshot_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("ascii")
        except Exception as e:
            print(f"[VNC] Screenshot failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Google Browser Authentication (Real Playwright-based login)
# ---------------------------------------------------------------------------

_STEALTH_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.navigator.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""


async def _run_google_login(job_id: str):
    """Open a real Chromium browser for Google login using a persistent profile."""
    login_jobs[job_id]["status"] = "BROWSER_OPEN"
    login_jobs[job_id]["detail"] = "Opening browser for Google sign-in…"

    try:
        from phantomwright_driver.async_api import async_playwright  # type: ignore
    except ImportError:
        login_jobs[job_id]["status"] = "ERROR"
        login_jobs[job_id]["detail"] = "Playwright not installed. Run: pip install playwright && playwright install chromium"
        return

    profile_dir = str(GOOGLE_PROFILE_DIR)
    os.makedirs(profile_dir, exist_ok=True)

    # Detect headless server (Render, Docker, CI, etc.)
    on_server = _is_headless_server()
    virtual_display = None
    headless = on_server

    try:
        if on_server:
            try:
                virtual_display = await VirtualDisplay.get_instance()
                headless = False
                login_jobs[job_id]["vnc_active"] = virtual_display.is_vnc_ready
                login_jobs[job_id]["vnc_ws_port"] = virtual_display.ws_port
                login_jobs[job_id]["detail"] = "Virtual display ready — launching visible browser for Google sign-in…"
            except Exception as e:
                print(f"[VNC] Failed to start virtual display for login: {e}")
                login_jobs[job_id]["vnc_active"] = False

        # Clean up existing locks if container crashed previously
        for lock_file in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            lock_path = os.path.join(profile_dir, lock_file)
            if os.path.exists(lock_path):
                try:
                    if os.path.islink(lock_path):
                        os.unlink(lock_path)
                    else:
                        os.remove(lock_path)
                except Exception:
                    pass

        async with async_playwright() as pw:
            context = await pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )

            await context.add_init_script(_STEALTH_SCRIPT)

            page = context.pages[0] if context.pages else await context.new_page()

            # Navigate to YouTube Studio — it will redirect to Google sign-in if needed
            await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=0)
            await page.wait_for_timeout(3000)

            current_url = page.url

            # Check if already logged in (page stayed on Studio, not redirected)
            if "studio.youtube.com" in current_url and "accounts.google.com" not in current_url:
                login_jobs[job_id]["status"] = "AUTHENTICATED"
                login_jobs[job_id]["detail"] = "Already signed in to YouTube Studio!"

                # Try to read channel name from the page
                name = "YouTube Creator"
                try:
                    name_el = page.locator(".channel-name").first
                    name = (await name_el.text_content(timeout=3000) or name).strip()
                except Exception:
                    pass

                master_data = {
                    "name": name,
                    "email": "Authenticated via browser",
                    "picture": "",
                    "authenticated_at": time.time(),
                    "auth_method": "browser_persistent",
                }
                (SESSIONS_DIR / "google_master.json").write_text(
                    json.dumps(master_data, indent=2)
                )
                login_jobs[job_id]["user"] = master_data

                await context.close()
                if virtual_display:
                    await virtual_display.release()
                return

            # Not logged in yet — check if we're on a headless server without VNC
            if on_server and not virtual_display:
                # On Render/Docker, user can't interact with the browser
                await context.close()
                
                # Check if YOUTUBE_COOKIES env var is set — that's the server alternative
                has_cookies = bool(os.environ.get("YOUTUBE_COOKIES"))
                if has_cookies:
                    # Create a synthetic "authenticated" state from cookies
                    master_data = {
                        "name": "Cookie Session",
                        "email": "Authenticated via YOUTUBE_COOKIES env var",
                        "picture": "",
                        "authenticated_at": time.time(),
                        "auth_method": "cookies_env_var",
                    }
                    (SESSIONS_DIR / "google_master.json").write_text(
                        json.dumps(master_data, indent=2)
                    )
                    login_jobs[job_id]["status"] = "AUTHENTICATED"
                    login_jobs[job_id]["detail"] = "Connected via YOUTUBE_COOKIES ✓"
                    login_jobs[job_id]["user"] = master_data
                else:
                    login_jobs[job_id]["status"] = "ERROR"
                    login_jobs[job_id]["detail"] = "Headless server detected. Virtual Display failed. Set the YOUTUBE_COOKIES environment variable in Railway dashboard to authenticate."
                return

            # Desktop/local — wait for the user to sign in manually
            login_jobs[job_id]["status"] = "WAITING_LOGIN"
            login_jobs[job_id]["detail"] = "Please sign in to your Google account in the browser window…"

            logged_in = False
            while not page.is_closed():
                await page.wait_for_timeout(1000)
                try:
                    cur = page.url
                    # We consider login successful once it lands on YouTube Studio and is no longer on Google Accounts
                    if "studio.youtube.com" in cur and "accounts.google.com" not in cur:
                        logged_in = True
                        break
                except Exception:
                    pass

            if logged_in:
                # Wait longer (10 seconds) to ensure all background scripts, session storage, and cookies fully settle
                await page.wait_for_timeout(10000)

                name = "YouTube Creator"
                try:
                    name_el = page.locator(".channel-name").first
                    name = (await name_el.text_content(timeout=5000) or name).strip()
                except Exception:
                    pass

                master_data = {
                    "name": name,
                    "email": "Authenticated via browser",
                    "picture": "",
                    "authenticated_at": time.time(),
                    "auth_method": "browser_persistent",
                }
                (SESSIONS_DIR / "google_master.json").write_text(
                    json.dumps(master_data, indent=2)
                )

                login_jobs[job_id]["status"] = "AUTHENTICATED"
                login_jobs[job_id]["detail"] = f"Signed in as {name}"
                login_jobs[job_id]["user"] = master_data

                # Export cookies to workspace root so yt-dlp can use them natively
                try:
                    cookies = await context.cookies()
                    lines = [
                        "# Netscape HTTP Cookie File",
                        "# http://curl.haxx.se/rfc/cookie_spec.html",
                        "# This is a generated file! Do not edit.",
                        ""
                    ]
                    for c in cookies:
                        domain = c.get("domain", "")
                        flag = "TRUE" if domain.startswith(".") else "FALSE"
                        path = c.get("path", "/")
                        secure = "TRUE" if c.get("secure", False) else "FALSE"
                        expiry = str(int(c.get("expires", 0)))
                        cname = c.get("name", "")
                        value = c.get("value", "")
                        lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{cname}\t{value}")
                    
                    with open("youtube_cookies.txt", "w", encoding="utf-8") as f:
                        f.write("\n".join(lines))
                    print(f"[AUTH] Exported {len(cookies)} cookies to youtube_cookies.txt for yt-dlp")
                except Exception as e:
                    print(f"[AUTH] Failed to export cookies: {e}")

            else:
                login_jobs[job_id]["status"] = "TIMEOUT"
                login_jobs[job_id]["detail"] = "Login was not completed (browser closed)."

            await context.close()

    except Exception as e:
        login_jobs[job_id]["status"] = "ERROR"
        login_jobs[job_id]["detail"] = f"Login failed: {str(e)}"
    finally:
        if virtual_display:
            try:
                await virtual_display.release()
            except Exception:
                pass
        if job_id in login_jobs:
            login_jobs[job_id]["vnc_active"] = False


def start_google_login_job() -> str:
    """Kick off a browser-based Google login.  Returns job_id for polling."""
    job_id = str(uuid.uuid4())[:8]
    login_jobs[job_id] = {
        "job_id": job_id,
        "status": "STARTING",
        "detail": "",
        "updated_at": time.time(),
    }

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run_google_login(job_id))
    except RuntimeError:
        import threading
        threading.Thread(
            target=lambda: asyncio.run(_run_google_login(job_id)), daemon=True
        ).start()

    return job_id


# ---------------------------------------------------------------------------
# Platform uploaders
# ---------------------------------------------------------------------------

def _is_tiktok_cookies_valid(account: str) -> bool:
    """Check if TikTok cookies file exists and is not expired."""
    cookie_file = Path(f"TK_cookies_{account}.json")
    if not cookie_file.is_file():
        # Fallback to standard TK_cookies.json if it exists and account is default
        if account == "default" and Path("TK_cookies.json").is_file():
            cookie_file = Path("TK_cookies.json")
        else:
            return False
            
    try:
        cookies = json.loads(cookie_file.read_text(encoding="utf-8"))
        if not isinstance(cookies, list) or len(cookies) == 0:
            return False
        
        current_time = int(time.time())
        cookies_expire = []
        for cookie in cookies:
            if cookie.get("name") in ["sessionid", "sid_tt", "sessionid_ss", "passport_auth_status"]:
                expiry = cookie.get("expires")
                if not expiry:
                    expiry = cookie.get("expirationDate")
                if expiry:
                    cookies_expire.append(expiry < current_time)
                    
        if cookies_expire and all(cookies_expire):
            return False
        return True
    except Exception:
        return False


async def _publish_tiktok(
    job_id: str,
    video_path: str,
    caption: str,
    hashtags: list[str],
    account: str = "default",
    save_as_draft: bool = False,
    headless: bool = False,
):
    """Upload to TikTok using the tiktokautouploader pip package."""
    _set_status(job_id, "LAUNCHING", "Importing tiktokautouploader…")
    try:
        import sys
        import inspect
        # Force reload modules to pick up local changes dynamically
        for mod in list(sys.modules.keys()):
            if mod.startswith("tiktokautouploader"):
                del sys.modules[mod]

        from tiktokautouploader import upload_tiktok  # type: ignore

        # Detect headless server environment
        on_server = _is_headless_server()
        virtual_display = None
        if on_server:
            try:
                virtual_display = await VirtualDisplay.get_instance()
                headless = False  # Run visible on virtual display for VNC streaming
                if job_id in publish_jobs:
                    publish_jobs[job_id]["vnc_active"] = virtual_display.is_vnc_ready
                    publish_jobs[job_id]["vnc_ws_port"] = virtual_display.ws_port
            except Exception:
                headless = True
                if job_id in publish_jobs:
                    publish_jobs[job_id]["vnc_active"] = False

        # Prepare the cookie files from database, falling back to env var if needed
        from database import db
        user_cookies = db.get_cookies(account, "tiktok")
        
        if user_cookies:
            try:
                # Write to all standard expected paths for the uploader
                for name in ["TK_cookies.json", f"TK_cookies_{account}.json", "TK_cookies_default.json"]:
                    with open(name, "w", encoding="utf-8") as f:
                        f.write(json.dumps(user_cookies))
            except Exception as e:
                print("Failed to write database cookies to disk:", e)
        else:
            # Fallback to the environment variable TIKTOK_COOKIES
            tiktok_cookies_env = os.environ.get("TIKTOK_COOKIES")
            if tiktok_cookies_env:
                try:
                    # Validate JSON then write it
                    cookies_list = json.loads(tiktok_cookies_env)
                    # Cache/seed it into the database for this user
                    db.save_cookies(account, "tiktok", cookies_list)
                    
                    for name in ["TK_cookies.json", f"TK_cookies_{account}.json", "TK_cookies_default.json"]:
                        with open(name, "w", encoding="utf-8") as f:
                            f.write(tiktok_cookies_env)
                except Exception as e:
                    print("Failed to parse TIKTOK_COOKIES env var:", e)

        # Check if we have valid cookies on headless server
        if on_server:
            if not _is_tiktok_cookies_valid(account):
                if not virtual_display:
                    _set_status(
                        job_id,
                        "ERROR",
                        "TikTok cookies are missing or have expired. Please log in locally to extract fresh cookies and update the TIKTOK_COOKIES environment variable in your Railway dashboard."
                    )
                    return
                else:
                    _set_status(job_id, "WAITING_LOGIN", "Please log in to TikTok in the browser window…")
                    from phantomwright_driver.async_api import async_playwright
                    async with async_playwright() as pw:
                        browser = await pw.chromium.launch(
                            headless=False,
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--no-sandbox",
                                "--disable-infobars",
                                "--disable-dev-shm-usage",
                                "--disable-gpu",
                            ]
                        )
                        context = await browser.new_context(
                            viewport={"width": 1920, "height": 1080},
                            locale="en-US",
                            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        )
                        await context.add_init_script(_STEALTH_SCRIPT)
                        page = await context.new_page()
                        
                        if job_id in publish_jobs:
                            publish_jobs[job_id]["_page"] = page
                            
                        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
                        
                        logged_in = False
                        while not page.is_closed():
                            await page.wait_for_timeout(1000)
                            try:
                                cookies = await context.cookies()
                                has_session = any(c.get("name") in ["sessionid", "sessionid_ss", "sid_tt"] for c in cookies)
                                if has_session and "login" not in page.url.lower():
                                    logged_in = True
                                    db.save_cookies(account, "tiktok", cookies)
                                    cookies_str = json.dumps(cookies)
                                    for name in ["TK_cookies.json", f"TK_cookies_{account}.json", "TK_cookies_default.json"]:
                                        with open(name, "w", encoding="utf-8") as f:
                                            f.write(cookies_str)
                                    break
                            except Exception:
                                pass
                                
                        if job_id in publish_jobs:
                            publish_jobs[job_id].pop("_page", None)
                        await browser.close()
                        
                        if not logged_in:
                            _set_status(job_id, "ERROR", "TikTok login was not completed (browser closed).")
                            return

        _set_status(job_id, "UPLOADING", "Browser opening for TikTok upload…")

        # Inspect signature to resolve dynamic kwargs (safely handles package version differences)
        sig = inspect.signature(upload_tiktok)
        kwargs = {
            "video": video_path,
            "description": caption,
            "accountname": account,
        }
        if "hashtags" in sig.parameters:
            kwargs["hashtags"] = hashtags or []
        if "headless" in sig.parameters:
            kwargs["headless"] = headless

        # tiktokautouploader is synchronous – run in a thread
        loop = asyncio.get_running_loop()
        
        import threading
        _thread_local = threading.local()
        
        import tiktokautouploader.function
        def monkeypatched_submit(page, schedule, stealth, suppressprint, post_success_wait, schedule_success_wait):
            is_draft = getattr(_thread_local, 'save_as_draft', False)
            is_headless = getattr(_thread_local, 'headless', True)
            
            if is_draft:
                if not suppressprint:
                    print("Monkeypatch: Saving as draft instead of posting...")
                try:
                    page.click('button:has-text("Save draft")', timeout=10000)
                except Exception:
                    pass
                if not suppressprint:
                    print("Draft saved!")
            else:
                try:
                    page.click('button:has-text("Post")[data-e2e="post_video_button"]', timeout=2000)
                except Exception:
                    try:
                        page.click('button:has-text("Post")[aria-disabled="false"]', timeout=2000, force=True)
                    except Exception:
                        pass
                
                # Check for copyright modal
                try:
                    modal_post = page.locator('button:has-text("Post now")')
                    if modal_post.is_visible(timeout=3000):
                        modal_post.click()
                except Exception:
                    pass

            if not is_headless:
                if not suppressprint:
                    print("Monkeypatch: Leaving browser open for user to review...")
                import time
                while not page.is_closed():
                    try:
                        time.sleep(1)
                    except Exception:
                        break
            else:
                page.close()
            
            return None

        tiktokautouploader.function._submit_upload = monkeypatched_submit

        def run_tiktok():
            _thread_local.save_as_draft = save_as_draft
            _thread_local.headless = headless
            return upload_tiktok(**kwargs)

        await loop.run_in_executor(
            None,
            run_tiktok,
        )

        # Mark cookie directory as existing (the package manages its own cookies)
        cookie_dir = SESSIONS_DIR / "tiktok" / account
        cookie_dir.mkdir(parents=True, exist_ok=True)
        (cookie_dir / "cookies.json").write_text(
            json.dumps({"source": "tiktokautouploader", "ts": time.time()})
        )

        _set_status(job_id, "PUBLISHED", "Successfully uploaded to TikTok ✓")
    except ImportError:
        _set_status(
            job_id,
            "ERROR",
            "tiktokautouploader not installed. Run: pip install tiktokautouploader",
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        _set_status(job_id, "ERROR", f"TikTok upload failed: {exc}")
    finally:
        if virtual_display:
            try:
                await virtual_display.release()
            except Exception:
                pass
        if job_id in publish_jobs:
            publish_jobs[job_id]["vnc_active"] = False


async def _publish_playwright(
    job_id: str,
    platform: str,
    video_path: str,
    caption: str,
    account: str = "default",
    save_as_draft: bool = False,
    headless: bool = False,
):
    """Upload using Playwright with the persistent Google browser profile."""
    _set_status(job_id, "LAUNCHING", f"Starting browser for {platform}…")
    try:
        from phantomwright_driver.async_api import async_playwright  # type: ignore
    except ImportError:
        _set_status(
            job_id,
            "ERROR",
            "Playwright not installed. Run: pip install playwright && playwright install chromium",
        )
        return

    virtual_display = None
    try:
        # Detect headless server environment
        on_server = _is_headless_server()

        if on_server:
            # Start the virtual display so we can run the browser non-headless
            # and stream it to the user via noVNC
            try:
                virtual_display = await VirtualDisplay.get_instance()
                headless = False  # Run non-headless on the virtual display!
                # Store VNC info in the job so the frontend can connect
                if job_id in publish_jobs:
                    publish_jobs[job_id]["vnc_active"] = virtual_display.is_vnc_ready
                    publish_jobs[job_id]["vnc_ws_port"] = virtual_display.ws_port
                _set_status(job_id, "LAUNCHING", f"Virtual display ready — launching visible browser for {platform}…")
            except Exception as vd_err:
                print(f"[VNC] Failed to start virtual display: {vd_err}. Falling back to headless.")
                headless = True
                if job_id in publish_jobs:
                    publish_jobs[job_id]["vnc_active"] = False

        # Prepare user cookies from database, falling back to environment variables
        from database import db
        user_cookies = db.get_cookies(account, platform)
        
        if not user_cookies:
            env_cookies_str = os.environ.get(f"{platform.upper()}_COOKIES")
            if env_cookies_str:
                try:
                    user_cookies = json.loads(env_cookies_str)
                    # Cache/seed into database for this user
                    db.save_cookies(account, platform, user_cookies)
                except Exception as e:
                    print(f"Failed to parse {platform.upper()}_COOKIES env var:", e)

        # Check if we have dynamic cookies or local persistent context fallback
        if not user_cookies and on_server and not virtual_display:
            _set_status(
                job_id,
                "ERROR",
                f"No active session found for {PLATFORMS.get(platform, {}).get('name', platform)} (User ID: '{account}'). "
                f"Please sync your account session using the You-Tik Chrome Extension or configure the {platform.upper()}_COOKIES environment variable in your Railway dashboard."
            )
            return

        async with async_playwright() as pw:
            browser = None
            if user_cookies:
                # Ephemeral, isolated browser context for this specific user
                _set_status(job_id, "LAUNCHING", f"Launching clean ephemeral browser for {platform}…")
                browser = await pw.chromium.launch(
                    headless=headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                )
                # Sanitize cookies for Playwright compatibility
                sanitized_cookies = []
                for cookie in user_cookies:
                    # Construct clean cookie compatible with Playwright
                    c = {
                        "name": str(cookie.get("name", "")),
                        "value": str(cookie.get("value", "")),
                        "domain": str(cookie.get("domain", "")),
                        "path": str(cookie.get("path", "/")),
                    }
                    
                    expires = cookie.get("expires")
                    if expires is not None:
                        try:
                            c["expires"] = float(expires)
                        except (ValueError, TypeError):
                            pass
                            
                    if "httpOnly" in cookie:
                        c["httpOnly"] = bool(cookie["httpOnly"])
                    if "secure" in cookie:
                        c["secure"] = bool(cookie["secure"])
                        
                    # Sanitize sameSite to case-sensitive Strict | Lax | None
                    same_site = cookie.get("sameSite")
                    if same_site:
                        same_site_str = str(same_site).lower()
                        if same_site_str == "no_restriction":
                            c["sameSite"] = "None"
                        elif same_site_str in ["lax", "strict", "none"]:
                            c["sameSite"] = same_site_str.capitalize()
                        else:
                            # Skip invalid sameSite properties to let browser handle them
                            pass
                    sanitized_cookies.append(c)

                await context.add_cookies(sanitized_cookies)
            else:
                # Local headed fallback (Persistent Profile Mode)
                _set_status(job_id, "LAUNCHING", f"Launching local persistent profile browser for {platform}…")
                profile_dir = str(GOOGLE_PROFILE_DIR)
                context = await pw.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    headless=headless,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                    viewport={"width": 1920, "height": 1080},
                    locale="en-US",
                )

            await context.add_init_script(_STEALTH_SCRIPT)

            page = context.pages[0] if context.pages else await context.new_page()

            # Store the page reference for live screenshots
            if job_id in publish_jobs:
                publish_jobs[job_id]["_page"] = page

            try:
                if platform == "youtube":
                    await _upload_youtube(job_id, page, video_path, caption, save_as_draft, headless)
                elif platform == "instagram":
                    await _upload_instagram(job_id, page, video_path, caption, headless)
                elif platform == "twitter":
                    await _upload_twitter(job_id, page, video_path, caption, headless)
                
                # Extract and save updated cookies so the VNC session persists
                try:
                    updated_cookies = await context.cookies()
                    db.save_cookies(account, platform, updated_cookies)
                    print(f"[{platform}] Extracted and saved updated cookies to database for account '{account}'.")
                except Exception as e:
                    print(f"[{platform}] Failed to save updated cookies: {e}")
                
                # Success path - keep open if visible (local or VNC)
                if not headless:
                    _set_status(job_id, "PUBLISHED", f"Successfully uploaded to {PLATFORMS.get(platform, {}).get('name', platform)}! Browser visible for verification.")
                    # Keep open forever until VNC/browser closes
                    while not page.is_closed():
                        try:
                            await asyncio.sleep(1)
                        except Exception:
                            break
                else:
                    _set_status(job_id, "PUBLISHED", f"Successfully uploaded to {PLATFORMS.get(platform, {}).get('name', platform)} ✓")
            except Exception as upload_exc:
                print(f"[{platform}] Upload script error: {upload_exc}")
                # Error path - keep open if visible
                if not headless:
                    _set_status(job_id, "ERROR", f"{platform} upload failed: {upload_exc}. Browser kept open for review.")
                    while not page.is_closed():
                        try:
                            await asyncio.sleep(1)
                        except Exception:
                            break
                else:
                    # Headless error path
                    _set_status(job_id, "ERROR", f"{platform} upload failed: {upload_exc}")
                    raise upload_exc

            # Clean up page reference
            if job_id in publish_jobs:
                publish_jobs[job_id].pop("_page", None)

            if browser:
                await browser.close()
            else:
                await context.close()

    except Exception as exc:
        import traceback
        traceback.print_exc()
        _set_status(job_id, "ERROR", f"{platform.title()} upload failed: {str(exc)}")
    finally:
        # Release the virtual display when done
        if virtual_display:
            try:
                await virtual_display.release()
            except Exception:
                pass
        # Clean up VNC flags
        if job_id in publish_jobs:
            publish_jobs[job_id]["vnc_active"] = False
            publish_jobs[job_id].pop("_page", None)


async def _upload_youtube(job_id, page, video_path, caption, save_as_draft=False, headless=False):
    """Navigate YouTube Studio and upload a Short."""
    _set_status(job_id, "AUTHENTICATING", "Navigating to YouTube Studio…")
    await page.goto("https://studio.youtube.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    # Check if logged in
    if "accounts.google.com" in page.url:
        if headless:
            raise Exception("YouTube session has expired or is invalid. Please log in locally, sync fresh cookies, and update the YOUTUBE_COOKIES environment variable in your Railway dashboard.")
            
        _set_status(
            job_id,
            "WAITING_LOGIN",
            "Please log in to your Google account in the browser window…",
        )
        # Wait indefinitely for the user to log in
        while not page.is_closed():
            await page.wait_for_timeout(1000)
            if "studio.youtube.com" in page.url and "accounts.google.com" not in page.url:
                break

        if "accounts.google.com" in page.url:
            raise Exception("Google sign-in was not completed (browser closed).")
            
        _set_status(job_id, "UPLOADING", "Login successful! Waiting for dashboard to load…")
        await page.wait_for_timeout(5000)

    _set_status(job_id, "UPLOADING", "Uploading video to YouTube Shorts…")

    try:
        # Check if we are on the dashboard and there is a center "Upload videos" button (empty channel state)
        center_upload_btn = page.locator("ytcp-button#upload-button, ytcp-button:has-text('Upload videos')").first
        
        if await center_upload_btn.is_visible(timeout=3000):
            _set_status(job_id, "UPLOADING", "Using central upload button…")
            await center_upload_btn.click()
        else:
            # Otherwise, use the standard Create button in the top right
            _set_status(job_id, "UPLOADING", "Clicking top-right Create button…")
            create_btn = page.locator("ytcp-button#create-icon-button, #create-icon-button, [aria-label='Create']").first
            await create_btn.click(timeout=10000)
            await page.wait_for_timeout(1500)

            upload_item = page.locator("tp-yt-paper-item:has-text('Upload videos'), ytcp-paper-item:has-text('Upload videos'), text=Upload videos").first
            await upload_item.click(timeout=5000)
            
        await page.wait_for_timeout(2000)

        # Upload the file
        _set_status(job_id, "UPLOADING", "Selecting video file…")
        file_input = page.locator("input[type='file']").first
        await file_input.wait_for(state="attached", timeout=10000)
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(3000)

        # Set title/description
        _set_status(job_id, "UPLOADING", "Setting video details…")
        title_input = page.locator("#textbox").first
        await title_input.wait_for(state="visible", timeout=15000)
        if title_input:
            await title_input.fill(caption[:100])

        _set_status(job_id, "UPLOADING", "Video uploading, waiting for processing…")
        
        # Select "Not made for kids" (YouTube requires this)
        try:
            not_for_kids_radio = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS'], tp-yt-paper-radio-button:has-text('No, it\\'s not made for kids')").first
            await not_for_kids_radio.click(timeout=5000)
        except Exception as kids_exc:
            print(f"Could not select 'not made for kids' automatically: {kids_exc}")

        # Navigate through the next steps (Details -> Video elements -> Checks -> Visibility)
        _set_status(job_id, "UPLOADING", "Navigating to Visibility step…")
        
        reached_visibility = False
        for step in range(5):
            # Check if any of the visibility radio options are visible on the page
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC'], tp-yt-paper-radio-button[name='PRIVATE'], tp-yt-paper-radio-button[name='UNLISTED']").first
            if await public_radio.is_visible(timeout=2000):
                reached_visibility = True
                _set_status(job_id, "UPLOADING", "Reached visibility options.")
                break
                
            next_btn = page.locator("#next-button, ytcp-button#next-button, button:has-text('Next')").first
            if await next_btn.is_visible(timeout=3000):
                is_disabled = await next_btn.get_attribute("disabled")
                if is_disabled is not None:
                    _set_status(job_id, "UPLOADING", "Waiting for Next button to be enabled…")
                    await page.wait_for_timeout(1000)
                    continue
                await next_btn.click(force=True)
                await page.wait_for_timeout(2000)
            else:
                await page.wait_for_timeout(1000)

        # Select visibility (Public vs Private/Unlisted)
        if save_as_draft:
            _set_status(job_id, "UPLOADING", "Selecting Private visibility (Save as Draft)…")
            private_radio = page.locator("tp-yt-paper-radio-button[name='PRIVATE'], #private-radio-button").first
            if await private_radio.is_visible(timeout=5000):
                await private_radio.click(force=True)
        else:
            _set_status(job_id, "UPLOADING", "Selecting Public visibility…")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC'], #public-radio-button").first
            if await public_radio.is_visible(timeout=5000):
                await public_radio.click(force=True)

        await page.wait_for_timeout(1500)

        # Click the done/publish button
        done_btn = page.locator("#done-button, ytcp-button#done-button, ytcp-button:has-text('Save'), ytcp-button:has-text('Publish')").first
        if await done_btn.is_visible(timeout=5000):
            if not headless:
                _set_status(job_id, "UPLOADING", "Ready to save/publish! Browser is staying open so you can watch the upload and close the window when done.")
                import asyncio
                while not page.is_closed():
                    await asyncio.sleep(1)
                return

            await done_btn.click(force=True)
            
            # CRITICAL: Wait for upload transfer to complete before closing browser!
            _set_status(job_id, "UPLOADING", "Waiting for video transfer to finish... Please wait.")
            
            # YouTube shows a share/confirmation dialog when upload is finished. 
            # If not, wait for the uploads-dialog to hide, meaning it's fully done.
            try:
                # Wait up to 600 seconds for the dialog to disappear or confirmation to show
                await page.wait_for_selector("ytcp-video-share-dialog, ytcp-uploads-dialog[hidden]", timeout=600000)
                
                # If share dialog appeared, close it
                close_btn = page.locator("ytcp-button#close-button, ytcp-button:has-text('Close')").first
                if await close_btn.is_visible(timeout=2000):
                    await close_btn.click(force=True)
            except Exception:
                # Fallback: wait extra time to let network finish
                await page.wait_for_timeout(10000)
                
            _set_status(job_id, "PUBLISHED", "Video successfully uploaded and saved to YouTube Shorts!")
        else:
            await page.wait_for_timeout(5000)

    except Exception as e:
        _set_status(job_id, "ERROR", f"YouTube upload failed: {e}")
        raise e


async def _upload_instagram(job_id, page, video_path, caption, headless=False):
    """Navigate Instagram and create a Reel."""
    _set_status(job_id, "AUTHENTICATING", "Navigating to Instagram…")
    await page.goto("https://www.instagram.com", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    if "login" in page.url.lower():
        if headless:
            raise Exception("Instagram session has expired or is invalid. Please update the INSTAGRAM_COOKIES environment variable in your Railway dashboard.")
            
        _set_status(
            job_id,
            "WAITING_LOGIN",
            "Please log in to Instagram in the browser window…",
        )
        while not page.is_closed():
            await page.wait_for_timeout(1000)
            if "login" not in page.url.lower():
                break

        if "login" in page.url.lower():
            raise Exception("Instagram sign-in was not completed (browser closed).")

    _set_status(job_id, "UPLOADING", "Creating new Reel on Instagram…")

    try:
        # Click the new post button
        new_post = page.locator("[aria-label='New post']").first
        await new_post.click(timeout=10000)
        await page.wait_for_timeout(2000)

        file_input = page.locator("input[type='file']").first
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(3000)

        _set_status(job_id, "UPLOADING", "Video selected! Please complete the upload manually.")
        if headless:
            await page.wait_for_timeout(60000)
    except Exception as e:
        _set_status(job_id, "UPLOADING", f"Manual upload may be needed: {e}")
        if headless:
            await page.wait_for_timeout(60000)


async def _upload_twitter(job_id, page, video_path, caption, headless=False):
    """Navigate X/Twitter and compose a tweet with video."""
    _set_status(job_id, "AUTHENTICATING", "Navigating to X.com…")
    await page.goto("https://x.com/compose/post", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    if "login" in page.url.lower() or "flow" in page.url.lower():
        if headless:
            raise Exception("X/Twitter session has expired or is invalid. Please update the TWITTER_COOKIES environment variable in your Railway dashboard.")
            
        _set_status(
            job_id,
            "WAITING_LOGIN",
            "Please log in to X/Twitter in the browser window…",
        )
        while not page.is_closed():
            await page.wait_for_timeout(1000)
            if "compose" in page.url.lower() or "home" in page.url.lower():
                break

        if "login" in page.url.lower() or "flow" in page.url.lower():
            raise Exception("X/Twitter sign-in was not completed (browser closed).")

    _set_status(job_id, "UPLOADING", "Composing post with video…")

    try:
        # Type the caption
        text_area = page.locator("[data-testid='tweetTextarea_0']").first
        if text_area:
            await text_area.fill(caption[:280])

        # Attach the video
        file_input = page.locator("input[type='file']").first
        await file_input.set_input_files(video_path)
        await page.wait_for_timeout(5000)

        _set_status(job_id, "UPLOADING", "Media attached! Please complete the post manually.")
        if headless:
            await page.wait_for_timeout(60000)
    except Exception as e:
        _set_status(job_id, "UPLOADING", f"Manual posting may be needed: {e}")
        if headless:
            await page.wait_for_timeout(60000)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_publish_job(
    video_path: str,
    platform: str,
    caption: str = "",
    hashtags: Optional[list[str]] = None,
    account: str = "default",
    save_as_draft: bool = False,
    headless: bool = False,
) -> str:
    """
    Kick off a background publish job.  Returns the job_id which the caller
    can use to poll status via ``publish_jobs[job_id]``.
    """
    _ensure_session_dirs()

    job_id = str(uuid.uuid4())[:8]
    publish_jobs[job_id] = {
        "job_id": job_id,
        "platform": platform,
        "video_path": video_path,
        "status": "QUEUED",
        "detail": "",
        "created_at": time.time(),
        "updated_at": time.time(),
    }

    async def _run():
        if platform == "tiktok":
            await _publish_tiktok(job_id, video_path, caption, hashtags or [], account, save_as_draft, headless)
        else:
            await _publish_playwright(job_id, platform, video_path, caption, account, save_as_draft, headless)

    # Schedule the coroutine in the running event loop (FastAPI is async)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_run())
    except RuntimeError:
        # Fallback: no running loop, start one in a thread
        import threading
        threading.Thread(target=lambda: asyncio.run(_run()), daemon=True).start()

    return job_id
