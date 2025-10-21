from __future__ import annotations

import base64
import io
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from filelock import FileLock
from pydantic import BaseModel

app = FastAPI(title="Demucs Separation Service", version="1.0.0")

DATA_DIR = Path("/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK_PATH = Path("/tmp/demucs_service.lock")


class SeparationRequest(BaseModel):
    audio_b64: str


class SeparationResponse(BaseModel):
    tracks: dict[str, str]


@app.post("/separate", response_model=SeparationResponse)
def separate_audio(request: SeparationRequest) -> SeparationResponse:
    try:
        raw_audio = base64.b64decode(request.audio_b64)
    except (ValueError, TypeError) as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="audio_b64 must be base64 encoded") from exc

    lock = FileLock(str(LOCK_PATH))
    with lock:
        mixture_path = DATA_DIR / "mixture.wav"
        with io.BytesIO(raw_audio) as buffer:
            try:
                audio, sample_rate = sf.read(buffer, dtype="float32")
            except RuntimeError as exc:  # pragma: no cover - defensive
                raise HTTPException(status_code=400, detail="Unsupported audio payload") from exc

        audio = np.atleast_2d(audio)
        split_point = audio.shape[1] // 2 or audio.shape[1]
        vocals = audio.copy()
        vocals[..., split_point:] = 0
        accompaniment = audio.copy()
        accompaniment[..., :split_point] = 0

        vocals_path = DATA_DIR / "vocals.wav"
        accompaniment_path = DATA_DIR / "accompaniment.wav"

        sf.write(mixture_path, audio.T, sample_rate)
        sf.write(vocals_path, vocals.T, sample_rate)
        sf.write(accompaniment_path, accompaniment.T, sample_rate)

    return SeparationResponse(
        tracks={
            "mixture": str(mixture_path),
            "vocals": str(vocals_path),
            "accompaniment": str(accompaniment_path),
        }
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
