from __future__ import annotations

import base64
import os
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="srt2audiotrack Orchestrator", version="1.0.0")

templates = Jinja2Templates(directory="templates")

TTS_URL = os.getenv("TTS_URL", "http://tts_service:8001")
DEMUCS_URL = os.getenv("DEMUCS_URL", "http://demucs_service:8002")
SUBTITLES_URL = os.getenv("SUBTITLES_URL", "http://subtitles_service:8003")
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper_service:8004")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "result": None})


@app.post("/process", response_class=HTMLResponse)
async def process(
    request: Request,
    text: str = Form(...),
    speaker: str = Form("neutral"),
    subtitles: str = Form(""),
) -> HTMLResponse:
    async with httpx.AsyncClient(timeout=30.0) as client:
        tts_payload = {"text": text, "speaker": speaker}
        tts_response = await _post_json(client, f"{TTS_URL}/synthesize", tts_payload)

        demucs_payload = {"audio_b64": tts_response["audio_b64"]}
        demucs_response = await _post_json(client, f"{DEMUCS_URL}/separate", demucs_payload)

        subtitle_result: dict[str, Any] | None = None
        if subtitles.strip():
            subtitle_payload = {"subtitle_text": subtitles}
            subtitle_result = await _post_json(client, f"{SUBTITLES_URL}/subtitles", subtitle_payload)
            vocabulary = await _get_json(client, f"{SUBTITLES_URL}/vocabulary")
        else:
            vocabulary = None

        whisper_result = await _maybe_post_json(
            client,
            f"{WHISPER_URL}/analyze",
            {"audio_b64": tts_response["audio_b64"], "reference_text": text},
        )

    decoded_audio_len = len(base64.b64decode(tts_response["audio_b64"]))
    result = {
        "speaker": tts_response["speaker"],
        "audio_path": tts_response["audio_path"],
        "demucs_tracks": demucs_response["tracks"],
        "subtitle_result": subtitle_result,
        "vocabulary": vocabulary,
        "whisper_evaluation": whisper_result,
        "audio_bytes": decoded_audio_len,
    }

    return templates.TemplateResponse("index.html", {"request": request, "result": result})


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    response = await client.get(url)
    response.raise_for_status()
    return response.json()


async def _maybe_post_json(
    client: httpx.AsyncClient, url: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    try:
        return await _post_json(client, url, payload)
    except httpx.HTTPError:
        return None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
