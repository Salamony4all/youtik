import os
import requests
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_google_api():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("FAIL: GOOGLE_API_KEY not found in .env")
        return False
    
    # We test with v1beta as it seems more stable for Gemma 4 models
    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
    models_to_test = ["models/gemma-4-31b-it", "models/gemma-4-26b-a4b-it", "models/gemini-2.0-flash"]
    
    all_ok = True
    for model_id in models_to_test:
        print(f"Testing {model_id} (v1beta)...")
        try:
            response = client.models.generate_content(
                model=model_id,
                contents="Write a 3-word slogan for an AI studio.",
                config=genai.types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            print(f"SUCCESS: {model_id} Working! Response: {response.text.strip()}")
        except Exception as e:
            print(f"FAIL: {model_id} Failed: {e}")
            all_ok = False
            
    return all_ok

def test_pexels_api():
    print("\nTesting Pexels API...")
    api_key = os.getenv("PEXELS_API_KEY")
    if not api_key:
        print("FAIL: PEXELS_API_KEY not found in .env")
        return False
    
    headers = {"Authorization": api_key}
    url = "https://api.pexels.com/videos/search?query=nature&per_page=1"
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            print("SUCCESS: Pexels API Working!")
            return True
        else:
            print(f"FAIL: Pexels API Failed with status {r.status_code}: {r.text}")
            return False
    except Exception as e:
        print(f"FAIL: Pexels API Error: {e}")
        return False

if __name__ == "__main__":
    g_ok = test_google_api()
    p_ok = test_pexels_api()
    
    print("\n--- Final Result ---")
    print(f"Google: {'OK' if g_ok else 'FAIL'}")
    print(f"Pexels: {'OK' if p_ok else 'FAIL'}")
