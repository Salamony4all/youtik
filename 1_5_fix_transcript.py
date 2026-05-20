import os
import json
from google import genai
from google.genai.types import GenerateContentConfig
from dotenv import load_dotenv
from difflib import SequenceMatcher

load_dotenv()

def align_words_pro(original_word_segments, corrected_text):
    """
    Aligns corrected text to the original high-precision word timestamps using fuzzy matching.
    This ensures that even if words are corrected/changed, they anchor to the actual vocal peaks.
    """
    corrected_words = corrected_text.strip().split()
    if not corrected_words:
        return []
    
    # Extract the original words and their metadata
    # word_segments is a flat list of ALL words in the audio with high precision
    orig_words = [w.get('word', '').strip() for w in original_word_segments]
    
    # We use a sequence matcher to find the best mapping between corrected and original words
    matcher = SequenceMatcher(None, corrected_words, orig_words)
    
    new_words = []
    
    # Start/End boundaries for fallback interpolation
    seg_start = original_word_segments[0]['start'] if original_word_segments else 0.0
    seg_end = original_word_segments[-1]['end'] if original_word_segments else 0.1
    duration = seg_end - seg_start
    
    # Track which original word we are currently "near"
    current_orig_idx = 0
    
    # We iterate through the matches
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Perfect match: Copy the high-precision timestamps!
            for k in range(i2 - i1):
                orig_w = original_word_segments[j1 + k]
                new_words.append({
                    "word": corrected_words[i1 + k],
                    "start": orig_w['start'],
                    "end": orig_w['end']
                })
                current_orig_idx = j1 + k + 1
        elif tag in ['replace', 'insert']:
            # For new/changed words, we interpolate between the last match and the next match
            # Find the boundaries for this "gap"
            gap_start = original_word_segments[j1]['start'] if j1 < len(original_word_segments) else (new_words[-1]['end'] if new_words else seg_start)
            gap_end = original_word_segments[j2-1]['end'] if j2 > 0 and j2 <= len(original_word_segments) else (original_word_segments[j1]['start'] if j1 < len(original_word_segments) else seg_end)
            
            num_words = i2 - i1
            if num_words > 0:
                gap_duration = max(0.1, gap_end - gap_start)
                word_dur = gap_duration / num_words
                for k in range(num_words):
                    new_words.append({
                        "word": corrected_words[i1 + k],
                        "start": round(gap_start + (k * word_dur), 3),
                        "end": round(gap_start + ((k + 1) * word_dur), 3)
                    })
        # 'delete' tag is ignored because the original words are "extra" noise
            
    return new_words

def fix_transcript(transcript_path, song_name, artist_name, official_lyrics, google_model="models/gemma-4-31b-it"):
    """
    Uses AI to correct a transcript and anchors it to high-precision WhisperX word timestamps.
    """
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1beta'})
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data.get("segments", [])
    # Ground Truth Timing: word_segments is the raw, unmerged, high-precision output from WhisperX
    raw_word_segments = data.get("word_segments", [])
    if not raw_word_segments:
        # Fallback if WhisperX alignment failed
        raw_word_segments = [w for s in segments for w in s.get('words', [])]

    # Lightweight text protocol
    text_segments = [f"[{i}] {seg['text']}" for i, seg in enumerate(segments)]
    rough_text_block = "\n".join(text_segments)

    lyrics_context = f"Official Lyrics:\n{official_lyrics}" if official_lyrics else f"Please retrieve accurate lyrics for '{song_name}' by '{artist_name}'."
    
    prompt = f"""
    You are a professional Egyptian Arabic Lyricist and Audio Editor. 
    Your goal is to RECONSTRUCT a rough transcription into the PERFECT official lyrics for '{song_name}' by '{artist_name}'.
    
    GROUND TRUTH LYRICS (USE THESE):
    {lyrics_context}
    
    ROUGH TRANSCRIPTION (FIX THIS):
    {rough_text_block}
    
    CRITICAL RULES:
    1. Every segment MUST match the official lyrics exactly as sung.
    2. If the rough transcript has a wrong word (e.g., 'بالسين'), replace it with the correct word from ground truth (e.g., 'بالسنين').
    3. Keep the Egyptian dialect (Ammiya) preserved.
    4. Return exactly {len(segments)} segments in a JSON list 'corrected_segments'.
    5. Each segment in 'corrected_segments' should be the FULL fixed text for that segment.
    """
    
    # Normalize model ID
    if google_model and not google_model.startswith("models/"):
        google_model = f"models/{google_model}"
    
    models_to_try = ["models/gemma-4-31b-it", "models/gemma-4-26b-a4b-it", "models/gemini-2.0-flash"]
    if google_model and google_model in models_to_try:
        models_to_try.remove(google_model)
        models_to_try.insert(0, google_model)
    
    print(f"[ULTRA-FIX] Fetching correction from AI...")
    corrected_response = None
    for model_name in models_to_try:
        for attempt in range(1, 3):  # Attempt each model twice
            try:
                print(f"[ULTRA-FIX] Attempting {model_name} (Try {attempt}/2)...")
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                )
                corrected_response = json.loads(response.text)
                print(f"[ULTRA-FIX] Success with {model_name}")
                break
            except Exception as e:
                print(f"[ULTRA-FIX] Model {model_name} (Try {attempt}/2) failed: {e}")
                if attempt == 2:
                    continue
        if corrected_response:
            break

    if not corrected_response:
        return False

    try:
        corrected_texts = corrected_response.get('corrected_segments', [])
        full_lyrics = corrected_response.get('corrected_lyrics', "")

        # ULTRA-PRECISION ALIGNMENT PHASE
        # Instead of aligning within segments, we align the WHOLE song for better context
        # but we use segment boundaries as soft anchors.
        
        for i, seg in enumerate(segments):
            if i < len(corrected_texts):
                new_text = corrected_texts[i]
                
                # Filter raw_word_segments to find original words spoken in this segment's timeframe
                # We add a 0.5s buffer to catch words that were slightly misaligned in the rough pass
                orig_words_in_seg = [
                    w for w in raw_word_segments 
                    if w['start'] >= (seg['start'] - 0.5) and w['end'] <= (seg['end'] + 0.5)
                ]
                
                if not orig_words_in_seg:
                    # Fallback to linear interpolation if no raw words found in timeframe
                    orig_words_in_seg = seg.get('words', [])

                seg['words'] = align_words_pro(orig_words_in_seg, new_text)
                seg['text'] = new_text
        
        data['segments'] = segments
        data['text'] = " ".join([s['text'] for s in segments])
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"[ULTRA-FIX] Finished with high-precision anchoring.")
        return True
    except Exception as e:
        print(f"[ERROR] Ultra-fix failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 4:
        lyrics = ""
        if os.path.exists(sys.argv[4]):
            with open(sys.argv[4], 'r', encoding='utf-8') as lf:
                lyrics = lf.read()
        model = sys.argv[5] if len(sys.argv) > 5 else "models/gemma-4-31b-it"
        fix_transcript(sys.argv[1], sys.argv[2], sys.argv[3], lyrics, model)
