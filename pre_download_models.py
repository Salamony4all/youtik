import os
import torch
from huggingface_hub import snapshot_download

# Ensure models directory exists
os.makedirs("./models", exist_ok=True)

models_to_download = [
    {"id": "IbrahimAmin/code-switched-egyptian-arabic-whisper-small", "type": "hf"}
]

device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"--- Starting Pre-download of You-Tik Studio Models ---")
print(f"Target Directory: ./models")
print(f"Device: {device.upper()}\n")

for model_info in models_to_download:
    m_id = model_info["id"]
    m_type = model_info["type"]
    
    print(f"[*] Preparing: {m_id} ({m_type})")
    try:
        if m_type == "hf":
            owner_repo = m_id.replace("/", "--")
            local_dir = os.path.join("./models", owner_repo)
            print(f"[*] Downloading from HF Hub using snapshot_download...")
            snapshot_download(
                repo_id=m_id,
                local_dir=local_dir,
                local_dir_use_symlinks=False,
                allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.*", "merges.txt", "*.yaml"]
            )
        print(f"[SUCCESS] {m_id} is ready.\n")
    except Exception as e:
        print(f"[ERROR] Failed to download {m_id}: {e}\n")

print("--- All downloads completed ---")

