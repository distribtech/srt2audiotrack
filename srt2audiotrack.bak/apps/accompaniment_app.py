from __future__ import annotations

import argparse
from pathlib import Path

from ..docker_models import run_demucs
from ..lock_utils import file_lock


def split_accompaniment(audio_path: str | Path, output_dir: str | Path, model: str = "mdx_extra") -> Path:
    """Extract accompaniment from ``audio_path`` using the local Demucs installation."""
    with file_lock(audio_path):
        run_demucs(audio_path, output_dir, model=model)
        return Path(output_dir)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Split vocals and accompaniment")
    parser.add_argument("audio", help="Input audio file")
    parser.add_argument("output", help="Directory for separated tracks")
    parser.add_argument("--model", default="mdx_extra", help="Demucs model name")
    args = parser.parse_args(argv)
    split_accompaniment(args.audio, args.output, args.model)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
