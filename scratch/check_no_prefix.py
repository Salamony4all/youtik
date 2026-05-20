import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_no_prefix():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    model_id = "gemma-4-31b-it"
    print(f"Testing {model_id} (no prefix)...")
    try:
        response = client.models.generate_content(
            model=model_id,
            contents="hi"
        )
        print(f"SUCCESS: {model_id} works")
    except Exception as e:
        print(f"FAIL: {model_id} error: {e}")

if __name__ == "__main__":
    test_no_prefix()
