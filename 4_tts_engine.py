import os
import json
import soundfile as sf
import torch
import stable_whisper
from typing import List, Dict
from supertonic import TTS

class SupertonicEngine:
    def __init__(self):
        print("[SUPERTONIC] Initializing TTS Engine...")
        self.tts = TTS(auto_download=True)
        self.voice_styles = {}
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[ALIGNER] Loading alignment model on {device}...")
        self.aligner = stable_whisper.load_model("small", device=device, download_root="./models")

    def get_style(self, voice_name: str):
        if voice_name not in self.voice_styles:
            print(f"[SUPERTONIC] Loading voice style: {voice_name}")
            self.voice_styles[voice_name] = self.tts.get_voice_style(voice_name=voice_name)
        return self.voice_styles[voice_name]

    def synthesize_stanzas(self, slicing_map_path: str, temp_dir: str, voice_name: str = "M1", lang: str = "ar"):
        with open(slicing_map_path, 'r', encoding='utf-8') as f:
            slicing_map = json.load(f)

        tts_dir = os.path.join(temp_dir, "tts_audio")
        os.makedirs(tts_dir, exist_ok=True)

        style = self.get_style(voice_name)
        
        print(f"[SUPERTONIC] Starting batch synthesis for {len(slicing_map)} stanzas (Voice: {voice_name}, Lang: {lang})")
        
        for i, item in enumerate(slicing_map):
            text = item.get('text', '').strip()
            if not text:
                print(f"[SUPERTONIC] Skipping empty stanza {i}")
                continue

            try:
                # FIX: Safely catch whatever tuple Supertonic returns
                synth_result = self.tts.synthesize(text, voice_style=style, lang=lang)
                wav = synth_result[0] if isinstance(synth_result, tuple) else synth_result
                
                output_filename = f"stanza_{i}_{voice_name}.wav"
                output_path = os.path.join(tts_dir, output_filename)
                self.tts.save_audio(wav, output_path)
                
                # FIX: Read the exact duration from the generated file to avoid numpy format errors
                audio_info = sf.info(output_path)
                actual_duration = audio_info.frames / audio_info.samplerate
                
                print(f"[SUPERTONIC] Synthesized stanza {i}: {actual_duration:.2f}s")
                
                print(f"[ALIGNER] Aligning stanza {i}...")
                try:
                    result = self.aligner.align(output_path, text, language=lang)
                    words = []
                    for w in result.all_words():
                        words.append({
                            'start': w.start,
                            'end': w.end,
                            'word': w.word
                        })
                    item['words'] = words
                    print(f"[ALIGNER] Successfully aligned {len(words)} words for stanza {i}")
                except Exception as align_e:
                    print(f"[ALIGNER] Alignment failed for stanza {i}: {align_e}")
                    item['words'] = None 
                
                item['audio_path'] = output_path
                item['duration'] = actual_duration
                item['tts_mode'] = True
            except Exception as e:
                print(f"[SUPERTONIC] Error synthesizing stanza {i}: {e}")

        with open(slicing_map_path, 'w', encoding='utf-8') as f:
            json.dump(slicing_map, f, ensure_ascii=False, indent=2)
            
        return slicing_map_path

def run_tts_step(slicing_map_path: str, temp_dir: str, voice_name: str = "M1", lang: str = "ar"):
    engine = SupertonicEngine()
    return engine.synthesize_stanzas(slicing_map_path, temp_dir, voice_name=voice_name, lang=lang)

if __name__ == "__main__":
    pass