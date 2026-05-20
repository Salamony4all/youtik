import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    
    print("Listing available models...")
    try:
        # Note: list_models might not work with some keys or might return too many
        # Let's just try to generate with 31b explicitly and see the error
        model_id = "models/gemma-4-31b-it"
        print(f"Testing {model_id}...")
        response = client.models.generate_content(
            model=model_id,
            contents="hi"
        )
        print(f"SUCCESS: {model_id} works")
    except Exception as e:
        print(f"FAIL: {model_id} error: {e}")

if __name__ == "__main__":
    list_models()
