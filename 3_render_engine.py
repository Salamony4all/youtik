import os
import json
import ffmpeg
import requests
from typing import List, Dict, Callable
from dotenv import load_dotenv

load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(_SCRIPT_DIR, "fonts")

def fetch_pexels_video(query: str, output_path: str):
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    try:
        print(f"Searching Pexels for: {query}...")
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get('videos') and len(data['videos']) > 0:
            video_url = data['videos'][0]['video_files'][0]['link']
            print(f"Found video: {video_url}. Downloading...")
            video_data = requests.get(video_url, timeout=30).content
            with open(output_path, 'wb') as f:
                f.write(video_data)
            return True
        else:
            print(f"No videos found for query: {query}")
    except Exception as e:
        print(f"Error fetching video for {query}: {str(e)}")
    return False

def run_precision_slicing_step(transcript_json_path: str, semantics_json_path: str, temp_dir: str, model_id: str = "large-v3-turbo") -> str:
    with open(transcript_json_path, 'r', encoding='utf-8') as f:
        transcript_data = json.load(f)
    with open(semantics_json_path, 'r', encoding='utf-8') as f:
        semantics = json.load(f)
    
    print(f"[*] Initializing Smart Vocal-Centric Slicing (Engine: {model_id})")

    vocal_points = []
    for seg in transcript_data.get('segments', []):
        if 'words' in seg:
            for w in seg['words']:
                vocal_points.append({'start': w['start'], 'end': w['end']})
        else:
            vocal_points.append({'start': seg['start'], 'end': seg['end']})

    slicing_map = []
    for i, sem in enumerate(semantics):
        raw_start = float(sem.get('start_time', 0.0))
        raw_end = float(sem.get('end_time', raw_start + 10.0))
        
        start_t = raw_start
        end_t = raw_end
        
        all_segments = transcript_data.get('segments', [])
        
        best_seg_start = min(all_segments, key=lambda s: abs(s['start'] - raw_start)) if all_segments else None
        if best_seg_start and abs(best_seg_start['start'] - raw_start) < 2.0:
            start_t = best_seg_start['start']
            
        best_seg_end = min(all_segments, key=lambda s: abs(s['end'] - raw_end)) if all_segments else None
        if best_seg_end and abs(best_seg_end['end'] - raw_end) < 2.0:
            end_t = best_seg_end['end']

        start_t = max(0.0, start_t - 0.2)
        end_t = end_t + 0.3 
        
        duration = end_t - start_t
        
        slicing_map.append({
            "scene_index": i,
            "title": sem.get('title', f'scene_{i}'),
            "text": sem.get('text', ''),
            "start_time": start_t,
            "end_time": end_t,
            "duration": duration,
            "visual_queries": sem.get('visual_queries', [])
        })
    
    slicing_json = os.path.join(temp_dir, "slicing_map.json")
    with open(slicing_json, 'w', encoding='utf-8') as f:
        json.dump(slicing_map, f, ensure_ascii=False, indent=2)
        
    return slicing_json

def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    if cs == 100:
        s += 1
        cs = 0
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

SUBTITLE_STYLES = {
    "TikTok": "Style: TikTok,Lalezar,154,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,12,3,5,30,30,80,178",
    "Cinematic": "Style: Cinematic,Amiri,126,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,6,2,5,30,30,120,178",
    "Calligraphy": "Style: Calligraphy,Aref Ruqaa,154,&H00E6F0FA,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,6,2,5,30,30,120,178",
    "Dynamic": "Style: Dynamic,Reem Kufi,147,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,10,0,5,30,30,100,178",
    "Glow": "Style: Glow,Aref Ruqaa,140,&H00FFFFFF,&H000000FF,&H00FF00FF,&H00000000,-1,0,0,0,100,100,0,0,1,14,14,5,30,30,100,178",
    "Box": "Style: Box,Reem Kufi,133,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,1,1,5,30,30,100,178",
    "MegaPop": "Style: MegaPop,Lalezar,126,&H0000FFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,15,3,5,30,30,80,178"
}

def generate_clip_subtitles(transcript_data: Dict, start_t: float, end_t: float, output_ass: str, style_name: str = "Dynamic", override_text: str = None, is_tts: bool = False, forced_duration: float = None, words: List[Dict] = None):
    import re
    
    style_definition = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["Dynamic"])
    
    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_definition}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    
    clip_words = []

    if words and len(words) > 0:
        clip_words = words
        if is_tts:
            start_t = 0.0
    elif is_tts and forced_duration:
        text_to_use = override_text if override_text else ""
        clean_text = re.sub(r'[^\w\s\u0600-\u06FF]', '', text_to_use).strip()
        words = clean_text.split()
        if words:
            chunk_dur = forced_duration / len(words)
            for j, w_txt in enumerate(words):
                clip_words.append({
                    'start': j * chunk_dur,
                    'end': (j + 1) * chunk_dur,
                    'word': w_txt
                })
        start_t = 0.0
    else:
        all_words = []
        for segment in transcript_data.get('segments', []):
            if 'words' in segment:
                all_words.extend(segment['words'])
            else:
                all_words.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'word': segment['text']
                })
                
        MUSIC_KEYWORDS = ["موسيقى", "music", "[music]", "(music)", "background", "instrumental"]
        for w in all_words:
            text = w.get('word', w.get('text', "")).lower().strip()
            if any(k in text for k in MUSIC_KEYWORDS):
                continue
            if w['end'] > start_t and w['start'] < end_t:
                clip_words.append(w)
        
        if override_text and override_text.strip():
            new_words = re.sub(r'[^\w\s\u0600-\u06FF]', '', override_text).split()
            if new_words:
                mapped_words = []
                num_slots = len(clip_words)
                if num_slots == 0:
                    chunk_dur = (end_t - start_t) / len(new_words)
                    for j, nw in enumerate(new_words):
                        mapped_words.append({
                            'start': start_t + (j * chunk_dur),
                            'end': start_t + ((j + 1) * chunk_dur),
                            'word': nw
                        })
                else:
                    for j, nw in enumerate(new_words):
                        slot_idx = min(j, num_slots - 1)
                        orig_slot = clip_words[slot_idx]
                        mapped_words.append({
                            'start': orig_slot['start'],
                            'end': orig_slot['end'],
                            'word': nw
                        })
                clip_words = mapped_words

    context_chunks = []
    chunk_size = 1 
    for i in range(0, len(clip_words), chunk_size):
        chunk = clip_words[i:i + chunk_size]
        context_chunks.append(chunk)

    with open(output_ass, 'w', encoding='utf-8') as f:
        f.write(ass_header)
        for chunk in context_chunks:
            for i, word in enumerate(chunk):
                w_start = max(0.0, word['start'] - start_t)
                w_end = max(0.0, word['end'] - start_t)
                start_str = format_ass_time(w_start)
                end_str = format_ass_time(w_end)
                
                def clean_text(t):
                    return re.sub(r'[^\w\s\u0600-\u06FF]', '', t).strip()
                
                text_content = clean_text(word.get('word', word.get('text', "")))
                if not text_content: continue

                if style_name in ["Cinematic", "Calligraphy", "MegaPop"]:
                    animated_text = f"{{\\fad(100,100)\\fscx200\\fscy200\\t(0,100,\\fscx600\\fscy600)\\t(100,200,\\fscx350\\fscy350)}}{text_content}"
                else:
                    animated_text = f"{{\\fad(50,50)\\t(0,120,\\fscx130\\fscy130)\\t(120,250,\\fscx100\\fscy100)}}{text_content}"
                
                f.write(f"Dialogue: 0,{start_str},{end_str},{style_name},,0,0,0,,{animated_text}\n")

def render_video(slicing_json_path: str, audio_path: str, output_dir: str, subtitle_style: str = "Dynamic", on_clip_finished: Callable = None) -> List[str]:
    temp_dir = os.path.dirname(slicing_json_path)
    
    with open(slicing_json_path, 'r', encoding='utf-8') as f:
        slicing_map = json.load(f)
        
    transcript_data = {}
    transcript_path = os.path.join(temp_dir, "full_transcript.json")
    if os.path.exists(transcript_path):
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
    generated_clips = []
    
    fallback_video_path = os.path.join(temp_dir, "fallback.mp4")
    if not os.path.exists(fallback_video_path):
        fetch_pexels_video("cinematic dark abstract background", fallback_video_path)
    
    os.makedirs(output_dir, exist_ok=True)
    
    for item in slicing_map:
        scene_idx = item.get('scene_index', 0)
        scene_name = "".join([c if c.isalnum() else "_" for c in item['title'].lower()])
        query = item['visual_queries'][0] if item.get('visual_queries') else "cinematic background"
        
        video_path = os.path.join(temp_dir, f"bg_{scene_idx}.mp4")
        ass_path = os.path.join(temp_dir, f"subs_{scene_idx}.ass")
        clip_output_path = os.path.join(output_dir, f"clip_{scene_idx:02d}_{scene_name}.mp4")
        
        if not fetch_pexels_video(query, video_path):
            video_path = fallback_video_path
            
        is_tts = item.get('tts_mode', False)
        generate_clip_subtitles(
            transcript_data, 
            item['start_time'], 
            item['end_time'], 
            ass_path, 
            style_name=subtitle_style, 
            override_text=item.get('text'), 
            is_tts=is_tts, 
            forced_duration=item.get('duration'),
            words=item.get('words')
        )
            
        rel_ass_path = os.path.relpath(ass_path, os.getcwd())
        safe_ass_path = rel_ass_path.replace('\\', '/')
        
        v_stream = (
            ffmpeg.input(video_path, stream_loop=-1).video
            .trim(duration=item['duration'])
            .setpts('PTS-STARTPTS')
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
            .filter('crop', 1080, 1920)
            .filter('fps', fps=30, round='up')
            .filter('setsar', 1)
            .filter('subtitles', safe_ass_path, fontsdir=FONTS_DIR.replace('\\', '/'))
            .filter('fade', type='in', duration=0.3, start_time=0)
            .filter('fade', type='out', duration=0.3, start_time=item['duration'] - 0.3)
        )
        
        stanza_audio = item.get('audio_path', audio_path)
        
        if is_tts:
            voice_stream = ffmpeg.input(stanza_audio).audio.filter('atrim', start=0, end=item['duration']).filter('volume', 1.5)
            music_track = audio_path if audio_path and os.path.exists(audio_path) else os.path.join(os.getcwd(), "lofi_beat.wav")
            
            if os.path.exists(music_track):
                start_music_t = item.get('start_time', 0.0) 
                beat_stream = (ffmpeg.input(music_track)
                                     .audio
                                     .filter('atrim', start=start_music_t, end=start_music_t + item['duration'])
                                     .filter('volume', 0.25))
                
                a_stream = (ffmpeg.filter([voice_stream, beat_stream], 'amix', inputs=2, duration='shortest')
                                  .filter('afade', type='in', duration=0.4, start_time=0)
                                  .filter('afade', type='out', duration=0.4, start_time=item['duration'] - 0.4))
            else:
                a_stream = voice_stream.filter('afade', type='in', duration=0.4, start_time=0).filter('afade', type='out', duration=0.4, start_time=item['duration'] - 0.4)
        else:
            a_stream = (
                ffmpeg.input(stanza_audio).audio
                .filter('atrim', start=item['start_time'], end=item['end_time'])
                .filter('asetpts', 'PTS-STARTPTS')
                .filter('afade', type='in', duration=0.4, start_time=0)
                .filter('afade', type='out', duration=0.4, start_time=item['duration'] - 0.4)
            )
        
        print(f"Rendering Clip {scene_idx}: {item['title']}...")
        
        try:
            ffmpeg.output(v_stream, a_stream, clip_output_path, vcodec='libx264', acodec='aac', preset='fast', threads=1).run(overwrite_output=True, capture_stderr=True)
            generated_clips.append(clip_output_path)
            print(f"Success: {clip_output_path}")
            
            if on_clip_finished:
                on_clip_finished(clip_output_path)
        except ffmpeg.Error as e:
            print(f"\n=== FFMPEG CRASH LOG FOR CLIP {scene_idx} ===")
            if e.stderr:
                print(e.stderr.decode('utf8'))
            else:
                print("No stderr output captured.")
            print("========================\n")
            print(f"Skipping Clip {scene_idx} due to error.")
 
    return generated_clips
 
def run_pipeline_step_3(slicing_json_path: str, audio_path: str, output_dir: str, subtitle_style: str = "Dynamic"):
    return render_video(slicing_json_path, audio_path, output_dir, subtitle_style=subtitle_style)

if __name__ == "__main__":
    run_pipeline_step_3("./temp/slicing_map.json", "./temp/source_audio.wav", "./output_clips")