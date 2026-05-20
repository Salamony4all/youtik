import os
import sys

# Move the print statements to the absolute top so you get instant feedback BEFORE the heavy imports freeze the terminal!
print("=======================================")
print("  UTIK LOCAL MUSIC ENGINE BOOTING...   ")
print("  (Loading heavy AI libraries, please wait 15-30 seconds...)  ")
print("=======================================")

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import scipy.io.wavfile
import uuid
import gc
from transformers import AutoProcessor, MusicgenForConditionalGeneration

# Initialize the API
app = FastAPI(title="Utik Music Engine (Local)")

OUTPUT_DIR = "./generated_tracks"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class MusicRequest(BaseModel):
    tags: str
    lyrics: str = "" 
    max_audio_length_ms: int = 30000
    temperature: float = 1.0
    topk: int = 250 # OPTIMIZED: Increased from 50 to 250 for richer multi-instrument orchestration
    cfg_scale: float = 4.5 # OPTIMIZED: Increased from 1.5 to 4.5 so the model aggressively follows your genres
    lazy_load: bool = True

@app.post("/generate/music")
async def generate_music(request: MusicRequest):
    print(f"\n[MUSIC ENGINE] Received request for genres: {request.tags}")
    
    duration_sec = min(30, max(5, int(request.max_audio_length_ms / 1000)))
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = "facebook/musicgen-small" 
    
    print(f"[MUSIC ENGINE] Loading {model_id} into memory on {device.upper()}...")
    try:
        processor = AutoProcessor.from_pretrained(model_id)
        model = MusicgenForConditionalGeneration.from_pretrained(model_id).to(device)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model: {str(e)}")

    # Cleaned prompt style to specialize as high fidelity backing track
    prompt = f"Cinematic studio instrumental background music, style: {request.tags}, clear stereo separation, crisp percussion, highly detailed production"
    
    inputs = processor(
        text=[prompt],
        padding=True,
        return_tensors="pt",
    ).to(device)

    print(f"[MUSIC ENGINE] Generating {duration_sec} seconds of audio...")
    audio_values = model.generate(
        **inputs,
        do_sample=True, # CRITICAL FIX: Unlocks creative sampling mode to kill the robotic looping notes
        max_new_tokens=int(duration_sec * 50), 
        temperature=request.temperature,
        top_k=request.topk,
        guidance_scale=request.cfg_scale
    )

    track_id = str(uuid.uuid4())[:8]
    output_path = os.path.join(OUTPUT_DIR, f"track_{track_id}.wav")
    
    sampling_rate = model.config.audio_encoder.sampling_rate
    audio_data = audio_values[0, 0].cpu().numpy()
    scipy.io.wavfile.write(output_path, rate=sampling_rate, data=audio_data)
    
    print(f"[MUSIC ENGINE] Track saved to: {output_path}")

    if request.lazy_load:
        print("[MUSIC ENGINE] Offloading model from memory...")
        del model
        del processor
        del inputs
        del audio_values
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()

    return {
        "status": "success",
        "save_path": os.path.abspath(output_path),
        "duration_sec": duration_sec
    }

if __name__ == "__main__":
    print("[MUSIC ENGINE] Libraries loaded. Starting local server on port 8001...")
    uvicorn.run(app, host="127.0.0.1", port=8001)