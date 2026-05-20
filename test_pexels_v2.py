import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

def test_pexels(query):
    print(f"Testing query: {query}")
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=portrait"
    try:
        r = requests.get(url, headers=headers)
        print(f"Status Code: {r.status_code}")
        # Save response to file to avoid console encoding issues
        with open("pexels_debug.json", "w", encoding="utf-8") as f:
            f.write(r.text)
        
        if r.status_code == 401:
            print("❌ API Key is UNAUTHORIZED (401).")
            return False
        elif r.status_code == 403:
            print("❌ API Key is FORBIDDEN (403).")
            return False
        
        r.raise_for_status()
        data = r.json()
        if data.get('videos') and len(data['videos']) > 0:
            print("✅ Success: Video found!")
            return True
        else:
            print("❌ Failure: No videos found in response.")
            return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    if not PEXELS_API_KEY:
        print("API Key missing from .env!")
    else:
        test_pexels("cinematic nature background")
