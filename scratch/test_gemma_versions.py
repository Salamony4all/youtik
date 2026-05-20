import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_v1beta():
    api_key = os.getenv("GOOGLE_API_KEY")
    # Try explicitly with v1beta
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    for model_id in ['models/gemma-4-26b-a4b-it', 'models/gemma-4-31b-it']:
        print(f"Testing {model_id} with v1beta...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents='Write a 3-word slogan for an AI studio.'
            )
            print(f"SUCCESS {model_id}: {response.text.strip()}")
        except Exception as e:
            print(f"FAILED {model_id} v1beta: {e}")

def test_v1():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    for model_id in ['models/gemma-4-26b-a4b-it', 'models/gemma-4-31b-it']:
        print(f"Testing {model_id} with default (v1)...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents='Hi'
            )
            print(f"SUCCESS {model_id}: {response.text.strip()}")
        except Exception as e:
            print(f"FAILED {model_id} v1: {e}")

if __name__ == "__main__":
    test_v1()
    test_v1beta()
