import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def simulate_get_semantics():
    # Simulate the logic in 2_google_semantics.py
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1beta'})
    
    model_name = "models/gemma-4-26b-a4b-it"
    segments = [
        {"start": 0.0, "end": 5.0, "text": "اهلا بكم في برنامجنا اليوم"},
        {"start": 5.0, "end": 10.0, "text": "سنتحدث عن الذكاء الاصطناعي"}
    ]
    
    formatted_transcript = ""
    for seg in segments:
        formatted_transcript += f"[{seg['start']:.2f}] {seg['text']}\n"
        
    prompt = f"Return a JSON array of stanzas for this transcript: {formatted_transcript}. Format: [{{'title': '...', 'visual_queries': ['...', '...'], 'start_time': 0.0, 'end_time': 10.0}}]"
    
    print(f"Testing {model_name} with simulated semantics prompt...")
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json"
            )
        )
        print(f"SUCCESS: {response.text.encode('utf-8').decode('utf-8', 'ignore')}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    simulate_get_semantics()
