import os
import yt_dlp
import json
import torch
from typing import Dict
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

def convert_playwright_cookies(json_path: str, txt_path: str) -> bool:
    """Converts Playwright JSON cookies format to standard Netscape cookies format."""
    try:
        if not os.path.exists(json_path):
            return False
        with open(json_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        lines = [
            "# Netscape HTTP Cookie File",
            "# http://curl.haxx.se/rfc/cookie_spec.html",
            "# This is a generated file! Do not edit.\n"
        ]
        for c in cookies:
            domain = c.get("domain", "")
            include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure", False) else "FALSE"
            expires = int(c.get("expires", 0))
            name = c.get("name", "")
            value = c.get("value", "")
            
            lines.append(f"{domain}\t{include_subdomains}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
            
        os.makedirs(os.path.dirname(txt_path), exist_ok=True)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"[COOKIES] Successfully converted Playwright cookies from {json_path} to Netscape {txt_path}")
        return True
    except Exception as e:
        print(f"[WARNING] Playwright cookies conversion failed: {e}")
        return False

def run_ingest_step(url: str, temp_dir: str) -> tuple:
    print(f"Starting ingest for: {url}")
    audio_base = os.path.join(temp_dir, "source_audio")
    
    # Locate best cookie file path
    cookie_file = None
    
    # 1. Check root cookies files
    for root_cookie in ["youtube_cookies.txt", "cookies.txt"]:
        if os.path.exists(root_cookie):
            cookie_file = root_cookie
            print(f"[INGEST] Found YouTube cookies file in workspace root: {cookie_file}")
            break
            
    # 2. Check Playwright session cookies
    if not cookie_file:
        pw_json = "sessions/youtube/default/cookies.json"
        pw_txt = "sessions/youtube/default/cookies.txt"
        if os.path.exists(pw_json):
            if convert_playwright_cookies(pw_json, pw_txt):
                cookie_file = pw_txt

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{audio_base}.%(ext)s", 
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
        'quiet': False,
        'js_runtimes': {'node': {}},
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }
    
    if cookie_file:
        ydl_opts['cookiefile'] = cookie_file
        print(f"[INGEST] Injecting cookies into yt-dlp from: {cookie_file}")

    
    metadata = {
        "song_name": None,
        "artist_name": None
    }

    try:
        extract_opts = {**ydl_opts, 'quiet': True, 'simulate': True}
        with yt_dlp.YoutubeDL(extract_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
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

    for attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            break
        except Exception as e:
            if attempt < 2 and ("WinError 32" in str(e) or "Unable to rename file" in str(e)):
                print(f"File lock detected during yt-dlp download/rename. Retrying in 5s... ({attempt + 1}/3)")
                time.sleep(5)
            else:
                raise e
        
    return f"{audio_base}.wav", metadata


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