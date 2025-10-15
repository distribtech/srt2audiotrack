import whisper
import numpy as np
import torch
import sys
# import whisperx

# def create_model_whisperx(name="large-v3"):
#     model = whisperx.load_model(name, device="cuda")
#     return model

def create_model_whisper(name="large-v3"):
    print(f"Loading Whisper model: {name}")
    model = whisper.load_model(name)
    print("Whisper model loaded successfully")
    return model

def create_model(name="large-v3",whisperx=False):
    return create_model_whisper(name)

def wav2txt(model, wav, sr, language):
    # Ensure the audio is in the correct format (float32) for Whisper
    if isinstance(wav, torch.Tensor):
        wav = wav.numpy()
    if wav.dtype != np.float32:
        wav = wav.astype(np.float32)
    return model.transcribe(wav, language=language)["text"]

# def wav2txt(model, wav, sr, language="en"):
#     print("\n=== Starting wav2txt ===")
#     print(f"Input type: {type(wav)}")
    
#     try:
#         # Handle PyTorch tensors
#         if isinstance(wav, torch.Tensor):
#             print(f"Converting PyTorch tensor to numpy array. Tensor shape: {wav.shape}, dtype: {wav.dtype}")
#             wav = wav.detach().cpu().numpy()
        
#         # Ensure we have a numpy array
#         if not isinstance(wav, np.ndarray):
#             print(f"Error: Expected numpy array or PyTorch tensor, got {type(wav)}")
#             return ""
        
#         print(f"Initial audio array shape: {wav.shape}, dtype: {wav.dtype}")
#         print(f"Initial audio stats - min: {wav.min()}, max: {wav.max()}, mean: {wav.mean()}, std: {wav.std()}")
        
#         # Convert to float32 if needed with explicit copy
#         if wav.dtype != np.float32:
#             print(f"Converting audio from {wav.dtype} to float32")
#             wav = np.ascontiguousarray(wav, dtype=np.float32)
        
#         # Handle multi-channel audio by taking mean across channels
#         if len(wav.shape) > 1:
#             print(f"Mixing {wav.shape[1]} audio channels to mono")
#             wav = np.mean(wav, axis=1, dtype=np.float32)
        
#         # Ensure audio is 1D
#         wav = wav.reshape(-1)
        
#         # Normalize to [-1, 1] range
#         max_val = np.max(np.abs(wav))
#         if max_val > 1e-7:  # Avoid division by zero
#             wav = wav / max_val
        
#         # Convert to float32 again to be absolutely sure
#         wav = wav.astype(np.float32, copy=False)
        
#         print(f"Processed audio shape: {wav.shape}, dtype: {wav.dtype}")
#         print(f"Processed audio stats - min: {wav.min()}, max: {wav.max()}, mean: {wav.mean()}, std: {wav.std()}")
        
#         # Save to a temporary file and reload to ensure clean data
#         import tempfile
#         import soundfile as sf
        
#         with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpfile:
#             tmp_path = tmpfile.name
        
#         try:
#             # Ensure sample rate is valid, default to 16000 if not provided
#             target_sr = 16000  # Whisper's default sample rate
#             if sr is not None and sr > 0:
#                 target_sr = int(sr)
#                 print(f"Using provided sample rate: {target_sr} Hz")
#             else:
#                 print(f"Using default sample rate: {target_sr} Hz")
            
#             # Save as 16-bit PCM WAV file with the specified sample rate
#             sf.write(tmp_path, wav, target_sr, subtype='PCM_16')
#             print(f"Saved temporary audio to {tmp_path} at {target_sr}Hz")
            
#             # Reload using Whisper's built-in audio loading
#             print("Loading audio with Whisper's audio loader...")
#             audio = whisper.load_audio(tmp_path, sr=target_sr)
#             print(f"Whisper loaded audio shape: {audio.shape}, dtype: {audio.dtype}")
#             print(f"Whisper audio stats - min: {audio.min()}, max: {audio.max()}, mean: {audio.mean()}, std: {audio.std()}")
            
#             # Transcribe using the loaded audio
#             print("Calling Whisper transcribe...")
#             result = model.transcribe(
#                 audio,
#                 language=language,
#                 fp16=torch.cuda.is_available()
#             )
#             print("Transcription successful")
#             return result["text"]
            
#         finally:
#             # Clean up the temporary file
#             try:
#                 import os
#                 os.unlink(tmp_path)
#             except Exception as e:
#                 print(f"Warning: Could not delete temporary file {tmp_path}: {e}")
#     except Exception as e:
#         print(f"Error in transcribing audio: {str(e)}", file=sys.stderr)
#         print(f"Audio shape: {wav.shape}, dtype: {wav.dtype}", file=sys.stderr)
#         print(f"Audio stats - min: {wav.min()}, max: {wav.max()}, mean: {wav.mean()}, std: {wav.std()}", file=sys.stderr)
        
#         # Try to save the problematic audio for debugging
#         try:
#             import soundfile as sf
#             debug_path = "debug_audio.wav"
#             sf.write(debug_path, wav, 16000)  # Assuming 16kHz sample rate
#             print(f"Saved problematic audio to: {debug_path}", file=sys.stderr)
#         except Exception as save_error:
#             print(f"Failed to save debug audio: {str(save_error)}", file=sys.stderr)
            
#         return ""       