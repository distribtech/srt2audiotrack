from __future__ import annotations

import base64
import math
import wave
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException
from filelock import FileLock
from pydantic import BaseModel, Field

app = FastAPI(title="Simple TTS Service", version="1.0.0")

DATA_DIR = Path("/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK_PATH = Path("/tmp/tts_service.lock")
SAMPLE_RATE = 16_000


class TtsRequest(BaseModel):
    text: str = Field(..., description="Plain text that should be synthesised into speech")
    speaker: Literal["neutral", "energetic"] = Field(
        "neutral", description="Name of the mock speaker profile"
    )


class TtsResponse(BaseModel):
    audio_path: str
    audio_b64: str
    speaker: str


@app.post("/synthesize", response_model=TtsResponse)
def synthesize(request: TtsRequest) -> TtsResponse:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    lock = FileLock(str(LOCK_PATH))
    with lock:
        output_path = DATA_DIR / f"tts_{abs(hash((text, request.speaker)))}.wav"
        if not output_path.exists():
            _synthesize_wave(text, output_path, request.speaker)
        audio_b64 = base64.b64encode(output_path.read_bytes()).decode("ascii")

    return TtsResponse(audio_path=str(output_path), audio_b64=audio_b64, speaker=request.speaker)


def _synthesize_wave(text: str, output_path: Path, speaker: str) -> None:
    duration_seconds = max(1.0, min(len(text) / 10.0, 10.0))
    samples = int(duration_seconds * SAMPLE_RATE)
    t = np.linspace(0, duration_seconds, samples, endpoint=False)

    base_freq = 200 if speaker == "energetic" else 150
    modulation = np.sin(2 * math.pi * 2 * t)
    waveform = 0.1 * np.sin(2 * math.pi * base_freq * t + 0.2 * modulation)

    data = np.int16(waveform * 32767)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(data.tobytes())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
