import os
import soundfile as sf
from supertonic import TTS

def test_arabic_tts():
    print("[TEST] Initializing Supertonic TTS...")
    try:
        tts = TTS(auto_download=True)
        print("[TEST] TTS Initialized.")
        
        voices = ["M1", "F1", "M2", "F2", "M3", "F3", "M4", "F4", "M5", "F5"]
        text = "مرحباً بك في يو تيك ستوديو. هذا اختبار للمحرك الجديد."
        
        output_dir = "test_tts_output"
        os.makedirs(output_dir, exist_ok=True)
        
        for v in voices[:2]: # Just test first two to save time/space
            print(f"[TEST] Synthesizing with voice {v}...")
            style = tts.get_voice_style(voice_name=v)
            wav, duration = tts.synthesize(text, voice_style=style, lang="ar")
            output_path = os.path.join(output_dir, f"test_ar_{v}.wav")
            tts.save_audio(wav, output_path)
            print(f"[TEST] Saved {output_path} (Duration: {duration:.2f}s)")
            
        print("[TEST] SUCCESS")
    except Exception as e:
        print(f"[TEST] FAILED: {e}")

if __name__ == "__main__":
    test_arabic_tts()
