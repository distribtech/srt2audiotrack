from __future__ import annotations

import argparse
from pathlib import Path

from ..docker_models import run_f5_tts
from ..lock_utils import file_lock


def generate_audio(csv_file: str | Path, output_dir: str | Path, language: str = "en") -> Path:
    """Generate speech audio files from a CSV using F5-TTS in Docker."""
    with file_lock(csv_file):
        run_f5_tts(csv_file, output_dir, language=language)
        return Path(output_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate audio from CSV")
    parser.add_argument("csv", help="Input CSV file")
    parser.add_argument("output", help="Directory where audio fragments are stored")
    parser.add_argument("--language", default="en", help="Language for TTS model")
    args = parser.parse_args(argv)
    generate_audio(args.csv, args.output, args.language)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
