import wave
import struct
import os
import traceback

# Create 1s silent WAV
wav_path = 'test_silence.wav'
if not os.path.exists(wav_path):
    with wave.open(wav_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        frames = b''.join([struct.pack('<h', 0) for _ in range(16000)])
        wf.writeframes(frames)

print(f"Created test WAV: {wav_path}")

from importlib import import_module

model_id = os.environ.get('TEST_MODEL_ID', 'large-v3-turbo')
print(f"Attempting to load model: {model_id}")

try:
    m = import_module('1_ingest_and_split')
    # Call transcribe_full which attempts model loading
    res = m.transcribe_full(wav_path, model_id=model_id)
    print("transcribe_full returned keys:", list(res.keys()))
except Exception as e:
    print("Exception during model load:")
    traceback.print_exc()

print('Test script finished')
