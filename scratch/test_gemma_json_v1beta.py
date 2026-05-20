import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_json_mode_v1beta():
    api_key = os.getenv("GOOGLE_API_KEY")
    # Try with v1beta
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    prompt = "Return a JSON object with a 'message' field saying 'hello'."
    
    for model_id in ['models/gemma-4-31b-it']:
        print(f"Testing {model_id} with JSON mode on v1beta...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            print(f"SUCCESS {model_id}: {response.text.strip()}")
        except Exception as e:
            print(f"FAILED {model_id} JSON mode v1beta: {e}")

if __name__ == "__main__":
    test_json_mode_v1beta()
