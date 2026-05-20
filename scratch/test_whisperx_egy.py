import whisperx
import torch

try:
    device = "cpu"
    compute_type = "int8"
    model_name = "moeshawky/faster-whisper-small-egyptian-arabic"
    print(f"Testing WhisperX load for {model_name}...")
    model = whisperx.load_model(model_name, device, compute_type=compute_type)
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
