from __future__ import annotations

import base64
import logging
import os
import tempfile
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .metrics import compute_metrics

try:  # pragma: no cover - optional dependency
    import whisper  # type: ignore
except Exception:  # pragma: no cover - guard against runtime import errors
    whisper = None  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Whisper QA Service", version="1.0.0")

_DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "tiny")
_MODEL_CACHE: Dict[str, "whisper.Whisper"] = {}


class WhisperAnalysisRequest(BaseModel):
    audio_b64: str = Field(..., description="Base64 encoded audio blob")
    reference_text: str = Field(..., description="Expected transcript for the audio")
    language: Optional[str] = Field(None, description="Language hint passed to Whisper")
    whisper_model: Optional[str] = Field(
        None, description="Optional override for the Whisper model to use"
    )


class WhisperAnalysisResponse(BaseModel):
    transcription: str
    word_error_rate: float
    character_error_rate: float
    missing_words: list[str]
    extra_words: list[str]
    matched_words: list[str]
    engine: str
    notes: Optional[str] = None


@app.post("/analyze", response_model=WhisperAnalysisResponse)
def analyze(request: WhisperAnalysisRequest) -> WhisperAnalysisResponse:
    try:
        audio_bytes = base64.b64decode(request.audio_b64)
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio payload: {exc}")

    transcription, engine, notes = _transcribe(
        audio_bytes,
        request.language,
        request.whisper_model or _DEFAULT_MODEL,
    )

    metrics = compute_metrics(request.reference_text, transcription)

    return WhisperAnalysisResponse(
        transcription=transcription,
        word_error_rate=metrics["word_error_rate"],
        character_error_rate=metrics["character_error_rate"],
        missing_words=list(metrics["missing"]),
        extra_words=list(metrics["extra"]),
        matched_words=list(metrics["matched"]),
        engine=engine,
        notes=notes,
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


def _transcribe(audio_bytes: bytes, language: Optional[str], model_name: str) -> Tuple[str, str, Optional[str]]:
    if whisper is None:
        logger.warning("Whisper package is not available; returning fallback result")
        return "", "unavailable", "Whisper package is not installed inside the service image."

    model = _load_model(model_name)
    if model is None:
        return "", "unavailable", f"Failed to load Whisper model '{model_name}'."

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_file.write(audio_bytes)
        tmp_path = tmp_file.name

    try:
        kwargs = {"fp16": False}
        if language:
            kwargs["language"] = language
        result = model.transcribe(tmp_path, **kwargs)
        transcription = result.get("text", "").strip()
        return transcription, model_name, None
    except Exception as exc:  # pragma: no cover - runtime guard
        logger.exception("Failed to transcribe audio with Whisper")
        return "", model_name, f"Transcription failed: {exc}"[:200]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            logger.debug("Could not remove temporary audio file %s", tmp_path)


def _load_model(model_name: str):
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    try:
        model = whisper.load_model(model_name)  # type: ignore[arg-type]
        _MODEL_CACHE[model_name] = model
        return model
    except Exception as exc:  # pragma: no cover - optional dependency issues
        logger.exception("Unable to load Whisper model '%s': %s", model_name, exc)
        return None


__all__ = [
    "analyze",
    "health",
    "_transcribe",
]
