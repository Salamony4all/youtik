import os
import yt_dlp
import json
import torch
import subprocess
from typing import Dict, Optional
import gc
import shutil
import time
import uuid
import glob
import re
import traceback
from huggingface_hub import snapshot_download

# Ensure the local models directory exists
os.makedirs("./models", exist_ok=True)

def resolve_hf_path(base_path):
    """Recursively finds the actual model files inside a HuggingFace cache folder."""
    if not os.path.isdir(base_path):
        return base_path
    
    print(f"[DEBUG] Hunting for model files in: {os.path.abspath(base_path)}")
    
    for root, dirs, files in os.walk(base_path):
        has_config = "config.json" in files
        has_weights = any(f in files for f in ["model.bin", "pytorch_model.bin", "model.safetensors", "model.pth"])
        if has_config or has_weights:
            resolved_path = os.path.abspath(root)
            print(f"[DEBUG] Found model root at: {resolved_path}")
            return resolved_path
                
    print(f"[DEBUG] No model files found in {base_path}, returning base.")
    return base_path


def find_local_model_path(model_id: str) -> str | None:
    """Resolve a model identifier to a local ./models directory if available."""
    if not model_id:
        return None

    aliases = {
        "stable-MAdel121/whisper-small-egyptian-arabic": "./models/MAdel121--whisper-small-egyptian-arabic",
        "stable-MAdel121/whisper-medium-egyptian-arabic": "./models/MAdel121--whisper-medium-egy",
        "stable-IbrahimAmin/code-switched-egyptian-arabic-whisper-small": "./models/IbrahimAmin--code-switched-egyptian-arabic-whisper-small",
        "stable-moeshawky/whisper-small-egyptian-arabic": "./models/models--moeshawky--faster-whisper-small-egyptian-arabic",
        "stable-Systran/faster-whisper-base": "./models/models--Systran--faster-whisper-base",
        "stable-Systran/faster-whisper-large-v3": "./models/models--Systran--faster-whisper-large-v3",
        "x-large-v3-turbo": "./models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
        "large-v3-turbo": "./models/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo",
        "stable-tarteel-ai/whisper-small-ar-egyptian": "./models/MAdel121--whisper-small-egyptian-arabic"
    }

    if model_id in aliases and os.path.isdir(aliases[model_id]):
        return aliases[model_id]

    candidate_id = model_id
    if candidate_id.startswith("stable-"):
        candidate_id = candidate_id[7:]
    if candidate_id.startswith("faster-"):
        candidate_id = candidate_id[7:]
    if candidate_id.startswith("x-"):
        candidate_id = candidate_id[2:]
    if candidate_id == "whisperx":
        candidate_id = "moeshawky/whisper-small-egyptian-arabic"

    if "moeshawky" in candidate_id and "faster-" not in candidate_id:
        candidate_id = candidate_id.replace("whisper-", "faster-whisper-")

    owner_repo = candidate_id.replace("/", "--")
    possible_paths = [
        os.path.join("./models", owner_repo),
        os.path.join("./models", f"models--{owner_repo}")
    ]

    for p in possible_paths:
        if os.path.isdir(p):
            return p

    tokens = [t for t in re.sub(r'[^a-z0-9]+', ' ', owner_repo.lower()).split() if t]
    if tokens and os.path.exists("./models"):
        for entry in os.listdir("./models"):
            entry_path = os.path.join("./models", entry)
            if not os.path.isdir(entry_path):
                continue
            entry_tokens = [t for t in re.sub(r'[^a-z0-9]+', ' ', entry.lower()).split() if t]
            if all(token in entry_tokens for token in tokens):
                return entry_path

    return None


def cleanup_old_sessions(base_temp_dir: str = "./temp", max_age_hours: int = 2):
    if not os.path.exists(base_temp_dir):
        return
        
    current_time = time.time()
    for folder in os.listdir(base_temp_dir):
        folder_path = os.path.join(base_temp_dir, folder)
        if os.path.isdir(folder_path):
            folder_age = current_time - os.path.getctime(folder_path)
            if folder_age > (max_age_hours * 3600):
                try:
                    shutil.rmtree(folder_path, ignore_errors=True)
                    print(f"Cleaned up old session: {folder}")
                except PermissionError:
                    pass

def cleanup_temp_folder(temp_dir: str, max_retries: int = 3, delay: float = 1.0):
    gc.collect()
    if not os.path.exists(temp_dir):
        return

    for attempt in range(max_retries):
        try:
            shutil.rmtree(temp_dir)
            print(f"Successfully cleaned: {temp_dir}")
            break 
        except PermissionError as e:
            if attempt < max_retries - 1:
                print(f"File locked. Retrying cleanup in {delay}s... ({attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"Warning: Could not completely clean temp folder due to persistent lock: {e}")

def parse_cookies_string_to_netscape(cookie_str: str, log_fn=None) -> str:
    """
    Robustly parses a cookie string from environment variables or files.
    Supports: Base64 decoding, JSON formats, Netscape format, and unescaping of newlines/tabs.
    """
    def log(msg):
        print(msg)
        if log_fn:
            log_fn(msg)
            
    cookie_str = cookie_str.strip()
    if not cookie_str:
        return ""
        
    # Normalize carriage returns and newlines at the very start
    cookie_str = cookie_str.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Check for Base64 encoding
    try:
        import base64
        cleaned_b64 = "".join(cookie_str.split())
        decoded = base64.b64decode(cleaned_b64).decode('utf-8', errors='ignore')
        decoded = decoded.replace("\r\n", "\n").replace("\r", "\n")
        # If it looks like JSON or Netscape format, adopt the decoded text
        if "youtube.com" in decoded or "Netscape" in decoded or decoded.strip().startswith("["):
            cookie_str = decoded.strip()
            log("[COOKIES] Successfully decoded Base64 cookie string.")
    except Exception:
        pass

    # 2. Unescape newlines and tabs (crucial for Render env vars where users cannot easily paste newlines)
    cookie_str = cookie_str.replace("\\n", "\n").replace("\\t", "\t")
    cookie_str = cookie_str.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Check for JSON format
    if cookie_str.startswith("["):
        try:
            cookies = json.loads(cookie_str)
            lines = [
                "# Netscape HTTP Cookie File",
                "# http://curl.haxx.se/rfc/cookie_spec.html",
                "# This is a generated file! Do not edit.\n"
            ]
            for c in cookies:
                domain = c.get("domain", "")
                include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
                path = c.get("path", "/")
                secure_val = c.get("secure")
                secure = "TRUE" if secure_val in [True, "TRUE", "true"] else "FALSE"
                
                # Check different expiration fields
                expires_val = c.get("expires") or c.get("expirationDate") or c.get("expiry") or 0
                try:
                    expires = int(float(expires_val))
                except Exception:
                    expires = 0
                    
                name = c.get("name", "")
                value = c.get("value", "")
                
                lines.append(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
                
            cookie_str = "\n".join(lines) + "\n"
            log("[COOKIES] Successfully parsed and converted JSON cookies format to Netscape.")
        except Exception as json_err:
            log(f"[WARNING] Tried parsing cookies as JSON but failed: {json_err}")

    # 4. Diagnostics & Validation
    domains = set()
    youtube_found = False
    for line in cookie_str.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split("\t")
            if len(parts) >= 6:
                domain = parts[0]
                domains.add(domain)
                if "youtube.com" in domain:
                    youtube_found = True
                    
    log(f"[COOKIES] Cookie string length: {len(cookie_str)} characters.")
    if domains:
        log(f"[COOKIES] Parsed {len(domains)} distinct domains: {', '.join(sorted(list(domains))[:10])}...")
    else:
        log("[WARNING] No valid domains parsed from the cookie string.")
        
    if not youtube_found:
        log("[WARNING] '.youtube.com' domain keys were NOT found in the loaded cookies! Ingestion may fail.")
    else:
        log("[COOKIES] Valid '.youtube.com' keys detected in loaded cookies!")
        
    # Ensure final output has strictly internal \n newlines and no \r carriage returns
    cookie_str = cookie_str.replace("\r\n", "\n").replace("\r", "\n")
    return cookie_str


def convert_playwright_cookies(json_path: str, txt_path: str, log_fn=None) -> bool:
    """Converts Playwright JSON cookies format to standard Netscape cookies format."""
    def log(msg):
        print(msg)
        if log_fn:
            log_fn(msg)
    try:
        if not os.path.exists(json_path):
            return False
        with open(json_path, 'r', encoding='utf-8') as f:
            cookie_str = f.read()
        netscape_content = parse_cookies_string_to_netscape(cookie_str, log_fn=log_fn)
        if not netscape_content:
            return False
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        # Force Unix newlines on Unix/Linux, and Windows newlines on Windows
        out_newline = "\r\n" if os.name == "nt" else "\n"
        with open(txt_path, 'w', encoding='utf-8', newline=out_newline) as f:
            f.write(netscape_content)
        log(f"[COOKIES] Successfully converted Playwright cookies from {json_path} to Netscape {txt_path}")
        return True
    except Exception as e:
        log(f"[WARNING] Playwright cookies conversion failed: {e}")
        return False


def download_via_playwright(url: str, output_wav_path: str, log_fn=None) -> bool:
    """
    Fallback download method using Playwright headless browser.
    Bypasses YouTube bot detection by running a real browser with JavaScript
    execution (solves BotGuard/PO tokens natively).
    
    Uses the same Google persistent profile from publisher.py for authentication.
    Returns True on success, False on failure.
    """
    import subprocess
    
    def log(msg):
        print(msg)
        if log_fn:
            log_fn(msg)

    log("[FALLBACK] yt-dlp failed due to bot detection. Attempting Playwright browser download...")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("[FALLBACK] Playwright not installed — cannot use browser fallback.")
        return False

    SESSIONS_DIR = os.path.join(".", "sessions")
    GOOGLE_PROFILE_DIR = os.path.join(SESSIONS_DIR, "google_profile")

    # Determine if we can use a persistent Google profile or need cookies
    has_google_profile = os.path.exists(GOOGLE_PROFILE_DIR) and bool(os.listdir(GOOGLE_PROFILE_DIR))
    env_cookies = os.environ.get("YOUTUBE_COOKIES", "")

    if not has_google_profile and not env_cookies:
        log("[FALLBACK] No Google browser profile and no YOUTUBE_COOKIES env var. Cannot authenticate.")
        log("[FALLBACK] Set YOUTUBE_COOKIES in Railway dashboard or sign in via the Publish panel locally.")
        return False

    STEALTH_SCRIPT = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        window.navigator.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """

    output_dir = os.path.dirname(output_wav_path)
    temp_video = os.path.join(output_dir, "pw_download_temp.mp4")
    captured_url = {"audio": None, "video": None}

    def handle_response(response):
        """Intercept network responses to capture audio/video stream URLs."""
        url_str = response.url
        content_type = response.headers.get("content-type", "")
        
        # Look for audio streams (DASH audio segments)
        if "mime=audio" in url_str or "audio/mp4" in content_type or "audio/webm" in content_type:
            if not captured_url["audio"]:
                captured_url["audio"] = url_str
        # Also capture video as fallback
        elif "mime=video" in url_str and "itag=" in url_str:
            if not captured_url["video"]:
                captured_url["video"] = url_str

    try:
        with sync_playwright() as pw:
            context = None

            if has_google_profile:
                log("[FALLBACK] Launching Chromium with Google profile...")
                launch_kwargs = {
                    "user_data_dir": GOOGLE_PROFILE_DIR,
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                    "viewport": {"width": 1280, "height": 720},
                    "locale": "en-US",
                }
                proxy_url = os.environ.get("YOUTUBE_PROXY") or os.environ.get("PROXY_URL")
                if proxy_url:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(proxy_url)
                    server_address = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}" if parsed.port else f"{parsed.scheme}://{parsed.hostname}"
                    pw_proxy = {"server": server_address}
                    if parsed.username and parsed.password:
                        pw_proxy["username"] = parsed.username
                        pw_proxy["password"] = parsed.password
                    launch_kwargs["proxy"] = pw_proxy
                    log(f"[FALLBACK] Injecting proxy into Playwright: {server_address}")
                context = pw.chromium.launch_persistent_context(**launch_kwargs)
            else:
                log("[FALLBACK] No Google profile. Launching Chromium with YOUTUBE_COOKIES...")
                launch_kwargs = {
                    "headless": True,
                    "args": [
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                }
                proxy_url = os.environ.get("YOUTUBE_PROXY") or os.environ.get("PROXY_URL")
                if proxy_url:
                    import urllib.parse
                    parsed = urllib.parse.urlparse(proxy_url)
                    server_address = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}" if parsed.port else f"{parsed.scheme}://{parsed.hostname}"
                    pw_proxy = {"server": server_address}
                    if parsed.username and parsed.password:
                        pw_proxy["username"] = parsed.username
                        pw_proxy["password"] = parsed.password
                    launch_kwargs["proxy"] = pw_proxy
                    log(f"[FALLBACK] Injecting proxy into Playwright: {server_address}")
                browser = pw.chromium.launch(**launch_kwargs)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    locale="en-US",
                )

                # Parse and inject cookies from YOUTUBE_COOKIES env var
                try:
                    parsed = parse_cookies_string_to_netscape(env_cookies, log_fn=log_fn)
                    if parsed:
                        cookie_list = []
                        for line in parsed.strip().split("\n"):
                            if line.startswith("#") or not line.strip():
                                continue
                            parts = line.split("\t")
                            if len(parts) >= 7:
                                cookie_list.append({
                                    "name": parts[5],
                                    "value": parts[6],
                                    "domain": parts[0],
                                    "path": parts[2],
                                    "secure": parts[3].upper() == "TRUE",
                                    "httpOnly": False,
                                    "expires": float(parts[4]) if parts[4] != "0" else -1,
                                })
                        if cookie_list:
                            context.add_cookies(cookie_list)
                            log(f"[FALLBACK] Injected {len(cookie_list)} cookies into browser context.")
                except Exception as cookie_err:
                    log(f"[FALLBACK] Cookie injection failed: {cookie_err}")

            context.add_init_script(STEALTH_SCRIPT)
            page = context.pages[0] if context.pages else context.new_page()

            # Listen for network responses to capture stream URLs
            page.on("response", handle_response)

            log(f"[FALLBACK] Navigating to {url}...")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            # Try to click play button if video didn't autoplay
            try:
                play_btn = page.locator("button.ytp-large-play-button, button.ytp-play-button")
                if play_btn.count() > 0 and play_btn.first.is_visible():
                    play_btn.first.click()
                    log("[FALLBACK] Clicked play button.")
                    page.wait_for_timeout(5000)
            except Exception:
                pass

            # Try to extract the stream URL via YouTube's internal player API
            stream_url = None
            try:
                stream_url = page.evaluate("""
                    () => {
                        const player = document.getElementById('movie_player');
                        if (player && player.getVideoData) {
                            // Try to get the streaming data from ytInitialPlayerResponse
                            const data = window.ytInitialPlayerResponse;
                            if (data && data.streamingData) {
                                const formats = data.streamingData.adaptiveFormats || data.streamingData.formats || [];
                                // Find best audio-only format
                                const audio = formats.find(f => f.mimeType && f.mimeType.startsWith('audio/') && f.url);
                                if (audio) return audio.url;
                                // Fallback: any format with a URL
                                const any = formats.find(f => f.url);
                                if (any) return any.url;
                            }
                        }
                        return null;
                    }
                """)
            except Exception as eval_err:
                log(f"[FALLBACK] JS evaluation failed: {eval_err}")

            if stream_url:
                log("[FALLBACK] Extracted stream URL via YouTube player API.")
            elif captured_url["audio"]:
                stream_url = captured_url["audio"]
                log("[FALLBACK] Captured audio stream URL from network interception.")
            elif captured_url["video"]:
                stream_url = captured_url["video"]
                log("[FALLBACK] Captured video stream URL from network interception (no audio-only found).")

            if stream_url:
                # Download the stream using the browser's authenticated context
                log("[FALLBACK] Downloading stream via browser context...")
                try:
                    response = page.request.get(stream_url, timeout=120000)
                    if response.ok:
                        with open(temp_video, "wb") as f:
                            f.write(response.body())
                        log(f"[FALLBACK] Stream downloaded: {os.path.getsize(temp_video)} bytes")
                    else:
                        log(f"[FALLBACK] Stream download failed with status {response.status}")
                        context.close()
                        return False
                except Exception as dl_err:
                    log(f"[FALLBACK] Stream download error: {dl_err}")
                    context.close()
                    return False
            else:
                # Last resort: use page.video recording
                log("[FALLBACK] No stream URL found. Trying page audio capture...")
                
                # Use the page's cookies to call yt-dlp with browser cookies
                cookies = context.cookies()
                log(f"[FALLBACK] Extracted {len(cookies)} cookies from browser context.")
                
                # Write cookies to Netscape format for yt-dlp
                browser_cookie_path = os.path.join(output_dir, "browser_cookies.txt")
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
                    name = c.get("name", "")
                    value = c.get("value", "")
                    lines.append(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}")
                
                with open(browser_cookie_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                
                context.close()
                
                # Now retry yt-dlp with these fresh browser cookies
                log("[FALLBACK] Retrying yt-dlp with fresh browser-extracted cookies...")
                try:
                    import yt_dlp
                    audio_base = output_wav_path.replace(".wav", "")
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': f"{audio_base}.%(ext)s",
                        'noplaylist': True,
                        'cookiefile': browser_cookie_path,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'wav',
                            'preferredquality': '192',
                        }],
                        'quiet': False,
                        'extractor_args': {
                            'youtube': {
                                'player_client': ['web_creator', 'mweb', 'web']
                            }
                        },
                        'external_downloader_args': {
                            'ffmpeg_i': ['-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5']
                        }
                    }
                    proxy_url = os.environ.get("YOUTUBE_PROXY") or os.environ.get("PROXY_URL")
                    if proxy_url:
                        ydl_opts['proxy'] = proxy_url
                        log(f"[FALLBACK] Injecting proxy into retry yt-dlp: {proxy_url}")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    log("[FALLBACK] yt-dlp succeeded with browser-extracted cookies!")
                    return True
                except Exception as ytdlp_err:
                    log(f"[FALLBACK] yt-dlp retry also failed: {ytdlp_err}")
                    return False

            context.close()

        # Convert downloaded stream to WAV using ffmpeg
        if os.path.exists(temp_video) and os.path.getsize(temp_video) > 0:
            log("[FALLBACK] Converting downloaded stream to WAV...")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_video, "-vn", "-acodec", "pcm_s16le",
                     "-ar", "44100", "-ac", "2", output_wav_path],
                    check=True, capture_output=True, timeout=120
                )
                # Clean up temp video
                if os.path.exists(temp_video):
                    os.remove(temp_video)
                
                if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0:
                    log(f"[FALLBACK] Success! Audio saved to {output_wav_path} ({os.path.getsize(output_wav_path)} bytes)")
                    return True
                else:
                    log("[FALLBACK] FFmpeg produced an empty file.")
                    return False
            except subprocess.CalledProcessError as ffmpeg_err:
                log(f"[FALLBACK] FFmpeg conversion failed: {ffmpeg_err.stderr.decode()[:500]}")
                return False
        else:
            log("[FALLBACK] No media file was downloaded.")
            return False

    except Exception as e:
        log(f"[FALLBACK] Playwright download failed: {e}")
        import traceback
        log(f"[FALLBACK] Traceback: {traceback.format_exc()}")
        return False


def run_ingest_step(url: str, temp_dir: str, log_fn=None, custom_cookies: Optional[str] = None) -> tuple:
    def log(msg):
        print(msg)
        if log_fn:
            log_fn(msg)
            
    log(f"Starting ingest for: {url}")
    audio_base = os.path.join(temp_dir, "source_audio")
    
    # Locate best cookie source and content
    cookie_source = None
    raw_cookie_content = None
    
    # 0. Check request-provided custom cookies (Highest priority)
    if custom_cookies:
        raw_cookie_content = custom_cookies
        cookie_source = "request-provided custom cookies"
        log("[INGEST] Using custom cookies provided directly in the request.")
    
    # 1. Check root cookies files
    for root_cookie in ["youtube_cookies.txt", "cookies.txt"]:
        if os.path.exists(root_cookie):
            try:
                with open(root_cookie, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_cookie_content = f.read()
                cookie_source = f"workspace root file ({root_cookie})"
                log(f"[INGEST] Found YouTube cookies file in workspace root: {root_cookie}")
                break
            except Exception as e:
                log(f"[WARNING] Failed to read {root_cookie}: {e}")
                
    # 2. Check Playwright session cookies
    if not raw_cookie_content:
        pw_json = "sessions/youtube/default/cookies.json"
        if os.path.exists(pw_json):
            try:
                with open(pw_json, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_cookie_content = f.read()
                cookie_source = f"Playwright session cookies ({pw_json})"
                log(f"[INGEST] Found Playwright session cookies: {pw_json}")
            except Exception as e:
                log(f"[WARNING] Failed to read {pw_json}: {e}")

    # 3. Check environment variable for YouTube cookies (Base64 or raw text)
    if not raw_cookie_content:
        env_cookies = os.environ.get("YOUTUBE_COOKIES")
        if env_cookies:
            raw_cookie_content = env_cookies
            cookie_source = "YOUTUBE_COOKIES environment variable"
            log(f"[INGEST] Found cookies in YOUTUBE_COOKIES environment variable.")

    cookie_file = None
    if raw_cookie_content:
        try:
            parsed_content = parse_cookies_string_to_netscape(raw_cookie_content, log_fn=log_fn)
            if parsed_content:
                temp_cookie_path = os.path.join(temp_dir, "active_youtube_cookies.txt")
                # Force Unix newlines on non-Windows platforms, and Windows newlines on Windows
                out_newline = "\r\n" if os.name == "nt" else "\n"
                with open(temp_cookie_path, 'w', encoding='utf-8', newline=out_newline) as f:
                    f.write(parsed_content)
                cookie_file = temp_cookie_path
                log(f"[INGEST] Successfully sanitized and wrote cookies from {cookie_source} to {cookie_file}")
            else:
                log(f"[WARNING] Sanitized content from {cookie_source} is empty!")
        except Exception as err:
            log(f"[WARNING] Failed to sanitize cookies from {cookie_source}: {err}")

    if not cookie_file:
        log("[WARNING] No YouTube cookies found (tried youtube_cookies.txt, cookies.json, and YOUTUBE_COOKIES environment variable). Datacenter IPs will likely be blocked!")

    # Always use cookie-compatible and PO-token compatible clients to utilize the rustypipe plugin
    player_clients = ['web_creator', 'mweb', 'web']

    ydl_format = 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best'
    
    proxy_url = os.environ.get("YOUTUBE_PROXY") or os.environ.get("PROXY_URL")
    if proxy_url:
        log(f"[INGEST] Injecting proxy into yt-dlp: {proxy_url}")
    
    if cookie_file:
        log(f"[INGEST] Injecting cookies into yt-dlp from: {cookie_file}")
        log(f"[INGEST] Using cookie-compatible player clients: {player_clients}")

    metadata = {
        "song_name": None,
        "artist_name": None
    }

    def build_yt_cmd(is_meta=False, fmt=None):
        cmd = ["yt-dlp"]
        if is_meta:
            cmd.extend(["--dump-json", "--no-playlist", "--quiet"])
        else:
            cmd.extend([
                "-f", fmt,
                "-o", f"{audio_base}.%(ext)s",
                "--no-playlist",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "192",
                "--downloader", "ffmpeg",
                "--downloader-args", "ffmpeg:-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                "--remote-components", "ejs:github"
            ])
        if proxy_url:
            cmd.extend(["--proxy", proxy_url])
        if cookie_file:
            cmd.extend(["--cookies", cookie_file])
            cmd.extend(["--extractor-args", f"youtube:player_client={','.join(player_clients)}"])
        cmd.append(url)
        return cmd

    try:
        cmd_meta = build_yt_cmd(is_meta=True)
        result = subprocess.run(cmd_meta, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        song = info.get('track') or info.get('alt_title')
        artist = info.get('artist') or info.get('creator') or info.get('uploader')
        title = info.get('title', "")
        
        if " - " in title:
            parts = title.split(" - ", 1)
            p1 = parts[0].strip()
            p2 = parts[1].strip()
            
            suffixes = [
                " (Official Video)", " [Official Music Video]", " (Lyrics)", 
                " (Offizielles Video)", " (Official Audio)", " | Official Video",
                " - Official Video", " [Lyrics]", " (HD)", " (4K)", " | Audio",
                " (OFFICIAL VIDEO)", " (Official Music Video)", " (Lyric Video)",
                " | official video", " [OFFICIAL VIDEO]", " (OFFICIAL AUDIO)"
            ]
            for s in suffixes:
                p1 = p1.replace(s, "").strip()
                p2 = p2.replace(s, "").strip()
            
            uploader = info.get('uploader', "").lower()
            if not artist:
                if uploader in p1.lower() or p1.lower() in uploader:
                    artist = p1
                    song = song or p2
                elif uploader in p2.lower() or p2.lower() in uploader:
                    artist = p2
                    song = song or p1
                else:
                    artist = p1
                    song = song or p2
        else:
            if not song: song = title
            if not artist: artist = info.get('uploader')

        if song:
            for s in [" (Official Video)", " [Official Video]", " (Lyrics)", " | Official", " (Official Music Video)"]:
                song = song.replace(s, "").strip()
        
        metadata["song_name"] = song
        metadata["artist_name"] = artist
        print(f"[METADATA] Auto-detected: {song} by {artist}")
    except Exception as e:
        print(f"[WARNING] Metadata extraction failed: {e}")

    ydl_succeeded = False
    last_error = None
    for attempt in range(3):
        try:
            cmd_dl = build_yt_cmd(is_meta=False, fmt=ydl_format)
            log(f"[INGEST] Running yt-dlp command: {' '.join(cmd_dl[:4])} ...")
            # We capture stderr to read errors, stdout flows to console so user sees progress
            result = subprocess.run(cmd_dl, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                ydl_succeeded = True
                break
            else:
                last_error = Exception(f"yt-dlp failed with return code {result.returncode}")
                err_str = result.stderr
                print(f"[ERROR] yt-dlp stderr: {err_str}")
                
                if attempt < 2 and ("WinError 32" in err_str or "Unable to rename file" in err_str):
                    log(f"File lock detected during yt-dlp download/rename. Retrying in 5s... ({attempt + 1}/3)")
                    time.sleep(5)
                elif attempt < 2 and "Requested format is not available" in err_str:
                    log(f"[RETRY] Format not available with current selector. Relaxing to 'best' on attempt {attempt + 2}/3...")
                    ydl_format = 'best'
                    time.sleep(2)
                elif "Sign in to confirm" in err_str or "cookies" in err_str.lower() or "Requested format is not available" in err_str or "bot" in err_str.lower() or "403" in err_str:
                    # Bot detection or format issue — break to try Playwright fallback
                    log("[WARNING] yt-dlp blocked by YouTube bot detection. Will try Playwright fallback...")
                    break
                else:
                    break  # Unknown error — try Playwright fallback anyway
        except Exception as e:
            last_error = e
            break

    # If yt-dlp failed, try the Playwright browser fallback
    wav_path = f"{audio_base}.wav"
    if not ydl_succeeded:
        log("[FALLBACK] yt-dlp could not download. Attempting Playwright browser-based download...")
        pw_success = download_via_playwright(url, wav_path, log_fn=log_fn)
        if not pw_success:
            # Both methods failed — raise the original error
            raise last_error or Exception("Both yt-dlp and Playwright fallback failed to download audio.")
        
    return wav_path, metadata


def transcribe_full(audio_path: str, model_id: str = "large-v3-turbo") -> Dict:
    """
    Generates a mathematically precise transcript using stable-ts.
    Compiles standard HF models into Faster-Whisper formats dynamically.
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "int8" if device == "cpu" else "float16"
    
    print(f"\n[SYSTEM] Hardware detected: {device.upper()}")
    print(f"[SYSTEM] Compute Type Forced: {compute_type.upper()} (Optimized for hardware)")
    print(f"[SYSTEM] Loading Engine: {model_id}...")

    if model_id == "whisperx" or model_id.startswith("x-"):
        print("[*] Initializing WhisperX Ultra-Precision pipeline...")
        try:
            import whisperx
            
            base_model_id = model_id
            if base_model_id.startswith("x-"): base_model_id = base_model_id[2:]
            if base_model_id.startswith("stable-"): base_model_id = base_model_id[7:]
            if base_model_id == "whisperx": base_model_id = "moeshawky/whisper-small-egyptian-arabic"
            
            if "moeshawky" in base_model_id and "faster-" not in base_model_id:
                base_model_id = base_model_id.replace("whisper-", "faster-whisper-")
            
            owner_repo = base_model_id.replace("/", "--")
            local_model_path = find_local_model_path(base_model_id)

            if local_model_path:
                print(f"[*] Local model found: {local_model_path}")
            elif "/" in base_model_id:
                print(f"[*] Model {base_model_id} not found locally. Downloading from Hub...")
                try:
                    local_model_path = snapshot_download(
                        repo_id=base_model_id,
                        local_dir=os.path.join("./models", owner_repo),
                        local_dir_use_symlinks=False,
                        allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.*", "merges.txt", "*.yaml"]
                    )
                except Exception as e:
                    print(f"[!] Hub download failed: {e}")
                    local_model_path = base_model_id
            
            if not local_model_path:
                local_model_path = base_model_id

            print(f"[1/2] WhisperX: Batched Transcription using {base_model_id}...")
            model = whisperx.load_model(local_model_path, device, compute_type=compute_type, download_root="./models")
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, batch_size=4, language="ar")
            
            print("[2/2] WhisperX: Forced Alignment (Arabic XLS-R)...")
            align_model_name = "jonatasgrosman/wav2vec2-large-xlsr-53-arabic"
            local_align_path = os.path.join("./models", align_model_name.replace("/", "--"))
            align_load_name = local_align_path if os.path.isdir(local_align_path) else align_model_name
            
            model_a, metadata = whisperx.load_align_model(
                language_code="ar", 
                device=device,
                model_name=align_load_name
            )
            result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
            result['text'] = " ".join([s['text'] for s in result['segments']])
            
            gc.collect()
            if device == "cuda": torch.cuda.empty_cache()
            return result
            
        except Exception as e:
            print(f"\n[CRITICAL ERROR] WhisperX pipeline failed!")
            print(f"Reason: {str(e)}")
            traceback.print_exc()
            print("\n[*] Falling back to standard Stable-TS...\n")
            
            if model_id.startswith("stable-"):
                model_id = model_id[7:]
            elif model_id.startswith("x-"):
                model_id = model_id[2:]
            elif model_id == "whisperx":
                model_id = "large-v3-turbo"
            
            fallback_local = find_local_model_path(model_id) if "/" not in model_id else None
            if not fallback_local and "/" in model_id:
                model_id = "large-v3-turbo"

    # STANDARD STABLE-TS PIPELINE
    print(f"[*] Initializing standard engine: {model_id}")
    try:
        import stable_whisper
        
        clean_id = model_id
        if clean_id.startswith("stable-"): clean_id = clean_id[7:]
        if clean_id.startswith("faster-"): clean_id = clean_id[7:]
        
        if "moeshawky" in clean_id and "faster-" not in clean_id:
            clean_id = clean_id.replace("whisper-", "faster-whisper-")
        
        local_path = find_local_model_path(clean_id)
        if not local_path and "/" in clean_id:
            print(f"[*] Model {clean_id} not found locally. Downloading from Hub...")
            try:
                owner_repo = clean_id.replace("/", "--")
                local_path = snapshot_download(
                    repo_id=clean_id,
                    local_dir=os.path.join("./models", owner_repo),
                    local_dir_use_symlinks=False,
                    allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.*", "merges.txt", "*.yaml"]
                )
            except Exception as e:
                print(f"[!] Hub download failed: {e}")
                local_path = None
        
        load_name = clean_id
        if local_path:
            load_name = resolve_hf_path(local_path)
            print(f"[*] Resolved model path: {load_name}")

        def has_file_recursive(root_path, filename):
            for dirpath, dirnames, filenames in os.walk(root_path):
                if filename in filenames:
                    return dirpath
            return None
        
        # Look for existing binary formats
        ct2_path = has_file_recursive(load_name, "model.bin") if os.path.isdir(load_name) else None
        safetensors_path = has_file_recursive(load_name, "model.safetensors") if os.path.isdir(load_name) else None
        
        egy_prompt = "يا جماعة، النهاردة هنشوف فيديو جديد، حاجة جامدة جداً هتعجبكم إن شاء الله. إحنا في مصر بنحب الحاجات دي."
        
        # 1. High Speed CTranslate2 Pipeline (If already available)
        if ct2_path:
            print(f"[*] Detected CTranslate2 format at {ct2_path}, routing through Faster-Whisper engine... (HIGH SPEED)")
            model = stable_whisper.load_faster_whisper(ct2_path, device=device, compute_type=compute_type)
        
        # 2. Safetensors / PyTorch Hugging Face pipeline -> Compile dynamically to CTranslate2 to avoid Windows dependency crash
        elif safetensors_path:
            print(f"[*] Detected HuggingFace safetensors model at {safetensors_path}")
            print(f"[*] Transformers pipeline is unstable on this OS. Bypassing HuggingFace loader entirely.")
            
            # Target output directory for the compiled CTranslate2 format
            ct2_compiled_dir = os.path.join(load_name, f"ct2_compiled_{compute_type}")
            
            # JIT Compile if it hasn't been done yet
            if not os.path.exists(os.path.join(ct2_compiled_dir, "model.bin")):
                print(f"[*] Compiling HF model to CTranslate2 format for maximum CPU speed. (This happens only once!)...")
                try:
                    from ctranslate2.converters import TransformersConverter
                    # Safely load the HuggingFace weights and convert them to blazing fast CT2 format
                    converter = TransformersConverter(load_name)
                    converter.convert(output_dir=ct2_compiled_dir, quantization=compute_type, force=True)
                    print(f"[*] Compilation successful! Saved to {ct2_compiled_dir}")
                except Exception as conv_err:
                    print(f"[!] Compilation failed: {conv_err}")
                    raise conv_err

            # Load the newly compiled, highly optimized model (which requires no torchcodec!)
            print(f"[*] Loading optimized Faster-Whisper engine...")
            model = stable_whisper.load_faster_whisper(
                ct2_compiled_dir,
                device=device,
                compute_type=compute_type
            )
            
        else:
            if load_name != clean_id and os.path.isdir(load_name):
                print(f"[*] Loading local PyTorch model from {load_name}")
            else:
                print(f"[*] Loading model {clean_id} (may download from Hub if not cached)")
            model = stable_whisper.load_model(load_name, device=device, download_root="./models")
        
        print("Starting transcription (Demucs=False for speed, VAD=True, EGY-Prompting=True)...")
        
        if hasattr(model, '_is_whisperx_model') and model._is_whisperx_model:
            import whisperx
            audio = whisperx.load_audio(audio_path)
            result = model.transcribe(audio, batch_size=4, language="ar")
            result['text'] = " ".join([s['text'] for s in result['segments']])
        else:
            result = model.transcribe(
                audio_path,
                language="ar",
                vad=True,
                regroup=True,
                initial_prompt=egy_prompt
            )
            result = result.to_dict()
        
        gc.collect()
        if device == "cuda": torch.cuda.empty_cache()
        return result
        
    except Exception as e:
        print(f"\n[ERROR] Model {clean_id} failed to transcribe!")
        print(f"Error: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        
        print(f"\n[FALLBACK] Attempting recovery with Large-v3-Turbo (device={device}, compute={compute_type})...")
        try:
            import stable_whisper
            model = stable_whisper.load_faster_whisper("large-v3-turbo", device=device, compute_type=compute_type, download_root="./models")
            print("[INFO] Large-v3-Turbo CTranslate2 engine loaded successfully.")
        except Exception as e2:
            print(f"[FALLBACK-2] CTranslate2 failed ({e2}), trying PyTorch loader...")
            import stable_whisper
            model = stable_whisper.load_model("large-v3-turbo", device=device, download_root="./models")
            
        egy_prompt = "يا جماعة، النهاردة هنشوف فيديو جديد، حاجة جامدة جداً هتعجبكم إن شاء الله. إحنا في مصر بنحب الحاجات دي."
        result = model.transcribe(audio_path, language="ar", initial_prompt=egy_prompt)
        print("[WARNING] Transcription completed with fallback model. Results may differ from selected model.")
        return result.to_dict()

def run_transcribe_step(audio_file: str, temp_dir: str, model_id: str = "large-v3-turbo") -> str:
    transcript_data = transcribe_full(audio_file, model_id=model_id)
    
    transcript_json = os.path.join(temp_dir, "full_transcript.json")
    with open(transcript_json, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        
    full_text = transcript_data.get('text', "")
    text_json = os.path.join(temp_dir, "full_text.json")
    with open(text_json, 'w', encoding='utf-8') as f:
        json.dump({"text": full_text}, f, ensure_ascii=False, indent=2)
        
    return transcript_json


if __name__ == "__main__":
    import sys
    
    cleanup_old_sessions()
    
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
        
        session_id = str(uuid.uuid4())[:8]
        temp_path = f"./temp/session_{session_id}"
        os.makedirs(temp_path, exist_ok=True)
        
        try:
            audio, metadata = run_ingest_step(test_url, temp_path)
            run_transcribe_step(audio, temp_path)
            print("Transcription test complete.")
        finally:
            print("Running cleanup strategy...")
            cleanup_temp_folder(temp_path)