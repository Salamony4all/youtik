import stable_whisper
try:
    print("Testing stable-whisper load with Repo ID...")
    model = stable_whisper.load_model('MAdel121/whisper-small-egyptian-arabic')
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
