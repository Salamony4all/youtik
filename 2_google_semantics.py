import os
import json
from google import genai
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

def generate_create_mode_script(prompt: str, temp_dir: str, model_name: str = "models/gemma-4-31b-it") -> str:
    """Writes an original script from a prompt and formats it directly for TTS rendering."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1beta'})
    
    sys_prompt = f"""
    You are an elite TikTok scriptwriter and cinematic director. 
    Write a highly engaging, viral 30-to-45 second spoken-word script in Egyptian Arabic based on this prompt: "{prompt}".
    
    CRITICAL RULES:
    1. Hook the viewer immediately.
    2. Write in Egyptian Ammiya.
    3. Split the script into 3 to 5 logical "stanzas" (scenes). 
    
    Format the output as a JSON array exactly like this:
    [
      {{
        "scene_index": 0,
        "title": "The Hook",
        "text": "The arabic dialogue to be spoken.",
        "visual_queries": ["cinematic lonely street night", "moody lighting"],
        "start_time": 0.0,
        "end_time": 0.0,
        "duration": 0.0,
        "tts_mode": true
      }}
    ]
    
    Return ONLY the raw JSON array. Do not include markdown blocks.
    """
    
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
        
    response = client.models.generate_content(
        model=model_name,
        contents=sys_prompt,
        config=genai.types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8)
    )
    
    text = response.text.strip()
    if "```" in text:
        text = text.split("```json")[1].split("```")[0].strip() if "```json" in text else text.split("```")[1].strip()
        
    script_data = json.loads(text)
    
    output_json = os.path.join(temp_dir, "slicing_map.json")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
        
    return output_json

def get_semantics(segments: List[Dict], model_name: str = "models/gemma-4-31b-it", song_name: str = "", artist_name: str = "") -> List[Dict]:
    """Analyzes transcript segments and groups them into cinematic stanzas using Google GenAI."""
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1beta'})
    
    total_duration = segments[-1]['end'] - segments[0]['start']
    total_minutes = total_duration / 60.0
    target_count = max(3, min(60, int(total_minutes * 1.5 + 2)))
    
    formatted_transcript = ""
    for seg in segments:
        formatted_transcript += f"[{seg['start']:.2f}] {seg['text']}\n"

    context_str = f"'{song_name}' by {artist_name}" if song_name and artist_name else "this Egyptian Arabic song"

    prompt = f"""
    You are a world-class Cinematic Director and Visual Concept Artist specializing in high-end music videos and art-house cinema.
    Your task is to analyze the lyrics of {context_str} and conceptualize a series of {target_count} atmospheric scenes that serve as a visual poem.
    
    STYLE GUIDELINES:
    - VIBE: Melancholic, surreal, and deeply poetic. Focus on "The Soul of the Scene" rather than literal action.
    - VISUALS: High contrast, cinematic lighting, rich textures, and evocative compositions.
    - CULTURAL SOUL: Capture the specific vibe of {context_str}.
    
    For each scene (stanza), return a JSON object with:
    1. "title": A poetic, evocative Arabic title (Fusha or elegant Ammiya).
    2. "text": The EXACT lyrics (Arabic) from the transcript that correspond to this stanza's time range. This is CRITICAL for subtitle generation.
    3. "visual_queries": A list of exactly 2 English search prompts for premium stock footage.
    4. "start_time": The start time (from transcript).
    5. "end_time": The end_time (from transcript).

    TRANSCRIPT:
    {formatted_transcript}

    CRITICAL REQUIREMENTS:
    - Return exactly {target_count} stanzas.
    - Output ONLY valid JSON.
    """
    
    try:
        if model_name and not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        primary_models = [
            "models/gemma-4-31b-it",
            "models/gemma-4-26b-a4b-it",
            "models/gemini-2.0-flash"
        ]
    
        if model_name in primary_models:
            primary_models.remove(model_name)
        primary_models.insert(0, model_name)
        
        response_text = None
        last_error = None
    
        for i, current_model in enumerate(primary_models):
            for attempt in range(1, 3):
                try:
                    print(f"[SEMANTICS] Attempting: {current_model} (Try {attempt}/2)...")
                    response = client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                        config=genai.types.GenerateContentConfig(response_mime_type="application/json", temperature=0.75)
                    )
                    response_text = response.text
                    if response_text: break
                except Exception as e:
                    last_error = str(e)
                    if attempt == 2: continue
            if response_text: break

        if not response_text:
            raise Exception(f"All models failed. Last error: {last_error}")
        
        text = response_text.strip()
        if "```" in text:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            else:
                text = text.split("```")[1].strip()
            
        return json.loads(text)
        
    except Exception as e:
        generic_vibe_pool = [
            ["cinematic landscape, ethereal lighting"],
            ["abstract motion, slow-motion particles"],
            ["urban street life, moody shadows"],
            ["nature macro, golden hour focus"],
            ["tech grid, futuristic blue glow"],
            ["spiritual atmosphere, soft bokeh"]
        ]
        
        chunk_size = total_duration / target_count
        fallback_semantics = []
        for i in range(target_count):
            vibe_idx = i % len(generic_vibe_pool)
            fallback_semantics.append({
                "title": f"الجزء {i+1}", 
                "visual_queries": generic_vibe_pool[vibe_idx], 
                "start_time": segments[0]['start'] + (i * chunk_size), 
                "end_time": segments[0]['start'] + ((i + 1) * chunk_size)
            })
        return fallback_semantics

def run_pipeline_step_2(full_transcript_json_path: str, temp_dir: str, google_model: str = "models/gemma-4-31b-it", song_name: str = "", artist_name: str = "", skip_ai: bool = False):
    with open(full_transcript_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    
    if skip_ai:
        semantics = []
        for i in range(0, len(segments), 4):
            chunk = segments[i:i+4]
            stanza_text = " ".join([s['text'] for s in chunk])
            semantics.append({
                "title": f"Stanza {len(semantics) + 1}",
                "text": stanza_text,
                "visual_queries": ["cinematic slow motion texture", "atmospheric lighting depth"],
                "start_time": chunk[0]['start'],
                "end_time": chunk[-1]['end']
            })
    else:
        semantics = get_semantics(segments, model_name=google_model, song_name=song_name, artist_name=artist_name)
    
    output_json = os.path.join(temp_dir, "semantics.json")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(semantics, f, ensure_ascii=False, indent=2)
        
    return output_json