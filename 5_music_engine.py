import requests
import os
import time
import shutil

class HeartMuLaClient:
    def __init__(self, host="http://127.0.0.1:8001"):
        self.host = host
        self.generate_endpoint = f"{self.host}/generate/music"

    def generate_master_track(self, tags: str, lyrics: str, output_path: str, max_duration_ms: int = 45000):
        print(f"[MUSIC_ENGINE] Attempting connection to local HeartMuLa API...")
        print(f"[MUSIC_ENGINE] Tags: {tags}")
        
        payload = {
            "tags": tags,
            "lyrics": lyrics,
            "max_audio_length_ms": max_duration_ms,
            "temperature": 1.0,
            "topk": 50,
            "cfg_scale": 1.5,
            "lazy_load": True 
        }
        
        try:
            # INCREASED TIMEOUT TO 1200 SECONDS (20 MINUTES) FOR CPU GENERATION
            response = requests.post(self.generate_endpoint, json=payload, timeout=1200)
            response.raise_for_status()
            data = response.json()
            
            source_path = data.get("save_path", "")
            if os.path.exists(source_path):
                shutil.copy(source_path, output_path)
                return output_path
            else:
                print(f"[MUSIC_ENGINE] Expected file not found. Falling back to default beats.")
                return None
                
        except Exception as e:
            print(f"[MUSIC_ENGINE] Local API Error: {e}")
            return None

def run_music_step(tags: str, full_lyrics: str, temp_dir: str, max_duration_ms: int = 45000) -> str:
    client = HeartMuLaClient()
    output_path = os.path.join(temp_dir, "master_music.wav")
    result = client.generate_master_track(tags, full_lyrics, output_path, max_duration_ms)
    return result