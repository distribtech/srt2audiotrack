from __future__ import annotations

import subprocess
from pathlib import Path


def run_whisper(audio_path: str | Path, language: str = "en", model: str = "large-v3") -> None:
    """Transcribe ``audio_path`` using OpenAI Whisper in Docker.

    The function delegates to the official Whisper Docker image.  The caller is
    responsible for mounting directories that contain the audio file.
    """
    audio_path = Path(audio_path).resolve()
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{audio_path.parent}:/data",
        "ghcr.io/ggerganov/whisper.cpp:latest",
        "--model",
        model,
        "--language",
        language,
        f"/data/{audio_path.name}",
    ]
    subprocess.run(cmd, check=True)


def run_demucs(audio_path: str | Path, output_dir: str | Path, model: str = "mdx_extra") -> None:
    """Separate accompaniment using Demucs inside Docker."""
    audio_path = Path(audio_path).resolve()
    output_dir = Path(output_dir).resolve()
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{audio_path.parent}:/data",
        "-v",
        f"{output_dir}:/out",
        "facebookresearch/demucs:latest",
        "--two-stems",
        "vocals",
        "-n",
        model,
        f"/data/{audio_path.name}",
        "-o",
        "/out",
    ]
    subprocess.run(cmd, check=True)


def run_f5_tts(csv_path: str | Path, output_dir: str | Path, language: str = "en") -> None:
    """Generate speech using F5-TTS in Docker."""
    csv_path = Path(csv_path).resolve()
    output_dir = Path(output_dir).resolve()
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{csv_path.parent}:/data",
        "-v",
        f"{output_dir}:/out",
        "ghcr.io/f5tts/f5-tts:latest",
        f"/data/{csv_path.name}",
        "--language",
        language,
        "--output",
        "/out",
    ]
    subprocess.run(cmd, check=True)
