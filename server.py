from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import uuid
import importlib
import shutil
from typing import List, Dict, Optional
import time
import subprocess
import json
import publisher

# Force UTF-8 console output on Windows so logs with Arabic text do not crash.
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Self-healing auto-installation of Playwright browser binaries
try:
    print("[SYSTEM] Verifying Playwright & Phantomwright browser binaries...")
    # Force a local writable path for Playwright browsers (fixes Railway/Render Nixpacks read-only errors)
    pw_path = os.path.join(os.getcwd(), "pw-browsers")
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_path
    
    # Install standard Playwright browsers
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
        capture_output=True,
        text=True
    )
    
    # Note: phantomwright uses the same browser binaries as Playwright — no separate install needed
    
    print(f"[SYSTEM] Playwright browser check completed successfully (Path: {pw_path}).")
    
    # Try installing system dependencies
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install-deps", "chromium"],
            check=False,
            capture_output=True
        )
    except Exception:
        pass
except subprocess.CalledProcessError as pw_install_err:
    print(f"[SYSTEM] Playwright browser auto-installation warning: {pw_install_err}")
    if hasattr(pw_install_err, 'stderr') and pw_install_err.stderr:
        print(f"[SYSTEM] Stderr: {pw_install_err.stderr}")
except Exception as e:
    print(f"[SYSTEM] Unexpected error during browser install: {e}")


def cleanup_workspace(full=True):
    dirs_to_clean = ["temp"]
    if full:
        dirs_to_clean.append("output")
        print("[SYSTEM] Performing FULL workspace reset (temp + output)...")
    else:
        print("[SYSTEM] Refreshing workspace (cleaning temp)...")
        
    for d in dirs_to_clean:
        if os.path.exists(d):
            for i in range(3):
                try:
                    shutil.rmtree(d)
                    os.makedirs(d, exist_ok=True)
                    with open(os.path.join(d, ".gitkeep"), "w") as f: f.write("")
                    break
                except Exception as e:
                    if i == 2: print(f"[WARNING] Failed to clean {d}: {e}")
                    time.sleep(1)
        else:
            os.makedirs(d, exist_ok=True)

def cleanup_session_temp(session_id: str, add_log_fn=None):
    """
    Cleans up high-volume intermediate assets in the session's temporary folder
    (like WAVs, temporary MP4s, SRTs) while preserving lightweight JSON metadata
    (like slicing_map.json, semantics.json) to match MoneyPrinterV2's .mp/ cleanup logic.
    """
    temp_dir = f"./temp/session_{session_id}"
    if not os.path.exists(temp_dir):
        return

    if add_log_fn:
        add_log_fn("[CLEANUP] Safely archiving session workspace: purging high-volume temp assets...")

    cleaned_count = 0
    # Try up to 3 times to handle potential Windows file locks
    for attempt in range(3):
        locked_files = []
        try:
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Keep lightweight JSON manifests/metadata
                    if not file.lower().endswith(".json"):
                        try:
                            os.remove(file_path)
                            cleaned_count += 1
                        except Exception:
                            locked_files.append(file_path)
                
                # Delete empty directories
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        shutil.rmtree(dir_path)
                    except Exception:
                        pass
            
            if not locked_files:
                break
            time.sleep(0.5)
        except Exception as e:
            if attempt == 2 and add_log_fn:
                add_log_fn(f"[WARNING] Temp cleanup encountered error: {e}")
            time.sleep(0.5)

    if add_log_fn and cleaned_count > 0:
        add_log_fn(f"[CLEANUP] Purged {cleaned_count} intermediate temp assets. Disk space optimized.")

cleanup_workspace(full=False)

app = FastAPI(title="You-Tik Studio API")

@app.post("/api/reset")
async def reset_app():
    global sessions
    sessions = {}
    cleanup_workspace(full=True)
    return {"message": "System fully reset. Output and Temp cleared."}

@app.post("/api/refresh")
async def refresh_app():
    cleanup_workspace(full=False)
    return {"message": "Workspace refreshed. Temp cleared."}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("output", exist_ok=True)
os.makedirs("temp", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")
app.mount("/temp", StaticFiles(directory="temp"), name="temp")

sessions = {}

class IngestRequest(BaseModel):
    mode: str = "clip"
    url: str = ""
    prompt: str = ""
    mixed_genres: str = ""
    subtitle_style: str = "Cinematic"
    model_id: str = "large-v3-turbo"
    google_model: str = "models/gemma-4-31b-it"
    song_name: Optional[str] = None
    artist_name: Optional[str] = None
    manual_review: bool = False
    tts_engine: Optional[str] = None
    tts_voice: Optional[str] = "M1"
    target_duration: int = 30
    custom_cookies: Optional[str] = None


class PublishRequest(BaseModel):
    video_path: str
    platform: str  # tiktok | youtube | instagram | twitter
    caption: str = ""
    hashtags: Optional[List[str]] = None
    account: str = "default"
    save_as_draft: bool = False
    headless: bool = False





# CRITICAL FIX: Removed 'async' so FastAPI runs this in a background thread, preventing UI freezing!
def run_pipeline(session_id: str, request: IngestRequest):
    def add_log(msg):
        sessions[session_id]["logs"].append(msg)
        try:
            print(f"[{session_id}] {msg}")
        except UnicodeEncodeError:
            print(f"[{session_id}] {msg.encode('utf-8', 'replace').decode('latin-1')}")

    try:
        temp_dir = f"./temp/session_{session_id}"
        output_dir = f"./output/session_{session_id}"
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        sessions[session_id]["data"] = {
            "temp_dir": temp_dir,
            "output_dir": output_dir,
            "subtitle_style": request.subtitle_style,
            "model_id": request.model_id,
            "google_model": request.google_model,
            "tts_engine": request.tts_engine,
            "tts_voice": request.tts_voice
        }

        # ----------------------------------------
        # MODE B: CREATE MODE (Faceless Content)
        # ----------------------------------------
        if request.mode == "create":
            sessions[session_id]["status"] = "SCRIPT_GENERATION"
            add_log("[SYSTEM] Processing mapped lyrics into production stanzas...")
            
            raw_stanzas = [s.strip() for s in request.prompt.split("\n\n") if s.strip()]
            if not raw_stanzas:
                raw_stanzas = [request.prompt.strip()]
                
            slicing_map = []
            for i, text in enumerate(raw_stanzas):
                slicing_map.append({
                    "scene_index": i,
                    "title": f"Stanza {i+1}",
                    "text": text,
                    "visual_queries": ["cinematic dark background abstract"], 
                    "start_time": 0.0,
                    "end_time": 0.0,
                    "duration": 0.0,
                    "tts_mode": True
                })
                
            slicing_json_path = os.path.join(temp_dir, "slicing_map.json")
            with open(slicing_json_path, 'w', encoding='utf-8') as f:
                json.dump(slicing_map, f, ensure_ascii=False, indent=2)
                
            add_log(f"[SYSTEM] Formatted {len(raw_stanzas)} stanzas for production.")

            sessions[session_id]["status"] = "TTS_SYNTHESIS"
            add_log(f"[SUPERTONIC] Synthesizing vocals ({request.tts_voice}) and forcing alignment...")
            m4 = importlib.import_module("4_tts_engine")
            slicing_json_path = m4.run_tts_step(slicing_json_path, temp_dir, voice_name=request.tts_voice, lang="ar")
            add_log("[SUPERTONIC] Voice generation and word alignment complete.")

            sessions[session_id]["status"] = "MUSIC_GENERATION"
            if request.mixed_genres.strip():
                add_log(f"[HEARTMULA] Generating AI Master Track: {request.mixed_genres}...")
                m5 = importlib.import_module("5_music_engine")
                
                with open(slicing_json_path, 'r', encoding='utf-8') as f:
                    smap = json.load(f)
                full_lyrics = "\n\n".join([f"[{item.get('title', 'verse')}]\n{item.get('text', '')}" for item in smap])
                
                master_music_path = m5.run_music_step(request.mixed_genres, full_lyrics, temp_dir, request.target_duration * 1000)
                add_log("[HEARTMULA] Custom music track generation complete.")
            else:
                add_log("[HEARTMULA] No genres selected. Skipping custom music track.")
                master_music_path = None

            sessions[session_id]["status"] = "COMPOSITING"
            add_log("[STUDIO] Compositing Faceless Video over background visuals/beats...")
            m3 = importlib.import_module("3_render_engine")
            final_clips = m3.run_pipeline_step_3(slicing_json_path, master_music_path, output_dir, request.subtitle_style)
            
            for clip in final_clips:
                thumb_path = clip.replace('.mp4', '.jpg')
                if not os.path.exists(thumb_path):
                    subprocess.run(["ffmpeg", "-y", "-ss", "01.5", "-i", clip, "-vframes", "1", thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            sessions[session_id]["data"]["final_clips"] = final_clips
            sessions[session_id]["status"] = "COMPLETED"
            add_log("[SUCCESS] AI Original Production complete. Assets ready in Gallery.")
            cleanup_session_temp(session_id, add_log)
            return

        # ----------------------------------------
        # MODE A: CLIP MODE (Original Flow)
        # ----------------------------------------
        sessions[session_id]["status"] = "INGESTION"
        add_log("[INGEST] Starting media download...")
        m1 = importlib.import_module("1_ingest_and_split")
        audio_file, metadata = m1.run_ingest_step(request.url, temp_dir, log_fn=add_log, custom_cookies=request.custom_cookies)
        sessions[session_id]["data"]["audio_file"] = audio_file
        
        if not request.song_name and metadata.get("song_name"):
            request.song_name = metadata["song_name"]
            add_log(f"[INGEST] Auto-detected song: {request.song_name}")
        if not request.artist_name and metadata.get("artist_name"):
            request.artist_name = metadata["artist_name"]
            add_log(f"[INGEST] Auto-detected artist: {request.artist_name}")
            
        add_log(f"[INGEST] Audio isolated: {os.path.basename(audio_file)}")

        sessions[session_id]["status"] = "VOCAL_ANALYSIS"
        add_log(f"[WHISPER] Starting Egyptian dialect transcription using engine: {request.model_id}")
        transcript_json = m1.run_transcribe_step(audio_file, temp_dir, model_id=request.model_id)
        sessions[session_id]["data"]["transcript_json"] = transcript_json
        add_log("[WHISPER] Transcription complete.")
 
        if request.song_name and not request.manual_review:
            sessions[session_id]["status"] = "CORRECTING_LYRICS"
            display_name = f"'{request.song_name}' by '{request.artist_name}'" if request.artist_name else f"'{request.song_name}'"
            add_log(f"[FIX] Fetching/Correcting lyrics for {display_name} using AI...")
            
            m15 = importlib.import_module("1_5_fix_transcript")
            success = m15.fix_transcript(transcript_json, request.song_name, request.artist_name or "Unknown Artist", "", google_model=request.google_model) 
            if success:
                add_log("[FIX] Lyrics corrected using AI ground truth.")
            else:
                add_log("[WARNING] Lyric correction failed, proceeding with raw transcript.")
        elif request.manual_review:
            add_log("[HITL] Skipping AI lyric correction (Manual Mode enabled).")
        else:
            add_log("[SKIP] Lyric correction skipped (missing song metadata).")

        sessions[session_id]["status"] = "SEMANTICS"
        if request.manual_review:
            add_log("[SEMANTICS] Generating basic HITL baseline (Skipping AI Visual Queries)...")
        else:
            add_log(f"[SEMANTICS] Generating cinematic mapping for {os.path.basename(audio_file)} using {request.google_model}...")
        
        m2 = importlib.import_module("2_google_semantics")
        semantics_json = m2.run_pipeline_step_2(transcript_json, temp_dir, google_model=request.google_model, song_name=request.song_name, artist_name=request.artist_name, skip_ai=request.manual_review)
        sessions[session_id]["data"]["semantics_json"] = semantics_json
        
        if request.manual_review:
            add_log("[SEMANTICS] Analysis complete. PAUSED for Human Review.")
            sessions[session_id]["status"] = "WAITING_FOR_REVIEW"
        else:
            add_log("[SEMANTICS] AI Analysis complete. AUTO-PROCEEDING to rendering...")
            # FIX: Call standard function without 'await'
            run_pipeline_phase_2(session_id, None)

    except Exception as e:
        sessions[session_id]["status"] = "ERROR"
        add_log(f"[ERROR] Phase 1 failed: {str(e)}")
        sessions[session_id]["error"] = str(e)

# CRITICAL FIX: Removed 'async' so FastAPI runs this in a background thread
def run_pipeline_phase_2(session_id: str, human_semantics: List[Dict]):
    """Continues the pipeline after human review (Clip Mode Only)."""
    try:
        data = sessions[session_id]["data"]
        temp_dir = data["temp_dir"]
        output_dir = data["output_dir"]
        audio_file = data["audio_file"]
        transcript_json = data["transcript_json"]
        subtitle_style = data["subtitle_style"]
        model_id = data.get("model_id", "x-large-v3-turbo")

        semantics_json_path = os.path.join(temp_dir, "semantics.json")
        if human_semantics:
            with open(semantics_json_path, 'w', encoding='utf-8') as f:
                json.dump(human_semantics, f, ensure_ascii=False, indent=2)
        
        sessions[session_id]["status"] = "SLICING"
        add_log = lambda msg: sessions[session_id]["logs"].append(msg)
        add_log("[RENDER] High-precision slicing...")
        
        m3 = importlib.import_module("3_render_engine")
        slicing_json_path = m3.run_precision_slicing_step(transcript_json, semantics_json_path, temp_dir, model_id=model_id)
        
        sessions[session_id]["status"] = "COMPOSITING"
        add_log("[STUDIO] Beginning final composite...")
        final_clips = m3.run_pipeline_step_3(slicing_json_path, audio_file, output_dir, subtitle_style)

        add_log("[GALLERY] Generating preview assets...")
        for clip in final_clips:
            thumb_path = clip.replace('.mp4', '.jpg')
            if not os.path.exists(thumb_path):
                subprocess.run(["ffmpeg", "-y", "-ss", "01.5", "-i", clip, "-vframes", "1", thumb_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        sessions[session_id]["data"]["final_clips"] = final_clips
        sessions[session_id]["status"] = "COMPLETED"
        add_log("[SUCCESS] Production complete. Assets ready in Gallery.")
        cleanup_session_temp(session_id, add_log)

    except Exception as e:
        sessions[session_id]["status"] = "ERROR"
        add_log = lambda msg: sessions[session_id]["logs"].append(msg)
        add_log(f"[ERROR] Phase 2 failed: {str(e)}")

@app.post("/process")
async def initialize_pipeline(request: IngestRequest, background_tasks: BackgroundTasks):
    # Auto-clean workspace and reset stale sessions to prevent disk bloat
    global sessions
    sessions = {}
    cleanup_workspace(full=True)

    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "session_id": session_id,
        "step": 0,
        "status": "INGESTION" if request.mode == "clip" else "SCRIPT_GENERATION",
        "logs": ["[SYSTEM] Initializing production pipeline..."],
        "data": {},
        "error": None
    }
    background_tasks.add_task(run_pipeline, session_id, request)
    return {"session_id": session_id}

@app.get("/status/{session_id}")
async def get_status(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    data = sessions[session_id]
    clips = []
    if "final_clips" in data["data"]:
        for clip_path in data["data"]["final_clips"]:
            web_path = clip_path.replace("./", "/")
            thumb_path = web_path.replace(".mp4", ".jpg")
            clips.append({
                "url": web_path,
                "thumbnail_url": thumb_path,
                "filename": os.path.basename(clip_path)
            })
            
    return {
        "status": data["status"],
        "logs": data["logs"],
        "clips": clips
    }

class ReviewCommit(BaseModel):
    semantics: List[Dict]

@app.get("/review/{session_id}")
async def get_review_data(session_id: str):
    if session_id not in sessions: raise HTTPException(status_code=404)
    temp_dir = sessions[session_id]["data"]["temp_dir"]
    
    semantics_path = os.path.join(temp_dir, "semantics.json")
    with open(semantics_path, 'r', encoding='utf-8') as f:
        semantics = json.load(f)
        
    full_text_path = os.path.join(temp_dir, "full_text.json")
    full_text = {}
    if os.path.exists(full_text_path):
        with open(full_text_path, 'r', encoding='utf-8') as f:
            full_text = json.load(f)

    transcript_path = os.path.join(temp_dir, "transcript.json")
    if not os.path.exists(transcript_path):
        transcript_path = os.path.join(temp_dir, "full_transcript.json")
        
    transcript = {}
    if os.path.exists(transcript_path):
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript = json.load(f)
            
    return {
        "semantics": semantics,
        "full_text": full_text.get("text", ""),
        "transcript": transcript
    }

@app.post("/review/{session_id}/commit")
async def commit_review(session_id: str, commit: ReviewCommit, background_tasks: BackgroundTasks):
    if session_id not in sessions: raise HTTPException(status_code=404)
    sessions[session_id]["status"] = "RESUMING"
    background_tasks.add_task(run_pipeline_phase_2, session_id, commit.semantics)
    return {"status": "ok"}

@app.get("/config")
async def get_config():
    return {
        "subtitle_styles": ["TikTok", "Cinematic", "Calligraphy", "Dynamic", "Glow", "Box", "MegaPop"],
        "models": [
            {"id": "stable-MAdel121/whisper-small-egyptian-arabic", "name": "EGY-Small (Studio)", "desc": "Highest Rated Egyptian Small (72h fine-tune)"},
            {"id": "stable-IbrahimAmin/code-switched-egyptian-arabic-whisper-small", "name": "EGY-Mix (Slang + EN)", "desc": "Best for casual talk with English words"},
            {"id": "stable-moeshawky/whisper-small-egyptian-arabic", "name": "EGY-Small (Legacy)", "desc": "Local faster-whisper model (Fast and available)"},
            {"id": "x-large-v3-turbo", "name": "Global Turbo + X (Precision)", "desc": "Fast + WhisperX Alignment (User Recommended)"},
            {"id": "large-v3-turbo", "name": "Global Turbo (Standard)", "desc": "Stable-TS engine only"}
        ],
        "google_models": [
            {"id": "models/gemma-4-31b-it", "name": "Gemma 4 31b", "desc": "Ultimate reasoning & cinematic mapping (Paid Tier)"},
            {"id": "models/gemma-4-26b-a4b-it", "name": "Gemma 4 26b", "desc": "High efficiency reasoning for fast cinematic mapping"},
            {"id": "models/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "desc": "Next-gen speed for real-time production (Free Tier)"}
        ],
        "tts_engines": [
            {"id": "none", "name": "Original Audio", "desc": "Use original vocals from the source media"},
            {"id": "supertonic", "name": "Supertonic TTS", "desc": "Lightning-fast on-device Arabic TTS (ONNX Optimized)"}
        ],
        "tts_voices": [
            {"id": "F1", "name": "Female 1", "desc": "Female voice F1"},
            {"id": "F2", "name": "Female 2", "desc": "Female voice F2"},
            {"id": "F3", "name": "Female 3", "desc": "Female voice F3"},
            {"id": "F4", "name": "Female 4", "desc": "Female voice F4"},
            {"id": "F5", "name": "Female 5", "desc": "Female voice F5"},
            {"id": "M1", "name": "Male 1", "desc": "Male voice M1"},
            {"id": "M2", "name": "Male 2", "desc": "Male voice M2"},
            {"id": "M3", "name": "Male 3", "desc": "Male voice M3"},
            {"id": "M4", "name": "Male 4", "desc": "Male voice M4"},
            {"id": "M5", "name": "Male 5", "desc": "Male voice M5"}
        ]
    }

# ---------------------------------------------------------------------------
# Social-Media Publish Endpoints
# ---------------------------------------------------------------------------

@app.post("/publish")
async def start_publish(req: PublishRequest):
    """Start a background publish job for a clip."""
    # Resolve the actual file path on disk from the web path
    file_path = req.video_path
    if file_path.startswith("/output/"):
        file_path = "." + file_path  # ./output/session_xxx/clip.mp4
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {file_path}")
    if req.platform not in publisher.PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {req.platform}")

    job_id = publisher.start_publish_job(
        video_path=os.path.abspath(file_path),
        platform=req.platform,
        caption=req.caption,
        hashtags=req.hashtags,
        account=req.account,
        save_as_draft=req.save_as_draft,
        headless=req.headless,
    )
    return {"job_id": job_id, "status": "QUEUED"}


@app.get("/publish/status/{job_id}")
async def publish_status(job_id: str):
    """Poll the status of a publish job."""
    job = publisher.publish_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Publish job not found")
    return {
        "job_id": job["job_id"],
        "platform": job["platform"],
        "status": job["status"],
        "detail": job["detail"],
        "vnc_active": job.get("vnc_active", False),
    }


@app.get("/publish/accounts")
async def list_publish_accounts():
    """List platforms that have saved authentication sessions."""
    return {"accounts": publisher.get_authenticated_accounts()}


@app.post("/auth/google")
async def auth_google():
    """Start a real browser-based Google login using Playwright persistent context."""
    job_id = publisher.start_google_login_job()
    return {"job_id": job_id, "status": "STARTING"}


@app.get("/auth/google/status/{job_id}")
async def auth_google_status(job_id: str):
    """Poll the status of a browser-based Google login job."""
    job = publisher.login_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Login job not found")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "detail": job.get("detail", ""),
        "user": job.get("user"),
        "vnc_active": job.get("vnc_active", False),
    }


@app.get("/auth/google/user")
async def get_google_user():
    """Get currently logged-in Google Master Account, if any."""
    master_profile_path = publisher.SESSIONS_DIR / "google_master.json"
    if master_profile_path.is_file() and publisher._has_google_profile():
        try:
            return json.loads(master_profile_path.read_text())
        except Exception:
            return None
    return None


@app.post("/auth/google/logout")
async def logout_google():
    """Log out of Google Master Account and clean persistent browser profile."""
    master_profile_path = publisher.SESSIONS_DIR / "google_master.json"
    if master_profile_path.exists():
        master_profile_path.unlink()

    # Clean the persistent browser profile (this is the real session data)
    if publisher.GOOGLE_PROFILE_DIR.exists():
        shutil.rmtree(publisher.GOOGLE_PROFILE_DIR, ignore_errors=True)

    # Clean sessions for all platforms
    if publisher.SESSIONS_DIR.exists():
        for item in publisher.SESSIONS_DIR.iterdir():
            if item.is_dir() and item.name in ["youtube", "tiktok", "instagram", "twitter"]:
                shutil.rmtree(item, ignore_errors=True)

    # Recreate session directories
    publisher._ensure_session_dirs()
    return {"status": "success", "message": "Logged out successfully. Browser session and platform data cleared."}


class CookieSyncRequest(BaseModel):
    cookies: str


class MultiUserCookieSyncRequest(BaseModel):
    user_id: str
    platform: str
    cookies: List[Dict]


@app.post("/auth/youtube/cookies")
async def sync_youtube_cookies(req: CookieSyncRequest):
    """Saves YouTube cookies synced from the user's browser extension."""
    try:
        # Write the cookies directly into standard cookie_file
        # This will be automatically picked up by 1_ingest_and_split.py
        cookie_path = "youtube_cookies.txt"
        with open(cookie_path, "w", encoding="utf-8") as f:
            f.write(req.cookies)
            
        # Also save to the database for 'default' user for backward compatibility
        try:
            from database import db
            cookies_list = json.loads(req.cookies)
            db.save_cookies("default", "youtube", cookies_list)
        except Exception as e:
            print("Failed to sync to database:", e)
            
        # Update google_master.json synthetic authentication state
        master_data = {
            "name": "Sync Extension Session",
            "email": "Authenticated via Chrome Extension Sync",
            "picture": "",
            "authenticated_at": time.time(),
            "auth_method": "extension_sync",
        }
        master_profile_path = publisher.SESSIONS_DIR / "google_master.json"
        master_profile_path.write_text(json.dumps(master_data, indent=2))
        
        return {"status": "success", "message": "YouTube session successfully synced!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync cookies: {str(e)}")


@app.post("/api/auth/cookies/sync")
async def sync_cookies(req: MultiUserCookieSyncRequest):
    """Saves user session cookies dynamically into the database for secure publishing."""
    try:
        from database import db
        success = db.save_cookies(req.user_id, req.platform.lower(), req.cookies)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save cookies to database.")
        
        # Also support backward compatibility by writing files for default user
        if req.user_id == "default":
            if req.platform.lower() == "youtube":
                cookie_path = "youtube_cookies.txt"
                with open(cookie_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(req.cookies))
            elif req.platform.lower() == "tiktok":
                for name in ["TK_cookies.json", "TK_cookies_default.json"]:
                    with open(name, "w", encoding="utf-8") as f:
                        f.write(json.dumps(req.cookies))
        
        return {"status": "success", "message": f"Successfully synced {req.platform.upper()} session for {req.user_id}!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/extension/download")
async def download_sync_extension():
    """Generates and serves a ZIP archive of the pre-built Chrome Extension."""
    import zipfile
    import io
    from fastapi.responses import StreamingResponse
    
    extension_dir = "you-tik-sync-extension"
    if not os.path.exists(extension_dir):
        raise HTTPException(status_code=404, detail="Extension directory not found.")
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, files in os.walk(extension_dir):
            for file in files:
                file_path = os.path.join(root, file)
                archive_name = os.path.relpath(file_path, extension_dir)
                zip_file.write(file_path, archive_name)
                
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=you-tik-sync-extension.zip"}
    )

from fastapi import WebSocket, WebSocketDisconnect
import asyncio

@app.websocket("/api/vnc/{job_id}")
async def vnc_proxy(websocket: WebSocket, job_id: str):
    """
    Proxies a WebSocket connection from the frontend's noVNC client
    directly to the local x11vnc TCP server running on port 5900.
    """
    await websocket.accept(subprotocol="binary")
    
    # 5900 is the default x11vnc port used by VirtualDisplay in publisher.py
    vnc_port = 5900
    
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", vnc_port)
    except Exception as e:
        print(f"[VNC Proxy] Could not connect to local x11vnc on port {vnc_port}: {e}")
        try:
            await websocket.close()
        except:
            pass
        return

    async def tcp_to_ws():
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                await websocket.send_bytes(data)
        except Exception:
            pass

    async def ws_to_tcp():
        try:
            while True:
                data = await websocket.receive_bytes()
                writer.write(data)
                await writer.drain()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    # Run both proxy directions concurrently
    await asyncio.gather(tcp_to_ws(), ws_to_tcp())
    
    # Clean up connections when done
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass
    
    try:
        await websocket.close()
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)