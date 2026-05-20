import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"), http_options={'api_version': 'v1beta'})
    print("Listing available models:")
    try:
        # Note: client.models.list() might return a pager
        for model in client.models.list():
            if "gemma" in model.name.lower():
                print(f"Name: {model.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
