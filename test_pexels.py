import os
import requests
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
        print(f"Response: {r.text}")
        r.raise_for_status()
        data = r.json()
        if data.get('videos'):
            print("✅ Success: Video found!")
            return True
        else:
            print("❌ Failure: No videos found in response.")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if not PEXELS_API_KEY:
        print("API Key missing!")
    else:
        test_pexels("cinematic nature background")
