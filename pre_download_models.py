import os
from huggingface_hub import snapshot_download

# Ensure models directory exists
os.makedirs("./models", exist_ok=True)

# Whisper model(s) to pre-download during Docker build
models_to_download = [
    {"id": "IbrahimAmin/code-switched-egyptian-arabic-whisper-small", "local": "IbrahimAmin--code-switched-egyptian-arabic-whisper-small"},
]

print(f"--- Starting Pre-download of You-Tik Studio Models ---")
print(f"Target Directory: ./models\n")

for model_info in models_to_download:
    m_id = model_info["id"]
    local_dir = os.path.join("./models", model_info["local"])

    print(f"[*] Downloading: {m_id} -> {local_dir}")
    try:
        snapshot_download(
            repo_id=m_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.*", "merges.txt", "*.yaml", "*.model"]
        )
        print(f"[SUCCESS] {m_id} is ready.\n")
    except Exception as e:
        print(f"[WARNING] Failed to download {m_id}: {e}\n")

print("--- All downloads completed ---")
