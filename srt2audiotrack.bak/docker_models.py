from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Iterable


class ExternalToolError(RuntimeError):
    """Raised when an external command fails to execute correctly."""


def _run(cmd: Iterable[str]) -> None:
    """Execute ``cmd`` and raise a descriptive error on failure."""

    try:
        subprocess.run(list(cmd), check=True)
    except FileNotFoundError as exc:  # pragma: no cover - depends on user env
        raise ExternalToolError(
            "Required command could not be found. Please ensure all project "
            "dependencies are installed in the current Python environment."
        ) from exc
    except subprocess.CalledProcessError as exc:  # pragma: no cover - external tool error
        raise ExternalToolError(
            f"Command '{' '.join(exc.cmd)}' failed with exit code {exc.returncode}."
        ) from exc


def run_whisper(audio_path: str | Path, language: str = "en", model: str = "large-v3") -> None:
    """Transcribe ``audio_path`` using the locally installed Whisper CLI."""

    audio_path = Path(audio_path).resolve()
    cmd = [
        sys.executable,
        "-m",
        "whisper",
        str(audio_path),
        "--model",
        model,
        "--language",
        language,
    ]
    _run(cmd)


def run_demucs(audio_path: str | Path, output_dir: str | Path, model: str = "mdx_extra") -> None:
    """Separate accompaniment using the locally installed Demucs CLI."""

    audio_path = Path(audio_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "demucs.separate",
        "--two-stems",
        "vocals",
        "-n",
        model,
        str(audio_path),
        "--out",
        str(output_dir),
    ]
    _run(cmd)


def run_f5_tts(csv_path: str | Path, output_dir: str | Path, language: str = "en") -> None:
    """Generate speech using the local F5-TTS CLI."""

    csv_path = Path(csv_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "f5_tts.cli",
        str(csv_path),
        "--language",
        language,
        "--output",
        str(output_dir),
    ]
    _run(cmd)
