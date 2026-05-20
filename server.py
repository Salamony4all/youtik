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

# Force UTF-8 console output on Windows so logs with Arabic text do not crash.
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

from fastapi.staticfiles import StaticFiles

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

cleanup_workspace(full=True)

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
            return

        # ----------------------------------------
        # MODE A: CLIP MODE (Original Flow)
        # ----------------------------------------
        sessions[session_id]["status"] = "INGESTION"
        add_log("[INGEST] Starting media download...")
        m1 = importlib.import_module("1_ingest_and_split")
        audio_file, metadata = m1.run_ingest_step(request.url, temp_dir)
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

    except Exception as e:
        sessions[session_id]["status"] = "ERROR"
        add_log = lambda msg: sessions[session_id]["logs"].append(msg)
        add_log(f"[ERROR] Phase 2 failed: {str(e)}")

@app.post("/process")
async def initialize_pipeline(request: IngestRequest, background_tasks: BackgroundTasks):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)