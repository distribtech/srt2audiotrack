from __future__ import annotations

import argparse
from pathlib import Path

from .. import pipeline, subtitle_csv
from ..lock_utils import file_lock


def generate_csv(subtitle: str | Path, vocabular: str | Path, output_folder: str | Path = "") -> Path:
    """Generate intermediate CSV files from a subtitle file."""
    with file_lock(subtitle):
        directory, subtitle_name, out_path = pipeline.prepare_subtitles(
            subtitle, vocabular, output_folder
        )
        srt_csv_file = directory / f"{subtitle_name}_1.0_srt.csv"
        if not srt_csv_file.exists():
            subtitle_csv.srt_to_csv(out_path, srt_csv_file)
        return srt_csv_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create CSV from SRT subtitles")
    parser.add_argument("subtitle", help="Path to subtitle file")
    parser.add_argument("vocabular", help="Path to vocabulary file")
    parser.add_argument("--output", default="", help="Optional output directory")
    args = parser.parse_args(argv)
    generate_csv(args.subtitle, args.vocabular, args.output)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    main()
